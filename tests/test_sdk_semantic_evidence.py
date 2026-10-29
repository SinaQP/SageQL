"""Independent request polarity regressions; no model approval is an oracle."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest

from examples import multi_domain as hosts
from sageql import LLMConfig, Message
from sageql.sdk import (
    ConceptRef, DimensionDefinition, Interpretation, MetricDefinition, OpenAIReportAgent,
    PeriodSelection, ReportIntent, SageQL, SQLiteSessionStore, UserFilter,
)
from sageql.sdk.business import explicit_measure_missing
from sageql.sdk.evidence import request_evidence
from sageql.sdk.phrases import ScopedText
from evaluations.runner import RecordingAdapter, ScriptedClient, extracted, ready


APPROVED = {"approved": True, "feedback": ""}


def engine_at(tmp_path, domain="retail", *, catalog=None, policy=None, responses=(), provider=None):
    scenario = next(item for item in hosts.scenarios() if item.name == domain)
    path = tmp_path / "facts.sqlite"
    scenario.create_data(path)
    adapter = RecordingAdapter(path)
    client = ScriptedClient(responses)
    provider = provider or OpenAIReportAgent(LLMConfig("synthetic", "https://example.test/v1", "fake"),
                                            client=client, language="en")
    engine = SageQL(catalog=catalog or scenario.catalog, database=adapter, provider=provider,
                    policy=policy or scenario.policy, clock=lambda: hosts.TODAY, execution="validated",
                    sessions=SQLiteSessionStore(tmp_path / "sessions.sqlite"), language="en")
    return engine, adapter, client


def submit(engine, message, *, session=None, request="first", revision=0):
    session = session or engine.create_session(hosts.ACTOR).session_id
    return engine.submit(session, message, hosts.ACTOR, request, revision)


def retail_spec(grain="none"):
    return replace(hosts.scenarios()[0].initial, chart="table", time_grain=grain,
                   order_by="department" if grain == "none" else "time_bucket", descending=False)


@pytest.mark.parametrize("text,grain,excluded", [
    ("Net sales by department, not daily", "none", ("day",)),
    ("Net sales by department; do not show it daily", "none", ("day",)),
    ("Monthly Net sales, not daily", "month", ("day",)),
    ("Not daily, but monthly Net sales", "month", ("day",)),
    ("فروش به تفکیک بخش، روزانه نباشد", "none", ("day",)),
    ("فروش ماهانه، نه روزانه", "month", ("day",)),
])
def test_grain_exclusions_are_not_positive_requirements(text, grain, excluded):
    evidence = request_evidence((Message("user", text),), hosts.retail_catalog())
    assert evidence.time_grain == grain
    assert evidence.forbidden_grains == excluded


@pytest.mark.parametrize("text", [
    "Show Net sales, but do not show the share of total.",
    "Net sales without shares of total.",
    "فروش را نشان بده؛ سهم از کل را نمایش نده.",
    'Show Net sales with the title "Share of total".',
])
def test_excluded_or_literal_shares_are_not_unavailable_requirements(text):
    evidence = request_evidence((Message("user", text),), hosts.retail_catalog())
    assert not evidence.operations


def test_exact_registered_participant_mean_needs_no_generic_mean_word():
    spec = ReportIntent(metrics=(ConceptRef("loans", "days_per_reader"),))
    messages = (Message("user", "Show Loan days per reader in September 2026"),)
    assert not explicit_measure_missing(spec, messages, None, hosts.library_catalog())


@pytest.mark.parametrize("phrase,polarity", [
    ("show daily", "positive"), ("not daily", "negative"),
    ("do not show it daily", "negative"), ("don't show daily", "negative"),
    ("no daily grouping", "negative"), ("exclude daily", "negative"),
    ("stop showing it daily", "negative"), ("daily is not wanted", "negative"),
    ("not only daily", "positive"), ("monthly instead of daily", "negative"),
    ("روزانه نباشد", "negative"), ("نه روزانه", "negative"),
    ("روزانه را نمایش نده", "negative"), ("بدون روزانه", "negative"),
    ('The example says "show daily"', "literal"),
    ('Show "daily"', "positive"), ('Use the title "daily"', "literal"),
    ('"daily"', "unresolved"), ('«روزانه» را نشان بده', "positive"),
    ('«روزانه» را نشان نده', "negative"),
    ('«روزانه» را در شهریور نشان بده', "positive"),
    ('«روزانه» را در شهریور نشان نده', "negative"),
])
def test_occurrence_scope_and_quote_roles(phrase, polarity):
    term = "روزانه" if "روزانه" in phrase else "daily"
    assert ScopedText(phrase).literal(term)[0].polarity == polarity


@pytest.mark.parametrize("phrase", [
    "not daily", "do not show it daily", "don't show it daily", "without daily grouping",
    "روزانه نباشد", "روزانه را نمایش نده", "نه روزانه",
])
def test_negated_daily_repairs_correlated_wrong_intent_and_plan_then_executes_exact_groups(tmp_path, phrase):
    correct = retail_spec()
    wrong = replace(correct, time_grain="day")
    engine, adapter, client = engine_at(tmp_path, responses=(
        extracted(wrong), ready(wrong), ready(correct), APPROVED))
    reply = submit(engine, "Net sales by department in September 2026; " + phrase)
    assert reply.status == "report_ready", reply.to_dict()
    assert reply.report.rows == (("Books", Decimal(70)), ("Garden", Decimal(45)))
    assert [field.id for field in reply.report.fields] == ["department", "revenue"]
    assert len(client.calls) == 4 and len(adapter.calls) == 1
    assert client.calls[-1]["response_format"]["json_schema"]["name"] == "sageql_report_review"


@pytest.mark.parametrize("phrase,grain", [
    ("Show daily", "day"), ("Show monthly, not daily", "month"),
    ("Not daily, but monthly", "month"), ("روزانه نباشد، ماهانه باشد", "month"),
    ('The example says "show daily"; show monthly', "month"),
    ('Use "daily" grouping', "day"),
])
def test_positive_and_quoted_grains_return_independent_actual_daily_or_monthly_data(tmp_path, phrase, grain):
    spec = retail_spec(grain)
    engine, adapter, _ = engine_at(tmp_path, responses=(extracted(spec), ready(spec), APPROVED))
    reply = submit(engine, phrase + " Net sales by department in September 2026")
    assert reply.status == "report_ready", reply.to_dict()
    expected = ((date(2026, 9, 1), "Books", Decimal(30)),
                (date(2026, 9, 2), "Books", Decimal(40)),
                (date(2026, 9, 2), "Garden", Decimal(45))) if grain == "day" else (
                (date(2026, 9, 1), "Books", Decimal(70)), (date(2026, 9, 1), "Garden", Decimal(45)))
    assert reply.report.rows == expected
    assert len(adapter.calls) == 1


@pytest.mark.parametrize("phrase", [
    "Net sales, not daily", "Net sales daily and not daily", "Net sales daily or monthly",
    'Net sales "daily"', "فروش روزانه و نه روزانه",
])
def test_conflicting_unresolved_or_replacement_free_grains_clarify_without_any_read(tmp_path, phrase):
    engine, adapter, client = engine_at(tmp_path)
    reply = submit(engine, phrase + " in September 2026")
    assert reply.status == "needs_clarification" and reply.clarification
    assert not adapter.calls and not client.calls and reply.report is None


@pytest.mark.parametrize("phrase", [
    "Net sales by department, not daily", "Net sales daily and not daily",
    "Net sales, not daily", "Remove Department grouping and show Net sales",
    "Show Quantity, do not include Net sales",
])
def test_custom_provider_cannot_bypass_final_exclusions_or_ambiguity(tmp_path, phrase):
    wrong = retail_spec("day") if "daily" in phrase else retail_spec()
    provider = SimpleNamespace(interpret=lambda *args: Interpretation("ready", wrong))
    engine, adapter, _ = engine_at(tmp_path, provider=provider)
    reply = submit(engine, phrase + " in September 2026")
    assert reply.status == "blocked" and reply.error["code"] == "intent_mismatch"
    assert reply.report is None and not adapter.calls


@pytest.mark.parametrize("phrase", [
    'Show "share of total" for Net sales', '«سهم از کل» را نشان بده',
    'Do not show share of total, but calculate another unsupported ratio',
    'Do not show share of total, but show entities with no records',
    'Do not show share of total, but show share of total anyway',
    'Show Net sales hourly',
])
def test_positive_unsupported_clause_is_never_hidden_by_other_negation_or_quotes(tmp_path, phrase):
    engine, adapter, client = engine_at(tmp_path)
    reply = submit(engine, phrase + " in September 2026")
    assert reply.status == "unsupported" and reply.report is None
    assert not client.calls and not adapter.calls


@pytest.mark.parametrize("phrase", [
    "Do not show share of total; show Net sales by department",
    "Omit share of total; show Net sales by department",
    "سهم از کل را نمایش نده؛ فروش را به تفکیک بخش نشان بده",
    'The example says "calculate share of total"; show Net sales by department',
])
def test_negated_or_literal_operations_do_not_activate_a_model_requirement_ledger(tmp_path, phrase):
    spec = retail_spec()
    intent = extracted(spec)
    quote = "سهم از کل" if "سهم" in phrase else "share of total"
    intent["unsupported_requirements"] = [{"operation": "percentage_share", "evidence": quote}]
    engine, adapter, client = engine_at(tmp_path, responses=(intent, ready(spec), APPROVED))
    reply = submit(engine, phrase + " in September 2026")
    assert reply.status == "report_ready", reply.to_dict()
    assert reply.report.rows == (("Books", Decimal(70)), ("Garden", Decimal(45)))
    assert len(adapter.calls) == 1
    assert json.loads(client.calls[1]["messages"][1]["content"])["intent"]["unsupported_requirements"] == []


@pytest.mark.parametrize("domain,label,alias,value", [
    ("library", "Loan days per reader", "Reader workload", 16),
    ("retail", "Sales per stock item", "Item revenue average", 57.5),
    ("library", "روزهای امانت به ازای خواننده", "بار امانت خواننده", 16),
    ("retail", "فروش به ازای کالا", "میانگین فروش کالا", 57.5),
])
@pytest.mark.parametrize("selection", ["label", "alias", "descriptive"])
def test_registered_mean_vocabulary_in_two_domains_uses_exact_independent_data(tmp_path, domain, label, alias, value, selection):
    scenario = next(item for item in hosts.scenarios() if item.name == domain)
    fact = scenario.catalog.datasets[0]
    metric = (replace(fact.metrics[2], label=label, selection_terms=(alias,)) if domain == "library" else
              MetricDefinition("per_stock", label, "sum_per_participant", "net_amount", "USD",
                               selection_terms=(alias,), participant_column="sku_code"))
    updated = replace(fact, metrics=tuple(item for item in fact.metrics if item.id != metric.id) + (metric,))
    catalog = replace(scenario.catalog, datasets=(updated, *scenario.catalog.datasets[1:]))
    spec = replace(scenario.initial, metric_ids=(metric.id,), dimension_ids=(), chart="table", order_by=None)
    term = label if selection != "alias" else alias
    phrase = ("mean " if selection == "descriptive" else "") + term
    engine, adapter, _ = engine_at(tmp_path, domain, catalog=catalog,
                                   responses=(extracted(spec), ready(spec), APPROVED))
    reply = submit(engine, "Show " + phrase + " in September 2026")
    assert reply.status == "report_ready", reply.to_dict()
    assert reply.report.rows == ((value,),) and len(adapter.calls) == 1


def test_mean_exclusion_does_not_remove_a_separately_requested_row_average(tmp_path):
    spec = replace(hosts.scenarios()[1].initial, metric_ids=("mean_duration",), dimension_ids=(), order_by=None)
    wrong = replace(spec, metric_ids=("mean_duration", "days_per_reader"))
    engine, adapter, _ = engine_at(tmp_path, "library", responses=(extracted(wrong), ready(spec), APPROVED))
    reply = submit(engine, "Show Mean loan duration, not Loan days per reader, in September 2026")
    assert reply.status == "report_ready", reply.to_dict()
    assert reply.report.rows == ((Decimal(8),),) and len(adapter.calls) == 1


def test_colliding_registered_aliases_clarify_instead_of_selecting_an_average(tmp_path):
    scenario = hosts.scenarios()[1]
    fact = scenario.catalog.datasets[0]
    catalog = replace(scenario.catalog, datasets=(replace(fact, metrics=tuple(
        replace(metric, selection_terms=("Shared average",)) if metric.id in {"mean_duration", "days_per_reader"} else metric
        for metric in fact.metrics)), *scenario.catalog.datasets[1:]))
    engine, adapter, client = engine_at(tmp_path, "library", catalog=catalog)
    reply = submit(engine, "Show Shared average in September 2026")
    assert reply.status == "needs_clarification" and not adapter.calls and not client.calls


def test_exact_vocabulary_does_not_grant_an_unauthorized_metric(tmp_path):
    scenario = hosts.scenarios()[1]
    spec = replace(scenario.initial, metric_ids=("days_per_reader",), dimension_ids=(), order_by=None)
    def policy(actor):
        scope = scenario.policy(actor)
        return replace(scope, datasets=tuple(replace(access, metric_ids=("borrowings",))
                        if access.dataset_id == "loans" else access for access in scope.datasets))
    engine, adapter, _ = engine_at(tmp_path, "library", policy=policy,
        provider=SimpleNamespace(interpret=lambda *args: Interpretation("ready", spec)))
    reply = submit(engine, "Show Loan days per reader in September 2026")
    assert reply.status == "blocked" and reply.error["code"] == "access_denied" and not adapter.calls


@pytest.mark.parametrize("label", ["Daily revenue", "Share of total"])
def test_registered_label_is_an_existing_metric_not_a_grain_or_new_formula(tmp_path, label):
    scenario = hosts.scenarios()[0]
    fact = scenario.catalog.datasets[0]
    catalog = replace(scenario.catalog, datasets=(replace(fact, metrics=(replace(fact.metrics[0], label=label), *fact.metrics[1:])),
                                                  *scenario.catalog.datasets[1:]))
    spec = replace(retail_spec(), dimension_ids=(), order_by=None)
    engine, adapter, _ = engine_at(tmp_path, catalog=catalog, responses=(extracted(spec), ready(spec), APPROVED))
    reply = submit(engine, "Show " + label + " in September 2026")
    assert reply.status == "report_ready", reply.to_dict()
    assert reply.report.rows == ((Decimal(115),),) and len(adapter.calls) == 1


def test_longer_mean_label_wins_without_silently_requesting_contained_row_average(tmp_path):
    scenario = hosts.scenarios()[1]
    fact = scenario.catalog.datasets[0]
    catalog = replace(scenario.catalog, datasets=(replace(fact, metrics=tuple(
        replace(metric, label="Loan days", selection_terms=()) if metric.id == "mean_duration" else metric
        for metric in fact.metrics)), *scenario.catalog.datasets[1:]))
    spec = replace(scenario.initial, metric_ids=("days_per_reader",), dimension_ids=(), order_by=None)
    wrong = replace(spec, metric_ids=("mean_duration",))
    engine, adapter, client = engine_at(tmp_path, "library", catalog=catalog,
        responses=(extracted(wrong), ready(wrong), ready(spec), APPROVED))
    reply = submit(engine, "Show Loan days per reader in September 2026")
    assert reply.status == "report_ready", reply.to_dict()
    assert reply.report.rows == ((16.0,),) and len(adapter.calls) == 1 and len(client.calls) == 4


def test_unregistered_alias_suffix_is_not_accepted_as_an_exact_selection(tmp_path):
    scenario = hosts.scenarios()[1]
    spec = replace(scenario.initial, metric_ids=("days_per_reader",), dimension_ids=(), order_by=None)
    engine, adapter, client = engine_at(tmp_path, "library", responses=(extracted(spec),))
    reply = submit(engine, "Show per readership in September 2026")
    assert reply.status == "needs_clarification" and not adapter.calls and len(client.calls) == 1


def test_numeric_letters_and_jalali_monthly_exclusion_preserve_independent_bounds(tmp_path):
    spec = replace(retail_spec("jalali_month"), period=PeriodSelection("jalali_month", year=1405, month=6))
    engine, adapter, _ = engine_at(tmp_path, responses=(extracted(spec), ready(spec), APPROVED))
    reply = submit(engine, "فروش ماهانه به تفکیک بخش در شهريور ١٤٠٥؛ روزانه نباشد")
    assert reply.status == "report_ready", reply.to_dict()
    assert reply.report.rows == ((date(2026, 8, 23), "Books", Decimal(70)), (date(2026, 8, 23), "Garden", Decimal(45)))
    assert (adapter.calls[0].period.start, adapter.calls[0].period.end) == (date(2026, 8, 23), date(2026, 9, 23))


def test_grain_removal_refinement_survives_restart_and_receipt_without_extra_reads(tmp_path):
    daily, total = retail_spec("day"), replace(retail_spec(), order_by=None)
    engine, adapter, client = engine_at(tmp_path, responses=(extracted(daily), ready(daily), APPROVED,
        extracted(daily, turn_kind="refine"), ready(daily), ready(total), APPROVED))
    first = submit(engine, "Show daily Net sales by department in September 2026")
    assert first.status == "report_ready"
    engine.sessions = SQLiteSessionStore(tmp_path / "sessions.sqlite")
    question = "Use the previous report, but remove daily grouping"
    refined = submit(engine, question, session=first.session_id, request="remove", revision=first.revision)
    assert refined.status == "report_ready", refined.to_dict()
    assert refined.report.rows == (("Books", Decimal(70)), ("Garden", Decimal(45)))
    assert len(adapter.calls) == 2 and len(client.calls) == 7
    again = submit(engine, question, session=first.session_id, request="remove", revision=first.revision)
    assert again.to_dict() == refined.to_dict() and len(adapter.calls) == 2 and len(client.calls) == 7
    assert engine.get_report(first.session_id, first.report.id, hosts.ACTOR).rows == first.report.rows


def test_dimension_removal_is_bound_to_the_refinement_not_the_old_report(tmp_path):
    grouped = retail_spec()
    total = replace(grouped, dimension_ids=(), order_by=None)
    engine, adapter, _ = engine_at(tmp_path, responses=(extracted(grouped), ready(grouped), APPROVED,
        extracted(grouped, turn_kind="refine"), ready(total), APPROVED))
    first = submit(engine, "Show Net sales by Department in September 2026")
    refined = submit(engine, "Remove Department grouping; keep Net sales", session=first.session_id,
                     request="remove", revision=first.revision)
    assert refined.status == "report_ready", refined.to_dict()
    assert refined.report.rows == ((Decimal(115),),) and len(adapter.calls) == 2


def test_failed_correlated_refinement_preserves_previous_success_and_never_replays(tmp_path):
    daily = retail_spec("day")
    engine, adapter, _ = engine_at(tmp_path, responses=(extracted(daily), ready(daily), APPROVED))
    first = submit(engine, "Show daily Net sales by department in September 2026")
    engine.provider = SimpleNamespace(interpret=lambda *args: Interpretation("ready", daily))
    question = "Show monthly Net sales by department, not daily"
    failed = submit(engine, question, session=first.session_id, request="bad", revision=first.revision)
    assert failed.status == "blocked" and failed.revision == first.revision and failed.report is None
    assert engine.get_session(first.session_id, hosts.ACTOR)["last_report_id"] == first.report.id
    assert engine.get_report(first.session_id, first.report.id, hosts.ACTOR).rows == first.report.rows
    assert len(adapter.calls) == 1
    assert submit(engine, question, session=first.session_id, request="bad", revision=first.revision).to_dict() == failed.to_dict()
    assert len(adapter.calls) == 1


def test_ambiguous_grain_answer_advances_and_repeating_ambiguity_stops_locally(tmp_path):
    monthly = replace(retail_spec("month"), dimension_ids=())
    engine, adapter, client = engine_at(tmp_path, responses=(extracted(monthly, turn_kind="answer"), ready(monthly), APPROVED))
    first = submit(engine, "Show Net sales in September 2026, not daily")
    assert first.status == "needs_clarification" and not client.calls
    final = submit(engine, "monthly", session=first.session_id, request="answer", revision=first.revision)
    assert final.status == "report_ready", final.to_dict()
    assert final.report.rows == ((date(2026, 9, 1), Decimal(115)),)
    assert len(adapter.calls) == 1
    # A new session's second unresolved answer must not loop forever.
    session = engine.create_session(hosts.ACTOR)
    pending = submit(engine, "Net sales, not daily", session=session.session_id)
    stalled = submit(engine, "still not daily", session=session.session_id, request="again", revision=pending.revision)
    assert stalled.error["code"] == "clarification_stalled" and len(adapter.calls) == 1


def test_pending_semantic_question_keeps_original_period_for_every_provider(tmp_path):
    engine, adapter, _ = engine_at(tmp_path)
    first = submit(engine, "Show Net sales in September 2026, not daily")
    assert first.status == "needs_clarification"
    wrong = replace(retail_spec("month"), dimension_ids=(), period=PeriodSelection("month", year=2027, month=8))
    engine.sessions = SQLiteSessionStore(tmp_path / "sessions.sqlite")
    engine.provider = SimpleNamespace(interpret=lambda *args: Interpretation("ready", wrong))
    reply = submit(engine, "monthly", session=first.session_id, request="answer", revision=first.revision)
    assert reply.status == "blocked" and reply.error["code"] == "intent_mismatch"
    assert not adapter.calls and reply.report is None


def test_unrelated_answer_does_not_discard_pending_grain_exclusion(tmp_path):
    engine, adapter, client = engine_at(tmp_path)
    first = submit(engine, "Show Net sales in September 2026, not daily")
    reply = submit(engine, "as a table", session=first.session_id, request="answer", revision=first.revision)
    assert reply.error["code"] == "clarification_stalled" and not adapter.calls and not client.calls


@pytest.mark.parametrize("answer,expected", [("It is only an example", "report_ready"),
                                            ("It is a requested operation", "unsupported")])
def test_explicit_quote_role_answer_resolves_the_pending_question(tmp_path, answer, expected):
    spec = retail_spec()
    engine, adapter, client = engine_at(tmp_path, responses=(extracted(spec, turn_kind="answer"), ready(spec), APPROVED))
    first = submit(engine, '"Share of total"; Net sales by Department in September 2026')
    assert first.status == "needs_clarification" and not client.calls
    reply = submit(engine, answer, session=first.session_id, request="answer", revision=first.revision)
    assert reply.status == expected, reply.to_dict()
    if expected == "report_ready":
        assert reply.report.rows == (("Books", Decimal(70)), ("Garden", Decimal(45)))
        assert len(adapter.calls) == 1
    else:
        assert not adapter.calls and not client.calls


def test_unspecified_average_exclusion_cannot_be_silently_ignored_by_custom_provider(tmp_path):
    spec = replace(hosts.scenarios()[1].initial, metric_ids=("borrowings", "mean_duration"), dimension_ids=(), order_by=None)
    engine, adapter, _ = engine_at(tmp_path, "library",
        provider=SimpleNamespace(interpret=lambda *args: Interpretation("ready", spec)))
    reply = submit(engine, "Show Borrowings in September 2026, without a mean")
    assert reply.status == "blocked" and reply.error["code"] == "intent_mismatch" and not adapter.calls


def test_generic_mean_removal_is_unambiguous_for_one_current_mean(tmp_path):
    initial = replace(hosts.scenarios()[1].initial, metric_ids=("borrowings", "mean_duration"), dimension_ids=(), order_by=None)
    totals = replace(initial, metric_ids=("borrowings",))
    engine, adapter, _ = engine_at(tmp_path, "library", responses=(extracted(initial), ready(initial), APPROVED,
        extracted(initial, turn_kind="refine"), ready(totals), APPROVED))
    first = submit(engine, "Show Borrowings and Mean loan duration in September 2026")
    assert first.status == "report_ready"
    reply = submit(engine, "Remove the mean from the previous report", session=first.session_id, request="remove", revision=first.revision)
    assert reply.status == "report_ready", reply.to_dict()
    assert reply.report.rows == ((4,),) and len(adapter.calls) == 2


@pytest.mark.parametrize("removed,rows", [("filter", (("Books", Decimal(70)), ("Garden", Decimal(45)))),
                                        ("grouping", ((Decimal(70),),))])
def test_filter_and_dimension_removal_are_different_refinements(tmp_path, removed, rows):
    initial = replace(retail_spec(), filters=(UserFilter("department_filter", "eq", ("Books",)),))
    target = replace(initial, filters=()) if removed == "filter" else replace(initial, dimension_ids=(), order_by=None)
    engine, adapter, _ = engine_at(tmp_path, responses=(extracted(initial), ready(initial), APPROVED,
        extracted(initial, turn_kind="refine"), ready(target), APPROVED))
    first = submit(engine, "Net sales by Department for Books in September 2026")
    assert first.report.rows == (("Books", Decimal(70)),)
    reply = submit(engine, "Remove Department " + removed, session=first.session_id, request="remove", revision=first.revision)
    assert reply.status == "report_ready", reply.to_dict()
    assert reply.report.rows == rows and len(adapter.calls) == 2


@pytest.mark.parametrize("explicit_date_dimension", [False, True])
def test_raw_registered_report_date_dimension_cannot_bypass_not_daily(tmp_path, explicit_date_dimension):
    scenario = hosts.scenarios()[0]
    fact = scenario.catalog.datasets[0]
    dimensions = (*[dim for dim in fact.dimensions if dim.column not in fact.related_columns],
                  DimensionDefinition("sale_day", "Sale day", "sold_on"),
                  *[dim for dim in fact.dimensions if dim.column in fact.related_columns])
    catalog = replace(scenario.catalog, datasets=(replace(fact, dimensions=dimensions), *scenario.catalog.datasets[1:]))
    wrong = replace(retail_spec(), dimension_ids=("department", "sale_day"))
    engine, adapter, _ = engine_at(tmp_path, catalog=catalog,
        provider=SimpleNamespace(interpret=lambda *args: Interpretation("ready", wrong)))
    wording = "Net sales by Department" + (" and Sale day" if explicit_date_dimension else "")
    reply = submit(engine, wording + " in September 2026, not daily")
    assert reply.status == "blocked" and reply.error["code"] == "intent_mismatch" and not adapter.calls


def test_grain_then_year_answers_do_not_lose_the_original_named_month(tmp_path):
    spec = replace(retail_spec("month"), dimension_ids=())
    engine, adapter, _ = engine_at(tmp_path, responses=(extracted(spec, period=None, missing=("year",), turn_kind="answer"),
        {"status": "needs_clarification", "spec": None, "question": "Which year?", "message": ""}, APPROVED))
    first = submit(engine, "Show Net sales in September, not daily")
    second = submit(engine, "monthly", session=first.session_id, request="grain", revision=first.revision)
    assert second.status == "needs_clarification", second.to_dict()
    wrong = replace(spec, period=PeriodSelection("month", year=2026, month=8))
    engine.provider = SimpleNamespace(interpret=lambda *args: Interpretation("ready", wrong))
    reply = submit(engine, "2026", session=first.session_id, request="year", revision=second.revision)
    assert reply.status == "blocked" and reply.error["code"] == "intent_mismatch" and not adapter.calls
