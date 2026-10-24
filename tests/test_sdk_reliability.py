"""Complete-or-transparent reporting through the public SDK in unrelated hosts."""

from dataclasses import replace
import json
from types import SimpleNamespace

import pytest

from sageql import LLMConfig, Message
from sageql.sdk import (
    ActorContext, ConceptRef, Interpretation, OpenAIReportAgent, PeriodSelection,
    ReportIntent, SDKError, SageQL, UnsupportedRequirement,
)
from sageql.sdk.agents import AgentReportInterpreter, AgentReview
from sageql.sdk.evidence import request_evidence
from test_sdk_application_independence import (
    Client, RecordingAdapter, demo, host, intent, ready,
)


APPROVED = {"approved": True, "feedback": ""}


def sdk(host, client, **options):
    scenario, path, _ = host
    provider = OpenAIReportAgent(LLMConfig("synthetic", "https://example.test/v1", "fake"),
        client=client, language="en", **options)
    return SageQL(catalog=scenario.catalog, database=RecordingAdapter(path), provider=provider,
        policy=scenario.policy, clock=lambda: demo.TODAY, language="en", execution="validated")


def submit(engine, text, *, session=None, revision=0, request="first", actor=demo.ACTOR):
    session = session or engine.create_session(actor).session_id
    return engine.submit(session, text, actor, request, revision)


@pytest.mark.parametrize("text,period,comparison", [
    ("September 2026 versus August", PeriodSelection("month", year=2026, month=9), PeriodSelection("month", year=2026, month=8)),
    ("August 2026 compared with September 2025", PeriodSelection("month", year=2026, month=8), PeriodSelection("month", year=2025, month=9)),
    ("شهریور ۱۴۰۵ نسبت به مرداد", PeriodSelection("jalali_month", year=1405, month=6), PeriodSelection("jalali_month", year=1405, month=5)),
    ("شهریور نسبت به مرداد ١٤٠٥", PeriodSelection("jalali_month", year=1405, month=6), PeriodSelection("jalali_month", year=1405, month=5)),
    ("Shahrivar 1405 versus Mordad", PeriodSelection("jalali_month", year=1405, month=6), PeriodSelection("jalali_month", year=1405, month=5)),
    ("September 2026 compared to August", PeriodSelection("month", year=2026, month=9), PeriodSelection("month", year=2026, month=8)),
    ("Shahrivar 1405 compared with September 2026", PeriodSelection("jalali_month", year=1405, month=6), PeriodSelection("month", year=2026, month=9)),
])
def test_explicit_comparison_repairs_wrong_intent_and_rejects_wrong_plan_before_reads(host, text, period, comparison):
    scenario = host[0]
    correct = replace(scenario.initial, dimension_ids=(), chart="table", time_grain="none",
                      period=period, comparison=comparison, order_by=None)
    wrong = replace(correct, period=PeriodSelection("month", year=2027, month=11),
                    comparison=PeriodSelection("month", year=2027, month=10))
    client = Client(intent(wrong), ready(wrong), ready(correct), APPROVED)
    engine = sdk(host, client)
    reply = submit(engine, text)
    assert reply.status == "report_ready", reply.to_dict()
    assert len(engine.database.calls) == 1
    assert engine.database.calls[0].spec.period == period
    assert engine.database.calls[0].spec.comparison == comparison
    assert len(client.calls) == 4
    assert "period_mismatch" in json.loads(client.calls[2]["messages"][1]["content"])["feedback"][0]


@pytest.mark.parametrize("text,period,grain", [
    ("Monthly totals from January through September 2026", PeriodSelection("range", "2026-01-01", "2026-10-01"), "month"),
    ("از فروردین تا شهریور ۱۴۰۵ در هر ماه", PeriodSelection("range", "2026-03-21", "2026-09-23"), "jalali_month"),
])
def test_monthly_evidence_recovers_yearly_intent_without_rejecting_correct_candidate(host, text, period, grain):
    scenario = host[0]
    report = replace(scenario.initial, dimension_ids=(), chart="table", time_grain=grain, period=period, order_by=None)
    client = Client(intent(report, time_grain="year"), ready(report), APPROVED)
    engine = sdk(host, client)
    reply = submit(engine, text)
    assert reply.status == "report_ready", reply.to_dict()
    assert len(client.calls) == 3 and len(engine.database.calls) == 1
    assert engine.database.calls[0].spec.time_grain == grain


