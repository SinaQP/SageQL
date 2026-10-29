"""Clarification resolves its target while preserving independent user evidence."""
from dataclasses import replace
from decimal import Decimal
import socket
from types import SimpleNamespace

import pytest

from sageql import LLMConfig, Message
from sageql.sdk import (InMemorySessionStore, Interpretation, OpenAIReportAgent,
    PeriodSelection, ReportSpec, SageQL, SQLiteSessionStore, UserFilter)
from sageql.sdk.evidence import evidence_question, request_evidence
from sageql.sdk.semantics import permitted_catalog
from evaluations.phase03_hosts import ACTOR, TODAY
from evaluations.phase05_hosts import host
from evaluations.phase05_reference import reference
from evaluations.runner import RecordingAdapter, ScriptedClient, extracted, ready
from evaluations.scoring import rows_match


L26_REQUEST = 'For July 2026 show Billed amount by Service for Portal only.'
APPROVED = {'approved': True, 'feedback': ''}


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError('No external requests are authorized in Phase 07 tests')
    monkeypatch.setattr(socket.socket, 'connect', reject)
    monkeypatch.setattr(socket.socket, 'connect_ex', reject)
    monkeypatch.setattr(socket, 'create_connection', reject)


def target(**changes):
    return replace(ReportSpec('jobs', ('billed',), dimension_ids=('service',),
        filters=(UserFilter('channel_filter', 'eq', ('Web',)),),
        period=PeriodSelection('month', year=2026, month=7)), **changes)


def clarified(answer, *, original=L26_REQUEST, catalog=None, current=None):
    catalog = catalog or host('workshop', 'workshop-ambiguous-v1')[0]
    prior = request_evidence((Message('user', original),), catalog, current)
    question = evidence_question(prior, 'en')
    assert question is not None
    return request_evidence((Message('user', original), Message('assistant', question.question),
                             Message('user', answer)), catalog, current)


def factory(tmp_path, desired, *, domain='workshop', profile='workshop-ambiguous-v1',
            store_kind='sqlite', catalog=None, policy=None, responses=None):
    registered, standard_policy, create = host(domain, profile)
    path = tmp_path / 'facts.sqlite'
    create(path)
    adapter = RecordingAdapter(path)
    client = ScriptedClient(responses if responses is not None else
        [extracted(desired, turn_kind='answer'), ready(desired), APPROVED])
    provider = OpenAIReportAgent(LLMConfig('synthetic', 'https://example.test/v1', 'fake'),
                                 client=client, language='en')
    store_path = tmp_path / 'sessions.sqlite'
    store = InMemorySessionStore() if store_kind == 'memory' else SQLiteSessionStore(store_path)
    bundle = SimpleNamespace(catalog=catalog or registered, policy=policy or standard_policy,
        adapter=adapter, client=client, provider=provider, store=store,
        store_path=store_path, store_kind=store_kind)
    bundle.engine = reopen(bundle)
    return bundle


def reopen(bundle):
    if bundle.store_kind == 'sqlite':
        bundle.store = SQLiteSessionStore(bundle.store_path)
    return SageQL(catalog=bundle.catalog, database=bundle.adapter, policy=bundle.policy,
        provider=bundle.provider, sessions=bundle.store, clock=lambda: TODAY,
        execution='validated', language='en')


def submit(engine, text, *, session=None, request='first', revision=0):
    session = session or engine.create_session(ACTOR).session_id
    return engine.submit(session, text, ACTOR, request, revision)


def assert_report(reply, bundle, desired, domain='workshop', bounds=None, *, truncated=False):
    assert reply.status == 'report_ready', reply.to_dict()
    actual_spec = bundle.adapter.calls[-1].spec
    # A resolved range and its explicitly named month have the same user
    # semantics; provenance below checks the actual executed boundaries.
    assert replace(actual_spec, period=desired.period, comparison=desired.comparison) == desired
    bounds = bounds or ['2026-07-01', '2026-08-01']
    expected = reference(domain, desired.to_dict(), bounds)
    public = reply.report.to_dict()
    assert [field['id'] for field in public['fields']] == expected['fields']
    assert [field['type'] for field in public['fields']] == expected['types']
    assert rows_match(public['fields'], public['rows'], expected['rows'])
    assert public['visualization'] == expected['visualization']
    assert public['truncated'] is truncated
    assert [public['provenance']['period_start'], public['provenance']['period_end_exclusive']] == bounds


