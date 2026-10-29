"""Parallel intent samples: agreement vote and tolerance of failed samples; no network."""
from dataclasses import replace
import json
import threading
from types import SimpleNamespace

import pytest

from sageql import LLMConfig, Message
from sageql.sdk import OpenAIReportAgent, PeriodSelection, ReportIntent, ReportSpec, SDKError
from sageql.sdk.semantics import permitted_catalog
from test_sdk_intent import TODAY, catalog, intent, scope

GROUPED = ReportSpec("activities", ("hours",), ("unit",), period=PeriodSelection("last_month"))
OTHER = replace(GROUPED, dimension_ids=("worker",))
REQUEST = (Message("user", "ساعات فعالیت به تفکیک واحد کاری در ماه گذشته"),)


def complete(request=GROUPED):
    return intent(request, filters=(), aggregate_filters=())


class Client:
    """Thread-safe scripted client; which sample receives which reply is arbitrary."""

    def __init__(self, *responses):
        self.responses, self.calls, self.lock = list(responses), [], threading.Lock()
        self.chat = SimpleNamespace(completions=self)

    def with_options(self, **options):
        return self

    def create(self, **options):
        with self.lock:
            self.calls.append(options)
            value = self.responses.pop(0)
        if isinstance(value, Exception):
            raise value
        raw = json.dumps(value.to_dict() if isinstance(value, ReportIntent) else value, ensure_ascii=False)
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=raw))])


def run(*responses, samples=3):
    events = []
    client = Client(*responses)
    agent = OpenAIReportAgent(LLMConfig("k", "https://example.test", "m"), client=client,
                              compile_intent=True, review=False, intent_samples=samples,
                              observer=lambda stage, status, **details: events.append((stage, details)))
    decision = agent.interpret(REQUEST, None, permitted_catalog(catalog(), scope()), TODAY)
    return decision, client, [details for stage, details in events if stage == "intent_samples"]


def test_majority_intent_wins_and_samples_run_once_each():
    decision, client, samples = run(complete(), complete(OTHER), complete())
    assert decision.spec == GROUPED
    assert len(client.calls) == 3
    assert samples == [{"requested": 3, "valid": 3, "agreement": 2}]


def test_failed_sample_is_tolerated_without_retry():
    decision, client, samples = run(RuntimeError("dropped connection"), complete(), complete())
    assert decision.spec == GROUPED and len(client.calls) == 3
    assert samples[0]["valid"] == 2


def test_malformed_sample_is_tolerated():
    decision, client, samples = run("{not json", complete(), complete(OTHER))
    assert decision.status == "ready" and samples[0]["valid"] == 2


def test_all_samples_failing_raises_a_safe_error():
    with pytest.raises(SDKError) as error:
        run(RuntimeError("a"), RuntimeError("b"), RuntimeError("c"))
    assert error.value.code == "provider_failed"


def test_default_uses_a_single_intent_call():
    decision, client, samples = run(complete(), samples=1)
    assert decision.spec == GROUPED and len(client.calls) == 1 and samples == []


@pytest.mark.parametrize("value", [0, 4, True, "2"])
def test_invalid_sample_counts_are_rejected(value):
    with pytest.raises(ValueError):
        OpenAIReportAgent(LLMConfig("k", "https://example.test", "m"), client=Client(), intent_samples=value)
