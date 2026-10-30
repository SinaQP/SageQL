"""Versioned multi-turn evaluation built on the existing runner and scorer.

Scripts exercise enforcement, not language understanding. Answer keys are local
scorer inputs, never additions to the SDK's model payload. Artifacts retain only
allowlisted diagnostics, not prompts, rows, SQL, filters or transport exceptions.
"""
from collections import Counter
from dataclasses import replace
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
from pathlib import Path
import platform
from tempfile import TemporaryDirectory
from time import perf_counter, monotonic
from types import SimpleNamespace

from sageql import LLMConfig
from sageql.sdk import (AccessScope, Interpretation, OpenAIReportAgent, UserFilter,
                        PeriodSelection, ReportSpec, SageQL, SDKError, SQLiteSessionStore)
from evaluations.frozen import file_digest
from evaluations.phase03_hosts import ACTOR, ROOT, TODAY, host
from evaluations.runner import RecordingAdapter, RecordingProvider, ScriptedClient, extracted, ready, specification
from evaluations.scoring import assess


def load_trajectories(cohort):
    manifest = json.loads((ROOT / "freeze.v2.json").read_text(encoding="utf-8"))
    base = ROOT.parents[1]
    for name, digest in manifest["files"].items():
        if file_digest(base / name) != digest:
            raise ValueError("Frozen assessment inputs changed; version and justify corrections")
    corpus = json.loads((ROOT / "cases.v2.json").read_text(encoding="utf-8"))
    cases = corpus["cases"]
    if len({item["id"] for item in cases}) != len(cases):
        raise ValueError("Duplicate trajectory IDs")
    return [item for item in cases if cohort == "phase03" or item["cohort"] == cohort]


def target_spec(case, turn):
    base = ReportSpec({"workshop": "jobs", "retail": "sales", "library": "loans"}[case["domain"]],
                      ("billed",), period=PeriodSelection("month", year=2026, month=7))
    return specification(base, turn["spec"])


def responses(turn, target):
    approved = {"approved": True, "feedback": ""}
    kind, fault = turn["expect"]["kind"], turn.get("fault")
    intent = extracted(target, turn_kind=turn.get("turn_kind", "new"))
    if kind == "clarification":
        missing = turn.get('missing', ['filter_value'])
        intent.update(missing=missing, period=None if "year" in missing or "period" in missing else intent["period"])
        return [intent, {"status": "needs_clarification", "spec": None,
                        "question": turn.get('question','Which registered filter should own this value?'), "message": ""}, approved]
    if turn.get("ledger"):
        intent["unsupported_requirements"] = [turn["ledger"]]
    if fault == "provider":
        return [RuntimeError("private synthetic transport exception")]
    if fault in {"group_omission", "filter_omission", "planner_group_omission"}:
        wrong = replace(target, dimension_ids=(), order_by=None) if "group" in fault else replace(target, filters=())
        if fault != "planner_group_omission":
            intent = extracted(wrong, turn_kind=turn.get("turn_kind", "new"))
        return [intent, ready(wrong), ready(target), approved] if "group" in fault else [intent, ready(wrong), approved]
    if fault in {"review_catches_order", "review_approves_order"}:
        # Controlled extraction leaves ordering unspecified, so the reviewer's
        # judgment is observed rather than preempted by intent agreement.
        intent.update(order_by=None, ordering_specified=False, descending=None)
        wrong = replace(target, descending=False)
        if fault == "review_catches_order":
            return [intent, ready(wrong), {"approved": False, "feedback": "Highest amounts must come first."}, ready(target), approved]
        return [intent, ready(wrong), approved]
    if fault == "review_rejects_correct":
        return [intent, ready(target), {"approved": False, "feedback": "Please reconsider the ordering."}, ready(target), approved]
    return [intent, ready(target), approved]


