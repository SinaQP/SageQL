"""Shared comparison-role and explicit-total invariants, independent of model agreement."""
from dataclasses import replace
from pathlib import Path
import pytest
from sageql import Message
from sageql.sdk import PeriodSelection, SDKError, ReportSpec
from sageql.sdk.evidence import request_evidence, final_evidence_check
from evaluations.phase03_hosts import TODAY
from evaluations.phase05_hosts import host
from evaluations.phase08 import load_cases as frozen
from evaluations.runner import ScriptedClient, extracted, ready
from evaluations.trajectories import run_trajectory, target_spec
from tests.test_sdk_semantic_evidence import APPROVED


def r04():
    return frozen('replacement', ['R04'], corpus_root=Path(__file__).resolve().parents[1] /
        'evaluations/phase14_replacements', corpus_version='v3', cohort_prefix='phase14')[0]


@pytest.mark.parametrize('text,kind,year,base,reference', [
    ('June 2026 is the base and July 2026 is the comparison.', 'month', 2026, 6, 7),
    ('The base period is June 2026 and the comparison period is July 2026.', 'month', 2026, 6, 7),
    ('Set the base to June 2026 and the reference to July 2026.', 'month', 2026, 6, 7),
    ('Set the reference to July 2026 and the base to June 2026.', 'month', 2026, 6, 7),
    ('The base is June 2026 and July 2026 is the comparison.', 'month', 2026, 6, 7),
    ('The base is 2026 June and the reference is 2026 July.', 'month', 2026, 6, 7),
    ('The base is Khordad 1405 and the reference is Tir 1405.', 'jalali_month', 1405, 3, 4),
    ('June is the base and July 2026 is the reference.', 'month', 2026, 6, 7),
])
def test_month_role_binding_is_independent_of_word_order(text, kind, year, base, reference):
    catalog, _, _ = host('workshop', 'workshop-values-v1')
    evidence = request_evidence((Message('user', text),), catalog)
    assert evidence.period == PeriodSelection(kind, year=year, month=base)
    assert evidence.comparison == PeriodSelection(kind, year=year, month=reference)


def test_assignment_to_can_never_become_a_month_range_at_final_gate():
    case = r04(); target = target_spec(case, case['turns'][0])
    target = replace(target, period=PeriodSelection('month', year=2026, month=6),
        comparison=PeriodSelection('month', year=2026, month=7))
    catalog, _, _ = host('library', 'library-values-v1')
    messages = (Message('user', 'Borrowings in a table; set the base to June 2026 and the reference to July 2026.'),)
    final_evidence_check(messages, catalog, target, TODAY, 'en')
    for wrong in (replace(target, period=target.comparison, comparison=target.period),
                  replace(target, period=PeriodSelection('range', '2026-06-01', '2026-08-01'), comparison=None)):
        with pytest.raises(SDKError):
            final_evidence_check(messages, catalog, wrong, TODAY, 'en')


@pytest.mark.parametrize('connector', ['to', 'through'])
def test_real_month_ranges_remain_ranges(connector):
    catalog, _, _ = host('workshop', 'workshop-values-v1')
    evidence = request_evidence((Message('user', f'Billed amount from June 2026 {connector} July 2026 in a table.'),), catalog)
    assert evidence.period == PeriodSelection('range', '2026-06-01', '2026-08-01')
    assert evidence.comparison is None


@pytest.mark.parametrize('text', [
    'Do not set the base to June 2026 or the reference to July 2026.',
    'Use the title "Set the base to June 2026 and the reference to July 2026".',
    'Billed amount; Channel = "The base is June 2026 and the reference is July 2026".',
])
def test_negative_and_data_role_text_never_supplies_positive_periods(text):
    catalog, _, _ = host('workshop', 'workshop-values-v1')
    evidence = request_evidence((Message('user', text),), catalog)
    assert evidence.period is None and evidence.comparison is None


@pytest.mark.parametrize('text', [
    'Set the base to June 2026 and the base to July 2026.',
    'Set the reference to June 2026; July 2026 is also mentioned.',
])
def test_incomplete_or_conflicting_roles_cannot_fall_back_to_a_range(text):
    catalog, _, _ = host('workshop', 'workshop-values-v1')
    evidence = request_evidence((Message('user', text),), catalog)
    assert evidence.missing == 'period' and evidence.period is None and evidence.comparison is None


def test_role_binding_never_invents_a_year():
    catalog, _, _ = host('workshop', 'workshop-values-v1')
    evidence = request_evidence((Message('user', 'Set the base to June and the reference to July.'),), catalog)
    assert evidence.missing == 'year' and evidence.period is None


