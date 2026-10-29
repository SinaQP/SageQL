"""Focused readiness checks, never a substitute for real-model measurements."""
import json
import socket

import pytest

from evaluations import phase08
from evaluations.phase06_runtime import validate_approval
from evaluations.phase05_reference import reference


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError('Network forbidden during preflight tests')
    monkeypatch.setattr(socket.socket, 'connect', forbidden)
    monkeypatch.setattr(socket.socket, 'connect_ex', forbidden)
    monkeypatch.setattr(socket, 'create_connection', forbidden)


def test_frozen_focused_population_and_separate_local_answer_keys():
    cases = phase08.load_cases()
    assert len(cases) == 14 and sum(len(c['turns']) for c in cases) == 23
    assert len(phase08.load_cases('pilot')) == 2
    assert len(phase08.load_cases('assessment')) == 12
    assert sum(t['expect']['kind'] == 'report' for c in cases for t in c['turns']) == 16
    questions = json.loads((phase08.ROOT / f'cases.{phase08.VERSION}.json').read_text(encoding='utf-8'))
    for c in questions['cases']:
        assert c['live_eligible'] and all('spec' not in t and 'expect' not in t for t in c['turns'])
    assert {c['domain'] for c in cases} == {'retail', 'library', 'workshop'}


def test_comparison_expectation_uses_the_existing_reference_once():
    c = phase08.load_cases(case_ids=['A07'])[0]
    t = c['turns'][0]
    assert t['expect'] == reference(c['domain'], t['spec'], ['2026-07-01', '2026-08-01'])
    assert t['expect']['fields'] == ['period_label', 'billed']


@pytest.mark.parametrize('cohort,requests,cost', [('pilot', 12, '0.25'), ('assessment', 120, '1.00')])
def test_disabled_draft_rejects_before_client_or_output_creation(tmp_path, cohort, requests, cost):
    cases = phase08.load_cases(cohort)
    out = tmp_path / 'never-created'
    value = phase08.draft(cases, out, 'https://api.avalai.ir/v1', 'gpt-5-nano')
    assert value['authorized'] is False and value['pricing']['reviewed'] is False
    assert value['accounting']['reviewed'] is False
    assert value['max_requests'] == requests and value['max_cost_usd'] == cost
    def forbidden():
        raise AssertionError('No client before exact approval')
    with pytest.raises(ValueError):
        phase08.run(cases, out, mode='live', endpoint='https://api.avalai.ir/v1', model='gpt-5-nano',
                    approval=value, live_client_factory=forbidden)
    assert not out.exists()


def test_boolean_authorization_alone_cannot_bypass_pricing_and_accounting_review(tmp_path):
    value = phase08.draft(phase08.load_cases('pilot'), tmp_path, 'https://api.avalai.ir/v1', 'gpt-5-nano')
    value.update(authorized=True, authorization_id='TEST_ONLY_NEVER_AN_APPROVAL')
    with pytest.raises(ValueError, match='pricing'):
        validate_approval(value, value['configuration'], tmp_path)


@pytest.mark.parametrize('change', [dict(accepted_specification_incorrect=True),
                                    dict(goal='denial', database_calls=1),
                                    dict(checks={'payload_isolation': False}),
                                    dict(status='report_ready', outcome='incomplete')])
def test_safety_hook_stops_on_measured_violations(change):
    turn = dict(accepted_specification_incorrect=False, goal='report', database_calls=1,
                checks={'payload_isolation': True})
    turn.update(change)
    with pytest.raises(RuntimeError):
        phase08.safety_check(turn)


def test_original_report_goal_is_not_reclassified_after_offline_failure():
    a = phase08.load_cases(case_ids=['A04'])[0]
    assert [t['expect']['kind'] for t in a['turns']] == ['clarification', 'report', 'report']
    first = json.loads((phase08.ROOT / 'contract-check-first.v1.json').read_text())
    assert 'A04' in first['summary']['failing_trajectories']
    assert first['mode'] == 'offline' and first['live_model_status'] == 'not_executed'
