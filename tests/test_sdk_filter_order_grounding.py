"""Independent filter/order gate regressions through real policies and adapters."""
from dataclasses import replace
from decimal import Decimal
import json
import socket
from types import SimpleNamespace

import pytest

from sageql import Column, Message
from sageql.sdk import (DatasetAccess, FilterDefinition, Interpretation, MetricDefinition,
                        PeriodSelection, ReportSpec, SageQL, SQLiteSessionStore, UserFilter)
from sageql.sdk.evidence import request_evidence, evidence_feedback
from sageql.sdk.semantics import permitted_catalog
from evaluations.phase03_hosts import ACTOR, TODAY, host, workshop_catalog
from evaluations.phase04 import load_cases
from evaluations.trajectories import run_trajectory


def spec(**changes):
    return replace(ReportSpec('jobs',('billed',),period=PeriodSelection('month',year=2026,month=7)),**changes)


def evidence(text, *, catalog=None, current=None):
    return request_evidence((Message('user',text),),catalog or workshop_catalog(),current)


def engine_at(tmp_path, requested, *, catalog=None, policy=None):
    from evaluations.runner import RecordingAdapter
    original, original_policy, create = host('workshop')
    path=tmp_path/'facts.sqlite'; create(path)
    adapter=RecordingAdapter(path)
    provider=SimpleNamespace(interpret=lambda *args: Interpretation('ready',requested))
    engine=SageQL(catalog=catalog or original,policy=policy or original_policy,provider=provider,database=adapter,
                  sessions=SQLiteSessionStore(tmp_path/'sessions.sqlite'),clock=lambda:TODAY,execution='validated',language='en')
    return engine,adapter


def submit(engine,text,session=None,revision=0,request='first'):
    session=session or engine.create_session(ACTOR).session_id
    return engine.submit(session,text,ACTOR,request,revision)


@pytest.fixture(scope='module')
def measured():
    def forbidden(*args,**kwargs): raise AssertionError('No remote evaluation calls authorized')
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(socket.socket,'connect',forbidden)
        patch.setattr(socket,'create_connection',forbidden)
        return {c['id']:run_trajectory(c) for c in load_cases()}


@pytest.mark.parametrize('identifier',[c['id'] for c in load_cases()])
def test_frozen_independent_spec_data_order_and_session_outcomes(identifier,measured):
    assert measured[identifier]['correct'],measured[identifier]


@pytest.mark.parametrize('text,operator',[
    ('Channel = Web','eq'),('Channel equals "Web"','eq'),('only Channel Web','eq'),
    ('Channel != Web','neq'),('Channel is not Web','neq'),('exclude Channel Web','neq'),
    ('فقط Channel برابر «Web»','eq'),('Channel برابر Web','eq'),
])
def test_exact_identity_operator_literal_and_surface_case(text,operator):
    result=evidence('Billed amount in July 2026; '+text)
    assert not result.missing
    assert result.filter_requirements[0].condition==UserFilter('channel_filter',operator,('Web',))


@pytest.mark.parametrize('text',[
    'Billed amount for Web only in July 2026', 'Billed amount; include only Web',
    'Billed amount; Channel =', 'Billed amount; Channel = Web; Channel = Phone',
])
def test_unbound_missing_or_conflicting_values_clarify(text):
    assert evidence(text).missing=='filter_value'


@pytest.mark.parametrize('text',[
    'Billed amount by Channel', 'Billed amount; title "Channel = Web"',
    'Billed amount; example "Channel = Web"', 'Billed amount; unrelated Web word',
])
def test_mentions_grouping_titles_examples_and_unrelated_words_do_not_invent_filters(text):
    assert not evidence(text).filter_requirements


def test_literal_values_do_not_select_metrics_dates_operations_or_directions():
    result=evidence('Billed amount in July 2026; Channel = "Work minutes daily highest share of total September 2025"')
    assert result.metrics==(('jobs','billed'),) and not result.operations
    assert result.time_grain is None and result.ordering is None and not result.missing
    assert result.period==PeriodSelection('month',year=2026,month=7)


