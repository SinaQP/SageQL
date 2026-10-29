"""Independent semantic continuation regressions, including final custom gates."""
from dataclasses import replace
import json
import socket
from types import SimpleNamespace

import pytest

from sageql import Message
from sageql.sdk import ConceptRef, Interpretation, PeriodSelection, ReportIntent, ReportSpec, SDKError, UserFilter
from sageql.sdk.evidence import evidence_question, request_evidence
from sageql.sdk.phrases import ScopedText
from evaluations import phase08, phase09
from evaluations.phase05_hosts import host
from evaluations.trajectories import target_spec
from test_sdk_clarification_continuation import factory, submit, reopen, assert_report


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Phase 09 authorizes no external request')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)


def original(identifier):
    return phase08.load_cases(case_ids=[identifier])[0]


def ledger(identifier, index=0, *, current=None, answer=None):
    case = original(identifier)
    catalog = host(case['domain'], case['host_version'])[0]
    messages = (Message('user', case['turns'][index]['request']),)
    first = request_evidence(messages, catalog, current)
    if answer is None:
        return first
    question = evidence_question(first, 'en')
    assert question is not None
    return request_evidence((*messages, Message('assistant', question.question), Message('user', answer)), catalog, current)


def test_owner_question_does_not_acquire_year_reason_or_lose_group():
    e = ledger('A03')
    assert e.missing == 'filter_value'
    assert 'filter' in evidence_question(e, 'en').question.lower()
    assert e.metrics == (('jobs', 'minutes_total'),) and e.dimensions == (('jobs', 'technician'),)


def test_equivalent_related_group_does_not_preempt_year_question():
    e = ledger('A04')
    assert e.missing == 'year'
    question = evidence_question(e, 'en')
    assert question is None or 'year' in question.question.lower()
    # The fact is still selected by interpretation; no unregistered measure is invented.
    assert not e.metrics


def test_ranking_metric_answer_binds_criterion_and_keeps_entity_group_direction():
    e = ledger('A05', answer='My choice is Completed jobs.')
    assert not e.missing and e.metrics == (('jobs', 'jobs_count'),)
    assert e.dimensions == (('jobs', 'service'),)
    assert e.ordering.target == 'jobs_count' and e.ordering.descending is True
    assert e.period == PeriodSelection('month', year=2026, month=7)


@pytest.mark.parametrize('answer', ['Not Completed jobs.', 'Is Completed jobs correct?',
                                   'Example: "Completed jobs".', 'Completed jobs and Billed amount'])
def test_unconfirmed_criterion_answer_does_not_select_metric(answer):
    assert ledger('A05', answer=answer).missing is not None


def test_explicit_ascending_order_and_row_count_survive_metric_replacement():
    c = original('A06'); current = target_spec(c, c['turns'][0])
    e = ledger('A06', 1, current=current)
    assert not e.missing
    assert e.metrics == (('jobs', 'jobs_count'),) and ('jobs', 'billed') in e.excluded_metrics
    assert e.ordering.target == 'jobs_count' and e.ordering.descending is False and e.ordering.limit == 2
    assert e.filter_requirements[0].condition == current.filters[0]


def test_grouping_replacement_excludes_old_and_requires_new_dimension():
    c = original('A06'); current = target_spec(c, c['turns'][2])
    e = ledger('A06', 3, current=current)
    assert not e.missing and e.dimensions == (('jobs', 'channel'),)
    assert ('jobs', 'service') in e.excluded_dimensions


@pytest.mark.parametrize('prefix,suffix', [
    ('The words ', ' are just an example'), ('The phrases ', ' are only examples'),
    ('The quoted terms ', ' are examples'), ('این عبارت ', ' فقط یک مثال است'),
])
def test_explicit_example_roles_do_not_create_unavailable_operations(prefix, suffix):
    catalog = host('workshop', 'original')[0]
    text = prefix + '"percentage share"' + suffix + '; Billed amount by Service in July 2026.'
    e = request_evidence((Message('user', text),), catalog)
    assert not e.operations and not e.missing and not e.clarification


def test_requested_quoted_operation_remains_unsupported_and_unknown_role_clarifies():
    catalog = host('workshop', 'original')[0]
    active = request_evidence((Message('user', 'Show "percentage share" of total Billed amount in July 2026.'),), catalog)
    unknown = request_evidence((Message('user', '"percentage share"; Billed amount in July 2026.'),), catalog)
    assert 'percentage_share' in active.operations
    assert unknown.clarification == 'quoted_requirement'