@pytest.mark.parametrize("text,operation", [
    ("Show the top groups and their percentage of the total in September 2026", "shares of a total"),
    ("در شهریور ۱۴۰۵ مجموع را با سهم آن‌ها از کل نشان بده", "shares of a total"),
    ("Show entities with no records in September 2026", "without related records"),
    ("در شهریور ۱۴۰۵ کدام موجودیت‌ها هیچ رکوردی ثبت نکرده‌اند؟", "without related records"),
    ("For each group show the primary category in September 2026", "within each group"),
    ("Show monthly totals and which month had the highest and lowest total in September 2026", "time-series extrema"),
    ("Compare September 2026 versus August versus July", "more than two periods"),
])
def test_unsupported_complete_request_is_terminal_without_any_model_or_database_loop(host, text, operation):
    client = Client()
    engine = sdk(host, client, max_revisions=3)
    result = submit(engine, text)
    assert result.status == "unsupported" and operation in result.text
    assert not client.calls and not engine.database.calls and result.report is None


def test_unrecognized_language_requirement_uses_typed_ledger_and_user_evidence(host):
    scenario = host[0]
    quote = "Anteil am Gesamtwert"
    request = intent(scenario.initial)
    request["unsupported_requirements"] = [{"operation": "percentage_share", "evidence": quote}]
    client = Client(request)
    engine = sdk(host, client)
    result = submit(engine, "September 2026: " + quote)
    assert result.status == "unsupported" and len(client.calls) == 1
    assert not engine.database.calls


def test_fabricated_requirement_evidence_fails_without_exposing_model_text(host):
    request = intent(host[0].initial)
    request["unsupported_requirements"] = [{"operation": "formula", "evidence": "private invented evidence"}]
    client = Client(request)
    engine = sdk(host, client)
    result = submit(engine, "September 2026")
    assert result.error == {"code": "invalid_interpretation", "retryable": False, "stage": "intent", "reason": "requirements"}
    assert "private invented" not in json.dumps(result.to_dict()) and not engine.database.calls


def test_exact_host_metric_label_cannot_be_dropped_from_intent_or_final_report(host):
    scenario = host[0]
    metrics = scenario.catalog.datasets[0].metrics[:2]
    complete = replace(scenario.initial, metric_ids=tuple(item.id for item in metrics), chart="table")
    incomplete = replace(complete, metric_ids=complete.metric_ids[:1], order_by=complete.metric_ids[0])
    client = Client(intent(incomplete), ready(incomplete), ready(complete), APPROVED)
    engine = sdk(host, client)
    result = submit(engine, "September 2026: show " + " and ".join(item.label for item in metrics))
    assert result.status == "report_ready", result.to_dict()
    assert engine.database.calls[0].spec.metric_ids == complete.metric_ids
    assert len(client.calls) == 4


@pytest.mark.parametrize("text", ["September 2026", "شهریور ۱۴۰۵", "Monthly totals in September 2026"])
def test_custom_provider_cannot_bypass_final_explicit_evidence_gate(host, text):
    scenario = host[0]
    wrong = replace(scenario.initial, period=PeriodSelection("month", year=2027, month=12))
    engine = sdk(host, Client())
    engine.provider = SimpleNamespace(interpret=lambda *args: Interpretation("ready", wrong))
    result = submit(engine, text)
    assert result.status == "blocked" and result.error["code"] == "intent_mismatch"
    assert result.error["stage"] == "semantic_validation" and not engine.database.calls


def test_year_clarification_anchors_original_period_despite_wrong_second_intent(host):
    scenario = host[0]
    report = scenario.initial
    client = Client(intent(report, period=None, missing=("year",)),
        {"status": "needs_clarification", "spec": None, "question": "Which year?", "message": ""}, APPROVED,
        intent(report, period=None, missing=("year",), turn_kind="answer"), ready(report), APPROVED)
    engine = sdk(host, client)
    first = submit(engine, "September")
    assert first.status == "needs_clarification" and not engine.database.calls
    result = submit(engine, "۲۰۲۶", session=first.session_id, revision=1, request="year")
    assert result.status == "report_ready", result.to_dict()
    assert result.report.rows == scenario.expected


def test_intent_reconsideration_repairs_root_of_repeated_semantic_conflict(host):
    scenario = host[0]
    correct = intent(scenario.initial)
    wrong = {**correct, "chart": "table" if scenario.initial.chart != "table" else "bar"}
    client = Client(wrong, ready(scenario.initial), ready(scenario.initial), correct, ready(scenario.initial), APPROVED)
    engine = sdk(host, client, max_revisions=3)
    result = submit(engine, scenario.question + " 2026")
    assert result.status == "report_ready", result.to_dict()
    assert len(client.calls) == 6 and len(engine.database.calls) == 1
    repair = json.loads(client.calls[3]["messages"][1]["content"])
    assert repair["consistency_feedback"] == ["intent_validation: chart_mismatch"]


