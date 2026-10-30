"""Manager acceptance: synthetic sources, real compilers, fake model transport."""

from dataclasses import replace
from datetime import date
import json
import sqlite3
from types import SimpleNamespace

import pytest

from sageql import LLMConfig, Message
from sageql.sdk import (
    AccessScope, ActorContext, AggregateFilter, ConceptRef, DatasetAccess,
    ExecutionLimits, Interpretation, OpenAIReportAgent, PeriodSelection, ReportIntent,
    ReportSpec, RowPolicy, SDKError, SageQL, SQLiteAdapter, SQLiteSessionStore, UserFilter,
)
from sageql.sdk.adapters import compile_report
from sageql.sdk.calendars import jalali_to_gregorian
from sageql.sdk.lookups import prepare_request
from sageql.sdk.provider import _metadata
from sageql.sdk.semantics import permitted_catalog, resolve_period, validate_catalog
from sageql.sdk.periods import relative_period_evidence
from sageql.sdk.business import measure_question
# The private Rahtal host supplies this catalog; it is not published.
pytest.importorskip("sageql_rahtal")
from sageql_rahtal.sdk import rahtal_reporting_catalog  # noqa: E402


TODAY = date(2026, 10, 11)
ACTOR = ActorContext("synthetic-manager")


@pytest.mark.parametrize("message, expected", [
    ("یک ماه گذشته", PeriodSelection("jalali_rolling", count=1, unit="month")),
    ("توی ۶ ماه گذشته", PeriodSelection("jalali_rolling", count=6, unit="month")),
    ("شش ماه اخیر", PeriodSelection("jalali_rolling", count=6, unit="month")),
    ("ماه قبل", PeriodSelection("last_jalali_month")),
    ("این ماه", PeriodSelection("this_jalali_month")),
    ("امسال", PeriodSelection("this_jalali_year")),
    ("سال گذشته", PeriodSelection("last_jalali_year")),
    ("یک ماه میلادی گذشته", PeriodSelection("rolling", count=1, unit="month")),
    ("ماه قبل میلادی", PeriodSelection("last_month")),
    ("مقایسه ماه قبل و این ماه", None),
    ("شهریور", None),
    ("سه ماه شمسی و میلادی گذشته", None),
])
def test_relative_phrase_evidence_is_calendar_aware_and_not_an_inferred_year(message, expected):
    assert relative_period_evidence(message, "jalali") == expected


def test_local_relative_evidence_corrects_wrong_initial_model_period():
    correct = spec(period=PeriodSelection("jalali_rolling", count=1, unit="month"))
    client = Client(intent(replace(correct, period=PeriodSelection("last_jalali_month"))),
                    decision(correct), {"approved": True, "feedback": ""})
    result = agent(client).interpret((Message("user", "مجموع کار هر موضوع در یک ماه گذشته"),), None,
                                    permitted_catalog(rahtal_reporting_catalog(), scope()), TODAY)
    assert result.spec.period == correct.period
    planned = json.loads(client.calls[1]["messages"][1]["content"])
    assert planned["intent"]["period"]["kind"] == "jalali_rolling"


@pytest.mark.parametrize("message", ["روند مجموع ساعات در شش ماه گذشته ماه به ماه شمسی",
                                     "فقط مجموع ساعات در شش ماه گذشته ماه به ماه شمسی"])
def test_rolling_month_count_cannot_become_a_chart_row_limit(message):
    correct = spec(metric_ids=("activity_hours",), dimension_ids=(), time_grain="jalali_month", chart="line",
                   period=PeriodSelection("jalali_rolling", count=6, unit="month"), order_by="time_bucket", descending=False)
    client = Client(intent(correct, time_grain="jalali_month", limit=6), decision(correct),
                    {"approved": True, "feedback": ""})
    result = agent(client).interpret((Message("user", message),), None,
                                    permitted_catalog(rahtal_reporting_catalog(), scope()), TODAY)
    assert result.spec.limit == 100
    assert json.loads(client.calls[1]["messages"][1]["content"])["intent"]["limit"] == 100


def test_explicit_series_point_limit_is_preserved():
    correct = spec(metric_ids=("activity_hours",), dimension_ids=(), time_grain="jalali_month", chart="line", limit=3,
                   period=PeriodSelection("jalali_rolling", count=6, unit="month"), order_by="time_bucket", descending=False)
    client = Client(intent(correct, time_grain="jalali_month", limit=3), decision(correct),
                    {"approved": True, "feedback": ""})
    result = agent(client).interpret((Message("user", "روند شش ماه گذشته فقط سه نقطه در نمودار"),), None,
                                    permitted_catalog(rahtal_reporting_catalog(), scope()), TODAY)
    assert result.spec.limit == 3


