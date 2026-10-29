"""Public SDK trajectories over real read-only SQLite and scripted/live transport.

Only synthetic, repository-owned fixtures are accepted. The harness never loads
host .env files or connects to SQL Server. Expectations do not depend on model
approval. Scripted runs test enforcement and execution, not language accuracy.
"""

from dataclasses import replace
from hashlib import sha256
from importlib.metadata import version
import json
from pathlib import Path
import platform
from tempfile import TemporaryDirectory
from time import perf_counter
from types import SimpleNamespace

from examples import multi_domain as hosts
from sageql import LLMConfig
from sageql.sdk import (
    ActorContext, ConceptRef, OpenAIReportAgent, PeriodSelection, ReportIntent,
    ReportSpec, SDKError, SageQL, SQLiteAdapter, SQLiteSessionStore,
)
from sageql.sdk.adapters import compile_report

from evaluations.scoring import assess, summarize


CORPUS = Path(__file__).with_name("cases.json")


def load_cases():
    corpus = json.loads(CORPUS.read_text(encoding="utf-8"))
    if corpus["version"] != 1 or len({x["id"] for x in corpus["cases"]}) != len(corpus["cases"]):
        raise ValueError("Unsupported or duplicate evaluation cases")
    return corpus["cases"]


def specification(base, overrides):
    values = {**base.to_dict(), **overrides}
    for key in ("period", "comparison"):
        if values[key] is not None:
            values[key] = PeriodSelection(**values[key]).__dict__
    return ReportSpec.from_dict(values)


def extracted(spec, **overrides):
    return replace(ReportIntent(
        metrics=tuple(ConceptRef(spec.dataset_id, key) for key in spec.metric_ids),
        dimensions=tuple(ConceptRef(spec.dataset_id, key) for key in spec.dimension_ids),
        chart=spec.chart, time_grain=spec.time_grain, period=spec.period,
        comparison=spec.comparison, comparison_specified=True,
        comparison_calculation=spec.comparison_calculation,
        include_matching_day_count=spec.include_matching_day_count,
        filters=spec.filters, aggregate_filters=spec.aggregate_filters,
        order_by=spec.order_by, ordering_specified=True,
        descending=spec.descending, limit=spec.limit,
    ), **overrides).to_dict()


def ready(spec):
    return {"status": "ready", "spec": spec.to_dict(), "question": "", "message": ""}


def scripted_responses(case, target, scenario):
    approved = {"approved": True, "feedback": ""}
    fault = case.get("fault")
    if fault == "provider":
        return [RuntimeError("synthetic private transport detail")]
    if case.get("follow_up"):
        initial = specification(scenario.initial, case["initial_spec"])
        return [extracted(initial), ready(initial), approved,
                extracted(target, turn_kind="refine"), ready(target), approved]
    if case.get("missing"):
        responses = [extracted(target, missing=tuple(case["missing"]), period=None),
                     {"status": "needs_clarification", "spec": None,
                      "question": "Which year should September cover?", "message": ""}, approved]
        if case.get("answer"):
            responses.extend([extracted(target, turn_kind="answer"), ready(target), approved])
        return responses
    # Simulate mutually agreeing model mistakes: the independent expectation
    # still says no daily grouping, regardless of the supplied stage responses.
    if fault == "correlated_daily":
        wrong = replace(target, time_grain="day")
        return [extracted(wrong), ready(wrong), ready(target), approved]
    responses = [extracted(target, turn_kind="answer") if case.get("answer") else extracted(target)]
    if case.get("ledger"):
        responses[0]["unsupported_requirements"] = case["ledger"]
    if fault == "malformed":
        responses.insert(0, "invalid synthetic JSON")
    if fault == "wrong_period":
        responses.append(ready(replace(target, period=PeriodSelection("month", year=2026, month=8))))
    candidate = ready(target)
    if fault == "sql":
        candidate["sql"] = "SELECT synthetic_untrusted_text"
    responses.extend([candidate, approved])
    if case.get("refine"):
        responses.extend([extracted(scenario.refined, turn_kind="refine"), ready(scenario.refined), approved])
    return responses


class ScriptedClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **options):
        return self

    def create(self, **options):
        self.calls.append(options)
        try:
            value = next(self.responses)
        except StopIteration:
            raise RuntimeError("Evaluation response script exhausted") from None
        if isinstance(value, Exception):
            raise value
        content = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))])


class MeasuredClient:
    """Count actual transport invocations, including failed calls and repairs."""
    def __init__(self, delegate, calls=None):
        self.delegate = delegate
        self.calls = [] if calls is None else calls
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **options):
        return MeasuredClient(self.delegate.with_options(**options), self.calls)

    def create(self, **options):
        self.calls.append(options)
        return self.delegate.chat.completions.create(**options)


