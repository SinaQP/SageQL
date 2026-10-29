"""Observed continuation defects, synthetic data and independent assertions only."""
from dataclasses import replace

import pytest

from sageql import Message
from sageql.sdk import FilterValueDefinition, UserFilter
from sageql.sdk.evidence import request_evidence
from evaluations.phase05_hosts import host
from evaluations.phase14 import load_cases
from evaluations.trajectories import run_trajectory


@pytest.mark.parametrize('identifier', ['N02', 'N03'])
def test_observed_conversation_completes_with_valid_scripted_model_outputs(identifier):
    # The shared scorer checks the frozen independent Decimal/row/spec oracle,
    # SQLite reopen, receipts, policies, old reports and model-data isolation.
    result = run_trajectory(load_cases(case_ids=[identifier])[0])
    assert result['correct'], [(t['index'], t['outcome'], t['safe_errors']) for t in result['turns']]


@pytest.mark.parametrize('answer', [
    'Use the Channel filter for Portal.', 'Choose Channel filter for Portal.',
    'Select the Channel filter for "Portal".',
])
def test_explicit_pending_owner_and_same_value_preserve_other_missing_details(answer):
    catalog, _, _ = host('workshop', 'workshop-ambiguous-v1')
    original = load_cases(case_ids=['N02'])[0]['turns'][0]['request']
    messages = (Message('user', original), Message('assistant',
        'Which registered filters and exact values should I use, retain or remove? Please clarify the selections.'),
        Message('user', answer))
    evidence = request_evidence(messages, catalog)
    assert evidence.missing == 'year' and evidence.pending_filter_value is None
    assert {r.condition for r in evidence.filter_requirements} == {
        UserFilter('channel_filter', 'eq', ('Web',)), UserFilter('technician_filter', 'neq', ('T3',))}
    assert evidence.metrics == (('jobs', 'minutes_total'),)
    assert evidence.dimensions == (('jobs', 'technician'),)


@pytest.mark.parametrize('answer', [
    'Not Channel filter for Portal.', 'Should I use Channel filter for Portal?',
    'Use Unknown filter for Portal.', 'Use Channel filter for Desk.',
    'Use Channel or Service filter for Portal.', '"Use Channel filter for Portal" is an example.',
    'Use Channel filter for Portal; not Channel.',
    'Use Channel filter for Portal; use Service filter for Portal.',
])
def test_unconfirmed_changed_or_ambiguous_pending_owner_is_not_bound(answer):
    catalog, _, _ = host('workshop', 'workshop-ambiguous-v1')
    from sageql.sdk.grounding import filter_controls
    result = filter_controls(answer, catalog, pending_value=('Portal', 'eq'))
    assert result.missing == 'filter_value' and not result.filters


@pytest.mark.parametrize('copula', ['باشد', 'باشه', 'است', 'هست'])
def test_unquoted_registered_alias_copula_binds_only_registered_value(copula):
    catalog, _, _ = host('library', 'library-values-v1')
    evidence = request_evidence((Message('user',
        'Borrowings by Shelf in September 2026; Shelf = تاریخی ' + copula + '.'),), catalog)
    assert [r.condition for r in evidence.filter_requirements] == [UserFilter('shelf_filter', 'eq', ('History',))]
    assert evidence.period.year == 2026 and evidence.period.month == 9


@pytest.mark.parametrize('literal', ['"تاریخی باشد"', '«تاریخی باشد»', 'ناشناخته باشد'])
def test_quoted_and_unregistered_text_keeps_its_exact_literal(literal):
    catalog, _, _ = host('library', 'library-values-v1')
    evidence = request_evidence((Message('user', 'Borrowings; Shelf = ' + literal),), catalog)
    expected = literal.strip('"«»')
    assert evidence.filter_requirements[0].condition.values == (expected,)


def test_complete_registered_term_with_copula_wins_over_shorter_alias():
    catalog, _, _ = host('library', 'library-values-v1')
    fact = catalog.datasets[0]
    fact = replace(fact, filters=tuple(replace(f, value_vocabulary=(*f.value_vocabulary,
        FilterValueDefinition('Exact phrase', ('تاریخی باشد',)))) if f.id == 'shelf_filter' else f
        for f in fact.filters))
    evidence = request_evidence((Message('user', 'Borrowings; Shelf = تاریخی باشد.'),),
                                replace(catalog, datasets=(fact, *catalog.datasets[1:])))
    assert evidence.filter_requirements[0].condition.values == ('Exact phrase',)


def test_canonical_value_with_copula_wins_even_without_a_matching_alias():
    catalog, _, _ = host('library', 'library-values-v1')
    fact = catalog.datasets[0]
    fact = replace(fact, filters=tuple(replace(f, value_vocabulary=(*f.value_vocabulary,
        FilterValueDefinition('تاریخی باشد', ('A separate label',)))) if f.id == 'shelf_filter' else f
        for f in fact.filters))
    evidence = request_evidence((Message('user', 'Borrowings; Shelf = تاریخی باشد.'),),
                                replace(catalog, datasets=(fact, *catalog.datasets[1:])))
    assert evidence.filter_requirements[0].condition.values == ('تاریخی باشد',)


@pytest.mark.parametrize('fault', ['unused_month_unit', 'duplicate_metric'])
def test_observed_malformed_outputs_still_fail_before_review_or_database(tmp_path, fault):
    from tests.test_sdk_semantic_evidence import engine_at, submit, APPROVED
    from tests.test_sdk_year_answer_recovery import desired
    from evaluations.runner import extracted, ready
    target = desired()
    intent, proposal = extracted(target), ready(target)
    if fault == 'unused_month_unit':
        intent['period']['unit'] = 'month'
    else:
        proposal['spec']['metric_ids'].append('units')
    engine, adapter, client = engine_at(tmp_path, responses=(intent, proposal, APPROVED))
    reply = submit(engine, 'Tabulate Units sold for each Department in September 2026.')
    assert reply.status == 'blocked' and not adapter.calls
    assert not any(c['response_format']['json_schema']['name'] == 'sageql_report_review' for c in client.calls)