class RawClient(Client):
    def create(self, **options):
        self.calls.append(options)
        value = next(self.responses)
        if isinstance(value, Exception):
            raise value
        raw = value if isinstance(value, str) else json.dumps(value)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=raw))])


@pytest.mark.parametrize("invalid,reason", [
    ("not JSON: private secret", "json_syntax"),
    ({"unregistered": "private secret"}, "response_shape"),
])
def test_opted_in_structured_repair_is_bounded_and_never_echoes_rejected_output(host, invalid, reason):
    scenario = host[0]
    client = RawClient(invalid, intent(scenario.initial), ready(scenario.initial), APPROVED)
    engine = sdk(host, client, max_structured_repairs=1)
    result = submit(engine, scenario.question + " 2026")
    assert result.status == "report_ready", result.to_dict()
    assert len(client.calls) == 4
    assert "private secret" not in json.dumps(client.calls)
    broken = RawClient(invalid, invalid)
    engine = sdk(host, broken, max_structured_repairs=1)
    failed = submit(engine, scenario.question + " 2026")
    assert failed.error["stage"] == "intent" and failed.error["reason"] == reason
    assert len(broken.calls) == 2 and not engine.database.calls


def test_transport_failure_is_not_a_structured_repair_or_database_failure(host):
    client = RawClient(RuntimeError("private endpoint credential"))
    engine = sdk(host, client, max_structured_repairs=1)
    result = submit(engine, "September 2026")
    assert result.error["code"] == "provider_failed" and result.error["retryable"]
    assert len(client.calls) == 1 and not engine.database.calls
    assert "credential" not in json.dumps(result.to_dict())


def test_database_connection_failure_does_not_replan_retry_or_publish_and_new_request_can_recover(host):
    scenario = host[0]
    client = Client(intent(scenario.initial), ready(scenario.initial), APPROVED,
                    intent(scenario.initial), ready(scenario.initial), APPROVED)
    engine = sdk(host, client)
    original = engine.database
    attempts = []
    def unavailable(*args, **kwargs):
        attempts.append(True)
        raise SDKError("database_unavailable", "Database unavailable.", retryable=True,
                       stage="database_connection", reason="unavailable")
    engine.database = SimpleNamespace(execute=unavailable)
    first = submit(engine, scenario.question + " 2026")
    assert first.status == "failed" and first.error["stage"] == "database_connection"
    assert first.revision == 0 and first.report is None and attempts == [True]
    engine.database = original
    recovered = submit(engine, scenario.question + " 2026", session=first.session_id, request="recover")
    assert recovered.status == "report_ready" and recovered.report.rows == scenario.expected


def test_authorization_is_checked_before_evidence_shortcuts(host):
    engine = sdk(host, Client())
    session = engine.create_session(demo.ACTOR).session_id
    denied = submit(engine, "Show shares of the total", session=session, actor=ActorContext("other"))
    assert denied.error["code"] == "access_denied" and not engine.database.calls


def test_structured_repair_allowance_is_shared_across_stages(host):
    report = host[0].initial
    client = RawClient("invalid private intent", intent(report), "invalid private plan")
    engine = sdk(host, client, max_structured_repairs=1)
    result = submit(engine, "September 2026")
    assert result.error["stage"] == "planning" and result.error["reason"] == "json_syntax"
    assert len(client.calls) == 3 and not engine.database.calls
    assert "private" not in json.dumps(result.to_dict())


def test_review_structured_repair_preserves_the_exact_checked_candidate(host):
    report = host[0].initial
    client = RawClient(intent(report), ready(report), {"approved": 1, "feedback": ""}, APPROVED)
    engine = sdk(host, client, max_structured_repairs=1)
    result = submit(engine, "September 2026")
    assert result.status == "report_ready" and len(client.calls) == 4
    assert client.calls[2]["messages"] == client.calls[3]["messages"]
    assert len(engine.database.calls) == 1


def test_assistant_cannot_supply_missing_named_month_year(host):
    report = host[0].initial
    client = Client(intent(report),
        {"status": "needs_clarification", "spec": None, "question": "Which year?", "message": ""}, APPROVED)
    provider = sdk(host, client).provider
    result = provider.interpret((Message("assistant", "Use September 2026."), Message("user", "September")),
                                None, host[0].catalog, demo.TODAY)
    assert result.status == "needs_clarification"
    planned_intent = json.loads(client.calls[1]["messages"][1]["content"])["intent"]
    assert planned_intent["period"] is None and "year" in planned_intent["missing"]