@pytest.mark.parametrize('original', [
    L26_REQUEST,
    'For July 2026, show Billed amount by Service for Portal only.',
    'Show Billed amount by Service for Portal only in July 2026.',
    'For July 2026 show Billed amount by Service; include only Portal.',
])
def test_initial_pending_literal_cannot_swallow_date_metric_or_group(original):
    catalog = host('workshop', 'workshop-ambiguous-v1')[0]
    evidence = request_evidence((Message('user', original),), catalog)
    assert evidence.missing == 'filter_value'
    assert evidence.pending_filter_value == ('Portal', 'eq')
    assert evidence.period == PeriodSelection('month', year=2026, month=7)
    assert evidence.metrics == (('jobs', 'billed'),)
    assert evidence.dimensions == (('jobs', 'service'),)


@pytest.mark.parametrize('answer', [
    'Channel', 'Use Channel', 'I mean Channel.', 'The Channel filter',
    'Please use Channel.', 'منظورم Channel است', 'فیلتر Channel',
])
def test_confirmed_owner_answer_preserves_the_original_typed_requirements(answer):
    evidence = clarified(answer)
    assert not evidence.missing
    assert evidence.metrics == (('jobs', 'billed'),)
    assert evidence.dimensions == (('jobs', 'service'),)
    assert evidence.period == PeriodSelection('month', year=2026, month=7)
    assert evidence.filter_requirements[0].condition == UserFilter('channel_filter', 'eq', ('Web',))


def test_persian_registered_owner_label_and_correction_are_not_domain_specific():
    catalog = host('workshop', 'workshop-ambiguous-v1')[0]
    fact = catalog.datasets[0]
    catalog = replace(catalog, datasets=(replace(fact, filters=tuple(
        replace(item, label='کانال') if item.id == 'channel_filter' else item
        for item in fact.filters)),))
    evidence = clarified('منظورم فیلتر کانال است', catalog=catalog)
    assert not evidence.missing
    assert evidence.filter_requirements[0].condition == UserFilter('channel_filter', 'eq', ('Web',))
    assert evidence.period == PeriodSelection('month', year=2026, month=7)


@pytest.mark.parametrize('answer', [
    'Not Channel', 'Is Channel correct?', 'Use Channel?', '"Channel"',
    'Example: Channel', 'Channel and Service', 'Carrier', 'hello', 'نه Channel',
])
def test_unconfirmed_negative_ambiguous_or_unrelated_owner_is_not_a_selection(answer):
    evidence = clarified(answer)
    assert evidence.missing == 'filter_value'
    assert not evidence.filter_requirements
    assert evidence.pending_filter_value == ('Portal', 'eq')
    assert evidence.metrics == (('jobs', 'billed'),)
    assert evidence.period == PeriodSelection('month', year=2026, month=7)


def test_owner_exclusion_is_not_an_exclusion_of_the_original_service_group():
    evidence = clarified('I mean Channel, not Service.')
    assert not evidence.missing
    assert evidence.filter_requirements[0].condition == UserFilter('channel_filter', 'eq', ('Web',))
    assert evidence.dimensions == (('jobs', 'service'),)
    assert ('jobs', 'service') not in evidence.excluded_dimensions


def test_other_predicate_comparison_order_limit_and_grain_exclusion_survive_owner_answer():
    original = ('Compare Billed amount by Service for Portal only in July 2026 with June 2026; '
                'Technician = T2; highest Billed amount first; top 2; not daily.')
    evidence = clarified('I mean Channel.', original=original)
    assert not evidence.missing
    assert evidence.period == PeriodSelection('month', year=2026, month=7)
    assert evidence.comparison == PeriodSelection('month', year=2026, month=6)
    assert {r.condition for r in evidence.filter_requirements} == {
        UserFilter('channel_filter', 'eq', ('Web',)), UserFilter('technician_filter', 'eq', ('T2',))}
    assert evidence.ordering.target == 'billed' and evidence.ordering.descending
    assert evidence.ordering.limit == 2 and 'day' in evidence.forbidden_grains


