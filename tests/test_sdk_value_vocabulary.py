"""Host-owned semantics, typed parameters, privacy and provider-neutral gates."""
from dataclasses import replace
from datetime import date
from decimal import Decimal
import json
from types import SimpleNamespace

import pytest

from sageql import Message
from sageql.sdk import (AccessScope, DatasetAccess, FilterDefinition, FilterValueDefinition,
    FullNameFilterDefinition, Interpretation, OpenAIReportAgent, PeriodSelection, ReportSpec,
    SageQL, SDKError, SQLiteSessionStore, UserFilter)
from sageql.sdk.evidence import request_evidence
from sageql.sdk.semantics import permitted_catalog, validate_catalog
from sageql.sdk.vocabulary import project_payload, restore_response
from evaluations.phase03_hosts import ACTOR, TODAY, host as original_host
from evaluations.phase05_hosts import host
from evaluations.runner import RecordingAdapter, ScriptedClient, extracted, ready
from evaluations.phase05 import load_cases
from evaluations.trajectories import run_trajectory


def spec(**changes):
    return replace(ReportSpec('jobs',('billed',),period=PeriodSelection('month',year=2026,month=7)),**changes)


def evidence(text, version='workshop-values-v1', current=None, catalog=None):
    catalog = catalog or host('workshop', version)[0]
    return request_evidence((Message('user',text),),catalog,current)


def make_engine(tmp_path, target, *, version='workshop-values-v1', client=None, catalog=None, policy=None, provider=None):
    from sageql import LLMConfig
    registered, original_policy, create = host('workshop',version)
    path=tmp_path/'facts.sqlite';create(path)
    adapter=RecordingAdapter(path)
    client=client or ScriptedClient([extracted(target),ready(target),{'approved':True,'feedback':''}])
    provider=provider or OpenAIReportAgent(LLMConfig('synthetic','https://example.test/v1','fake'),client=client,language='en')
    engine=SageQL(catalog=catalog or registered,policy=policy or original_policy,database=adapter,provider=provider,
                  sessions=SQLiteSessionStore(tmp_path/'sessions.sqlite'),clock=lambda:TODAY,execution='validated',language='en')
    return engine,adapter,client


def submit(engine,text,session=None,request='first',revision=0):
    session=session or engine.create_session(ACTOR).session_id
    return engine.submit(session,text,ACTOR,request,revision)


def with_entries(entries, *, operators=None):
    catalog=original_host('workshop')[0];dataset=catalog.datasets[0]
    filters=tuple(replace(f,value_vocabulary=entries,**({'operators':operators} if operators is not None else {}))
                  if f.id=='channel_filter' else f for f in dataset.filters)
    return replace(catalog,datasets=(replace(dataset,filters=filters),))


def test_optional_keyword_only_extension_preserves_name_filter_positional_contract():
    assert FilterDefinition('x','X','x').value_vocabulary==()
    assert FullNameFilterDefinition('n','Name','first',('eq',),('first','last')).name_columns==('first','last')
    from sageql.sdk.engine import _typed
    assert 'value_vocabulary' not in _typed(FilterDefinition('x','X','x'))


@pytest.mark.parametrize('entries',[
    [], (object(),), (FilterValueDefinition(None,('X',)),),
    (FilterValueDefinition(1,('X',)),), (FilterValueDefinition('Web',()),),
    (FilterValueDefinition('Web',('',)),), (FilterValueDefinition('Web',('x'*121,)),),
    (FilterValueDefinition('Web',('Online','online')),),
    (FilterValueDefinition('Web',('One',)),FilterValueDefinition('Web',('Two',))),
    tuple(FilterValueDefinition(str(i),(str(i),)) for i in range(65)),
])
def test_invalid_host_registrations_fail_without_values_in_errors(entries):
    with pytest.raises(SDKError) as error:
        validate_catalog(with_entries(entries))
    assert error.value.code=='invalid_catalog'
    assert 'Web' not in str(error.value) and 'Online' not in str(error.value)