def test_failed_reconsideration_never_relaxes_explicit_periods(host):
    report = host[0].initial
    wrong = replace(report, period=PeriodSelection("month", year=2027, month=11))
    client = Client(intent(wrong), ready(wrong), ready(wrong), intent(wrong), ready(wrong))
    engine = sdk(host, client, max_revisions=3)
    result = submit(engine, "September 2026")
    assert result.error["code"] == "intent_mismatch" and result.error["reason"] == "repeated_conflict"
    assert len(client.calls) == 5 and not engine.database.calls


def test_removing_an_unsupported_part_can_start_a_supported_report(host):
    report = host[0].initial
    client = Client(intent(report), ready(report), APPROVED)
    engine = sdk(host, client)
    first = submit(engine, "September 2026 totals and share of the total")
    assert first.status == "unsupported" and not client.calls
    result = submit(engine, "September 2026 totals without shares of the total",
                    session=first.session_id, revision=1, request="supported")
    assert result.status == "report_ready", result.to_dict()


def test_single_highest_time_bucket_remains_ordinary_supported_ranking(host):
    report = replace(host[0].initial, dimension_ids=(), chart="table", time_grain="month", limit=1,
                     order_by=host[0].initial.metric_ids[0], descending=True)
    client = Client(intent(report), ready(report), APPROVED)
    engine = sdk(host, client)
    result = submit(engine, "Which month had the highest total in September 2026?")
    assert result.status == "report_ready", result.to_dict()


def test_invented_comparison_cannot_execute_even_when_models_agree(host):
    report = host[0].initial
    invented = replace(report, chart="table", comparison=PeriodSelection("month", year=2026, month=8))
    client = Client(intent(invented), ready(invented), ready(invented))
    engine = sdk(host, client)
    result = submit(engine, "September 2026 totals")
    assert result.error["code"] == "intent_mismatch" and not engine.database.calls


def test_structured_repair_keeps_the_original_deadline(host, monkeypatch):
    ticks = [100.0]
    monkeypatch.setattr("sageql.sdk.agents.time.monotonic", lambda: ticks[0])
    class Slow(RawClient):
        def create(self, **options):
            ticks[0] += 4
            return super().create(**options)
    client = Slow("invalid", intent(host[0].initial))
    provider = sdk(host, client, max_structured_repairs=1, timeout_seconds=6).provider
    with pytest.raises(SDKError) as failed:
        provider.interpret((Message("user", "September 2026"),), None, host[0].catalog, demo.TODAY)
    assert failed.value.code == "request_timeout" and len(client.calls) == 2
    assert client.calls[0]["timeout"] == 6 and client.calls[1]["timeout"] == 2


@pytest.mark.parametrize("text,period", [
    ("Totals from 2026-09-01 before 2026-10-01", PeriodSelection("range", "2026-09-01", "2026-10-01")),
    ("Totals from 2026-09-01 through 2026-09-30 inclusive", PeriodSelection("range", "2026-09-01", "2026-10-01")),
    ("Totals on 2026-09-02", PeriodSelection("range", "2026-09-02", "2026-09-03")),
    ("از ۱۴۰۵/۰۶/۰۱ تا ۱۴۰۵/۰۶/۳۱ شمسی", PeriodSelection("jalali_range", "1405-06-01", "1405-06-31")),
])
def test_explicit_date_only_bounds_are_not_model_conversions(host, text, period):
    report = replace(host[0].initial, period=period)
    wrong = replace(report, period=PeriodSelection("month", year=2027, month=1))
    client = Client(intent(wrong), ready(report), APPROVED)
    engine = sdk(host, client)
    result = submit(engine, text)
    assert result.status == "report_ready", result.to_dict()
    assert engine.database.calls[0].spec.period == period and len(client.calls) == 3


def test_english_modal_may_is_not_a_month_requirement(host):
    report = host[0].initial
    client = Client(intent(report), ready(report), APPROVED)
    engine = sdk(host, client)
    result = submit(engine, "May I see the report for September 2026?")
    assert result.status == "report_ready", result.to_dict()


def test_ambiguous_numeric_calendar_cannot_be_replaced_by_a_model_guess(host):
    report = host[0].initial
    client = Client(intent(report), {"status": "needs_clarification", "spec": None,
        "question": "Which calendar?", "message": ""}, APPROVED)
    engine = sdk(host, client)
    result = submit(engine, "Totals on 1405-06-01")
    assert result.status == "needs_clarification" and not engine.database.calls