def test_same_permitted_filter_label_remains_ambiguous_and_dataset_context_disambiguates_imports():
    catalog=workshop_catalog(); fact=catalog.datasets[0]
    catalog=replace(catalog,datasets=(replace(fact,filters=(*fact.filters,FilterDefinition('other','Channel','service'))),))
    assert evidence('Billed amount; Channel = Web',catalog=catalog).missing=='filter_value'
    # Same literal across different registered concepts is not an ambiguity
    # when the user explicitly names its business owner.
    result=evidence('Billed amount; Channel = Web; Service = Web')
    assert {r.condition.filter_id for r in result.filter_requirements}=={'channel_filter','service_filter'}


@pytest.mark.parametrize('kind,value,expected', [('int','12',12),('decimal','12.50',Decimal('12.50')),
                                              ('bit','true',True),('nvarchar(50)','Unknown category','Unknown category')])
def test_free_form_typed_values_need_no_static_enumeration(kind,value,expected):
    catalog=workshop_catalog(); fact=catalog.datasets[0]
    fact=replace(fact,columns=(*fact.columns,Column(fact.table.key,'typed',kind)),filters=(FilterDefinition('typed_filter','Choice','typed'),))
    result=evidence('Billed amount; Choice = '+value,catalog=replace(catalog,datasets=(fact,)))
    assert not result.missing and result.filter_requirements[0].condition.values==(expected,)


def test_unregistered_operator_and_invalid_type_are_not_grounded_as_valid():
    catalog=workshop_catalog(); fact=catalog.datasets[0]
    catalog=replace(catalog,datasets=(replace(fact,filters=(FilterDefinition('choice','Choice','minutes',('eq',)),)),))
    assert evidence('Billed amount; Choice != 12',catalog=catalog).missing=='filter_value'
    assert evidence('Billed amount; Choice = twelve',catalog=catalog).missing=='filter_value'


@pytest.mark.parametrize('descending,phrase,rows',[(True,'highest',(('Install',500),('Repair',300),('Tune',60))),
    (False,'lowest',(('Tune',60),('Repair',300),('Install',500)))])
def test_actual_numeric_order_and_parameterized_category_under_tenant_policies(tmp_path,descending,phrase,rows):
    requested=spec(dimension_ids=('service',),order_by='billed',descending=descending)
    engine,adapter=engine_at(tmp_path,requested)
    reply=submit(engine,'Billed amount by Service in July 2026; '+phrase+' Billed amount first')
    assert reply.status=='report_ready' and reply.report.rows==rows and len(adapter.calls)==1


def test_actual_neq_filter_and_sql_parameter_binding(tmp_path):
    requested=spec(filters=(UserFilter('channel_filter','neq',('Web',)),))
    engine,adapter=engine_at(tmp_path,requested)
    reply=submit(engine,'Billed amount in July 2026; exclude Channel Web')
    assert reply.report.rows==((280,),) and len(adapter.calls)==1
    from sageql.sdk import ExecutionLimits
    from sageql.sdk.adapters import compile_report
    for dialect in ('sqlite','tsql'):
        query=compile_report(adapter.calls[0],ExecutionLimits(),dialect=dialect)
        assert 'Web' not in query.sql and 'Web' in query.parameters


@pytest.mark.parametrize('change',[{'filters':()}, {'filters':(UserFilter('service_filter','eq',('Web',)),)},
    {'filters':(UserFilter('channel_filter','eq',('Phone',)),)}, {'filters':(UserFilter('channel_filter','neq',('Web',)),)}])
def test_custom_provider_cannot_omit_change_owner_value_or_polarity(tmp_path,change):
    engine,adapter=engine_at(tmp_path,spec(**change))
    reply=submit(engine,'Billed amount in July 2026; Channel = Web')
    assert reply.status=='blocked' and reply.error['code']=='intent_mismatch' and not adapter.calls
    assert 'Web' not in json.dumps(reply.error)


