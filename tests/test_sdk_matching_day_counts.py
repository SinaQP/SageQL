"""Counts of complete filtered daily entity groups, independent of the catalog."""

from dataclasses import replace
from datetime import date
import json
import sqlite3
from types import SimpleNamespace

import pytest

from sageql import LLMConfig, Message
from sageql.schema import Column, Table
from sageql.sdk import (
    AccessScope, ActorContext, AdapterResult, AggregateFilter, ConceptRef, DatasetAccess,
    DatasetDefinition, DimensionDefinition, EntityLabelDimension, ExecutionLimits,
    FilterDefinition, Interpretation, MetricDefinition, OpenAIReportAgent, PeriodSelection,
    ReportField, ReportIntent, ReportingCatalog, ReportSpec, RowPolicy, SDKError, SageQL,
    SQLiteAdapter, SQLiteSessionStore, TimeDefinition, UserFilter,
)
from sageql.sdk.adapters import compile_report
from sageql.sdk.day_counts import matching_day_context, validate_matching_day_result
from sageql.sdk.intent import check_intent, clarification_key, intent_feedback
from sageql.sdk.provider import _check_spec, _format, _metadata
from sageql.sdk.semantics import validate_catalog, validate_report


ACTOR = ActorContext("synthetic-manager")
TODAY = date(2027, 2, 5)
SPEC = ReportSpec("logs", ("total",), ("person_name",),
    period=PeriodSelection("month", year=2027, month=1), time_grain="day",
    aggregate_filters=(AggregateFilter("total", "gt", (10.0,)),),
    order_by="total", descending=True, include_matching_day_count=True)


def catalog():
    facts, labels = Table("entries", "main"), Table("labels", "main")
    return ReportingCatalog((
        DatasetDefinition("logs", "Recorded amounts", facts,
            tuple(Column(facts.key,key,kind,nullable=key!="record_key") for key,kind in (
                ("record_key","int"),("actor_key","int"),("recorded_day","date"),
                ("private_amount","float"),("deleted","bit"))),
            metrics=(MetricDefinition("total","Total amount","sum","private_amount"),
                     MetricDefinition("events","Entry count","count_rows")),
            dimensions=(EntityLabelDimension("person_name","Person","actor_key","labels","identity",
                        "identity_filter",("given","surname")), DimensionDefinition("person_id","ID","actor_key")),
            filters=(FilterDefinition("person_filter","Person","actor_key"),),
            time=TimeDefinition("recorded_day"), row_key=("record_key",)),
        DatasetDefinition("labels","Display names", labels,
            tuple(Column(labels.key,key,kind) for key,kind in (
                ("identity","int"),("given","nvarchar"),("surname","nvarchar"),("deleted","bit"))),
            metrics=(), dimensions=tuple(DimensionDefinition(key,key,key) for key in ("identity","given","surname")),
            filters=(FilterDefinition("identity_filter","Identity","identity"),)),
    ))


class Provider:
    def __init__(self,spec): self.spec=spec
    def interpret(self,*args): return Interpretation("ready",self.spec)


class Adapter(SQLiteAdapter):
    def __init__(self,path):
        super().__init__(path)
        self.calls=[]
    def execute(self,request,limits,*,cancel=None):
        self.calls.append(request)
        return super().execute(request,limits,cancel=cancel)


def engine_at(tmp_path,spec=SPEC,*,language="en",definitions=None,scope=None):
    tmp_path.mkdir(parents=True,exist_ok=True)
    path=tmp_path/"facts.sqlite"
    with sqlite3.connect(path) as connection:
        connection.executescript("""
            CREATE TABLE entries (record_key int NOT NULL,actor_key int,recorded_day date,private_amount float,deleted bit);
            CREATE TABLE labels (identity int,given nvarchar,surname nvarchar,deleted bit);
            INSERT INTO labels VALUES (1,'PrivateShared','Name',0),(2,'PrivateShared','Name',0),
                (3,'Unknown','Duration',0),(5,'Deleted','Profile',1),(9,'Idle','Person',0);
            INSERT INTO entries VALUES
                (1,1,'2027-01-01',6,0),(2,1,'2027-01-01',5,0),(3,1,'2027-01-02',11,0),
                (4,1,'2027-01-03',10,0),(5,1,'2027-01-04',8,0),
                (6,2,'2027-01-01',12,0),(7,2,'2027-01-02',13,0),(8,2,'2027-01-03',14,0),
                (9,3,'2027-01-01',NULL,0),(10,3,'2027-01-02',99,1),
                (11,4,'2027-01-02',15,0),(12,5,'2027-01-02',16,0),
                (13,NULL,'2027-01-02',20,0),(14,NULL,'2027-01-03',21,0),
                (15,1,'2026-12-31',90,0),(16,1,'2027-02-01',99,0),(17,1,NULL,99,0);
        """)
    scope=scope or AccessScope(tuple(DatasetAccess(key,policies=(RowPolicy("deleted","eq",(False,)),))
                                   for key in ("logs","labels")))
    database=Adapter(path)
    engine=SageQL(catalog=definitions or catalog(),database=database,provider=Provider(spec),
        policy=lambda actor:scope,clock=lambda:TODAY,execution="validated",language=language,
        sessions=SQLiteSessionStore(tmp_path/"sessions.sqlite"))
    return engine,database,path


