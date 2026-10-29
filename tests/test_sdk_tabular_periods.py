"""Regressions from Phase 13's real model: period selection is not grouping."""
from dataclasses import replace
from decimal import Decimal

import pytest

from examples import multi_domain as hosts
from sageql import Message
from sageql.sdk.evidence import request_evidence
from tests.test_sdk_semantic_evidence import engine_at, submit, APPROVED
from evaluations.runner import extracted, ready


@pytest.mark.parametrize('text', [
    'For the September 2026 ledger, return Net sales in a table.',
    'Tabulate Net sales over September 2026.',
    'فروش را در September 2026 در جدول نمایش بده.',
])
def test_dated_table_evidence_requires_period_totals(text):
    evidence = request_evidence((Message('user', text),), hosts.retail_catalog())
    assert evidence.period.year == 2026 and evidence.period.month == 9
    assert evidence.time_grain == 'none'


@pytest.mark.parametrize('text,expected', [
    ('Show daily Net sales in a table for September 2026', 'day'),
    ('Show monthly Net sales in a table for September 2026', 'month'),
    ('Show Net sales for September 2026 with the title "table"', None),
    ('Show Net sales for September 2026, not in a table', None),
    ('Show Net sales for September 2026', None),
])
def test_explicit_breakdowns_and_literal_table_word_are_preserved(text, expected):
    assert request_evidence((Message('user', text),), hosts.retail_catalog()).time_grain == expected


def test_tabular_refinement_preserves_existing_time_breakdown():
    current = replace(hosts.scenarios()[0].initial, time_grain='month')
    evidence = request_evidence((Message('user', 'Return that in a table for September 2026'),),
                                hosts.retail_catalog(), current)
    assert evidence.time_grain is None


def test_correlated_wrong_intent_and_plan_are_blocked_before_review_and_read(tmp_path):
    correct = replace(hosts.scenarios()[0].initial, dimension_ids=(), chart='table', time_grain='none',
                      order_by=None, descending=False, limit=100)
    wrong = replace(correct, time_grain='month')
    engine, adapter, client = engine_at(tmp_path, responses=(extracted(wrong), ready(wrong), ready(wrong), APPROVED))
    reply = submit(engine, 'For the September 2026 ledger, return Net sales in a table.')
    assert reply.status == 'blocked' and reply.report is None
    assert not adapter.calls
    assert not any(call['response_format']['json_schema']['name'] == 'sageql_report_review' for call in client.calls)


def test_model_repairs_wrong_time_breakdown_then_returns_independent_total(tmp_path):
    correct = replace(hosts.scenarios()[0].initial, dimension_ids=(), chart='table', time_grain='none',
                      order_by=None, descending=False, limit=100)
    wrong = replace(correct, time_grain='month')
    engine, adapter, client = engine_at(tmp_path, responses=(extracted(wrong), ready(wrong), ready(correct), APPROVED))
    reply = submit(engine, 'For the September 2026 ledger, return Net sales in a table.')
    assert reply.status == 'report_ready', reply.to_dict()
    assert reply.report.rows == ((Decimal('115'),),)
    assert [field.id for field in reply.report.fields] == ['revenue']
    assert len(adapter.calls) == 1


def test_plain_tabulation_does_not_authorize_model_invented_ranking(tmp_path):
    correct = replace(hosts.scenarios()[0].initial, chart='table', time_grain='none',
                      order_by=None, descending=False)
    wrong = replace(correct, order_by='revenue', descending=True)
    observed_intent = extracted(correct, ordering_specified=False, descending=None, limit=None)
    engine, adapter, client = engine_at(tmp_path, responses=(observed_intent, ready(wrong), ready(wrong), APPROVED))
    reply = submit(engine, 'Tabulate Net sales for each department over September 2026.')
    assert reply.status == 'blocked' and not adapter.calls
    assert not any(call['response_format']['json_schema']['name'] == 'sageql_report_review' for call in client.calls)


@pytest.mark.parametrize('text,target,direction', [
    ('Tabulate Net sales by department in September 2026', None, False),
    ('Tabulate the top 2 departments by Net sales in September 2026', 'revenue', True),
    ('Tabulate Net sales by department in September 2026, sort by department ascending', 'department', False),
])
def test_plain_and_explicit_table_ordering_evidence(text, target, direction):
    evidence = request_evidence((Message('user', text),), hosts.retail_catalog())
    if target is None:
        assert evidence.plain_table and evidence.ordering is None
    else:
        assert evidence.ordering.target == target and evidence.ordering.descending == direction
