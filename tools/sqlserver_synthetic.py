"""Separately approved, disposable SQL Server fixture support. No default access.

Only test-specific credentials are read, after full approval validation. This
module never loads .env, creates a database, changes isolation options or retries.
"""
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
import json
import math
import os
from pathlib import Path
import re
import time
from uuid import uuid4


OPERATIONS = {"select", "create_fixture", "insert_fixture", "update_fixture",
              "delete_fixture", "drop_fixture", "waitfor_probe", "reader_denial_probe", "observe_sessions"}


def validate_approval(value):
    """Reject incomplete approval before imports, credentials or connections."""
    required={"version","authorized","synthetic_only","authorization_id","server","database","driver",
              "authentication","schema","fixture_policy","tables","allowed_operations","network_exposure",
              "cleanup_policy","connect_timeout_seconds","query_timeout_seconds","max_seconds"}
    if not isinstance(value,dict) or set(value)!=required:
        raise ValueError("Exact synthetic integration approval fields are required")
    if type(value["version"]) is not int or value["version"]!=1 or value["authorized"] is not True or value["synthetic_only"] is not True:
        raise ValueError("Explicit synthetic integration authorization is required")
    for key in ("authorization_id","server","database","driver","network_exposure","cleanup_policy"):
        if not isinstance(value[key],str) or not 1<=len(value[key])<=256 or any(c in value[key] for c in "\x00\r\n"):
            raise ValueError("Bounded reviewed target and operational fields are required")
    if not value["database"].startswith("SageQL_Phase11_"):
        raise ValueError("Use an explicitly isolated SageQL_Phase11_ database")
    if value["authorization_id"].startswith("REQUIRES_") or value["network_exposure"].startswith("REVIEW_"):
        raise ValueError("Replace approval placeholders after explicit human review")
    if value["authentication"] not in ("sql","integrated") or value["fixture_policy"] not in ("host_seeded","create_drop"):
        raise ValueError("Reviewed authentication and fixture policy are required")
    if not isinstance(value["schema"],str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]{0,63}",value["schema"]):
        raise ValueError("A bounded fixture schema identifier is required")
    ops=value["allowed_operations"]
    if not isinstance(ops,list) or not all(isinstance(k,str) for k in ops) or len(set(ops))!=len(ops) or not set(ops)<=OPERATIONS or "select" not in ops:
        raise ValueError("Explicit supported synthetic operations are required")
    for key,cap in (("connect_timeout_seconds",5),("query_timeout_seconds",5),("max_seconds",120)):
        if type(value[key]) is not int or not 1<=value[key]<=cap:
            raise ValueError("Finite synthetic integration limits are required")
    if value["fixture_policy"]=="create_drop":
        if value["tables"]!={} or not {"create_fixture","insert_fixture","drop_fixture"}<=set(ops) or value["cleanup_policy"]!="drop_created_fixtures":
            raise ValueError("Fixture creation requires explicit creation/seeding/drop approval")
    else:
        if not isinstance(value["tables"],dict) or set(value["tables"])!={"facts","people"} or value["cleanup_policy"]!="leave_host_seeded_unchanged":
            raise ValueError("Host-seeded fixtures must be identified and left unchanged")
        for name in value["tables"].values():
            if not isinstance(name,str) or not re.fullmatch(r"sageql_phase11_[A-Za-z0-9_]{1,80}",name):
                raise ValueError("Only explicitly named synthetic fixture tables are supported")
    return dict(value)


def load_approval():
    if os.environ.get("SAGEQL_SQLSERVER_TEST_CONFIRM_PHASE11")!="1":
        return None
    path=os.environ.get("SAGEQL_SQLSERVER_TEST_PHASE11_APPROVAL")
    if not path:raise ValueError("An approved synthetic target manifest is required")
    return validate_approval(json.loads(Path(path).read_text(encoding="utf-8")))


def require(condition, reason):
    if not condition:raise AssertionError("Synthetic SQL Server check failed: "+reason)


def _brace(value):return "{"+value.replace("}","}}")+"}"