class CorrelatedFaultClient(ScriptedClient):
    """Approve the wrong plan if admitted; repair only when planning is retried."""
    def __init__(self, turn, target):
        super().__init__([])
        self.turn, self.target, self.plans = turn, target, 0

    def create(self, **options):
        name = options["response_format"]["json_schema"]["name"]
        fault = self.turn.get('fault')
        wrong = (replace(self.target,filters=(UserFilter('channel_filter','eq',('Desk',)),)) if fault == 'value_wrong_scalar' else
                 replace(self.target,filters=(UserFilter('service_filter','eq',('Web',)),)) if fault == 'value_wrong_filter' else
                 replace(self.target, filters=()) if 'filter_omission' in fault else
                 replace(self.target, descending=not self.target.descending) if fault in {
                     'order_omission', 'review_catches_order', 'review_approves_order'} else
                 replace(self.target, dimension_ids=(), order_by=None))
        if name == "sageql_report_intent":
            value = extracted(self.target if fault == 'value_wrong_filter' else wrong,
                              turn_kind=self.turn.get("turn_kind", "new"))
            if fault in {'order_omission', 'review_catches_order', 'review_approves_order'}:
                value.update(order_by=None, ordering_specified=False, descending=None)
        elif name == "sageql_report_interpretation":
            self.plans += 1
            value = ready(wrong if self.plans == 1 or fault.startswith('persistent_') else self.target)
        else:
            reject = fault == 'review_catches_order' and self.plans == 1
            value = {"approved": not reject, "feedback": "Highest amounts must come first." if reject else ""}
        self.responses = iter([value])
        return super().create(**options)


class LiveBudget:
    """Explicit whole-run caps, shared across every turn and configured client.

    Reserve a conservative UTF-8 byte estimate plus output cap before dispatch.
    Use reported token usage afterwards, otherwise retain the reservation. This
    is accounting, not a guarantee about an arbitrary provider's tokenizer/bill.
    """
    def __init__(self, config, approval):
        if not isinstance(approval, dict):
            raise ValueError("Live approval must be a reviewed object")
        expected = {"authorized": True, "synthetic_only": True, "endpoint": config.base_url, "model": config.model}
        if any(approval.get(key) != value for key, value in expected.items()):
            raise ValueError("Reviewed live approval does not match this endpoint/model")
        for key in ("max_requests", "max_tokens", "max_seconds"):
            if type(approval.get(key)) is not int or approval[key] <= 0:
                raise ValueError("Live evaluation requires positive finite budgets")
        pricing = approval.get("pricing", {})
        if (not isinstance(pricing, dict) or pricing.get("reviewed") is not True or not isinstance(pricing.get("source_url"), str)
                or not pricing["source_url"].startswith("https://") or not pricing.get("verified_at")):
            raise ValueError("Live evaluation requires reviewed pricing provenance and a cost ceiling")
        try:
            self.cost_limit = Decimal(str(approval["max_cost_usd"]))
            self.input_price = Decimal(str(pricing["input_usd_per_million"]))
            self.output_price = Decimal(str(pricing["output_usd_per_million"]))
            if (not all(v.is_finite() and v >= 0 for v in (self.cost_limit, self.input_price, self.output_price))
                    or self.cost_limit == 0):
                raise ValueError
        except (KeyError, ValueError, InvalidOperation):
            raise ValueError("Invalid reviewed live cost budget") from None
        self.cost = Decimal(0)
        self.approval = approval
        self.started, self.requests, self.tokens = monotonic(), 0, 0
        self.exhausted = False

    def reserve(self, options):
        output = options.get("max_completion_tokens", 4096)
        inputs = len(json.dumps(options["messages"], ensure_ascii=False).encode("utf-8"))
        estimate = inputs + output
        cost = (inputs * self.input_price + output * self.output_price) / 1000000
        if (self.requests >= self.approval["max_requests"] or self.tokens + estimate > self.approval["max_tokens"]
                or self.cost + cost > self.cost_limit or monotonic() - self.started >= self.approval["max_seconds"]):
            self.exhausted = True
            raise RuntimeError("Live evaluation budget exhausted")
        self.requests += 1
        self.tokens += estimate
        self.cost += cost
        options["timeout"] = min(options.get("timeout", 30), max(.001, self.approval["max_seconds"] - (monotonic() - self.started)))
        return estimate, cost