@pytest.mark.parametrize('text,value', [
    ('Use Channel = Online instead.', 'Web'), ('Select Channel = Counter instead.', 'Desk'),
    ('Use Channel = "  Online instead  ".', '  Online instead  '),
    ('Channel = "Online instead".', 'Online instead'),
])
def test_correction_modifier_is_not_part_of_unquoted_value_but_quotes_are_exact(text, value):
    catalog = host('workshop', 'workshop-values-v1')[0]
    e = request_evidence((Message('user', 'Work minutes in July 2026; ' + text),), catalog)
    assert not e.missing and e.filter_requirements[0].condition.values == (value,)


@pytest.mark.parametrize('store_kind', ['memory', 'sqlite'])
def test_owner_then_year_reopen_invalid_answer_replay_and_custom_no_guess(tmp_path, store_kind):
    c = original('A03'); desired = target_spec(c, c['turns'][-1])
    from evaluations.runner import extracted
    responses = [extracted(desired, turn_kind='answer', period=None, missing=('year',)),
        {'status': 'needs_clarification', 'spec': None, 'question': 'Which year for July?', 'message': ''},
        {'approved': True, 'feedback': ''}]
    bundle = factory(tmp_path, desired, store_kind=store_kind, responses=responses)
    first = submit(bundle.engine, c['turns'][0]['request'])
    assert first.status == 'needs_clarification' and 'filter' in first.clarification.lower()
    invalid = submit(bundle.engine, 'Not Channel.', session=first.session_id, request='invalid', revision=first.revision)
    assert invalid.status == 'blocked' and not bundle.adapter.calls
    bundle.engine = reopen(bundle)
    owner = submit(bundle.engine, c['turns'][1]['request'], session=first.session_id, request='owner', revision=first.revision)
    assert owner.status == 'needs_clarification' and 'year' in owner.clarification.lower()
    bundle.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', desired))
    bundle.engine = reopen(bundle)
    guess = submit(bundle.engine, 'Thanks.', session=first.session_id, request='guess', revision=owner.revision)
    assert guess.status == 'blocked' and not bundle.adapter.calls
    final = submit(bundle.engine, '2026.', session=first.session_id, request='year', revision=owner.revision)
    assert_report(final, bundle, desired)
    replay = submit(bundle.engine, '2026.', session=first.session_id, request='year', revision=owner.revision)
    assert replay.to_dict() == final.to_dict() and len(bundle.adapter.calls) == 1


@pytest.mark.parametrize('store_kind', ['memory', 'sqlite'])
def test_equivalent_group_requirement_blocks_custom_omission_after_year(tmp_path, store_kind):
    c = original('A04'); desired = target_spec(c, c['turns'][1])
    from evaluations.runner import extracted
    responses = [extracted(desired, period=None, missing=('year',)),
        {'status': 'needs_clarification', 'spec': None, 'question': 'Which year for September?', 'message': ''},
        {'approved': True, 'feedback': ''}]
    bundle = factory(tmp_path, desired, domain='retail', profile='original', store_kind=store_kind, responses=responses)
    first = submit(bundle.engine, c['turns'][0]['request'])
    assert first.status == 'needs_clarification' and 'year' in first.clarification.lower()
    bundle.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', replace(desired, dimension_ids=())))
    bundle.engine = reopen(bundle)
    wrong = submit(bundle.engine, '2026.', session=first.session_id, request='wrong', revision=first.revision)
    assert wrong.status == 'blocked' and not bundle.adapter.calls
    bundle.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', desired))
    bundle.engine = reopen(bundle)
    good = submit(bundle.engine, '2026.', session=first.session_id, request='good', revision=first.revision)
    assert_report(good, bundle, desired, 'retail', ['2026-09-01', '2026-10-01'])


@pytest.mark.parametrize('store_kind', ['memory', 'sqlite'])
def test_conflict_correction_is_sdk_grounding_not_permission_to_accept_unissued_reference(tmp_path, store_kind):
    c = original('A11'); desired = target_spec(c, c['turns'][-1])
    bundle = factory(tmp_path, desired, profile=c['host_version'], store_kind=store_kind)
    first = submit(bundle.engine, c['turns'][0]['request'])
    assert first.status == 'needs_clarification'
    bundle.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', desired))
    bundle.engine = reopen(bundle)
    final = submit(bundle.engine, c['turns'][1]['request'], session=first.session_id, request='fix', revision=first.revision)
    assert_report(final, bundle, desired)


