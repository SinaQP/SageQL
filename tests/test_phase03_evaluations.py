"""Independent trajectory/scorer regressions; no live endpoint or credentials."""
from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
import socket
from types import SimpleNamespace

import pytest

from sageql import LLMConfig, Message
from sageql.sdk import DimensionDefinition
from sageql.sdk.evidence import request_evidence, evidence_feedback, evidence_question
from evaluations.phase03_hosts import workshop_catalog
from evaluations.reference import expected_report, facts
from evaluations.scoring import assess
from evaluations.trajectories import (
    LiveBudget, StageClient, fraction, load_trajectories, run_trajectory,
    summarize_trajectories, target_spec,
)


@pytest.fixture(scope="module")
def measured():
    def forbidden(*args, **kwargs):
        raise AssertionError("Default evaluation must not use the network")
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(socket.socket, "connect", forbidden)
        patch.setattr(socket.socket, "connect_ex", forbidden)
        patch.setattr(socket, "create_connection", forbidden)
        return {case["id"]: run_trajectory(case) for case in load_trajectories("phase03")}


@pytest.mark.parametrize("identifier", ["D01", "D04", "H12", "H25"])
def test_confirmed_scoped_defects_complete_independent_reports(identifier, measured):
    assert measured[identifier]["correct"], measured[identifier]


def test_custom_provider_cannot_execute_omitted_explicit_grouping(measured):
    turn = measured["D02"]["turns"][0]
    assert turn["status"] == "blocked" and turn["database_calls"] == 0
    assert not turn["accepted_specification_incorrect"]


@pytest.mark.parametrize("phrase", ["Billed amount by Service in July 2026",
    "Billed amount grouped by Service in July 2026", "دستمزد به تفکیک Service در ژوئیه ۲۰۲۶"])
def test_positive_grouping_is_independent_evidence(phrase):
    evidence = request_evidence((Message("user", phrase),), workshop_catalog())
    assert evidence.dimensions == (("jobs", "service"),)


@pytest.mark.parametrize("phrase", ["Billed amount for Service Repair in July 2026",
    'Billed amount; title "by Service"', "Remove Service grouping"])
def test_predicate_title_or_removal_does_not_require_grouping(phrase):
    evidence = request_evidence((Message("user", phrase),), workshop_catalog())
    assert not evidence.dimensions


def test_longest_grouping_label_is_selected_without_its_contained_label():
    catalog = workshop_catalog()
    dataset = catalog.datasets[0]
    catalog = replace(catalog, datasets=(replace(dataset, dimensions=(*dataset.dimensions,
        DimensionDefinition("service_category", "Service category", "service"))),))
    evidence = request_evidence((Message("user", "Billed amount by Service category in July 2026"),), catalog)
    assert evidence.dimensions == (("jobs", "service_category"),)


@pytest.mark.parametrize("phrase", ["Replace Billed amount with Completed jobs without Work minutes",
    "Swap Billed amount for Completed jobs; exclude Work minutes"])
def test_replacement_scope_preserves_an_independent_exclusion(phrase):
    evidence = request_evidence((Message("user", phrase),), workshop_catalog())
    assert evidence.metrics == (("jobs", "jobs_count"),)
    assert set(evidence.excluded_metrics) == {("jobs", "billed"), ("jobs", "minutes_total")}


def test_explicit_filter_retention_uses_current_typed_values_and_survives_clarification():
    from evaluations.phase03_hosts import TODAY
    case = next(c for c in load_trajectories("development") if c["id"] == "D04")
    current = target_spec(case, case["turns"][0])
    for text in ("Keep the Channel filter", "فیلتر Channel را نگه دار"):
        evidence = request_evidence((Message("user", text),), workshop_catalog(), current)
        assert evidence.retained_filters == current.filters
        assert evidence_feedback(evidence, replace(current, filters=()), TODAY) == "retained_filter_mismatch"
    message = Message("user", "Keep Channel filter; remove Channel filter")
    evidence = request_evidence((message,), workshop_catalog(), current)
    question = evidence_question(evidence, "en")
    assert question.status == "needs_clarification" and "filters" in question.question
    history = (message, Message("assistant", question.question))
    retained = request_evidence((*history, Message("user", "Keep Channel filter")), workshop_catalog(), current)
    assert retained.retained_filters == current.filters and not retained.excluded_filters
    removed = request_evidence((*history, Message("user", "Remove Channel filter")), workshop_catalog(), current)
    assert removed.excluded_filters == (("jobs", "channel_filter"),) and not removed.retained_filters