class StageClient:
    def __init__(self, delegate, *, budget=None, state=None):
        self.delegate, self.budget = delegate, budget
        self.state = state if state is not None else {"calls": [], "records": []}
        self.chat = SimpleNamespace(completions=self)

    @property
    def calls(self):
        return self.state["calls"]

    @property
    def records(self):
        return self.state["records"]

    def with_options(self, **options):
        return StageClient(self.delegate.with_options(**options), budget=self.budget, state=self.state)

    def create(self, **options):
        reservation = self.budget.reserve(options) if self.budget else None
        self.calls.append(options)
        name = options["response_format"]["json_schema"]["name"]
        stage = {"sageql_report_intent": "intent", "sageql_report_interpretation": "planning",
                 "sageql_report_review": "review"}[name]
        record = {"stage": stage, "elapsed_ms": None, "usage": None, "failed": False}
        # Parsed structures stay only in memory for independent checks below.
        if stage == "review":
            record["candidate"] = json.loads(options["messages"][-1]["content"])["candidate"]
        started = perf_counter()
        try:
            response = self.delegate.chat.completions.create(**options)
            usage = getattr(response, "usage", None)
            if usage is not None:
                prompt, completion = getattr(usage, "prompt_tokens", None), getattr(usage, "completion_tokens", None)
                if type(prompt) is int and type(completion) is int and min(prompt, completion) >= 0:
                    record["usage"] = {"input": prompt, "output": completion}
                    if self.budget:
                        self.budget.tokens += prompt + completion - reservation[0]
                        self.budget.cost += (prompt * self.budget.input_price + completion * self.budget.output_price) / 1000000 - reservation[1]
                        if self.budget.tokens >= self.budget.approval["max_tokens"] or self.budget.cost >= self.budget.cost_limit:
                            self.budget.exhausted = True
            try:
                record["decoded"] = json.loads(response.choices[0].message.content)
            except (ValueError, TypeError):
                record["decoded"] = None
            return response
        except Exception:
            record["failed"] = True
            raise
        finally:
            record["elapsed_ms"] = round((perf_counter() - started) * 1000, 3)
            self.records.append(record)
            if self.budget and (self.budget.requests >= self.budget.approval["max_requests"]
                                or monotonic() - self.budget.started >= self.budget.approval["max_seconds"]):
                self.budget.exhausted = True


def _diagnosis(turn, public, assessment, events):
    if assessment.outcome == "correct_report":
        return "correct_report"
    status, goal = public["status"], turn["expect"]["kind"]
    if assessment.outcome == "correct_clarification":
        return "required_clarification"
    if status == "needs_clarification":
        return "unnecessary_clarification"
    if status == "unsupported":
        return "unsupported_capability" if goal == "unsupported" else "incorrect_unsupported"
    error = public.get("error") or {}
    if error.get("code") == "access_denied":
        return "authorization_denial"
    if status == "failed":
        code = error.get('code')
        if code == 'agent_exhausted':
            return 'agent_recovery_exhaustion'
        if code == 'provider_failed':
            return 'provider_transport_failure'
        if code in {'database_unavailable', 'adapter_failed'}:
            return 'database_execution_failure'
        return 'request_deadline' if code == 'request_timeout' else 'operational_failure'
    if status == "report_ready":
        if assessment.outcome == "incomplete":
            return "incomplete_result"
        return "incorrect_report_data" if assessment.checks.get("specification") else "incorrect_accepted_specification"
    if any(e["stage"] in {"intent_check", "request_check"} and e["status"] == "failed" for e in events) or error.get("code") == "intent_mismatch":
        return "deterministic_semantic_mismatch"
    return "extraction_failure" if error.get("stage") == "intent" else "planning_failure"


def _intent_diagnostics(decoded, target, turn):
    expected = target.to_dict()
    checks = {}
    for key, field in (('metrics', 'metric_ids'), ('dimensions', 'dimension_ids')):
        refs = decoded.get(key)
        checks[key] = (isinstance(refs, list) and all(isinstance(r, dict) and 'concept_id' in r and r.get('dataset_id') == target.dataset_id for r in refs)
                       and [r['concept_id'] for r in refs] == expected[field])
    checks.update({key: decoded.get(key) == expected[key] for key in (
        'filters', 'period', 'comparison', 'chart', 'time_grain', 'order_by', 'descending', 'limit', 'aggregate_filters')})
    def period_key(value):
        if not isinstance(value, dict):
            return value
        if value.get('kind') == 'range':
            return value.get('start'), value.get('end')
        if value.get('kind') == 'month' and type(value.get('year')) is int and type(value.get('month')) is int:
            year, month = value['year'], value['month']
            if 1 <= month <= 12:
                return f'{year:04}-{month:02}-01', f'{year + (month == 12):04}-{month % 12 + 1:02}-01'
        return value
    missing = turn.get('missing', ['filter_value']) if turn['expect']['kind'] == 'clarification' else []
    checks['period'] = (decoded.get('period') is None if {'period', 'year'} & set(missing)
                        else period_key(decoded.get('period')) == period_key(expected['period']))
    checks['comparison'] = period_key(decoded.get('comparison')) == period_key(expected['comparison'])
    checks['missing'] = decoded.get('missing') == missing
    return checks


