"""Identity-aligned loss rankings with complete bounded synthetic candidates."""

from dataclasses import replace
from datetime import date
from decimal import Decimal
import json
import sqlite3
from types import SimpleNamespace

import pytest

from sageql import LLMConfig, Message
from sageql.sdk import (
    AccessScope, ActorContext, AggregateFilter, ConceptRef, DatasetAccess,
    ExecutionLimits, Interpretation, OpenAIReportAgent, PeriodSelection,
    ReportIntent, ReportSpec, RowPolicy, SDKError, SageQL, SQLiteAdapter,
    SQLiteSessionStore,
)
from sageql.sdk.decreases import make_decrease_report
from sageql.sdk.models import ReportArtifact, ReportField
from sageql.sdk.adapters import compile_report
from sageql.sdk.comparisons import comparison_evidence_context
from sageql.sdk.lookups import prepare_request
# The private Rahtal host supplies this catalog; it is not published.
pytest.importorskip("sageql_rahtal")
from sageql_rahtal.sdk import rahtal_reporting_catalog  # noqa: E402


ACTOR = ActorContext("synthetic-reader")
TODAY = date(2026, 10, 11)
QUESTION = "شناسایی کارکنان با افت فعالیت: کدام کارکنان در شهریور نسبت به مرداد ۱۴۰۵ بیشترین کاهش ساعت فعالیت را داشته‌اند؟ نام، ساعات هر ماه و درصد افتشان را نمایش بده."
SPEC = ReportSpec("activities", ("activity_hours",), ("employee_name",),
                  period=PeriodSelection("jalali_month", year=1405, month=6),
                  comparison=PeriodSelection("jalali_month", year=1405, month=5),
                  comparison_calculation="decrease", order_by="absolute_decrease", descending=True)
SCOPE = AccessScope(tuple(DatasetAccess(key, policies=(RowPolicy("is_deleted", "eq", (False,)),))
                          for key in ("activities", "employees")))


class Provider:
    def __init__(self, spec=SPEC):
        self.spec = spec

    def interpret(self, messages, current, catalog, today):
        return Interpretation("ready", self.spec)


class Adapter(SQLiteAdapter):
    def __init__(self, path):
        super().__init__(path)
        self.calls = []
        self.alter = lambda result: result
        self.after = lambda request: None

    def execute(self, request, limits, *, cancel=None):
        self.calls.append(request)
        result = super().execute(request, limits, cancel=cancel)
        self.after(request)
        return self.alter(result) if request.dataset.id == "activities" else result


