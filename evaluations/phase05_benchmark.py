"""Measure bounded local matching separately from model/DB work; no SLA gate."""
import argparse
from dataclasses import replace
from hashlib import sha256
import json
from pathlib import Path
import platform
from statistics import median
from time import perf_counter

from sageql.sdk import FilterDefinition, FilterValueDefinition
from sageql.sdk.grounding import filter_controls
from sageql.sdk.semantics import validate_catalog
from evaluations.phase03_hosts import workshop_catalog


def measure():
    results=[]
    for count in (0, 32, 64, 256, 1024):
        catalog=workshop_catalog();dataset=catalog.datasets[0]
        filters=[]
        for start in range(0,count,64):
            entries=tuple(FilterValueDefinition(f'canonical-{i}',tuple(f'Term {i} variant {j}' for j in range(4)))
                          for i in range(start,min(start+64,count)))
            filters.append(FilterDefinition(f'value_filter_{start}',f'Category {start}','channel',value_vocabulary=entries))
        catalog=replace(catalog,datasets=(replace(dataset,filters=tuple(filters) or dataset.filters),))
        validate_catalog(catalog)
        request=f'Billed amount for Term {max(count-1,0)} variant 3 only in July 2026.'
        durations=[]
        for _ in range(5):
            started=perf_counter();result=filter_controls(request,catalog)
            durations.append((perf_counter()-started)*1000)
        assert bool(result.filters)==bool(count)
        results.append({'entries':count,'aliases':4*count,'samples':len(durations),
                        'median_ms':median(durations),'min_ms':min(durations),'max_ms':max(durations)})
    import sageql
    source=Path(sageql.__file__).parent;digest=sha256()
    for path in sorted(source.rglob('*.py')):
        digest.update(path.relative_to(source).as_posix().encode());digest.update(path.read_bytes())
    return {'mode':'offline_local_only','python':platform.python_version(),'source_sha256':digest.hexdigest(),
            'benchmark_sha256':sha256(Path(__file__).read_bytes()).hexdigest(),
            'description':'Full bounded filter_controls call, synthetic short request; no model or DB; one local run, no latency SLA',
            'results':results}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=Path('dist/phase05/resolution-overhead.json'))
    options=parser.parse_args();result=measure()
    options.output.parent.mkdir(parents=True,exist_ok=True)
    options.output.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,indent=2))


if __name__=='__main__':main()
