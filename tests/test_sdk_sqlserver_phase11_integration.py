"""Real SQL Server only after a separately approved synthetic target manifest.

Default/offline CI skips before reading any credentials or loading private files.
Never run against Rahtal/production. See docs/PHASE11_SQLSERVER_TESTING.md.
"""
from contextlib import contextmanager
from datetime import date, datetime
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import platform
import re
from threading import Event, Thread
import time

import pytest

from tools.sqlserver_synthetic import Runtime, load_approval, require

pytestmark = pytest.mark.sqlserver_integration


@pytest.fixture(scope="module")
def runtime(tmp_path_factory):
    approval=load_approval()
    if approval is None:pytest.skip("Phase 11 SQL Server needs separately approved synthetic target/operations")
    pytest.importorskip("pyodbc")
    result=Runtime(approval);result.records=[]
    yield result
    output=Path(os.environ.get("SAGEQL_SQLSERVER_TEST_PHASE11_OUTPUT") or tmp_path_factory.mktemp("phase11-sqlserver")/"results.json")
    if output.exists():raise ValueError("Preserve first integration evidence; choose a fresh output")
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps({"schema_version":1,"python":platform.python_version(),"platform":platform.platform(),
        "synthetic_only":True,"approval_sha256":hashlib.sha256(json.dumps(approval,sort_keys=True).encode()).hexdigest(),
        "driver":result.metadata,"scenarios":result.records},indent=2),encoding="utf-8")


@contextmanager
def measured(runtime, name, isolation):
    record={"scenario":name,"database":"SQL Server","isolation_mode":isolation,"execution_status":"running"}
    start=time.monotonic()
    try:
        yield record
        record["execution_status"]="passed"
    except pytest.skip.Exception:
        record["execution_status"]="not executed; capability or operation unavailable"
        raise
    except BaseException:
        record["execution_status"]="failed"
        raise
    finally:
        record["seconds"]=round(time.monotonic()-start,3)
        record["driver"]=dict(runtime.metadata)
        runtime.records.append(record)


def test_opt_in_phase11_driver_types_unicode_policies_and_collation(runtime):
    from sageql.sdk import AccessScope,ActorContext,DatasetAccess,ExecutionLimits,Interpretation,PeriodSelection,ReportSpec,RowPolicy,SageQL,SQLServerAdapter
    with measured(runtime,"driver types, Unicode, collation and tenant policies","compatibility") as record:
        with runtime.fixtures():
            with runtime.connection() as connection:
                cursor=connection.cursor()
                try:
                    cursor.execute("SELECT amount,rate,note,day,stamp FROM "+runtime.name("facts")+" WHERE tenant=? AND deleted=? AND owner=?",1,0,1)
                    rows=cursor.fetchmany(2)
                    typed=(len(rows)==1 and type(rows[0][0]) is Decimal and rows[0][0]==Decimal("10.2500")
                           and rows[0][0].as_tuple().exponent==-4 and type(rows[0][1]) is float and rows[0][1]==1.25 and rows[0][2] is None
                           and type(rows[0][3]) is date and rows[0][3]==date(2026,9,1)
                           and rows[0][4]==datetime(2026,9,1,12,30))
                    require(typed,"scalar mapping")
                    cursor.execute("SELECT COUNT(*) FROM "+runtime.name("people")+" WHERE tenant=? AND label=?",1,"ada")
                    require(cursor.fetchone()[0]==0,"case-sensitive fixture collation")
                finally:cursor.close()
            class Provider:
                def interpret(self,*args):return Interpretation("ready",ReportSpec("facts",("amount",),("owner_name",),
                    period=PeriodSelection("month",year=2026,month=9),order_by="amount",limit=2))
            def policy(actor):return AccessScope(tuple(DatasetAccess(k,policies=(RowPolicy("tenant","eq",(int(actor.tenant_id),)),RowPolicy("deleted","eq",(0,)))) for k in ("facts","people")))
            sdk=SageQL(catalog=runtime.catalog(),database=SQLServerAdapter(lambda:runtime.connect()),provider=Provider(),policy=policy,
                execution="validated",clock=lambda:date(2026,10,7),language="en",limits=ExecutionLimits(query_timeout_seconds=runtime.approval["query_timeout_seconds"]))
            actor=ActorContext("synthetic","1");session=sdk.create_session(actor).session_id
            reply=sdk.submit(session,"Show amount by owner name in September 2026.",actor,"first",0)
            expected=(("Ada",Decimal("10.25")),("کیان نمونه",Decimal("20.5")))
            require(reply.status=="report_ready" and reply.report.rows==expected,"Unicode report and policies")
            record.update(expected={"rows":[["Ada","10.25"],["کیان نمونه","20.5"]]},actual={"matched_expected":True},cleanup="driver rollback/close completed; server observation separate")
        record["server_cleanup"]=runtime.observe_closed_sessions()