def test_non_equality_and_lookup_vocabulary_are_rejected():
    with pytest.raises(SDKError):
        validate_catalog(with_entries((FilterValueDefinition('Web',('Online',)),),operators=('in',)))
    from sageql.sdk.vocabulary import validate_values
    from sageql import Column
    with pytest.raises(SDKError):
        validate_values(FullNameFilterDefinition('n','Name','name',('eq',),('name',),
            value_vocabulary=(FilterValueDefinition('Private name',('X',)),)),Column('t','name','text'))


@pytest.mark.parametrize('alias',['Web','Online','ONLINE','آنلاین'])
def test_host_mapping_supplies_owner_and_exact_canonical_value(alias):
    result=evidence(f'Billed amount for {alias} only in July 2026.')
    assert not result.missing
    assert result.filter_requirements[0].condition==UserFilter('channel_filter','eq',('Web',))


@pytest.mark.parametrize('text',['Billed amount; title "Online" in July 2026',
    'Billed amount; example "for Online only" in July 2026','Billed amount; unrelated Online word'])
def test_mentions_titles_and_examples_do_not_filter(text):
    assert not evidence(text).filter_requirements


def test_original_host_d03_still_clarifies_and_extended_contract_is_distinct(tmp_path):
    target=spec(filters=(UserFilter('channel_filter','eq',('Web',)),))
    original=original_host('workshop')[0]
    engine,adapter,client=make_engine(tmp_path,target,catalog=original)
    reply=submit(engine,'Billed amount for Web only in July 2026.')
    assert reply.status=='needs_clarification' and not adapter.calls and not client.calls


def test_registered_d03_executes_independent_580_and_replays_without_reads(tmp_path):
    target=spec(filters=(UserFilter('channel_filter','eq',('Web',)),))
    engine,adapter,client=make_engine(tmp_path,target)
    reply=submit(engine,'Billed amount for Web only in July 2026.')
    assert reply.status=='report_ready' and reply.report.rows==((Decimal(580),),)
    assert len(adapter.calls)==1 and len(client.calls)==3
    assert engine.submit(reply.session_id,'Billed amount for Web only in July 2026.',ACTOR,'first',0).to_dict()==reply.to_dict()
    assert len(adapter.calls)==1 and len(client.calls)==3


def test_ambiguous_owner_answer_survives_restart_and_keeps_period(tmp_path):
    target=spec(filters=(UserFilter('channel_filter','eq',('Web',)),))
    engine,adapter,client=make_engine(tmp_path,target,version='workshop-ambiguous-v1',
        client=ScriptedClient([extracted(target,turn_kind='answer'),ready(target),{'approved':True,'feedback':''}]))
    first=submit(engine,'Billed amount for Portal only in July 2026.')
    assert first.status=='needs_clarification' and not adapter.calls and not client.calls
    engine.sessions=SQLiteSessionStore(tmp_path/'sessions.sqlite')
    final=submit(engine,'Channel',first.session_id,'answer',first.revision)
    assert final.status=='report_ready' and final.report.rows==((Decimal(580),),)
    assert str(adapter.calls[0].period.start)=='2026-07-01'


def test_same_alias_for_two_values_in_one_filter_clarifies():
    catalog=with_entries((FilterValueDefinition('Web',('Portal',)),FilterValueDefinition('Desk',('Portal',))))
    validate_catalog(catalog)
    assert evidence('Billed amount; Channel = Portal',catalog=catalog).missing=='filter_value'


def test_value_only_extraction_cannot_consume_an_earlier_date_or_metric_clause():
    catalog=host('workshop','workshop-ambiguous-v1')[0]
    from sageql.sdk.evidence import evidence_question
    text='For July 2026 show Billed amount; only Portal.'
    initial=request_evidence((Message('user',text),),catalog)
    assert initial.pending_filter_value==('Portal','eq')
    question=evidence_question(initial,'en')
    completed=request_evidence((Message('user',text),Message('assistant',question.question),Message('user','Channel')),catalog)
    assert completed.period==PeriodSelection('month',year=2026,month=7)
    assert completed.metrics==(('jobs','billed'),)
    assert completed.filter_requirements[0].condition.values==('Web',)


@pytest.mark.parametrize('value',['Courier','ABC-123','  MiXeD  ك  '])
def test_free_form_owned_values_remain_valid_and_unchanged(value):
    result=evidence('Billed amount in July 2026; Channel = '+json.dumps(value,ensure_ascii=False))
    assert not result.missing
    assert result.filter_requirements[0].condition.values==(value,)