@pytest.fixture(scope='module')
def measured(tmp_path_factory):
    return phase09.run(phase09.load_cases(), tmp_path_factory.mktemp('phase09-offline'))


@pytest.mark.parametrize('identifier', [c['id'] for c in phase09.load_cases()])
def test_frozen_promoted_and_replacement_reports_remain_independently_complete(identifier, measured):
    assert next(c for c in measured['results'] if c['id'] == identifier)['correct']


def test_promotions_preserve_exact_original_turns_and_frozen_source():
    for c in phase09.load_cases('development'):
        old = (original(c['id']) if c.get('origin') else next(item for item in
            json.loads((phase09.ROOT / 'cases.v1.json').read_text(encoding='utf-8'))['cases'] if item['id'] == c['id']))
        assert c['turns'] == old['turns']
        assert not c['live_eligible']
    freeze = json.loads((phase09.ROOT / 'freeze.v1.json').read_text(encoding='utf-8'))
    assert freeze['frozen_before_targeted_production_repair']


def test_offline_author_alias_is_normalized_without_relaxing_public_model_enum():
    from evaluations.phase06_transport import ProtocolClient
    from sageql.sdk.intent import check_intent
    c = original('A04'); turn = c['turns'][2]
    client = ProtocolClient(turn, target_spec(c, turn), host(c['domain'], c['host_version'])[0])
    assert turn['turn_kind'] == 'refinement' and client.turn['turn_kind'] == 'refine'
    invalid = ReportIntent(metrics=(ConceptRef('jobs', 'jobs_count'),), turn_kind='refinement')
    with pytest.raises(SDKError):
        check_intent(invalid, host('workshop', 'original')[0])


@pytest.mark.parametrize('store_kind', ['memory', 'sqlite'])
@pytest.mark.parametrize('fault', ['old_metric', 'filter', 'date', 'direction', 'limit', 'group', 'invented_filter'])
def test_replacement_final_gate_rejects_wrong_or_invented_constraints_and_preserves_saved_report(tmp_path, store_kind, fault):
    from evaluations.runner import extracted, ready
    c = original('A06'); initial = target_spec(c, c['turns'][0]); desired = target_spec(c, c['turns'][1])
    bundle = factory(tmp_path, initial, profile=c['host_version'], store_kind=store_kind,
        responses=[extracted(initial, turn_kind='new'), ready(initial), {'approved': True, 'feedback': ''}])
    first = submit(bundle.engine, c['turns'][0]['request'])
    assert first.status == 'report_ready'
    wrong = {'old_metric': replace(desired, metric_ids=('billed', 'jobs_count')),
             'filter': replace(desired, filters=()),
             'date': replace(desired, period=PeriodSelection('month', year=2026, month=6)),
             'direction': replace(desired, descending=True),
             'limit': replace(desired, limit=100),
             'group': replace(desired, dimension_ids=('channel',)),
             'invented_filter': replace(desired, filters=(*desired.filters, UserFilter('technician_filter', 'eq', ('T2',))))}[fault]
    bundle.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', wrong))
    bundle.engine = reopen(bundle)
    blocked = submit(bundle.engine, c['turns'][1]['request'], session=first.session_id, request='wrong', revision=first.revision)
    assert blocked.status == 'blocked' and len(bundle.adapter.calls) == 1
    from evaluations.phase03_hosts import ACTOR
    assert bundle.engine.get_report(first.session_id, first.report.id, ACTOR).to_dict() == first.report.to_dict()


