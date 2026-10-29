"""Matched nano/mini stage comparison over the frozen Phase 14 selections.

Each setup runs the same cohort through the shared Phase 06 runner, budget,
journal and scorer. Only gpt-5-nano and gpt-5-mini may be selected. Unlike the
Phase 08/14 assessment gate, a wrong synthetic report is scored and the run
continues so both setups cover every turn; isolation failures and denied reads
still stop the batch. A dropped provider connection fails only its turn (never
retried); its full reservation stays in every budget limit.
"""
import argparse
from collections import defaultdict
from decimal import Decimal
import json
from pathlib import Path

from evaluations.phase06 import approval_template, configuration, run as run_evaluation
from evaluations.phase14 import corpus_for, load_cases

ENDPOINT = 'https://api.avalai.ir/v1'
BASE_MODEL = 'gpt-5-nano'
ALLOWED_MODELS = {'gpt-5-nano', 'gpt-5-mini'}
PRICES = {  # AvalAI published USD per million tokens, observed 2026-10-29.
    'gpt-5-nano': ('https://docs.avalai.org/en/models/gpt-5-nano', '0.05', '0.40'),
    'gpt-5-mini': ('https://docs.avalai.org/en/models/gpt-5-mini', '0.25', '2.00'),
}
SETUPS = {
    'A': {'reasoning_effort': 'low'},
    'B': {'reasoning_effort': 'low', 'stage_models': {'intent': 'gpt-5-mini'}},
}


def comparison_check(turn):
    """Stop only for safety boundaries; semantic errors are measured, not gated."""
    if not turn['checks'].get('payload_isolation', True) or turn['goal'] == 'denial' and turn['database_calls']:
        raise RuntimeError('Comparison safety boundary stopped subsequent work')


def settings(setup):
    value = SETUPS[setup]
    if set(value.get('stage_models', {}).values()) - ALLOWED_MODELS:
        raise ValueError('Only gpt-5-nano and gpt-5-mini are approved for this comparison')
    return value


def prepare(cases, directory, setup, authorization_id, observed_at):
    """An enabled packet; the authorization reference names the human approval."""
    root, version = corpus_for(cases)
    options = settings(setup)
    value = approval_template(configuration(cases, 'live', ENDPOINT, BASE_MODEL, corpus_root=root,
                                            corpus_version=version, **options),
                              directory, accounting_mode='exploratory')
    url, inp, out = PRICES[BASE_MODEL]
    value['pricing'].update(reviewed=True, source_url=url, observed_date=observed_at[:10], verified_at=observed_at,
                            input_usd_per_million=inp, output_usd_per_million=out)
    extra = set(options.get('stage_models', {}).values()) - {BASE_MODEL}
    if extra:
        value['pricing']['models'] = {model: dict(zip(('source_url', 'input_usd_per_million', 'output_usd_per_million'),
                                                      PRICES[model])) for model in sorted(extra)}
    value.update(authorized=True, authorization_id=authorization_id, accepts_billing_uncertainty=True,
                 capture_responses=True, call_timeout_seconds=120, turn_timeout_seconds=240,
                 max_requests=110, max_input_tokens=3000000, max_output_tokens=600000,
                 max_total_tokens=3600000, max_seconds=3000, max_cost_usd='0.45',
                 per_call_output_tokens=8192)
    return value


def run(cases, directory, setup, approval, **options):
    root, version = corpus_for(cases)
    return run_evaluation(cases, directory, mode='live', endpoint=ENDPOINT, model=BASE_MODEL,
                          approval=approval, corpus_root=root, corpus_version=version,
                          accounting_mode='exploratory', turn_hook=comparison_check,
                          stop_on_transport_failure=False, **settings(setup), **options)


def usage_by_stage(directory):
    """Actual settled usage per stage/model from the durable journal."""
    calls = json.loads((Path(directory) / 'journal.json').read_text(encoding='utf-8'))['budget']['calls']
    totals = defaultdict(lambda: {'calls': 0, 'input': 0, 'output': 0, 'cost': Decimal(0)})
    for call in calls:
        item = totals[(call['stage'], call.get('model', BASE_MODEL))]
        item['calls'] += 1; item['input'] += call['input']; item['output'] += call['output']
        item['cost'] += Decimal(call['cost'])
    return [{'stage': stage, 'model': model, **{k: str(v) if k == 'cost' else v for k, v in item.items()}}
            for (stage, model), item in sorted(totals.items())]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--setup', choices=sorted(SETUPS), required=True)
    parser.add_argument('--cohort', choices=('legacy', 'independent'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--prepare-approval', type=Path)
    parser.add_argument('--authorization-id')
    parser.add_argument('--observed-at')
    parser.add_argument('--approval', type=Path)
    options = parser.parse_args(argv)
    cases = load_cases(options.cohort)
    if options.prepare_approval:
        if not options.authorization_id or not options.observed_at:
            raise SystemExit('Authorization reference and pricing observation time are required')
        value = prepare(cases, options.output, options.setup, options.authorization_id, options.observed_at)
        options.prepare_approval.parent.mkdir(parents=True, exist_ok=True)
        with options.prepare_approval.open('x', encoding='utf-8') as stream:
            json.dump(value, stream, indent=2, ensure_ascii=False); stream.write('\n')
        print('Comparison approval written; no key or model client accessed.')
        return 0
    approval = json.loads(options.approval.read_text(encoding='utf-8'))
    try:
        result = run(cases, options.output, options.setup, approval)
    finally:
        if (options.output / 'journal.json').exists():
            print(json.dumps(usage_by_stage(options.output), indent=2))
    print(json.dumps(result['summary'], indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
