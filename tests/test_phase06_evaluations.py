from copy import deepcopy
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
import json
import socket
import time

import pytest

from evaluations.phase06 import approval_template, configuration, load_cases, run
from evaluations.phase06_runtime import (Budget, BudgetStopped, Journal, atomic_json,
    run_lock, usage_metadata, validate_approval)
from evaluations.phase06_transport import ProtocolClient
from evaluations.phase05_hosts import host
from evaluations.trajectories import target_spec
from sageql.sdk.vocabulary import project_payload, restore_response


@pytest.fixture(autouse=True)
def no_external_calls(monkeypatch):
 def reject(*args,**kwargs):raise AssertionError('Network forbidden in Phase 06 tests')
 monkeypatch.setattr(socket.socket,'connect',reject)
 monkeypatch.setattr(socket.socket,'connect_ex',reject)
 monkeypatch.setattr(socket,'create_connection',reject)


def reviewed(tmp_path,cases=None):
 cases=cases or load_cases(case_ids=['L01'])
 config=configuration(cases,'live','https://example.test/v1','mock-model')
 approval=approval_template(config,tmp_path)
 approval.update(authorized=True,authorization_id='UNIT_TEST_ONLY',max_requests=100,
  max_input_tokens=10000000,max_output_tokens=1000000,max_total_tokens=11000000,
  max_seconds=600,max_cost_usd='100')
 approval['pricing'].update(reviewed=True,effective_date='2026-10-26',verified_at='2026-10-26T00:00:00+00:00',
  input_usd_per_million='1',output_usd_per_million='2')
 approval['accounting'].update(reviewed=True,overhead_tokens=100,output_cap_includes_reasoning=True,
  usage_includes_reasoning=True,no_unpriced_fees=True)
 return config,approval


def options():return {'model':'mock-model','messages':[{'role':'user','content':'synthetic'}],
 'response_format':{'type':'json_schema','schema':{'description':'schema is charged too'}},
 'max_completion_tokens':1024,'timeout':30}


def budget(tmp_path,**changes):
 config,a=reviewed(tmp_path);a.update(changes)
 j=Journal(tmp_path,config);return Budget(a,j),j,a


def test_approval_exact_configuration_and_disabled_default(tmp_path):
 config,a=reviewed(tmp_path);validate_approval(a,config,tmp_path)
 a['authorized']=False
 with pytest.raises(ValueError):validate_approval(a,config,tmp_path)


@pytest.mark.parametrize('field,value',[
 ('max_requests',True),('max_requests',0),('max_requests',10001),('max_input_tokens',0),
 ('max_output_tokens',-1),('max_total_tokens',0),('max_seconds',0),('max_cost_usd','NaN'),
 ('max_cost_usd','0'),('per_call_output_tokens',20000),('output_directory','wrong')])
def test_invalid_approval_never_dispatches(tmp_path,field,value):
 config,a=reviewed(tmp_path);a[field]=value
 with pytest.raises(ValueError):validate_approval(a,config,tmp_path)


@pytest.mark.parametrize('section,key,value',[
 ('pricing','reviewed',False),('pricing','source_url','http://example.test'),
 ('pricing','effective_date','invalid'),('pricing','verified_at','2026-10-26'),
 ('pricing','input_usd_per_million','Infinity'),('accounting','reviewed',False),
 ('accounting','output_cap_includes_reasoning',False),('accounting','usage_includes_reasoning',False),
 ('accounting','no_unpriced_fees',False),('accounting','overhead_tokens',True)])
def test_unverifiable_accounting_and_pricing_block_live(tmp_path,section,key,value):
 config,a=reviewed(tmp_path);a[section][key]=value
 with pytest.raises(ValueError):validate_approval(a,config,tmp_path)


@pytest.mark.parametrize('field,value', [('model','different'),('endpoint','https://different.test/v1'),
 ('adapter','unknown'),('source_sha256','changed'),('case_ids',['L02'])])
def test_approval_is_bound_to_exact_experiment(tmp_path,field,value):
 config,a=reviewed(tmp_path);changed={**config,field:value}
 with pytest.raises(ValueError):validate_approval(a,changed,tmp_path)


@pytest.mark.parametrize('field,value,reason',[
 ('max_requests',1,'request_budget'),('max_input_tokens',1,'input_budget'),
 ('max_output_tokens',1,'output_budget'),('max_total_tokens',1,'total_token_budget'),
 ('max_cost_usd','0.000001','cost_budget')])