@pytest.mark.parametrize('slot', ['grain', 'year'])
def test_metric_answer_does_not_resolve_an_independent_missing_slot(slot):
    catalog = host('workshop', 'original')[0]; fact = catalog.datasets[0]
    metrics = tuple(replace(m, selection_terms=(*m.selection_terms, 'Volume'))
                    if m.id in {'billed', 'jobs_count'} else m for m in fact.metrics)
    catalog = replace(catalog, datasets=(replace(fact, metrics=metrics),))
    text = 'Volume in July 2026; without daily grouping.' if slot == 'grain' else 'Volume in July.'
    e = request_evidence((Message('user', text),), catalog)
    q = evidence_question(e, 'en'); assert e.missing == 'measure' and q is not None
    history = (Message('user', text), Message('assistant', q.question), Message('user', 'I mean Completed jobs.'))
    e = request_evidence(history, catalog)
    assert e.metrics == (('jobs', 'jobs_count'),) and e.missing == ('grouping' if slot == 'grain' else 'year')
    q = evidence_question(e, 'en')
    question = q.question if q else 'Which year for July?'
    answer = 'period totals' if slot == 'grain' else '2026.'
    final = request_evidence((*history, Message('assistant', question), Message('user', answer)), catalog)
    assert not final.missing and final.metrics == e.metrics
    assert final.period == PeriodSelection('month', year=2026, month=7)


def test_grouping_answer_keeps_both_comparison_periods():
    catalog = host('workshop', 'original')[0]
    text = 'Billed amount for July 2026 compared with June 2026; without daily grouping.'
    e = request_evidence((Message('user', text),), catalog)
    q = evidence_question(e, 'en'); assert q is not None
    final = request_evidence((Message('user', text), Message('assistant', q.question), Message('user', 'period totals')), catalog)
    assert not final.missing and final.time_grain == 'none'
    assert final.period == PeriodSelection('month', year=2026, month=7)
    assert final.comparison == PeriodSelection('month', year=2026, month=6)


def test_explicit_sort_answer_resolves_only_target_and_preserves_original_limit():
    from evaluations.phase07 import load_cases
    c = load_cases(case_ids=['A12'])[0]; catalog = host(c['domain'], c['host_version'])[0]
    first = request_evidence((Message('user', c['turns'][0]['request']),), catalog)
    q = evidence_question(first, 'en'); assert q is not None
    final = request_evidence((Message('user', c['turns'][0]['request']), Message('assistant', q.question),
                              Message('user', c['turns'][1]['request'])), catalog)
    assert not final.missing and final.ordering.target == 'jobs_count'
    assert final.ordering.descending is True and final.ordering.limit == 2


@pytest.mark.parametrize('kind', ['owner', 'sort', 'year'])
def test_confirmation_question_cannot_publish_a_custom_report(tmp_path, kind):
    from evaluations.runner import extracted
    if kind == 'owner':
        c = original('A11'); desired = target_spec(c, c['turns'][-1])
        text = 'Is Channel = Online correct?'
        proposed = replace(desired, filters=(UserFilter('channel_filter', 'eq', ('Online correct',)),))
    elif kind == 'sort':
        from evaluations.phase07 import load_cases
        c = load_cases(case_ids=['A12'])[0]; desired = target_spec(c, c['turns'][-1])
        text = 'Should I sort by Completed jobs, highest first?'; proposed = desired
    else:
        c = original('A04'); desired = target_spec(c, c['turns'][1])
        text = 'Is September 2026 correct?'; proposed = desired
    responses = [extracted(desired, period=None, missing=('year',)),
        {'status': 'needs_clarification', 'spec': None, 'question': 'Which year for September?', 'message': ''},
        {'approved': True, 'feedback': ''}]
    bundle = factory(tmp_path, desired, domain=c['domain'], profile=c['host_version'], responses=responses)
    first = submit(bundle.engine, c['turns'][0]['request'])
    assert first.status == 'needs_clarification'
    bundle.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', proposed))
    bundle.engine = reopen(bundle)
    reply = submit(bundle.engine, text, session=first.session_id, request='question', revision=first.revision)
    assert reply.status == 'blocked' and not bundle.adapter.calls


def test_one_question_clause_does_not_cancel_an_independent_affirmative_owner_answer():
    e = ledger('A03', answer='Is Service correct? I mean Channel.')
    assert e.filter_requirements[0].condition == UserFilter('channel_filter', 'eq', ('Web',))
    assert e.missing == 'year'


def test_owner_and_separate_year_clause_can_supply_two_missing_details():
    e = ledger('A03', answer='Use Channel; the year is 2026.')
    assert not e.missing
    assert e.period == PeriodSelection('month', year=2026, month=7)
    assert e.filter_requirements[0].condition == UserFilter('channel_filter', 'eq', ('Web',))


