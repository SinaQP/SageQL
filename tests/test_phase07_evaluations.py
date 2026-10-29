"""Corpus binding and promotion checks; no model understanding is inferred."""
from hashlib import sha256
from dataclasses import replace
import json
from pathlib import Path
import socket
import sys
from types import SimpleNamespace

import pytest

from evaluations import phase06, phase07


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError('Network forbidden in Phase 07 evaluation tests')
    monkeypatch.setattr(socket.socket, 'connect', reject)
    monkeypatch.setattr(socket.socket, 'connect_ex', reject)
    monkeypatch.setattr(socket, 'create_connection', reject)


def test_phase06_default_configuration_keeps_original_keys_and_corpus_binding():
    cases = phase06.load_cases(case_ids=['L01'])
    default = phase06.configuration(cases, 'offline', None, None)
    explicit = phase06.configuration(cases, 'offline', None, None,
                                     corpus_root=phase06.ROOT, corpus_version='v4')
    assert set(default) == {
        'mode', 'adapter', 'endpoint', 'model', 'case_ids', 'selection_sha256',
        'corpus_sha256', 'freeze_sha256', 'source_sha256', 'evaluator_sha256',
    }
    for key in ('case_ids', 'selection_sha256', 'corpus_sha256', 'freeze_sha256'):
        assert default[key] == explicit[key]
    assert default['corpus_sha256'] == sha256((phase06.ROOT / 'cases.v4.json').read_bytes()).hexdigest()
    assert default['freeze_sha256'] == sha256((phase06.ROOT / 'freeze.v4.json').read_bytes()).hexdigest()


def test_configuration_uses_the_requested_root_and_version(tmp_path):
    cases = phase07.load_cases(case_ids=['L26'])
    (tmp_path / 'cases.v9.json').write_text('{"fixture":"distinct corpus"}\n', encoding='utf-8')
    (tmp_path / 'freeze.v9.json').write_text('{"fixture":"distinct freeze"}\n', encoding='utf-8')
    config = phase06.configuration(cases, 'offline', None, None,
                                   corpus_root=str(tmp_path), corpus_version='v9')
    assert config['corpus_sha256'] == sha256((tmp_path / 'cases.v9.json').read_bytes()).hexdigest()
    assert config['freeze_sha256'] == sha256((tmp_path / 'freeze.v9.json').read_bytes()).hexdigest()
    assert config['corpus_sha256'] != sha256((phase06.ROOT / 'cases.v4.json').read_bytes()).hexdigest()


