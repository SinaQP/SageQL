"""Measured completion failures: strict candidates, finite repair, real SQLite."""
from dataclasses import replace
import json

import pytest

from sageql import LLMConfig, Message
from sageql.sdk import OpenAIReportAgent, PeriodSelection, UserFilter
from sageql.sdk.evidence import request_evidence
from evaluations.runner import extracted, ready
from tests.test_sdk_semantic_evidence import engine_at, submit, APPROVED
from tests.test_sdk_year_answer_recovery import desired


def engine_with_repair(tmp_path, responses):
    engine, adapter, client = engine_at(tmp_path, responses=responses)
    engine.provider = OpenAIReportAgent(LLMConfig('synthetic', 'https://example.test/v1', 'fake'),
        client=client, language='en', max_structured_repairs=1)
    return engine, adapter, client


@pytest.mark.parametrize('fault', ['duplicate_metric', 'fixed_month_unit'])
def test_opted_in_repair_receives_validation_feedback_and_completes_correct_report(tmp_path, fault):
    target = desired(); intent = extracted(target); proposal = ready(target)
    if fault == 'duplicate_metric':
        broken = ready(target); broken['spec']['metric_ids'].append('units')
        responses = [intent, broken, proposal, APPROVED]
    else:
        broken = extracted(target); broken['period']['unit'] = 'month'
        responses = [broken, intent, proposal, APPROVED]
    engine, adapter, client = engine_with_repair(tmp_path, responses)
    reply = submit(engine, 'Tabulate Units sold by Department in September 2026.')
    assert reply.status == 'report_ready' and len(adapter.calls) == 1 and len(client.calls) == 4
    assert reply.report.rows == (('Books', 5), ('Garden', 9))
    repaired = json.loads(client.calls[2 if fault == 'duplicate_metric' else 1]['messages'][-1]['content'])
    assert any('structured_validation:' in x for x in repaired.get('feedback', repaired.get('consistency_feedback', [])))
    replay = submit(engine, 'Tabulate Units sold by Department in September 2026.', session=reply.session_id)
    assert replay.to_dict() == reply.to_dict() and len(client.calls) == 4 and len(adapter.calls) == 1


def test_fresh_plain_table_default_is_transferred_to_planner_without_rewriting_candidate(tmp_path):
    target = desired(); intent = extracted(target); intent['limit'] = None
    wrong = ready(replace(target, limit=1))
    engine, adapter, client = engine_at(tmp_path, responses=[intent, wrong, ready(target), APPROVED])
    reply = submit(engine, 'Tabulate Units sold by Department in September 2026.')
    assert reply.status == 'report_ready' and len(adapter.calls) == 1
    payload = json.loads(client.calls[1]['messages'][-1]['content'])
    assert payload['intent']['limit'] == 100
    correction = json.loads(client.calls[2]['messages'][-1]['content'])
    assert correction['feedback'] == ['intent_validation: limit_mismatch']


@pytest.mark.parametrize('wrong', ['repeated_duplicate', 'semantic_change'])
def test_opted_in_repair_never_accepts_an_invalid_or_semantically_different_report(tmp_path, wrong):
    target = desired(); invalid = ready(target); invalid['spec']['metric_ids'].append('units')
    repaired = invalid if wrong == 'repeated_duplicate' else ready(replace(target, metric_ids=('revenue',)))
    engine, adapter, client = engine_with_repair(tmp_path, [extracted(target), invalid, repaired, repaired])
    reply = submit(engine, 'Tabulate Units sold by Department in September 2026.')
    assert reply.status == 'blocked' and not adapter.calls
    assert len(client.calls) <= 4


def test_named_reference_to_current_total_keeps_base_period_and_filter():
    from evaluations.phase05_hosts import host
    from evaluations.phase14 import load_cases
    from evaluations.trajectories import target_spec
    case = load_cases(case_ids=['N04'])[0]
    catalog, _, _ = host(case['domain'], case['host_version'])
    current = target_spec(case, case['turns'][0])
    e = request_evidence((Message('user', case['turns'][1]['request']),), catalog, current)
    assert e.period == current.period and e.comparison == PeriodSelection('month', year=2026, month=6)
    assert e.retained_filters == current.filters


@pytest.mark.parametrize('text', [
    'Compare that total with June 2026.', 'Compare the current report with June 2026.',
])
def test_relative_comparison_without_a_current_report_asks_for_base(text):
    from evaluations.phase05_hosts import host
    catalog, _, _ = host('workshop', 'workshop-values-v1')
    e = request_evidence((Message('user', text),), catalog)
    assert e.missing == 'period' and e.period is None


def test_existing_n04_frozen_scripted_conversation_completes_without_changing_answers():
    from evaluations.phase14 import load_cases
    from evaluations.trajectories import run_trajectory
    result = run_trajectory(load_cases(case_ids=['N04'])[0])
    assert result['correct'], [(t['index'],t['outcome']) for t in result['turns']]