@pytest.mark.parametrize("mode",["compatibility","snapshot"])
@pytest.mark.parametrize("mutation",["update","rollback","insert","delete"])
def test_opt_in_phase11_controlled_concurrent_commit(runtime,mode,mutation):
    from sageql.sdk import AccessScope,ActorContext,DatasetAccess,ExecutionLimits,Interpretation,PeriodSelection,ReportSpec,RowPolicy,SageQL,SQLServerAdapter
    required="update" if mutation=="rollback" else mutation
    with measured(runtime,mutation+" between aggregate and labels",mode) as record:
        if runtime.approval["fixture_policy"]!="create_drop" or not runtime.allowed(required+"_fixture"):
            pytest.skip("Disposable mutation/cleanup operations not approved")
        with runtime.fixtures():
            adapter=SQLServerAdapter(lambda:runtime.connect(),snapshot_connection_factory=lambda:runtime.connect(snapshot=True))
            calls=[]
            class Database:
                def read(self,executor,report,limits,cancel):
                    result=executor.execute(report,limits,cancel=cancel);calls.append(report.dataset.id)
                    if len(calls)==1:runtime.mutate(required,commit=mutation!="rollback")
                    return result
                def execute(self,report,limits,*,cancel=None):return self.read(adapter,report,limits,cancel)
                @contextmanager
                def read_scope(self,limits,*,cancel=None):
                    owner=self
                    class Bound:
                        def execute(self,report,limits,*,cancel=None):return owner.read(read,report,limits,cancel)
                    with adapter.read_scope(limits,cancel=cancel) as read:yield Bound()
            class Provider:
                def interpret(self,*args):return Interpretation("ready",ReportSpec("facts",("amount",),("owner_name",),
                    period=PeriodSelection("month",year=2026,month=9),order_by="amount",limit=2))
            scope=AccessScope(tuple(DatasetAccess(k,policies=(RowPolicy("tenant","eq",(1,)),RowPolicy("deleted","eq",(0,)))) for k in ("facts","people")))
            sdk=SageQL(catalog=runtime.catalog(),database=Database(),provider=Provider(),policy=lambda a:scope,execution="validated",
                clock=lambda:date(2026,10,7),language="en",read_consistency=mode,
                limits=ExecutionLimits(query_timeout_seconds=runtime.approval["query_timeout_seconds"]))
            actor=ActorContext("synthetic","1");session=sdk.create_session(actor).session_id
            reply=sdk.submit(session,"Show amount by owner name in September 2026.",actor,"first",0)
            if reply.error and reply.error.get("reason")=="consistency_unavailable":
                record["actual"]={"snapshot_capability":"unavailable; no downgrade"}
                pytest.skip("Database snapshot capability unavailable; configuration unchanged")
            expected=(("Ada",Decimal("10.25")),("کیان نمونه",Decimal("20.5")))
            if mode=="compatibility" and mutation=="insert":
                require(reply.error and reply.error["code"]=="entity_label_conflict","insert conflict")
            else:
                if mode=="compatibility" and mutation=="update":expected=(("Changed",Decimal("10.25")),expected[1])
                if mode=="compatibility" and mutation=="delete":expected=(("Name unavailable",Decimal("10.25")),expected[1])
                require(reply.status=="report_ready" and reply.report.rows==expected,"controlled read view")
            record.update(expected={"view":"before commit" if mode=="snapshot" else "per-read committed state"},actual={"matched_expected":True},
                          transaction_boundaries={"contributing_reads":calls,"mode":mode},cleanup="adapter and fixture cleanup completed")
        record["server_cleanup"]=runtime.observe_closed_sessions()