def run_trajectory(case, *, live_config=None, budget=None, live_client=None,
                   client_factory=None, stage_client_type=StageClient,
                   turn_checkpoint=None, agent_options=None, outcome_scorer=assess):
    catalog, policy, create_data = host(case["domain"])
    if case.get("host_version"):
        from evaluations.phase05_hosts import host as vocabulary_host
        catalog, policy, create_data = vocabulary_host(case["domain"], case["host_version"])
    policy_state = {"revoked": False, "deny_metric": False}
    def current_policy(actor):
        if policy_state["revoked"]:
            return AccessScope((), version="revoked")
        value = policy(actor)
        if policy_state.get("restrict_value_filter"):
            value = replace(value, datasets=tuple(replace(access,
                filter_ids=tuple(f.id for d in catalog.datasets if d.id == access.dataset_id for f in d.filters
                                 if f.id != 'channel_filter')) for access in value.datasets))
        if policy_state["deny_metric"]:
            return AccessScope((replace(value.datasets[0], metric_ids=("jobs_count",)),), version="restricted")
        return value
    turns, last_report, reports = [], None, {}
    with TemporaryDirectory(prefix="sageql-trajectory-") as directory:
        path = Path(directory) / "facts.sqlite"
        create_data(path)
        before = sha256(path.read_bytes()).hexdigest()
        adapter = RecordingAdapter(path)
        session_path = Path(directory) / "sessions.sqlite"
        engine = SageQL(catalog=catalog, database=adapter, policy=current_policy,
                        provider=SimpleNamespace(interpret=lambda *args: None), clock=lambda: TODAY,
                        execution="validated", language="en", sessions=SQLiteSessionStore(session_path))
        session = engine.create_session(ACTOR)
        revision = session.revision
        for index, turn in enumerate(case["turns"]):
            if budget and budget.exhausted:
                break
            if budget and callable(getattr(budget, 'remaining_seconds', None)):
                # Phase 06 shares the run's remaining wall time with the SDK's
                # complete interpretation/execution deadline, not only HTTP.
                engine.limits = replace(engine.limits, request_timeout_seconds=max(.001, min(
                    budget.approval.get('turn_timeout_seconds', 60), budget.remaining_seconds())))
            target = target_spec(case, turn)
            control = turn.get("control")
            policy_state["revoked"] = control == "revoke"
            policy_state["deny_metric"] = control == "deny_metric"
            policy_state["restrict_value_filter"] = control == "restrict_value_filter"
            if turn.get("reopen"):
                engine.sessions = SQLiteSessionStore(session_path)
            events = []
            scripted = (None if live_config else client_factory(turn, target, catalog) if client_factory else
                        CorrelatedFaultClient(turn, target) if turn.get("fault") in {
                            "group_omission", "filter_omission", 'persistent_filter_omission',
                            'order_omission', 'review_catches_order', 'review_approves_order',
                            'value_wrong_scalar', 'value_wrong_filter'}
                        else ScriptedClient(responses(turn, target)))
            client = stage_client_type(live_client if live_config else scripted, budget=budget)
            provider = RecordingProvider(OpenAIReportAgent(
                live_config or LLMConfig("synthetic", "https://example.test/v1", "scripted"),
                client=client, language="en", max_revisions=1,
                observer=lambda stage, status, **details: events.append({"stage": stage, "status": status, **details}),
                **(agent_options or {})))
            if not live_config and (control in {"deny_metric", "revoke"} or turn.get("fault", '').startswith('custom_')):
                fault = turn.get('fault')
                wrong = (replace(target, dimension_ids=()) if fault == 'custom_group_omission' else
                         replace(target, filters=()) if fault == 'custom_filter_omission' else
                         replace(target, filters=(UserFilter('channel_filter','eq',('Desk',)),)) if fault == 'custom_wrong_value' else
                         replace(target, descending=not target.descending) if fault == 'custom_order_omission' else target)
                provider = RecordingProvider(SimpleNamespace(interpret=lambda *args: Interpretation("ready", wrong)))
            engine.provider = provider
            adapter.fault = turn.get("fault")
            resolution_ms = None
            if case.get("host_version"):
                from sageql.sdk.grounding import filter_controls
                from sageql.sdk.semantics import permitted_catalog
                permitted = permitted_catalog(catalog, current_policy(ACTOR))
                resolution_start = perf_counter()
                filter_controls(turn["request"], permitted)
                resolution_ms = round((perf_counter() - resolution_start) * 1000, 6)
            db_before = len(adapter.calls)
            database_started = adapter.elapsed_ms
            started = perf_counter()
            reply = engine.submit(session.session_id, turn["request"], ACTOR, "turn-" + str(index), revision)
            elapsed = round((perf_counter() - started) * 1000, 3)
            public = reply.to_dict()
            db_calls = len(adapter.calls) - db_before
            calls_before = (len(client.calls), len(adapter.calls), len(events))
            cached = engine.submit(session.session_id, turn["request"], ACTOR, "turn-" + str(index), revision)
            receipt = cached.to_dict() == public and calls_before == (len(client.calls), len(adapter.calls), len(events))
            selected = provider.decisions[-1].spec if provider.decisions else None
            spec_matches = selected == target
            requirement_checks = {item["field"]: reply.report is not None and selected is not None and selected.to_dict()[item["field"]] == target.to_dict()[item["field"]]
                                  for item in turn["requirements"] if "field" in item}
            persisted, previous_preserved = True, True
            if reply.report:
                reports[reply.report.id] = reply.report.to_dict()
                last_report = reply.report.id
                provenance = public["report"]["provenance"]
                spec_matches = spec_matches and [provenance["period_start"], provenance["period_end_exclusive"]] == turn["expect"].get("bounds")
            for identifier, saved in reports.items():
                try:
                    loaded = engine.get_report(session.session_id, identifier, ACTOR).to_dict()
                    persisted = persisted and loaded == saved and not policy_state["revoked"]
                except SDKError as error:
                    persisted = persisted and policy_state["revoked"] and error.code == "access_denied"
            if not policy_state["revoked"]:
                previous_preserved = engine.get_session(session.session_id, ACTOR)["last_report_id"] == last_report
            payload = json.dumps(client.calls, ensure_ascii=False)
            isolation = not any(value in payload for value in ('"workshop_jobs"', '"blue"', '"PRIVATE_TECH"', '"private synthetic transport exception"'))
            no_reads = turn["expect"]["kind"] in {"clarification", "unsupported", "denial", "blocked"}
            invariant = all((receipt, persisted, previous_preserved, isolation,
                             not no_reads or not db_calls, before == sha256(path.read_bytes()).hexdigest()))
            if turn["expect"]["kind"] == "failure":
                invariant = invariant and (public.get("error") or {}).get("code") == turn["expect"]["error_code"]
                if turn.get("fault") == "database":
                    invariant = invariant and db_calls == 1
            assessment = outcome_scorer(turn["expect"], public, spec_matches=spec_matches and all(requirement_checks.values()), invariants=invariant)
            reviews = []
            stage_requirements = []
            effective_recorded = False
            for record_index, record in enumerate(client.records):
                decoded = record.get("decoded")
                candidate = record.get("candidate")
                if case.get("host_version"):
                    try:
                        from sageql.sdk.vocabulary import restore_response
                    except ImportError:
                        restore_response = None
                    if restore_response is not None:
                        content = client.calls[record_index]["messages"][-1]["content"]
                        try:
                            decoded = restore_response(decoded, catalog, content) if decoded is not None else None
                            candidate = restore_response(candidate, catalog, content) if candidate is not None else None
                        except (ValueError, TypeError, KeyError, RecursionError):
                            # A rejected protocol response is evidence, not a
                            # reason to discard the SDK's safe failure outcome.
                            decoded, candidate = None, None
                if record["stage"] == "intent" and isinstance(decoded, dict) and "metrics" in decoded:
                    stage_requirements.append({"stage": "decoded_intent", "checks": {
                        "metrics": isinstance(decoded.get('metrics'), list) and all(isinstance(r, dict) for r in decoded['metrics']) and [r.get("concept_id") for r in decoded["metrics"]] == list(target.metric_ids),
                        "dimensions": isinstance(decoded.get('dimensions'), list) and all(isinstance(r, dict) for r in decoded['dimensions']) and [r.get("concept_id") for r in decoded["dimensions"]] == list(target.dimension_ids),
                        "filters": decoded.get("filters") is None or decoded["filters"] == target.to_dict()["filters"]}})
                    if client_factory is not None or stage_client_type is not StageClient:
                        stage_requirements[-1]['checks'] = _intent_diagnostics(decoded, target, turn)
                if client_factory is not None or stage_client_type is not StageClient:
                    if decoded is None and not record['failed'] and record['stage'] in ('intent', 'planning'):
                        stage_requirements.append({'stage': 'decoded_intent' if record['stage'] == 'intent' else 'proposal',
                                                   'checks': {'response_valid': False}})
                    if record['stage'] == 'planning' and not effective_recorded:
                        content = client.calls[record_index]['messages'][-1]['content']
                        effective = json.loads(content).get('intent')
                        if isinstance(effective, dict):
                            from sageql.sdk.vocabulary import restore_response
                            effective = restore_response(effective, catalog, content)
                            stage_requirements.append({'stage': 'effective_intent', 'checks': _intent_diagnostics(effective, target, turn)})
                            effective_recorded = True
                if record["stage"] == "planning" and isinstance(decoded, dict) and decoded.get("spec"):
                    stage_requirements.append({"stage": "proposal", "checks": {
                        key: value == target.to_dict().get(key) for key, value in decoded["spec"].items()}})
                if record["stage"] != "review" or not isinstance(record.get("decoded"), dict):
                    continue
                correct = (candidate.get("spec") == target.to_dict() if candidate["status"] == "ready"
                           and turn["expect"]["kind"] in {"report", "failure"}
                           else candidate["status"] == "needs_clarification" and turn["expect"]["kind"] == "clarification")
                reviews.append({"candidate_correct": correct, "approved": record["decoded"].get("approved")})
            for event in events:
                if event["stage"] == "agent_intent" and event["status"] == "complete" and not effective_recorded:
                    stage_requirements.append({"stage": "effective_intent", "checks": {
                        "metrics": event.get("metrics") == list(target.metric_ids),
                        "dimensions": event.get("dimensions") == list(target.dimension_ids)}})
            origin = next((item["stage"] for item in stage_requirements if not all(item["checks"].values())), None)
            failure_origin = None
            if reply.report is not None and not spec_matches:
                failure_origin = ("context_extraction_failure" if index else "extraction_failure") if origin == "decoded_intent" else (
                    "review_failure" if any(not r["candidate_correct"] and r["approved"] for r in reviews) else "planning_failure")
            successful = {"report": "correct_report", "clarification": "correct_clarification", "unsupported": "correct_unsupported",
                          "denial": "correct_denial", "blocked": "correct_block", "failure": "operational_failure"}
            turns.append({"index": index + 1, "goal": turn["expect"]["kind"], "status": reply.status,
                "outcome": assessment.outcome, "diagnosis": _diagnosis(turn, public, assessment, events),
                "first_disagreement_stage": origin, "stage_requirements": stage_requirements,
                "failure_origin": failure_origin,
                "correct": assessment.outcome == successful[turn["expect"]["kind"]] and invariant,
                "requirements": requirement_checks, "checks": {**assessment.checks, "receipt": receipt,
                    "persisted": persisted, "previous_preserved": previous_preserved, "payload_isolation": isolation},
                "accepted_specification_incorrect": reply.report is not None and not spec_matches,
                "database_calls": db_calls, "elapsed_ms": elapsed,
                **({"vocabulary_resolution_ms": resolution_ms} if resolution_ms is not None else {}),
                "model_calls": [dict((key, record[key]) for key in ("stage", "elapsed_ms", "usage", "failed")) for record in client.records],
                "reviews": reviews, "revisions": sum(e["stage"] == "agent_plan" and e["status"] == "started" and e.get("attempt", 1) > 1 for e in events),
                "deterministic_rejections": sum(e["stage"] in {"intent_check", "request_check"} and e["status"] == "failed" for e in events),
                "evidence_corrections": sum(e["stage"] == "intent_evidence" and e["status"] == "corrected" for e in events),
                "structured_repairs": sum(e["stage"] == "structured_repair" and e["status"] == "started" for e in events),
                "intent_reconsiderations": sum(e["stage"] == "intent_reconsideration" and e["status"] == "started" for e in events)})
            if client_factory is not None or stage_client_type is not StageClient:
                for call, record in zip(turns[-1]['model_calls'], client.records):
                    call['recovery'] = record.get('recovery', False)
                turns[-1]["protocol"] = [record.get('protocol', {}) for record in client.records]
                turns[-1]["safe_errors"] = [{key: public['error'][key] for key in ('code', 'stage', 'reason', 'field')
                                             if key in public['error']}] if public.get('error') else []
                turns[-1]["database_latency_ms"] = round(adapter.elapsed_ms - database_started, 3)
                turns[-1]['stage_detection'] = {
                    'decoded_intent_wrong': sum(item['stage'] == 'decoded_intent' and not all(item['checks'].values()) for item in stage_requirements),
                    'proposals_wrong': sum(item['stage'] == 'proposal' and not all(item['checks'].values()) for item in stage_requirements),
                    'wrong_review_approved': sum(not r['candidate_correct'] and bool(r['approved']) for r in reviews),
                    'wrong_review_rejected': sum(not r['candidate_correct'] and not r['approved'] for r in reviews),
                    'local_checks_failed': turns[-1]['deterministic_rejections'],
                    'final_report_wrong': turns[-1]['accepted_specification_incorrect']}
            if turn_checkpoint:
                turn_checkpoint(turns[-1])
            revision = reply.revision
        return {"id": case["id"], "cohort": case["cohort"], "domain": case["domain"], "tags": case["tags"],
                **({"host_version": case["host_version"]} if case.get("host_version") else {}),
                "correct": len(turns) == len(case["turns"]) and all(t["correct"] for t in turns),
                "first_failing_turn": next((t["index"] for t in turns if not t["correct"]), None),
                "unexecuted_turns": len(case["turns"]) - len(turns), "turns": turns}