@pytest.mark.parametrize("wording", ["ماه به ماه شمسی", "ماهانه"])
def test_monthly_intent_uses_explicit_or_host_preferred_persian_calendar(wording):
    correct = spec(metric_ids=("activity_hours",), dimension_ids=(), time_grain="jalali_month", chart="line",
                   period=PeriodSelection("jalali_rolling", count=6, unit="month"), order_by="time_bucket", descending=False)
    client = Client(intent(correct, time_grain="month", chart="line"), decision(correct),
                    {"approved": True, "feedback": ""})
    result = agent(client).interpret((Message("user", "مجموع ساعت شش ماه گذشته " + wording),), None,
                                    permitted_catalog(rahtal_reporting_catalog(), scope()), TODAY)
    assert result.spec == correct


def test_explicit_gregorian_monthly_report_remains_available():
    correct = spec(metric_ids=("activity_hours",), dimension_ids=(), time_grain="month", chart="line",
                   period=PeriodSelection("rolling", count=6, unit="month"), order_by="time_bucket", descending=False)
    client = Client(intent(correct, time_grain="month", chart="line"), decision(correct),
                    {"approved": True, "feedback": ""})
    result = agent(client).interpret((Message("user", "مجموع ساعت شش ماه میلادی گذشته ماه به ماه میلادی"),), None,
                                    permitted_catalog(rahtal_reporting_catalog(), scope()), TODAY)
    assert result.spec == correct


def test_grouping_refinement_cannot_invent_a_different_period_even_if_both_models_agree():
    current = spec(period=PeriodSelection("range", start="2026-09-10", end="2026-10-12"))
    correct = replace(current, dimension_ids=("activity_topic",))
    wrong = replace(correct, period=PeriodSelection("last_month"))
    client = Client(intent(wrong, turn_kind="refine"), decision(correct), {"approved": True, "feedback": ""})
    result = agent(client).interpret((Message("user", "همین گزارش را فقط به تفکیک موضوع جمع بزن"),), current,
                                    permitted_catalog(rahtal_reporting_catalog(), scope()), TODAY)
    assert result.spec.period == current.period


def scope():
    return AccessScope((DatasetAccess("activities", policies=(RowPolicy("is_deleted", "eq", (False,)),)),
                        DatasetAccess("employees", policies=(RowPolicy("is_deleted", "eq", (False,)),)),
                        DatasetAccess("activity_topics", policies=(RowPolicy("id", "neq", (3,)),))))