@pytest.mark.parametrize("probe",["timeout","cancel"])
def test_opt_in_phase11_real_driver_timeout_and_cancel(runtime,probe):
    with measured(runtime,"fixed bounded driver WAITFOR "+probe,"driver manual transaction") as record:
        if not runtime.allowed("waitfor_probe"):pytest.skip("Fixed timing probe not approved")
        if probe=="cancel" and not runtime.allowed("observe_sessions"):
            pytest.skip("Deterministic server WAITFOR checkpoint observation not approved")
        for cancel in (probe=="cancel",):
            with runtime.connection() as connection:
                connection.timeout=runtime.approval["query_timeout_seconds"] if cancel else 1
                cursor=connection.cursor();started=Event();done=Event();cancel_called=Event()
                observer_failed=Event()
                def cancel_cursor():
                    try:
                        if not started.wait(2):return
                        with runtime.connection("observer") as observer:
                            checkpoint=observer.cursor()
                            try:
                                runtime.verify_observer_permission(checkpoint)
                                while not done.is_set() and time.monotonic()<runtime.deadline:
                                    checkpoint.execute("SELECT COUNT(*) FROM sys.dm_exec_requests AS r JOIN sys.dm_exec_sessions AS s ON s.session_id=r.session_id WHERE s.program_name=? AND r.wait_type='WAITFOR'",runtime.application)
                                    if checkpoint.fetchone()[0]:
                                        cursor.cancel();cancel_called.set();return
                                    done.wait(0.01)
                            finally:checkpoint.close()
                    except Exception:observer_failed.set()
                thread=Thread(target=cancel_cursor,daemon=True) if cancel else None
                state=None
                try:
                    if thread:thread.start()
                    started.set()
                    try:cursor.execute("WAITFOR DELAY '00:00:05'")
                    except Exception as error:state=error.args[0] if error.args else None
                    require(state in ({"HY008"} if cancel else {"HYT00","HYT01"}),"driver timeout/cancellation SQLSTATE")
                finally:
                    done.set()
                    if thread:thread.join(2)
                    cursor.close()
                if cancel:require(cancel_called.is_set() and not observer_failed.is_set() and not thread.is_alive(),"cancel completion")
        record.update(expected={probe:True},actual={probe:True,"sqlstate":state},cleanup="rollback and close attempted/completed")


def test_opt_in_phase11_reader_write_permission_denied(runtime):
    with measured(runtime,"explicit read-only principal probe","manual rollback") as record:
        if not runtime.allowed("reader_denial_probe"):pytest.skip("Reader permission probe not approved")
        with runtime.fixtures():
            with runtime.connection() as connection:
                cursor=connection.cursor();denied=False
                try:
                    try:cursor.execute("INSERT INTO "+runtime.name("people")+" VALUES (1,0,999999,?)","rollback-only permission probe")
                    except Exception as error:
                        denied=bool(error.args and error.args[0]=="42000" and re.search(r"\(229\)",str(error.args[1:])))
                finally:cursor.close()
                require(denied,"reader principal had write permission")
        record.update(expected={"write_denied":True},actual={"write_denied":True},cleanup="uncommitted probe rolled back")
