"""The evaluator must detect incorrect data even when all model stages approve."""

import json
from pathlib import Path
import socket

import pytest

from evaluations.__main__ import main
from evaluations.history import inventory
from evaluations.runner import load_cases, run
from evaluations.scoring import assess, rows_match, summarize


CASES = load_cases()
RESOLVED = {"known_negated_daily", "known_negated_share", "known_exact_mean_label"}
ORIGINAL = json.loads((Path(__file__).parents[1] / "evaluations/baselines/phase01_cases.json").read_text(encoding="utf-8"))["cases"]


@pytest.fixture(scope="module")
def measured():
    with pytest.MonkeyPatch.context() as patch:
        def no_network(*args, **kwargs):
            raise AssertionError("Offline evaluation attempted network access")
        patch.setattr(socket.socket, "connect", no_network)
        patch.setattr(socket.socket, "connect_ex", no_network)
        patch.setattr(socket, "create_connection", no_network)
        return run()


@pytest.mark.parametrize("case", CASES, ids=lambda x: x["id"])
def test_case_matches_explicit_baseline_without_network(case, measured):
    result = next(x for x in measured["results"] if x["id"] == case["id"])
    assert result["meets_baseline"], result
    assert result["checks"]["source_unchanged"]
    assert result["checks"]["receipt"]
    assert result["checks"]["payload_isolation"]


@pytest.mark.parametrize("case", [case for case in CASES if case["id"] in RESOLVED], ids=lambda x: x["id"])
def test_known_supported_requests_should_complete(case, measured):
    result = next(x for x in measured["results"] if x["id"] == case["id"])
    assert result["outcome"] == "correct_report", result


def test_summary_keeps_refusal_failure_and_report_populations_separate(measured):
    original_ids = {case["id"] for case in ORIGINAL}
    summary = summarize([result for result in measured["results"] if result["id"] in original_ids])
    assert summary["supported_completion"] == {"numerator": 20, "denominator": 20, "value": 1}
    assert summary["outcomes"]["correct_unsupported"] == 2
    assert summary["outcomes"]["operational_failure"] == 2
    assert summary["known_failures"] == 0 and summary["new_regressions"] == 0
    assert summary["model_calls"] == 78 and summary["database_calls"] == 24
    assert measured["live_model_status"] == "not_executed"
    assert summary["recovery_effectiveness"]["numerator"] == 2
    assert summary["unauthorized_prevention"]["denominator"] == 1
    assert summary["recovery_attempts"] == {"planning_revisions": 2, "structured_repairs": 1, "intent_reconsiderations": 0}
    assert measured["summary"]["supported_completion"]["denominator"] == 40
    assert measured["summary"]["new_regressions"] == 0


def test_original_expectations_and_supported_population_are_preserved():
    current = {case["id"]: case for case in CASES}
    assert RESOLVED <= set(current)
    for original in ORIGINAL:
        assert current[original["id"]]["expect"] == original["expect"]
        assert current[original["id"]]["request"] == original["request"]
    assert not any(case.get("known_issue") for case in CASES)


@pytest.fixture
def scored_report():
    expected = {"kind": "report", "fields": ["category", "total"],
                "types": ["text", "decimal"], "rows": [["Books", "70"]], "chart": "table"}
    reply = {"status": "report_ready", "assistant": {"text": "Total by category"}, "error": None,
             "report": {"fields": [{"id": "category", "type": "text"}, {"id": "total", "type": "decimal"}],
                        "rows": [["Books", "70.00"]], "visualization": {"kind": "table"}, "truncated": False}}
    return expected, reply


@pytest.mark.parametrize("mutation,outcome", [
    ("wrong_total", "semantic_error"), ("wrong_group", "semantic_error"),
    ("missing_metric", "incomplete"), ("missing_row", "incomplete"),
    ("truncated", "incomplete"), ("wrong_chart", "semantic_error"),
    ("no_report", "incomplete"), ("false_success_text", "semantic_error"),
    ("wrong_type", "semantic_error"), ("wrong_axis", "semantic_error"),
])
def test_approval_and_success_status_cannot_hide_mutated_results(scored_report, mutation, outcome):
    expected, reply = scored_report
    if mutation == "wrong_total":
        reply["report"]["rows"][0][1] = "71"
    elif mutation == "wrong_group":
        reply["report"]["rows"][0][0] = "Garden"
    elif mutation == "missing_metric":
        reply["report"]["fields"].pop()
        reply["report"]["rows"] = [["Books"]]
    elif mutation == "missing_row":
        reply["report"]["rows"] = []
    elif mutation == "truncated":
        reply["report"]["truncated"] = True
    elif mutation == "wrong_chart":
        reply["report"]["visualization"]["kind"] = "bar"
    elif mutation == "no_report":
        reply["report"] = None
    elif mutation == "wrong_type":
        reply["report"]["fields"][1]["type"] = "text"
    elif mutation == "wrong_axis":
        reply["report"]["visualization"]["value"] = "unknown_metric"
    else:
        reply["assistant"]["text"] = ""
    assert assess(expected, reply).outcome == outcome


