"""SQL Server lifecycle/control-flow evidence only; no server/driver execution."""
from datetime import date
from decimal import Decimal
from threading import Event, Thread
from types import SimpleNamespace

import pytest

from sageql.sdk import ExecutionLimits, SDKError, SQLServerAdapter
from sageql.sdk import consistency
from sageql.sdk import adapters
from sageql.sdk.lookups import prepare_request
from test_sdk_read_consistency import ACTOR, catalog, policy, spec


def report():
    return prepare_request(catalog(), spec(), policy(ACTOR), date(2026,10,7))[0]


class Cursor:
    def __init__(self, connection):
        self.connection = connection
        self.closed = False
        self.cancelled = Event()
        self.description = []
        self.phase = None

    def execute(self, sql, *parameters):
        c = self.connection
        c.statements.append((sql, parameters))
        if sql == consistency.SQL_SERVER_SNAPSHOT_STATE:
            self.phase, self.rows = "probe", c.state
        elif "sys.columns" in sql:
            self.phase = "metadata"
            dataset = next(d for d in catalog().datasets if d.table.name == parameters[1])
            self.rows = [(p.name, "nvarchar" if p.data_type == "text" else p.data_type,
                          p.nullable, "U", 18, 2) for p in dataset.columns]
        else:
            c.reads += 1
            self.phase = "report"
            self.rows = c.rows
            self.description = [(k,) for k in c.fields]
            c.started.set()
        if c.fail_phase == self.phase or (self.phase == "report" and c.fail_read == c.reads):
            raise RuntimeError("private driver host and row values")
        return self

    def fetchmany(self, count):
        c = self.connection
        if self.phase == "metadata" and c.after_metadata:
            c.after_metadata()
        if self.phase == c.block_phase:
            self.cancelled.wait(5)
            raise RuntimeError("private timeout message")
        return self.rows[:count]

    def cancel(self):
        self.connection.cancels += 1
        self.cancelled.set()

    def close(self):
        self.closed = True
        if self.connection.fail_cursor_close:
            raise RuntimeError("private cursor cleanup")


class Connection:
    def __init__(self):
        self.autocommit = False
        self.timeout = 0
        self.state = [(5,1)]
        self.rows = [(1,Decimal(10)),(2,Decimal(20))]
        self.fields = ("owner_name", "amount")
        self.statements = []
        self.cursors = []
        self.reads = self.rollbacks = self.closes = self.cancels = 0
        self.fail_phase = self.fail_read = self.block_phase = self.after_metadata = None
        self.fail_cursor_close = self.fail_rollback = self.fail_close = False
        self.started = Event()

    def cursor(self):
        cursor = Cursor(self)
        self.cursors.append(cursor)
        return cursor

    def rollback(self):
        self.rollbacks += 1
        if self.fail_rollback:
            raise RuntimeError("private rollback")

    def close(self):
        self.closes += 1
        if self.fail_close:
            raise RuntimeError("private connection close")


def adapter(connection, **options):
    calls = []
    def lease():
        calls.append(1)
        return connection
    db = SQLServerAdapter(lambda: pytest.fail("Default factory used by snapshot reads"),
                          snapshot_connection_factory=lease, **options)
    return db, calls


def test_same_connection_no_intermediate_rollback_all_cursors_closed():
    c = Connection(); db, calls = adapter(c); limits = ExecutionLimits()
    with db.read_scope(limits) as scope:
        first = scope.execute(report(), limits)
        assert c.rollbacks == c.closes == 0
        second = scope.execute(report(), limits)
        assert first == second
        assert all(p.closed for p in c.cursors)
    assert len(calls) == 1 and c.reads == 2 and c.rollbacks == c.closes == 1
    assert len(c.cursors) == 3
    assert all(sql.startswith("SELECT") for sql, _ in c.statements)
    with pytest.raises(SDKError):
        scope.execute(report(), limits)
    assert c.reads == 2


@pytest.mark.parametrize("state", [[(2,1)],[(2,0)],[(5,0)],[],[(5,1),(5,1)]])
def test_rcsi_disabled_snapshot_or_unverifiable_state_fails_closed(state):
    c = Connection();c.state = state;db, calls = adapter(c)
    with pytest.raises(SDKError) as failure:
        with db.read_scope(ExecutionLimits()):
            pytest.fail("Unavailable capability entered scope")
    assert failure.value.reason == "consistency_unavailable"
    assert c.reads == 0 and c.rollbacks == c.closes == 1


