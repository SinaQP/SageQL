"""Replacement integrity; no live/model-quality or blind-generalization claim."""
from pathlib import Path

import pytest

from evaluations.phase08 import load_cases
from evaluations.phase05_reference import reference
from evaluations.phase06 import run


ROOT = Path(__file__).resolve().parents[1] / 'evaluations/phase14_replacements'


def replacements():
    return load_cases('replacement', corpus_root=ROOT, corpus_version='v1', cohort_prefix='phase14')


def test_replacements_remain_separate_and_ineligible_for_live_execution(tmp_path):
    cases = replacements()
    assert [c['id'] for c in cases] == ['R01', 'R02', 'R03']
    assert sum(len(c['turns']) for c in cases) == 10
    assert not any(c['live_eligible'] for c in cases)
    with pytest.raises(ValueError, match='Only reviewed natural assessment cases'):
        run(cases, tmp_path / 'forbidden', mode='live')
    assert not (tmp_path / 'forbidden').exists()


@pytest.mark.parametrize('identifier', ['R01', 'R02', 'R03'])
def test_replacement_answers_use_independent_arithmetic_and_manual_bounds(identifier):
    case = next(c for c in replacements() if c['id'] == identifier)
    for turn in case['turns']:
        if turn['expect']['kind'] == 'report':
            month = turn['spec']['period']['month']
            assert turn['expect'] == reference(case['domain'], turn['spec'],
                [f'2026-{month:02}-01', f'2026-{month+1:02}-01'])