@pytest.fixture
def source(tmp_path):
    path = tmp_path / "synthetic.sqlite"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE functionality_activities (id int NOT NULL, user_id int, date date, time float, is_deleted bit, title_id bigint);
            CREATE TABLE persons_person (user_id int, first_name nvarchar, last_name nvarchar, job_position nvarchar, is_deleted bit);
        """)
        months = [(1,100,50), (2,40,"absent"), (3,100,60), (4,200,160),
                  (5,"absent",500), (6,None,0), (7,20,20), (8,10,20),
                  (None,999,"absent"), (10,-10,-20), (11,50,None), (12,0,0), (13,30,5)]
        rows = []
        for identity, reference, current in months:
            for day, value in (("2026-07-23", reference), ("2026-08-23", current)):
                if value != "absent":
                    rows.append((len(rows)+1, identity, day, value, 0, None))
        rows += [(900,1,"2026-08-01",999,1,None), (901,1,"2026-09-23",888,0,None),
                 (902,1,"2026-07-22",777,0,None)]
        connection.executemany("INSERT INTO functionality_activities VALUES (?,?,?,?,?,?)", rows)
        connection.executemany("INSERT INTO persons_person VALUES (?,?,?,?,?)", [
            (1,"نام","مشترک",None,0), (1,"نام","مشترک",None,0),
            (2,"نام","دوم",None,0), (3,"نام","مشترک",None,0), (4,"نام","چهارم",None,0),
            (13,"پروفایل","حذف‌شده",None,1),
        ])
    return path


def make_engine(source, tmp_path, spec=SPEC, **options):
    return SageQL(catalog=rahtal_reporting_catalog("main"), database=Adapter(source),
                  provider=Provider(spec), policy=lambda actor: SCOPE, execution="validated",
                  clock=lambda: TODAY, sessions=SQLiteSessionStore(tmp_path / "sessions.sqlite"), **options)


def submit(engine, message=QUESTION, *, request="first", revision=0, session=None):
    session = session or engine.create_session(ACTOR).session_id
    return engine.submit(session, message, ACTOR, request, revision)


def test_absolute_loss_rank_missing_month_ties_equal_names_and_source_policies(source, tmp_path):
    engine = make_engine(source, tmp_path)
    reply = submit(engine)
    assert reply.status == "report_ready", reply.error
    rows = reply.report.rows
    assert [row[0] for row in rows] == ["نام مشترک", "نام دوم", "نام مشترک", "نام چهارم", "نام در دسترس نیست"]
    assert [row[1:4] for row in rows] == [(100,50,50), (40,0,40), (100,60,40), (200,160,40), (30,5,25)]
    assert [row[4] for row in rows[:4]] == [Decimal(50), Decimal(100), Decimal(40), Decimal(20)]
    assert tuple(field.id for field in reply.report.fields) == ("employee_name", "comparison_value", "base_value", "absolute_decrease", "percent_decrease")
    assert reply.report.fields[0].type == "text" and reply.report.fields[1].unit == "ساعت"
    provenance = reply.report.provenance
    assert provenance["ranking"] == "absolute_decrease_desc" and provenance["eligible_groups"] == 5
    assert provenance["excluded_groups"] == {"null_identity":1,"missing_value":2,"nonpositive_reference":3,"non_decrease":2}
    assert [call.dataset.id for call in engine.database.calls] == ["activities", "employees"]
    assert engine.database.calls[1].spec.filters[0].values == (1,2,3,4,13)
    assert not reply.report.truncated and provenance["entity_labels"]["unavailable_rows"] == 1


def test_output_limit_is_applied_after_complete_candidates_and_exact_ranking(source, tmp_path):
    engine = make_engine(source, tmp_path, replace(SPEC, limit=1), limits=ExecutionLimits(max_rows=50))
    reply = submit(engine)
    assert reply.status == "report_ready" and reply.report.rows[0][0] == "نام مشترک"
    assert len(reply.report.rows) == 1 and reply.report.truncated
    assert reply.report.provenance["eligible_groups"] == 5
    assert engine.database.calls[1].spec.filters[0].values == (1,)
    for dialect in ("tsql", "sqlite"):
        query = compile_report(engine.database.calls[0], engine.limits, dialect=dialect)
        assert query.limit == 50 and (51 in query.parameters)
        assert query.sql.count("is_deleted") == 2 and "UNION ALL" in query.sql
        assert "GROUP BY" in query.sql and "JOIN" not in query.sql
        assert "absolute_decrease" not in query.sql and "/" not in query.sql


def test_candidate_truncation_fails_before_name_reads_or_session_mutation(source, tmp_path):
    engine = make_engine(source, tmp_path, replace(SPEC, limit=1), limits=ExecutionLimits(max_rows=3))
    reply = submit(engine)
    assert reply.status == "failed" and reply.error["code"] == "adapter_failed"
    assert reply.report is None and len(engine.database.calls) == 1
    state = engine.sessions.get(reply.session_id, (ACTOR.subject, ACTOR.tenant_id))
    assert not state["reports"] and state["current_spec"] is None


@pytest.mark.parametrize("changes", [
    {"comparison":None}, {"dimension_ids":()}, {"dimension_ids":("employee_id",)},
    {"dimension_ids":("employee_name","employee_id")}, {"metric_ids":("average_activity_hours",)},
    {"metric_ids":("activity_hours","activity_count")}, {"time_grain":"day"}, {"chart":"bar"},
    {"order_by":"activity_hours"}, {"order_by":"percent_decrease"}, {"descending":False},
    {"aggregate_filters":(AggregateFilter("activity_hours","gt",(0,)),)},
])
def test_out_of_scope_shapes_cannot_execute(changes):
    with pytest.raises(SDKError):
        prepare_request(rahtal_reporting_catalog(), replace(SPEC, **changes), SCOPE, TODAY)


@pytest.mark.parametrize("alter", [
    lambda result: replace(result, truncated=True),
    lambda result: replace(result, rows=(*result.rows,result.rows[0])),
    lambda result: replace(result, rows=(("other",*result.rows[0][1:]),*result.rows[1:])),
    lambda result: replace(result, rows=(("base","private-identity",5),*result.rows[1:])),
    lambda result: replace(result, rows=(("base",1,"private-value"),*result.rows[1:])),
    lambda result: replace(result, rows=(("base",1,float("inf")),*result.rows[1:])),
])
def test_bad_adapter_candidates_fail_without_leaking_values(source, tmp_path, alter):
    engine = make_engine(source, tmp_path)
    engine.database.alter = alter
    reply = submit(engine)
    assert reply.status == "failed" and reply.error["code"] == "adapter_failed"
    assert len(engine.database.calls) == 1 and "private-" not in json.dumps(reply.to_dict())


def test_empty_complete_source_is_a_valid_empty_decline_report(source, tmp_path):
    with sqlite3.connect(source) as connection:
        connection.execute("DELETE FROM functionality_activities")
    engine = make_engine(source, tmp_path)
    reply = submit(engine)
    assert reply.status == "report_ready" and reply.report.rows == ()
    assert not reply.report.truncated and reply.report.provenance["completeness"] == "empty"
    assert len(engine.database.calls) == 1


def test_conflicting_profiles_fail_after_ranking_without_persisting(source, tmp_path):
    with sqlite3.connect(source) as connection:
        connection.execute("INSERT INTO persons_person VALUES (1,'نام','متفاوت',NULL,0)")
    engine = make_engine(source, tmp_path)
    reply = submit(engine)
    assert reply.status == "blocked" and reply.error["code"] == "entity_label_conflict"
    assert reply.report is None


def test_persisted_retrieval_retry_and_refinement_keep_fixed_decline_contract(source, tmp_path):
    engine = make_engine(source, tmp_path)
    first = submit(engine)
    assert first.status == "report_ready"
    saved = engine.get_report(first.session_id, first.report.id, ACTOR)
    assert saved.to_dict() == first.report.to_dict()
    cached = submit(engine, session=first.session_id)
    assert cached.to_dict() == first.to_dict() and len(engine.database.calls) == 2
    second = submit(engine,"همین گزارش", session=first.session_id, request="refine",revision=first.revision)
    assert second.status == "report_ready" and second.report.rows == first.report.rows
    state = engine.sessions.get(first.session_id, (ACTOR.subject, ACTOR.tenant_id))
    current = ReportSpec.from_dict(state["current_spec"])
    assert current.comparison_calculation == "decrease" and current.order_by == "absolute_decrease"
    assert current.period == SPEC.period and current.comparison == SPEC.comparison


def test_decline_wording_fixes_operation_and_absolute_ranking_without_result_evidence():
    wrong = ReportIntent(metrics=(ConceptRef("activities","activity_hours"),),
                         dimensions=(ConceptRef("activities","employee_name"),), comparison=SPEC.comparison,
                         comparison_calculation="change", order_by="activity_hours", descending=False)
    checked = comparison_evidence_context(wrong,(Message("user",QUESTION),),None)
    assert checked.comparison_calculation == "decrease" and checked.order_by == "absolute_decrease"
    assert checked.descending and checked.time_grain == "none"
    assert checked.limit == 100  # Two months are not a two-employee output limit.
    refine = replace(checked, turn_kind="refine",comparison_calculation=None)
    assert comparison_evidence_context(refine,(Message("user","سه نفر اول"),),SPEC).comparison_calculation == "decrease"


def test_actual_agent_schemas_repair_wrong_sort_and_exclude_results_from_model(source, tmp_path):
    intent = ReportIntent(metrics=(ConceptRef("activities","activity_hours"),),
                          dimensions=(ConceptRef("activities","employee_name"),),period=SPEC.period,
                          comparison=SPEC.comparison,comparison_specified=True,comparison_calculation="decrease",
                          order_by="absolute_decrease",ordering_specified=True,descending=True)
    bad = replace(SPEC, order_by="activity_hours")
    plans = [{"status":"ready","spec":spec.to_dict(),"question":"","message":""} for spec in (bad,SPEC)]
    responses = iter((intent.to_dict(),*plans,{"approved":True,"feedback":""}))
    calls = []
    def create(**options):
        calls.append(options)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(next(responses))))])
    client = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
    client.with_options = lambda **options: client
    engine = make_engine(source,tmp_path)
    engine.provider = OpenAIReportAgent(LLMConfig("fake","https://example.test/v1","fake"),client=client)
    reply = submit(engine)
    assert reply.status == "report_ready", reply.error
    assert len(calls) == 4 and len(engine.database.calls) == 2
    payload = json.dumps(calls,ensure_ascii=False)
    assert "نام مشترک" not in payload and "functionality_activities" not in payload and "eligible_groups" not in payload
    schema = calls[1]["response_format"]["json_schema"]["schema"]["properties"]["spec"]["anyOf"][0]
    assert "absolute_decrease" in schema["properties"]["order_by"]["enum"]


@pytest.mark.parametrize("metric", ["activity_count", "participant_count"])
def test_absent_period_is_zero_for_registered_count_metrics(source, tmp_path, metric):
    engine = make_engine(source, tmp_path, replace(SPEC, metric_ids=(metric,)))
    reply = submit(engine)
    assert reply.status == "report_ready" and reply.report.rows == (("نام دوم",1,0,Decimal(1),Decimal(100)),)


def test_access_changes_during_candidates_block_before_name_enrichment(source, tmp_path):
    engine = make_engine(source, tmp_path)
    engine.database.after = lambda request: setattr(engine,"_policy",lambda actor: replace(SCOPE,version="changed"))
    reply = submit(engine)
    assert reply.status == "blocked" and reply.error["code"] == "access_denied"
    assert len(engine.database.calls) == 1 and reply.report is None


def test_denied_label_source_is_rejected_before_fact_execution(source, tmp_path):
    engine = make_engine(source,tmp_path)
    engine._policy = lambda actor: AccessScope((SCOPE.datasets[0],))
    reply = submit(engine)
    assert reply.status == "blocked" and reply.error["code"] == "access_denied"
    assert not engine.database.calls


def test_exact_decimal_loss_ranking_does_not_round_before_selecting():
    fields = (ReportField("period_label","Period","text"), ReportField("employee_name","Name","integer"),
              ReportField("activity_hours","Hours","decimal","hours"))
    report = ReportArtifact("synthetic","synthetic",1,"Synthetic",fields,(
        ("comparison",1,Decimal("10.00000000000000000001")),("base",1,Decimal(10)),
        ("comparison",2,Decimal("10.00000000000000000002")),("base",2,Decimal(10)),
    ),{"kind":"table"},{"period_labels":{"base":"Current","comparison":"Reference"}},False)
    from decimal import Inexact, ROUND_UP, localcontext
    with localcontext() as context:
        context.prec = 2
        context.rounding = ROUND_UP
        context.traps[Inexact] = True
        result = make_decrease_report(report,replace(SPEC,limit=1),rahtal_reporting_catalog().datasets[0],language="en",max_rows=10)
    assert result.rows[0][0] == 2 and result.rows[0][3] == Decimal(".00000000000000000002")
    assert result.truncated and result.provenance["eligible_groups"] == 2


@pytest.mark.parametrize("message", ["کارکنان با بیشترین درصد افت را نشان بده", "rank employees by percentage decline"])
def test_explicit_percentage_ranking_cannot_silently_become_absolute_ranking(message):
    intent = ReportIntent(dimensions=(ConceptRef("activities","employee_name"),),
                          comparison=SPEC.comparison,comparison_calculation="decrease")
    with pytest.raises(SDKError) as error:
        comparison_evidence_context(intent,(Message("user",message),),None)
    assert error.value.code == "unsupported"