def test_l26_promotion_preserves_original_requests_and_expected_results():
    original = phase06.load_cases(case_ids=['L26'])[0]
    promoted = phase07.load_cases(case_ids=['L26'])[0]
    assert original['cohort'] == 'phase06_assessment'
    assert promoted['cohort'] == 'phase07_development'
    assert promoted['turns'] == original['turns']
    assert promoted['live_eligible'] is False
    assert promoted['origin']['corpus'] == 'evaluations/phase06/cases.v4.json'
    metadata = json.loads((phase07.ROOT / f'cases.{phase07.VERSION}.json').read_text(encoding='utf-8'))
    promotion = next(item for item in metadata['promotions'] if item['id'] == 'L26')
    assert promotion['source_case_sha256'] == sha256(
        json.dumps(original, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def test_independent_replacement_is_frozen_and_not_the_original_question():
    corpus = json.loads((phase07.ROOT / f'cases.{phase07.VERSION}.json').read_text(encoding='utf-8'))
    replacement = next(c for c in phase07.load_cases('assessment')
                       if c['id'] == corpus['replacement']['id'])
    original = phase06.load_cases(case_ids=['L26'])[0]
    assert corpus['replacement']['for'] == 'L26'
    assert replacement['domain'] != original['domain']
    assert replacement['turns'][0]['request'] != original['turns'][0]['request']
    assert replacement['live_eligible'] is True
    freeze = json.loads((phase07.ROOT / f'freeze.{phase07.VERSION}.json').read_text(encoding='utf-8'))
    original_freeze = json.loads((phase07.ROOT / 'freeze.v1.json').read_text(encoding='utf-8'))
    assert original_freeze['frozen_before_phase07_sdk_repair'] is True
    if phase07.VERSION != 'v1':
        assert freeze['frozen_before_phase07_sdk_repair'] is False
        assert freeze['files']['evaluations/phase07/cases.v1.json'] == original_freeze['files'][
            'evaluations/phase07/cases.v1.json']
    assert freeze['live_exposure'] == 'none'
    for name, expected in freeze['files'].items():
        assert sha256(Path(name).read_bytes()).hexdigest() == expected, name


def test_phase07_offline_run_uses_new_hashes_without_constructing_a_live_client(tmp_path, monkeypatch):
    def forbidden_client(*args, **kwargs):
        raise AssertionError('Offline runs must not construct a live client')
    monkeypatch.setitem(sys.modules, 'openai', SimpleNamespace(OpenAI=forbidden_client))
    cases = phase07.load_cases(case_ids=['L26'])
    result = phase07.run(cases, tmp_path)
    assert result['mode'] == 'offline'
    assert result['live_model_status'] == 'not_executed'
    assert result['budget_accounting'] is None
    assert result['configuration']['corpus_sha256'] == sha256(
        (phase07.ROOT / f'cases.{phase07.VERSION}.json').read_bytes()).hexdigest()
    assert result['configuration']['freeze_sha256'] == sha256(
        (phase07.ROOT / f'freeze.{phase07.VERSION}.json').read_bytes()).hexdigest()
    journal = json.loads((tmp_path / 'journal.json').read_text(encoding='utf-8'))
    assert journal['manifest']['corpus_sha256'] == result['configuration']['corpus_sha256']
    assert 'corpus_root' not in journal['manifest']


def test_changed_corpus_binding_cannot_resume_an_existing_run(tmp_path):
    cases = phase07.load_cases(case_ids=['L26'])
    output = tmp_path / 'run'
    first = phase07.run(cases, output, max_cases=0)
    saved = (output / 'journal.json').read_bytes()
    other = tmp_path / 'other'
    other.mkdir()
    (other / 'cases.v9.json').write_text('{"different":true}\n', encoding='utf-8')
    (other / 'freeze.v9.json').write_text('{"version":9}\n', encoding='utf-8')
    with pytest.raises(ValueError, match='Resume configuration'):
        phase06.run(cases, output, resume=True, corpus_root=other, corpus_version='v9')
    assert (output / 'journal.json').read_bytes() == saved
    assert first['unexecuted_trajectories'] == 1


def _review_bundle(tmp_path, desired, *, catalog=None, policy=None):
    from sageql import LLMConfig
    from sageql.sdk import InMemorySessionStore, OpenAIReportAgent, SageQL
    from evaluations.phase03_hosts import ACTOR, TODAY
    from evaluations.phase05_hosts import host
    from evaluations.runner import RecordingAdapter, ScriptedClient
    registered, standard_policy, create = host('workshop', 'workshop-ambiguous-v1')
    path = tmp_path / 'review-facts.sqlite'
    create(path)
    adapter = RecordingAdapter(path)
    provider = OpenAIReportAgent(LLMConfig('synthetic', 'https://example.test/v1', 'fake'),
                                 client=ScriptedClient([]), language='en')
    engine = SageQL(catalog=catalog or registered, database=adapter, policy=policy or standard_policy,
                    provider=provider, sessions=InMemorySessionStore(), clock=lambda: TODAY,
                    execution='validated', language='en')
    session = engine.create_session(ACTOR)
    return SimpleNamespace(engine=engine, adapter=adapter, actor=ACTOR,
                           session=session.session_id, desired=desired)


def _review_first(bundle, request):
    first = bundle.engine.submit(bundle.session, request, bundle.actor, 'initial', 0)
    assert first.status == 'needs_clarification' and not bundle.adapter.calls
    return first


def _review_answer_with_custom_provider(bundle, first, answer):
    from sageql.sdk import Interpretation
    bundle.engine.provider = SimpleNamespace(interpret=lambda *args: Interpretation('ready', bundle.desired))
    return bundle.engine.submit(bundle.session, answer, bundle.actor, 'answer', first.revision)


@pytest.mark.parametrize('question', [
    'Should I start a new report?',
    'If I start a new report, what happens?',
])
def test_question_about_new_report_is_not_an_instruction_to_reset_pending_context(tmp_path, question):
    from sageql.sdk import PeriodSelection, ReportSpec
    desired = ReportSpec('jobs', ('jobs_count',), period=PeriodSelection('month', year=2026, month=6))
    bundle = _review_bundle(tmp_path, desired)
    first = _review_first(bundle, 'For July 2026 show Billed amount by Service for Portal only.')
    reply = _review_answer_with_custom_provider(bundle, first, question)
    assert reply.status in {'blocked', 'needs_clarification'}
    assert not bundle.adapter.calls


@pytest.mark.parametrize('answer', ['I mean no', 'Please use no'])
def test_negative_answer_does_not_become_a_literal_after_removing_wrapper(tmp_path, answer):
    from sageql.sdk import PeriodSelection, ReportSpec, UserFilter
    desired = ReportSpec('jobs', ('billed',), dimension_ids=('service',),
                         filters=(UserFilter('channel_filter', 'eq', ('no',)),),
                         period=PeriodSelection('month', year=2026, month=7))
    bundle = _review_bundle(tmp_path, desired)
    first = _review_first(bundle, 'Billed amount by Service in July 2026; Channel =')
    reply = _review_answer_with_custom_provider(bundle, first, answer)
    assert reply.status in {'blocked', 'needs_clarification'}
    assert not bundle.adapter.calls


def test_ordering_choice_does_not_prioritize_metric_alias_over_equal_dimension_label(tmp_path):
    from sageql.sdk import PeriodSelection, ReportSpec
    from evaluations.phase05_hosts import host
    catalog = host('workshop', 'original')[0]
    fact = catalog.datasets[0]
    catalog = replace(catalog, datasets=(replace(fact,
        metrics=tuple(replace(m, selection_terms=(*m.selection_terms, 'Score')) if m.id == 'billed' else m
                      for m in fact.metrics),
        dimensions=tuple(replace(d, label='Score') if d.id == 'service' else d for d in fact.dimensions)),))
    desired = ReportSpec('jobs', ('billed', 'jobs_count'), dimension_ids=('service',),
                         period=PeriodSelection('month', year=2026, month=7),
                         order_by='billed', descending=True)
    bundle = _review_bundle(tmp_path, desired, catalog=catalog)
    first = _review_first(bundle, 'Billed amount and Completed jobs by Score in July 2026; highest first.')
    reply = _review_answer_with_custom_provider(bundle, first, 'I mean Score.')
    assert reply.status in {'blocked', 'needs_clarification'}
    assert not bundle.adapter.calls


def test_revoked_answer_owner_cannot_be_replaced_by_another_now_unique_visible_owner(tmp_path):
    from sageql.sdk import PeriodSelection, ReportSpec, UserFilter
    from evaluations.phase05_hosts import host
    _, standard_policy, _ = host('workshop', 'workshop-ambiguous-v1')
    hidden = {'channel': False}
    def policy(actor):
        scope = standard_policy(actor)
        return replace(scope, datasets=(replace(scope.datasets[0],
            filter_ids=('service_filter', 'technician_filter')),)) if hidden['channel'] else scope
    desired = ReportSpec('jobs', ('billed',), dimension_ids=('service',),
                         filters=(UserFilter('service_filter', 'eq', ('Web',)),),
                         period=PeriodSelection('month', year=2026, month=7))
    bundle = _review_bundle(tmp_path, desired, policy=policy)
    first = _review_first(bundle, 'For July 2026 show Billed amount by Service for Portal only.')
    hidden['channel'] = True
    reply = _review_answer_with_custom_provider(bundle, first, 'I mean Channel.')
    assert reply.status in {'blocked', 'needs_clarification'}
    assert not bundle.adapter.calls