def test_authorized_metadata_does_not_grant_a_hidden_filter_or_reveal_it(tmp_path):
    original,policy,_=host('workshop')
    def restricted(actor):
        return replace(policy(actor),datasets=(DatasetAccess('jobs',filter_ids=('service_filter',),policies=policy(actor).datasets[0].policies),))
    requested=spec(filters=(UserFilter('channel_filter','eq',('Web',)),))
    engine,adapter=engine_at(tmp_path,requested,policy=restricted)
    reply=submit(engine,'Billed amount in July 2026; Channel = Web')
    assert reply.error['code']=='access_denied' and not adapter.calls
    visible=permitted_catalog(original,restricted(ACTOR))
    assert not evidence('Channel = Web',catalog=visible).filter_requirements


def test_failure_retains_success_saved_spec_receipt_and_earlier_report(tmp_path):
    initial=spec(filters=(UserFilter('channel_filter','eq',('Web',)),),dimension_ids=('service',),order_by='billed',descending=True)
    engine,adapter=engine_at(tmp_path,initial)
    first=submit(engine,'Billed amount by Service in July 2026; Channel = Web; highest Billed amount first')
    assert first.status=='report_ready'
    engine.sessions=SQLiteSessionStore(tmp_path/'sessions.sqlite')
    text='Reverse the ordering; keep the Channel filter'
    failed=submit(engine,text,first.session_id,first.revision,'bad')
    assert failed.status=='blocked' and failed.revision==first.revision
    assert submit(engine,text,first.session_id,first.revision,'bad').to_dict()==failed.to_dict()
    assert len(adapter.calls)==1
    assert engine.get_report(first.session_id,first.report.id,ACTOR).to_dict()==first.report.to_dict()
    saved=engine.get_session(first.session_id,ACTOR)
    assert saved['last_report_id']==first.report.id


@pytest.mark.parametrize('phrase,direction', [('highest Billed amount first',True),('lowest Billed amount first',False),
    ('largest Billed amount first',True),('smallest Billed amount first',False),('sort by Billed amount descending',True),
    ('Billed amount نزولی',True),('Billed amount صعودی',False)])
def test_direction_constraints_are_independent_of_provider_agreement(phrase,direction):
    result=evidence('Billed amount by Service in July 2026; '+phrase)
    assert result.ordering.target=='billed' and result.ordering.descending is direction
    assert evidence_feedback(result,spec(dimension_ids=('service',),order_by='billed',descending=not direction),TODAY)=='explicit_ordering_mismatch'


@pytest.mark.parametrize('phrase',['highest first','lowest first','most first'])
def test_multiple_requested_sort_metrics_do_not_acquire_an_arbitrary_target(phrase):
    assert evidence('Billed amount and Completed jobs; '+phrase).missing=='ordering'


def test_registered_dimension_sort_does_not_invent_a_numeric_ranking_or_direction():
    result=evidence('Billed amount by Service; sort by Service')
    assert result.ordering.target=='service' and result.ordering.descending is None and result.ordering.limit is None


def test_model_predicate_does_not_provide_evidence_for_a_value_only_request(tmp_path):
    requested=spec(filters=(UserFilter('channel_filter','eq',('Web',)),))
    engine,adapter=engine_at(tmp_path,requested)
    reply=submit(engine,'Billed amount for Web only in July 2026')
    assert reply.status=='blocked' and not adapter.calls


@pytest.mark.parametrize('value',['A  B','Straße','وب  فارسی','يک كالا','۱٢۳','highest; daily, amount'])
def test_quoted_text_literals_preserve_exact_original_unicode_and_internal_whitespace(value):
    result=evidence('Billed amount; Channel = "'+value+'"')
    assert result.filter_requirements[0].condition.values==(value,) and not result.missing


@pytest.mark.parametrize('text', ['Channel in ("Web", "Phone")', 'filter Channel in [Web, Phone]'])
def test_registered_in_operator_preserves_complete_member_set(text):
    result=evidence('Billed amount; '+text)
    assert not result.missing
    assert result.filter_requirements[0].condition==UserFilter('channel_filter','in',('Web','Phone'))