@pytest.mark.parametrize('domain,profile,metric,label,identifier,empty', [
    ('retail', 'retail-values-v1', 'revenue', 'Department', 'department_filter', None),
    ('library', 'library-values-v1', 'borrowings', 'Shelf', 'shelf_filter', 0),
])
def test_unregistered_free_form_literal_owner_continues_in_independent_domains(
        tmp_path, domain, profile, metric, label, identifier, empty):
    dataset = 'sales' if domain == 'retail' else 'loans'
    desired = ReportSpec(dataset, (metric,), filters=(UserFilter(identifier, 'eq', ('Unlisted',)),),
                         period=PeriodSelection('month', year=2026, month=9))
    bundle = factory(tmp_path, desired, domain=domain, profile=profile)
    request = ('Net sales' if domain == 'retail' else 'Borrowings') + ' for Unlisted only in September 2026.'
    first = submit(bundle.engine, request)
    assert first.status == 'needs_clarification' and not bundle.adapter.calls
    final = submit(bundle.engine, 'I mean ' + label + '.', session=first.session_id,
                   request='answer', revision=first.revision)
    assert_report(final, bundle, desired, domain, ['2026-09-01', '2026-10-01'])
    assert final.report.rows == ((empty,),)


@pytest.mark.parametrize('answer,value', [
    ('I mean "Web"', 'Web'), ('"I mean Web"', 'I mean Web'),
    ('"  MiXeD  ك  "', '  MiXeD  ك  '),
])
def test_missing_filter_value_distinguishes_a_wrapper_from_quoted_data(answer, value):
    evidence = clarified(answer, original='Billed amount in July 2026; Channel equals')
    assert not evidence.missing
    assert evidence.filter_requirements[0].condition == UserFilter('channel_filter', 'eq', (value,))
    assert evidence.metrics == (('jobs', 'billed'),)
    assert evidence.period == PeriodSelection('month', year=2026, month=7)


def test_metric_answer_uses_registered_ambiguity_and_keeps_original_date():
    catalog = host('workshop', 'workshop-values-v1')[0]
    fact = catalog.datasets[0]
    catalog = replace(catalog, datasets=(replace(fact, default_metric_ids=(), metrics=tuple(
        replace(item, selection_terms=(*item.selection_terms, 'Volume'))
        if item.id in {'billed', 'jobs_count'} else item for item in fact.metrics)),))
    evidence = clarified('I mean Completed jobs.', original='Volume in July 2026.', catalog=catalog)
    assert not evidence.missing
    assert evidence.metrics == (('jobs', 'jobs_count'),)
    assert evidence.period == PeriodSelection('month', year=2026, month=7)


def test_grouping_answer_preserves_metric_date_and_explicit_exclusion():
    evidence = clarified('I mean monthly.', original='Billed amount in July 2026, not daily.')
    assert not evidence.missing and evidence.time_grain == 'month'
    assert evidence.metrics == (('jobs', 'billed'),) and 'day' in evidence.forbidden_grains
    assert evidence.period == PeriodSelection('month', year=2026, month=7)


def test_ordering_target_answer_preserves_original_direction_limit_and_date():
    evidence = clarified('I mean Billed amount.', original=(
        'Billed amount and Completed jobs by Service in July 2026; highest first; top 2.'))
    assert not evidence.missing
    assert evidence.ordering.target == 'billed' and evidence.ordering.descending
    assert evidence.ordering.limit == 2
    assert evidence.metrics == (('jobs', 'billed'), ('jobs', 'jobs_count'))
    assert evidence.period == PeriodSelection('month', year=2026, month=7)


@pytest.mark.parametrize('store_kind', ['memory', 'sqlite'])
def test_public_owner_continuation_reopen_exact_results_and_cached_receipt(tmp_path, store_kind):
    desired = target()
    bundle = factory(tmp_path, desired, store_kind=store_kind)
    first = submit(bundle.engine, L26_REQUEST)
    assert first.status == 'needs_clarification' and not bundle.adapter.calls and not bundle.client.calls
    bundle.engine = reopen(bundle)
    answer = submit(bundle.engine, 'I mean Channel.', session=first.session_id,
                    request='answer', revision=first.revision)
    assert_report(answer, bundle, desired)
    calls = len(bundle.client.calls), len(bundle.adapter.calls)
    cached = submit(bundle.engine, 'I mean Channel.', session=first.session_id,
                    request='answer', revision=first.revision)
    assert cached.to_dict() == answer.to_dict()
    assert calls == (len(bundle.client.calls), len(bundle.adapter.calls))
    assert bundle.engine.get_report(first.session_id, answer.report.id, ACTOR).to_dict() == answer.report.to_dict()