class RecordingAdapter:
    def __init__(self, path, fault=None):
        self.delegate = SQLiteAdapter(path)
        self.fault = fault
        self.calls = []
        self.results = []
        self.elapsed_ms = 0.0

    def execute(self, prepared, limits, *, cancel=None):
        started = perf_counter()
        try:
            return self._execute(prepared, limits, cancel=cancel)
        finally:
            self.elapsed_ms += (perf_counter() - started) * 1000

    def _execute(self, prepared, limits, *, cancel=None):
        self.calls.append(prepared)
        # These are the adapter's actual validated inputs; compile both dialects.
        # T-SQL is checked offline, never passed to a SQL Server connection.
        for dialect in ("sqlite", "tsql"):
            compile_report(prepared, limits, dialect=dialect)
        if self.fault == "database":
            raise SDKError("database_unavailable", "Synthetic unavailable database.", retryable=True,
                           stage="database_connection", reason="unavailable")
        result = self.delegate.execute(prepared, limits, cancel=cancel)
        self.results.append(result)
        return result


class RecordingProvider:
    def __init__(self, delegate):
        self.delegate = delegate
        self.decisions = []

    def interpret(self, *args):
        decision = self.delegate.interpret(*args)
        self.decisions.append(decision)
        return decision


def run_case(case, *, live_config=None):
    scenario = next(x for x in hosts.scenarios() if x.name == case["domain"])
    base = scenario.refined if case.get("template") == "refined" else scenario.initial
    target = specification(base, case.get("spec", {}))
    if live_config:
        from openai import OpenAI
        client = MeasuredClient(OpenAI(api_key=live_config.api_key, base_url=live_config.base_url,
                                      timeout=30, max_retries=0))
    else:
        client = ScriptedClient(scripted_responses(case, target, scenario))
    events = []
    def observe(stage, status, **details):
        events.append({"stage": stage, "status": status, **details})
    provider = RecordingProvider(OpenAIReportAgent(
        live_config or LLMConfig("synthetic", "https://example.test/v1", "scripted"),
        client=client, language="en", max_structured_repairs=1 if case.get("fault") == "malformed" else 0,
        observer=observe))
    with TemporaryDirectory(prefix="sageql-evaluation-") as directory:
        path = Path(directory) / "facts.sqlite"
        scenario.create_data(path)
        before = sha256(path.read_bytes()).hexdigest()
        adapter = RecordingAdapter(path, case.get("fault"))
        session_path = Path(directory) / "sessions.sqlite"
        engine = SageQL(catalog=scenario.catalog, database=adapter, provider=provider,
                        policy=scenario.policy, clock=lambda: hosts.TODAY, language="en",
                        execution="validated", sessions=SQLiteSessionStore(session_path))
        session = engine.create_session(hosts.ACTOR)
        actor = ActorContext("not-the-session-owner") if case.get("fault") == "actor" else hosts.ACTOR
        turns = []
        def submit_turn(message, revision, request_id):
            started = perf_counter()
            model_before, database_before = len(client.calls), len(adapter.calls)
            response = engine.submit(session.session_id, message, actor, request_id, revision)
            turns.append({"status": response.status, "model_calls": len(client.calls) - model_before,
                          "database_calls": len(adapter.calls) - database_before,
                          "elapsed_ms": round((perf_counter() - started) * 1000, 3)})
            return response
        start = perf_counter()
        message, revision, request_id = case["request"], 0, "initial"
        first = submit_turn(message, revision, request_id)
        prerequisites = True
        reply = first
        if case.get("answer") and first.status == "needs_clarification":
            message, revision, request_id = case["answer"], first.revision, "answer"
            reply = submit_turn(message, revision, request_id)
        elif case.get("answer"):
            prerequisites = False
        if case.get("follow_up") and first.report is not None:
            prerequisites = assess(case["initial_expect"], first.to_dict()).outcome == "correct_report"
            engine.sessions = SQLiteSessionStore(session_path)
            message, revision, request_id = case["follow_up"], first.revision, "refine"
            reply = submit_turn(message, revision, request_id)
        elif case.get("follow_up"):
            prerequisites = False
        if case.get("refine") and first.report is not None:
            prerequisites = first.report.rows == scenario.expected
            # Reopen the persisted store to exercise the host restart boundary.
            engine.sessions = SQLiteSessionStore(session_path)
            message, revision, request_id = scenario.refinement, first.revision, "refine"
            reply = submit_turn(message, revision, request_id)
            target = scenario.refined
        elif case.get("refine"):
            prerequisites = False
        elapsed_ms = (perf_counter() - start) * 1000
        calls_before = len(adapter.calls)
        model_calls_before = len(client.calls)
        events_before = len(events)
        retry = engine.submit(session.session_id, message, actor, request_id, revision)
        receipt = (retry.to_dict() == reply.to_dict() and calls_before == len(adapter.calls)
                   and model_calls_before == len(client.calls) and events_before == len(events))
        persisted = True
        if reply.report is not None:
            persisted = engine.get_report(session.session_id, reply.report.id, actor).to_dict() == reply.report.to_dict()
        unchanged = before == sha256(path.read_bytes()).hexdigest()
        payloads = json.dumps(client.calls, ensure_ascii=False) if client else ""
        hidden = ("Private product", "Private department", "Restricted title", "Private shelf",
                  '"sale_lines"', '"merchandise"', '"circulation_events"', '"holdings"',
                  '"shop_key"', '"branch_code"', '"north"', '"synthetic private transport detail"')
        isolation = not any(token in payloads for token in hidden) if client else None
        public = reply.to_dict()
        redacted = "synthetic private transport detail" not in json.dumps(public)
        selected = provider.decisions[-1].spec if provider.decisions else None
        spec_matches = selected == target
        expected = case["expect"]
        bounds = expected.get("bounds", ["2026-09-01", "2026-10-01"])
        if reply.report is not None:
            provenance = public["report"]["provenance"]
            spec_matches = spec_matches and [provenance["period_start"], provenance["period_end_exclusive"]] == bounds
        no_reads = expected["kind"] in {"unsupported", "denial", "clarification", "blocked"}
        invariants = all((unchanged, receipt, persisted, redacted, prerequisites,
                          not no_reads or not turns[-1]["database_calls"], isolation is not False))
        if expected["kind"] == "failure":
            invariants = invariants and (public.get("error") or {}).get("code") == expected["error_code"]
            if case.get("fault") == "database":
                invariants = invariants and len(adapter.calls) == 1
        assessment = assess(expected, public, spec_matches=spec_matches, invariants=invariants)
        successful = {"report": "correct_report", "clarification": "correct_clarification",
                      "unsupported": "correct_unsupported", "denial": "correct_denial",
                      "blocked": "correct_block", "failure": "operational_failure"}
        baseline = (successful[expected["kind"]] if live_config else
                    case.get("baseline_outcome", successful[expected["kind"]]))
        # Known failures remain failures in the metrics. A fixed known failure
        # requires removing its baseline waiver, rather than silently passing.
        meets_baseline = assessment.outcome == baseline and invariants
        stages = [event for event in events if event["stage"] in {
            "agent_intent_decoded", "agent_intent", "agent_plan", "agent_review", "intent_evidence"}]
        model_calls = len(client.calls)
        return {
            "id": case["id"], "domain": case["domain"], "tags": case["tags"],
            "goal": expected["kind"], "status": reply.status, "outcome": assessment.outcome,
            "checks": {**assessment.checks, "receipt": receipt, "persisted": persisted,
                       "source_unchanged": unchanged, "payload_isolation": isolation},
            "known_issue": case.get("known_issue"), "baseline_outcome": baseline,
            "meets_baseline": meets_baseline, "recovery_expected": case.get("recovery_expected", False),
            "model_calls": model_calls, "database_calls": len(adapter.calls),
            "recovery_attempts": {
                "planning_revisions": sum(e["stage"] == "agent_plan" and e["status"] == "started"
                                          and e.get("attempt", 1) > 1 for e in events),
                "structured_repairs": sum(e["stage"] == "structured_repair" and e["status"] == "started" for e in events),
                "intent_reconsiderations": sum(e["stage"] == "intent_reconsideration" and e["status"] == "started" for e in events),
            },
            "elapsed_ms": round(elapsed_ms, 3), "turns": turns, "stages": stages,
            "validated_queries": [{"dataset_id": prepared.dataset.id,
                                   "metrics": list(prepared.spec.metric_ids),
                                   "dimensions": list(prepared.spec.dimension_ids),
                                   "time_grain": prepared.spec.time_grain,
                                   "period_start": str(prepared.period.start) if prepared.period.start else None,
                                   "period_end_exclusive": str(prepared.period.end) if prepared.period.end else None}
                                  for prepared in adapter.calls],
        }


def run(cases=None, *, live_config=None):
    selected = load_cases() if cases is None else cases
    results = [run_case(case, live_config=live_config) for case in selected]
    source = Path(__file__).parents[1] / "src" / "sageql"
    digest = sha256()
    for path in sorted(source.rglob("*.py")):
        digest.update(path.relative_to(source).as_posix().encode("utf-8"))
        digest.update(path.read_bytes())
    evaluator_digest = sha256()
    for path in sorted(Path(__file__).parent.glob("*.py")):
        evaluator_digest.update(path.name.encode("utf-8"))
        evaluator_digest.update(path.read_bytes())
    return {"schema_version": 1, "mode": "live_synthetic" if live_config else "scripted_offline",
            "corpus_sha256": sha256(CORPUS.read_bytes()).hexdigest(),
            "package_source_sha256": digest.hexdigest(),
            "evaluator_sha256": evaluator_digest.hexdigest(),
            "host_fixture_sha256": sha256(Path(hosts.__file__).read_bytes()).hexdigest(),
            "environment": {"python": platform.python_version(), "sqlglot": version("sqlglot"),
                            "sageql": version("sageql")},
            "live_model_status": "executed" if live_config else "not_executed",
            "summary": summarize(results), "results": results}