def submit(engine,*,request="first",session=None,revision=0,message="Daily matching amounts and number of qualifying days"):
    session=session or engine.create_session(ACTOR).session_id
    return engine.submit(session,message,ACTOR,request,revision)


def test_daily_sums_then_strict_filter_then_counts_and_separate_equal_names(tmp_path):
    engine,database,_=engine_at(tmp_path)
    reply=submit(engine)
    assert reply.status=="report_ready",reply.error
    rows=reply.report.rows
    assert len(rows)==9 and not reply.report.truncated
    shared=[row for row in rows if row[1]=="PrivateShared Name"]
    assert sorted(row[-1] for row in shared)==[2,2,3,3,3]
    assert (date(2027,1,1),"PrivateShared Name",11.0,2) in rows  # 6+5 exceeds 10; no single row does.
    assert not any(row[2] in (8,10,90,99) for row in rows)
    unavailable=[row for row in rows if row[1]=="Name unavailable"]
    assert sorted((row[2],row[-1] or 0) for row in unavailable)==[(15.0,1),(16.0,1),(20.0,0),(21.0,0)]
    assert reply.report.fields[-1]==ReportField("matching_day_count","Matching days","integer","days")
    assert "Matching days" in reply.report.title
    assert reply.report.provenance["matching_day_count"]=={
        "scope":"per_entity_per_period","after_aggregate_filters":True,"before_output_limit":True}
    assert [call.dataset.id for call in database.calls]==["logs","labels"]


def test_output_cap_does_not_shrink_full_period_day_count(tmp_path):
    spec=replace(SPEC,filters=(UserFilter("person_filter","eq",(2,)),),limit=1)
    engine,_,_=engine_at(tmp_path,spec)
    reply=submit(engine)
    assert reply.status=="report_ready" and reply.report.truncated
    assert reply.report.rows==((date(2027,1,3),"PrivateShared Name",14.0,3),)


@pytest.mark.parametrize("threshold,expected",[(0.0,4),(10.0,2),(12.0,0),(100.0,0)])
def test_thresholds_are_regular_typed_parameters_not_question_constants(tmp_path,threshold,expected):
    spec=replace(SPEC,filters=(UserFilter("person_filter","eq",(1,)),),
                 aggregate_filters=(AggregateFilter("total","gt",(threshold,)),))
    engine,_,_=engine_at(tmp_path,spec)
    reply=submit(engine)
    assert reply.status=="report_ready" and len(reply.report.rows)==expected
    assert all(row[-1]==expected for row in reply.report.rows)


def test_other_metric_count_conditions_and_ordering_use_same_operation(tmp_path):
    spec=replace(SPEC,metric_ids=("events",),aggregate_filters=(AggregateFilter("events","gte",(2,)),),
                 order_by="matching_day_count")
    engine,_,_=engine_at(tmp_path,spec)
    reply=submit(engine)
    assert reply.status=="report_ready" and reply.report.rows==((date(2027,1,1),"PrivateShared Name",2,1),)


def test_comparison_periods_have_independent_matching_counts(tmp_path):
    spec=replace(SPEC,comparison=PeriodSelection("month",year=2026,month=12),
                 filters=(UserFilter("person_filter","eq",(1,)),))
    engine,_,_=engine_at(tmp_path,spec)
    reply=submit(engine)
    assert reply.status=="report_ready"
    assert sorted((row[0],row[-1]) for row in reply.report.rows)==[("base",2),("base",2),("comparison",1)]


