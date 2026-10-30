"""Versioned optional-vocabulary cohorts; independent existing trajectory scorer."""
import json
from pathlib import Path

from evaluations.frozen import file_digest

ROOT = Path(__file__).with_name('phase05')


def load_cases(cohort='phase05'):
    manifest=json.loads((ROOT/'freeze.v2.json').read_text(encoding='utf-8'))
    base=ROOT.parents[1]
    for name,digest in manifest['files'].items():
        if file_digest(base/name)!=digest:
            raise ValueError('Frozen Phase 05 inputs changed')
    cases=json.loads((ROOT/'cases.v2.json').read_text(encoding='utf-8'))['cases']
    return [case for case in cases if cohort=='phase05' or case['cohort']==cohort]
