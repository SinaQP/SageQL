"""Controlled synthetic database schedules; no model or real SQL Server."""
from contextlib import contextmanager, nullcontext
from dataclasses import replace
from datetime import date
from decimal import Decimal
import sqlite3
from threading import Event, Thread
from types import SimpleNamespace

import pytest

from sageql import Column, Table
from sageql.sdk import (
    AccessScope, ActorContext, DatasetAccess, DatasetDefinition, DimensionDefinition,
    EntityLabelDimension, EntityLookupDefinition, ExecutionLimits, FilterDefinition,
    FullNameFilterDefinition, Interpretation, MetricDefinition, PeriodSelection,
    ReportingCatalog, ReportSpec, RowPolicy, SDKError, SageQL, SQLiteAdapter, TimeDefinition,
    InMemorySessionStore, SQLiteSessionStore, UserFilter,
    RelatedDimension, RelationshipDefinition, register_relationships,
)
from sageql.sdk.lookups import prepare_request
from sageql.sdk import consistency


ACTOR = ActorContext("synthetic-reader", "1")
CONNECT = sqlite3.connect


@contextmanager
def transaction(path):
    value=CONNECT(path)
    try:
        with value:yield value
    finally:value.close()


def catalog():
    fact, people = Table("private_fact"), Table("private_people")
    return ReportingCatalog((
        DatasetDefinition("facts", "Sales", fact,
            tuple(Column(fact.key, n, t) for n, t in (("tenant", "int"), ("deleted", "int"),
                ("owner", "int"), ("day", "date"), ("amount", "decimal"))),
            metrics=(MetricDefinition("amount", "Amount", "sum", "amount"),),
            dimensions=(EntityLabelDimension("owner_name", "Owner name", "owner", "people", "person",
                                             "person_filter", ("name",)),),
            filters=(FilterDefinition("owner_filter", "Owner", "owner"),), time=TimeDefinition("day")),
        DatasetDefinition("people", "People", people,
            tuple(Column(people.key, n, t) for n, t in (("tenant", "int"), ("deleted", "int"),
                ("id", "int"), ("label", "text"))), metrics=(),
            dimensions=(DimensionDefinition("person", "Person", "id"), DimensionDefinition("name", "Name", "label")),
            filters=(FilterDefinition("person_filter", "Person", "id"),
                     FullNameFilterDefinition("name_filter", "Name", "label", ("eq",), ("label",)))),
    ), lookups=(EntityLookupDefinition("owner_lookup", "Owner name", "facts", "owner_filter",
                                       "people", "person", "name_filter"),))


def policy(actor):
    return AccessScope(tuple(DatasetAccess(k, policies=(RowPolicy("tenant", "eq", (int(actor.tenant_id),)),
        RowPolicy("deleted", "eq", (0,)))) for k in ("facts", "people")))


def spec(**changes):
    return replace(ReportSpec("facts", ("amount",), ("owner_name",),
        period=PeriodSelection("month", year=2026, month=9), order_by="amount", limit=2), **changes)


class Provider:
    def __init__(self, selection=None):
        self.selection = selection or spec()
        self.calls = []

    def interpret(self, *args):
        self.calls.append(args)
        return Interpretation("ready", self.selection)


@pytest.fixture
def database(tmp_path):
    path = tmp_path / "synthetic.sqlite"
    with transaction(path) as c:
        assert c.execute("PRAGMA journal_mode=WAL").fetchone()[0] == "wal"
        c.execute("CREATE TABLE private_fact (tenant INT, deleted INT, owner INT, day DATE, amount DECIMAL)")
        c.execute("CREATE TABLE private_people (tenant INT, deleted INT, id INT, label TEXT)")
        c.executemany("INSERT INTO private_fact VALUES (?,?,?,?,?)", [(1,0,1,"2026-09-01",10),
            (1,0,2,"2026-09-01",20),(2,0,1,"2026-09-01",900),(1,1,1,"2026-09-01",800)])
        c.executemany("INSERT INTO private_people VALUES (?,?,?,?)", [(1,0,1,"Ada"),(1,0,2,"Ben"),(2,0,1,"Hidden")])
    return path