def test_other_domain_catalog_and_current_scope_are_reused(tmp_path):
    definitions=catalog()
    logs,labels=definitions.datasets
    dimension=replace(logs.dimensions[0],id="customer_name",source_dataset_id="customers")
    definitions=replace(definitions,datasets=(replace(logs,id="sales",dimensions=(dimension,)),replace(labels,id="customers")))
    scope=AccessScope(tuple(DatasetAccess(key,policies=(RowPolicy("deleted","eq",(False,)),)) for key in ("sales","customers")))
    spec=replace(SPEC,dataset_id="sales",dimension_ids=("customer_name",))
    engine,_,_=engine_at(tmp_path,spec,definitions=definitions,scope=scope)
    reply=submit(engine)
    assert reply.status=="report_ready" and len(reply.report.rows)==9


@pytest.mark.parametrize("dialect",["sqlite","tsql"])
def test_compiler_window_uses_identity_after_filters_before_limit_with_bound_values(tmp_path,dialect):
    engine,database,_=engine_at(tmp_path)
    submit(engine)
    query=compile_report(database.calls[0],ExecutionLimits(),dialect=dialect)
    count="COUNT_BIG" if dialect=="tsql" else "COUNT"
    assert f"{count}(*) OVER (PARTITION BY" in query.sql
    assert "CASE WHEN" in query.sql and "IS NULL THEN NULL" in query.sql
    assert query.fields[-1].id=="matching_day_count"
    assert "10.0" not in query.sql
    assert query.parameters==((101,False,date(2027,1,1),date(2027,2,1),10.0) if dialect=="tsql"
                              else (False,"2027-01-01","2027-02-01",10.0,101))


@pytest.mark.parametrize("changes",[
    {"time_grain":"month"},{"chart":"bar"},{"dimension_ids":("person_id",)},
    {"dimension_ids":("person_name","person_id")},{"period":PeriodSelection("all")},
    {"include_matching_day_count":1},{"include_matching_day_count":"true"},
    {"include_matching_day_count":None},{"comparison_calculation":"change"},
    {"include_matching_day_count":False,"order_by":"matching_day_count"},
])
def test_invalid_shapes_fail_closed(changes):
    definition=catalog().datasets[0]
    with pytest.raises(SDKError):
        validate_report(definition,replace(SPEC,**changes),DatasetAccess("logs"),today=TODAY)


def test_reserved_count_field_cannot_be_registered_as_a_metric():
    definitions=catalog()
    first=replace(definitions.datasets[0],metrics=(MetricDefinition("matching_day_count","Collision","count_rows"),))
    with pytest.raises(SDKError): validate_catalog(replace(definitions,datasets=(first,definitions.datasets[1])))


def test_legacy_false_default_keeps_ordinary_sql_and_results_without_extra_field(tmp_path):
    spec=replace(SPEC,include_matching_day_count=False)
    raw=spec.to_dict(); raw.pop("include_matching_day_count")
    assert ReportSpec.from_dict(raw)==spec
    engine,database,_=engine_at(tmp_path,spec)
    reply=submit(engine)
    assert reply.status=="report_ready" and len(reply.report.fields)==3
    assert all(len(row)==3 for row in reply.report.rows)
    assert " OVER " not in compile_report(database.calls[0],engine.limits,dialect="tsql").sql


def test_denied_entity_names_cannot_be_granted_by_new_operation(tmp_path):
    scope=AccessScope((DatasetAccess("logs",policies=(RowPolicy("deleted","eq",(False,)),)),))
    engine,database,_=engine_at(tmp_path,scope=scope)
    reply=submit(engine)
    assert reply.status=="blocked" and not database.calls


def test_persistent_refinement_removal_retrieval_and_cached_retry(tmp_path):
    engine,database,_=engine_at(tmp_path)
    first=submit(engine)
    assert submit(engine,session=first.session_id).to_dict()==first.to_dict() and len(database.calls)==2
    assert engine.get_report(first.session_id,first.report.id,ACTOR).rows==first.report.rows
    engine.provider=Provider(replace(SPEC,include_matching_day_count=False))
    second=submit(engine,session=first.session_id,request="remove",revision=first.revision,message="Remove day count")
    assert second.status=="report_ready" and len(second.report.fields)==3


@pytest.mark.parametrize("mutation",["missing","float","zero","too_large","inconsistent","duplicate","wrong_type","null_identity"])
def test_malformed_custom_adapter_day_counts_fail_before_name_reads(tmp_path,mutation):
    engine,database,_=engine_at(tmp_path)
    submit(engine)
    prepared=database.calls[0]
    fields=(ReportField("time_bucket","Date","date"),ReportField("person_name","Person","integer"),
            ReportField("total","Total","number"),ReportField("matching_day_count","Matching days","integer"))
    rows=[(date(2027,1,1),1,11.0,2),(date(2027,1,2),1,12.0,2)]
    if mutation=="missing": fields=fields[:-1]; rows=[row[:-1] for row in rows]
    if mutation=="float": rows[0]=(*rows[0][:-1],2.0)
    if mutation=="zero": rows[0]=(*rows[0][:-1],0)
    if mutation=="too_large": rows=[(*row[:-1],32) for row in rows]
    if mutation=="inconsistent": rows[0]=(*rows[0][:-1],1)
    if mutation=="duplicate": rows[1]=rows[0]
    if mutation=="wrong_type": fields=(*fields[:-1],replace(fields[-1],type="number"))
    if mutation=="null_identity": rows=[(row[0],None,*row[2:]) for row in rows]
    with pytest.raises(SDKError) as error:
        validate_matching_day_result(prepared,AdapterResult(fields,tuple(rows),False))
    assert error.value.code=="adapter_failed"