def spec(**changes):
    return replace(ReportSpec("activities", ("activity_hours", "activity_count"),
                              ("activity_topic", "employee_name"),
                              period=PeriodSelection("last_jalali_month"),
                              order_by="activity_hours", descending=True), **changes)


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "synthetic-manager.sqlite"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE functionality_activities
                (id int NOT NULL, user_id int, date date, time float, is_deleted bit, title_id bigint);
            CREATE TABLE persons_person
                (user_id int, first_name nvarchar, last_name nvarchar, job_position nvarchar, is_deleted bit);
            CREATE TABLE core_titleactivity (id bigint NOT NULL, name nvarchar NOT NULL);
            INSERT INTO core_titleactivity VALUES (1,'Design'), (2,'Support'), (3,'Restricted');
            INSERT INTO persons_person VALUES (1,'Test','One','Engineering',0), (2,'Test','Two','Operations',0);
            INSERT INTO functionality_activities VALUES
                (1,1,'2026-08-22',100,0,1),
                (2,1,'2026-08-23',1,0,1),
                (3,1,'2026-09-10',2,0,1),
                (4,2,'2026-09-22',4,0,1),
                (5,1,'2026-09-22',8,0,2),
                (6,1,'2026-09-23',16,0,1),
                (7,1,'2026-09-10',999,1,1),
                (8,2,'2026-09-10',32,0,3);
        """)
    return path


def execute(database, request):
    prepared = prepare_request(rahtal_reporting_catalog("main"), request, scope(), TODAY)
    return SQLiteAdapter(database).execute(prepared[0], ExecutionLimits())


@pytest.mark.parametrize("period, start, end", [
    (PeriodSelection("last_jalali_month"), "2026-08-23", "2026-09-23"),
    (PeriodSelection("this_jalali_month"), "2026-09-23", "2026-10-23"),
    (PeriodSelection("this_jalali_year"), "2026-03-21", "2027-03-21"),
    (PeriodSelection("last_jalali_year"), "2025-03-21", "2026-03-21"),
    (PeriodSelection("jalali_year", year=1403), "2024-03-20", "2025-03-21"),
    (PeriodSelection("jalali_range", start="1403-12-30", end="1404-01-01"), "2025-03-20", "2025-03-22"),
    (PeriodSelection("jalali_range", start="1405-07-19", end="1405-07-19"), "2026-10-11", "2026-10-12"),
    (PeriodSelection("jalali_rolling", count=1, unit="month"), "2026-09-10", "2026-10-12"),
    (PeriodSelection("jalali_rolling", count=6, unit="month"), "2026-04-08", "2026-10-12"),
    (PeriodSelection("jalali_rolling", count=1, unit="year"), "2025-10-11", "2026-10-12"),
])
def test_manager_date_windows_use_local_persian_boundaries(period, start, end):
    resolved = resolve_period(period, TODAY)
    assert (resolved.start.isoformat(), resolved.end.isoformat()) == (start, end)


def test_relative_month_clamps_day_and_rolls_over_year():
    resolved = resolve_period(PeriodSelection("jalali_rolling", count=1, unit="month"),
                              jalali_to_gregorian(1404, 1, 31))
    assert resolved.start == jalali_to_gregorian(1403, 12, 30)
    assert resolve_period(PeriodSelection("last_jalali_month"), date(2026, 3, 21)).start == date(2026, 2, 20)


@pytest.mark.parametrize("period", [
    PeriodSelection("jalali_range", start="1404-12-30", end="1405-01-01"),
    PeriodSelection("jalali_range", start="1405-07-31", end="1405-08-01"),
    PeriodSelection("jalali_range", start="1405-07-20", end="1405-07-19"),
    PeriodSelection("jalali_range", start="2026-09-01", end="2026-10-01"),
    PeriodSelection("jalali_range", start="1405-7-1", end="1405-07-02"),
    PeriodSelection("jalali_year", year=True),
    PeriodSelection("last_jalali_month", year=1405),
    PeriodSelection("jalali_rolling", count=True, unit="month"),
    PeriodSelection("jalali_rolling", count=1201, unit="month"),
    PeriodSelection("jalali_rolling", count=1200, unit="year"),
    PeriodSelection("jalali_rolling", count=1, unit=["month"]),
    PeriodSelection("rolling", count=1, unit={"unit": "month"}),
])
def test_invalid_persian_dates_fail_closed(period):
    with pytest.raises(SDKError) as error:
        resolve_period(period, TODAY)
    assert error.value.code == "invalid_spec"


def test_topic_contributions_sum_every_activity_and_apply_source_policy(database):
    result = execute(database, spec(dimension_ids=("activity_topic", "employee_id")))
    assert result.rows == ((None, 2, 32.0, 1), ("Support", 1, 8.0, 1),
                           ("Design", 2, 4.0, 1), ("Design", 1, 3.0, 2))
    assert not result.truncated


def test_shared_topics_count_distinct_people_before_ranking(database):
    request = spec(metric_ids=("activity_hours", "activity_count", "participant_count"),
                   dimension_ids=("activity_topic",),
                   aggregate_filters=(AggregateFilter("participant_count", "gte", (2,)),), limit=1)
    result = execute(database, request)
    assert result.rows == (("Design", 7.0, 3, 2),) and not result.truncated


def test_duplicate_topic_keys_block_totals_even_outside_returned_top_n(database):
    with sqlite3.connect(database) as connection:
        connection.execute("INSERT INTO core_titleactivity VALUES (1,'Duplicate')")
    with pytest.raises(SDKError) as error:
        execute(database, spec(dimension_ids=("activity_topic",), limit=1))
    assert error.value.code == "relationship_cardinality"


def test_topic_access_is_required_and_names_are_not_model_results():
    catalog = rahtal_reporting_catalog()
    denied = replace(scope(), datasets=scope().datasets[:2])
    visible = permitted_catalog(catalog, denied)
    assert "activity_topic" not in {d.id for d in visible.datasets[0].dimensions}
    public = json.dumps(_metadata(permitted_catalog(catalog, scope())))
    assert "core_titleactivity" not in public and "title_id" not in public
    assert "Test One" not in public and "Design" not in public


def test_denied_default_measures_are_removed_from_model_and_local_capabilities():
    access = scope()
    limited = replace(access, datasets=(replace(access.datasets[0], metric_ids=("activity_count",)), *access.datasets[1:]))
    visible = permitted_catalog(rahtal_reporting_catalog(), limited)
    assert visible.datasets[0].default_metric_ids == ("activity_count",)
    assert "activity_hours" not in json.dumps(_metadata(visible))
    result = agent(Client()).interpret((Message("user", "سلام"),), None, visible, TODAY)
    assert "مجموع ساعات فعالیت" not in result.question and "تعداد فعالیت" in result.question


def test_invalid_metric_identity_cannot_crash_default_measure_validation():
    catalog = rahtal_reporting_catalog()
    dataset = replace(catalog.datasets[0], metrics=(replace(catalog.datasets[0].metrics[0], id={}),))
    with pytest.raises(SDKError) as error:
        validate_catalog(replace(catalog, datasets=(dataset, *catalog.datasets[1:])))
    assert error.value.code == "invalid_catalog"


def test_persian_monthly_totals_do_not_use_gregorian_months(database):
    request = spec(metric_ids=("activity_hours",), dimension_ids=(),
                   period=PeriodSelection("jalali_range", start="1405-05-31", end="1405-07-01"),
                   time_grain="jalali_month", order_by="time_bucket", descending=False)
    result = execute(database, request)
    assert result.rows == ((date(2026, 7, 23), 100.0), (date(2026, 8, 23), 47.0),
                           (date(2026, 9, 23), 16.0))


def test_persian_month_ctes_preserve_tsql_bind_order_with_related_policy(database):
    request = spec(dimension_ids=("activity_topic",), time_grain="jalali_month",
                   comparison=PeriodSelection("jalali_month", year=1405, month=5))
    prepared = prepare_request(rahtal_reporting_catalog(), request, scope(), TODAY)
    query = compile_report(prepared[0], ExecutionLimits(), dialect="tsql")
    assert query.parameters[:6] == (date(2026, 7, 23), date(2026, 8, 23),
                                    date(2026, 8, 23), date(2026, 9, 23), 3, 101)
    assert query.sql.count("?") == len(query.parameters)
    assert "COUNT_BIG(*)" in query.sql and "GROUP BY calendar.[bucket]" in query.sql
    result = execute(database, request)
    assert {row[0] for row in result.rows} == {"base", "comparison"}


@pytest.mark.parametrize("period", [PeriodSelection("all"),
                                    PeriodSelection("jalali_range", start="1380-01-01", end="1405-07-01")])
def test_persian_monthly_grouping_is_bounded(period):
    with pytest.raises(SDKError) as error:
        prepare_request(rahtal_reporting_catalog(), spec(period=period, time_grain="jalali_month"), scope(), TODAY)
    assert error.value.code == "unsupported"


class Client:
    def __init__(self, *responses):
        self.responses = iter(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **options):
        return self

    def create(self, **options):
        self.calls.append(options)
        result = next(self.responses)
        if isinstance(result, ReportIntent):
            result = result.to_dict()
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(result)))])


def intent(request, **changes):
    return replace(ReportIntent(metrics=tuple(ConceptRef(request.dataset_id, m) for m in request.metric_ids),
                                dimensions=tuple(ConceptRef(request.dataset_id, d) for d in request.dimension_ids),
                                period=request.period), **changes)


def decision(request):
    return {"status": "ready", "spec": request.to_dict(), "question": "", "message": ""}


def agent(client):
    return OpenAIReportAgent(LLMConfig("fake", "https://example.test/v1", "fake"), client=client)


@pytest.mark.parametrize("message, calls", [("بهترین بازدهی در شش ماه گذشته", 0), ("گزارش فعالیت‌های روزانه ماه قبل", 1),
                                            ("مجموع ساعت‌های فعالیت ماه قبل", 1), ("best productivity in six months", 0)])
def test_hallucinated_average_gets_business_clarification_without_reads(database, message, calls):
    average = spec(metric_ids=("average_activity_hours",), dimension_ids=("employee_name",), order_by="average_activity_hours")
    client = Client(intent(average))
    engine = SageQL(catalog=rahtal_reporting_catalog("main"), database=SQLiteAdapter(database),
                    provider=agent(client), policy=lambda actor: scope(), clock=lambda: TODAY, execution="validated")
    session = engine.create_session(ACTOR)
    reply = engine.submit(session.session_id, message, ACTOR, "quality", 0)
    assert reply.status == "needs_clarification" and reply.report is None
    assert "مجموع ساعات" in reply.text and "تعداد فعالیت" in reply.text
    assert len(client.calls) == calls


def test_assistant_average_suggestion_does_not_count_as_user_evidence():
    average = spec(metric_ids=("average_activity_hours",), order_by="average_activity_hours")
    client = Client(intent(average, turn_kind="answer"))
    result = agent(client).interpret((Message("user", "بازدهی ماه قبل"),
                                     Message("assistant", "میانگین ساعت را حساب کنم؟"), Message("user", "بله")),
                                    None, permitted_catalog(rahtal_reporting_catalog(), scope()), TODAY)
    assert result.status == "needs_clarification" and len(client.calls) == 1


@pytest.mark.parametrize("message", ["میانگین مدت فعالیت‌ها در ماه قبل", "متوسط ساعت هر فعالیت", "average activity duration"])
def test_explicit_average_is_available_and_instructions_include_business_defaults(message):
    average = spec(metric_ids=("average_activity_hours",), order_by="average_activity_hours")
    client = Client(intent(average), decision(average), {"approved": True, "feedback": ""})
    result = agent(client).interpret((Message("user", message),), None,
                                    permitted_catalog(rahtal_reporting_catalog(), scope()), TODAY)
    assert result.spec == average
    for call in client.calls:
        payload = json.loads(call["messages"][1]["content"])
        assert payload["catalog"]["preferred_calendar"] == "jalali"
        assert payload["catalog"]["datasets"][0]["default_metric_ids"] == ["activity_hours", "activity_count"]
        assert "Never substitute average duration for productivity" in payload["catalog"]["datasets"][0]["description"]
        assert "jalali_range" in call["messages"][0]["content"]


def test_capability_question_explains_manager_reports_without_model_or_data_calls():
    client = Client(ReportIntent(missing=("request",)))
    result = agent(client).interpret((Message("user", "سلام چه کارهایی می‌تونی انجام بدی؟"),), None,
                                    permitted_catalog(rahtal_reporting_catalog(), scope()), TODAY)
    assert result.status == "needs_clarification" and len(client.calls) == 0
    assert "موضوع فعالیت" in result.question and "تاریخ‌های شمسی" in result.question


@pytest.mark.parametrize("metric", ["activity_hours", "activity_count"])
def test_vague_quality_cannot_rank_by_any_available_default(metric):
    ranked = spec(metric_ids=(metric,), dimension_ids=("employee_name",), order_by=metric, limit=1)
    client = Client(intent(ranked, order_by=metric, ordering_specified=True, limit=1))
    result = agent(client).interpret((Message("user", "بهترین بازدهی در شش ماه گذشته؟"),), None,
                                    permitted_catalog(rahtal_reporting_catalog(), scope()), TODAY)
    assert result.status == "needs_clarification" and len(client.calls) == 0


def test_candidate_cannot_hide_an_unjustified_ranking_from_intent():
    ranked = spec(dimension_ids=("employee_name",), limit=1)
    client = Client(intent(ranked), decision(ranked))
    result = agent(client).interpret((Message("user", "نفر اول را نشان بده"),), None,
                                    permitted_catalog(rahtal_reporting_catalog(), scope()), TODAY)
    assert result.status == "needs_clarification" and len(client.calls) == 2


def test_quality_answer_inherits_original_persian_window_without_reasking():
    correct = spec(dimension_ids=("employee_name",), limit=1,
                   period=PeriodSelection("jalali_rolling", count=6, unit="month"))
    wrong_period = replace(correct, period=PeriodSelection("last_month"))
    client = Client(intent(wrong_period, turn_kind="answer"), decision(correct), {"approved": True, "feedback": ""})
    result = agent(client).interpret((Message("user", "بهترین بازدهی در 6 ماه گذشته"),
                                     Message("assistant", "مجموع ساعت یا تعداد فعالیت؟"),
                                     Message("user", "مجموع ساعت")), None,
                                    permitted_catalog(rahtal_reporting_catalog(), scope()), TODAY)
    assert result.spec == correct and len(client.calls) == 3


def test_quality_answer_can_explicitly_replace_original_relative_window():
    correct = spec(metric_ids=("activity_hours",), dimension_ids=("employee_name",), limit=1,
                   period=PeriodSelection("jalali_month", year=1405, month=6))
    client = Client(intent(correct, turn_kind="answer"), decision(correct), {"approved": True, "feedback": ""})
    result = agent(client).interpret((Message("user", "بهترین بازدهی در شش ماه گذشته"),
                                     Message("assistant", "مجموع ساعت یا تعداد فعالیت؟"),
                                     Message("user", "مجموع ساعت در شهریور ۱۴۰۵")), None,
                                    permitted_catalog(rahtal_reporting_catalog(), scope()), TODAY)
    assert result.spec == correct


def test_local_measure_clarification_preserves_window_when_model_calls_answer_new():
    catalog = permitted_catalog(rahtal_reporting_catalog(), scope())
    correct = spec(metric_ids=("activity_hours",), dimension_ids=("employee_name",), limit=1,
                   period=PeriodSelection("jalali_rolling", count=6, unit="month"))
    wrong = replace(correct, period=PeriodSelection("rolling", count=6, unit="month"))
    client = Client(intent(wrong, turn_kind="new"), decision(correct), {"approved": True, "feedback": ""})
    result = agent(client).interpret((Message("user", "چه شخصی بهترین بازدهی در شش ماه گذشته داشته؟"),
                                     Message("assistant", measure_question(catalog).question),
                                     Message("user", "معیارم مجموع ساعت است، نفر اول را بگو")), None, catalog, TODAY)
    assert result.spec == correct
    assert json.loads(client.calls[1]["messages"][1]["content"])["intent"]["turn_kind"] == "answer"


def test_explicit_english_period_refinement_is_not_frozen_to_old_dates():
    current = spec(period=PeriodSelection("range", start="2026-09-10", end="2026-10-12"))
    correct = replace(current, period=PeriodSelection("rolling", count=6, unit="month"))
    client = Client(intent(correct, turn_kind="refine"), decision(correct), {"approved": True, "feedback": ""})
    result = agent(client).interpret((Message("user", "Show the past six months in the Gregorian calendar"),), current,
                                    permitted_catalog(rahtal_reporting_catalog(), scope()), TODAY)
    assert result.spec == correct


def test_registered_hour_criterion_can_rank_and_observer_excludes_prose_values():
    ranked = spec(dimension_ids=("employee_name",), limit=1)
    client = Client(intent(ranked), decision(ranked), {"approved": True, "feedback": ""})
    events = []
    provider = OpenAIReportAgent(LLMConfig("fake", "https://example.test/v1", "fake"), client=client,
                                observer=lambda stage, status, **details: events.append((stage, status, details)))
    result = provider.interpret((Message("user", "بیشترین مجموع ساعت در ماه قبل"),), None,
                                permitted_catalog(rahtal_reporting_catalog(), scope()), TODAY)
    assert result.spec == ranked
    assert [e[0] for e in events] == ["request_evidence", "agent_intent", "agent_intent_decoded", "intent_evidence",
        "agent_intent", "requirements_check", "agent_plan", "agent_plan", "agent_review", "agent_review"]
    assert "بیشترین" not in json.dumps(events) and "question" not in json.dumps(events)


def test_persistent_refinement_keeps_relative_persian_dates_after_clock_changes(database, tmp_path):
    requested = spec()
    class Provider:
        def interpret(self, messages, current, catalog, today):
            return Interpretation("ready", requested if current is None else replace(current, dimension_ids=("activity_topic",)))
    def engine(today):
        return SageQL(catalog=rahtal_reporting_catalog("main"), database=SQLiteAdapter(database), provider=Provider(),
                      policy=lambda actor: scope(), sessions=SQLiteSessionStore(tmp_path / "conversation.sqlite"),
                      clock=lambda: today, execution="validated")
    first_engine = engine(TODAY)
    session = first_engine.create_session(ACTOR)
    first = first_engine.submit(session.session_id, "سهم هر کارمند روی موضوع در ماه قبل", ACTOR, "first", 0)
    assert first.status == "report_ready", first.to_dict()
    assert "مجموع ساعات" in first.text and "شمسی" in first.text
    second = engine(date(2027, 4, 1)).submit(session.session_id, "فقط جمع هر موضوع", ACTOR, "second", 1)
    assert second.status == "report_ready", second.to_dict()
    assert second.report.provenance["period_start"] == first.report.provenance["period_start"] == "2026-08-23"
    assert second.report.provenance["period_end_exclusive"] == first.report.provenance["period_end_exclusive"] == "2026-09-23"
    assert sum(row[-2] for row in second.report.rows) == sum(row[-2] for row in first.report.rows) == 47
