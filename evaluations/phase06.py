"""Phase 06 readiness. Offline by default; live is a separately reviewed command."""
import argparse
from collections import Counter
from hashlib import sha256
import json
from pathlib import Path
import platform

from evaluations.phase06_runtime import Budget, Journal, atomic_json, run_lock, validate_approval
from evaluations.phase06_transport import ObservedClient, mock_client
from evaluations.trajectories import run_trajectory, summarize_trajectories, fraction
from evaluations.scoring import assess, Assessment

ROOT = Path(__file__).with_name('phase06')


def assess_outcome(expected, reply, **options):
    result = assess(expected, reply, **options)
    terms = expected.get('question_keywords_any')
    if expected['kind'] == 'clarification' and reply['status'] == 'needs_clarification' and terms:
        question = reply.get('clarification') or ''
        detail = any(term.casefold() in question.casefold() for term in terms)
        return Assessment('incorrect_rejection' if result.outcome == 'correct_clarification' and not detail else result.outcome,
                          {**result.checks, 'clarification_detail': detail})
    return result


def load_cases(cohort='all', case_ids=None):
    freeze = json.loads((ROOT / 'freeze.v4.json').read_text(encoding='utf-8'))
    for name, expected in freeze['files'].items():
        if sha256((ROOT.parents[1] / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen Phase 06 inputs changed; preserve and version corrections')
    cases = json.loads((ROOT / 'cases.v4.json').read_text(encoding='utf-8'))['cases']
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate evaluation IDs')
    cases = [c for c in cases if cohort == 'all' or c['cohort'] == 'phase06_' + cohort]
    if case_ids:
        if set(case_ids) - {c['id'] for c in cases}:
            raise ValueError('Unknown evaluation case')
        cases = [c for c in cases if c['id'] in case_ids]
    if not cases:
        raise ValueError('Empty evaluation selection')
    return cases


def configuration(cases, mode, endpoint, model, *, corpus_root=None, corpus_version='v4', max_structured_repairs=0,
                  stage_models=None, reasoning_effort=None):
    if type(max_structured_repairs) is not int or max_structured_repairs not in (0, 1):
        raise ValueError('Structured repairs must be explicitly bounded to zero or one')
    if (stage_models or reasoning_effort) and mode != 'live':
        raise ValueError('Per-stage model settings apply only to live comparisons')
    # Absent settings keep earlier configuration hashes and approvals unchanged.
    stage = {**({'stage_models': dict(stage_models)} if stage_models else {}),
             **({'reasoning_effort': reasoning_effort if isinstance(reasoning_effort, str)
                 else dict(reasoning_effort)} if reasoning_effort else {})}
    import sageql
    corpus = ROOT if corpus_root is None else Path(corpus_root)
    source = Path(sageql.__file__).parent
    digest = sha256()
    for file in sorted(source.rglob('*.py')):
        digest.update(file.relative_to(source).as_posix().encode()); digest.update(file.read_bytes())
    return {**({'max_structured_repairs': max_structured_repairs} if max_structured_repairs else {}), **stage,
            'mode': mode, 'adapter': 'sdk_chat_completions', 'endpoint': endpoint if mode == 'live' else None,
            'model': model if mode == 'live' else 'scripted',
            'case_ids': [c['id'] for c in cases],
            'selection_sha256': sha256(json.dumps(cases, sort_keys=True, ensure_ascii=False).encode()).hexdigest(),
            'corpus_sha256': sha256((corpus / f'cases.{corpus_version}.json').read_bytes()).hexdigest(),
            'freeze_sha256': sha256((corpus / f'freeze.{corpus_version}.json').read_bytes()).hexdigest(),
            'source_sha256': digest.hexdigest(),
            'evaluator_sha256': sha256(b''.join(p.name.encode() + p.read_bytes()
                for p in sorted(Path(__file__).parent.glob('*.py')))).hexdigest()}


def approval_template(config, directory, *, accounting_mode='strict'):
    if accounting_mode not in ('strict', 'exploratory'):
        raise ValueError('Unknown accounting mode')
    value = {'authorized': False, 'authorization_id': 'REQUIRES_EXPLICIT_HUMAN_APPROVAL', 'synthetic_only': True,
            'configuration': config, 'output_directory': str(Path(directory).resolve()),
            'max_requests': 12, 'max_input_tokens': 100000, 'max_output_tokens': 20000,
            'max_total_tokens': 120000, 'max_seconds': 120, 'max_cost_usd': '0.50',
            'per_call_output_tokens': 1024,
            'pricing': {'reviewed': False, 'source_url': 'https://reviewed-provider.example/pricing',
                        'effective_date': 'REVIEW_REQUIRED', 'verified_at': 'REVIEW_REQUIRED',
                        'units': 'USD_per_million_tokens', 'input_usd_per_million': 'REVIEW_REQUIRED',
                        'output_usd_per_million': 'REVIEW_REQUIRED'},
            'accounting': {'reviewed': False, 'input_bound': 'serialized_utf8_bytes_plus_overhead',
                           'overhead_tokens': 0, 'output_cap_includes_reasoning': False,
                           'usage_includes_reasoning': False, 'no_unpriced_fees': False}}
    if accounting_mode == 'exploratory':
        value.update(accounting_mode='exploratory', accepts_billing_uncertainty=False,
                     call_timeout_seconds=90, turn_timeout_seconds=240, capture_responses=False)
        value['pricing']['observed_date'] = value['pricing'].pop('effective_date')
        value['accounting'] = {'input_estimate': 'serialized_utf8_bytes_plus_overhead',
                               'overhead_tokens': 4096, 'guaranteed_bound': False,
                               'provider_billing_verified': False}
    return value


def _view_results(journal):
    results = list(journal.data['results'])
    active = journal.data['active']
    if active:
        results.append({k: v for k, v in active.items() if k != 'planned_turns'} |
                       {'correct': False, 'interrupted': True,
                        'unexecuted_turns': active['planned_turns'] - len(active['turns'])})
    return results


def artifact(cases, journal, budget, config):
    results = _view_results(journal)
    summary = summarize_trajectories(results)
    turns = [t for c in results for t in c['turns']]
    calls = [call for t in turns for call in t['model_calls']]
    protocols = [p for t in turns for p in t.get('protocol', [])]
    report_count = summary['supported_completion']['numerator']
    summary.update(protocol=dict(sum((Counter(p) for p in protocols), Counter())),
                   database_latency_ms=round(sum(t.get('database_latency_ms', 0) for t in turns), 3),
                   recovery_latency_ms=round(sum(c['elapsed_ms'] for c in calls if c.get('recovery')), 3),
                   calls_per_complete_report=fraction(len(calls), report_count),
                   missing_clarifications=sum(t['goal'] == 'clarification' and t['status'] != 'needs_clarification' for t in turns),
                   recovery_success=fraction(sum(t['revisions'] > 0 and t['outcome'] == 'correct_report' for t in turns),
                                             sum(t['revisions'] > 0 for t in turns)),
                   unauthorized_reads=sum(t['database_calls'] for t in turns if t['goal'] == 'denial'),
                   clarification_turnaround_ms=None)
    observed_usage = [call['usage'] for call in calls if call['usage'] is not None]
    summary['usage_details'] = {key: {'observed_calls': sum(u.get(key) is not None for u in observed_usage),
                                     'tokens': sum(u[key] for u in observed_usage if u.get(key) is not None)
                                      if any(u.get(key) is not None for u in observed_usage) else None}
                                for key in ('cached_input', 'reasoning')}
    budget_exhausted = budget.exhausted if budget else False
    account = budget.accounting() if budget else None
    dispatched = account['requests_dispatched'] if account else len(calls)
    summary['diagnostic_call_coverage'] = fraction(len(calls), dispatched)
    summary['calls_per_complete_report'] = fraction(dispatched, report_count)
    summary['completion_over_planned_supported_turns'] = fraction(report_count,
        sum(t['expect']['kind'] == 'report' for case in cases for t in case['turns']))
    summary['correct_over_planned_trajectories'] = fraction(sum(r['correct'] for r in results), len(cases))
    summary['stage_correctness'] = {stage: fraction(
        sum(all(item['checks'].values()) for t in turns for item in t['stage_requirements'] if item['stage'] == stage),
        sum(item['stage'] == stage for t in turns for item in t['stage_requirements']))
        for stage in ('decoded_intent', 'effective_intent', 'proposal')}
    reviewer = summary['reviewer']
    summary['reviewer_incorrect_plan_rejection'] = fraction(reviewer['incorrect_rejected'],
        reviewer['incorrect_rejected'] + reviewer['incorrect_approved'])
    summary['reviewer_false_rejection'] = fraction(reviewer['correct_rejected'],
        reviewer['correct_rejected'] + reviewer['correct_approved'])
    summary['stage_detection'] = dict(sum((Counter(t.get('stage_detection', {})) for t in turns), Counter()))
    summary['model_sql_attempts_accepted'] = sum(t['database_calls'] > 0 and any(
        p.get('model_sql_attempt', 0) for p in t.get('protocol', [])) for t in turns)
    summary['payload_isolation_failures'] = sum(not t['checks']['payload_isolation'] for t in turns)
    if account:
        summary['model_calls_by_stage'] = dict(Counter(c['stage'] for c in budget.state['calls']))
        summary['estimated_cost'] = account['estimated_usd_charged_or_reserved']
        summary['cost_status'] = ('Exploratory published-rate estimate/reservation; billing and input bound unverified'
                                  if budget.exploratory else
                                  'Conservative operator-reviewed USD estimate/reservation; provider invoice unavailable')
    completed_ids = {r['id'] for r in journal.data['results']}
    planned_turns = sum(len(c['turns']) for c in cases)
    injected = journal.data['manifest'].get('transport_test_injected', False)
    return {'schema_version': 3, 'mode': 'live_budget_mock_test' if injected else config['mode'],
            'live_model_status': ('not_executed_mock_transport' if injected else
                                  'requests_dispatched' if account and account['requests_dispatched'] else 'not_executed'),
            'python': platform.python_version(),
            'configuration': {k: v for k, v in config.items() if k != 'endpoint'},
            'endpoint_sha256': sha256(config['endpoint'].encode()).hexdigest() if config['endpoint'] else None,
            'planned_trajectories': len(cases), 'planned_turns': planned_turns,
            'unexecuted_trajectories': sum(not next(
                (r['turns'] for r in results if r['id'] == c['id']), []) for c in cases),
            'remaining_untouched_trajectories': sum(c['id'] not in {r['id'] for r in results} for c in cases),
            'unexecuted_turns': planned_turns - len(turns),
            'interrupted': journal.data['interrupted'], 'budget_accounting': account,
            'runner_reason': journal.data.get('runner_reason'),
            'budget_exhausted': budget_exhausted,
            'cleanup_failed': journal.data.get('cleanup_failed', False),
            'pricing': budget.approval['pricing'] if budget else None,
            'summary': summary, 'results': results}


def run(cases, directory, *, mode='offline', endpoint=None, model=None, approval=None,
        resume=False, max_cases=None, live_client_factory=None, turn_hook=None,
        corpus_root=None, corpus_version='v4', accounting_mode='strict', max_structured_repairs=0,
        stage_models=None, reasoning_effort=None, stop_on_transport_failure=True):
    if mode not in ('offline', 'protocol', 'live'):
        raise ValueError('Unknown evaluation mode')
    if mode == 'live' and any(not c['live_eligible'] for c in cases):
        raise ValueError('Only reviewed natural assessment cases may run live')
    config = configuration(cases, mode, endpoint, model, corpus_root=corpus_root, corpus_version=corpus_version,
                           max_structured_repairs=max_structured_repairs, stage_models=stage_models,
                           reasoning_effort=reasoning_effort)
    if mode == 'live':
        validate_approval(approval, config, directory, accounting_mode=accounting_mode)
    elif (approval is not None or live_client_factory is not None or endpoint is not None or model is not None
          or accounting_mode != 'strict'):
        raise ValueError('Offline/protocol mode cannot construct a live client')
    manifest = {**{k: v for k, v in config.items() if k != 'endpoint'},
                'endpoint_sha256': sha256(endpoint.encode()).hexdigest() if endpoint else None,
                'transport_test_injected': live_client_factory is not None,
                'approval_sha256': sha256(json.dumps(approval, sort_keys=True).encode()).hexdigest() if approval else None,
                **({} if stop_on_transport_failure else {'stop_on_transport_failure': False})}
    with run_lock(directory):
        journal = Journal(directory, manifest, resume=resume)
        if resume:
            journal.abandon_active()  # Never replay a possibly dispatched turn.
        budget = (Budget(approval, journal, stop_on_transport_failure=stop_on_transport_failure)
                  if mode == 'live' else None)
        client = None
        try:
            if mode == 'live' and not budget.exhausted:
                if live_client_factory:
                    client = live_client_factory()
                else:
                    # No credential is read before exact approval validation.
                    import os
                    from openai import OpenAI
                    key = os.environ.get('SAGEQL_EVAL_API_KEY')
                    if not key:
                        raise ValueError('Explicit evaluation credential configuration is required')
                    client = OpenAI(api_key=key, base_url=endpoint,
                                    timeout=approval.get('call_timeout_seconds', 30), max_retries=0)
            done = {c['id'] for c in journal.data['results']}
            count = 0
            for case in cases:
                if case['id'] in done:
                    continue
                if (budget and budget.exhausted) or (max_cases is not None and count >= max_cases):
                    break
                journal.begin(case)
                def checkpoint(turn):
                    journal.turn(turn)
                    if turn_hook:
                        turn_hook(turn)
                if mode == 'live':
                    from sageql import LLMConfig
                    live_config = LLMConfig('credential-held-by-injected-client', endpoint, model)
                else:
                    live_config = None
                result = run_trajectory(case, live_config=live_config, budget=budget, live_client=client,
                                        client_factory=None if mode == 'live' else mock_client,
                                        stage_client_type=ObservedClient, turn_checkpoint=checkpoint,
                                        outcome_scorer=assess_outcome,
                                        agent_options={**({'max_structured_repairs': max_structured_repairs} if max_structured_repairs else {}),
                                                       **{key: config[key] for key in ('stage_models', 'reasoning_effort')
                                                          if key in config},
                                                       **({'max_output_tokens': approval['per_call_output_tokens'],
                                                       'timeout_seconds': max(.001, min(approval.get('call_timeout_seconds', 30),
                                                                                       budget.remaining_seconds()))} if approval else {})})
                journal.finish(result)
                count += 1
                atomic_json(Path(directory) / 'results.json', artifact(cases, journal, budget, config))
        except KeyboardInterrupt:
            journal.data['interrupted'] = True
            journal.data['runner_reason'] = 'interrupted'
            journal.save()
        except Exception as error:
            journal.data['interrupted'] = True
            journal.data['runner_reason'] = ('local_io' if isinstance(error, OSError) else
                'runner_contract' if isinstance(error, (KeyError, TypeError)) else
                'invalid_input' if isinstance(error, ValueError) else
                'dependency' if isinstance(error, ImportError) else 'runner_failure')
            journal.save()
            atomic_json(Path(directory) / 'results.json', artifact(cases, journal, budget, config))
            raise
        finally:
            if client is not None:
                try:
                    client.close()
                except Exception:
                    journal.data['cleanup_failed'] = True
                    journal.save()
        result = artifact(cases, journal, budget, config)
        atomic_json(Path(directory) / 'results.json', result)
        return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('offline', 'protocol', 'live'), default='offline')
    parser.add_argument('--accounting-mode', choices=('strict', 'exploratory'), default='strict')
    parser.add_argument('--cohort', choices=('all', 'assessment', 'development', 'protocol'), default='assessment')
    parser.add_argument('--case', action='append', dest='case_ids')
    parser.add_argument('--output', type=Path, default=Path('dist/phase06/offline'))
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--approval', type=Path)
    parser.add_argument('--endpoint')
    parser.add_argument('--model')
    parser.add_argument('--prepare-approval', type=Path)
    options = parser.parse_args(argv)
    try:
        cases = load_cases(options.cohort, options.case_ids)
        if options.prepare_approval:
            if not options.endpoint or not options.model or options.prepare_approval.exists():
                raise ValueError('Select endpoint/model and a new approval-template path')
            value = approval_template(configuration(cases, 'live', options.endpoint, options.model), options.output,
                                      accounting_mode=options.accounting_mode)
            options.prepare_approval.parent.mkdir(parents=True, exist_ok=True)
            with options.prepare_approval.open('x', encoding='utf-8') as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2); stream.write('\n')
            print('Disabled approval template created; no model client constructed.')
            return 0
        if options.mode == 'live' and (not options.approval or not options.endpoint or not options.model):
            raise ValueError('Live mode requires separate exact approval, endpoint and model')
        approval = json.loads(options.approval.read_text(encoding='utf-8')) if options.approval else None
        result = run(cases, options.output, mode=options.mode, endpoint=options.endpoint, model=options.model,
                     approval=approval, resume=options.resume, accounting_mode=options.accounting_mode)
    except Exception:
        print('Evaluation cannot start or resume; review frozen inputs, exact approval, budgets and output configuration.')
        return 2
    print(json.dumps(result['summary'], indent=2))
    return 2 if result['cleanup_failed'] else int(bool(result['summary']['failing_trajectories'] or result['unexecuted_turns']))


if __name__ == '__main__':
    raise SystemExit(main())