@pytest.mark.parametrize('text',['Channel in ()','filter Channel in Web or Phone','Channel in (Web,)',
                               'Channel in (Web, Phone'])
def test_incomplete_or_unbounded_list_language_cannot_become_a_partial_filter(text):
    assert evidence('Billed amount; '+text).missing=='filter_value'


@pytest.mark.parametrize('text,expected',[('Channel =','Web'),('Channel equals','Web')])
def test_pending_filter_identity_and_period_survive_a_literal_answer_and_restart(tmp_path,text,expected):
    from sageql import LLMConfig
    from sageql.sdk import OpenAIReportAgent
    from evaluations.runner import ScriptedClient, extracted, ready
    target=spec(filters=(UserFilter('channel_filter','eq',(expected,)),))
    engine,adapter=engine_at(tmp_path,target)
    client=ScriptedClient([extracted(target,turn_kind='answer'),ready(target),{'approved':True,'feedback':''}])
    engine.provider=OpenAIReportAgent(LLMConfig('synthetic','https://example.test/v1','fake'),client=client,language='en')
    first=submit(engine,'Billed amount in July 2026; '+text)
    assert first.status=='needs_clarification' and not adapter.calls
    engine.sessions=SQLiteSessionStore(tmp_path/'sessions.sqlite')
    answer=submit(engine,expected,first.session_id,first.revision,'answer')
    assert answer.status=='report_ready' and answer.report.rows==((580,),)


def test_pending_order_target_keeps_original_direction_and_date():
    from sageql.sdk.evidence import evidence_question
    text='Billed amount and Completed jobs by Service in July 2026; highest first'
    prior=evidence(text)
    question=evidence_question(prior,'en')
    resolved=request_evidence((Message('user',text),Message('assistant',question.question),
                              Message('user','Billed amount')),workshop_catalog())
    assert not resolved.missing and resolved.ordering.target=='billed' and resolved.ordering.descending
    assert resolved.period==PeriodSelection('month',year=2026,month=7)


def test_rejecting_one_sort_direction_does_not_remove_the_metric_from_the_output():
    result=evidence('Billed amount by Service; do not sort Billed amount ascending; sort by Billed amount descending')
    assert not result.excluded_metrics and not result.missing
    assert result.ordering.target=='billed' and result.ordering.descending


@pytest.mark.parametrize('text,direction',[('from highest to lowest',True),('از بیشترین به کمترین',True),
                                         ('from lowest to highest',False),('از کمترین به بیشترین',False)])
def test_directional_ranges_are_not_conflicting_directions(text,direction):
    result=evidence('Billed amount by Service; '+text)
    assert not result.missing and result.ordering.descending is direction


def test_ordering_a_direct_quoted_selection_uses_its_registered_dimension():
    result=evidence('Billed amount by Service; sort by "Service" ascending')
    assert not result.missing and result.ordering.target=='service' and result.ordering.descending is False


def test_filter_and_order_retention_do_not_apply_to_explicit_new_reports():
    current=spec(filters=(UserFilter('channel_filter','eq',('Web',)),),dimension_ids=('service',),order_by='billed',descending=True,limit=2)
    result=evidence('New report: show Completed jobs in June 2026',current=current)
    assert not result.filter_requirements and result.ordering is None


def test_two_conjunctive_predicates_on_one_category_are_preserved():
    result=evidence('Billed amount; Channel = Web; exclude Channel Phone')
    assert not result.missing and len(result.filter_requirements)==2
    target=spec(filters=(UserFilter('channel_filter','eq',('Web',)),UserFilter('channel_filter','neq',('Phone',))))
    assert evidence_feedback(result,target,TODAY) is None
    assert evidence_feedback(result,replace(target,filters=target.filters[:1]),TODAY)=='explicit_filter_mismatch'


