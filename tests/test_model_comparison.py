"""Offline checks for the nano/mini comparison runner; no network or credentials."""
from decimal import Decimal
import socket
from types import SimpleNamespace

import pytest

from evaluations import model_comparison as comparison
from evaluations.phase05_hosts import host
from evaluations.phase06 import configuration
from evaluations.phase06_runtime import Budget, BudgetStopped, Journal, validate_approval
from evaluations.phase06_transport import ProtocolClient
from evaluations.phase14 import load_cases
from evaluations.trajectories import target_spec

STAMP = '2026-10-29T10:00:00+03:30'


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
    def reject(*args, **kwargs):
        raise AssertionError('Network forbidden in comparison tests')
    monkeypatch.setattr(socket.socket, 'connect', reject)
    monkeypatch.setattr(socket, 'create_connection', reject)


def packet(tmp_path, setup):
    cases = load_cases('independent', ['N02'])
    return cases, comparison.prepare(cases, tmp_path, setup, 'UNIT_TEST_ONLY', STAMP)


def test_unset_stage_settings_preserve_existing_configuration_keys():
    cases = load_cases('independent', ['N02'])
    config = configuration(cases, 'live', comparison.ENDPOINT, 'gpt-5-nano')
    assert 'stage_models' not in config and 'reasoning_effort' not in config
    with pytest.raises(ValueError):
        configuration(cases, 'offline', None, None, reasoning_effort='low')


@pytest.mark.parametrize('setup', sorted(comparison.SETUPS))
def test_prepared_packets_validate_with_reviewed_rates(tmp_path, setup):
    cases, approval = packet(tmp_path, setup)
    validate_approval(approval, approval['configuration'], tmp_path, accounting_mode='exploratory')
    assert approval['configuration']['model'] == 'gpt-5-nano'
    assert approval['configuration']['reasoning_effort'] == 'low'
    assert ('models' in approval['pricing']) == (setup in ('B', 'C', 'D', 'E'))
    assert approval['configuration'].get('compile_intent', False) == (setup in ('C', 'D', 'E'))
    assert approval['configuration'].get('review', True) == (setup not in ('D', 'E'))
    assert approval['configuration'].get('intent_samples', 1) == (3 if setup == 'E' else 1)
    if setup in ('B', 'C', 'D', 'E'):
        assert approval['configuration']['stage_models'] == {'intent': 'gpt-5-mini'}
        assert approval['pricing']['models']['gpt-5-mini']['output_usd_per_million'] == '2.00'


def test_stage_model_without_reviewed_rate_is_rejected(tmp_path):
    cases, approval = packet(tmp_path, 'B')
    del approval['pricing']['models']
    with pytest.raises(ValueError):
        validate_approval(approval, approval['configuration'], tmp_path, accounting_mode='exploratory')


def test_only_nano_and_mini_are_selectable(monkeypatch):
    monkeypatch.setitem(comparison.SETUPS, 'X', {'stage_models': {'intent': 'gpt-5'}})
    with pytest.raises(ValueError):
        comparison.settings('X')


def test_budget_prices_each_call_by_its_model_and_rejects_others(tmp_path):
    cases, approval = packet(tmp_path, 'B')
    journal = Journal(tmp_path, approval['configuration'])
    budget = Budget(approval, journal)
    request = {'messages': [{'role': 'user', 'content': 'synthetic'}], 'max_completion_tokens': 1000,
               'response_format': {'json_schema': {'name': 'sageql_report_intent'}}}
    usage = {'input': 1_000_000, 'output': 1000, 'total': 1_001_000, 'cached_input': None, 'reasoning': None}
    budget.settle(budget.reserve({**request, 'model': 'gpt-5-mini'}), usage)
    budget.settle(budget.reserve({**request, 'model': 'gpt-5-nano'}), usage)
    calls = budget.state['calls']
    assert [call['model'] for call in calls] == ['gpt-5-mini', 'gpt-5-nano']
    assert [Decimal(call['cost']) for call in calls] == [Decimal('0.252'), Decimal('0.0504')]
    with pytest.raises(BudgetStopped):
        budget.reserve({**request, 'model': 'gpt-5'})
    assert budget.state['stop_reason'] == 'model_changed'


