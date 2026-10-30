"""Frozen Phase 04 cohorts; same independent scorer, policies and session runner."""
import json
from pathlib import Path

from evaluations.frozen import file_digest

ROOT = Path(__file__).with_name('phase04')


def load_cases(cohort='phase04'):
    manifest = json.loads((ROOT / 'freeze.v1.json').read_text(encoding='utf-8'))
    base = ROOT.parents[1]
    for name, digest in manifest['files'].items():
        if file_digest(base / name) != digest:
            raise ValueError('Frozen Phase 04 inputs changed')
    cases = json.loads((ROOT / 'cases.v1.json').read_text(encoding='utf-8'))['cases']
    return [case for case in cases if cohort == 'phase04' or case['cohort'] == cohort]
