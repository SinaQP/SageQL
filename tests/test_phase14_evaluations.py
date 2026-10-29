"""Assessment integrity and no-dispatch gates; actual language quality is unmeasured."""
from copy import deepcopy
import json
from pathlib import Path

import pytest

from evaluations import phase08, phase14
from evaluations.phase05_reference import reference
from evaluations.phase06_runtime import validate_approval


def test_separate_populations_and_exact_denominators():
    old = phase14.load_cases('legacy')
    new = phase14.load_cases()
    assert old == phase08.load_cases('assessment')
    assert len(old) == 12 and sum(len(c['turns']) for c in old) == 21
    assert len(new) == 6 and sum(len(c['turns']) for c in new) == 19
    assert sum(t['expect']['kind'] == 'report' for c in new for t in c['turns']) == 13
    assert {c['domain'] for c in new} == {'retail', 'library', 'workshop'}
    assert not {'P01', 'P02'} & {c['id'] for c in old + new}


def test_author_metadata_correction_preserves_questions_and_all_report_answers():
    root = phase14.ROOT
    first = json.loads((root / 'cases.v1.json').read_text(encoding='utf-8'))
    final = json.loads((root / 'cases.v2.json').read_text(encoding='utf-8'))
    assert first['cases'] == final['cases']
    before = json.loads((root / 'expectations.v1.json').read_text(encoding='utf-8'))
    after = json.loads((root / 'expectations.v2.json').read_text(encoding='utf-8'))
    changed = []
    for old, new in zip(before['cases'], after['cases']):
        for index, (left, right) in enumerate(zip(old['turns'], new['turns'])):
            if left != right:
                changed.append((old['id'], index + 1))
            if left['expect']['kind'] == 'report':
                assert left == right
    assert changed == [('N02', 2), ('N06', 1)]


@pytest.mark.parametrize('case_id', ['N01', 'N02', 'N03', 'N04', 'N05', 'N06'])
def test_new_reports_reuse_independent_arithmetic_not_generated_sql(case_id):
    case = phase14.load_cases(case_ids=[case_id])[0]
    for turn in case['turns']:
        if turn['expect']['kind'] != 'report':
            continue
        month = turn['spec']['period']['month']
        bounds = [f'2026-{month:02}-01', f'2026-{month + 1:02}-01']
        assert turn['expect'] == reference(case['domain'], turn['spec'], bounds)
        assert len(turn['requirements']) == 13


@pytest.mark.parametrize('cohort', ['legacy', 'independent'])
@pytest.mark.parametrize('accounting_mode', ['strict', 'exploratory'])
def test_disabled_scope_never_reads_key_constructs_client_or_creates_output(tmp_path, monkeypatch, cohort, accounting_mode):
    import os
    original = os.environ.get
    key_reads = []
    def guarded(key, *default):
        if key == 'SAGEQL_EVAL_API_KEY':
            key_reads.append(key)
            raise AssertionError('No credential read before authorization')
        return original(key, *default)
    monkeypatch.setattr(os.environ, 'get', guarded)
    cases = phase14.load_cases(cohort)
    directory = tmp_path / 'must-not-exist'
    approval = phase14.draft(cases, directory, 'https://api.avalai.ir/v1', 'gpt-5-nano', accounting_mode=accounting_mode)
    clients = []
    with pytest.raises(ValueError):
        phase14.run(cases, directory, mode='live', approval=approval,
            endpoint='https://api.avalai.ir/v1', model='gpt-5-nano', accounting_mode=accounting_mode,
            live_client_factory=lambda: clients.append(1))
    assert approval['authorized'] is False
    assert clients == key_reads == [] and not directory.exists()
    if accounting_mode == 'exploratory':
        assert approval['accepts_billing_uncertainty'] is False
        assert approval['accounting']['guaranteed_bound'] is False


@pytest.mark.parametrize('cohort', ['legacy', 'independent'])
def test_exact_phase14_scope_has_finite_quality_oriented_limits(tmp_path, cohort):
    approval = phase14.draft(phase14.load_cases(cohort), tmp_path,
                             'https://api.avalai.ir/v1', 'gpt-5-nano', accounting_mode='exploratory')
    assert approval['max_requests'] == 120 and approval['max_seconds'] == 1800
    assert approval['per_call_output_tokens'] == 8192 and approval['max_total_tokens'] == 2983040
    assert approval['max_cost_usd'] == '5.00'
    assert approval['configuration']['case_ids'] == [c['id'] for c in phase14.load_cases(cohort)]


def test_new_freeze_rejects_tampering_before_any_live_work(monkeypatch):
    original = Path.read_bytes
    def tampered(path):
        if path.resolve() == (phase14.ROOT / 'cases.v2.json').resolve():
            return b'changed assessment'
        return original(path)
    monkeypatch.setattr(Path, 'read_bytes', tampered)
    with pytest.raises(ValueError, match='Frozen'):
        phase14.load_cases()


@pytest.mark.parametrize('cohort,identifiers', [('pilot', None), ('independent', ['unknown']), ('legacy', ['P01'])])
def test_unknown_or_completed_pilot_selections_are_rejected(cohort, identifiers):
    with pytest.raises(ValueError):
        phase14.load_cases(cohort, identifiers)


def test_populations_cannot_be_pooled_or_misbound():
    with pytest.raises(ValueError):
        phase14.corpus_for(phase14.load_cases('legacy') + phase14.load_cases())
    with pytest.raises(ValueError):
        phase14.corpus_for([])


def test_draft_cli_remains_disabled_and_wont_overwrite_prior_packet(tmp_path):
    path = tmp_path / 'packet.json'
    args = ['--cohort', 'independent', '--prepare-approval', str(path),
            '--output', str(tmp_path / 'not-created'), '--endpoint', 'https://api.avalai.ir/v1',
            '--model', 'gpt-5-nano', '--accounting-mode', 'exploratory']
    assert phase14.main(args) == 0
    before = path.read_bytes()
    assert phase14.main(args) == 2 and path.read_bytes() == before
    assert not (tmp_path / 'not-created').exists()


def test_new_question_files_never_include_answer_keys():
    value = json.loads((phase14.ROOT / f'cases.{phase14.VERSION}.json').read_text(encoding='utf-8'))
    assert all('spec' not in t and 'expect' not in t and 'requirements' not in t
               for c in value['cases'] for t in c['turns'])
    assert all(c['live_eligible'] for c in value['cases'])


def test_explicit_authorization_does_not_imply_strict_accounting_guarantees(tmp_path):
    approval = phase14.draft(phase14.load_cases(), tmp_path, 'https://api.avalai.ir/v1', 'gpt-5-nano')
    approval.update(authorized=True, authorization_id='UNIT_TEST_ONLY')
    with pytest.raises(ValueError, match='pricing'):
        validate_approval(approval, approval['configuration'], tmp_path)