def test_budget_reserves_before_dispatch_and_stops(tmp_path,field,value,reason):
 b,j,a=budget(tmp_path,**{field:value})
 if field=='max_requests':b.reserve(options())
 before=len(b.state['calls'])
 with pytest.raises(BudgetStopped):b.reserve(options())
 assert b.state['stop_reason']==reason and len(b.state['calls'])==before
 assert json.loads(j.path.read_text())['budget']['stop_reason']==reason


def test_schema_and_provider_overhead_are_reserved_and_persisted(tmp_path):
 b,j,a=budget(tmp_path);o=options();ticket=b.reserve(o)
 expected=len(json.dumps(options(),ensure_ascii=False,allow_nan=False).encode())+100
 assert b.accounting()['input_charged_or_reserved']==expected
 assert json.loads(j.path.read_text())['budget']['calls'][ticket]['status']=='reserved'
 assert o['timeout']<=30


def test_missing_usage_and_failed_call_retain_conservative_reservation(tmp_path):
 b,j,a=budget(tmp_path);ticket=b.reserve(options());before=b.accounting()
 b.settle(ticket,None,failed=True)
 assert b.accounting()['input_charged_or_reserved']==before['input_charged_or_reserved']
 assert b.accounting()['estimated_usd_charged_or_reserved']==before['estimated_usd_charged_or_reserved']
 assert b.state['calls'][ticket]['status']=='failed'
 resumed=Budget(a,Journal(tmp_path,j.data['manifest'],resume=True))
 assert resumed.accounting()==b.accounting()


def test_uncertain_reservation_survives_process_restart(tmp_path):
 b,j,a=budget(tmp_path);b.reserve(options())
 resumed=Budget(a,Journal(tmp_path,j.data['manifest'],resume=True))
 assert resumed.accounting()['requests_dispatched']==1
 assert resumed.accounting()['uncertain_requests']==1


def test_complete_usage_adjusts_without_double_counting_reasoning(tmp_path):
 b,j,a=budget(tmp_path);ticket=b.reserve(options())
 usage={'input':20,'output':30,'total':50,'cached_input':5,'reasoning':10}
 b.settle(ticket,usage)
 assert b.accounting()['input_charged_or_reserved']==20
 assert b.accounting()['output_charged_or_reserved']==30
 assert b.accounting()['estimated_usd_charged_or_reserved']=='0.00008'


def test_usage_overrun_stops_further_calls(tmp_path):
 b,j,a=budget(tmp_path);ticket=b.reserve(options())
 b.settle(ticket,{'input':10**8,'output':3,'total':10**8+3,'cached_input':None,'reasoning':None})
 assert b.exhausted and b.state['stop_reason']=='provider_bound_violation'
 with pytest.raises(BudgetStopped):b.reserve(options())


def test_elapsed_wall_time_including_pause_and_clock_rollback(tmp_path):
 b,j,a=budget(tmp_path);j.data['started_at']=time.time()-a['max_seconds']-1
 assert b.exhausted
 with pytest.raises(BudgetStopped):b.reserve(options())
 j.data['started_at']=time.time()+100
 assert b.remaining_seconds()==0


@pytest.mark.parametrize('raw',[
 {'prompt_tokens':True,'completion_tokens':0}, {'prompt_tokens':5,'completion_tokens':-1},
 {'prompt_tokens':5,'completion_tokens':6,'total_tokens':12},
 {'prompt_tokens':5,'completion_tokens':6,'prompt_tokens_details':{'cached_tokens':6}},
 {'prompt_tokens':5,'completion_tokens':6,'completion_tokens_details':{'reasoning_tokens':7}},
 {'prompt_tokens':5}])
def test_invalid_usage_is_not_invented(raw):
 with pytest.raises(ValueError):usage_metadata(SimpleNamespace(usage=raw))
 assert usage_metadata(SimpleNamespace()) is None


def test_usage_subset_fields_remain_unavailable_when_absent():
 assert usage_metadata(SimpleNamespace(usage={'prompt_tokens':3,'completion_tokens':7}))=={
  'input':3,'output':7,'total':10,'cached_input':None,'reasoning':None}


def test_atomic_checkpoints_and_exclusive_lock(tmp_path):
 with run_lock(tmp_path):
  with pytest.raises(ValueError):
   with run_lock(tmp_path):pass
 atomic_json(tmp_path/'safe.json',{'ok':True})
 assert json.loads((tmp_path/'safe.json').read_text())=={'ok':True}


