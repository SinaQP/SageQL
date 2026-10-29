"""Owner-scoped saved report definitions; re-running one needs no model call.

A saved report stores the public report specification (registered concepts,
the original period selection and user-visible filter values) plus a name. It
never stores SQL, resolved lookup identities, policy values or result rows, so
every run re-validates against the current catalog and the caller's policies.
"""

from __future__ import annotations

from contextlib import contextmanager
import json
from pathlib import Path
import sqlite3
from threading import RLock
from typing import Any, Iterator, Protocol

from sageql.sdk.models import SDKError

MAX_SAVED_PER_OWNER = 100
MAX_NAME_CHARS = 120


def _copy(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


class SavedReportStore(Protocol):
    def save(self, record: dict[str, Any]) -> None: ...

    def list(self, owner: tuple[str, str]) -> list[dict[str, Any]]: ...

    def get(self, saved_id: str, owner: tuple[str, str]) -> dict[str, Any]: ...

    def delete(self, saved_id: str, owner: tuple[str, str]) -> None: ...


def _owned(record: dict[str, Any] | None, owner: tuple[str, str]) -> dict[str, Any]:
    if record is None or record.get("owner") != list(owner):
        raise SDKError("access_denied", "Saved report is unavailable for this caller.")
    return record


class InMemorySavedReportStore:
    """Thread-safe example store; records are copied through JSON."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, Any]] = {}
        self._lock = RLock()

    def save(self, record: dict[str, Any]) -> None:
        with self._lock:
            owned = [item for item in self._records.values() if item["owner"] == record["owner"]]
            if len(owned) >= MAX_SAVED_PER_OWNER:
                raise SDKError("saved_report_limit", "Saved report limit reached; delete one first.")
            self._records[record["id"]] = _copy(record)

    def list(self, owner: tuple[str, str]) -> list[dict[str, Any]]:
        with self._lock:
            return [_copy(item) for item in self._records.values() if item["owner"] == list(owner)]

    def get(self, saved_id: str, owner: tuple[str, str]) -> dict[str, Any]:
        with self._lock:
            return _copy(_owned(self._records.get(saved_id), owner))

    def delete(self, saved_id: str, owner: tuple[str, str]) -> None:
        with self._lock:
            _owned(self._records.get(saved_id), owner)
            del self._records[saved_id]


class SQLiteSavedReportStore:
    """Saved reports in an explicitly selected local SQLite file (application state)."""

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path).resolve()
        with self._transaction() as connection:
            connection.execute(
                "CREATE TABLE IF NOT EXISTS sageql_saved_reports "
                "(id TEXT PRIMARY KEY, subject TEXT NOT NULL, tenant TEXT NOT NULL, record TEXT NOT NULL)")

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
            raise SDKError("storage_failed", "Saved report storage is unavailable.", retryable=True) from None
        finally:
            if connection is not None:
                connection.close()

    @staticmethod
    def _decode(raw: str) -> dict[str, Any]:
        try:
            record = json.loads(raw)
            if not isinstance(record, dict) or record.get("schema_version") != 1:
                raise ValueError
            return record
        except (ValueError, TypeError):
            raise SDKError("storage_failed", "Saved report has an unsupported format.") from None

    def save(self, record: dict[str, Any]) -> None:
        subject, tenant = record["owner"]
        with self._transaction() as connection:
            (count,) = connection.execute("SELECT COUNT(*) FROM sageql_saved_reports WHERE subject = ? AND tenant = ?",
                                          (subject, tenant)).fetchone()
            if count >= MAX_SAVED_PER_OWNER:
                raise SDKError("saved_report_limit", "Saved report limit reached; delete one first.")
            connection.execute("INSERT INTO sageql_saved_reports(id, subject, tenant, record) VALUES(?, ?, ?, ?)",
                               (record["id"], subject, tenant, json.dumps(record, allow_nan=False)))

    def list(self, owner: tuple[str, str]) -> list[dict[str, Any]]:
        with self._transaction() as connection:
            rows = connection.execute("SELECT record FROM sageql_saved_reports WHERE subject = ? AND tenant = ? "
                                      "ORDER BY rowid", owner).fetchall()
        return [self._decode(row[0]) for row in rows]

    def get(self, saved_id: str, owner: tuple[str, str]) -> dict[str, Any]:
        with self._transaction() as connection:
            row = connection.execute("SELECT record FROM sageql_saved_reports WHERE id = ?", (saved_id,)).fetchone()
        return _owned(self._decode(row[0]) if row else None, owner)

    def delete(self, saved_id: str, owner: tuple[str, str]) -> None:
        with self._transaction() as connection:
            row = connection.execute("SELECT record FROM sageql_saved_reports WHERE id = ?", (saved_id,)).fetchone()
            _owned(self._decode(row[0]) if row else None, owner)
            connection.execute("DELETE FROM sageql_saved_reports WHERE id = ?", (saved_id,))
