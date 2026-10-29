"""Unspecified-control placeholders observed from live nano output; no network."""
from dataclasses import replace

import pytest

from sageql import Message
from sageql.sdk import PeriodSelection, SDKError
from sageql.sdk.intent import check_intent, normalize_unspecified_controls
from sageql.sdk.semantics import permitted_catalog
from test_sdk_intent import APPROVED, TODAY, catalog, intent, planned, provider, scope, spec

ALL = PeriodSelection("all")
EMPTY_MONTH = PeriodSelection("month")  # Observed: month with neither year nor month.
MESSAGES = (Message("user", "ساعات کارکنان ماه گذشته"),)


@pytest.mark.parametrize("placeholder", [ALL, EMPTY_MONTH])
def test_unspecified_comparison_placeholder_is_cleared(placeholder):
    raw = intent(comparison=placeholder, comparison_specified=False)
    normalized = normalize_unspecified_controls(raw)
    assert normalized.comparison is None and normalized.comparison_specified is False
    check_intent(normalized, permitted_catalog(catalog(), scope()), today=TODAY)
    with pytest.raises(SDKError):
        check_intent(raw, permitted_catalog(catalog(), scope()), today=TODAY)


def test_comparison_with_change_calculation_keeps_value_and_sets_flag():
    previous = PeriodSelection("month", year=2026, month=8)
    normalized = normalize_unspecified_controls(intent(
        comparison=previous, comparison_specified=False, comparison_calculation="change"))
    assert normalized.comparison == previous and normalized.comparison_specified is True


def test_unspecified_ordering_drops_order_and_direction():
    normalized = normalize_unspecified_controls(intent(order_by="hours", descending=True,
                                                       ordering_specified=False))
    assert (normalized.order_by, normalized.descending, normalized.ordering_specified) == (None, None, False)


def test_consistent_or_malformed_intents_are_unchanged():
    consistent = intent(comparison=PeriodSelection("last_month"), comparison_specified=True,
                        order_by="hours", ordering_specified=True, descending=True)
    assert normalize_unspecified_controls(consistent) is consistent
    malformed = replace(intent(comparison=ALL), comparison_specified="no")
    assert normalize_unspecified_controls(malformed) is malformed


def test_live_decoding_accepts_observed_nano_placeholder_and_completes_report():
    raw = intent().to_dict()
    raw.update(comparison={"kind": "all", "start": None, "end": None, "year": None, "month": None,
                           "count": None, "unit": None}, comparison_specified=False)
    agent, client = provider(raw, planned(), APPROVED)
    decision = agent.interpret(MESSAGES, spec(), permitted_catalog(catalog(), scope()), TODAY)
    assert decision.status == "ready" and decision.spec.comparison is None
    assert len(client.calls) == 3
