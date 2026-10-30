"""Frozen clarification-continuation evaluation; reuse Phase 06 durable runner."""
import argparse
import json
from pathlib import Path

from evaluations.frozen import file_digest
from evaluations.phase06 import run as run_evaluation


ROOT = Path(__file__).with_name('phase07')
VERSION = 'v2'


def load_cases(cohort='all', case_ids=None):
    freeze = json.loads((ROOT / f'freeze.{VERSION}.json').read_text(encoding='utf-8'))
    for name, expected in freeze['files'].items():
        if file_digest(ROOT.parents[1] / name) != expected:
            raise ValueError('Frozen Phase 07 inputs changed; preserve and version corrections')
    cases = json.loads((ROOT / f'cases.{VERSION}.json').read_text(encoding='utf-8'))['cases']
    if len({case['id'] for case in cases}) != len(cases):
        raise ValueError('Duplicate Phase 07 trajectory IDs')
    cases = [case for case in cases if cohort == 'all' or case['cohort'] == 'phase07_' + cohort]
    if case_ids:
        if set(case_ids) - {case['id'] for case in cases}:
            raise ValueError('Unknown Phase 07 trajectory')
        cases = [case for case in cases if case['id'] in case_ids]
    if not cases:
        raise ValueError('Empty Phase 07 selection')
    return cases


def run(cases, directory, **options):
    """Keep one journal, scorer, transport observer and public execution path."""
    return run_evaluation(cases, directory, corpus_root=ROOT, corpus_version=VERSION, **options)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=('all', 'assessment', 'development'), default='all')
    parser.add_argument('--case', action='append', dest='case_ids')
    parser.add_argument('--output', type=Path, default=Path('dist/phase07/offline'))
    parser.add_argument('--resume', action='store_true')
    options = parser.parse_args(argv)
    try:
        result = run(load_cases(options.cohort, options.case_ids), options.output, resume=options.resume)
    except Exception:
        print('Phase 07 evaluation cannot start or resume; review frozen inputs and output configuration.')
        return 2
    print(json.dumps(result['summary'], indent=2))
    return 2 if result['cleanup_failed'] else int(bool(result['summary']['failing_trajectories'] or result['unexecuted_turns']))


if __name__ == '__main__':
    raise SystemExit(main())
