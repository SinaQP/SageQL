"""Phase 14 regression: missing-year failures must not become unrelated reports."""
from dataclasses import replace
from decimal import Decimal
from types import SimpleNamespace

import pytest

from examples import multi_domain as hosts
from sageql import Message
from sageql.sdk import Interpretation, PeriodSelection, SQLiteSessionStore
from sageql.sdk.evidence import request_evidence
from evaluations.runner import extracted, ready
from tests.test_sdk_semantic_evidence import engine_at, submit, APPROVED


REQUEST = 'For the stock review, tabulate Units for each Department in September. Which year should I supply?'


def desired():
    return replace(hosts.scenarios()[0].initial, metric_ids=('units',), dimension_ids=('department',),
                   chart='table', time_grain='none', order_by=None, descending=False, limit=100)


def partial_month():
    value = extracted(desired(), period=None, missing=('period',))
    value['period'] = {'kind': 'month', 'start': None, 'end': None, 'year': None,
                       'month': 9, 'count': None, 'unit': None}
    return value


def test_observed_partial_month_becomes_a_real_year_question_without_retries(tmp_path):
    engine, adapter, client = engine_at(tmp_path, responses=(partial_month(),))
    reply = submit(engine, REQUEST)
    assert reply.status == 'needs_clarification', reply.to_dict()
    assert 'year' in reply.clarification.lower()
    assert len(client.calls) == 1 and not adapter.calls
    state = engine.get_session(reply.session_id, hosts.ACTOR)
    assert state['revision'] == 1 and state['clarification'] == reply.clarification
    replay = submit(engine, REQUEST, session=reply.session_id)
    assert replay.to_dict() == reply.to_dict() and len(client.calls) == 1


@pytest.mark.parametrize('answer', ['Use 2026, please.', 'Please use 2026.', 'The year is 2026.', '۲۰۲۶، لطفاً.'])
def test_year_answer_preserves_month_metric_grouping_across_reopen(tmp_path, answer):
    correct = desired()
    engine, adapter, client = engine_at(tmp_path, responses=(partial_month(),
        extracted(correct, turn_kind='answer'), ready(correct), APPROVED))
    first = submit(engine, REQUEST)
    assert first.status == 'needs_clarification', first.to_dict()
    engine.sessions = SQLiteSessionStore(tmp_path / 'sessions.sqlite')
    reply = submit(engine, answer, session=first.session_id, request='year', revision=first.revision)
    assert reply.status == 'report_ready', reply.to_dict()
    assert reply.report.rows == (('Books', Decimal('5')), ('Garden', Decimal('9')))
    assert [f.id for f in reply.report.fields] == ['department', 'units']
    assert reply.report.provenance['period_start'] == '2026-09-01'
    assert reply.report.provenance['period_end_exclusive'] == '2026-10-01'
    assert len(adapter.calls) == 1 and len(client.calls) == 4
    replay = submit(engine, answer, session=first.session_id, request='year', revision=first.revision)
    assert replay.to_dict() == reply.to_dict() and len(adapter.calls) == 1 and len(client.calls) == 4


def test_captured_wrong_annual_plan_is_rejected_even_when_reviewer_would_approve(tmp_path):
    wrong = replace(desired(), metric_ids=('revenue',), dimension_ids=(),
                    period=PeriodSelection('year', year=2026))
    engine, adapter, client = engine_at(tmp_path, responses=(partial_month(), extracted(wrong),
        ready(wrong), ready(wrong), APPROVED))
    first = submit(engine, REQUEST)
    assert first.status == 'needs_clarification'
    reply = submit(engine, 'Use 2026, please.', session=first.session_id, request='answer', revision=first.revision)
    assert reply.status == 'blocked' and reply.report is None and not adapter.calls
    assert not any(c['response_format']['json_schema']['name'] == 'sageql_report_review' for c in client.calls)


@pytest.mark.parametrize('answer', ['2026', 'Use 2026, please.', 'The year is 2026.', '۲۰۲۶، لطفاً.'])
def test_year_without_report_context_cannot_execute_provider_invented_defaults(tmp_path, answer):
    calls = []
    wrong = replace(desired(), metric_ids=('revenue',), dimension_ids=(),
                    period=PeriodSelection('year', year=2026))
    provider = SimpleNamespace(interpret=lambda *args: calls.append(args) or Interpretation('ready', wrong))
    engine, adapter, _ = engine_at(tmp_path, provider=provider)
    reply = submit(engine, answer)
    assert reply.status == 'needs_clarification' and reply.report is None
    assert not calls and not adapter.calls