def extracted(**changes):
    return replace(ReportIntent(metrics=(ConceptRef("logs","total"),),dimensions=(ConceptRef("logs","person_name"),),
        period=SPEC.period,chart="table",time_grain="day",filters=(),aggregate_filters=SPEC.aggregate_filters,
        comparison_specified=True,order_by="total",ordering_specified=True,descending=True,limit=100),**changes)


class Client:
    def __init__(self,*plans):
        self.values=iter((extracted(include_matching_day_count=False).to_dict(),*[
            {"status":"ready","spec":plan.to_dict(),"question":"","message":""} for plan in plans],
            {"approved":True,"feedback":""}))
        self.chat=SimpleNamespace(completions=self); self.calls=[]
    def with_options(self,**options): return self
    def create(self,**options):
        self.calls.append(options)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(next(self.values))))])


def test_intent_extraction_cannot_drop_day_count_and_wrong_plan_is_repaired(tmp_path):
    engine,_,_=engine_at(tmp_path)
    client=Client(replace(SPEC,include_matching_day_count=False),SPEC)
    engine.provider=OpenAIReportAgent(LLMConfig("fake","https://example.test/v1","fake"),client=client)
    reply=submit(engine)
    assert reply.status=="report_ready" and len(client.calls)==4
    assert json.loads(client.calls[2]["messages"][1]["content"])["feedback"]==["intent_validation: matching_day_count_mismatch"]
    payload=json.dumps(client.calls)
    assert "PrivateShared" not in payload and "private_amount" not in payload and "actor_key" not in payload
    assert client.calls[0]["response_format"]["json_schema"]["schema"]["properties"]["include_matching_day_count"]["type"]==["boolean","null"]


def test_strict_spec_schema_and_intent_key_optional_provider_neutral_compatibility():
    schema=_format(catalog())["json_schema"]["schema"]["properties"]["spec"]["anyOf"][0]
    assert schema["properties"]["include_matching_day_count"]=={"type":"boolean"}
    assert "include_matching_day_count" in schema["required"]
    assert "actor_key" not in json.dumps(_metadata(catalog()))
    old=extracted()
    check_intent(old,catalog(),today=TODAY)
    assert intent_feedback(old,Interpretation("ready",SPEC),today=TODAY,catalog=catalog()) is None
    assert clarification_key(old)!=clarification_key(replace(old,include_matching_day_count=True))


def test_provider_accepts_active_computed_ordering_but_rejects_nonboolean_flag():
    _check_spec(replace(SPEC,order_by="matching_day_count"),catalog())
    with pytest.raises(ValueError): _check_spec(replace(SPEC,include_matching_day_count="true"),catalog())


def test_count_evidence_refinement_removal_and_no_effect_on_previous_question_shapes():
    old=extracted()
    enabled=matching_day_context(old,(Message("user","تعداد روزهای دارای این وضعیت را هم نشان بده"),),None)
    assert enabled.include_matching_day_count and enabled.time_grain=="day"
    refined=matching_day_context(replace(old,turn_kind="refine"),(Message("user","همین گزارش با آستانهٔ جدید"),),SPEC)
    assert refined.include_matching_day_count
    removed=matching_day_context(replace(old,turn_kind="answer"),
        (Message("user","تعداد روزها را نشان بده"),Message("user","تعداد روزها را حذف کن")),SPEC)
    assert removed.include_matching_day_count is False
    for question in ("مجموع ساعات و تعداد فعالیت و مشارکت کنندگان", "درصد تغییر نسبت به ماه قبل",
                     "بیشترین افت ساعت", "۱۰ کارمند برتر و میانگین مدت فعالیت", "میانگین ساعات به ازای هر کارمند"):
        ordinary=replace(old,time_grain="none")
        value=matching_day_context(ordinary,(Message("user",question),),None)
        assert value.time_grain=="none" and value.include_matching_day_count is False
