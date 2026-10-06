"""JSON session stores with ownership, revisions and durable request receipts.

Rows and conversation text may be private. Persistent stores must live in a
host-controlled directory with appropriate access and retention policies.
"""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
import json
from pathlib import Path
import sqlite3
from threading import RLock
import time
from typing import Any, Iterator, Protocol
from uuid import uuid4

from sageql.sdk.models import SDKError
from sageql.localization import error_text


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


@dataclass(frozen=True)
class SessionClaim:
    session_id: str
    request_id: str
    token: str | None
    state: dict[str, Any]
    cached_reply: dict[str, Any] | None = None


class SessionStore(Protocol):
    def create(self, state: dict[str, Any]) -> None: ...

    def get(self, session_id: str, owner: tuple[str, str]) -> dict[str, Any]: ...

    def claim(
        self, session_id: str, owner: tuple[str, str], request_id: str,
        fingerprint: str, scope_key: str, expected_revision: int, lease_seconds: float,
    ) -> SessionClaim: ...

    def complete(
        self, claim: SessionClaim, state: dict[str, Any], reply: dict[str, Any],
    ) -> None: ...


def _authorize(state: dict[str, Any] | None, owner: tuple[str, str]) -> dict[str, Any]:
    if state is None or state.get("owner") != list(owner):
        raise SDKError("access_denied", "Session is unavailable for this caller.")
    return state


def _claim(
    state: dict[str, Any], request_id: str, fingerprint: str, scope_key: str,
    expected_revision: int, lease_seconds: float,
) -> SessionClaim:
    inflight = state.get("inflight")
    if inflight and inflight["expires_at"] <= time.time():
        # Never repeat an uncertain request after a host crash/deadline. A new
        # request ID is necessary for an intentional retry of this read operation.
        interrupted = state["receipts"][inflight["request_id"]]
        interrupted["reply"] = {
            "contract_version": 1, "session_id": state["id"],
            "revision": state["revision"], "status": "failed",
            "assistant": {"text": error_text("interrupted_request",
                "The previous request was interrupted. Submit a new request to retry.",
                state.get("language", "fa"))},
            "clarification": None, "report": None,
            "error": {"code": "interrupted_request", "retryable": True},
        }
        state["inflight"] = None
    previous = state["receipts"].get(request_id)
    if previous is not None:
        if previous["fingerprint"] != fingerprint:
            raise SDKError("request_conflict", "Request ID was already used with different input.")
        if previous["scope_key"] != scope_key:
            raise SDKError("access_denied", "Request is unavailable under the current access rules.")
        if previous.get("retired"):
            raise SDKError("request_retired", "This request was already processed; its cached reply has expired.")
        if previous["reply"] is None:
            raise SDKError("request_in_progress", "This request is still running.", retryable=True)
        return SessionClaim(state["id"], request_id, None, _copy(state), _copy(previous["reply"]))
    if state["inflight"] is not None:
        raise SDKError("session_busy", "Another request is running in this session.", retryable=True)
    if expected_revision != state["revision"]:
        raise SDKError("revision_conflict", "Session changed; reload its current revision.", retryable=True)
    if len(state["receipts"]) >= 1_000:
        raise SDKError("request_limit", "This session reached its request limit; create a new session.")
    token = uuid4().hex
    state["receipts"][request_id] = {
        "fingerprint": fingerprint, "scope_key": scope_key, "reply": None,
    }
    state["inflight"] = {
        "request_id": request_id, "token": token,
        "expires_at": time.time() + lease_seconds,
    }
    return SessionClaim(state["id"], request_id, token, _copy(state))


def _complete(current: dict[str, Any], claim: SessionClaim, state: dict[str, Any],
              reply: dict[str, Any]) -> dict[str, Any]:
    inflight = current.get("inflight")
    if (not inflight or claim.token is None or inflight["token"] != claim.token
            or inflight["expires_at"] <= time.time()):
        raise SDKError("request_expired", "Request is no longer active; reload the session.", retryable=True)
    if state["owner"] != current["owner"] or state["id"] != current["id"]:
        raise SDKError("invalid_session", "Session identity cannot change.")
    if state["revision"] not in (current["revision"], current["revision"] + 1):
        raise SDKError("invalid_session", "Session revision is invalid.")
    saved = _copy(state)
    saved["receipts"] = current["receipts"]
    saved["receipts"][claim.request_id]["reply"] = _copy(reply)
    # Retain bounded tombstones, including failed turns at unchanged revisions.
    # Retrying an evicted reply must never repeat an uncertain database execution.
    cached = [key for key, receipt in saved["receipts"].items() if not receipt.get("retired")]
    for key in cached[:-100]:
        saved["receipts"][key]["reply"] = None
        saved["receipts"][key]["retired"] = True
    saved["inflight"] = None
    return saved