@pytest.mark.parametrize('answer', ['Use 2026, please.', 'The year is 2026.', '۲۰۲۶، لطفاً.'])
def test_affirmative_year_evidence_binds_original_period_and_for_each_group(answer):
    catalog = hosts.retail_catalog()
    messages = (Message('user', REQUEST), Message('assistant', 'Which year should the requested period use?'),
                Message('user', answer))
    evidence = request_evidence(messages, catalog)
    assert evidence.period == PeriodSelection('month', year=2026, month=9)
    assert not evidence.missing
    assert ('sales', 'department') in evidence.dimensions or any(
        ('sales', 'department') in alternatives for alternatives in evidence.dimension_choices)


@pytest.mark.parametrize('fault', ['unknown_metric', 'malformed_json'])
def test_year_fallback_does_not_accept_other_invalid_provider_output(tmp_path, fault):
    value = partial_month()
    if fault == 'unknown_metric':
        value['metrics'][0]['concept_id'] = 'unregistered'
    else:
        value = 'not valid JSON'
    engine, adapter, client = engine_at(tmp_path, responses=(value,))
    reply = submit(engine, REQUEST)
    assert reply.status == 'blocked' and not adapter.calls and len(client.calls) == 1


@pytest.mark.parametrize('answer', ['Not 2026.', 'Use 2026 or 2027.', 'Is it 2026?', '«2026» is only an example.'])
def test_unconfirmed_or_conflicting_year_is_never_used_as_the_month_year(answer):
    evidence = request_evidence((Message('user', REQUEST),
        Message('assistant', 'Which year should the requested period use?'), Message('user', answer)),
        hosts.retail_catalog())
    assert evidence.missing == 'year' and evidence.period is None


def test_existing_report_can_still_receive_a_year_refinement(tmp_path):
    correct = desired()
    changed = replace(correct, period=PeriodSelection('month', year=2027, month=9))
    decisions = iter((correct, changed))
    provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', next(decisions)))
    engine, adapter, _ = engine_at(tmp_path, provider=provider)
    first = submit(engine, 'Units for each Department in September 2026, as a table.')
    assert first.status == 'report_ready'
    second = submit(engine, '2027', session=first.session_id, request='next-year', revision=first.revision)
    assert second.status == 'report_ready' and len(adapter.calls) == 2
    assert second.report.provenance['period_start'] == '2027-09-01'


def test_registered_numeric_business_label_is_not_misclassified_as_unbound_year(tmp_path):
    catalog = hosts.retail_catalog()
    fact = catalog.datasets[0]
    fact = replace(fact, metrics=tuple(replace(metric, label='2026') if metric.id == 'units' else metric
                                       for metric in fact.metrics))
    catalog = replace(catalog, datasets=(fact, *catalog.datasets[1:]))
    provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', desired()))
    engine, adapter, _ = engine_at(tmp_path, catalog=catalog, provider=provider)
    reply = submit(engine, '2026')
    assert reply.status == 'report_ready' and len(adapter.calls) == 1


def test_repeated_unbound_year_cannot_loop_or_execute_an_invented_report(tmp_path):
    calls = []
    provider = SimpleNamespace(interpret=lambda *args: calls.append(args) or Interpretation('ready', desired()))
    engine, adapter, _ = engine_at(tmp_path, provider=provider)
    first = submit(engine, '2026')
    assert first.status == 'needs_clarification'
    second = submit(engine, '2027', session=first.session_id, request='again', revision=first.revision)
    assert second.status == 'blocked' and second.error['code'] == 'clarification_stalled'
    assert not calls and not adapter.calls


def test_for_each_inside_a_literal_filter_value_does_not_add_grouping():
    catalog = hosts.retail_catalog()
    evidence = request_evidence((Message('user',
        'Net sales in September 2026, Department = "for each Department".'),), catalog)
    assert not evidence.dimensions and not evidence.dimension_choices