def test_additional_limit_instruction_in_sort_answer_is_not_discarded():
    from evaluations.phase07 import load_cases
    c = load_cases(case_ids=['A12'])[0]; catalog = host(c['domain'], c['host_version'])[0]
    e = request_evidence((Message('user', c['turns'][0]['request']),), catalog)
    q = evidence_question(e, 'en')
    final = request_evidence((Message('user', c['turns'][0]['request']), Message('assistant', q.question),
                              Message('user', 'Sort by Completed jobs, highest first, top 3.')), catalog)
    assert not final.missing and final.ordering.limit == 3


@pytest.mark.parametrize('extra', ['', '; also include Work minutes'])
def test_metric_choice_keeps_other_independently_requested_metrics(extra):
    catalog = host('workshop', 'original')[0]; fact = catalog.datasets[0]
    catalog = replace(catalog, datasets=(replace(fact, metrics=tuple(
        replace(m, selection_terms=(*m.selection_terms, 'Volume')) if m.id in {'billed', 'jobs_count'} else m
        for m in fact.metrics)),))
    text = 'Billed amount and Volume in July 2026.'
    e = request_evidence((Message('user', text),), catalog); q = evidence_question(e, 'en')
    answer = 'I mean Completed jobs' + extra + '.'
    final = request_evidence((Message('user', text), Message('assistant', q.question), Message('user', answer)), catalog)
    required = {('jobs', 'billed'), ('jobs', 'jobs_count')} | ({('jobs', 'minutes_total')} if extra else set())
    assert not final.missing and set(final.metrics) == required


@pytest.mark.parametrize('store_kind', ['memory', 'sqlite'])
def test_metric_answer_does_not_authorize_unrequested_extra_metric(tmp_path, store_kind):
    catalog = host('workshop', 'original')[0]; fact = catalog.datasets[0]
    catalog = replace(catalog, datasets=(replace(fact, metrics=tuple(
        replace(m, selection_terms=(*m.selection_terms, 'Volume')) if m.id in {'billed', 'jobs_count'} else m
        for m in fact.metrics)),))
    desired = ReportSpec('jobs', ('jobs_count',), period=PeriodSelection('month', year=2026, month=7))
    bundle = factory(tmp_path, desired, catalog=catalog, profile='original', store_kind=store_kind)
    first = submit(bundle.engine, 'Volume in July 2026.')
    assert first.status == 'needs_clarification'
    bundle.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', replace(desired, metric_ids=('billed', 'jobs_count'))))
    bundle.engine = reopen(bundle)
    final = submit(bundle.engine, 'I mean Completed jobs.', session=first.session_id, request='extra', revision=first.revision)
    assert final.status == 'blocked' and not bundle.adapter.calls


@pytest.mark.parametrize('store_kind', ['memory', 'sqlite'])
@pytest.mark.parametrize('persistent', [False, True])
def test_wrong_intent_and_planner_cannot_override_replacement_even_with_approving_reviewer(tmp_path, store_kind, persistent):
    from evaluations.runner import extracted, ready
    from evaluations.phase03_hosts import ACTOR
    c = original('A06'); initial = target_spec(c, c['turns'][0]); desired = target_spec(c, c['turns'][1])
    wrong = replace(desired, metric_ids=('billed', 'jobs_count'), filters=(),
                    period=PeriodSelection('month', year=2026, month=6))
    approved = {'approved': True, 'feedback': ''}
    replies = [extracted(initial, turn_kind='new'), ready(initial), approved,
               extracted(wrong, turn_kind='refine'), ready(wrong), ready(wrong if persistent else desired), approved]
    bundle = factory(tmp_path, initial, profile=c['host_version'], store_kind=store_kind, responses=replies)
    first = submit(bundle.engine, c['turns'][0]['request']); assert first.status == 'report_ready'
    bundle.engine = reopen(bundle)
    final = submit(bundle.engine, c['turns'][1]['request'], session=first.session_id, request='replace', revision=first.revision)
    if persistent:
        assert final.status == 'blocked' and len(bundle.adapter.calls) == 1
        assert bundle.engine.get_report(first.session_id, first.report.id, ACTOR).to_dict() == first.report.to_dict()
    else:
        assert_report(final, bundle, desired, truncated=True)
        assert len(bundle.adapter.calls) == 2
    stages = [call['response_format']['json_schema']['name'] for call in bundle.client.calls]
    # Invalid proposals are intercepted before the always-approving review can
    # give them authority. No database operation is retried.
    assert stages.count('sageql_report_interpretation') == 3
    assert stages.count('sageql_report_review') == (1 if persistent else 2)