def test_resume_rejects_changed_manifest_and_preserves_first_result(tmp_path):
 j=Journal(tmp_path,{'source':'initial'})
 with pytest.raises(ValueError):Journal(tmp_path,{'source':'initial'})
 with pytest.raises(ValueError):Journal(tmp_path,{'source':'changed'},resume=True)
 assert json.loads(j.path.read_text())['manifest']=={'source':'initial'}


def test_live_preflight_never_builds_client_without_separate_exact_approval(tmp_path):
 calls=[]
 with pytest.raises(ValueError):run(load_cases(case_ids=['L01']),tmp_path,mode='live',
  endpoint='https://example.test/v1',model='mock-model',approval={},live_client_factory=lambda:calls.append(1))
 assert not calls


def test_ineligible_fault_cases_cannot_run_live(tmp_path):
 with pytest.raises(ValueError):run(load_cases('protocol'),tmp_path,mode='live')


def test_interruption_resume_keeps_first_turn_and_never_repeats_active_trajectory(tmp_path):
 cases=load_cases(case_ids=['L01','L23','L25'])
 def interrupt(turn):
  if turn['goal']=='clarification':raise KeyboardInterrupt
 first=run(cases,tmp_path,turn_hook=interrupt)
 assert first['interrupted'] and len(first['results'])==2
 before=deepcopy(first['results'][0])
 second=run(cases,tmp_path,resume=True)
 assert second['results'][0]==before
 active=next(c for c in second['results'] if c['id']=='L23')
 assert active['interrupted'] and len(active['turns'])==1 and active['unexecuted_turns']==3
 assert next(c for c in second['results'] if c['id']=='L25')['correct']
 assert second['unexecuted_turns']==3


def test_controlled_stop_can_resume_only_untouched_cases(tmp_path):
 cases=load_cases(case_ids=['L01','L03'])
 first=run(cases,tmp_path,max_cases=1)
 second=run(cases,tmp_path,resume=True)
 assert first['results'][0]==second['results'][0]
 assert len(second['results'])==2


def test_live_budget_on_real_sdk_path_with_mock_transport(tmp_path):
 cases=load_cases(case_ids=['L01']);config,a=reviewed(tmp_path,cases);a['max_requests']=2
 c=cases[0];client=ProtocolClient(c['turns'][0],target_spec(c,c['turns'][0]),host(c['domain'],c['host_version'])[0])
 client.close=lambda:None
 result=run(cases,tmp_path,mode='live',endpoint=config['endpoint'],model=config['model'],approval=a,live_client_factory=lambda:client)
 assert result['budget_accounting']['requests_dispatched']==2
 assert result['mode']=='live_budget_mock_test' and result['live_model_status']=='not_executed_mock_transport'
 assert result['budget_accounting']['stop_reason']=='request_budget'
 assert result['summary']['database_calls']==0
 assert result['summary']['supported_completion']['numerator']==0


def wire():
 catalog=host('workshop','workshop-values-v1')[0]
 request={'host_filter_requirements':[{'dataset_id':'jobs','filter_id':'channel_filter','operator':'eq','values':['Web']}]}
 projected=project_payload(request,catalog)
 return catalog,json.dumps(projected),projected['host_filter_requirements'][0]['values'][0]


@pytest.mark.parametrize('literal',['__sageql_value_99_99_99__','__sageql_value_0_0_0_',
 '__sageql-value_0_0_0__','__SAGEQL_VALUE_0_0_0__',
 '_sageql_value_0_0_0__','sageql_value_0_0_0__','__sageql value_0_0_0__'])
def test_fabricated_and_altered_reserved_references_reject(literal):
 catalog,content,token=wire()
 with pytest.raises(ValueError):restore_response({'dataset_id':'jobs','filters':[
  {'filter_id':'channel_filter','operator':'eq','values':[literal]}]},catalog,content)


def test_issued_ref_restores_and_wrong_owner_rejects():
 catalog,content,token=wire();value={'dataset_id':'jobs','filters':[{'filter_id':'channel_filter','operator':'eq','values':[token]}]}
 assert restore_response(value,catalog,content)['filters'][0]['values']==['Web']
 value['filters'][0]['filter_id']='service_filter'
 with pytest.raises(ValueError):restore_response(value,catalog,content)


def test_reviewer_feedback_cannot_display_private_reference():
 catalog,content,token=wire()
 with pytest.raises(ValueError):restore_response({'approved':False,'feedback':'Use '+token},catalog,content)