@pytest.mark.parametrize('change', ['metric', 'period', 'group', 'owner', 'value', 'direction', 'limit'])
def test_custom_provider_cannot_bypass_resolved_and_retained_requirements(tmp_path, change):
    desired = target(order_by='billed', descending=True, limit=2)
    request = L26_REQUEST + ' Highest Billed amount first; top 2.'
    bundle = factory(tmp_path, desired)
    first = submit(bundle.engine, request)
    assert first.status == 'needs_clarification' and not bundle.adapter.calls
    wrong = {'metric': replace(desired, metric_ids=('jobs_count',), order_by='jobs_count'),
             'period': replace(desired, period=PeriodSelection('month', year=2026, month=6)),
             'group': replace(desired, dimension_ids=()),
             'owner': replace(desired, filters=(UserFilter('service_filter', 'eq', ('Web',)),)),
             'value': replace(desired, filters=(UserFilter('channel_filter', 'eq', ('Desk',)),)),
             'direction': replace(desired, descending=False), 'limit': replace(desired, limit=3)}[change]
    bundle.engine.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', wrong))
    answer = submit(bundle.engine, 'I mean Channel.', session=first.session_id,
                    request='wrong', revision=first.revision)
    assert answer.status == 'blocked' and not bundle.adapter.calls


def test_corrupted_legacy_literal_cannot_authorize_wrong_metric_group_or_period(tmp_path):
    bundle = factory(tmp_path, target())
    first = submit(bundle.engine, L26_REQUEST)
    wrong = ReportSpec('jobs', ('jobs_count',),
        filters=(UserFilter('channel_filter', 'eq', ('July 2026 show Billed amount by Service for',)),),
        period=PeriodSelection('month', year=2026, month=6))
    bundle.engine.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', wrong))
    answer = submit(bundle.engine, 'Channel', session=first.session_id,
                    request='wrong', revision=first.revision)
    assert answer.status == 'blocked' and not bundle.adapter.calls


@pytest.mark.parametrize('store_kind', ['memory', 'sqlite'])
def test_failed_answer_preserves_previous_success_pending_context_and_later_valid_answer(tmp_path, store_kind):
    prior = target(dimension_ids=(), filters=())
    desired = target()
    responses = [extracted(prior), ready(prior), APPROVED,
                 extracted(desired, turn_kind='answer'), ready(desired), APPROVED]
    bundle = factory(tmp_path, desired, store_kind=store_kind, responses=responses)
    initial = submit(bundle.engine, 'Billed amount in July 2026.')
    assert_report(initial, bundle, prior)
    pending = submit(bundle.engine, L26_REQUEST, session=initial.session_id,
                     request='pending', revision=initial.revision)
    assert pending.status == 'needs_clarification'
    failed = submit(bundle.engine, 'Is Channel correct?', session=initial.session_id,
                    request='invalid', revision=pending.revision)
    assert failed.status in {'blocked', 'needs_clarification'} and len(bundle.adapter.calls) == 1
    assert bundle.engine.get_session(initial.session_id, ACTOR)['last_report_id'] == initial.report.id
    assert bundle.engine.get_report(initial.session_id, initial.report.id, ACTOR).to_dict() == initial.report.to_dict()
    bundle.engine = reopen(bundle)
    final = submit(bundle.engine, 'I mean Channel.', session=initial.session_id,
                   request='valid', revision=failed.revision)
    assert_report(final, bundle, desired)
    assert len(bundle.adapter.calls) == 2


def test_owner_then_year_are_two_distinct_clarifications(tmp_path):
    desired = target()
    responses = [extracted(desired, turn_kind='answer', period=None, missing=('year',)),
        {'status': 'needs_clarification', 'spec': None, 'question': 'Which year for July?', 'message': ''}, APPROVED,
        extracted(desired, turn_kind='answer'), ready(desired), APPROVED]
    bundle = factory(tmp_path, desired, responses=responses)
    first = submit(bundle.engine, 'Billed amount by Service for Portal only in July.')
    assert first.status == 'needs_clarification'
    second = submit(bundle.engine, 'I mean Channel.', session=first.session_id,
                    request='owner', revision=first.revision)
    assert second.status == 'needs_clarification' and 'year' in second.clarification.casefold()
    bundle.engine = reopen(bundle)
    final = submit(bundle.engine, '2026', session=first.session_id,
                   request='year', revision=second.revision)
    assert_report(final, bundle, desired)


