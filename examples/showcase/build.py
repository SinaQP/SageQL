"""Build the showcase site data by running example conversations through SageQL.

    python examples/showcase/build.py            # replay recording.json offline
    python examples/showcase/build.py --record   # one live run with the .env model

Every stage after the model's reply is the real engine: validation, policy,
SQL compilation and execution on synthetic data. The model's replies come from
recording.json. ``--record`` refreshes them with one live call per model stage;
without it no network is used. Simulated "compromised model" examples always
use their scripted replies and are labelled as such on the site.
"""

import argparse
from dataclasses import replace
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import host  # noqa: E402
from examples_spec import EXAMPLES  # noqa: E402
from sageql import LLMConfig  # noqa: E402
from sageql.sdk import ExecutionLimits, OpenAIReportAgent, SageQL, SQLiteAdapter  # noqa: E402
from sageql.sdk.adapters import compile_report  # noqa: E402

RECORDING = HERE / "recording.json"
OUTPUT = HERE / "site" / "showcase.json"
STAGES = {"sageql_report_intent": "intent", "sageql_report_interpretation": "planner",
          "sageql_report_review": "reviewer"}
LIMITS = ExecutionLimits(max_rows=50, query_timeout_seconds=5, request_timeout_seconds=60)


def _stage(request):
    return STAGES.get(request.get("response_format", {}).get("json_schema", {}).get("name"), "unknown")


def _sent(request):
    """The user-role payload the model received: registered labels only, no rows or SQL."""
    content = next((m["content"] for m in request["messages"] if m["role"] == "user"), "")
    try:
        return json.loads(content)
    except ValueError:
        return content


def _usage(response):
    usage = getattr(response, "usage", None)
    if usage is None:
        return None
    return {"input": getattr(usage, "prompt_tokens", None), "output": getattr(usage, "completion_tokens", None)}


def _response(content, usage=None):
    usage_value = None if usage is None else SimpleNamespace(
        prompt_tokens=usage.get("input"), completion_tokens=usage.get("output"), total_tokens=None)
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=content))], usage=usage_value)


class LiveClient:
    """Pass calls to the real endpoint and keep exactly what came back."""

    def __init__(self, delegate):
        self.delegate, self.calls = delegate, []
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **options):
        clone = LiveClient(self.delegate.with_options(**options))
        clone.calls = self.calls
        return clone

    def create(self, **request):
        response = self.delegate.chat.completions.create(**request)
        self.calls.append({"stage": _stage(request), "model": request.get("model"),
                           "sent": _sent(request), "output": response.choices[0].message.content,
                           "usage": _usage(response)})
        return response


class ReplayClient:
    """Return recorded replies in order; a different stage order means the SDK changed."""

    def __init__(self, recorded):
        self.recorded, self.calls = list(recorded), []
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **options):
        return self

    def create(self, **request):
        if len(self.calls) >= len(self.recorded):
            raise RuntimeError("The recording has fewer model replies than this run needs; re-record.")
        item = self.recorded[len(self.calls)]
        if item["stage"] != _stage(request):
            raise RuntimeError(f"Recorded stage {item['stage']} but the SDK asked for {_stage(request)}; re-record.")
        self.calls.append({**item, "sent": _sent(request)})
        return _response(item["output"], item.get("usage"))


class ScriptedClient:
    """Simulated model replies, one queue per stage; a reviewer approves by default."""

    def __init__(self, replies):
        self.queues = {stage: list(items) for stage, items in replies.items()}
        self.calls = []
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **options):
        return self

    def create(self, **request):
        stage = _stage(request)
        queue = self.queues.get(stage) or ([{"approved": True, "feedback": ""}] if stage == "reviewer" else [])
        if not queue:
            raise RuntimeError(f"No scripted {stage} reply left")
        output = json.dumps(queue.pop(0), ensure_ascii=False)
        self.calls.append({"stage": stage, "model": "scripted", "sent": _sent(request),
                           "output": output, "usage": None})
        return _response(output)


class CapturingAdapter:
    """The real SQLite adapter, plus a copy of every compiled query for display."""

    def __init__(self, path):
        self.delegate, self.queries = SQLiteAdapter(path), []

    def execute(self, report, limits, *, cancel=None):
        sqlite, tsql = (compile_report(report, limits, dialect=d) for d in ("sqlite", "tsql"))
        entry = {"dataset": report.dataset.id, "sqlite": sqlite.sql, "tsql": tsql.sql,
                 "parameters": [_plain(value) for value in sqlite.parameters]}
        self.queries.append(entry)
        result = self.delegate.execute(report, limits, cancel=cancel)
        entry["rows_returned"] = len(result.rows)
        return result


def _plain(value):
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _reply(reply):
    data = reply.to_dict()
    for key in ("session_id", "revision"):
        data.pop(key, None)
    if data.get("report"):
        report = data["report"]
        for key in ("id", "session_id", "revision"):
            report.pop(key, None)
        report.get("provenance", {}).pop("generated_at", None)
        report.get("provenance", {}).pop("saved_report_id", None)
    return data