def mutate(path):
    # Independent connection commits one atomic state change at the read boundary.
    with transaction(path) as c:
        c.execute("UPDATE private_fact SET amount=99 WHERE tenant=1 AND owner=1")
        c.execute("UPDATE private_people SET label='Changed' WHERE tenant=1 AND id=1")


class ControlledAdapter:
    def __init__(self, path, after=None):
        self.inner = SQLiteAdapter(path)
        self.after = after or (lambda n, report: None)
        self.calls = []
        self.exited = False

    def read(self, executor, report, limits, cancel):
        result = executor.execute(report, limits, cancel=cancel)
        self.calls.append(report)
        self.after(len(self.calls), report)
        return result

    def execute(self, report, limits, *, cancel=None):
        return self.read(self.inner, report, limits, cancel)

    @contextmanager
    def read_scope(self, limits, *, cancel=None):
        owner = self

        class Bound:
            def execute(self, report, limits, *, cancel=None):
                return owner.read(scoped, report, limits, cancel)

        try:
            with self.inner.read_scope(limits, cancel=cancel) as scoped:
                yield Bound()
        finally:
            self.exited = True


def engine(adapter, **options):
    return SageQL(catalog=catalog(), database=adapter, provider=options.pop("provider", Provider()),
        policy=options.pop("policy", policy), clock=lambda: date(2026,10,7),
        execution="validated", language="en", **options)


def submit(sdk, **options):
    session = options.pop("session", None) or sdk.create_session(ACTOR).session_id
    return sdk.submit(session, options.pop("message", "Show amount by owner name in September 2026."),
                      ACTOR, options.pop("request", "first"), options.pop("revision", 0), **options)


def test_compatibility_mode_demonstrates_mixed_committed_states(database):
    adapter = ControlledAdapter(database, lambda n, report: mutate(database) if n == 1 else None)
    reply = submit(engine(adapter))
    assert reply.status == "report_ready", reply.to_dict()
    assert reply.report.rows == (("Changed", Decimal(10)), ("Ben", Decimal(20)))
    assert reply.report.provenance["read_consistency"] == "compatibility"
    # No committed state had Changed/10: before was Ada/10, after is Changed/99.
    with transaction(database) as c:
        assert c.execute("SELECT amount FROM private_fact WHERE tenant=1 AND deleted=0 AND owner=1").fetchone() == (99,)


def test_snapshot_scope_preserves_aggregate_and_label_state(database):
    adapter = ControlledAdapter(database, lambda n, report: mutate(database) if n == 1 else None)
    reply = submit(engine(adapter, read_consistency="snapshot"))
    assert reply.status == "report_ready", reply.to_dict()
    assert reply.report.rows == (("Ada", Decimal(10)), ("Ben", Decimal(20)))
    assert reply.report.provenance["read_consistency"] == "snapshot"
    assert adapter.exited and [r.dataset.id for r in adapter.calls] == ["facts", "people"]


@pytest.mark.parametrize("mode", ["compatibility", "snapshot"])
@pytest.mark.parametrize("mutation", ["none", "update", "insert", "delete", "rollback"])
def test_actual_sqlite_transaction_schedules(database, mode, mutation):
    adapter=SQLiteAdapter(database);limits=ExecutionLimits()
    prepared=prepare_request(catalog(),spec(),policy(ACTOR),date(2026,10,7))[0]
    context=adapter.read_scope(limits) if mode=="snapshot" else nullcontext(adapter)
    with context as read:
        first=read.execute(prepared,limits)
        with transaction(database) as writer:
            if mutation in ("update","rollback"):
                writer.execute("UPDATE private_fact SET amount=99 WHERE tenant=1 AND owner=1")
            elif mutation=="insert":
                writer.execute("INSERT INTO private_fact VALUES (1,0,1,'2026-09-02',5)")
            elif mutation=="delete":
                writer.execute("DELETE FROM private_fact WHERE tenant=1 AND owner=1")
            if mutation=="rollback":writer.rollback()
        second=read.execute(prepared,limits)
    same=mode=="snapshot" or mutation in ("none","rollback")
    assert (first==second) is same
    assert first.rows==((1,Decimal(10)),(2,Decimal(20)))
    after=adapter.execute(prepared,limits)
    assert after==second if mode=="compatibility" else (after==first) is (mutation in ("none","rollback"))