class InMemorySessionStore:
    """Thread-safe example store; all state is copied through JSON."""

    def __init__(self, *, max_sessions: int = 1_000) -> None:
        if type(max_sessions) is not int or max_sessions < 1:
            raise ValueError("max_sessions must be positive")
        self._max_sessions = max_sessions
        self._states: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def create(self, state: dict[str, Any]) -> None:
        with self._lock:
            if len(self._states) >= self._max_sessions:
                raise SDKError("session_limit", "Session storage capacity was reached.")
            if state["id"] in self._states:
                raise SDKError("session_conflict", "Session already exists.")
            self._states[state["id"]] = _copy(state)

    def get(self, session_id: str, owner: tuple[str, str]) -> dict[str, Any]:
        with self._lock:
            return _copy(_authorize(self._states.get(session_id), owner))

    def claim(self, session_id, owner, request_id, fingerprint, scope_key,
              expected_revision, lease_seconds) -> SessionClaim:
        with self._lock:
            state = _copy(_authorize(self._states.get(session_id), owner))
            claim = _claim(state, request_id, fingerprint, scope_key, expected_revision, lease_seconds)
            self._states[session_id] = state
            return claim

    def complete(self, claim, state, reply) -> None:
        with self._lock:
            current = self._states.get(claim.session_id)
            if current is None:
                raise SDKError("access_denied", "Session is unavailable.")
            self._states[claim.session_id] = _complete(current, claim, state, reply)


class SQLiteSessionStore:
    """Persistent JSON sessions in an explicitly selected local SQLite file.

    Short transactions atomically claim turns; remote calls and report execution
    happen outside transactions. Separate hosts/processes share revision guards.
    This database is application state, not a report data connection.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).resolve()
        try:
            with self._transaction() as connection:
                connection.execute(
                    "CREATE TABLE IF NOT EXISTS sageql_sessions "
                    "(id TEXT PRIMARY KEY, state TEXT NOT NULL)"
                )
        except SDKError:
            raise

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        connection = None
        try:
            connection = sqlite3.connect(self._path, timeout=3.0)
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except sqlite3.Error:
            if connection is not None:
                connection.rollback()
            raise SDKError("storage_failed", "Session storage is unavailable.", retryable=True) from None
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _load(connection, session_id: str) -> dict[str, Any] | None:
        row = connection.execute("SELECT state FROM sageql_sessions WHERE id = ?", (session_id,)).fetchone()
        if row is None:
            return None
        try:
            state = json.loads(row[0])
            if not isinstance(state, dict) or state.get("schema_version") != 1:
                raise ValueError
            return state
        except (ValueError, TypeError):
            raise SDKError("storage_failed", "Saved session has an unsupported format.") from None

    @staticmethod
    def _save(connection, state: dict[str, Any]) -> None:
        connection.execute("UPDATE sageql_sessions SET state = ? WHERE id = ?",
                           (json.dumps(state, allow_nan=False), state["id"]))

    def create(self, state: dict[str, Any]) -> None:
        with self._transaction() as connection:
            connection.execute("INSERT INTO sageql_sessions(id, state) VALUES(?, ?)",
                               (state["id"], json.dumps(state, allow_nan=False)))

    def get(self, session_id: str, owner: tuple[str, str]) -> dict[str, Any]:
        with self._transaction() as connection:
            return _copy(_authorize(self._load(connection, session_id), owner))

    def claim(self, session_id, owner, request_id, fingerprint, scope_key,
              expected_revision, lease_seconds) -> SessionClaim:
        with self._transaction() as connection:
            state = _authorize(self._load(connection, session_id), owner)
            claim = _claim(state, request_id, fingerprint, scope_key, expected_revision, lease_seconds)
            self._save(connection, state)
            return claim

    def complete(self, claim, state, reply) -> None:
        with self._transaction() as connection:
            current = self._load(connection, claim.session_id)
            if current is None:
                raise SDKError("access_denied", "Session is unavailable.")
            self._save(connection, _complete(current, claim, state, reply))