def run_example(example, client):
    language = example["language"]
    config = LLMConfig("not-used", "https://example.invalid/v1", example.get("planner_model", "gpt-5-nano"))
    agent = OpenAIReportAgent.recommended(config, client, language=language)
    with TemporaryDirectory(prefix="sageql-showcase-") as directory:
        path = Path(directory) / "shop.sqlite"
        host.create_data(path)
        adapter = CapturingAdapter(path)
        engine = SageQL(catalog=host.catalog(language), database=adapter, provider=agent,
                        policy=host.policy, clock=lambda: host.TODAY, execution="validated",
                        language=language, limits=LIMITS)
        session = engine.create_session(host.ACTOR)
        revision, turns, last = session.revision, [], None
        for number, message in enumerate(example["turns"], 1):
            calls_before, queries_before = len(client.calls), len(adapter.queries)
            reply = engine.submit(session.session_id, message, host.ACTOR, f"turn-{number}", revision)
            revision, last = reply.revision, reply
            turns.append({"user": message, "model_calls": client.calls[calls_before:],
                          "queries": adapter.queries[queries_before:], "reply": _reply(reply)})
        if example.get("save") and last is not None and last.report is not None:
            save = example["save"]
            calls_before, queries_before = len(client.calls), len(adapter.queries)
            saved = engine.save_report(session.session_id, last.report.id, host.ACTOR, save["name"],
                                       period=save.get("period"))
            rerun = engine.run_saved_report(saved["id"], host.ACTOR)
            turns.append({"saved_report": {"name": save["name"], "period": _period(save.get("period"))},
                          "model_calls": client.calls[calls_before:],
                          "queries": adapter.queries[queries_before:], "reply": _reply(rerun)})
        return turns


def _period(period):
    return None if period is None else {k: v for k, v in period.__dict__.items() if v is not None}


def build(record=False, output=OUTPUT):
    recording = json.loads(RECORDING.read_text(encoding="utf-8")) if RECORDING.exists() else {"examples": {}}
    live = None
    if record:
        from dotenv import load_dotenv
        from openai import OpenAI
        load_dotenv(HERE.parents[1] / ".env", override=False)
        key = os.environ.get("LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
        if not key:
            raise SystemExit("Set LLM_API_KEY in .env (or the environment) to record.")
        base_url = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1")
        live = OpenAI(api_key=key, base_url=base_url, timeout=60, max_retries=1)
        recording = {"source": "live", "recorded_at": datetime.now(timezone.utc).date().isoformat(),
                     "planner_model": os.environ.get("LLM_MODEL", "gpt-5-nano"), "examples": {}}
    examples, total_calls = [], 0
    for example in EXAMPLES:
        if example.get("simulated"):
            client, source = ScriptedClient(example["scripted"]), "simulated"
        elif live is not None:
            client, source = LiveClient(live), "live"
            example = {**example, "planner_model": recording["planner_model"]}
        elif example["id"] in recording["examples"]:
            client, source = ReplayClient(recording["examples"][example["id"]]), recording.get("source", "live")
        else:
            client, source = ScriptedClient(example["scripted"]), "scripted"
        turns = run_example(example, client)
        for turn in turns:
            for call in turn["model_calls"]:
                # Only what SageQL adds; the user's own words may name anything.
                sent = call["sent"] if isinstance(call["sent"], dict) else {}
                text = json.dumps({k: v for k, v in sent.items() if k != "conversation"}, ensure_ascii=False)
                call["leaked"] = [name for name in host.HIDDEN_FROM_MODEL if name in text]
        if live is not None:
            recording["examples"][example["id"]] = [
                {k: call[k] for k in ("stage", "model", "output", "usage")} for call in client.calls]
            failed = [turn for turn in turns if (turn["reply"].get("error") or {}).get("code") == "provider_failed"]
            if failed:
                raise SystemExit(f"{example['id']}: the model endpoint failed ({failed[0]['reply']['error']}). "
                                 "Nothing was saved; run --record again.")
        total_calls += len(client.calls)
        examples.append({key: example[key] for key in ("id", "category", "language", "title", "summary")
                         } | {"source": source, "turns": turns})
        print(f"{example['id']}: {len(client.calls)} model call(s), {source}", file=sys.stderr)
    if record:
        RECORDING.write_text(json.dumps(recording, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    data = {"sageql_version": _version(), "today": host.TODAY.isoformat(),
            "hidden_from_model": list(host.HIDDEN_FROM_MODEL), "policy_columns": list(host.POLICY_COLUMNS),
            "actor_store": host.ACTOR.attributes["store"],
            "recorded_at": recording.get("recorded_at"), "examples": examples}
    Path(output).write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"Wrote {Path(output).name}: {len(examples)} examples, {total_calls} model calls", file=sys.stderr)
    return data


def _version():
    from importlib.metadata import version
    try:
        return version("sageql")
    except Exception:
        return "unknown"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record", action="store_true",
                        help="Call the model configured in .env once per stage and save the replies.")
    args = parser.parse_args(argv)
    build(record=args.record)


if __name__ == "__main__":
    main()
