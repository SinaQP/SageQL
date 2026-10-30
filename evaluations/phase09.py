"""Offline continuation repair cohorts using the existing durable evaluator."""
import argparse
import json
from pathlib import Path

from evaluations.frozen import file_digest
from evaluations.phase06 import run as run_evaluation
from evaluations.phase08 import safety_check

ROOT = Path(__file__).with_name('phase09')
VERSION = 'v2'


def load_cases(cohort='all', case_ids=None):
    freeze = json.loads((ROOT / f'freeze.{VERSION}.json').read_text(encoding='utf-8'))
    for name, expected in freeze['files'].items():
        if file_digest(ROOT.parents[1] / name) != expected:
            raise ValueError('Frozen Phase 09 inputs changed; preserve and version corrections')
    cases = json.loads((ROOT / f'cases.{VERSION}.json').read_text(encoding='utf-8'))['cases']
    if len({c['id'] for c in cases}) != len(cases):
        raise ValueError('Duplicate Phase 09 scenario')
    cases = [c for c in cases if cohort == 'all' or c['cohort'] == 'phase09_' + cohort]
    if case_ids:
        if set(case_ids) - {c['id'] for c in cases}:
            raise ValueError('Unknown Phase 09 scenario')
        cases = [c for c in cases if c['id'] in case_ids]
    if not cases:
        raise ValueError('Empty Phase 09 selection')
    return cases


def run(cases, directory, **options):
    return run_evaluation(cases, directory, corpus_root=ROOT, corpus_version=VERSION,
                          turn_hook=safety_check, **options)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=('all', 'assessment', 'development'), default='all')
    parser.add_argument('--case', action='append', dest='case_ids')
    parser.add_argument('--output', type=Path, default=Path('dist/phase09/offline'))
    parser.add_argument('--resume', action='store_true')
    options = parser.parse_args(argv)
    try:
        result = run(load_cases(options.cohort, options.case_ids), options.output, resume=options.resume)
    except Exception:
        print('Evaluation cannot start or resume; review frozen inputs and output configuration.')
        return 2
    print(json.dumps(result['summary'], indent=2))
    return 2 if result['cleanup_failed'] else int(bool(result['summary']['failing_trajectories'] or result['unexecuted_turns']))


if __name__ == '__main__':
    raise SystemExit(main())