def test_expected_topn_is_not_confused_with_accidental_partial_report(scored_report):
    expected, reply = scored_report
    expected["truncated"] = True
    reply["report"]["truncated"] = True
    assert assess(expected, reply).outcome == "correct_report"


def test_decimal_comparison_preserves_precision_and_rejects_nonfinite_or_boolean():
    fields = [{"id": "x", "type": "decimal"}]
    assert rows_match(fields, [["12345678901234567890.01"]], [["12345678901234567890.010"]])
    assert not rows_match(fields, [["12345678901234567890.01"]], [["12345678901234567890.02"]])
    assert not rows_match(fields, [["NaN"]], [["NaN"]])
    assert not rows_match(fields, [[True]], [[1]])
    assert summarize([])["supported_completion"]["value"] is None


def test_unsupported_does_not_count_as_report_completion(scored_report):
    expected, _ = scored_report
    reply = {"status": "unsupported", "report": None, "assistant": {"text": "Unavailable"}}
    assert assess(expected, reply).outcome == "incorrect_rejection"
    assert assess({"kind": "unsupported"}, reply).outcome == "correct_unsupported"


def test_success_for_unauthorized_request_is_an_unexpected_report(scored_report):
    _, reply = scored_report
    assert assess({"kind": "denial"}, reply).outcome == "unexpected_report"
    assert assess({"kind": "unsupported"}, reply).outcome == "unexpected_report"


def test_cli_strict_mode_accepts_resolved_case_and_emits_no_rows(tmp_path):
    path = tmp_path / "evaluation.json"
    assert main(["--case", "known_negated_share", "--strict", "--output", str(path)]) == 0
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["summary"]["known_failures"] == 0
    assert "rows" not in result["results"][0] and "request" not in result["results"][0]


def test_cli_original_cohort_and_compact_artifact_keep_measured_denominators(tmp_path):
    path = tmp_path / "original.json"
    assert main(["--cohort", "phase01", "--compact", "--strict", "--output", str(path)]) == 0
    result = json.loads(path.read_text(encoding="utf-8"))
    assert result["summary"]["cases"] == 27
    assert result["summary"]["supported_completion"]["denominator"] == 20
    assert all("stages" not in row and "turns" not in row for row in result["results"])


def test_live_transport_requires_explicit_flag_and_configuration(monkeypatch, tmp_path):
    for name in ("SAGEQL_EVAL_API_KEY", "SAGEQL_EVAL_BASE_URL", "SAGEQL_EVAL_MODEL"):
        monkeypatch.delenv(name, raising=False)
    with pytest.raises(SystemExit) as error:
        main(["--live", "--output", str(tmp_path / "live.json")])
    assert error.value.code == 2
    assert not (tmp_path / "live.json").exists()


def write_history(path):
    question = "synthetic confidential question"
    record = {"test": 1, "question": question, "status": "report_ready", "report_produced": True,
              "row_count": 1, "status_classification": "PASS", "numeric_match": True,
              "requested_complete": True, "date_match": True, "source_stable": True,
              "independent_reference_complete": True}
    values = {
        "questions.json": [{"test": 1, "question": question}],
        "verification_results.json": [record], "pipeline_summary.json": [record],
        "expected_results.json": {"1": {"rows": [{"x": "private result"}], "bounds": ["2026-09-01", "2026-10-01"]}},
        "test_01_reply.json": {"status": "report_ready", "report": {"rows": [["private result"]],
            "provenance": {"period_start": "2026-09-01", "period_end_exclusive": "2026-10-01"}}},
    }
    for name, value in values.items():
        (path / name).write_text(json.dumps(value), encoding="utf-8")
    return values


def test_historical_inventory_retains_provenance_without_copying_private_content(tmp_path):
    write_history(tmp_path)
    result = inventory(tmp_path)
    assert result["evidence_consistent"] and not result["data_correctness_reexecuted"]
    assert result["summary"]["recorded_outcomes"] == {"PASS": 1}
    assert "confidential" not in json.dumps(result) and "private result" not in json.dumps(result)
    assert result["live_model_status"] == "not_executed"


@pytest.mark.parametrize("change", ["question", "bounds", "unstable", "unsupported_with_report"])
def test_inconsistent_historical_evidence_cannot_be_imported_as_verified(tmp_path, change):
    files = write_history(tmp_path)
    if change == "question":
        files["questions.json"][0]["question"] = "different"
    elif change == "bounds":
        files["expected_results.json"]["1"]["bounds"][0] = "2026-08-01"
    elif change == "unstable":
        files["verification_results.json"][0]["source_stable"] = False
    else:
        files["verification_results.json"][0]["status_classification"] = "UNSUPPORTED"
    for name, value in files.items():
        (tmp_path / name).write_text(json.dumps(value), encoding="utf-8")
    assert not inventory(tmp_path)["evidence_consistent"]