def test_explicit_keep_does_not_get_replaced_by_a_new_exclusion_of_another_value():
    from sageql.sdk.evidence import anchor_intent
    from sageql.sdk import ConceptRef,ReportIntent
    current=spec(filters=(UserFilter('channel_filter','eq',('Web',)),))
    result=evidence('Keep the Channel filter; exclude Channel Phone',current=current)
    assert not result.missing
    intent=anchor_intent(ReportIntent(metrics=(ConceptRef('jobs','billed'),),filters=()),result)
    assert set(intent.filters)=={*current.filters,UserFilter('channel_filter','neq',('Phone',))}
    assert evidence_feedback(result,replace(current,filters=intent.filters),TODAY) is None


def test_supported_in_filter_executes_all_members_and_preserves_policies(tmp_path):
    target=spec(filters=(UserFilter('channel_filter','in',('Web','Desk')),))
    engine,adapter=engine_at(tmp_path,target)
    reply=submit(engine,'Billed amount in July 2026; Channel in ("Web", "Desk")')
    assert reply.status=='report_ready' and reply.report.rows==((860,),)
    assert len(adapter.calls)==1


@pytest.mark.parametrize('text',['Channel = Web; exclude Channel Web','Channel in (Web, Phone); Channel = Store'])
def test_logically_contradictory_category_conditions_require_clarification(text):
    assert evidence('Billed amount; '+text).missing=='filter_value'


def test_injection_like_literal_remains_a_bound_value_and_never_an_operation(tmp_path):
    value="x'); DROP TABLE workshop_jobs; --"
    target=spec(filters=(UserFilter('channel_filter','eq',(value,)),))
    engine,adapter=engine_at(tmp_path,target)
    reply=submit(engine,'Billed amount in July 2026; Channel = "'+value+'"')
    assert reply.status=='report_ready' and reply.report.rows==((None,),)
    from sageql.sdk import ExecutionLimits
    from sageql.sdk.adapters import compile_report
    for dialect in ('sqlite','tsql'):
        query=compile_report(adapter.calls[0],ExecutionLimits(),dialect=dialect)
        assert value not in query.sql and value in query.parameters


@pytest.mark.parametrize('text',[
    'Show the five technicians with the highest Billed amount',
    'Show five technicians with highest Billed amount',
    '۵ تکنسین با بیشترین Billed amount',
])
def test_counted_highest_selection_preserves_direction_metric_and_limit(text):
    result=evidence(text)
    assert result.ordering.target=='billed' and result.ordering.descending and result.ordering.limit==5
    assert evidence_feedback(result,spec(order_by='billed',descending=True,limit=100),TODAY)=='explicit_limit_mismatch'


def test_requested_secondary_ordering_is_transparently_unsupported(tmp_path):
    target=spec(dimension_ids=('service',),order_by='billed',descending=True)
    engine,adapter=engine_at(tmp_path,target)
    reply=submit(engine,'Billed amount by Service in July 2026; sort by Billed amount descending, then by Service')
    assert reply.status=='unsupported' and not adapter.calls


def test_persian_value_only_filter_scope_without_a_registered_owner_is_unresolved():
    assert evidence('Billed amount in July 2026; فقط برای وب').missing=='filter_value'


def test_unknown_prior_filter_value_is_never_reconstructed_from_a_provider():
    assert evidence('Keep the Channel filter').missing=='filter_value'


def test_negated_in_list_does_not_turn_into_a_positive_selection(tmp_path):
    target=spec(filters=(UserFilter('channel_filter','in',('Web','Desk')),))
    engine,adapter=engine_at(tmp_path,target)
    reply=submit(engine,'Billed amount in July 2026; exclude Channel in (Web, Desk)')
    assert reply.status=='unsupported' and not adapter.calls


def test_comma_separates_named_predicates_but_is_preserved_inside_quoted_data():
    result=evidence('Billed amount; Channel = "Web, highest", Service = Repair')
    assert not result.missing and len(result.filter_requirements)==2
    assert {r.condition.values for r in result.filter_requirements}=={('Web, highest',),('Repair',)}
    assert result.ordering is None