@dataclass
class Runtime:
    approval: dict = field(repr=False)
    connections: list = field(default_factory=list,repr=False)
    metadata: dict = field(default_factory=dict)

    def __post_init__(self):
        self.approval=validate_approval(self.approval)
        self.application="SageQLPhase11-"+uuid4().hex
        self.deadline=time.monotonic()+self.approval["max_seconds"]
        self.tables=(dict(self.approval["tables"]) if self.approval["fixture_policy"]=="host_seeded" else
                     {k:"sageql_phase11_"+uuid4().hex+"_"+k for k in ("facts","people")})

    def allowed(self,*operations):return set(operations)<=set(self.approval["allowed_operations"])

    def name(self,key):return "["+self.approval["schema"]+"].["+self.tables[key]+"]"

    def connect(self,role="reader",*,snapshot=False,cleanup=False):
        if role not in ("reader","writer","observer"):
            raise ValueError("An explicitly supported synthetic connection role is required")
        if role=="observer" and not self.allowed("observe_sessions"):
            raise ValueError("Session observation is not approved")
        if role=="writer" and not set(self.approval["allowed_operations"]) & {"create_fixture","insert_fixture","update_fixture","delete_fixture","drop_fixture"}:
            raise ValueError("Synthetic writer access is not approved")
        remaining=self.deadline-time.monotonic()
        if remaining<=0 and not cleanup:raise RuntimeError("Synthetic integration time budget exhausted")
        import pyodbc
        # Test process only; no live connection may predate this fixture. A host
        # pool needs its own reset/discard verification beyond this suite.
        pyodbc.pooling=False
        a=self.approval
        parts=["DRIVER="+_brace(a["driver"]),"SERVER="+_brace(a["server"]),"DATABASE="+_brace(a["database"]),
               "Encrypt=yes","TrustServerCertificate=no","APP="+_brace(self.application+("-observer" if role=="observer" else ""))]
        if a["authentication"]=="integrated":parts.append("Trusted_Connection=yes")
        else:
            prefix="SAGEQL_SQLSERVER_TEST_PHASE11_"+("" if role=="reader" else role.upper()+"_")
            user,password=os.environ.get(prefix+"USERNAME"),os.environ.get(prefix+"PASSWORD")
            if not user or not password:raise ValueError("Approved test-specific credentials are missing")
            parts.extend(("UID="+_brace(user),"PWD="+_brace(password)))
        connection=None
        try:
            connection=pyodbc.connect(";".join(parts)+";",timeout=min(a["connect_timeout_seconds"],max(1,math.ceil(remaining))),autocommit=False)
            connection.timeout=min(a["query_timeout_seconds"],max(1,math.ceil(remaining)))
            if snapshot:
                # Microsoft SQL_COPT_SS_TXN_ISOLATION / SQL_TXN_SS_SNAPSHOT.
                # Driver-specific ODBC attributes; selected before any SQL.
                connection.set_attr(1227,32)
            self.metadata.update(driver_name=connection.getinfo(pyodbc.SQL_DRIVER_NAME),
                                 driver_version=connection.getinfo(pyodbc.SQL_DRIVER_VER),
                                 dbms_version=connection.getinfo(pyodbc.SQL_DBMS_VER))
            self.connections.append(connection)
            return connection
        except Exception:
            if connection is not None:
                try:connection.close()
                except Exception:pass
            raise RuntimeError("Approved synthetic SQL Server connection failed") from None

    @contextmanager
    def connection(self,role="reader",*,snapshot=False,cleanup=False):
        value=self.connect(role,snapshot=snapshot,cleanup=cleanup)
        try:
            yield value
        except Exception:
            raise RuntimeError("Approved synthetic SQL Server operation failed") from None
        finally:
            failed=False
            for operation in (value.rollback,value.close):
                try:operation()
                except Exception:failed=True
            if failed:raise RuntimeError("Synthetic connection cleanup failed") from None

    def catalog(self):
        from sageql import Column,Table
        from sageql.sdk import (DatasetDefinition,DimensionDefinition,EntityLabelDimension,FilterDefinition,
                               MetricDefinition,ReportingCatalog,TimeDefinition)
        fact=Table(self.tables["facts"],self.approval["schema"]);people=Table(self.tables["people"],self.approval["schema"])
        return ReportingCatalog((
            DatasetDefinition("facts","Amount",fact,tuple(Column(fact.key,n,t) for n,t in (
                ("tenant","int"),("deleted","int"),("owner","int"),("day","date"),("amount","decimal(18,4)"),
                ("rate","float"),("note","nvarchar(100)"),("stamp","datetime2"))),
                metrics=(MetricDefinition("amount","Amount","sum","amount"),),
                dimensions=(EntityLabelDimension("owner_name","Owner name","owner","people","person","person_filter",("name",)),),
                time=TimeDefinition("day")),
            DatasetDefinition("people","People",people,tuple(Column(people.key,n,t) for n,t in (
                ("tenant","int"),("deleted","int"),("id","int"),("label","nvarchar(100)"))),metrics=(),
                dimensions=(DimensionDefinition("person","Person","id"),DimensionDefinition("name","Name","label")),
                filters=(FilterDefinition("person_filter","Person","id"),)),
        ))

    @contextmanager
    def fixtures(self):
        if self.approval["fixture_policy"]=="host_seeded":
            yield self
            return
        created=[]
        try:
            with self.connection("writer") as writer:
                cursor=writer.cursor()
                try:
                    cursor.execute("CREATE TABLE "+self.name("facts")+" (tenant INT NOT NULL, deleted INT NOT NULL, owner INT NOT NULL, day DATE NOT NULL, amount DECIMAL(18,4), rate FLOAT, note NVARCHAR(100), stamp DATETIME2)")
                    created.append("facts")
                    cursor.execute("CREATE TABLE "+self.name("people")+" (tenant INT NOT NULL, deleted INT NOT NULL, id INT NOT NULL, label NVARCHAR(100) COLLATE Latin1_General_100_CS_AS NOT NULL)")
                    created.append("people")
                    for row in [(1,0,1,date(2026,9,1),Decimal("10.2500"),1.25,None,datetime(2026,9,1,12,30)),
                                (1,0,2,date(2026,9,1),Decimal("20.5000"),None,"synthetic",None),
                                (2,0,1,date(2026,9,1),Decimal("900"),None,None,None),
                                (1,1,1,date(2026,9,1),Decimal("800"),None,None,None)]:
                        cursor.execute("INSERT INTO "+self.name("facts")+" VALUES (?,?,?,?,?,?,?,?)",*row)
                    for row in [(1,0,1,"Ada"),(1,0,2,"کیان نمونه"),(2,0,1,"Hidden")]:
                        cursor.execute("INSERT INTO "+self.name("people")+" VALUES (?,?,?,?)",*row)
                    writer.commit()
                finally:cursor.close()
            yield self
        finally:
            if created:
                with self.connection("writer",cleanup=True) as writer:
                    cursor=writer.cursor()
                    try:
                        for key in reversed(created):
                            cursor.execute("SELECT OBJECT_ID(?)",self.approval["schema"]+"."+self.tables[key])
                            if cursor.fetchone()[0] is not None:cursor.execute("DROP TABLE "+self.name(key))
                        writer.commit()
                    finally:cursor.close()

    def mutate(self,operation,*,commit=True):
        if self.approval["fixture_policy"]!="create_drop" or not self.allowed(operation+"_fixture"):
            raise ValueError("This mutation lacks explicit disposable-fixture authorization")
        with self.connection("writer") as writer:
            cursor=writer.cursor()
            try:
                if operation=="update":
                    cursor.execute("UPDATE "+self.name("facts")+" SET amount=? WHERE tenant=1 AND owner=1",Decimal("99.75"))
                    cursor.execute("UPDATE "+self.name("people")+" SET label=? WHERE tenant=1 AND id=1","Changed")
                elif operation=="insert":cursor.execute("INSERT INTO "+self.name("people")+" VALUES (1,0,1,?)","Conflicting")
                elif operation=="delete":
                    cursor.execute("DELETE FROM "+self.name("people")+" WHERE tenant=1 AND id=1")
                    cursor.execute("DELETE FROM "+self.name("facts")+" WHERE tenant=1 AND owner=1")
                writer.commit() if commit else writer.rollback()
            finally:cursor.close()

    def observe_closed_sessions(self):
        if not self.allowed("observe_sessions"):return "unverified; observer not authorized"
        with self.connection("observer") as observer:
            cursor=observer.cursor()
            try:
                self.verify_observer_permission(cursor)
                end=min(self.deadline,time.monotonic()+self.approval["query_timeout_seconds"])
                while True:
                    cursor.execute("SELECT COUNT(*) FROM sys.dm_exec_sessions WHERE program_name = ?",self.application)
                    if cursor.fetchone()[0]==0:break
                    require(time.monotonic()<end,"server sessions remained after lease close")
            finally:cursor.close()
        return "verified by separately approved session observer"

    def verify_observer_permission(self,cursor):
        # Without this check a restricted observer could falsely report zero
        # sessions simply because it cannot see the reader's connection.
        cursor.execute("SELECT CONVERT(int, SERVERPROPERTY('ProductMajorVersion'))")
        permission="VIEW SERVER PERFORMANCE STATE" if cursor.fetchone()[0]>=16 else "VIEW SERVER STATE"
        cursor.execute("SELECT HAS_PERMS_BY_NAME(NULL, 'SERVER', ?)",permission)
        require(cursor.fetchone()[0]==1,"approved observer lacks server visibility")