def test_model_switch_is_rejected_before_dispatch(tmp_path):
 b,j,a=budget(tmp_path);o=options();o['model']='unapproved'
 with pytest.raises(BudgetStopped):b.reserve(o)
 assert not b.state['calls'] and b.state['stop_reason']=='model_changed'


def test_invalid_usage_holds_reservation_and_stops(tmp_path):
 b,j,a=budget(tmp_path);ticket=b.reserve(options());before=b.accounting()
 b.settle(ticket,None,invalid=True)
 assert b.exhausted and b.accounting()['input_charged_or_reserved']==before['input_charged_or_reserved']
 assert b.state['stop_reason']=='invalid_usage'


def test_fully_scored_last_turn_survives_interruption_without_reexecution(tmp_path):
 cases=load_cases(case_ids=['L01'])
 def interrupt(turn):raise KeyboardInterrupt
 first=run(cases,tmp_path,turn_hook=interrupt)
 second=run(cases,tmp_path,resume=True)
 assert len(second['results'][0]['turns'])==1 and second['results'][0]['correct']
 assert first['results'][0]['turns']==second['results'][0]['turns']


def test_no_vocabulary_does_not_make_fabricated_reference_a_free_form_scalar():
 from evaluations.phase03_hosts import workshop_catalog
 with pytest.raises(ValueError):restore_response({'dataset_id':'jobs','filters':[
  {'filter_id':'channel_filter','operator':'eq','values':['__sageql_value_99_99_99__']}]},workshop_catalog(),'{}')


def test_failed_database_read_is_attempted_once_and_receipt_preserves_failure(tmp_path):
 from evaluations.trajectories import run_trajectory
 from evaluations.phase06_transport import mock_client,ObservedClient
 case=deepcopy(load_cases(case_ids=['L01'])[0]);turn=case['turns'][0]
 turn['fault']='database';turn['expect']={'kind':'failure','error_code':'database_unavailable'}
 result=run_trajectory(case,client_factory=mock_client,stage_client_type=ObservedClient)
 assert result['correct'] and result['turns'][0]['database_calls']==1
 assert result['turns'][0]['checks']['receipt'] and result['turns'][0]['checks']['previous_preserved']


@pytest.fixture(scope='module')
def corpus_result(tmp_path_factory):
 return run(load_cases(),tmp_path_factory.mktemp('phase06-corpus'))


@pytest.mark.parametrize('identifier',[c['id'] for c in load_cases() if c['id']!='L26'])
def test_frozen_protocol_semantics_and_complete_results(identifier,corpus_result):
 result=next(c for c in corpus_result['results'] if c['id']==identifier)
 assert result['correct'],result


def test_repaired_continuation_stays_in_original_report_denominator(corpus_result):
 result=next(c for c in corpus_result['results'] if c['id']=='L26')
 assert result['correct'] and result['turns'][1]['goal']=='report'
 assert result['turns'][1]['outcome']=='correct_report' and result['turns'][1]['database_calls']==1
 assert corpus_result['summary']['supported_completion']['denominator']==36
 assert corpus_result['summary']['supported_completion']['numerator']==36
 assert corpus_result['summary']['failing_trajectories']==[]


def test_allowlisted_measurements_do_not_store_prompts_rows_or_provider_secrets(corpus_result):
 text=json.dumps(corpus_result,ensure_ascii=False)
 for forbidden in ('PRIVATE_PROVIDER_EXCEPTION','DROP TABLE','For the finance pack','host_filter_requirements',
  'value_vocabulary','__sageql_value_','"endpoint"','"api_key"'):
  assert forbidden not in text
 assert corpus_result['summary']['incorrect_accepted_specifications']==0
 assert corpus_result['summary']['unauthorized_reads']==0
 assert corpus_result['summary']['usage_coverage']['numerator']==0
 assert corpus_result['summary']['tokens'] is None and corpus_result['summary']['estimated_cost'] is None


def test_frozen_protocol_errors_do_not_discard_first_failed_stages(corpus_result):
 byid={c['id']:c for c in corpus_result['results']}
 assert byid['P01']['turns'][0]['protocol'][1]['fabricated']==1
 assert byid['P02']['turns'][0]['protocol'][1]['modified']==1
 assert byid['P11']['turns'][0]['model_calls'][-1]['failed']
 assert byid['P14']['turns'][0]['database_calls']==0
 assert byid['P10']['turns'][0]['database_calls']==0
 assert byid['P12']['correct']  # Canonical values remain semantic scalars, not secret identities.


