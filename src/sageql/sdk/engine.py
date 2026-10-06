"""Framework-neutral chat orchestration with explicit trusted infrastructure."""

from __future__ import annotations

from dataclasses import fields, is_dataclass, replace
from datetime import date, datetime, timezone
from decimal import Decimal
import hashlib
import json
from threading import Event, Thread, Timer
import time
from typing import Any, Callable
from uuid import uuid4

from sageql.conversation import Message
from sageql.localization import GRAINS_FA, error_text, validate_language
from sageql.sdk.models import (
    AccessScope, ActorContext, AdapterResult, DatabaseAdapter, ExecutionLimits,
    Interpretation, PeriodSelection, Reply, ReportArtifact, ReportField, ReportingCatalog,
    ReportPolicy, ReportProvider, ReportSpec, SDKError, json_value,
)
from sageql.sdk.semantics import permitted_catalog, validate_catalog, validate_report, validate_scope
from sageql.sdk.sessions import InMemorySessionStore, SessionStore
from sageql.sdk.lookups import prepare_request, resolve_request


def _typed(value: Any) -> Any:
    if isinstance(value, Decimal):
        return {"$decimal": str(value)}
    if isinstance(value, date):
        return {"$date": value.isoformat()}
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _typed(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, dict):
        return {key: _typed(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_typed(item) for item in value]
    return value


def _untyped(value: Any) -> Any:
    if isinstance(value, dict):
        if set(value) == {"$decimal"}:
            return Decimal(value["$decimal"])
        if set(value) == {"$date"}:
            return date.fromisoformat(value["$date"])
        return {key: _untyped(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_untyped(item) for item in value]
    return value


def _digest(value: Any) -> str:
    return hashlib.sha256(json.dumps(_typed(value), sort_keys=True, allow_nan=False,
                                     separators=(",", ":")).encode("utf-8")).hexdigest()


def _artifact(raw: dict[str, Any]) -> ReportArtifact:
    report_fields = tuple(ReportField(**item) for item in raw["fields"])
    rows = []
    for row in raw["rows"]:
        if len(row) != len(report_fields):
            raise SDKError("storage_failed", "Saved report columns are invalid.")
        values = []
        for field, value in zip(report_fields, row):
            if value is not None and field.type == "decimal":
                value = Decimal(value)
                if not value.is_finite():
                    raise SDKError("storage_failed", "Saved report contains an invalid decimal.")
            elif value is not None and field.type == "date":
                value = date.fromisoformat(value)
            values.append(value)
        rows.append(tuple(values))
    return ReportArtifact(
        raw["id"], raw["session_id"], raw["revision"], raw["title"],
        report_fields, tuple(rows), raw["visualization"],
        raw["provenance"], raw["truncated"],
    )


def _reply(raw: dict[str, Any]) -> Reply:
    return Reply(raw["session_id"], raw["revision"], raw["status"], raw["assistant"]["text"],
                 raw["clarification"], _artifact(raw["report"]) if raw["report"] else None,
                 raw["error"])


class SageQL:
    """An application-scoped reporting engine; user input never supplies infrastructure.

    SQL execution is disabled until the developer opts in with execution="validated".
    The policy callback is required and is re-evaluated for every operation. The
    default clock is today's UTC business date; supply a business-date clock for
    another timezone. A provider should independently cap its transport timeout.
    Presentation defaults to Persian; register Persian labels/units and use a
    Persian-speaking provider. Hosts may explicitly choose language="en".
    """

    def __init__(
        self, *, catalog: ReportingCatalog, database: DatabaseAdapter,
        provider: ReportProvider, policy: ReportPolicy,
        sessions: SessionStore | None = None, clock: Callable[[], date] | None = None,
        limits: ExecutionLimits | None = None, execution: str = "disabled",
        language: str = "fa",
    ) -> None:
        self.language = validate_language(language)
        validate_catalog(catalog)
        if execution not in {"disabled", "validated"}:
            raise ValueError("execution must be disabled or validated")
        if not callable(policy) or not callable(getattr(provider, "interpret", None)):
            raise ValueError("policy and report provider are required")
        if not callable(getattr(database, "execute", None)):
            raise ValueError("database adapter is required")
        if clock is not None and not callable(clock):
            raise ValueError("Business-date clock must be callable")
        if limits is not None and not isinstance(limits, ExecutionLimits):
            raise ValueError("Execution limits must be an ExecutionLimits object")
        if clock is None and any(dataset.time is not None and dataset.time.timezone != "UTC"
                                 for dataset in catalog.datasets):
            raise ValueError("A non-UTC time definition requires an explicit business-date clock")
        self.catalog = catalog
        self.database = database
        self.provider = provider
        self._policy = policy
        self.sessions = sessions if sessions is not None else InMemorySessionStore()
        self._clock = clock or (lambda: datetime.now(timezone.utc).date())
        self.limits = limits if limits is not None else ExecutionLimits()
        self.execution = execution

    def _scope(self, actor: ActorContext) -> AccessScope:
        if not isinstance(actor, ActorContext):
            raise SDKError("access_denied", "Authenticated actor context is required.")
        try:
            scope = self._policy(actor)
            validate_scope(self.catalog, scope)
        except SDKError:
            raise
        except Exception:
            raise SDKError("policy_failed", "Report access could not be established.") from None
        if not permitted_catalog(self.catalog, scope).datasets:
            raise SDKError("access_denied", "No reporting datasets are available for this caller.")
        return scope

    def create_session(self, actor: ActorContext) -> Reply:
        self._scope(actor)
        session_id = uuid4().hex
        self.sessions.create({
            "schema_version": 1, "id": session_id, "language": self.language,
            "owner": [actor.subject, actor.tenant_id], "revision": 0,
            "messages": [], "current_spec": None, "pending_question": None, "pending_origin": None,
            "last_report_id": None, "reports": {}, "receipts": {}, "inflight": None,
        })
        return Reply(session_id, 0, "session_ready", "چه گزارشی می‌خواهید تهیه کنید؟"
                     if self.language == "fa" else "What report would you like to create?")

    def get_session(self, session_id: str, actor: ActorContext) -> dict[str, Any]:
        """Return safe resume metadata, never the store's receipts or internal state."""
        self._scope(actor)
        state = self.sessions.get(session_id, (actor.subject, actor.tenant_id))
        return {"session_id": state["id"], "revision": state["revision"],
                "clarification": state["pending_question"],
                "last_report_id": state["last_report_id"]}

    def get_report(self, session_id: str, report_id: str, actor: ActorContext) -> ReportArtifact:
        scope = self._scope(actor)
        state = self.sessions.get(session_id, (actor.subject, actor.tenant_id))
        saved = state["reports"].get(report_id)
        if (saved is None or saved["scope_key"] != _digest(scope)
                or saved["catalog_key"] != _digest(self.catalog)):
            raise SDKError("access_denied", "Report is unavailable under the current access rules.")
        spec = ReportSpec.from_dict(_untyped(saved["spec"]))
        dataset = next((item for item in self.catalog.datasets if item.id == spec.dataset_id), None)
        access = next((item for item in scope.datasets if item.dataset_id == spec.dataset_id), None)
        if dataset is None or access is None:
            raise SDKError("access_denied", "Report is unavailable for this caller.")
        validate_report(dataset, spec, access, today=date.fromisoformat(saved["as_of"]))
        return _artifact(saved["artifact"])

    def _error(self, session_id: str, revision: int, error: SDKError) -> Reply:
        status = "unsupported" if error.code == "unsupported" else (
            "failed" if error.retryable or error.code.endswith("failed") else "blocked"
        )
        return Reply(session_id, revision, status, error_text(error.code, str(error), self.language),
                     error={"code": error.code, "retryable": error.retryable})

    def submit(
        self, session_id: str, message: str, actor: ActorContext,
        request_id: str, expected_revision: int, *, cancel: Event | None = None,
    ) -> Reply:
        """Process one idempotent turn and publish a report only after full success.

        Reusing an ID with different input is rejected. Retries of completed IDs
        return the prior reply only while its catalog and access scope still match.
        Provider and execution failures do not replace the last successful report.
        """
        revision = expected_revision if type(expected_revision) is int and expected_revision >= 0 else 0
        try:
            if (not isinstance(session_id, str) or not 1 <= len(session_id) <= 128
                    or not isinstance(request_id, str) or not 1 <= len(request_id) <= 128
                    or type(expected_revision) is not int or expected_revision < 0
                    or (cancel is not None and not isinstance(cancel, Event))
                    or not isinstance(message, str) or not message.strip()
                    or len(message) > self.limits.max_message_chars):
                raise SDKError("invalid_input", "Provide a bounded message, request ID and session revision.")
            scope = self._scope(actor)
            visible = permitted_catalog(self.catalog, scope)
            scope_key = _digest(scope)
            fingerprint = _digest({"message": message, "revision": expected_revision,
                                   "catalog": _digest(self.catalog)})
            claim = self.sessions.claim(session_id, (actor.subject, actor.tenant_id), request_id,
                                        fingerprint, scope_key, expected_revision,
                                        self.limits.request_timeout_seconds + 5)
        except SDKError as error:
            return self._error(session_id, revision, error)
        except Exception:
            return self._error(session_id, revision, SDKError(
                "storage_failed", "Report session could not be claimed.", retryable=True))
        if claim.cached_reply is not None:
            try:
                return _reply(claim.cached_reply)
            except Exception:
                return self._error(session_id, revision, SDKError(
                    "storage_failed", "Saved reply is unavailable.", retryable=True))

        state = claim.state
        original_state = json.loads(json.dumps(state, allow_nan=False))
        revision = state["revision"]
        deadline = time.monotonic() + self.limits.request_timeout_seconds
        cancelled = Event()
        finished = Event()
        timer = Timer(self.limits.request_timeout_seconds, cancelled.set)
        timer.daemon = True
        timer.start()
        if cancel is not None:
            def forward_cancel() -> None:
                while not finished.wait(0.02):
                    if cancel.is_set():
                        cancelled.set()
                        return
            Thread(target=forward_cancel, daemon=True).start()

        def active() -> None:
            if time.monotonic() >= deadline:
                raise SDKError("request_timeout", "Report request exceeded its time limit.", retryable=True)
            if cancelled.is_set() or (cancel is not None and cancel.is_set()):
                raise SDKError("cancelled", "Report request was cancelled.", retryable=True)

        try:
            active()
            today = self._clock()
            if type(today) is not date:
                raise SDKError("clock_failed", "Business-date clock must return a date.")
            current = (ReportSpec.from_dict(_untyped(state["current_spec"]))
                       if state["current_spec"] is not None else None)
            # A prior spec is itself metadata; don't reveal IDs revoked since the
            # preceding turn. Users can start a fresh permitted report instead.
            if current is not None:
                old_dataset = next((item for item in self.catalog.datasets if item.id == current.dataset_id), None)
                old_access = next((item for item in scope.datasets if item.dataset_id == current.dataset_id), None)
                try:
                    if old_dataset is None or old_access is None:
                        raise SDKError("access_denied", "Previous report access changed.")
                    prepare_request(self.catalog, current, scope, today)
                except SDKError:
                    current = None
            history = tuple(Message(**item) for item in state["messages"])
            # Retain structured current spec for refinements; history remains bounded.
            retain = max(0, self.limits.max_history_messages - 1)
            messages = (*(history[-retain:] if retain else ()), Message("user", message.strip()))
            origin = state.get("pending_origin")
            if origin and not any(item.role == "user" and item.content == origin for item in messages[:-1]):
                messages = (Message("user", origin), *messages[-(self.limits.max_history_messages - 1):])
            try:
                decision = self.provider.interpret(messages, current, visible, today)
            except SDKError:
                raise
            except Exception:
                raise SDKError("provider_failed", "Report interpretation failed; retry with a new request.",
                               retryable=True) from None
            active()
            if _digest(self._scope(actor)) != scope_key:
                raise SDKError("access_denied", "Report access changed during this request.")
            if not isinstance(decision, Interpretation):
                raise SDKError("invalid_interpretation", "Provider returned an invalid interpretation.")
            prepared = None
            if decision.status == "ready":
                if not isinstance(decision.spec, ReportSpec) or decision.question:
                    raise SDKError("invalid_interpretation", "Provider returned an invalid report specification.")
                prepared, lookup = prepare_request(self.catalog, decision.spec, scope, today)
                if self.execution != "validated":
                    raise SDKError("execution_disabled", "The developer has not enabled report execution.")
                if lookup is not None:
                    def check_lookup_access() -> None:
                        active()
                        if _digest(self._scope(actor)) != scope_key:
                            raise SDKError("access_denied", "Report access changed during this request.")
                    prepared, question = resolve_request(
                        prepared, lookup, self.database, self.limits,
                        cancel=cancelled, check_access=check_lookup_access, language=self.language,
                    )
                    if question:
                        decision = Interpretation("needs_clarification", question=question)
            if decision.status == "needs_clarification":
                if (decision.spec is not None or not isinstance(decision.question, str)
                        or not decision.question.strip() or len(decision.question) > 4_000):
                    raise SDKError("invalid_interpretation", "Provider returned an invalid clarification.")
                reply = Reply(session_id, revision + 1, "needs_clarification", decision.question.strip(),
                              clarification=decision.question.strip())
                context = state.get("pending_origin") or message.strip()
                if state.get("pending_origin") and state.get("pending_question"):
                    context += "\nEarlier clarification: " + state["pending_question"] + "\nUser answer: " + message.strip()
                if len(context) > self.limits.max_message_chars:
                    raise SDKError("clarification_limit", "Clarification context reached its limit; start a new session with a complete question.")
                state["pending_question"] = decision.question.strip()
                state["pending_origin"] = context
            elif decision.status == "unsupported":
                if decision.spec is not None or decision.question or not isinstance(decision.message, str):
                    raise SDKError("invalid_interpretation", "Provider returned an invalid unsupported result.")
                reply = Reply(session_id, revision + 1, "unsupported",
                              decision.message[:4_000] or ("اطلاعات ثبت‌شده برای این گزارش کافی نیست."
                              if self.language == "fa" else "The registered data cannot support this report."))
                state["pending_question"] = None
                state["pending_origin"] = None
            elif decision.status == "ready":
                if not isinstance(decision.spec, ReportSpec) or decision.question or prepared is None:
                    raise SDKError("invalid_interpretation", "Provider returned an invalid report specification.")
                spec = decision.spec
                active()
                # Re-evaluate immediately before executing, including changes that
                # occurred during a remote model request.
                if _digest(self._scope(actor)) != scope_key:
                    raise SDKError("access_denied", "Report access changed during this request.")
                result = self.database.execute(prepared, self.limits, cancel=cancelled)
                active()
                if _digest(self._scope(actor)) != scope_key:
                    raise SDKError("access_denied", "Report access changed during this request.")
                artifact = self._make_report(session_id, revision + 1, prepared, result, scope)
                if prepared.spec.filters != spec.filters:
                    # Name/qualifier inputs belong in the public report context.
                    # The resolved identity stays out of provider specifications.
                    artifact = replace(artifact, provenance={**artifact.provenance,
                                                            "filters": json_value(spec.filters)})
                # Verify the public JSON contract before accepting session mutation.
                artifact_json = artifact.to_dict()
                state["reports"][artifact.id] = {
                    "artifact": artifact_json, "spec": _typed(prepared.spec),
                    "scope_key": scope_key, "catalog_key": _digest(self.catalog),
                    "as_of": today.isoformat(),
                }
                while len(state["reports"]) > 20:
                    state["reports"].pop(next(iter(state["reports"])))
                state["last_report_id"] = artifact.id
                # Refinements preserve effective dates across a day/month change.
                # The saved report still records the original period selection.
                frozen_period = (PeriodSelection("range", prepared.period.start.isoformat(),
                                                 prepared.period.end.isoformat())
                                 if prepared.period.start is not None else spec.period)
                frozen_comparison = (PeriodSelection("range", prepared.comparison_period.start.isoformat(),
                                                     prepared.comparison_period.end.isoformat())
                                     if prepared.comparison_period else None)
                state["current_spec"] = _typed(replace(spec, period=frozen_period,
                                                      comparison=frozen_comparison))
                state["pending_question"] = None
                state["pending_origin"] = None
                reply = Reply(session_id, revision + 1, "report_ready", artifact.title, report=artifact)
            else:
                raise SDKError("invalid_interpretation", "Provider returned an unsupported status.")
            state["revision"] = reply.revision
            state["messages"] = [json_value(item) for item in (*history, Message("user", message.strip()),
                                                              Message("assistant", reply.text))]
            state["messages"] = state["messages"][-self.limits.max_history_messages:]
            active()
            if _digest(self._scope(actor)) != scope_key:
                raise SDKError("access_denied", "Report access changed during this request.")
        except SDKError as error:
            # Restore the claimed snapshot so a partially built report is never saved.
            state = original_state
            reply = self._error(session_id, revision, error)
        except Exception:
            state = original_state
            reply = self._error(session_id, revision,
                                SDKError("request_failed", "Report request failed; retry with a new request.",
                                         retryable=True))
        finally:
            timer.cancel()
            finished.set()
        try:
            self.sessions.complete(claim, state, reply.to_dict())
        except SDKError as error:
            return self._error(session_id, revision, error)
        except Exception:
            return self._error(session_id, revision, SDKError(
                "storage_failed", "Session storage is unavailable.", retryable=True))
        return reply

    def _make_report(self, session_id, revision, prepared, result, scope) -> ReportArtifact:
        spec, dataset = prepared.spec, prepared.dataset
        if (not isinstance(result, AdapterResult) or type(result.truncated) is not bool
                or len(result.rows) > min(spec.limit, self.limits.max_rows)):
            raise SDKError("adapter_failed", "Database adapter returned an invalid report result.")
        expected_ids = (("period_label",) if spec.comparison else ()) + (
            ("time_bucket",) if spec.time_grain != "none" else ()) + spec.dimension_ids + spec.metric_ids
        if (tuple(item.id for item in result.fields) != expected_ids
                or any(len(row) != len(result.fields) for row in result.rows)):
            raise SDKError("adapter_failed", "Database adapter returned invalid report columns.")
        metric_defs = {item.id: item for item in dataset.metrics}
        dimension_defs = {item.id: item for item in dataset.dimensions}
        separator = "، " if self.language == "fa" else ", "
        title = separator.join(metric_defs[key].label for key in spec.metric_ids)
        grain = GRAINS_FA.get(spec.time_grain, spec.time_grain) if self.language == "fa" else spec.time_grain
        labels = ([grain] if spec.time_grain != "none" else []) + [
            dimension_defs[key].label for key in spec.dimension_ids]
        if not spec.metric_ids:
            title = dataset.label + ": " + separator.join(labels)
        elif labels:
            title += (" به تفکیک " if self.language == "fa" else " by ") + separator.join(labels)
        report_fields = tuple(
            replace(item, label={"time_bucket": "تاریخ", "period_label": "دوره"}[item.id])
            if self.language == "fa" and item.id in {"time_bucket", "period_label"} else item
            for item in result.fields
        )
        visualization: dict[str, Any] = {"kind": spec.chart}
        if spec.chart in {"bar", "line"}:
            visualization.update(x="time_bucket" if spec.time_grain != "none" else spec.dimension_ids[0],
                                 y=spec.metric_ids[0])
        if spec.chart == "kpi":
            visualization["value"] = spec.metric_ids[0]
        provenance = {
            "dataset_id": dataset.id, "dataset_version": dataset.version,
            "report_kind": "aggregate" if spec.metric_ids else "listing",
            "catalog_version": self.catalog.version, "policy_version": scope.version,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "period_start": json_value(prepared.period.start),
            "period_end_exclusive": json_value(prepared.period.end),
            "comparison_start": json_value(prepared.comparison_period.start) if prepared.comparison_period else None,
            "comparison_end_exclusive": json_value(prepared.comparison_period.end) if prepared.comparison_period else None,
            "time_grain": spec.time_grain,
            "metrics": [{"id": key, "label": metric_defs[key].label,
                         "aggregation": metric_defs[key].aggregation, "unit": metric_defs[key].unit}
                        for key in spec.metric_ids],
            "filters": json_value(spec.filters),
            "completeness": "truncated" if result.truncated else ("empty" if not result.rows else "complete"),
        }
        return ReportArtifact(uuid4().hex, session_id, revision, title, report_fields, result.rows,
                              visualization, provenance, result.truncated)