@pytest.mark.parametrize('literal,identifier,canonical',[
    ('Budget fee','fee_filter',Decimal('80.00')),('Opening day','completed_filter',date(2026,7,1)),
    ('Active records','voided_filter',False),('Half hour','minutes_filter',30),
])
def test_typed_aliases_preserve_canonical_scalars(literal,identifier,canonical):
    result=evidence('Billed amount for '+literal+' only in July 2026.',version='workshop-typed-v1')
    assert not result.missing
    assert result.filter_requirements[0].condition==UserFilter(identifier,'eq',(canonical,))


def test_restricted_mapping_does_not_influence_owner_or_resolve_ambiguity():
    catalog,policy,_=host('workshop','workshop-values-v1')
    scope=policy(ACTOR)
    scope=replace(scope,datasets=(replace(scope.datasets[0],filter_ids=('service_filter','technician_filter')),))
    visible=permitted_catalog(catalog,scope)
    assert all(f.id!='channel_filter' for d in visible.datasets for f in d.filters)
    result=evidence('Billed amount for Online only in July 2026.',catalog=visible)
    assert result.missing=='filter_value' and not result.filter_requirements


@pytest.mark.parametrize('domain,version,owner,identifier,alias,canonical',[
    ('retail','retail-values-v1','sales','department_filter','Reading','Books'),
    ('library','library-values-v1','loans','shelf_filter','علمی','Science')])
def test_relationship_imports_preserve_source_vocabulary_and_permissions(domain,version,owner,identifier,alias,canonical):
    catalog,policy,_=host(domain,version);validate_catalog(catalog)
    visible=permitted_catalog(catalog,policy(ACTOR))
    target=next(d for d in visible.datasets if d.id==owner)
    definition=next(f for f in target.filters if f.id==identifier)
    assert any(e.value==canonical for e in definition.value_vocabulary)
    from sageql.sdk.grounding import _typed
    assert _typed(alias,target,definition,'eq').values==(canonical,)
    source_id='products' if domain=='retail' else 'books'
    scope=policy(ACTOR);source=next(a for a in scope.datasets if a.dataset_id==source_id)
    restricted=replace(scope,datasets=tuple(replace(a,filter_ids=()) if a==source else a for a in scope.datasets))
    projected=permitted_catalog(catalog,restricted)
    assert identifier not in {f.id for d in projected.datasets if d.id==owner for f in d.filters}


@pytest.mark.parametrize('wrong',[spec(),spec(filters=(UserFilter('channel_filter','eq',('Desk',)),)),
    spec(filters=(UserFilter('service_filter','eq',('Web',)),))])
def test_custom_provider_omitted_wrong_value_or_wrong_filter_never_reads(tmp_path,wrong):
    engine,adapter,_=make_engine(tmp_path,wrong,provider=SimpleNamespace(interpret=lambda *args:Interpretation('ready',wrong)))
    reply=submit(engine,'Billed amount for Online only in July 2026.')
    assert reply.status=='blocked' and reply.error['code']=='intent_mismatch' and not adapter.calls


def test_private_canonical_value_never_enters_any_standard_stage_or_current_spec(tmp_path):
    target=spec(filters=(UserFilter('channel_filter','eq',('Web',)),))
    class ReferenceClient(ScriptedClient):
        def __init__(self):
            super().__init__([])
        def create(self,**options):
            payload=json.loads(options['messages'][-1]['content'])
            stage=options['response_format']['json_schema']['name']
            if stage.endswith('intent'):
                value=extracted(replace(target,filters=()),turn_kind='refine' if payload['current_spec'] else 'new')
            elif stage.endswith('interpretation'):
                token=payload['intent']['filters'][0]['values'][0]
                assert token.startswith('__sageql_value_')
                value=ready(replace(target,filters=(UserFilter('channel_filter','eq',(token,)),)))
            else:
                value={'approved':True,'feedback':''}
            self.responses=iter([value]);return super().create(**options)
    client=ReferenceClient();engine,adapter,_=make_engine(tmp_path,target,client=client)
    first=submit(engine,'Billed amount for Online only in July 2026.')
    assert first.status=='report_ready' and first.report.rows==((Decimal(580),),)
    second=submit(engine,'Keep the Channel filter and same metric.',first.session_id,'refine',first.revision)
    assert second.status=='report_ready' and len(adapter.calls)==2
    wire=json.dumps(client.calls,ensure_ascii=False)
    assert 'Web' not in wire and 'Counter' not in wire and 'حضوری' not in wire
    assert first.report.rows==second.report.rows


