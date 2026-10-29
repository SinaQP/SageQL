# Phase 09 — deterministic semantic continuation

Offline engineering only; no external model request is authorized or executed.
The [engineering report](../docs/PHASE09_ENGINEERING.md) distinguishes SDK fixes,
an invalid offline-script enum and unchanged historical evidence.

```powershell
.\.venv\Scripts\python.exe -m evaluations.phase09 --output dist/phase09/new-all
.\.venv\Scripts\python.exe -m evaluations.phase09 --cohort development --output dist/phase09/new-development
.\.venv\Scripts\python.exe -m evaluations.phase09 --cohort assessment --output dist/phase09/new-assessment
.\.venv\Scripts\python.exe -m pytest tests/test_sdk_semantic_continuation.py -q
```

Choose fresh output paths. The wrapper reuses Phase 06's public SDK path,
independent scorer, standard mock codecs, journals, locks and conservative resume.
The CLI is offline-only; all new cases have live eligibility disabled. The existing
post-turn safety hook checkpoints a wrong published result before stopping.
There is no new reporting implementation, execution retry or approval mechanism.

## Promotion and replacement history

Before production repair, exact Phase 08 v2 A03/A04/A05/A06/A10/A11 turns and
expectations were copied into Phase 09 development. Original Phase 08 questions,
answer keys, goals, versions, results and disabled approvals remain unchanged.
Six independently calculated retail/library/workshop replacements R01–R06 were
frozen before repair in v1. Source, host/reference and input hashes are recorded.

V1's first post-repair execution exposed R01's Persian owner/year continuation
failure. Its first result is retained as `phase09/first-after.v1.json`; R01's
exact turns/answers were promoted before the year-context correction. New library
R07 was frozen as replacement before that correction and before execution. V2
honestly records freezing after the initial SDK repairs. No report answer or
supported goal was weakened. These are locally authored assessments with explicit
exposure, not externally blind trials. See `phase09/exposure.v1.json`.

Current v2: **13 trajectories / 30 turns**, **7 development / 6 assessment**,
**18 required reports / 12 clarifications**. Assessment is R02–R07. Development
contains the six original Phase 08 cases plus R01. Independent Python/Decimal
reference arithmetic uses unchanged source facts/host policies and checks complete
specifications, filters, grouping, bounds, order, limits, fields/types, rows,
presentation, truncation, replay and saved reports. No answer key enters model
context. Unknown business associations and analytical capabilities are not added.

## Script correction and comparison matrix

Original Phase 08 A04/A06 author metadata uses `turn_kind="refinement"`. The strict
public intent enum is `"refine"`. Once local preemption was fixed, the mock copied
that invalid enum into wire output. Script v2 normalizes this author metadata
before mock serialization. It never changes real provider output, SDK decoding,
questions, target specs or scoring. Raw invalid model output remains rejected.
The change is documented in `phase09/script.v2.json` and bound by evaluator hashes.

| SDK / offline script | Phase 08 trajectories | Required reports |
| --- | ---: | ---: |
| Captured starting SDK / original script | 8/14 | 8/16 |
| Captured starting SDK / corrected script v2 | 8/14 | 10/16 |
| Final SDK / original script | 12/14 | 12/16 |
| Final SDK / corrected script v2 | **14/14** | **16/16** |

All cells use the original Phase 08 v2 questions, specs, expected results and
scoring rules. The original-script final failures are A04/A06's invalid enum,
correctly rejected; they are not silently credited as successful reports.
The same-corrected-script comparison isolates SDK behavior from the script repair.

New Phase 09 v2, same final script/scorer before/after captured SDK:
**1/13 → 13/13 trajectories**, **7/18 → 18/18 reports**; development **0/7 → 7/7**
and **4/11 → 11/11 reports**; assessment **1/6 → 6/6** and **3/7 → 7/7 reports**.
Both compared populations have zero wrong accepted specs/unauthorized reads.
All versions and unexpected first outcomes remain preserved.

## Measurements and interruptions

Original Phase 08 with corrected script: requirement completeness 130/208 →
208/208, correct returned clarifications 3/8 → 5/5, unnecessary clarifications
3 → 0, stalled errors 2 → 0. Stage calls 12/11/11 → 18/18/18
(intent/planning/review), adapter reads 10 → 16, planning revisions 0 → 0.
Local scenario time 660.466 → 773.505 ms.

New Phase 09: completeness 91/234 → 234/234, correct clarifications 7/18 → 12/12,
unnecessary clarifications 6 → 0, stalled errors 3 → 0. Calls 13/10/10 → 23/23/23,
reads 7 → 18, revisions 0 → 0, local time 727.390 → 1,016.450 ms. More completed
reports explain added calls; these are not remote performance improvements. Usage,
cost, actual reviewer benefit and live-model generalization remain unmeasured.

Two earlier verification runs recorded local I/O interruptions: one after every
Phase 08 turn was durably scored, and one after six Phase 06 trajectories were
durably finished with no active request. First results/journals are preserved.
Existing controlled resume finalized the scored Phase 08 work without any new
model/database calls and continued only untouched Phase 06 trajectories, preserving
its first six results exactly. The raw I/O cause is unverified; it remains an
operational limitation. No failed or uncertain database operation was replayed.
The final Phase 07/08/09 runs have no interruption and all expected outcomes pass.

## Approval and privacy boundary

Phase 08's disabled pilot/assessment packets retain their original bytes. They
bind the old SDK/evaluator and cannot authorize the modified source. A later live
run needs separate exact approval, pricing/accounting evidence and reviewed
exposure/source versions. Phase 09 creates no replacement live-approval flag,
reads no API key and sends no private data or result rows to models.

The final record families are `baselines/phase09_phase08*`, `phase09_before.json`,
`phase09_all.json`, `phase09_phase06.json`, `phase09_phase07.json` and the
interruption/first-v1 records. `phase09/verification.json` binds preservation,
test/package checks and exact source/evaluator/corpus/freeze hashes.