def test_lookup_main_and_labels_share_the_same_snapshot(database):
    adapter=ControlledAdapter(database,lambda n,r:mutate(database) if n==1 else None)
    provider=Provider(spec(filters=(UserFilter("owner_lookup","eq",("Ada",)),)))
    sdk=engine(adapter,provider=provider,read_consistency="snapshot")
    reply=submit(sdk,message='Show amount for "Ada" by owner name in September 2026.')
    assert reply.status=="report_ready",reply.to_dict()
    assert reply.report.rows==(("Ada",Decimal(10)),)
    assert [r.dataset.id for r in adapter.calls]==["people","facts","people"]
    assert "Changed" not in repr(provider.calls) and "Hidden" not in repr(provider.calls)


def test_multiple_label_batches_stay_in_the_same_snapshot(database):
    with transaction(database) as c:
        c.executemany("INSERT INTO private_fact VALUES (1,0,?,'2026-09-01',?)",[(i,i) for i in range(3,202)])
        c.executemany("INSERT INTO private_people VALUES (1,0,?,?)",[(i,f"Owner {i}") for i in range(3,202)])
    def change_after_first_batch(n,report):
        if n==2:
            with transaction(database) as c:
                c.execute("UPDATE private_people SET label='Late' WHERE id=201")
                c.execute("UPDATE private_fact SET amount=999 WHERE owner=201")
    adapter=ControlledAdapter(database,change_after_first_batch)
    sdk=engine(adapter,provider=Provider(spec(limit=201)),limits=ExecutionLimits(max_rows=201),read_consistency="snapshot")
    reply=submit(sdk)
    assert reply.status=="report_ready",reply.to_dict()
    assert ("Owner 201",Decimal(201)) in reply.report.rows
    assert len(adapter.calls)==4 and [r.dataset.id for r in adapter.calls]==["facts","people","people","people"]


@pytest.fixture
def traced(monkeypatch):
    connections=[]

    class TracedCursor(sqlite3.Cursor):
        def __init__(self,*args,**options):
            super().__init__(*args,**options);self.closed=False
        def close(self):
            self.closed=True;super().close()

    class TracedConnection(sqlite3.Connection):
        def __init__(self,*args,**options):
            super().__init__(*args,**options)
            self.cursors=[];self.events=[];self.closed=False;self.rollbacks=0
            self.set_trace_callback(lambda sql:self.events.append(sql.split()[0].upper()))
        def cursor(self,*args,**options):
            options.setdefault("factory",TracedCursor)
            cursor=super().cursor(*args,**options);self.cursors.append(cursor);return cursor
        def execute(self,sql,parameters=()):
            cursor=self.cursor()
            try:return cursor.execute(sql,parameters)
            except BaseException:cursor.close();raise
        def rollback(self):
            self.rollbacks+=1;return super().rollback()
        def close(self):
            super().close();self.closed=True

    def connect(*args,**options):
        assert options.get("uri") is True and "mode=ro" in args[0]
        value=CONNECT(*args,**options,factory=TracedConnection);connections.append(value);return value
    monkeypatch.setattr(consistency,"sqlite3",SimpleNamespace(connect=connect,Error=sqlite3.Error))
    return connections


def assert_clean(connections):
    assert connections and all(c.closed and c.rollbacks==1 and all(p.closed for p in c.cursors) for c in connections)
    assert all(c.events.count("BEGIN")==c.events.count("ROLLBACK")==1 for c in connections)


