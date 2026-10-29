"""Per-stage model selection, reasoning effort and usage accounting; no network."""

from types import SimpleNamespace

import pytest

from sageql import LLMConfig, Message
from sageql.sdk import OpenAIReportAgent, OpenAIReportInterpreter
from sageql.sdk.semantics import permitted_catalog
from test_sdk_intent import APPROVED, TODAY, Client, catalog, intent, planned, scope, spec


CONFIG = LLMConfig("fake-key", "https://example.test", "cheap-model")
MESSAGES = (Message("user", "ساعات کارکنان ماه گذشته"),)


class UsageClient(Client):
    """Adds provider usage counts to otherwise identical fake responses."""

    def create(self, **kwargs):
        response = super().create(**kwargs)
        response.usage = SimpleNamespace(
            prompt_tokens=1000, completion_tokens=300, total_tokens=1300,
            prompt_tokens_details=SimpleNamespace(cached_tokens=256),
            completion_tokens_details=SimpleNamespace(reasoning_tokens=200))
        return response


def run(client_type=Client, **options):
    client = client_type(intent(), planned(), APPROVED)
    agent = OpenAIReportAgent(CONFIG, client=client, **options)
    decision = agent.interpret(MESSAGES, spec(), permitted_catalog(catalog(), scope()), TODAY)
    assert decision.status == "ready"
    return client.calls


def sent(calls, key):
    return [call.get(key) for call in calls]


def test_defaults_keep_configured_model_and_send_no_reasoning_effort():
    calls = run()
    assert sent(calls, "model") == ["cheap-model"] * 3
    assert all("reasoning_effort" not in call for call in calls)


def test_stage_models_replace_only_the_selected_stage():
    calls = run(stage_models={"intent": "stronger-model"})
    assert sent(calls, "model") == ["stronger-model", "cheap-model", "cheap-model"]

    calls = run(stage_models={"planner": "p", "reviewer": "r"})
    assert sent(calls, "model") == ["cheap-model", "p", "r"]


def test_reasoning_effort_applies_globally_or_per_stage():
    assert sent(run(reasoning_effort="low"), "reasoning_effort") == ["low"] * 3
    calls = run(reasoning_effort={"intent": "medium", "reviewer": "minimal"})
    assert sent(calls, "reasoning_effort") == ["medium", None, "minimal"]
    assert "reasoning_effort" not in calls[1]


def test_usage_counts_reach_observer_per_stage_without_content():
    events = []
    run(UsageClient, stage_models={"intent": "stronger-model"},
        observer=lambda stage, status, **details: events.append((stage, status, details)))
    usage = [details for stage, _, details in events if stage == "model_usage"]
    assert [item["agent_stage"] for item in usage] == ["intent", "planner", "reviewer"]
    assert [item["model"] for item in usage] == ["stronger-model", "cheap-model", "cheap-model"]
    for item in usage:
        assert set(item) == {"agent_stage", "model", "input_tokens", "output_tokens",
                             "cached_input_tokens", "reasoning_tokens"}
        assert (item["input_tokens"], item["output_tokens"]) == (1000, 300)
        assert (item["cached_input_tokens"], item["reasoning_tokens"]) == (256, 200)


def test_missing_usage_emits_no_event_and_broken_observer_cannot_change_decision():
    events = []
    run(observer=lambda stage, status, **details: events.append(stage))
    assert "model_usage" not in events

    def broken(stage, status, **details):
        raise RuntimeError("observer failure")

    assert len(run(UsageClient, observer=broken)) == 3


@pytest.mark.parametrize("options", [
    {"stage_models": {"sql": "model"}},
    {"stage_models": {"intent": ""}},
    {"stage_models": {"intent": 5}},
    {"stage_models": ["intent"]},
    {"reasoning_effort": "extreme"},
    {"reasoning_effort": {"intent": "extreme"}},
    {"reasoning_effort": {"review": "low"}},
    {"reasoning_effort": 3},
])
def test_invalid_stage_settings_fail_at_construction(options):
    with pytest.raises(ValueError):
        OpenAIReportAgent(CONFIG, client=Client(), **options)


def test_single_interpreter_accepts_optional_reasoning_effort():
    client = Client(planned())
    interpreter = OpenAIReportInterpreter(CONFIG, client=client, reasoning_effort="low")
    interpreter.interpret(MESSAGES, spec(), permitted_catalog(catalog(), scope()), TODAY)
    assert client.calls[0]["model"] == "cheap-model"
    assert client.calls[0]["reasoning_effort"] == "low"
    with pytest.raises(ValueError):
        OpenAIReportInterpreter(CONFIG, client=Client(), reasoning_effort="max")