@pytest.mark.parametrize('domain,version,text,metric,dimension', [
    ('library', 'library-values-v1', 'Give a table total of Borrowings for September 2026 with Shelf = Scientific; no time buckets.', 'borrowings', 'shelf'),
    ('workshop', 'workshop-values-v1', 'Give Billed amount for July 2026 with Channel = "Counter" as a total in a table.', 'billed', 'channel'),
    ('retail', 'retail-values-v1', 'Tabulate the total Units sold for September 2026.', 'units', 'department'),
])
def test_explicit_total_has_a_known_empty_business_projection(domain, version, text, metric, dimension):
    catalog, _, _ = host(domain, version)
    evidence = request_evidence((Message('user', text),), catalog)
    owner = evidence.metrics[0][0]
    spec = ReportSpec(owner, (metric,), filters=tuple(r.condition for r in evidence.filter_requirements),
        period=evidence.period, chart='table', time_grain='none', order_by=None)
    final_evidence_check((Message('user', text),), catalog, spec, TODAY, 'en')
    with pytest.raises(SDKError):
        final_evidence_check((Message('user', text),), catalog, replace(spec, dimension_ids=(dimension,)), TODAY, 'en')


@pytest.mark.parametrize('grouping', ['by Shelf', 'for each Shelf'])
def test_total_with_an_explicit_group_keeps_it(grouping):
    case = r04(); spec = replace(target_spec(case, case['turns'][0]), dimension_ids=('shelf',))
    catalog, _, _ = host('library', 'library-values-v1')
    messages = (Message('user', f'Give a table total of Borrowings {grouping} in September 2026 with Shelf = Scientific.'),)
    final_evidence_check(messages, catalog, spec, TODAY, 'en')


@pytest.mark.parametrize('suffix', ['Service = "total".', 'This is a table, not a total.'])
def test_literal_or_negative_total_does_not_close_grouping(suffix):
    catalog, _, _ = host('workshop', 'workshop-values-v1')
    evidence = request_evidence((Message('user', 'Billed amount in July 2026 in a table; ' + suffix),), catalog)
    assert getattr(evidence, 'projection', None) is None


def pending_total_messages(owner_answer):
    return (Message('user', 'Give a table total of Billed amount in July, only Portal.'),
        Message('assistant', 'Which registered filters and exact values should I use, retain or remove? Please clarify the selections.'),
        Message('user', owner_answer), Message('assistant', 'Which year should the requested period use?'),
        Message('user', '2026.'))


def test_known_empty_projection_survives_owner_and_year_answers():
    catalog, _, _ = host('workshop', 'workshop-ambiguous-v1')
    messages = pending_total_messages('Choose Channel filter for Portal.')
    evidence = request_evidence(messages, catalog)
    correct = ReportSpec('jobs', ('billed',), filters=tuple(r.condition for r in evidence.filter_requirements),
        period=PeriodSelection('month', year=2026, month=7))
    final_evidence_check(messages, catalog, correct, TODAY, 'en')
    with pytest.raises(SDKError):
        final_evidence_check(messages, catalog, replace(correct, dimension_ids=('service',)), TODAY, 'en')


def test_explicit_new_group_answer_replaces_previous_total_projection():
    catalog, _, _ = host('workshop', 'workshop-ambiguous-v1')
    messages = pending_total_messages('Choose Channel filter for Portal; group by Service.')
    evidence = request_evidence(messages, catalog)
    correct = ReportSpec('jobs', ('billed',), ('service',), filters=tuple(r.condition for r in evidence.filter_requirements),
        period=PeriodSelection('month', year=2026, month=7))
    final_evidence_check(messages, catalog, correct, TODAY, 'en')


def test_r04_total_pipeline_rejects_extra_group_and_publishes_only_corrected_plan():
    case = r04(); case['turns'] = case['turns'][:1]
    def client(turn, target, catalog):
        wrong = replace(target, dimension_ids=('shelf',))
        return ScriptedClient([extracted(wrong), ready(wrong), ready(target), APPROVED])
    result = run_trajectory(case, client_factory=client)
    assert result['correct'], result['turns'][0]['safe_errors']
    turn = result['turns'][0]
    assert turn['checks']['rows'] and turn['checks']['fields'] and turn['checks']['specification']
    assert turn['reviews'] == [{'candidate_correct': True, 'approved': True}]


def test_persistently_wrong_group_plan_stays_blocked():
    case = r04(); case['turns'] = case['turns'][:1]
    def client(turn, target, catalog):
        wrong = replace(target, dimension_ids=('shelf',))
        return ScriptedClient([extracted(wrong), ready(wrong), ready(wrong), APPROVED])
    result = run_trajectory(case, client_factory=client)
    assert result['turns'][0]['status'] == 'blocked' and not result['turns'][0]['database_calls']
    assert not result['turns'][0]['reviews']


def test_existing_grouped_report_is_not_erased_by_period_totals_refinement():
    case = r04(); current = replace(target_spec(case, case['turns'][0]), dimension_ids=('shelf',))
    catalog, _, _ = host('library', 'library-values-v1')
    messages = (Message('user', 'Keep the same report; show whole-period totals.'),)
    final_evidence_check(messages, catalog, current, TODAY, 'en', current)


def test_total_in_registered_metric_label_is_data_not_a_projection_command():
    catalog, _, _ = host('library', 'library-values-v1')
    fact = catalog.datasets[0]
    catalog = replace(catalog, datasets=(replace(fact, metrics=tuple(
        replace(m, label='Total borrowings') if m.id == 'borrowings' else m for m in fact.metrics)), *catalog.datasets[1:]))
    evidence = request_evidence((Message('user', 'Total borrowings for September 2026 in a table.'),), catalog)
    assert getattr(evidence, 'projection', None) is None
