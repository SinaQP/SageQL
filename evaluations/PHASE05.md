# Phase 05: optional host vocabulary evaluation

Offline scripted evaluation only. **Live-model generalization remains unverified.**

```powershell
.\.venv\Scripts\python.exe -m evaluations --suite phase05 --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase05_development --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase05_assessment --strict
.\.venv\Scripts\python.exe -m pytest tests/test_sdk_value_vocabulary.py -q
.\.venv\Scripts\python.exe -m evaluations.phase05_benchmark
```

Outputs default to ignored `dist/phase05/`. Explicit `--output` paths generate
the measured `baselines/phase05_*.json` records. The existing trajectory runner,
scorer and read-only adapters are reused. No known-issue waivers or score changes
make this cohort pass. Guard blocks are separate from completed reports.

## Host contracts, expected answers and exposure

`phase05/hosts.v1.json` identifies separate workshop, retail and library host
registrations. `original` retains the unchanged host without vocabulary.
`workshop-values-v1` explicitly establishes Web/Online/آنلاین -> Channel = Web.
Other profiles cover ambiguous owners, scalar types, metric collisions and
registered relationship imports. All values/records are authored synthetic data.

The unchanged original Phase 03 D03 still has its one-turn **report** goal and
remains unfulfilled with zero-read clarification. V01 repeats its exact request
with explicitly different host metadata. V02 checks safe behavior without added
semantics; that expected clarification is not completion credit for original D03.
The old explicit-owner continuation still completes through Phase 04 F05.

`phase05_reference.py` uses independent Python/Decimal source arithmetic, not
generated SQL or model/SDK results. Its only additions to the preserved reference
are typed decimal literals and an evaluation-only complement calculation for
inequality. No such source enumeration exists in the SDK. Expected examples:
workshop July Web 580, Desk 280, Repair+Web 220, June Web 400, opening day 320,
budget fee 80, half-hour tier 120; retail Books 70/5 units, Garden 45; library
Science three borrowings. Unknown free-form SUM values correctly return null.

V1 froze 24 development and 12 assessment trajectories before assessment execution.
First assessment: 11/12 trajectories, 10/11 required reports; the original record
is `baselines/phase05_assessment_v1_first.json`. A10 exposed a safe second-turn
failure: an old value-only regex crossed a semicolon, swallowing the date/metric
instead of preserving the actual literal. A10 was promoted to development before
targeted repair; independently authored A13 replaces it. Requests/answer keys are
not weakened. V1 inputs/freeze and first results remain available.

V2 has **25 development / 12 assessment trajectories**, 45 total turns, 36 required
reports. It freezes all input/configuration/reference hashes before execution of
that revision. Eleven assessment cases had previous exposure; one is a replacement.
This is not an untouched blind benchmark. Tests outside the corpus are development
evidence. The final assessment was not used for targeted production fixes.

Development fault scripts distinguish omitted/wrong scalar intent, wrong-filter
planning, bounded repair, persistent errors and custom providers. The wrong-filter
script's extraction was corrected to match its declared planner-only fault before
the comparable runs; no request, expected spec or reference result changed.

## Measurements and reproducibility

Final v2: 37/37 trajectories, 36/36 complete reports, 468/468 specification-field
requirements, five correct clarifications, three correct guard blocks, one zero-read
denial; zero wrong accepted specifications. Development: 25/25 trajectories/reports.
Assessment: 12/12 trajectories, 11/11 reports, one guard block. All seven multi-turn
trajectories pass; replay/source/persistence checks are performed per turn.

The before run loads the exact initial Phase 04 sources from ignored
`dist/phase05/starting/src`. The evaluation-only fixture loader attaches passive
value declarations through an existing FilterDefinition subclass because the old
SDK lacks the new public type; the old SDK ignores these declarations. This keeps
the intended versioned host configuration, source data, requests, answer keys and
final driver/scorer fixed. It does not pretend the old SDK implemented the new API.
Source/evaluator/corpus/freeze hashes identify both conditions. Comparable before:
14/37 trajectories, 10/36 complete reports, one incorrect accepted specification.
The original D03 is measured separately and never relabeled as completed.

`phase05_before_v2.json`, `phase05_all.json`, `phase05_development.json` and
`phase05_assessment.json` contain the distinct measurements. Existing cohorts are
measured separately with `phase05_regression*.json`, `phase05_phase03*.json` and
`phase05_phase04*.json`. Every historical baseline/corpus/freeze is preserved.

The runner compares complete specs/rows/fields/types/order/bounds/presentation and
state using unchanged scoring definitions. Local wire references are decoded for
stage diagnostics, never used as the expected-data oracle. Model calls by stage,
revisions, adapter calls and local timings are recorded. Token/cost data are null
without usage/pricing. No scripted number estimates real-model accuracy.

Per-turn resolution probes measure a local filter_controls call over the permitted
catalog, with no model/database work. The separate benchmark measures five samples
on short synthetic text at 0, 32, 64, 256 and 1,024 entries (up to 4,096 terms), with
source/benchmark hashes. It reports median/min/max without a latency threshold.
It is not end-to-end SDK latency, a cold-start guarantee or a production SLA.

## Safety and live policy

Artifacts contain allowlisted IDs, boolean checks, classifications, counts, timings
and hashes; no prompts, SQL, rows, canonical values or alias inventory. Answer keys
remain local. Registered value semantics cause no lookup/discovery read. Canonical
predicate values are protected from standard model context with opaque references;
the user's own input text is still ordinary conversation input.

Live evaluation is not authorized or executed. Existing reviewed/budgeted opt-in
policy in [PHASE03.md](PHASE03.md) remains unchanged. The CLI rejects Phase 05 live
trials; default tests never load `.env`, contact a model or query Rahtal.
