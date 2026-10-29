"""Phase 14 selections only; shared frozen loader, transport, journal and scorer."""
import argparse
import json
from pathlib import Path

from evaluations.phase06 import approval_template, configuration, run as run_evaluation
from evaluations.phase08 import ROOT as LEGACY_ROOT, VERSION as LEGACY_VERSION, load_cases as load_frozen, safety_check

ROOT = Path(__file__).with_name('phase14')
VERSION = 'v2'


def load_cases(cohort='independent', case_ids=None):
    if cohort == 'legacy':
        return load_frozen('assessment', case_ids)
    if cohort != 'independent':
        raise ValueError('Select a separately scoped Phase 14 cohort')
    return load_frozen('independent', case_ids, corpus_root=ROOT,
                       corpus_version=VERSION, cohort_prefix='phase14')


def corpus_for(cases):
    if not cases:
        raise ValueError('Empty Phase 14 selection')
    cohorts = {c['cohort'] for c in cases}
    if cohorts == {'phase08_assessment'}:
        return LEGACY_ROOT, LEGACY_VERSION
    if cohorts == {'phase14_independent'}:
        return ROOT, VERSION
    raise ValueError('Do not pool assessment populations or include the completed pilot')


def run(cases, directory, **options):
    root, version = corpus_for(cases)
    return run_evaluation(cases, directory, corpus_root=root, corpus_version=version,
                          turn_hook=safety_check, **options)


def draft(cases, directory, endpoint, model, *, accounting_mode='strict', max_structured_repairs=0):
    root, version = corpus_for(cases)
    value = approval_template(configuration(cases, 'live', endpoint, model,
                              corpus_root=root, corpus_version=version, max_structured_repairs=max_structured_repairs), directory,
                              accounting_mode=accounting_mode)
    value.update(max_requests=120, max_input_tokens=2000000, max_output_tokens=983040,
                 max_total_tokens=2983040, max_seconds=1800, max_cost_usd='5.00',
                 per_call_output_tokens=8192)
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cohort', choices=('legacy', 'independent'), default='independent')
    parser.add_argument('--case', action='append', dest='case_ids')
    parser.add_argument('--mode', choices=('offline', 'live'), default='offline')
    parser.add_argument('--accounting-mode', choices=('strict', 'exploratory'), default='strict')
    parser.add_argument('--output', type=Path, default=Path('dist/phase14/offline-independent'))
    parser.add_argument('--approval', type=Path)
    parser.add_argument('--endpoint')
    parser.add_argument('--model')
    parser.add_argument('--prepare-approval', type=Path)
    parser.add_argument('--resume', action='store_true')
    options = parser.parse_args(argv)
    try:
        cases = load_cases(options.cohort, options.case_ids)
        if options.prepare_approval:
            if not options.endpoint or not options.model:
                raise ValueError('Exact endpoint/model required')
            value = draft(cases, options.output, options.endpoint, options.model,
                          accounting_mode=options.accounting_mode)
            options.prepare_approval.parent.mkdir(parents=True, exist_ok=True)
            with options.prepare_approval.open('x', encoding='utf-8') as stream:
                json.dump(value, stream, indent=2, ensure_ascii=False); stream.write('\n')
            print('Disabled Phase 14 scope created; no key or model client accessed.')
            return 0
        approval = json.loads(options.approval.read_text(encoding='utf-8')) if options.approval else None
        result = run(cases, options.output, mode=options.mode, endpoint=options.endpoint,
                     model=options.model, approval=approval, resume=options.resume,
                     accounting_mode=options.accounting_mode)
    except Exception:
        print('Evaluation cannot start or resume; review frozen inputs, exact approval and output configuration.')
        return 2
    print(json.dumps(result['summary'], indent=2))
    return 2 if result['cleanup_failed'] else int(bool(result['summary']['failing_trajectories'] or result['unexecuted_turns']))


if __name__ == '__main__':
    raise SystemExit(main())