@pytest.mark.parametrize("store_kind",["memory","sqlite"])
@pytest.mark.parametrize("failure",["label_error","cancel","invalid_label","revoked"])
def test_failed_turn_keeps_last_report_and_failed_replay_does_not_read(database,tmp_path,traced,store_kind,failure):
    sessions=InMemorySessionStore() if store_kind=="memory" else SQLiteSessionStore(tmp_path/'sessions.sqlite')
    revoked=[False]
    def current_policy(actor):
        result=policy(actor)
        return AccessScope(result.datasets[:1]) if revoked[0] else result
    adapter=ControlledAdapter(database);sdk=engine(adapter,read_consistency="snapshot",sessions=sessions,policy=current_policy)
    session=sdk.create_session(ACTOR).session_id
    good=submit(sdk,session=session)
    assert good.status=="report_ready"
    original_read=adapter.read;adapter.calls=[]
    def failed_read(executor,report,limits,cancel):
        result=original_read(executor,report,limits,cancel)
        if len(adapter.calls)==1:
            if failure=="cancel":cancel.set()
            if failure=="revoked":revoked[0]=True
        elif failure=="label_error":
            raise SDKError("execution_failed","Synthetic failure",retryable=True)
        elif failure=="invalid_label":
            return replace(result,rows=(("invalid",),))
        return result
    adapter.read=failed_read
    reply=submit(sdk,session=session,request="failed",revision=1)
    assert reply.status in ("failed","blocked") and reply.report is None,reply.to_dict()
    assert_clean(traced)
    assert sdk.get_session(session,ACTOR)["last_report_id"]==good.report.id
    calls=len(adapter.calls)
    replay=submit(sdk,session=session,request="failed",revision=1)
    assert replay.report is None and len(adapter.calls)==calls
    if failure=="revoked":
        with pytest.raises(SDKError):sdk.get_report(session,good.report.id,ACTOR)
    else:
        assert sdk.get_report(session,good.report.id,ACTOR)==good.report


def test_success_uses_one_connection_cleans_before_session_publication(database,traced):
    class Store(InMemorySessionStore):
        def complete(self,*args):
            assert_clean(traced)
            return super().complete(*args)
    reply=submit(engine(SQLiteAdapter(database),sessions=Store(),read_consistency="snapshot"))
    assert reply.status=="report_ready" and len(traced)==1


def test_scope_closed_failure_and_thread_confinement(database,traced):
    adapter=SQLiteAdapter(database);limits=ExecutionLimits()
    prepared=prepare_request(catalog(),spec(),policy(ACTOR),date(2026,10,7))[0]
    with pytest.raises(SDKError):
        with adapter.read_scope(limits) as read:
            def wrong_thread():
                with pytest.raises(SDKError):read.execute(prepared,limits)
            thread=Thread(target=wrong_thread);thread.start();thread.join(2)
            assert not thread.is_alive()
    with pytest.raises(SDKError):read.execute(prepared,limits)
    assert_clean(traced)


def test_custom_adapter_missing_capability_never_executes(database):
    class Plain:
        def execute(self,*args,**options):pytest.fail("Unsupported adapter executed")
    reply=submit(engine(Plain(),read_consistency="snapshot"))
    assert reply.status=="unsupported" and reply.error["reason"]=="consistency_unavailable"
    assert reply.error["field"]=="read_consistency"


def test_cached_and_saved_compatibility_report_cannot_claim_snapshot(database):
    sessions=InMemorySessionStore();legacy=engine(SQLiteAdapter(database),sessions=sessions)
    session=legacy.create_session(ACTOR).session_id;good=submit(legacy,session=session)
    strong=engine(SQLiteAdapter(database),sessions=sessions,read_consistency="snapshot")
    replay=submit(strong,session=session)
    assert replay.error["code"]=="request_conflict"
    with pytest.raises(SDKError) as failure:strong.get_report(session,good.report.id,ACTOR)
    assert failure.value.reason=="consistency_unavailable"
    assert legacy.get_report(session,good.report.id,ACTOR)==good.report