def test_unissued_or_wrong_filter_value_references_fail_closed():
    catalog=host('workshop','workshop-values-v1')[0]
    payload={'current_spec':spec(filters=(UserFilter('channel_filter','eq',('Web',)),)).to_dict()}
    public=project_payload(payload,catalog)
    token=public['current_spec']['filters'][0]['values'][0]
    assert 'Web' not in json.dumps(public)
    assert restore_response(public,catalog,json.dumps(public))['current_spec']['filters'][0]['values']==['Web']
    candidate={'spec':spec(filters=(UserFilter('service_filter','eq',(token,)),)).to_dict()}
    with pytest.raises(ValueError):restore_response(candidate,catalog,json.dumps(public))
    with pytest.raises(ValueError):restore_response({'spec':payload['current_spec']|{'filters':[{'filter_id':'channel_filter','operator':'eq','values':[token]}]}},catalog,'{}')
    with pytest.raises(ValueError):restore_response({'question':'Explain '+token},catalog,json.dumps(public))


def test_value_definition_repr_and_metadata_do_not_disclose_inventory():
    from sageql.sdk.provider import _metadata
    entry=FilterValueDefinition('Secret canonical',('Unasked secret alias',))
    catalog=with_entries((entry,));validate_catalog(catalog)
    assert 'Secret' not in repr(entry) and 'Unasked' not in repr(catalog.datasets[0].filters)
    public=json.dumps(_metadata(catalog))
    assert 'Secret canonical' not in public and 'Unasked secret alias' not in public


def test_requirement_ledger_respects_registered_value_roles_and_other_positive_operations(tmp_path):
    catalog=with_entries((FilterValueDefinition('Web',('Share of total',)),))
    target=spec(filters=(UserFilter('channel_filter','eq',('Web',)),))
    intent=extracted(target)
    intent['unsupported_requirements']=[{'operation':'percentage_share','evidence':'Share of total'}]
    client=ScriptedClient([intent,ready(target),{'approved':True,'feedback':''}])
    engine,adapter,_=make_engine(tmp_path,target,catalog=catalog,client=client)
    report=submit(engine,'Billed amount for Share of total only in July 2026.')
    assert report.status=='report_ready' and report.report.rows==((Decimal(580),),)
    refused=submit(engine,'Billed amount for Share of total only in July 2026; calculate an unregistered ratio.')
    assert refused.status=='unsupported' and len(adapter.calls)==1 and len(client.calls)==3


def test_string_enum_canonical_value_is_private_after_json_storage_round_trip(tmp_path):
    from enum import Enum
    class ChannelCode(str,Enum):
        WEB='Web'
    catalog=with_entries((FilterValueDefinition(ChannelCode.WEB,('Online',)),))
    validate_catalog(catalog)
    payload={'current_spec':spec(filters=(UserFilter('channel_filter','eq',(ChannelCode.WEB,)),)).to_dict()}
    persisted=json.loads(json.dumps(payload))
    assert persisted['current_spec']['filters'][0]['values']==['Web']
    wire=project_payload(persisted,catalog)
    assert 'Web' not in json.dumps(wire)
    assert restore_response(wire,catalog,json.dumps(wire))['current_spec']['filters'][0]['values']==['Web']
    target=spec(filters=(UserFilter('channel_filter','eq',('Web',)),))
    engine,_,_=make_engine(tmp_path,target,catalog=catalog)
    reply=submit(engine,'Billed amount for Online only in July 2026.')
    assert reply.status=='report_ready' and reply.report.rows==((Decimal(580),),)


