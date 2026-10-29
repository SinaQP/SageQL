"""Frozen Phase 04 cohorts; same independent scorer, policies and session runner."""
from hashlib import sha256
import json
from pathlib import Path

ROOT = Path(__file__).with_name('phase04')


def load_cases(cohort='phase04'):
    manifest = json.loads((ROOT / 'freeze.v1.json').read_text(encoding='utf-8'))
    base = ROOT.parents[1]
    for name, digest in manifest['files'].items():
        if sha256((base / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen Phase 04 inputs changed')
    cases = json.loads((ROOT / 'cases.v1.json').read_text(encoding='utf-8'))['cases']
    return [case for case in cases if cohort == 'phase04' or case['cohort'] == cohort]