def test_revocation_during_scope_cleanup_is_checked_before_publication(database):
    revoked=[False]
    class Adapter(ControlledAdapter):
        @contextmanager
        def read_scope(self,*args,**options):
            with super().read_scope(*args,**options) as read:yield read
            revoked[0]=True
    def current_policy(actor):
        result=policy(actor);return AccessScope(result.datasets[:1]) if revoked[0] else result
    sdk=engine(Adapter(database),policy=current_policy,read_consistency="snapshot")
    session=sdk.create_session(ACTOR).session_id;reply=submit(sdk,session=session)
    assert reply.status=="blocked" and reply.error["code"]=="access_denied"
    assert sdk.get_session(session,ACTOR)["last_report_id"] is None


def test_ambiguous_lookup_clarifies_and_closes_scope(database,traced):
    with transaction(database) as c:c.execute("INSERT INTO private_people VALUES(1,0,3,'Ada')")
    adapter=ControlledAdapter(database);sdk=engine(adapter,provider=Provider(spec(filters=(UserFilter("owner_lookup","eq",("Ada",)),))),read_consistency="snapshot")
    reply=submit(sdk,message='Show amount for "Ada" in September 2026.')
    assert reply.status=="needs_clarification" and len(adapter.calls)==1 and reply.report is None
    assert_clean(traced)


def test_single_query_snapshot_report_has_no_label_read(database,traced):
    adapter=ControlledAdapter(database)
    sdk=engine(adapter,provider=Provider(spec(dimension_ids=(),order_by=None)),read_consistency="snapshot")
    reply=submit(sdk,message="Show amount in September 2026.")
    assert reply.status=="report_ready" and reply.report.rows==((Decimal(30),),)
    assert len(adapter.calls)==1 and len(traced)==1
    assert_clean(traced)


def test_scope_cleanup_precedes_failed_publication(database,traced):
    class Store(InMemorySessionStore):
        fail=False
        def complete(self,*args):
            assert_clean(traced)
            if self.fail:raise SDKError("storage_failed","Synthetic publication failure")
            return super().complete(*args)
    store=Store();sdk=engine(SQLiteAdapter(database),sessions=store,read_consistency="snapshot")
    session=sdk.create_session(ACTOR).session_id;good=submit(sdk,session=session)
    store.fail=True;failed=submit(sdk,session=session,request="second",revision=1)
    assert failed.error["code"]=="storage_failed" and failed.report is None
    assert sdk.get_report(session,good.report.id,ACTOR)==good.report
    assert sdk.get_session(session,ACTOR)["last_report_id"]==good.report.id
    assert_clean(traced)


def test_new_strong_report_replays_without_query_and_is_owned(database,traced,tmp_path):
    store=SQLiteSessionStore(tmp_path/'sessions.sqlite')
    sdk=engine(SQLiteAdapter(database),sessions=store,read_consistency="snapshot")
    session=sdk.create_session(ACTOR).session_id;first=submit(sdk,session=session)
    other=engine(SQLiteAdapter(database),sessions=SQLiteSessionStore(tmp_path/'sessions.sqlite'),read_consistency="snapshot")
    replay=submit(other,session=session)
    assert replay.report==first.report and len(traced)==1
    assert other.get_report(session,first.report.id,ACTOR)==first.report
    with pytest.raises(SDKError):other.get_report(session,first.report.id,ActorContext(ACTOR.subject,"2"))
    assert_clean(traced)


@pytest.mark.parametrize("replacement",["limits","cancel"])
def test_bound_scope_does_not_allow_budget_or_cancel_replacement(database,traced,replacement):
    limits=ExecutionLimits();cancel=Event();adapter=SQLiteAdapter(database)
    prepared=prepare_request(catalog(),spec(),policy(ACTOR),date(2026,10,7))[0]
    with pytest.raises(SDKError):
        with adapter.read_scope(limits,cancel=cancel) as read:
            with pytest.raises(SDKError) as failure:
                read.execute(prepared,replace(limits,max_rows=1000) if replacement=="limits" else limits,
                             cancel=Event() if replacement=="cancel" else cancel)
            assert failure.value.code=="invalid_input"
    assert_clean(traced)