@pytest.mark.parametrize('store_kind', ['memory', 'sqlite'])
def test_explicit_new_report_does_not_continue_the_old_owner_question(tmp_path, store_kind):
    desired = ReportSpec('jobs', ('jobs_count',), period=PeriodSelection('month', year=2026, month=6))
    bundle = factory(tmp_path, desired, store_kind=store_kind,
        responses=[extracted(desired, turn_kind='new'), ready(desired), APPROVED])
    first = submit(bundle.engine, L26_REQUEST)
    assert first.status == 'needs_clarification'
    final = submit(bundle.engine, 'Start a new report: Completed jobs in June 2026.',
                   session=first.session_id, request='new', revision=first.revision)
    assert_report(final, bundle, desired, bounds=['2026-06-01', '2026-07-01'])


@pytest.mark.parametrize('store_kind', ['memory', 'sqlite'])
@pytest.mark.parametrize('stale_field', ['filter', 'ordering', 'limit'])
def test_explicit_new_report_rejects_custom_provider_controls_from_previous_report(tmp_path, store_kind, stale_field):
    prior = target(order_by='billed', descending=True, limit=2)
    fresh = target(dimension_ids=(), filters=(), period=PeriodSelection('month', year=2026, month=6))
    bundle = factory(tmp_path, prior, store_kind=store_kind,
        responses=[extracted(prior), ready(prior), APPROVED])
    initial = submit(bundle.engine,
        'Billed amount by Service in July 2026; Channel = Web; highest Billed amount first; top 2.')
    assert_report(initial, bundle, prior, truncated=True)
    wrong = {'filter': replace(fresh, filters=prior.filters),
             'ordering': replace(fresh, order_by=prior.order_by, descending=prior.descending),
             'limit': replace(fresh, limit=prior.limit)}[stale_field]
    bundle.engine.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', wrong))
    final = submit(bundle.engine, 'Start a new report: Billed amount in June 2026.',
                   session=initial.session_id, request='new', revision=initial.revision)
    assert final.status == 'blocked' and len(bundle.adapter.calls) == 1
    assert bundle.engine.get_session(initial.session_id, ACTOR)['last_report_id'] == initial.report.id


@pytest.mark.parametrize('store_kind', ['memory', 'sqlite'])
def test_explicit_new_report_accepts_custom_provider_without_previous_controls(tmp_path, store_kind):
    prior = target(order_by='billed', descending=True, limit=2)
    fresh = target(dimension_ids=(), filters=(), period=PeriodSelection('month', year=2026, month=6))
    bundle = factory(tmp_path, prior, store_kind=store_kind,
        responses=[extracted(prior), ready(prior), APPROVED])
    initial = submit(bundle.engine,
        'Billed amount by Service in July 2026; Channel = Web; highest Billed amount first; top 2.')
    assert_report(initial, bundle, prior, truncated=True)
    bundle.engine.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', fresh))
    final = submit(bundle.engine, 'Start a new report: Billed amount in June 2026.',
                   session=initial.session_id, request='new', revision=initial.revision)
    assert_report(final, bundle, fresh, bounds=['2026-06-01', '2026-07-01'])
    assert len(bundle.adapter.calls) == 2


@pytest.mark.parametrize('store_kind', ['memory', 'sqlite'])
def test_new_report_reset_survives_clarification_then_allows_normal_refinement(tmp_path, store_kind):
    prior = target(order_by='billed', descending=True, limit=2)
    fresh = target(period=PeriodSelection('month', year=2026, month=6))
    original = 'Start a new report: Billed amount by Service for Portal only in June 2026.'
    evidence = clarified('I mean Channel.', original=original, current=prior)
    assert evidence.new_report and evidence.ordering is None
    bundle = factory(tmp_path, prior, store_kind=store_kind,
        responses=[extracted(prior), ready(prior), APPROVED])
    initial = submit(bundle.engine,
        'Billed amount by Service in July 2026; Channel = Web; highest Billed amount first; top 2.')
    assert_report(initial, bundle, prior, truncated=True)
    pending = submit(bundle.engine, original, session=initial.session_id,
                     request='new', revision=initial.revision)
    assert pending.status == 'needs_clarification' and len(bundle.adapter.calls) == 1
    bundle.engine.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', fresh))
    resolved = submit(bundle.engine, 'I mean Channel.', session=initial.session_id,
                      request='owner', revision=pending.revision)
    assert_report(resolved, bundle, fresh, bounds=['2026-06-01', '2026-07-01'])
    refined = replace(fresh, order_by='billed', descending=True, limit=3)
    bundle.engine.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', refined))
    final = submit(bundle.engine, 'Highest Billed amount first; top 3.', session=initial.session_id,
                   request='refine', revision=resolved.revision)
    assert_report(final, bundle, refined, bounds=['2026-06-01', '2026-07-01'])
    assert len(bundle.adapter.calls) == 3