def test_legacy_interpreter_can_copy_a_first_call_private_reference(tmp_path):
    from sageql import LLMConfig
    from sageql.sdk import OpenAIReportInterpreter
    target=spec(filters=(UserFilter('channel_filter','eq',('Web',)),))
    class FirstReferenceClient(ScriptedClient):
        def __init__(self):super().__init__([])
        def create(self,**options):
            payload=json.loads(options['messages'][-1]['content'])
            token=payload['host_filter_requirements'][0]['values'][0]
            assert token.startswith('__sageql_value_') and 'Web' not in json.dumps(payload)
            self.responses=iter([ready(replace(target,filters=(UserFilter('channel_filter','eq',(token,)),)))])
            return super().create(**options)
    client=FirstReferenceClient()
    provider=OpenAIReportInterpreter(LLMConfig('synthetic','https://example.test/v1','fake'),client=client,language='en')
    engine,adapter,_=make_engine(tmp_path,target,client=client,provider=provider)
    reply=submit(engine,'Billed amount for Online only in July 2026.')
    assert reply.status=='report_ready' and reply.report.rows==((Decimal(580),),) and len(client.calls)==1


@pytest.fixture(scope='module')
def measured():
    import socket
    def forbidden(*args,**kwargs):raise AssertionError('Live evaluation is not authorized')
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(socket.socket,'connect',forbidden)
        patch.setattr(socket.socket,'connect_ex',forbidden)
        patch.setattr(socket,'create_connection',forbidden)
        return {case['id']:run_trajectory(case) for case in load_cases()}


@pytest.mark.parametrize('identifier',[case['id'] for case in load_cases()])
def test_frozen_complete_spec_data_state_and_no_read_outcomes(identifier,measured):
    assert measured[identifier]['correct'],measured[identifier]


def test_original_d03_and_new_host_are_not_the_same_frozen_condition():
    from evaluations.trajectories import load_trajectories
    old=next(case for case in load_trajectories('development') if case['id']=='D03')
    new=next(case for case in load_cases() if case['id']=='V01')
    assert old['turns'][0]['request']==new['turns'][0]['request']
    assert old['turns'][0]['expect']['kind']=='report' and 'host_version' not in old
    assert new['host_version']=='workshop-values-v1'
    assert next(case for case in load_cases() if case['id']=='A10')['cohort']=='phase05_development'
    assert next(case for case in load_cases() if case['id']=='A13')['cohort']=='phase05_assessment'


def test_longest_alias_boundaries_and_free_form_are_distinct():
    catalog=with_entries((FilterValueDefinition('Web',('Online',)),FilterValueDefinition('Desk',('Online priority',))))
    validate_catalog(catalog)
    result=evidence('Billed amount for Online priority only in July 2026.',catalog=catalog)
    assert result.filter_requirements[0].condition.values==('Desk',)
    assert evidence('Billed amount for Onlineish only in July 2026.',catalog=catalog).missing=='filter_value'
    assert evidence('Billed amount; Channel = Onlineish',catalog=catalog).filter_requirements[0].condition.values==('Onlineish',)


@pytest.mark.parametrize('operand',['Online premium','"Online premium"','Online premium only'])
def test_registered_prefix_cannot_ground_a_longer_unknown_value(operand):
    result=evidence('Billed amount for '+operand+' in July 2026.')
    assert result.missing=='filter_value' and not result.filter_requirements
    assert result.pending_filter_value==('Online premium','eq')


def test_whole_quoted_alias_is_a_predicate_and_compound_terms_keep_connectors():
    assert evidence('Billed amount for "Online" only in July 2026.').filter_requirements[0].condition.values==('Web',)
    catalog=with_entries((FilterValueDefinition('Web',('Research and Development',)),))
    assert evidence('Billed amount for Research and Development only in July 2026.',catalog=catalog).filter_requirements[0].condition.values==('Web',)
    assert evidence('Billed amount; exclude Online premium').pending_filter_value==('Online premium','neq')


def test_metric_alias_collision_does_not_create_an_unrequested_predicate():
    catalog=host('workshop','workshop-collision-v1')[0]
    assert not evidence('Completed jobs by Service in July 2026.',catalog=catalog).filter_requirements
    assert evidence('Billed amount for Completed jobs only in July 2026.',catalog=catalog).missing=='filter_value'
    explicit=evidence('Billed amount; Channel = Completed jobs',catalog=catalog)
    assert explicit.filter_requirements[0].condition.values==('Web',)