@pytest.mark.parametrize('text', [
    'Do not compare that total with June 2026.',
    'Use the title "Compare that total with June 2026".',
    'Compare July 2026 with June 2026.',
])
def test_negative_literal_and_explicit_two_period_requests_do_not_rebind_base(text):
    from evaluations.phase05_hosts import host
    from evaluations.phase14 import load_cases
    from evaluations.trajectories import target_spec
    case = load_cases(case_ids=['N04'])[0]
    catalog, _, _ = host(case['domain'], case['host_version'])
    current = replace(target_spec(case, case['turns'][0]), period=PeriodSelection('month', year=2025, month=10))
    e = request_evidence((Message('user', text),), catalog, current)
    assert e.comparison is None or e.period != current.period


@pytest.mark.parametrize('category,expected', [
    ('timeout','transport_timeout'),('connection','transport_connection'),
    ('429','transport_rate_limit'),('503','transport_server'),('401','transport_client'),
    ('unknown','transport'),
])
def test_transport_categories_are_safe_and_never_retried(tmp_path, monkeypatch, category, expected):
    import sys
    from types import SimpleNamespace
    class Connection(Exception):pass
    class Timeout(Connection):pass
    class Status(Exception):
        def __init__(self, code):self.status_code=code
    monkeypatch.setitem(sys.modules,'openai',SimpleNamespace(APITimeoutError=Timeout,APIConnectionError=Connection,APIStatusError=Status))
    error = Timeout('PRIVATE_URL_KEY') if category=='timeout' else Connection('PRIVATE_URL_KEY') if category=='connection' else Status(int(category)) if category.isdigit() else RuntimeError('PRIVATE_URL_KEY')
    class Failing:
        def __init__(self):self.chat=SimpleNamespace(completions=self);self.calls=[]
        def with_options(self,**kw):return self
        def create(self,**kw):self.calls.append(kw);raise error
    client=Failing();engine,adapter,_=engine_at(tmp_path)
    engine.provider=OpenAIReportAgent(LLMConfig('synthetic','https://example.test/v1','fake'),client=client,language='en',max_structured_repairs=1)
    reply=submit(engine,'Tabulate Units sold by Department in September 2026.')
    assert reply.error['reason']==expected and len(client.calls)==1 and not adapter.calls
    assert 'PRIVATE' not in json.dumps(reply.to_dict())


@pytest.mark.parametrize('code,expected', [('agent_exhausted','agent_recovery_exhaustion'),
    ('provider_failed','provider_transport_failure'),('request_timeout','request_deadline')])
def test_failure_diagnoses_do_not_turn_exhaustion_into_transport(code, expected):
    from evaluations.trajectories import _diagnosis
    from evaluations.scoring import Assessment
    assert _diagnosis({'expect':{'kind':'report'}},{'status':'failed','error':{'code':code}},Assessment('operational_failure',{}),[])==expected


def test_repair_option_is_exact_approval_configuration_and_cannot_be_enabled_implicitly(tmp_path):
    from evaluations.phase06 import configuration, run
    from evaluations.phase14 import load_cases, corpus_for, draft
    cases=load_cases(case_ids=['N01']);root,version=corpus_for(cases)
    base=configuration(cases,'live','https://api.avalai.ir/v1','gpt-5-nano',corpus_root=root,corpus_version=version)
    enabled=configuration(cases,'live','https://api.avalai.ir/v1','gpt-5-nano',corpus_root=root,corpus_version=version,max_structured_repairs=1)
    assert 'max_structured_repairs' not in base and enabled['max_structured_repairs']==1
    approval=draft(cases,tmp_path/'absent','https://api.avalai.ir/v1','gpt-5-nano',accounting_mode='exploratory')
    approval['authorized']=True
    clients=[]
    with pytest.raises(ValueError,match='Exact evaluation approval'):run(cases,tmp_path/'absent',mode='live',endpoint='https://api.avalai.ir/v1',model='gpt-5-nano',approval=approval,
        corpus_root=root,corpus_version=version,accounting_mode='exploratory',max_structured_repairs=1,live_client_factory=lambda:clients.append(1))
    assert not clients and not (tmp_path/'absent').exists()


def test_transport_diagnostics_do_not_cold_import_an_optional_sdk(monkeypatch):
    import builtins,sys
    from sageql.sdk.provider import _transport_reason
    monkeypatch.delitem(sys.modules,'openai',raising=False)
    original=builtins.__import__
    def guarded(name,*a,**kw):
        if name=='openai':raise AssertionError('Optional SDK must not initialize on a failure path')
        return original(name,*a,**kw)
    monkeypatch.setattr(builtins,'__import__',guarded)
    assert _transport_reason(RuntimeError('private injected failure'))=='transport'
