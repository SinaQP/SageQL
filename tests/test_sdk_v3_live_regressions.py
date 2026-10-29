"""Observed V3 failures; synthetic hosts and frozen independent answers."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from sageql import Message
from sageql.sdk import Interpretation, SageQL, SQLiteSessionStore
from sageql.sdk.evidence import request_evidence
from evaluations.phase05_hosts import host
from evaluations.phase14 import load_cases
from evaluations.runner import ScriptedClient, RecordingAdapter, extracted, ready
from evaluations.phase03_hosts import ACTOR, TODAY
from evaluations.trajectories import run_trajectory, target_spec
from tests.test_sdk_semantic_evidence import APPROVED


def test_confirmed_owner_invalid_period_asks_known_year_before_using_repair():
    case = load_cases(case_ids=['N02'])[0]
    case['turns'] = case['turns'][:3]
    clients = []
    def client(turn, target, catalog):
        partial = extracted(target, period=None, missing=('year',), turn_kind='new')
        partial['period'] = dict(kind='month', start=None, end=None, year=None,
                                 month=7, count=None, unit=None)
        value = ScriptedClient([partial, ''])  # Original invalid period, then empty repair.
        clients.append(value)
        return value
    result = run_trajectory(case, client_factory=client, agent_options={'max_structured_repairs': 1})
    assert result['correct'], [(t['outcome'], t['safe_errors']) for t in result['turns']]
    assert sum(len(c.calls) for c in clients) == 1
    assert result['turns'][2]['structured_repairs'] == 0
    assert all(not t['database_calls'] for t in result['turns'])


def test_pending_year_question_preserves_full_frozen_owner_and_reopened_report():
    result = run_trajectory(load_cases(case_ids=['N02'])[0])
    assert result['correct'], [(t['index'], t['outcome']) for t in result['turns']]
    assert result['turns'][2]['status'] == 'needs_clarification'
    assert len(result['turns'][2]['model_calls']) == 3
    assert result['turns'][3]['checks']['rows'] and result['turns'][3]['checks']['persisted']


def test_captured_extra_grouping_intent_can_complete_all_frozen_comparison_turns():
    case = load_cases(case_ids=['N04'])[0]
    clients = []
    def client(turn, target, catalog):
        wrong = replace(target, dimension_ids=('channel',)) if not clients else target
        value = ScriptedClient([extracted(wrong, turn_kind=turn.get('turn_kind', 'new')), ready(target), APPROVED])
        clients.append(value)
        return value
    result = run_trajectory(case, client_factory=client)
    assert result['correct'], [(t['index'], t['outcome'], t['safe_errors']) for t in result['turns']]
    assert all(t['checks']['specification'] and t['checks']['rows'] for t in result['turns'])


def test_persistent_extra_grouping_planner_never_reaches_review_or_database():
    case = load_cases(case_ids=['N04'])[0]
    case['turns'] = case['turns'][:1]
    clients = []
    def client(turn, target, catalog):
        wrong = replace(target, dimension_ids=('channel',))
        value = ScriptedClient([extracted(wrong), ready(wrong), ready(wrong), APPROVED])
        clients.append(value)
        return value
    result = run_trajectory(case, client_factory=client)
    turn = result['turns'][0]
    assert turn['status'] == 'blocked' and turn['database_calls'] == 0
    assert not turn['reviews'] and not turn['accepted_specification_incorrect']


def test_provider_neutral_extra_grouping_is_rejected_before_execution(tmp_path):
    case = load_cases(case_ids=['N04'])[0]
    target = target_spec(case, case['turns'][0])
    catalog, policy, create_data = host('workshop', 'workshop-values-v1')
    wrong = replace(target, dimension_ids=('channel',))
    path = tmp_path / 'facts.sqlite'
    create_data(path)
    adapter = RecordingAdapter(path)
    engine = SageQL(catalog=catalog, policy=policy, database=adapter,
        provider=SimpleNamespace(interpret=lambda *args: Interpretation('ready', wrong)),
        clock=lambda: TODAY, execution='validated', language='en',
        sessions=SQLiteSessionStore(tmp_path / 'sessions.sqlite'))
    session = engine.create_session(ACTOR)
    reply = engine.submit(session.session_id, case['turns'][0]['request'], ACTOR, 'first', session.revision)
    assert reply.status == 'blocked' and reply.report is None and not adapter.calls


@pytest.mark.parametrize('wording', ['whole period', 'entire period', 'کل دوره', 'کل بازه'])
def test_explicit_period_total_without_dimension_request_excludes_added_grouping(wording):
    catalog, _, _ = host('workshop', 'workshop-values-v1')
    message = Message('user', 'Billed amount in July 2026, Channel = Counter; table for ' + wording + '.')
    evidence = request_evidence((message,), catalog)
    assert ('jobs', 'channel') in evidence.excluded_dimensions


@pytest.mark.parametrize('text', [
    'Billed amount by Channel in July 2026; show the entire period in one table.',
    'Billed amount in July 2026; Service = "entire period" in a table.',
    'Billed amount in July 2026; table, not the entire period.',
    'Billed amount by UnregisteredZone in July 2026; entire period in a table.',
])
def test_requested_grouping_literals_negation_and_unknown_grouping_are_not_erased(text):
    catalog, _, _ = host('workshop', 'workshop-values-v1')
    evidence = request_evidence((Message('user', text),), catalog)
    assert ('jobs', 'channel') not in evidence.excluded_dimensions


def test_current_grouped_report_keeps_business_groups_when_time_buckets_are_removed():
    case = load_cases(case_ids=['N04'])[0]
    current = replace(target_spec(case, case['turns'][0]), dimension_ids=('channel',))
    catalog, _, _ = host('workshop', 'workshop-values-v1')
    evidence = request_evidence((Message('user', 'Keep that report; entire period in one table.'),), catalog, current)
    assert ('jobs', 'channel') not in evidence.excluded_dimensions
