"""V5 comparison-role and clarified-table failures; frozen answers unchanged."""
from dataclasses import replace
from pathlib import Path

import pytest

from sageql import Message
from sageql.sdk import PeriodSelection, SDKError
from sageql.sdk.evidence import request_evidence, final_evidence_check, anchor_intent
from sageql.sdk.intent import ReportIntent, ConceptRef
from evaluations.phase03_hosts import TODAY
from evaluations.phase05_hosts import host
from evaluations.phase08 import load_cases as frozen
from evaluations.phase14 import load_cases
from evaluations.runner import ScriptedClient, extracted, ready
from evaluations.trajectories import run_trajectory, target_spec, responses
from tests.test_sdk_semantic_evidence import APPROVED


def replacement():
    return frozen('replacement', ['R02'], corpus_root=Path(__file__).resolve().parents[1] /
                  'evaluations/phase14_replacements', corpus_version='v3', cohort_prefix='phase14')[0]


def owner_year_messages(*, sorting=''):
    case = replacement()
    return (Message('user', case['turns'][0]['request'] + sorting),
        Message('assistant', 'Which registered filters and exact values should I use, retain or remove? Please clarify the selections.'),
        Message('user', case['turns'][2]['request']),
        Message('assistant', 'Which year should the requested period use?'), Message('user', '2026.'))


@pytest.mark.parametrize('text', [
    'Reverse the comparison: June 2026 is the base and July 2026 is the comparison.',
    'July 2026 is the reference and June 2026 is the base.',
    'Use June 2026 as the base and July 2026 as the comparison.',
])
def test_explicit_month_roles_override_mention_order_and_stale_intent(text):
    catalog, _, _ = host('workshop', 'workshop-values-v1')
    evidence = request_evidence((Message('user', text),), catalog)
    assert evidence.period == PeriodSelection('month', year=2026, month=6)
    assert evidence.comparison == PeriodSelection('month', year=2026, month=7)
    stale = ReportIntent(metrics=(ConceptRef('jobs', 'billed'),),
        period=evidence.comparison, comparison=evidence.period)
    anchored = anchor_intent(stale, evidence)
    assert anchored.period == evidence.period and anchored.comparison == evidence.comparison


def test_explicit_jalali_month_roles_reuse_registered_date_operations():
    catalog, _, _ = host('workshop', 'workshop-values-v1')
    evidence = request_evidence((Message('user',
        'Tir 1405 is the comparison and Khordad 1405 is the base.'),), catalog)
    assert evidence.period == PeriodSelection('jalali_month', year=1405, month=3)
    assert evidence.comparison == PeriodSelection('jalali_month', year=1405, month=4)


@pytest.mark.parametrize('text', [
    'Do not use June 2026 as the base or July 2026 as the comparison.',
    'Use the title "June 2026 is the base and July 2026 is the comparison".',
    'Billed amount; Channel = "June 2026 is the base and July 2026 is the comparison".',
])
def test_negated_roles_titles_and_predicate_values_supply_no_period_roles(text):
    catalog, _, _ = host('workshop', 'workshop-values-v1')
    evidence = request_evidence((Message('user', text),), catalog)
    assert evidence.period is None and evidence.comparison is None


def test_duplicate_period_roles_require_clarification_instead_of_guessing():
    catalog, _, _ = host('workshop', 'workshop-values-v1')
    evidence = request_evidence((Message('user', 'June 2026 is the base and July 2026 is the base.'),), catalog)
    assert evidence.missing == 'period' and evidence.period is None and evidence.comparison is None


def test_explicit_period_roles_never_supply_a_missing_year():
    catalog, _, _ = host('workshop', 'workshop-values-v1')
    evidence = request_evidence((Message('user', 'June is the base and July is the comparison.'),), catalog)
    assert evidence.missing == 'year' and evidence.period is None


def test_stale_reversed_periods_fail_the_provider_neutral_gate():
    case = load_cases(case_ids=['N04'])[0]
    target = target_spec(case, case['turns'][2])
    stale = replace(target, period=target.comparison, comparison=target.period)
    catalog, _, _ = host('workshop', 'workshop-values-v1')
    with pytest.raises(SDKError, match='contradicts'):
        final_evidence_check((Message('user', case['turns'][2]['request']),), catalog, stale, TODAY, 'en')


