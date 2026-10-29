"""Measure controlled SQLite read schedules. Synthetic/offline only."""
from __future__ import annotations

import argparse
from contextlib import contextmanager, closing
from datetime import date
from decimal import Decimal
import hashlib
import json
import os
from pathlib import Path
import platform
import sqlite3
import tempfile
import time
from types import SimpleNamespace
from unittest.mock import patch

from sageql import Column, Table
from sageql.sdk import (
    AccessScope, ActorContext, DatasetAccess, DatasetDefinition, DimensionDefinition,
    EntityLabelDimension, ExecutionLimits, FilterDefinition, Interpretation,
    MetricDefinition, PeriodSelection, ReportingCatalog, ReportSpec, RowPolicy,
    SDKError, SageQL, SQLiteAdapter, TimeDefinition,
)
from sageql.sdk import adapters, consistency


def host():
    sales, people = Table("synthetic_sales"), Table("synthetic_people")
    catalog = ReportingCatalog((
        DatasetDefinition("sales", "Sales", sales,
            tuple(Column(sales.key, n, t) for n,t in (("tenant","int"),("owner","int"),("day","date"),("amount","decimal"))),
            metrics=(MetricDefinition("sales", "Sales", "sum", "amount"),),
            dimensions=(EntityLabelDimension("person_name", "Person name", "owner", "people", "person", "person_filter", ("name",)),),
            time=TimeDefinition("day")),
        DatasetDefinition("people", "People", people,
            tuple(Column(people.key,n,t) for n,t in (("tenant","int"),("id","int"),("label","text"))),metrics=(),
            dimensions=(DimensionDefinition("person","Person","id"),DimensionDefinition("name","Name","label")),
            filters=(FilterDefinition("person_filter","Person","id"),)),
    ))
    scope = AccessScope(tuple(DatasetAccess(k, policies=(RowPolicy("tenant","eq",(1,)),)) for k in ("sales","people")))
    spec = ReportSpec("sales", ("sales",), ("person_name",), period=PeriodSelection("month",year=2026,month=9),
                      order_by="sales", limit=2)
    class Provider:
        def interpret(self,*unused):return Interpretation("ready",spec)
    return catalog, scope, Provider()


class TraceCursor(sqlite3.Cursor):
    closed = False
    def close(self):
        super().close();self.closed=True


class TraceConnection(sqlite3.Connection):
    def __init__(self,*args,**options):
        super().__init__(*args,**options)
        self.events=[];self.handles=[];self.closed=False;self.rollbacks=0
        self.set_trace_callback(lambda text:self.events.append(text.split()[0].upper()))
    def execute(self,sql,parameters=()):
        cursor=self.cursor(factory=TraceCursor);self.handles.append(cursor)
        try:return cursor.execute(sql,parameters)
        except BaseException:cursor.close();raise
    def rollback(self):
        self.rollbacks+=1;return super().rollback()
    def close(self):
        super().close();self.closed=True


def normalized(rows):
    return [[str(v.normalize()) if isinstance(v,Decimal) else v for v in row] for row in rows]