def test_scope_vm_budget_is_shared_across_queries(database):
    with transaction(database) as c:
        c.executemany("INSERT INTO private_fact VALUES (1,0,1,'2026-09-01',1)",[()] * 500)
    limits=ExecutionLimits();adapter=SQLiteAdapter(database,max_vm_steps=200000)
    prepared=prepare_request(catalog(),spec(dimension_ids=(),order_by=None),policy(ACTOR),date(2026,10,7))[0]
    successes=0
    with pytest.raises(SDKError) as failure:
        with adapter.read_scope(limits) as read:
            for _ in range(100):
                read.execute(prepared,limits);successes+=1
    assert failure.value.code=="query_work_limit" and 1<successes<100


def test_scope_covers_two_registered_relationship_sources(database,traced):
    team=Table("private_team")
    ds=DatasetDefinition("teams","Teams",team,tuple(Column(team.key,n,t) for n,t in (
        ("tenant","int"),("deleted","int"),("id","int"),("team","text"))),metrics=(),
        dimensions=(DimensionDefinition("team_id","Team identity","id"),DimensionDefinition("team","Team","team")))
    cat=replace(catalog(),datasets=(*catalog().datasets,ds))
    cat=register_relationships(cat,(
        RelationshipDefinition("person_relation","facts","people",(("owner","id"),),
            dimensions=(RelatedDimension("person_text","Person text","name"),)),
        RelationshipDefinition("team_relation","facts","teams",(("owner","id"),),
            dimensions=(RelatedDimension("team","Team","team"),)),))
    access=AccessScope((*policy(ACTOR).datasets,DatasetAccess("teams",policies=(
        RowPolicy("tenant","eq",(1,)),RowPolicy("deleted","eq",(0,))))))
    with transaction(database) as c:
        c.execute("CREATE TABLE private_team(tenant INT, deleted INT, id INT, team TEXT)")
        c.executemany("INSERT INTO private_team VALUES(1,0,?,?)",[(1,"A"),(2,"B")])
    prepared=prepare_request(cat,spec(dimension_ids=("person_text","team")),access,date(2026,10,7))[0]
    adapter=SQLiteAdapter(database);limits=ExecutionLimits()
    with adapter.read_scope(limits) as read:
        first=read.execute(prepared,limits)
        with transaction(database) as c:
            c.execute("UPDATE private_people SET label='Changed' WHERE tenant=1 AND id=1")
            c.execute("UPDATE private_team SET team='C' WHERE id=1")
            c.execute("UPDATE private_fact SET amount=99 WHERE tenant=1 AND owner=1")
        assert read.execute(prepared,limits)==first
    assert first.rows==(("Ada","A",Decimal(10)),("Ben","B",Decimal(20)))
    assert len(traced)==1;assert_clean(traced)


@pytest.mark.parametrize("mode",[None,False,[],"statement","SNAPSHOT"])
def test_invalid_consistency_is_a_host_configuration_error(database,mode):
    with pytest.raises(ValueError):engine(SQLiteAdapter(database),read_consistency=mode)


def test_sqlite_scope_accepts_python310_authorizer_contract(database,monkeypatch):
    class Python310Connection(sqlite3.Connection):
        def set_authorizer(self,callback):
            if callback is None:raise TypeError("Python 3.10 requires a callable authorizer")
            return super().set_authorizer(callback)
    def connect(*args,**options):return CONNECT(*args,**options,factory=Python310Connection)
    monkeypatch.setattr(consistency,"sqlite3",SimpleNamespace(connect=connect,Error=sqlite3.Error))
    reply=submit(engine(SQLiteAdapter(database),read_consistency="snapshot"))
    assert reply.status=="report_ready",reply.to_dict()