def test_independent_reference_totals_and_policy_exclusions():
    july = [r for r in facts("workshop") if "2026-07-01" <= r["completed"] < "2026-08-01"]
    assert sum(r["fee"] for r in july) == 860 and len(july) == 6
    assert sum(r["minutes"] for r in july) == 255
    assert not any(r.get("org") == "red" or r.get("voided") for r in july)
    assert any(r["shelf"] is None for r in facts("library"))


def test_frozen_cases_match_independently_recomputed_expected_data():
    for case in load_trajectories("phase03"):
        for turn in case["turns"]:
            if turn["expect"]["kind"] == "report":
                assert expected_report(case["domain"], turn["spec"], turn["expect"]["bounds"]) == turn["expect"]


def test_original_phase02_corpus_and_measurements_are_unchanged():
    assert Path("evaluations/cases.json").read_bytes() == Path("evaluations/baselines/phase02_cases.json").read_bytes()
    assert Path("evaluations/baseline.json").read_bytes() == Path("evaluations/baselines/phase02.json").read_bytes()


def test_frozen_corpus_separates_promotions_and_replacements():
    holdout = {c["id"] for c in load_trajectories("holdout")}
    development = {c["id"] for c in load_trajectories("development")}
    assert len(holdout) == 30 and len(development) == 6
    assert {"H12", "H25"} <= development and {"H31", "H32"} <= holdout
    assert not holdout & development
    assert Path("evaluations/phase03/cases.v1.json").exists()


@pytest.mark.parametrize("identifier", [case["id"] for case in load_trajectories("holdout")])
def test_frozen_holdout_scripts_preserve_each_turn_and_state(identifier, measured):
    assert measured[identifier]["correct"], measured[identifier]


def test_multi_turn_first_failure_cannot_be_erased_by_later_success(measured):
    broken = deepcopy(measured["H23"])
    broken["turns"][0]["correct"] = False
    broken["turns"][0]["outcome"] = "semantic_error"
    broken["correct"] = False
    result = summarize_trajectories([broken])
    assert result["trajectory_correctness"]["numerator"] == 0
    assert result["supported_completion"]["numerator"] == len(broken["turns"]) - 1


def test_no_incorrect_or_incomplete_report_receives_credit(measured):
    for case in measured.values():
        for turn in case["turns"]:
            if turn["accepted_specification_incorrect"]:
                assert not turn["correct"] and turn["outcome"] != "correct_report"
    summary = summarize_trajectories(list(measured.values()))
    assert summary["supported_completion"]["denominator"] == 42
    assert summary["tokens"] is None and summary["estimated_cost"] is None


def test_pipeline_experiments_distinguish_useful_and_unproductive_reviews(measured):
    assert measured["P01"]["correct"] and measured["P03"]["correct"] and measured["P04"]["correct"]
    # Phase 04 now preempts the faulty proposal before it reaches review. The
    # historical Phase 03 baselines retain the original false approval/rejection.
    assert measured["P01"]["turns"][0]["reviews"] == [{"candidate_correct": True, "approved": True}]
    assert measured["P03"]["turns"][0]["reviews"][0] == {"candidate_correct": True, "approved": False}
    assert measured["P02"]["correct"]
    assert measured["P02"]["turns"][0]["reviews"] == [{"candidate_correct": True, "approved": True}]
    assert measured["P02"]["turns"][0]["deterministic_rejections"] == 1


def test_denial_revocation_replay_and_operational_failures(measured):
    for identifier in ("H20", "H27"):
        turn = measured[identifier]["turns"][-1]
        assert turn["outcome"] == "correct_denial" and turn["database_calls"] == 0
        assert all(turn["checks"].values())
    for identifier in ("P05", "P06"):
        assert measured[identifier]["correct"]
        assert measured[identifier]["turns"][0]["outcome"] == "operational_failure"
    assert measured["P06"]["turns"][0]["database_calls"] == 1
    assert measured["P06"]["turns"][0]["reviews"] == [{"candidate_correct": True, "approved": True}]


def test_answer_keys_and_result_rows_never_enter_model_payload(monkeypatch):
    original = StageClient.create
    audited = []
    def inspect(self, **options):
        payload = json.loads(options["messages"][-1]["content"])
        def visit(value):
            if isinstance(value, dict):
                assert not {"expect", "requirements", "rows", "bounds", "exclusions"} & value.keys()
                for item in value.values():
                    visit(item)
            elif isinstance(value, list):
                for item in value:
                    visit(item)
        visit(payload)
        audited.append(True)
        return original(self, **options)
    monkeypatch.setattr(StageClient, "create", inspect)
    case = next(c for c in load_trajectories("holdout") if c["id"] == "H23")
    assert run_trajectory(case)["correct"] and len(audited) == 12