def fraction(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator, "value": numerator / denominator if denominator else None}


def summarize_trajectories(results):
    turns = [turn for case in results for turn in case["turns"]]
    reports = [t for t in turns if t["goal"] == "report"]
    returned = [t for t in turns if t["status"] == "report_ready"]
    calls = [call for t in turns for call in t["model_calls"]]
    reviews = [review for t in turns for review in t["reviews"]]
    requirements = [value for t in reports for value in t["requirements"].values()]
    usage = [call["usage"] for call in calls if call["usage"] is not None]
    return {"trajectories": len(results), "turns": len(turns),
        "trajectory_correctness": fraction(sum(c["correct"] for c in results), len(results)),
        "supported_completion": fraction(sum(t["outcome"] == "correct_report" for t in reports), len(reports)),
        "semantic_correctness": fraction(sum(t["outcome"] == "correct_report" for t in returned), len(returned)),
        "requirement_completeness": fraction(sum(requirements), len(requirements)),
        "complete_supported_turns": fraction(sum(t["outcome"] == "correct_report" and all(t["requirements"].values()) for t in reports), len(reports)),
        "clarification_precision": fraction(sum(t["outcome"] == "correct_clarification" for t in turns), sum(t["status"] == "needs_clarification" for t in turns)),
        "unnecessary_clarifications": sum(t["status"] == "needs_clarification" and t["goal"] != "clarification" for t in turns),
        "correct_unsupported": fraction(sum(t["outcome"] == "correct_unsupported" for t in turns), sum(t["goal"] == "unsupported" for t in turns)),
        "incorrect_unsupported": sum(t["status"] == "unsupported" and t["goal"] != "unsupported" for t in turns),
        "unauthorized_prevention": fraction(sum(t["outcome"] == "correct_denial" and t["database_calls"] == 0 for t in turns), sum(t["goal"] == "denial" for t in turns)),
        "incorrect_accepted_specifications": sum(t["accepted_specification_incorrect"] for t in turns),
        "outcomes": dict(Counter(t["outcome"] for t in turns)), "diagnoses": dict(Counter(t["diagnosis"] for t in turns)),
        "failure_origins": dict(Counter(t["failure_origin"] for t in turns if t["failure_origin"])),
        "model_calls_by_stage": dict(Counter(c["stage"] for c in calls)),
        "stage_latency_ms": {stage: round(sum(c["elapsed_ms"] for c in calls if c["stage"] == stage), 3) for stage in ("intent", "planning", "review")},
        "scenario_latency_ms": round(sum(t["elapsed_ms"] for t in turns), 3),
        **{key: sum(t[key] for t in turns) for key in ("database_calls", "revisions", "structured_repairs", "intent_reconsiderations", "deterministic_rejections", "evidence_corrections")},
        "reviewer": {"incorrect_rejected": sum(not r["candidate_correct"] and not r["approved"] for r in reviews),
                     "incorrect_approved": sum(not r["candidate_correct"] and bool(r["approved"]) for r in reviews),
                     "correct_rejected": sum(r["candidate_correct"] and not r["approved"] for r in reviews),
                     "correct_approved": sum(r["candidate_correct"] and bool(r["approved"]) for r in reviews),
                     "useful_revisions": sum(any(not r["candidate_correct"] and not r["approved"] for r in t["reviews"]) and t["outcome"] == "correct_report" for t in turns),
                     "unproductive_revisions": sum(any(r["candidate_correct"] and not r["approved"] for r in t["reviews"]) for t in turns)},
        "usage_coverage": fraction(len(usage), len(calls)),
        "tokens": {key: sum(u[key] for u in usage) for key in ("input", "output")} if usage else None,
        "estimated_cost": None, "cost_status": "No independently verified pricing metadata supplied",
        "failing_trajectories": [c["id"] for c in results if not c["correct"]]}