@pytest.mark.parametrize("changes,field,reason", [
    ({"limit": True}, "limit", "intent_constraints"),
    ({"comparison_specified": 1}, "comparison_specified", "intent_constraints"),
    ({"metrics": [{"dataset_id": "unknown", "concept_id": "private concept"}]}, "metrics", "concept_reference"),
    ({"period": PeriodSelection("range", "private invalid date", "2026-10-01").__dict__}, "period", "period_selection"),
])
def test_invalid_intent_diagnoses_a_safe_field_without_logging_values(host, changes, field, reason):
    request = {**intent(host[0].initial), **changes}
    client = Client(request)
    engine = sdk(host, client)
    failed = submit(engine, "September 2026")
    assert failed.error["stage"] == "intent" and failed.error["reason"] == reason
    assert failed.error["field"] == field and len(client.calls) == 1
    assert "private" not in json.dumps(failed.to_dict()) and not engine.database.calls


def test_plan_observation_excludes_invalid_date_strings_and_filter_values(host):
    report = host[0].initial
    bad = replace(report, period=PeriodSelection("range", "private invalid date", "2026-10-01"))
    client = Client(intent(report), ready(bad), ready(report), APPROVED)
    events = []
    engine = sdk(host, client, observer=lambda stage,status,**details: events.append((stage,status,details)))
    result = submit(engine, "September 2026")
    assert result.status == "report_ready" and "private invalid date" not in json.dumps(events)
    plans = [details for stage,status,details in events if stage == "agent_plan" and status == "complete"]
    assert plans[0]["period"] == {"valid": False, "kind": "range"}
    assert plans[1]["period"] == report.period.__dict__


@pytest.mark.parametrize("language,expected", [("en", "shares of a total"), ("fa", "سهم از کل")])
def test_custom_provider_subset_is_actionable_unsupported_in_both_reply_languages(host, language, expected):
    engine = sdk(host, Client())
    engine.language = language
    engine.provider = SimpleNamespace(interpret=lambda *args: Interpretation("ready", host[0].initial))
    result = submit(engine, "September 2026 totals and share of the total")
    assert result.status == "unsupported" and expected in result.text
    assert not engine.database.calls


def test_named_gregorian_month_overrides_host_calendar_preference_for_buckets(host):
    report = replace(host[0].initial, dimension_ids=(), time_grain="month", chart="table", order_by=None)
    client = Client(intent(report, time_grain="jalali_month"), ready(report), APPROVED)
    engine = sdk(host, client)
    engine.catalog = replace(engine.catalog, preferred_calendar="jalali")
    result = submit(engine, "Monthly totals in September 2026")
    assert result.status == "report_ready", result.to_dict()


@pytest.mark.parametrize("text", [
    "Totals on 2026-02-30", "Totals on 1405-13-01 Jalali",
    "از ۱۴۰۵/۰۶/۳۱ تا ۱۴۰۵/۰۶/۰۱ شمسی", "شهریور ۱۲۰۰",
])
def test_invalid_user_date_evidence_requests_correction_without_blame_or_model_loop(host, text):
    client = Client()
    engine = sdk(host, client)
    result = submit(engine, text)
    assert result.status == "needs_clarification" and result.error is None
    assert "valid date range" in result.text and not client.calls and not engine.database.calls


def test_reconsidered_unavailable_combination_is_terminal_before_another_plan(host):
    scenario = host[0]
    source = scenario.catalog.datasets[1]
    imports = {getattr(item, "source_dimension_id", None) for item in scenario.catalog.datasets[0].dimensions
               if getattr(item, "source_dataset_id", None) == source.id}
    unimported = next(item for item in source.dimensions if item.id not in imports)
    good = intent(scenario.initial)
    wrong = {**good, "chart": "table" if scenario.initial.chart != "table" else "bar"}
    unavailable = {**good, "dimensions": [*good["dimensions"],
        {"dataset_id": source.id, "concept_id": unimported.id}]}
    client = Client(wrong, ready(scenario.initial), ready(scenario.initial), unavailable)
    engine = sdk(host, client, max_revisions=3)
    result = submit(engine, "September 2026")
    assert result.status == "unsupported" and len(client.calls) == 4
    assert not engine.database.calls


def test_repeated_ambiguous_host_metric_labels_do_not_invent_a_dataset_selection(host):
    scenario = host[0]
    fact = scenario.catalog.datasets[0]
    other = replace(fact, id="another_fact", metrics=(replace(fact.metrics[0], id="another_metric"),))
    registered = replace(scenario.catalog, datasets=(*scenario.catalog.datasets, other))
    text = (fact.metrics[0].label + " ") * 400 + "September 2026"
    evidence = request_evidence((Message("user", text),), registered)
    assert evidence.metrics == ()