def test_artifacts_exclude_requests_answers_rows_sql_and_policy_values(measured):
    serialized = json.dumps(list(measured.values()))
    for token in ('"request"', '"blue"', '"workshop_jobs"', 'private synthetic transport exception'):
        assert token not in serialized
    for case in measured.values():
        for turn in case["turns"]:
            assert type(turn["checks"].get("rows", True)) is bool
            assert type(turn["requirements"].get("filters", True)) is bool


def approval(**changes):
    return {"authorized": True, "synthetic_only": True, "endpoint": "https://example.test/v1",
            "model": "fake", "max_requests": 1, "max_tokens": 100000, "max_seconds": 30,
            "max_cost_usd": "1", "pricing": {"reviewed": True, "source_url": "https://example.test/synthetic-pricing",
                "verified_at": "synthetic-test", "input_usd_per_million": "1", "output_usd_per_million": "2"}, **changes}


@pytest.mark.parametrize("changes", [{"authorized": False}, {"model": "other"}, {"max_requests": 0}, {"max_seconds": True}])
def test_live_requires_reviewed_matching_approval_and_budgets(changes):
    with pytest.raises(ValueError):
        LiveBudget(LLMConfig("synthetic", "https://example.test/v1", "fake"), approval(**changes))


def test_live_budget_prevents_dispatch_and_token_estimates_are_not_usage():
    budget = LiveBudget(LLMConfig("synthetic", "https://example.test/v1", "fake"), approval())
    options = {"messages": [{"role": "user", "content": "synthetic"}], "max_completion_tokens": 100}
    assert budget.reserve(options)[0] > 100
    with pytest.raises(RuntimeError):
        budget.reserve(options)
    assert budget.requests == 1 and budget.exhausted
    assert fraction(0, 0)["value"] is None


@pytest.mark.parametrize("changes", [{"max_tokens": 1}, {"max_cost_usd": "0.000000001"}])
def test_token_and_cost_caps_stop_before_transport(changes):
    budget = LiveBudget(LLMConfig("synthetic", "https://example.test/v1", "fake"), approval(**changes))
    with pytest.raises(RuntimeError):
        budget.reserve({"messages": [{"role": "user", "content": "synthetic"}]})
    assert budget.requests == 0


def test_stage_client_records_reported_tokens_without_exposing_payloads():
    response = SimpleNamespace(usage=SimpleNamespace(prompt_tokens=12, completion_tokens=7),
        choices=[SimpleNamespace(message=SimpleNamespace(content='{"metrics": []}'))])
    delegate = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **options: response)))
    client = StageClient(delegate)
    client.create(messages=[], response_format={"json_schema": {"name": "sageql_report_intent"}})
    assert client.records[0]["usage"] == {"input": 12, "output": 7}


def test_live_path_uses_only_injected_live_client_and_stops_with_checkpoint(monkeypatch):
    import sys
    from evaluations.trajectories import run_trajectories
    dispatched, checkpoints = [], []
    class UnavailableLiveClient:
        def __init__(self, **options):
            self.chat = SimpleNamespace(completions=self)
        def with_options(self, **options):
            return self
        def create(self, **options):
            dispatched.append(options)
            raise RuntimeError("synthetic live transport failure")
        def close(self):
            pass
    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=UnavailableLiveClient))
    cases = [c for c in load_trajectories("holdout") if c["id"] in {"H01", "H02", "H03"}]
    result = run_trajectories(cases, live_config=LLMConfig("synthetic", "https://example.test/v1", "fake"),
        approval=approval(), checkpoint=checkpoints.append)
    assert len(dispatched) == 1 and result["budget_exhausted"]
    assert result["summary"]["supported_completion"]["numerator"] == 0
    assert result["unexecuted_trajectories"] == 2
    assert checkpoints and result["results"][0]["turns"][0]["diagnosis"] == "provider_transport_failure"


def test_cli_live_requires_explicit_approval_without_constructing_client(monkeypatch, tmp_path):
    from evaluations.__main__ import main
    for key in ("SAGEQL_EVAL_API_KEY", "SAGEQL_EVAL_BASE_URL", "SAGEQL_EVAL_MODEL"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(SystemExit) as error:
        main(["--suite", "holdout", "--live", "--output", str(tmp_path / "live.json")])
    assert error.value.code == 2