def test_stale_intent_can_recover_with_the_recorded_correct_period_plan():
    case = load_cases(case_ids=['N04'])[0]
    def client(turn, target, catalog):
        if turn['request'].startswith('Reverse'):
            stale = replace(target, period=target.comparison, comparison=target.period)
            # Original first plan had an unrequested calculation; it still must
            # be rejected. The bounded revision fixes it before a valid review.
            return ScriptedClient([extracted(stale, turn_kind='refine'),
                ready(replace(target, comparison_calculation='change')), ready(target), APPROVED])
        return ScriptedClient(responses(turn, target))
    result = run_trajectory(case, client_factory=client)
    assert result['correct'], [(t['index'], t['outcome'], t['safe_errors']) for t in result['turns']]
    assert result['turns'][2]['revisions'] == 1
    assert all(t['checks']['rows'] and t['checks']['specification'] for t in result['turns'])


def test_owner_then_year_preserves_plain_table_defaults():
    catalog, _, _ = host('workshop', 'workshop-ambiguous-v1')
    evidence = request_evidence(owner_year_messages(), catalog)
    assert evidence.plain_table and evidence.confirmed_clarification_answer
    assert evidence.period == PeriodSelection('month', year=2026, month=7)


def test_clarified_table_rejects_extra_sort_at_the_provider_neutral_boundary():
    case = replacement()
    target = target_spec(case, case['turns'][3])
    catalog, _, _ = host('workshop', 'workshop-ambiguous-v1')
    wrong = replace(target, order_by='billed', descending=True)
    with pytest.raises(SDKError, match='contradicts'):
        final_evidence_check(owner_year_messages(), catalog, wrong, TODAY, 'en')
    final_evidence_check(owner_year_messages(), catalog, target, TODAY, 'en')


def test_added_sort_requires_a_corrected_plan_before_review_and_publication():
    case = replacement()
    def client(turn, target, catalog):
        if turn['expect']['kind'] == 'report':
            return ScriptedClient([extracted(target, turn_kind='new', ordering_specified=False,
                descending=None, limit=None), ready(replace(target, order_by='billed', descending=True)),
                ready(target), APPROVED])
        return ScriptedClient(responses(turn, target))
    result = run_trajectory(case, client_factory=client)
    assert result['correct'], [(t['index'], t['outcome'], t['safe_errors']) for t in result['turns']]
    last = result['turns'][3]
    assert last['revisions'] == 1 and last['checks']['rows'] and last['checks']['specification']
    assert last['reviews'] == [{'candidate_correct': True, 'approved': True}]


def test_explicit_sorting_survives_the_same_clarification_chain():
    catalog, _, _ = host('workshop', 'workshop-ambiguous-v1')
    evidence = request_evidence(owner_year_messages(sorting=' Sort by Billed amount descending.'), catalog)
    assert evidence.ordering is not None and evidence.ordering.target == 'billed' and evidence.ordering.descending
    case = replacement()
    sorted_spec = replace(target_spec(case, case['turns'][3]), order_by='billed', descending=True)
    final_evidence_check(owner_year_messages(sorting=' Sort by Billed amount descending.'), catalog, sorted_spec, TODAY, 'en')


def test_existing_grouped_ranked_report_is_not_reset_to_fresh_table_defaults():
    case = replacement()
    current = replace(target_spec(case, case['turns'][3]), order_by='billed', descending=True)
    catalog, _, _ = host('workshop', 'workshop-ambiguous-v1')
    messages = (Message('user', 'Keep this report and its ordering.'),)
    evidence = request_evidence(messages, catalog, current)
    assert not evidence.plain_table
    final_evidence_check(messages, catalog, current, TODAY, 'en', current)


def test_legacy_host_defined_table_ordering_without_owner_clarification_is_preserved():
    from examples.multi_domain import scenarios
    scenario = next(s for s in scenarios() if s.name == 'library')
    messages = (Message('user', scenario.question),
        Message('assistant', 'Which year should September cover?'), Message('user', '2026'))
    # This existing provider chooses a preset ordering. The new closed defaults
    # belong to confirmed owner continuations, not every historical provider.
    final_evidence_check(messages, scenario.catalog, scenario.initial, TODAY, 'en')
