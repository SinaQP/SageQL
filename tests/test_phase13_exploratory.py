"""Offline tests of the explicit exploratory option; no real model credentials."""
from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from evaluations.phase06 import approval_template, configuration, load_cases, run
from evaluations.phase06_runtime import Budget, BudgetStopped, Journal, validate_approval
from evaluations.phase06_transport import ObservedClient


def approval_at(directory):
    config = configuration(load_cases(case_ids=['L01']), 'live', 'https://example.test/v1', 'mock-model')
    approval = approval_template(config, directory, accounting_mode='exploratory')
    approval.update(authorized=True, authorization_id='EXPLORATORY_UNIT_TEST_ONLY',
                    accepts_billing_uncertainty=True, capture_responses=True,
                    max_requests=12, max_input_tokens=250000, max_output_tokens=98304,
                    max_total_tokens=348304, max_seconds=600, max_cost_usd='5', per_call_output_tokens=8192)
    approval['pricing'].update(reviewed=True, observed_date='2026-10-27',
        verified_at='2026-10-27T00:00:00+00:00', input_usd_per_million='.05', output_usd_per_million='.4')
    return config, approval


def make_budget(directory):
    config, approval = approval_at(directory)
    validate_approval(approval, config, directory, accounting_mode='exploratory')
    return Budget(approval, Journal(directory, config))


def options():
    return {'model': 'mock-model', 'messages': [{'role': 'user', 'content': '{"request":"Synthetic request"}'}],
            'response_format': {'json_schema': {'name': 'sageql_report_intent'}},
            'max_completion_tokens': 8192, 'timeout': 90}


def test_explicit_mode_required_and_strict_cannot_be_downgraded(tmp_path):
    config, approval = approval_at(tmp_path)
    with pytest.raises(ValueError):
        validate_approval(approval, config, tmp_path)
    validate_approval(approval, config, tmp_path, accounting_mode='exploratory')
    del approval['accounting_mode']
    with pytest.raises(ValueError):
        validate_approval(approval, config, tmp_path, accounting_mode='exploratory')


@pytest.mark.parametrize('section,key,value', [
    (None, 'accepts_billing_uncertainty', False), (None, 'call_timeout_seconds', 0),
    (None, 'turn_timeout_seconds', 601), (None, 'capture_responses', 'yes'),
    (None, 'max_requests', 0), (None, 'max_total_tokens', True), (None, 'max_cost_usd', 'NaN'),
    ('accounting', 'guaranteed_bound', True), ('accounting', 'provider_billing_verified', True),
    ('accounting', 'overhead_tokens', -1), ('pricing', 'reviewed', False),
    ('pricing', 'observed_date', 'invalid')])
def test_invalid_exploratory_manifest_blocks_before_client(tmp_path, section, key, value):
    config, approval = approval_at(tmp_path)
    (approval[section] if section else approval)[key] = value
    clients = []
    with pytest.raises(ValueError):
        run(load_cases(case_ids=['L01']), tmp_path, mode='live', endpoint=config['endpoint'],
            model=config['model'], approval=approval, accounting_mode='exploratory',
            live_client_factory=lambda: clients.append(1))
    assert clients == [] and not (tmp_path / 'journal.json').exists()


def test_exploratory_input_estimate_variance_is_observed_not_guaranteed(tmp_path):
    budget = make_budget(tmp_path)
    ticket = budget.reserve(options())
    estimate = budget.state['calls'][ticket]['estimated_input']
    budget.settle(ticket, {'input': estimate + 100, 'output': 10})
    assert not budget.exhausted
    assert budget.accounting()['input_charged_or_reserved'] == estimate + 100
    assert budget.state['calls'][ticket]['estimated_input'] == estimate
    assert budget.accounting()['provider_billed_usd'] is None


@pytest.mark.parametrize('usage,failed,invalid,reason', [
    (None, False, False, 'missing_usage'), (None, True, False, 'transport_failure'),
    (None, False, True, 'invalid_usage'),
    ({'input': 10, 'output': 8193}, False, False, 'provider_bound_violation'),
    ({'input': 250001, 'output': 10}, False, False, 'input_budget')])
def test_uncontrolled_or_unobservable_consumption_stops(tmp_path, usage, failed, invalid, reason):
    budget = make_budget(tmp_path)
    ticket = budget.reserve(options())
    budget.settle(ticket, usage, failed=failed, invalid=invalid)
    assert budget.exhausted and budget.state['stop_reason'] == reason
    with pytest.raises(BudgetStopped):
        budget.reserve(options())
    assert len(budget.state['calls']) == 1
    if usage is None:
        assert budget.accounting()['output_charged_or_reserved'] == 8192


def test_actual_response_recorded_locally_without_transport_secrets(tmp_path):
    budget = make_budget(tmp_path)
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='{"status":"ready"}'),
        finish_reason='stop')], usage={'prompt_tokens': 100, 'completion_tokens': 20, 'total_tokens': 120},
        headers={'Authorization': 'PRIVATE_KEY'})
    requests = []
    delegate = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(
        create=lambda **kw: requests.append(kw) or response)))
    client = ObservedClient(delegate, budget=budget)
    assert client.create(**options()) is response
    artifact = tmp_path / 'responses/call-0001.json'
    recorded = json.loads(artifact.read_text())
    assert recorded['content'] == response.choices[0].message.content
    assert recorded['usage']['total'] == 120 and len(requests) == 1
    assert 'PRIVATE_KEY' not in artifact.read_text()


def test_response_recording_failure_stops_before_next_dispatch(tmp_path, monkeypatch):
    budget = make_budget(tmp_path)
    ticket = budget.reserve(options())
    response = SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content='x' * 128001),
                                                        finish_reason='stop')])
    with pytest.raises(ValueError):
        budget.capture_response(ticket, response, None)
    assert budget.exhausted
    with pytest.raises(BudgetStopped):
        budget.reserve(options())


def test_changed_exploratory_approval_cannot_resume_first_attempt(tmp_path):
    config, approval = approval_at(tmp_path)
    manifest = {'config': config, 'approval': deepcopy(approval)}
    journal = Journal(tmp_path, manifest)
    budget = Budget(approval, journal)
    budget.reserve(options())
    original = journal.path.read_bytes()
    manifest['approval']['max_requests'] += 1
    with pytest.raises(ValueError):
        Journal(tmp_path, manifest, resume=True)
    assert journal.path.read_bytes() == original


def test_safety_stop_does_not_label_scored_active_case_untouched(tmp_path):
    from evaluations.phase08 import load_cases as phase08_cases, run as run_phase08
    cases = phase08_cases('pilot')
    # Controlled checkpoint stop after a correctly scored turn, no external calls.
    from evaluations.phase06 import run as run_shared
    from evaluations.phase08 import ROOT, VERSION
    def stop(turn):
        raise RuntimeError('LOCAL_TEST_STOP')
    with pytest.raises(RuntimeError):
        run_shared(cases, tmp_path, corpus_root=ROOT, corpus_version=VERSION, turn_hook=stop)
    result = json.loads((tmp_path / 'results.json').read_text())
    assert result['unexecuted_turns'] == 1
    assert result['unexecuted_trajectories'] == 1
    assert result['remaining_untouched_trajectories'] == 1
    assert result['results'][0]['id'] == 'P01' and len(result['results'][0]['turns']) == 1
