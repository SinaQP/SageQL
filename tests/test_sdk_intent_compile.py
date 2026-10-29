"""Opt-in local compilation of complete intents (planner skipped); no network."""
from dataclasses import replace

import pytest

from sageql import Message
from sageql.sdk import PeriodSelection, ReportSpec
from sageql.sdk.intent import spec_from_intent
from sageql.sdk.semantics import permitted_catalog
from test_sdk_intent import APPROVED, TODAY, catalog, intent, planned, provider, scope, spec

GROUPED = ReportSpec("activities", ("hours",), ("unit",), period=PeriodSelection("last_month"))
REQUEST = (Message("user", "ساعات فعالیت به تفکیک واحد کاری در ماه گذشته"),)


def visible():
    return permitted_catalog(catalog(), scope())


def complete(request=GROUPED, **changes):
    return intent(request, filters=(), aggregate_filters=(), **changes)


def run(*responses, current=None, messages=REQUEST, **options):
    events = []
    agent, client = provider(*responses, compile_intent=True,
                             observer=lambda stage, status, **details: events.append(
                                 (stage, status, details.get("code"))), **options)
    decision = agent.interpret(messages, current, visible(), TODAY)
    return decision, client, [item for item in events if item[0] == "intent_compiled"]


def test_complete_intent_skips_planner_and_keeps_review():
    decision, client, compiled = run(complete(), APPROVED)
    assert decision.status == "ready" and decision.spec == GROUPED
    assert [call["response_format"]["json_schema"]["name"] for call in client.calls] == [
        "sageql_report_intent", "sageql_report_review"]
    assert compiled == [("intent_compiled", "complete", None)]


def test_default_still_calls_the_planner():
    agent, client = provider(complete(), planned(GROUPED), APPROVED)
    assert agent.interpret(REQUEST, None, visible(), TODAY).spec == GROUPED
    assert len(client.calls) == 3


def test_failed_preview_falls_back_to_planner_without_using_a_revision():
    # A line chart needs time grouping; with no grain the compiled spec fails
    # local preview, and the planner (unconstrained grain) supplies one.
    total = ReportSpec("activities", ("hours",), period=PeriodSelection("last_month"))
    line = replace(total, chart="line", time_grain="day")
    decision, client, compiled = run(complete(total, chart="line"), planned(line), APPROVED, max_revisions=0,
                                     messages=(Message("user", "نمودار خطی ساعات فعالیت در ماه گذشته"),))
    assert compiled == [("intent_compiled", "skipped", "specification_validation")]
    assert decision.status == "ready" and decision.spec == line
    assert len(client.calls) == 3


def test_unspecified_filters_on_refinement_use_the_planner():
    refine = replace(complete(turn_kind="refine"), filters=None)
    decision, client, compiled = run(refine, planned(GROUPED), APPROVED, current=GROUPED)
    assert compiled == [("intent_compiled", "skipped", "incomplete_intent")]
    assert len(client.calls) == 3


def test_spec_from_intent_inherits_presentation_on_refinement_and_defaults_otherwise():
    current = replace(GROUPED, chart="bar", limit=10)
    refined = spec_from_intent(complete(turn_kind="refine"), visible(), current)
    assert (refined.chart, refined.limit) == ("bar", 10)
    fresh = spec_from_intent(complete(), visible(), current)
    assert (fresh.chart, fresh.limit, fresh.order_by, fresh.comparison) == ("table", 100, None, None)


@pytest.mark.parametrize("changes", [
    {"missing": ("period",), "period": None},
    {"period": None},
    {"unsupported_reason": "share of total"},
])
def test_spec_from_intent_declines_incomplete_or_unavailable_intents(changes):
    assert spec_from_intent(replace(complete(), **changes), visible()) is None


def test_refinement_that_leaves_current_ordering_unspecified_declines():
    current = replace(GROUPED, order_by="hours", descending=True)
    assert spec_from_intent(complete(turn_kind="refine"), visible(), current) is None
    explicit = complete(turn_kind="refine", order_by="hours", ordering_specified=True, descending=True)
    assert spec_from_intent(explicit, visible(), current).order_by == "hours"


def test_invalid_compile_intent_or_review_option_is_rejected():
    with pytest.raises(ValueError):
        provider(compile_intent="yes")
    with pytest.raises(ValueError):
        provider(review=0)


def test_without_review_a_compiled_report_needs_one_model_call():
    decision, client, compiled = run(complete(), review=False)
    assert decision.status == "ready" and decision.spec == GROUPED
    assert [call["response_format"]["json_schema"]["name"] for call in client.calls] == ["sageql_report_intent"]


def test_without_review_planner_output_still_passes_local_intent_checks():
    agent, client = provider(complete(), planned(GROUPED), review=False)
    assert agent.interpret(REQUEST, None, visible(), TODAY).spec == GROUPED
    assert len(client.calls) == 2
    # A planner proposal that contradicts the intent is still rejected locally.
    agent, client = provider(complete(), planned(replace(GROUPED, dimension_ids=())), review=False,
                             max_revisions=0)
    with pytest.raises(Exception) as error:
        agent.interpret(REQUEST, None, visible(), TODAY)
    assert getattr(error.value, "code", None) == "intent_mismatch"