@pytest.mark.parametrize(('operation', 'identifier'), [
    ('show share of total', 'percentage_share'), ('show an arbitrary formula', 'formula'),
])
def test_resolving_known_filter_does_not_erase_a_separate_unsupported_operation(tmp_path, operation, identifier):
    original = 'Billed amount by Service in July 2026; Channel equals'
    answer = 'Channel = Web; ' + operation
    evidence = clarified(answer, original=original)
    assert evidence.operations == (identifier,)
    assert evidence.filter_requirements[0].condition == target().filters[0]
    bundle = factory(tmp_path, target())
    first = submit(bundle.engine, original)
    assert first.status == 'needs_clarification'
    bundle.engine.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', target()))
    final = submit(bundle.engine, answer, session=first.session_id,
                   request='unsupported', revision=first.revision)
    assert final.status == 'unsupported' and not bundle.adapter.calls


def test_quoted_unsupported_phrase_remains_exact_pending_filter_data(tmp_path):
    original = 'Billed amount by Service in July 2026; Channel equals'
    desired = target(filters=(UserFilter('channel_filter', 'eq', ('share of total',)),))
    evidence = clarified('I mean "share of total".', original=original)
    assert not evidence.operations and not evidence.missing
    assert evidence.filter_requirements[0].condition == desired.filters[0]
    bundle = factory(tmp_path, desired)
    first = submit(bundle.engine, original)
    assert first.status == 'needs_clarification'
    final = submit(bundle.engine, 'I mean "share of total".', session=first.session_id,
                   request='literal', revision=first.revision)
    assert_report(final, bundle, desired)


def test_known_filter_answer_keeps_requirements_in_a_separate_clause():
    evidence = clarified('Channel = Web; include Completed jobs by Service daily.',
                         original='Billed amount in July 2026; Channel equals')
    assert not evidence.missing
    assert evidence.metrics == (('jobs', 'billed'), ('jobs', 'jobs_count'))
    assert evidence.dimensions == (('jobs', 'service'),)
    assert evidence.time_grain == 'day'
    assert evidence.period == PeriodSelection('month', year=2026, month=7)
    assert evidence.filter_requirements[0].condition == target().filters[0]


@pytest.mark.parametrize('store_kind', ['memory', 'sqlite'])
def test_custom_provider_cannot_drop_separate_clause_after_known_filter_answer(tmp_path, store_kind):
    wrong = target(dimension_ids=())
    bundle = factory(tmp_path, wrong, store_kind=store_kind)
    first = submit(bundle.engine, 'Billed amount in July 2026; Channel equals')
    assert first.status == 'needs_clarification' and not bundle.adapter.calls
    bundle.engine = reopen(bundle)
    bundle.engine.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', wrong))
    final = submit(bundle.engine, 'Channel = Web; include Completed jobs by Service daily.',
                   session=first.session_id, request='dropped', revision=first.revision)
    assert final.status == 'blocked' and not bundle.adapter.calls


@pytest.mark.parametrize('store_kind', ['memory', 'sqlite'])
def test_custom_provider_can_fulfill_separate_clause_after_known_filter_answer(tmp_path, store_kind):
    desired = target(metric_ids=('billed', 'jobs_count'), time_grain='day')
    bundle = factory(tmp_path, desired, store_kind=store_kind)
    first = submit(bundle.engine, 'Billed amount in July 2026; Channel equals')
    assert first.status == 'needs_clarification' and not bundle.adapter.calls
    bundle.engine = reopen(bundle)
    bundle.engine.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', desired))
    final = submit(bundle.engine, 'Channel = Web; include Completed jobs by Service daily.',
                   session=first.session_id, request='fulfilled', revision=first.revision)
    assert_report(final, bundle, desired)


