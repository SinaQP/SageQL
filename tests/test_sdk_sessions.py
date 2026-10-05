"""Race/restart behavior of durable idempotency and revision guards."""

from concurrent.futures import ThreadPoolExecutor
import time

import pytest

from sageql.sdk import InMemorySessionStore, SDKError, SQLiteSessionStore


def state():
    return {"schema_version": 1, "id": "s1", "owner": ["u1", "t1"], "revision": 0,
            "messages": [], "current_spec": None, "pending_question": None,
            "last_report_id": None, "reports": {}, "receipts": {}, "inflight": None}


@pytest.fixture(params=["memory", "sqlite"])
def store(request, tmp_path):
    value = InMemorySessionStore() if request.param == "memory" else SQLiteSessionStore(tmp_path / "sessions.sqlite")
    value.create(state())
    return value


def test_claim_is_atomic_and_only_one_turn_can_run(store):
    def claim(identifier):
        try:
            return store.claim("s1", ("u1", "t1"), identifier, identifier, "scope", 0, 60)
        except SDKError as error:
            return error.code

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(claim, ["r1", "r2"]))
    assert sum(isinstance(result, str) for result in results) == 1
    assert "session_busy" in results


def test_cached_receipt_survives_restart_and_conflicting_id_is_denied(store):
    claim = store.claim("s1", ("u1", "t1"), "r1", "input", "scope", 0, 60)
    changed = claim.state
    changed["revision"] = 1
    reply = {"session_id": "s1", "revision": 1, "status": "needs_clarification"}
    store.complete(claim, changed, reply)
    cached = store.claim("s1", ("u1", "t1"), "r1", "input", "scope", 0, 60)
    assert cached.cached_reply == reply
    with pytest.raises(SDKError) as error:
        store.claim("s1", ("u1", "t1"), "r1", "changed", "scope", 0, 60)
    assert error.value.code == "request_conflict"
    with pytest.raises(SDKError) as error:
        store.claim("s1", ("u1", "t1"), "r2", "new", "scope", 0, 60)
    assert error.value.code == "revision_conflict"


def test_expired_uncertain_request_is_not_executed_again(store, monkeypatch):
    first = store.claim("s1", ("u1", "t1"), "r1", "input", "scope", 0, 0.01)
    future = time.time() + 100
    monkeypatch.setattr("sageql.sdk.sessions.time.time", lambda: future)
    replay = store.claim("s1", ("u1", "t1"), "r1", "input", "scope", 0, 60)
    assert replay.token is None
    assert replay.cached_reply["error"]["code"] == "interrupted_request"
    with pytest.raises(SDKError) as error:
        store.complete(first, first.state, {"status": "report_ready"})
    assert error.value.code == "request_expired"


def test_unauthorized_lookup_has_same_safe_error_as_missing_session(store):
    for session_id, owner in [("s1", ("other", "t1")), ("missing", ("u1", "t1"))]:
        with pytest.raises(SDKError) as error:
            store.get(session_id, owner)
        assert error.value.code == "access_denied"
        assert str(error.value) == "Session is unavailable for this caller."


def test_memory_store_does_not_expose_mutable_state(store):
    copy = store.get("s1", ("u1", "t1"))
    copy["owner"][0] = "attacker"
    assert store.get("s1", ("u1", "t1"))["owner"] == ["u1", "t1"]


def test_evicted_failed_receipt_cannot_execute_again_at_same_revision(store):
    # A failure can occur after database execution, while the accepted revision
    # stays unchanged. Removing its receipt would allow an accidental replay.
    for index in range(101):
        identifier = f"r{index}"
        claim = store.claim("s1", ("u1", "t1"), identifier, identifier, "scope", 0, 60)
        store.complete(claim, claim.state, {"status": "failed", "revision": 0})
    with pytest.raises(SDKError) as error:
        store.claim("s1", ("u1", "t1"), "r0", "r0", "scope", 0, 60)
    assert error.value.code == "request_retired"
    assert store.claim("s1", ("u1", "t1"), "r100", "r100", "scope", 0, 60).cached_reply


def test_tombstone_capacity_requires_new_session_instead_of_discarding_ids(store):
    existing = store.get("s1", ("u1", "t1"))
    # Seed a full trusted state without spending 1000 SQLite write transactions.
    existing["id"] = "full"
    existing["receipts"] = {f"r{i}": {"fingerprint": "x", "scope_key": "scope",
                                        "reply": None, "retired": True} for i in range(1000)}
    store.create(existing)
    with pytest.raises(SDKError) as error:
        store.claim("full", ("u1", "t1"), "new", "new", "scope", 0, 60)
    assert error.value.code == "request_limit"
