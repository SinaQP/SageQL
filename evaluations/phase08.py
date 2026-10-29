"""Focused Phase 08 selection; reuse the Phase 06 runner and exact approval gate."""
import argparse
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

from evaluations.phase06 import approval_template, configuration, run as run_evaluation

ROOT = Path(__file__).with_name('phase08')
VERSION = 'v2'


def load_cases(cohort='all', case_ids=None, *, corpus_root=None, corpus_version=None, cohort_prefix='phase08'):
    """Load separate frozen question/answer files; defaults preserve Phase 08."""
    root = ROOT if corpus_root is None else Path(corpus_root)
    version = VERSION if corpus_version is None else corpus_version
    freeze = json.loads((root / f'freeze.{version}.json').read_text(encoding='utf-8'))
    for name, expected in freeze['files'].items():
        if sha256((root.parents[1] / name).read_bytes()).hexdigest() != expected:
            raise ValueError('Frozen inputs changed; preserve and version corrections')
    questions = json.loads((root / f'cases.{version}.json').read_text(encoding='utf-8'))['cases']
    answers = json.loads((root / f'expectations.{version}.json').read_text(encoding='utf-8'))['cases']
    if (len({c['id'] for c in questions}) != len(questions)
            or len({c['id'] for c in answers}) != len(answers)
            or {c['id'] for c in questions} != {c['id'] for c in answers}):
        raise ValueError('Question and answer selections must match uniquely')
    by_id = {c['id']: c for c in answers}
    cases = []
    for original in questions:
        case = deepcopy(original)
        expected = by_id[case['id']]['turns']
        if len(case['turns']) != len(expected):
            raise ValueError('Turn counts must match')
        for turn, answer in zip(case['turns'], expected):
            if set(turn) & set(answer):
                raise ValueError('Model inputs and local answer keys overlap')
            turn.update(answer)
        cases.append(case)
    cases = [c for c in cases if cohort == 'all' or c['cohort'] == cohort_prefix + '_' + cohort]
    if case_ids:
        if set(case_ids) - {c['id'] for c in cases}:
            raise ValueError('Unknown Phase 08 scenario')
        cases = [c for c in cases if c['id'] in case_ids]
    if not cases:
        raise ValueError('Empty Phase 08 selection')
    return cases


def safety_check(turn):
    """The shared runner checkpoints this scored turn before stopping."""
    if (turn['accepted_specification_incorrect']
            or turn.get('status') == 'report_ready' and turn.get('outcome') != 'correct_report'
            or not turn['checks'].get('payload_isolation', True)
            or turn['goal'] == 'denial' and turn['database_calls']):
        raise RuntimeError('Phase 08 safety gate stopped subsequent work')


def run(cases, directory, **options):
    return run_evaluation(cases, directory, corpus_root=ROOT, corpus_version=VERSION,
                          turn_hook=safety_check, **options)


def draft(cases, directory, endpoint, model, *, accounting_mode='strict'):
    value = approval_template(configuration(cases, 'live', endpoint, model,
                              corpus_root=ROOT, corpus_version=VERSION), directory, accounting_mode=accounting_mode)
    pilot = all(c['cohort'] == 'phase08_pilot' for c in cases)
    value.update(max_requests=12 if pilot else 120, max_input_tokens=250000 if pilot else 2000000,
                 max_output_tokens=49152 if pilot else 491520,
                 max_total_tokens=299152 if pilot else 2491520,
                 max_seconds=300 if pilot else 1800, max_cost_usd='0.25' if pilot else '1.00',
                 per_call_output_tokens=4096)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('offline', 'live'), default='offline')
    parser.add_argument('--accounting-mode', choices=('strict', 'exploratory'), default='strict')
    parser.add_argument('--cohort', choices=('all', 'pilot', 'assessment'), default='all')
    parser.add_argument('--case', action='append', dest='case_ids')
    parser.add_argument('--output', type=Path, default=Path('dist/phase08/offline'))
    parser.add_argument('--resume', action='store_true')
    parser.add_argument('--approval', type=Path)
    parser.add_argument('--endpoint')
    parser.add_argument('--model')
    parser.add_argument('--prepare-approval', type=Path)
    options = parser.parse_args(argv)
    try:
        cases = load_cases(options.cohort, options.case_ids)
        if options.prepare_approval:
            if not options.endpoint or not options.model:
                raise ValueError('Select the exact endpoint/model')
            value = draft(cases, options.output, options.endpoint, options.model,
                          accounting_mode=options.accounting_mode)
            options.prepare_approval.parent.mkdir(parents=True, exist_ok=True)
            with options.prepare_approval.open('x', encoding='utf-8') as stream:
                json.dump(value, stream, ensure_ascii=False, indent=2); stream.write('\n')
            print('Disabled approval draft created; no key or client accessed.')
            return 0
        approval = json.loads(options.approval.read_text(encoding='utf-8')) if options.approval else None
        result = run(cases, options.output, mode=options.mode, endpoint=options.endpoint,
                     model=options.model, approval=approval, resume=options.resume,
                     accounting_mode=options.accounting_mode)
    except Exception:
        print('Evaluation cannot start or resume; review frozen inputs, exact approval, budgets and output configuration.')
        return 2
    print(json.dumps(result['summary'], indent=2))
    return 2 if result['cleanup_failed'] else int(bool(result['summary']['failing_trajectories'] or result['unexecuted_turns']))


if __name__ == '__main__':
    raise SystemExit(main())
