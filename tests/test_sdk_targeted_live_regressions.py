"""Regressions from the stopped targeted run; original frozen answers unchanged."""
from dataclasses import replace
import json

import pytest

from sageql.sdk import Interpretation, PeriodSelection
from evaluations.phase14 import load_cases
from evaluations.runner import ScriptedClient, extracted, ready
from evaluations.trajectories import run_trajectory
from tests.test_sdk_semantic_evidence import engine_at, submit, APPROVED
from tests.test_sdk_year_answer_recovery import desired


def test_named_month_refinement_keeps_typed_period_when_model_uses_equal_range(tmp_path):
    target=desired();same=replace(target,period=PeriodSelection('range','2026-09-01','2026-10-01'))
    engine,adapter,client=engine_at(tmp_path,responses=[extracted(target),ready(target),APPROVED,
        extracted(same,turn_kind='refine'),ready(same),APPROVED])
    first=submit(engine,'Tabulate Units sold by Department in September 2026.')
    second=submit(engine,'Keep the same report and period.',session=first.session_id,revision=first.revision,request='refine')
    assert second.status=='report_ready'
    assert client.calls[-1]['response_format']['json_schema']['name']=='sageql_report_review'
    reviewed=json.loads(client.calls[-1]['messages'][-1]['content'])['candidate']['spec']['period']
    assert reviewed['kind']=='month' and reviewed['year']==2026 and reviewed['month']==9
    assert len(adapter.calls)==2 and second.report.rows==first.report.rows


def test_provider_neutral_equal_range_canonicalizes_only_to_user_selected_month(tmp_path):
    from types import SimpleNamespace
    target=desired();same=replace(target,period=PeriodSelection('range','2026-09-01','2026-10-01'))
    engine,adapter,_=engine_at(tmp_path,provider=SimpleNamespace(interpret=lambda *a:Interpretation('ready',same)))
    reply=submit(engine,'Units sold by Department in September 2026 as a table.')
    assert reply.status=='report_ready'
    assert adapter.calls[0].spec.period==target.period


@pytest.mark.parametrize('start,end',[('2026-09-02','2026-10-01'),('2026-09-01','2026-10-02'),('2025-09-01','2025-10-01')])
def test_different_range_is_never_accepted_as_the_requested_month(tmp_path,start,end):
    from types import SimpleNamespace
    wrong=replace(desired(),period=PeriodSelection('range',start,end))
    engine,adapter,_=engine_at(tmp_path,provider=SimpleNamespace(interpret=lambda *a:Interpretation('ready',wrong)))
    reply=submit(engine,'Units sold by Department in September 2026 as a table.')
    assert reply.status=='blocked' and not adapter.calls


def test_explicit_date_range_is_preserved_as_a_range(tmp_path):
    target=replace(desired(),period=PeriodSelection('range','2026-09-01','2026-10-01'))
    engine,adapter,_=engine_at(tmp_path,responses=[extracted(target),ready(target),APPROVED])
    reply=submit(engine,'Tabulate Units sold by Department from 2026-09-01 before 2026-10-01.')
    assert reply.status=='report_ready' and adapter.calls[0].spec.period==target.period


def test_confirmed_owner_and_year_answers_override_model_new_turn_tag():
    case=load_cases(case_ids=['N02'])[0]
    def client(turn,target,catalog):
        # Local known-slot questions need no model. The model wrongly tags a
        # year answer as new; the trusted pending role still owns continuation.
        return ScriptedClient([extracted(target,period=None,missing=('period',),turn_kind='new'),
            {'status':'needs_clarification','spec':None,'question':'Which year should July use?','message':''},APPROVED]
            if turn['expect']['kind']=='clarification' else [extracted(target,turn_kind='new'),ready(target),APPROVED])
    result=run_trajectory(case,client_factory=client)
    assert result['correct'],[(t['index'],t['outcome'],t['safe_errors']) for t in result['turns']]


@pytest.mark.parametrize('answer', ['Not Channel.', 'Use Unknown filter for Portal.',
    'Use Channel or Service filter for Portal.',
    'Start a new report: Completed jobs for June 2026 in a table.'])
def test_unconfirmed_or_explicit_new_requests_do_not_gain_confirmed_answer_role(answer):
    from sageql import Message
    from sageql.sdk.evidence import request_evidence
    from evaluations.phase05_hosts import host
    catalog,_,_=host('workshop','workshop-ambiguous-v1')
    original=load_cases(case_ids=['N02'])[0]['turns'][0]['request']
    evidence=request_evidence((Message('user',original),Message('assistant',
        'Which registered filters and exact values should I use, retain or remove? Please clarify the selections.'),
        Message('user',answer)),catalog)
    assert not evidence.confirmed_clarification_answer


def test_fixed_year_and_comparison_periods_canonicalize_without_changing_filters():
    from sageql.sdk.evidence import RequestEvidence,canonical_fixed_periods
    from datetime import date
    from sageql.sdk import UserFilter
    year=PeriodSelection('year',year=2026);month=PeriodSelection('month',year=2025,month=9)
    source=replace(desired(),period=PeriodSelection('range','2026-01-01','2027-01-01'),
        comparison=PeriodSelection('range','2025-09-01','2025-10-01'),filters=(UserFilter('department_filter','eq',('Books',)),))
    result=canonical_fixed_periods(RequestEvidence(period=year,comparison=month),source,date(2026,10,28))
    assert result.period==year and result.comparison==month and result.filters==source.filters


def test_relative_period_still_freezes_dates_across_business_clock_change(tmp_path):
    from types import SimpleNamespace
    from datetime import date
    relative=replace(desired(),period=PeriodSelection('this_month'))
    frozen=replace(relative,period=PeriodSelection('range','2026-09-01','2026-10-01'))
    decisions=iter([relative,frozen])
    engine,adapter,_=engine_at(tmp_path,provider=SimpleNamespace(interpret=lambda *a:Interpretation('ready',next(decisions))))
    engine._clock=lambda:date(2026,9,15)
    first=submit(engine,'Units sold by Department this month in a table.')
    engine._clock=lambda:date(2026,10,15)
    second=submit(engine,'Keep the same report.',session=first.session_id,revision=first.revision,request='later')
    assert second.status=='report_ready' and first.report.rows==second.report.rows
    assert adapter.calls[-1].spec.period==frozen.period


def test_later_relative_selection_does_not_reuse_an_older_equal_fixed_month():
    from datetime import date
    from sageql import Message
    from sageql.sdk.evidence import request_evidence,canonical_fixed_periods
    from examples.multi_domain import retail_catalog
    current=replace(desired(),period=PeriodSelection('range','2026-09-01','2026-10-01'))
    messages=(Message('user','Units sold by Department in September 2026.'),
        Message('assistant','Report ready.'),Message('user','Use this month instead.'),
        Message('assistant','Report ready.'),Message('user','Keep the same report.'))
    evidence=request_evidence(messages,retail_catalog(),current)
    assert canonical_fixed_periods(evidence,current,date(2026,11,1),messages=messages,
        catalog=retail_catalog(),current_spec=current).period==current.period