@pytest.mark.parametrize('stop', [True, False])
def test_transport_failure_keeps_reservation_and_stops_only_when_requested(tmp_path, stop):
    cases, approval = packet(tmp_path, 'A')
    budget = Budget(approval, Journal(tmp_path, approval['configuration']), stop_on_transport_failure=stop)
    request = {'messages': [{'role': 'user', 'content': 'synthetic'}], 'max_completion_tokens': 1000,
               'model': 'gpt-5-nano', 'response_format': {'json_schema': {'name': 'sageql_report_intent'}}}
    ticket = budget.reserve(dict(request))
    reserved = budget.state['calls'][ticket]['cost']
    budget.settle(ticket, None, failed=True)
    assert budget.state['calls'][ticket]['status'] == 'failed'
    assert budget.state['calls'][ticket]['cost'] == reserved
    assert budget.accounting()['uncertain_requests'] == 1
    assert budget.exhausted is stop


class Recording(ProtocolClient):
    def __init__(self, *args):
        super().__init__(*args)
        self.sent = []

    def create(self, **options):
        self.sent.append((options['response_format']['json_schema']['name'], options['model'],
                          options.get('reasoning_effort')))
        response = super().create(**options)
        # Exploratory accounting stops on missing usage; supply plausible counts.
        response.usage = SimpleNamespace(prompt_tokens=1000, completion_tokens=100, total_tokens=1100,
                                         prompt_tokens_details=None, completion_tokens_details=None)
        return response

    def close(self):
        pass


def test_setup_b_routes_intent_to_mini_on_the_real_runner_path(tmp_path):
    cases, approval = packet(tmp_path, 'B')
    approval.update(max_requests=2, capture_responses=False)  # Scripted choices lack finish_reason.
    case = cases[0]
    turn = case['turns'][0]
    client = Recording(turn, target_spec(case, turn), host(case['domain'], case['host_version'])[0])
    result = comparison.run(cases, tmp_path, 'B', approval, live_client_factory=lambda: client)
    assert client.sent[0] == ('sageql_report_intent', 'gpt-5-mini', 'low')
    assert client.sent[1] == ('sageql_report_interpretation', 'gpt-5-nano', 'low')
    assert result['budget_accounting']['stop_reason'] == 'request_budget'
    usage = comparison.usage_by_stage(tmp_path)
    assert {(item['stage'], item['model']) for item in usage} == {('intent', 'gpt-5-mini'),
                                                                 ('planning', 'gpt-5-nano')}


def test_rate_limit_halts_the_batch_even_when_transport_failures_continue(tmp_path):
    from evaluations.phase06_transport import ObservedClient

    class RateLimited(Exception):
        status_code = 429

    class Delegate:
        def __init__(self):
            self.chat = SimpleNamespace(completions=self)

        def create(self, **options):
            raise RateLimited()

    cases, approval = packet(tmp_path, 'A')
    budget = Budget(approval, Journal(tmp_path, approval['configuration']), stop_on_transport_failure=False)
    client = ObservedClient(Delegate(), budget=budget)
    request = {'messages': [{'role': 'user', 'content': 'synthetic'}], 'max_completion_tokens': 1000,
               'model': 'gpt-5-nano', 'response_format': {'json_schema': {'name': 'sageql_report_intent'}}}
    with pytest.raises(RateLimited):
        client.chat.completions.create(**request)
    assert budget.state['stop_reason'] == 'rate_limited' and budget.exhausted
    with pytest.raises(BudgetStopped):
        client.chat.completions.create(**request)


@pytest.mark.parametrize('level', sorted(comparison.LEVELS))
def test_levels_select_existing_cases_with_a_hard_cap(tmp_path, level):
    turns = 0
    for cohort, case_ids in comparison.LEVELS[level].items():
        cases = load_cases(cohort, case_ids)
        turns += sum(len(case['turns']) for case in cases)
        approval = comparison.prepare(cases, tmp_path / cohort, 'D', 'UNIT_TEST_ONLY', STAMP,
                                      max_cost_usd=comparison.LEVEL_CAPS[level])
        assert approval['max_cost_usd'] == comparison.LEVEL_CAPS[level]
    assert turns == {'smoke': 5, 'standard': 21, 'full': 40}[level]


def test_cli_refuses_an_existing_output_directory(tmp_path):
    with pytest.raises(SystemExit):
        comparison.main(['--output', str(tmp_path), '--authorization-id', 'UNIT_TEST_ONLY'])