def test_live_interrupt_retains_uncertain_request_and_skips_it_on_resume(tmp_path):
 cases=load_cases(case_ids=['L01','L03']);config,a=reviewed(tmp_path,cases)
 class InterruptClient:
  def __init__(self):self.chat=SimpleNamespace(completions=self);self.calls=0
  def with_options(self,**kw):return self
  def create(self,**kw):self.calls+=1;raise KeyboardInterrupt
  def close(self):pass
 client=InterruptClient()
 first=run(cases,tmp_path,mode='live',endpoint=config['endpoint'],model=config['model'],approval=a,live_client_factory=lambda:client)
 assert first['budget_accounting']['requests_dispatched']==1
 assert first['budget_accounting']['uncertain_requests']==1
 assert first['summary']['diagnostic_call_coverage']['value']==0
 second=run(cases,tmp_path,mode='live',endpoint=config['endpoint'],model=config['model'],approval=a,resume=True,live_client_factory=lambda:client)
 assert client.calls==2 and second['budget_accounting']['requests_dispatched']==2
 assert second['budget_accounting']['uncertain_requests']==2
 assert next(c for c in second['results'] if c['id']=='L01')['unexecuted_turns']==1


def test_measurement_row_and_filter_keys_hold_only_boolean_checks(corpus_result):
 def walk(value):
  if isinstance(value,dict):
   for key,item in value.items():
    if key in ('rows','filters'):assert type(item) is bool
    walk(item)
  elif isinstance(value,list):
   for item in value:walk(item)
 walk(corpus_result)


def test_stage_period_scoring_accepts_equivalent_frozen_ranges_and_missing_dates():
 from evaluations.trajectories import _intent_diagnostics
 from evaluations.runner import extracted
 case=load_cases(case_ids=['L01'])[0];turn=case['turns'][0];target=target_spec(case,turn)
 value=extracted(target);value['period']={'kind':'range','start':'2026-07-01','end':'2026-08-01'}
 assert _intent_diagnostics(value,target,turn)['period']
 value['period']['end']='2026-08-02'
 assert not _intent_diagnostics(value,target,turn)['period']
 missing=load_cases(case_ids=['L15'])[0]['turns'][0];value['period']=None;value['missing']=['period']
 assert _intent_diagnostics(value,target,missing)['period']
 assert _intent_diagnostics(value,target,missing)['missing']
 owner=load_cases(case_ids=['L10'])[0]['turns'][0];value['missing']=['filter_value']
 assert _intent_diagnostics(value,target,owner)['missing']


def test_unexpected_runner_failure_is_durable_and_sanitized(tmp_path,monkeypatch):
 import evaluations.phase06 as module
 def fail(*args,**kwargs):raise RuntimeError('PRIVATE_UNEXPECTED_FAILURE')
 monkeypatch.setattr(module,'run_trajectory',fail)
 with pytest.raises(RuntimeError):run(load_cases(case_ids=['L01']),tmp_path)
 value=json.loads((tmp_path/'results.json').read_text())
 assert value['runner_reason']=='runner_failure' and value['interrupted']
 assert value['unexecuted_turns']==1
 assert 'PRIVATE_UNEXPECTED_FAILURE' not in json.dumps(value)


def test_clarification_requires_the_frozen_missing_business_detail():
 from evaluations.phase06 import assess_outcome
 expected=next(t['expect'] for c in load_cases(case_ids=['L10']) for t in c['turns'])
 wrong={'status':'needs_clarification','report':None,'clarification':'Which year should I use?'}
 assert assess_outcome(expected,wrong).outcome=='incorrect_rejection'
 right={**wrong,'clarification':'Which registered filter owns this value?'}
 assert assess_outcome(expected,right).outcome=='correct_clarification'
 assert assess_outcome(expected,right).checks['clarification_detail']


def test_invalid_custom_title_oracle_is_preserved_and_replaced():
 old=json.loads(Path('evaluations/phase06/cases.v3.json').read_text(encoding='utf-8'))
 current=json.loads(Path('evaluations/phase06/cases.v4.json').read_text(encoding='utf-8'))
 assert current['retired_cases'][0]['case']==next(c for c in old['cases'] if c['id']=='L11')
 assert 'L11' not in {c['id'] for c in load_cases()}
 assert next(c for c in load_cases() if c['id']=='L27')['turns'][0]['expect']['kind']=='report'
