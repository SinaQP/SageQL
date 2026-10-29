# Phase 07: clarification-continuation evaluation

**Offline scripted evaluation only; live-model generalization remains unverified.**
This phase authorizes no billable request, production query or secret access.
The new command is deliberately offline-only. Phase 06's reviewed live approval,
budgets, atomic journals, locking and uncertain-work resume rules remain in force.

```powershell
.\.venv\Scripts\python.exe -m evaluations.phase07 --cohort all --output dist/phase07/all-first
.\.venv\Scripts\python.exe -m evaluations.phase07 --cohort assessment --output dist/phase07/assessment-first
.\.venv\Scripts\python.exe -m evaluations.phase07 --cohort development --output dist/phase07/development-first
.\.venv\Scripts\python.exe -m evaluations.phase07 --case L26 --output dist/phase07/promoted-L26-first
.\.venv\Scripts\python.exe -m evaluations.phase07 --case A01 --output dist/phase07/replacement-first
```

Use a new output directory to preserve first attempts. `--resume` retains the
same selection/source/configuration and never repeats an uncertain trajectory.
Exit 0 means all selected outcomes were fulfilled, 1 means an incorrect or
unfinished turn/trajectory, 2 means configuration or runner failure. Intentional
guard blocks are not report completions. Every turn contributes its own score;
a later successful answer cannot erase an earlier wrong result.

## Promotion and independent replacement

The original Phase 06 v4 corpus, freeze and measurements are unchanged. Its exact
L26 requests, target specs, requirements, data and classifications are copied into
Phase 07 **development** evidence before targeted production repair. Only cohort,
live eligibility and exposure/provenance metadata change. L26 is already exposed
and is not described as a blind assessment.

New A01 is a separate library scenario: ownerless Science must be bound to the
registered Shelf filter by the user's `The Shelf filter.` answer, preserving
Borrowings, Shelf grouping and September 2026 across a real session reopen. It
uses the unchanged original host, not a newly invented synonym or automatic
database value lookup. Independent source facts require Science / 3 borrowings.
This is a meaningfully different domain, predicate owner, wording and source policy
from L26's Portal / Channel / workshop business contract.

## Frozen v1 population and scope

`phase07/cases.v1.json` contains **26 trajectories / 59 turns**, split into **13
assessment / 13 development**. The input/reference/host hashes in
`phase07/freeze.v1.json` were frozen before Phase 07 SDK repair and before execution
of the new corpus. Its exposure history is explicit; scripted repetition is not
evidence of real-model language generalization.

Assessment contrasts include bare and wrapped owner answers, Persian corrections
around exact registered labels, original free-form versus registered-vocabulary
hosts, known-owner missing values, year completion, grain choice, ordering target
selection among two metrics and a missing ranking criterion. They span retail,
library and workshop, including existing policy-bound related filter imports.

Development includes exact L26, positive choice with a negative alternative,
negative-only/question/example/multiple/unknown/unrelated answers, invalid then
valid answers, multiple filters, exclusions, metrics, sorting and top-N retention,
comparison periods, custom-provider omissions, opaque-reference faults, prior
successful report preservation, reopen/replay and revoked access. Negative-only
answers do not positively select an owner by elimination in this bounded contract.
The unresolved guards declare the existing `clarification_stalled` public result;
they never earn supported-report completion credit.

Frozen supported-report goals remain reports if the implementation fails. There
are no known-failure waivers, skipped case scores, or classification changes made
to turn a safe block into a completed report. If an assessment is used to target
a production fix, preserve its first result, promote it and freeze an independently
authored replacement before claiming a new assessment population.

## Independent expected results and shared runner

The existing `phase05_reference.py` / `reference.py` calculate groups, sums,
counts, means, filtering, bounds, sorting and top-N from authored source facts in
Python/Decimal. Expected values are not derived from generated SQL, model/reviewer
approval or SDK output. Examples include workshop Web / July 580, retail Books /
September 70, and library Science / September three borrowings. Full expected
specs, rows, types, order, presentation, truncation and boundaries are frozen.

The new loader calls the same Phase 06 durable evaluation runner with Phase 07
corpus metadata. That runner uses the real public SDK, standard transport codecs,
the existing independent report scorer and clarification-detail checks, both SQL
compilers, policy-bound read-only SQLite and persistent session stores. It does
not add a competing reporting implementation or runtime dependency. Answer keys
and reference rows remain local and never enter model payloads.

Phase 06's original 45-trajectory population is measured separately through its
unchanged command and v4 files. Do not merge that historical denominator with the
new population. The original D02/D03 remain separate historical
unfulfilled cases with unchanged host knowledge and report goals.

## Preserved first result and current v2

The first v1 execution completed 24/26 trajectories and 22/23 required reports,
with zero incorrect accepted specifications. Preserve
`baselines/phase07_initial_v1.json`. A07 exposed an unsupported **answer form**
for an otherwise supported report: `فیلتر Department را می‌گویم.` It is promoted
unchanged into development before the general Persian suffix repair. A fresh
library History / Shelf / September scenario, A14, replaces it in assessment;
independent source facts require History / one borrowing. Both use current
policy-bound source relationships. A01 remains the independent L26 replacement.

A13's first clarification asked for a missing measure before grouping. V1's
keyword annotation accepted only grouping words despite declaring both details
missing. V2 accepts either legitimate missing-detail question. Its request,
report goal, target specification and numeric answer are unchanged. The original
v1 corpus/freeze/result remain available; this annotation correction is separate
from the A07 production repair.

Current `cases.v2.json` / `freeze.v2.json` contain **27 trajectories / 61 turns**:
**13 assessment / 14 development**, **24 required reports**, 27 clarifications,
nine intentional guard blocks and one denial. V2 was frozen after the first SDK
repair and before the A07 suffix repair and replacement execution; its metadata
states that timing explicitly. These synthetic assessments are authored locally,
not an externally blind or live-model population.

Comparable before/after records use the captured uncommitted Phase 06 SDK source
and final SDK source with identical v2 corpus, reference, scorer and runner:
10/27 to 27/27 trajectories; 8/24 to 24/24 reports; assessment 6/13 to 13/13;
development 4/14 to 14/14. Both have zero incorrect accepted specifications and
unauthorized reads. Original Phase 06 v4 improves separately from 44/45 to 45/45
and 35/36 to 36/36. Full source/configuration hashes and observed stage counts are
in `baselines/phase07_before_v2.json`, `phase07_all.json`,
`phase07_phase06_before.json` and `phase07_phase06.json`.

## Measurement and privacy boundaries

Records retain safe IDs/hashes, classifications, boolean requirement checks,
first disagreement, stage call counts/timings, revisions, adapter calls,
persistence/replay checks and available usage. They contain no prompts, canonical
inventories, result rows, SQL, physical mappings, policies, credentials or raw
provider exceptions. Normal scripted responses have no usage/cost metadata;
missing values stay unavailable. Local scripted times are not remote-model or
production SQL Server performance measurements.

Current actor/catalog/vocabulary compatibility must still protect pending answers,
saved reports and replay receipts. A clarification answer cannot authorize a hidden
concept, invent a capability, supply caller identity or bypass source policies.
No failed database operation is automatically retried. See the Phase 07 engineering
report for actual before/after results and any unfulfilled supported scenarios.