def run_trajectories(cases, *, live_config=None, approval=None, checkpoint=None):
    budget = LiveBudget(live_config, approval or {}) if live_config else None
    client = None
    if live_config:
        from openai import OpenAI
        client = OpenAI(api_key=live_config.api_key, base_url=live_config.base_url, timeout=30, max_retries=0)
    results = []
    def artifact():
        import sageql
        source = Path(sageql.__file__).parent
        corpus_root = (Path(__file__).with_name('phase05') if cases and cases[0]['cohort'].startswith('phase05') else
                       Path(__file__).with_name('phase04') if cases and cases[0]['cohort'].startswith('phase04') else ROOT)
        version = 'v1' if corpus_root.name == 'phase04' else 'v2'
        digest = sha256()
        for file in sorted(source.rglob("*.py")):
            digest.update(file.relative_to(source).as_posix().encode()); digest.update(file.read_bytes())
        summary = summarize_trajectories(results)
        if corpus_root.name == 'phase05':
            measured = [turn['vocabulary_resolution_ms'] for result in results for turn in result['turns']]
            summary['vocabulary_resolution_ms'] = {'total': round(sum(measured),6), 'calls': len(measured),
                                                  'mean': sum(measured)/len(measured) if measured else None}
        if budget:
            summary["estimated_cost"] = str(budget.cost)
            summary["cost_status"] = "USD reservation estimate, adjusted by usage when supplied; operator-reviewed pricing, not a provider invoice"
        return {"schema_version": 2, "mode": "live_synthetic" if live_config else "scripted_offline",
                "live_model_status": "executed" if live_config else "not_executed", "python": platform.python_version(),
                "corpus_sha256": sha256((corpus_root / ('cases.'+version+'.json')).read_bytes()).hexdigest(),
                "freeze_sha256": sha256((corpus_root / ('freeze.'+version+'.json')).read_bytes()).hexdigest(),
                "source_sha256": digest.hexdigest(),
                "evaluator_sha256": sha256(b"".join(p.name.encode() + p.read_bytes() for p in sorted(Path(__file__).parent.glob("*.py")))).hexdigest(),
                "model": live_config.model if live_config else "scripted",
                "endpoint_sha256": sha256(live_config.base_url.encode()).hexdigest() if live_config else None,
                "budget_exhausted": budget.exhausted if budget else False,
                "budget_accounting": {"requests_dispatched": budget.requests, "tokens_charged_or_reserved": budget.tokens,
                                      "estimated_usd_charged_or_reserved": str(budget.cost),
                                      "pricing_source": budget.approval["pricing"]["source_url"],
                                      "pricing_verified_at": budget.approval["pricing"]["verified_at"]} if budget else None,
                "unexecuted_trajectories": len(cases) - len(results), "summary": summary, "results": results}
    try:
        for case in cases:
            if budget and budget.exhausted:
                break
            if live_config and (case["cohort"] != "holdout" or any(t.get("control") or t.get("fault") for t in case["turns"])):
                raise ValueError("Live evaluation permits only natural synthetic holdouts, without scripted faults/controls")
            results.append(run_trajectory(case, live_config=live_config, budget=budget, live_client=client))
            if checkpoint:
                checkpoint(artifact())
        return artifact()
    finally:
        if client is not None:
            client.close()