def test_autocommit_is_rejected_without_changing_or_committing_connection():
    c = Connection();c.autocommit = True;db, calls = adapter(c)
    with pytest.raises(SDKError):
        with db.read_scope(ExecutionLimits()):
            pass
    assert c.autocommit is True and not c.statements and c.rollbacks == c.closes == 1


def test_missing_factory_does_not_open_default_connection():
    db = SQLServerAdapter(lambda: pytest.fail("Must not connect"))
    with pytest.raises(SDKError) as failure:
        with db.read_scope(ExecutionLimits()):
            pass
    assert failure.value.code == "unsupported"


@pytest.mark.parametrize("phase", ["probe","metadata","report"])
def test_failed_read_cleans_every_resource_without_retry_or_private_errors(phase):
    c = Connection();c.fail_phase = phase;db,calls = adapter(c);limits = ExecutionLimits()
    with pytest.raises(SDKError) as failure:
        with db.read_scope(limits) as scope:
            scope.execute(report(), limits)
    assert "private" not in str(failure.value)
    assert len(calls) == 1 and c.rollbacks == c.closes == 1 and all(p.closed for p in c.cursors)
    assert c.reads <= 1


@pytest.mark.parametrize("cleanup", ["fail_cursor_close","fail_rollback","fail_close"])
def test_cleanup_failure_prevents_success(cleanup):
    c = Connection();db,calls = adapter(c);limits = ExecutionLimits()
    with pytest.raises(SDKError) as failure:
        with db.read_scope(limits) as scope:
            scope.execute(report(), limits)
            setattr(c, cleanup, True)
            if cleanup == "fail_cursor_close":
                scope.execute(report(), limits)
    assert failure.value.code == "execution_failed"
    assert c.rollbacks == c.closes == 1 and all(p.closed for p in c.cursors)


def test_failed_second_read_poisoned_scope_even_when_caller_catches_error():
    c = Connection();c.fail_read = 2;db,calls = adapter(c);limits = ExecutionLimits()
    with pytest.raises(SDKError):
        with db.read_scope(limits) as scope:
            scope.execute(report(), limits)
            with pytest.raises(SDKError):
                scope.execute(report(), limits)
            with pytest.raises(SDKError):
                scope.execute(report(), limits)
    assert c.reads == 2 and c.rollbacks == c.closes == 1


def test_scope_holds_one_concurrency_slot_until_exit():
    c = Connection();db,calls = adapter(c,max_concurrent_queries=1);limits=ExecutionLimits()
    with db.read_scope(limits):
        with pytest.raises(SDKError) as failure:
            with db.read_scope(limits):
                pass
        assert failure.value.code == "database_busy" and len(calls) == 1
    with db.read_scope(limits):
        pass
    assert len(calls) == 2


def test_actual_watcher_cancellation_uses_event_and_disposes_lease():
    c=Connection();c.block_phase="report";db,calls=adapter(c);cancel=Event();limits=ExecutionLimits()
    def cancel_when_running():
        assert c.started.wait(2)
        cancel.set()
    thread=Thread(target=cancel_when_running);thread.start()
    try:
        with pytest.raises(SDKError) as failure:
            with db.read_scope(limits,cancel=cancel) as scope:
                scope.execute(report(),limits,cancel=cancel)
        assert failure.value.code == "cancelled"
    finally:
        cancel.set();thread.join(2)
    assert not thread.is_alive() and c.cancels and c.rollbacks == c.closes == 1


def test_metadata_deadline_prevents_later_business_query(monkeypatch):
    clock=[0.0]
    fake_time=SimpleNamespace(monotonic=lambda:clock[0])
    monkeypatch.setattr(consistency,"time",fake_time)
    monkeypatch.setattr(adapters,"time",fake_time)
    c=Connection();c.after_metadata=lambda:clock.__setitem__(0,2.0);db,calls=adapter(c)
    limits=ExecutionLimits(query_timeout_seconds=1,request_timeout_seconds=10)
    with pytest.raises(SDKError) as failure:
        with db.read_scope(limits) as scope:
            scope.execute(report(),limits)
    assert failure.value.code == "query_timeout"
    assert c.reads == 0