@pytest.mark.parametrize('identifier,value',[
    ('fee_filter',Decimal('1e39')),('fee_filter',float('nan')),
    ('completed_filter','2026-02-30'),('voided_filter',0),('minutes_filter',True),
])
def test_canonical_type_errors_reuse_existing_scalar_validation(identifier,value):
    catalog=host('workshop','workshop-typed-v1')[0];dataset=catalog.datasets[0]
    filters=tuple(replace(f,value_vocabulary=(FilterValueDefinition(value,('Private term',)),)) if f.id==identifier else f
                  for f in dataset.filters)
    with pytest.raises(SDKError) as error:validate_catalog(replace(catalog,datasets=(replace(dataset,filters=filters),)))
    assert error.value.code=='invalid_catalog' and 'Private term' not in str(error.value)


def test_catalog_total_bound_prevents_unbounded_vocabulary_work():
    catalog=original_host('workshop')[0];dataset=catalog.datasets[0]
    entries=tuple(FilterValueDefinition(str(i),(f'Value {i}',)) for i in range(64))
    filters=tuple(FilterDefinition(f'f{i}',f'Filter {i}','channel',value_vocabulary=entries) for i in range(17))
    with pytest.raises(SDKError):validate_catalog(replace(catalog,datasets=(replace(dataset,filters=filters),)))


def test_in_aliases_and_decimal_date_tokens_round_trip_through_standard_transport(tmp_path):
    target=spec(filters=(UserFilter('channel_filter','in',('Web','Desk')),))
    result=evidence('Billed amount; Channel in (Online, Counter)')
    assert result.filter_requirements[0].condition==target.filters[0]
    engine,adapter,_=make_engine(tmp_path,target)
    reply=submit(engine,'Billed amount in July 2026; Channel in (Online, Counter)')
    assert reply.status=='report_ready' and reply.report.rows==((Decimal(860),),)
    catalog=host('workshop','workshop-typed-v1')[0]
    for identifier,value in [('fee_filter',Decimal('80.00')),('completed_filter',date(2026,7,1))]:
        payload={'current_spec':spec(filters=(UserFilter(identifier,'eq',(value,)),)).to_dict()}
        wire=project_payload(payload,catalog)
        assert str(value) not in json.dumps(wire)
        assert restore_response(wire,catalog,json.dumps(wire))['current_spec']['filters'][0]['values']==payload['current_spec']['filters'][0]['values']


def test_canonical_parameter_unicode_whitespace_and_sql_text_remain_exact(tmp_path):
    canonical="  MiXeD  ك  '; DROP TABLE jobs;--  "
    catalog=with_entries((FilterValueDefinition(canonical,('Private category',)),))
    target=spec(filters=(UserFilter('channel_filter','eq',(canonical,)),))
    engine,adapter,_=make_engine(tmp_path,target,catalog=catalog)
    reply=submit(engine,'Billed amount for Private category only in July 2026.')
    assert reply.status=='report_ready' and reply.report.rows==((None,),)
    from sageql.sdk.adapters import compile_report
    from sageql.sdk import ExecutionLimits
    for dialect in ['sqlite','tsql']:
        compiled=compile_report(adapter.calls[0],ExecutionLimits(),dialect=dialect)
        assert canonical not in compiled.sql and canonical in compiled.parameters


def test_vocabulary_revision_invalidates_old_saved_report_and_receipt(tmp_path):
    target=spec(filters=(UserFilter('channel_filter','eq',('Web',)),))
    engine,adapter,_=make_engine(tmp_path,target)
    request='Billed amount for Online only in July 2026.'
    first=submit(engine,request)
    catalog=replace(with_entries((FilterValueDefinition('Web',('Digital',)),)),version=engine.catalog.version)
    updated=SageQL(catalog=catalog,policy=original_host('workshop')[1],database=adapter,provider=engine.provider,
        sessions=SQLiteSessionStore(tmp_path/'sessions.sqlite'),clock=lambda:TODAY,execution='validated',language='en')
    with pytest.raises(SDKError) as error:updated.get_report(first.session_id,first.report.id,ACTOR)
    assert error.value.code=='access_denied'
    cached=updated.submit(first.session_id,request,ACTOR,'first',0)
    assert cached.status=='blocked' and cached.error['code']=='request_conflict'
    assert len(adapter.calls)==1