def scenario(directory, mode, mutation):
    path=directory/(mode+"-"+mutation+".sqlite")
    with closing(sqlite3.connect(path)) as writer, writer:
        assert writer.execute("PRAGMA journal_mode=WAL").fetchone()[0]=="wal"
        writer.execute("CREATE TABLE synthetic_sales(tenant INT, owner INT, day DATE, amount DECIMAL)")
        writer.execute("CREATE TABLE synthetic_people(tenant INT, id INT, label TEXT)")
        writer.executemany("INSERT INTO synthetic_sales VALUES(?,?,?,?)",[(1,1,"2026-09-01","10.25"),(1,2,"2026-09-01","20.50"),(2,1,"2026-09-01","900")])
        writer.executemany("INSERT INTO synthetic_people VALUES(?,?,?)",[(1,1,"Ada"),(1,2,"Ben"),(2,1,"Hidden")])
    observed=[]
    def connect(*args,**options):
        assert options.get("uri") and "mode=ro" in args[0]
        connection=sqlite3.connect(*args,**options,factory=TraceConnection);observed.append(connection);return connection
    proxy=SimpleNamespace(**{n:getattr(sqlite3,n) for n in dir(sqlite3) if not n.startswith("__")})
    proxy.connect=connect
    class Database:
        def __init__(self):self.inner=SQLiteAdapter(path);self.reads=0
        def execute_bound(self,executor,report,limits,cancel):
            self.reads+=1
            if self.reads==2 and mutation=="failure":raise SDKError("execution_failed","Synthetic injected failure",retryable=True)
            result=executor.execute(report,limits,cancel=cancel)
            if self.reads==1:
                if mutation=="cancel":cancel.set()
                elif mutation in ("update","rollback","delete","insert"):
                    with closing(sqlite3.connect(path)) as writer, writer:
                        if mutation in ("update","rollback"):
                            writer.execute("UPDATE synthetic_sales SET amount=99.75 WHERE tenant=1 AND owner=1")
                            writer.execute("UPDATE synthetic_people SET label='Changed' WHERE tenant=1 AND id=1")
                        elif mutation=="delete":
                            writer.execute("DELETE FROM synthetic_sales WHERE tenant=1 AND owner=1")
                            writer.execute("DELETE FROM synthetic_people WHERE tenant=1 AND id=1")
                        else:writer.execute("INSERT INTO synthetic_people VALUES(1,1,'Conflicting')")
                        if mutation=="rollback":writer.rollback()
            return result
        def execute(self,report,limits,*,cancel=None):return self.execute_bound(self.inner,report,limits,cancel)
        @contextmanager
        def read_scope(self,limits,*,cancel=None):
            owner=self
            class Bound:
                def execute(self,report,limits,*,cancel=None):return owner.execute_bound(read,report,limits,cancel)
            with self.inner.read_scope(limits,cancel=cancel) as read:yield Bound()
    catalog,scope,provider=host();database=Database();actor=ActorContext("synthetic-reader","1")
    sdk=SageQL(catalog=catalog,database=database,provider=provider,policy=lambda unused:scope,
        execution="validated",read_consistency=mode,clock=lambda:date(2026,10,7),language="en")
    start=time.monotonic()
    with patch.object(adapters,"sqlite3",proxy),patch.object(consistency,"sqlite3",proxy):
        session=sdk.create_session(actor).session_id
        reply=sdk.submit(session,"Show sales by person name in September 2026.",actor,"first",0)
    old=[["Ada","10.25"],["Ben","20.5"]]
    expected_status="report_ready";expected_rows=old;expected_error=None
    if mutation=="cancel":expected_status="failed";expected_rows=None;expected_error="cancelled"
    elif mutation=="failure":expected_status="failed";expected_rows=None;expected_error="execution_failed"
    elif mode=="compatibility" and mutation=="update":expected_rows=[["Changed","10.25"],["Ben","20.5"]]
    elif mode=="compatibility" and mutation=="delete":expected_rows=[["Name unavailable","10.25"],["Ben","20.5"]]
    elif mode=="compatibility" and mutation=="insert":expected_status="blocked";expected_rows=None;expected_error="entity_label_conflict"
    actual_rows=normalized(reply.report.rows) if reply.report else None
    cleaned=all(c.closed and c.rollbacks==1 and all(p.closed for p in c.handles) for c in observed)
    actual_error=reply.error["code"] if reply.error else None
    result={"scenario":mutation,"database":"SQLite","database_version":sqlite3.sqlite_version,
        "driver":"sqlite3 stdlib","journal_mode":"wal","isolation_mode":mode,
        "expected":{"status":expected_status,"rows":expected_rows,"error":expected_error},
        "actual":{"status":reply.status,"rows":actual_rows,"error":actual_error},
        "transaction_boundaries":{"connections":len(observed),"begin":sum(c.events.count("BEGIN") for c in observed),
            "rollback_calls":sum(c.rollbacks for c in observed),"sql_rollback":sum(c.events.count("ROLLBACK") for c in observed),
            "all_connections_closed":all(c.closed for c in observed),"all_cursors_closed":all(p.closed for c in observed for p in c.handles)},
        "cleanup":cleaned,"seconds":round(time.monotonic()-start,4),"execution_status":"executed",
        "classification":"demonstrated compatibility read skew" if mode=="compatibility" and mutation in ("update","delete") else "contract check",
        "passed":reply.status==expected_status and actual_rows==expected_rows and actual_error==expected_error and cleaned}
    if mode=="snapshot":result["passed"] &= result["transaction_boundaries"]["connections"]==1 and result["transaction_boundaries"]["begin"]==1
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("--output",type=Path,required=True);args=p.parse_args()
    output=args.output.resolve()
    if output.exists():p.error("Choose a fresh output path")
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent,prefix="synthetic-") as directory:
        root=Path(directory).resolve();assert root.is_relative_to(output.parent)
        results=[scenario(root,mode,case) for mode in ("compatibility","snapshot") for case in ("none","update","rollback","insert","delete","cancel","failure")]
    import sageql
    source=Path(sageql.__file__).parent;digest=hashlib.sha256()
    for file in sorted(source.rglob("*.py")):digest.update(file.relative_to(source).as_posix().encode());digest.update(file.read_bytes())
    record={"schema_version":1,"phase":11,"synthetic_only":True,"python":platform.python_version(),"platform":platform.platform(),
        "source_sha256":digest.hexdigest(),"cases":results,"sql_server":{"execution_status":"not executed","reason":"No approved isolated target supplied"},
        "passed":all(r["passed"] for r in results)}
    temporary=output.with_suffix(".json.tmp")
    with temporary.open("w",encoding="utf-8") as f:json.dump(record,f,indent=2);f.flush();os.fsync(f.fileno())
    os.replace(temporary,output)
    print(json.dumps({"passed":sum(r["passed"] for r in results),"total":len(results),"sql_server":"not executed"}))
    return 0 if record["passed"] else 1


if __name__=="__main__":raise SystemExit(main())