def test_revoked_owner_cannot_be_restored_from_pending_text(tmp_path):
    registered, policy, _ = host('workshop', 'workshop-ambiguous-v1')
    restricted = {'value': False}
    def current_policy(actor):
        value = policy(actor)
        return replace(value, datasets=(replace(value.datasets[0],
            filter_ids=('service_filter', 'technician_filter')),)) if restricted['value'] else value
    bundle = factory(tmp_path, target(), policy=current_policy)
    first = submit(bundle.engine, L26_REQUEST)
    restricted['value'] = True
    bundle.engine.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', target()))
    final = submit(bundle.engine, 'I mean Channel.', session=first.session_id,
                   request='hidden', revision=first.revision)
    assert final.status == 'blocked' and not bundle.adapter.calls
    projected = permitted_catalog(registered, current_policy(ACTOR))
    assert 'channel_filter' not in {f.id for d in projected.datasets for f in d.filters}


@pytest.mark.parametrize('store_kind', ['memory', 'sqlite'])
def test_pending_owner_resolves_after_catalog_version_change_and_old_receipt_conflicts(tmp_path, store_kind):
    desired = target()
    bundle = factory(tmp_path, desired, store_kind=store_kind)
    first = submit(bundle.engine, L26_REQUEST)
    assert first.status == 'needs_clarification' and not bundle.adapter.calls and not bundle.client.calls
    bundle.catalog = replace(bundle.catalog, version=bundle.catalog.version + ':next')
    bundle.engine = reopen(bundle)
    replay = submit(bundle.engine, L26_REQUEST, session=first.session_id, request='first', revision=0)
    assert replay.status == 'blocked' and replay.error['code'] == 'request_conflict'
    assert not bundle.adapter.calls and not bundle.client.calls
    answer = submit(bundle.engine, 'I mean Channel.', session=first.session_id,
                    request='current-catalog', revision=first.revision)
    assert_report(answer, bundle, desired)
    assert len(bundle.adapter.calls) == 1


@pytest.mark.parametrize('store_kind', ['memory', 'sqlite'])
def test_pending_owner_revalidates_changed_vocabulary_and_rejects_stale_provider_value(tmp_path, store_kind):
    stale = target()
    current = target(filters=(UserFilter('channel_filter', 'eq', ('Direct',)),))
    bundle = factory(tmp_path, current, store_kind=store_kind)
    first = submit(bundle.engine, L26_REQUEST)
    assert first.status == 'needs_clarification' and not bundle.adapter.calls and not bundle.client.calls
    dataset = bundle.catalog.datasets[0]
    changed_filters = tuple(replace(definition, value_vocabulary=tuple(
        replace(entry, value='Direct', terms=('Direct', 'Portal'))
        if entry.value == 'Web' else entry for entry in definition.value_vocabulary))
        if definition.id == 'channel_filter' else definition for definition in dataset.filters)
    # Metadata itself invalidates receipts, even if the host's version text is
    # unchanged. The original ambiguous literal must use the current meanings.
    bundle.catalog = replace(bundle.catalog, datasets=(replace(dataset, filters=changed_filters),))
    bundle.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', stale))
    bundle.engine = reopen(bundle)
    replay = submit(bundle.engine, L26_REQUEST, session=first.session_id, request='first', revision=0)
    assert replay.status == 'blocked' and replay.error['code'] == 'request_conflict'
    assert not bundle.adapter.calls and not bundle.client.calls
    evidence = clarified('I mean Channel.', catalog=bundle.catalog)
    assert evidence.filter_requirements[0].condition == current.filters[0]
    rejected = submit(bundle.engine, 'I mean Channel.', session=first.session_id,
                      request='stale-value', revision=first.revision)
    assert rejected.status == 'blocked' and not bundle.adapter.calls
    bundle.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', current))
    bundle.engine = reopen(bundle)
    accepted = submit(bundle.engine, 'I mean Channel.', session=first.session_id,
                      request='current-value', revision=rejected.revision)
    assert_report(accepted, bundle, current)
    assert accepted.report.rows == () and len(bundle.adapter.calls) == 1


def test_empty_answer_does_not_erase_the_pending_request(tmp_path):
    bundle = factory(tmp_path, target())
    first = submit(bundle.engine, L26_REQUEST)
    empty = submit(bundle.engine, '   ', session=first.session_id,
                   request='empty', revision=first.revision)
    assert empty.status == 'blocked' and empty.error['code'] == 'invalid_input'
    assert not bundle.adapter.calls and not bundle.client.calls
    final = submit(bundle.engine, 'I mean Channel.', session=first.session_id,
                   request='valid', revision=first.revision)
    assert_report(final, bundle, target())
