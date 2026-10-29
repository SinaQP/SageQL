# Phase 09 engineering report — 2026-10-26

## 1. Executive summary

The six Phase 08 incompletions have been independently diagnosed and the confirmed
SDK defects repaired. Clarification retains independent missing details, metric
and grouping replacements preserve applicable context, quoted examples keep their
literal role, and affirmative filter corrections bind their intended value.
Provider-neutral gates also close reproduced wrong-report paths involving stale
dates, extra filters/measures and unconfirmed question answers.

With the corrected **offline author script**, unchanged Phase 08 v2 questions,
specifications, answers and scoring complete **14/14 trajectories and 16/16 reports**.
The untouched old script remains **12/14 and 12/16** against the final SDK because
it emits an invalid intent enum. This distinction is essential: SDK repair and
script correction are measured separately below. New Phase 09 v2 completes
**13/13 trajectories, 18/18 reports**; new assessment is 6/6 and development 7/7.
All these completed cohorts have zero incorrect accepted specs/unauthorized reads.

Full verification: **2,119 tests pass / one optional SQL Server integration skip**.
No live model, production DB, new analytical capability, runtime dependency,
persistent schema, extra agent stage, commit or push. Live-model language quality,
usage, latency, cost and reviewer utility remain unverified. Phase 10 is not begun.

## 2. Verified starting baseline

Started on `main`, HEAD `b74c10974265dcac522b3e23623e0f4f9a8ae582`, empty index,
17 tracked modifications / 173 untracked files from earlier phases. Before edits,
`dist/phase09/starting/state.json` records 303 repository hashes and 690 earlier
measurement JSON hashes. Uncommitted source/evaluation/example copies preserve the
actual starting SDK; old HEAD is not substituted for prior uncommitted work.
Required product/phase/evaluation contracts and actual phrase, grounding, evidence,
intent, agent, business, engine, session, period, model and transport paths were
reviewed. Original baseline: **2,048 passed / one skip**, 60.62 s.

The exact original Phase 08 v2 run reproduces **8/14 trajectories, 8/16 reports**,
zero wrong accepted specifications/unauthorized reads and the same six failures.
`dist/phase09/evidence-before.json` records synthetic typed evidence contrasts;
original results are preserved in `phase09_phase08_observed_before.json`.

Starting SDK SHA256:
`1f4fe6d4e99933a2636fd2f1ccb16c0ca82004d2178be136c3e3fedffab06c06`.
Final SDK SHA256:
`74ee880e1af76afc317501b51528beba663a42c674895dfc3f146b20c4925fe1`.
Source changes are limited to three SDK modules; all public model/session formats,
host mappings, independent reference functions and scoring definitions remain.

## 3. Root-cause analysis

### A03 — owner/year slot collision

The request asks for Work minutes by Technician, an ambiguous Portal restriction
and July without a year. Grounding correctly records a pending filter owner.
Date parsing then overwrites `missing` with `year` while leaving
`clarification=control_ambiguity`. The question selector treats this inconsistent
pair as time grouping. The first question is wrong even though later turns can
produce the correct report. Independent unresolved slot/reason pairs now retain
owner and year; answering the owner leaves the year unresolved.

### A04 — deferred fact selection mistaken for grouping ambiguity

`Units` is unfamiliar wording for registered Units sold; no deterministic metric
match selects its fact yet. Department is exposed both on its source and as an
explicit registered fact import. The old matcher treats those equivalent origins
as a collision. A missing-year overwrite then yields an unrelated time-grouping
question. The SDK now preserves alternative permitted representations of that
same registered grouping until intent selects the fact. It asks/permits the
necessary year question without inventing a measure or relation. Effective intent
and every final custom-provider spec must include the matching grouping.

### A05 — criterion, ranked entity and direction conflated

`from most to least` is scanned as independent ascending and descending cues,
where only a few directional ranges were recognized. The local ordering question
then cannot apply the metric answer. The explicit request to ask for a measure
also lacks its own criterion role, and `rank Service` was not grounding the entity
grouping. Bounded range/criterion/grouping recognition now preserves Service,
July and descending direction. A confirmed authorized metric becomes the ranking
criterion; negative, unknown, ambiguous or question answers do not select one.

### A06 — top-N default overrides explicit direction

Baseline metric polarity already distinguishes the old and replacement metric.
The first blocker is ordering: `top 2` adds descending even alongside explicit
ascending. Top/bottom now supplies a default only when direction is absent.
Explicit contradictory directions still clarify. Later `change grouping from
Service to Channel` also needed scoped old/new roles; it now excludes the former
and requires the latter. Filters, date and row limit retain their applicable meaning.

Fixing local preemption exposes a separate invalid mock enum in A04/A06, described
in section 6. That is corrected in the offline author adapter, never model decoding.

### A10 — plural literal-role grammar

The quote classifier recognizes singular `word/phrase/example` and limited
`is/was an example` suffixes. `The quoted words ... are just an example` consequently
leaves an unavailable-operation phrase unresolved and asks an unnecessary question.
Plural terminology and explicit example copulas now share the existing literal
role. Direct quoted operation selections remain active/unsupported, unknown roles
still clarify, and predicate values preserve original Unicode/spacing.

### A11 — bad local value, correctly rejected reference

`Use Channel = Online instead.` binds the entire unquoted `Online instead` as
data. The scripted canonical Web response is projected to an opaque reference,
but Web is not issued in that request because local grounding supplied the wrong
literal. The strict restorer correctly raises an unissued-reference error, which
becomes the safe intent `response_shape` failure. Its JSON shape is not the root
problem and there is no evidence of poor live-model behavior.

A failing custom-provider test returning the correct canonical spec also blocks
before repair, independently confirming the local semantics defect. Terminal
`instead` is now a correction modifier only for an affirmative named-predicate
assignment. Quoted `Online instead` remains exact data. Correct grounding issues
the proper current reference; the unchanged A11 script/spec then succeeds. No
reference-validation relaxation or A11 answer-key correction is needed.

## 4. Semantic architecture and alternatives

The [pre-repair design](PHASE09_SEMANTIC_DESIGN.md) retains bounded message
reconstruction, pending origin/question/key and typed current report. Internal
evidence adds unresolved slot/reason pairs, alternative grouping representations
and explicit complete-selection markers. These are local contracts, not new
model capabilities or persistent state. The existing stores already preserve
the needed user context, ownership, rollback and receipts; no schema migration
or framework is justified.

An answer clears only supplied information. Owner/year and metric/grain or
metric/year can remain independent. Separate affirmative clauses can explicitly
answer several slots or add a measure/filter/limit. Question clauses are removed
from answer evidence without negating another affirmative clause. Typed user
years bind the original incomplete month; assistant-suggested years never do.
Prior Persian owner wording is no longer reparsed as a fresh filter value on a
later year turn. Existing provider date clarification remains; no global fixed
question ordering or unnecessary model stage is introduced.

Imported/source grouping alternatives retain a disjunctive requirement, resolved
only against a selected permitted fact and enforced at the final gate. Confirmed
metric selection retains other independently required measures and answer clauses,
while excluding unrequested extras. A date-free refinement retains its frozen
period, explicit plural filter retention preserves the complete typed filter set,
and new date/comparison instructions still take effect. Sort answers preserve an
earlier limit or apply a newly supplied one. No formula or unregistered meaning
is guessed. Disabling local validation or merely rewriting prompts would leave
custom providers unprotected and cannot repair these preemptive failures.

## 5. Implementation and compatibility

| Changed component | Responsibility |
| --- | --- |
| `src/sageql/sdk/phrases.py` | Scoped replacements/ranked grouping, registered dimension equivalence, plural quote roles, clause-scoped unconfirmed answers |
| `src/sageql/sdk/grounding.py` | Directional ranges, explicit direction over row-count default, bounded terminal correction modifier |
| `src/sageql/sdk/evidence.py` | Independent pending details, year reconstruction, grouping alternatives, criterion answers, unchanged period/filter retention and closed metric choice; intent/final gates |
| `evaluations/phase06_transport.py` | Script v2 normalizes legacy author `refinement` to valid `refine` before constructing mock output |
| New Phase 09 loader/assets/tests/docs | Existing runner/scorer reuse, promotion/freeze/provenance and reproducible measurements |

ReportSpec, public providers, period/calendar operations, catalog registrations,
session/report JSON, errors, models, compiler, engine and stores retain their
interfaces. New evidence fields have internal defaults and are never accepted
from model/browser authority. No runtime dependency or host capability expansion.
Earlier saved reports remain governed by the same current-access and catalog
compatibility checks; cached old receipts are not automatically recomputed.

## 6. Independent evaluation and integrity

Exact original A03/A04/A05/A06/A10/A11 were promoted before targeted SDK repair.
Six fresh cross-domain replacements were independently specified/frozen in v1.
V1's first post-repair result exposed R01's Persian owner text being reparsed
during year completion. Preserve that result, promote R01 unchanged, freeze new
library R07 before that fix. V2 explicitly records its later freeze timing.
No question, expected supported goal or original Phase 08 answer was weakened.
Current v2 has **13 trajectories / 30 turns / 18 reports / 12 clarifications**:
seven development and six assessment. Local authorship/exposure is explicit;
there is no external blind-review or real-model generalization claim.

The public intent enum is `new/refine/answer`, while frozen Phase 08 A04/A06 author
metadata says `refinement`. The old mock copies that metadata into invalid wire
responses. Script v2 corrects only the author alias before serialization. Public
model output with `refinement` remains rejected in an explicit regression. The
original files/scripts and their failures remain available; scorer/reference
code and complete report expectations are unchanged.

| Original Phase 08 v2 experiment | Trajectories | Required reports |
| --- | ---: | ---: |
| Starting SDK, untouched original script | 8/14 | 8/16 |
| Final SDK, untouched original script | 12/14 | 12/16 |
| Starting SDK, corrected script v2 | 8/14 | 10/16 |
| Final SDK, same corrected script v2 | **14/14** | **16/16** |

The untouched-script final failures are the correctly rejected A04/A06 enum
outputs. The same-corrected-script comparison isolates production improvements;
the observed historical 8/16 is not silently relabeled as 10/16.

| New Phase 09 v2, identical final runner/scorer | Before SDK repair | After |
| --- | ---: | ---: |
| All trajectories / reports | 1/13; 7/18 | **13/13; 18/18** |
| Development trajectories / reports | 0/7; 4/11 | **7/7; 11/11** |
| Replacement assessment trajectories / reports | 1/6; 3/7 | **6/6; 7/7** |

All compared populations have zero incorrect accepted specifications and
unauthorized reads. Supported report goals remain reports even on safe blocks.
Expected specs and Python/Decimal rows/fields/types/order/bounds/truncation/
presentation derive from unchanged synthetic source/reference definitions,
independently of SQL, SDK output or reviewer agreement.

Phase 08 corpus/freeze hashes:
`f915e30613ccf2609386a608b0b433fd8919501db7b221529dc42452f4d45b48` /
`c2c84188dbcdf0db5ec2dead8ecee435dcd99af0ce4c3fd736d4394fb80c4011`.
Phase 09 v2 hashes:
`06bfcbde73549e40699dc66e4a65eeaee12685d84fd4764fa3ab34d0ad003b72` /
`1f0287cd898548fc1048b0e0687f9d2fa1c31213b109be95a4041076506fce29`.
Identical corrected evaluator before/after:
`4a5e09182594685c21674fab877c5cad004480f4461a2820c07cf063f0ecd5c8`.
Original evaluator snapshot:
`1c60436353cde3e974de391ced6d0d0121fdca4881d35755806cdde15ccbe8ab`.
The [evaluation guide](../evaluations/PHASE09.md) identifies every record family.

## 7. Multi-turn reliability

Both InMemorySessionStore and SQLiteSessionStore pass reopen during clarification,
owner then year, invalid then valid answer, cached replay, failed-refinement
rollback and earlier successful report retrieval. Existing catalog/vocabulary
revision, revocation, new-report reset and ownership tests remain green. No
uncertain operation is replayed. New tests cover metric/grain, metric/year,
comparison/grain, sort-target/limit and independent answer clauses.

The new ledger initially retained resolved ordering on original Phase 07 A12's
full sort answer. Its first failed regression run is preserved; a focused red
test now verifies clearing that target while retaining top-2 and accepting a
separate top-3 instruction. Final Phase 07 remains 27/27 and 24/24 reports. R01's
first assessment failure is preserved/promoted rather than hidden by its later
completion. Every turn counts; later reports never erase an earlier wrong question.

## 8. Agent pipeline and additional findings

The first focused regression run had **27 failures / 10 passes**. Final focused
module has **71 passing tests** across original/promoted/replacement paths,
en/fa roles, ambiguous/negative/quoted/question answers and both stores.

Controlled wrong intent loses filters/dates and retains the replaced metric;
deterministic anchoring corrects it. A wrong planner is intercepted before the
always-approving reviewer can grant authority; one later conforming proposal
completes within the existing single revision. Persistent bad proposals block
before another read and preserve the old report. Custom providers independently
test wrong metric, grouping, date, filter, direction, limit and extra selection.

These probes also demonstrated semantic wrong-report paths beyond the corpus:
date-free refinement could execute a changed period, `keep the filters` allowed
an invented extra filter, and a metric choice allowed extra measures or discarded
independently requested ones. Explicit typed retention/selection now blocks these
cases. Question-form filter assignments, sort targets and year suggestions cannot
authorize a custom ready result. These are corrected semantic integrity defects;
the probes do not demonstrate a row-policy or SQL authorization bypass.

| Same-script metric | Original Phase 08 before → after | New Phase 09 before → after |
| --- | --- | --- |
| Requirement completeness | 130/208 → 208/208 | 91/234 → 234/234 |
| Correct returned clarifications | 3/8 → 5/5 | 7/18 → 12/12 |
| Unnecessary clarifications / stalled errors | 3/2 → 0/0 | 6/3 → 0/0 |
| Intent / planning / review calls | 12/11/11 → 18/18/18 | 13/10/10 → 23/23/23 |
| Adapter calls / planning revisions | 10/0 → 16/0 | 7/0 → 18/0 |
| Local scenario ms | 660.466 → 773.505 | 727.390 → 1,016.450 |

Added calls correspond to completed reports and required clarification, not a
model-efficiency improvement. Wrong-plan reviewer detection has no measured real
denominator; scripted agreement is not independent truth. No real usage, billing,
latency, language accuracy or reviewer usefulness measurement exists.

## 9. Security and compatibility

Current actor/catalog projection, source/tenant policies, permitted relationships,
opaque references, deterministic parameterized SELECTs, execution opt-in, limits,
deadlines, result completeness, atomic publication and ownership/idempotency remain
enforced. Both SQL compilers and all safety/session/protocol regressions pass.
No new executable model SQL, physical mapping, join choice, private identity,
vocabulary inventory, credential or report-result feedback enters model context.
Safe diagnostic stages/reasons exclude rejected values and secrets. No telemetry,
production data/object change or automatic database retry.

All Phase 08 disabled approval packets retain their initial bytes and remain
disabled. Their old source/evaluator bindings do not match the repaired SDK.
A future live run needs separate exact review of source/corpus/exposure, pricing,
accounting, endpoint/model and ceilings; Phase 09 neither enables nor weakens that
gate. No API key was inspected or external request made in this phase.

## 10. Regression and package verification

Final commands use fresh Phase 09 paths unless explicitly resuming a preserved
journal. Exact evidence is linked through `evaluations/phase09/verification.json`.

| Executed check | Result |
| --- | --- |
| `python -m pytest -q` | **2,119 passed / one optional SQL Server skip**, 62.29 s |
| New semantic continuation module | **71 passed** |
| Phase 06 evaluator + vocabulary selection | **215 passed** |
| `python -m evaluations --strict` | **61/61**, exit 0 |
| `--suite holdout --strict` | **30/30**, exit 0 |
| `--suite phase04 --strict` | **26/26**, exit 0 |
| `--suite phase05 --strict` | **37/37**, exit 0 |
| `--suite phase03 --strict` | **40/42**, expected exit **1**, original D02/D03 |
| Original Phase 06 v4 | **45/45, 36/36 reports**, controlled-resume exit 0 |
| Original Phase 07 v2 | **27/27, 24/24 reports**, exit 0 |
| Original Phase 08 v2 with valid script | **14/14, 16/16 reports**, exit 0 |
| New Phase 09 v2 | **13/13, 18/18 reports**, exit 0 |
| Original untouched-script comparison | **12/14, 12/16**, invalid enums retained |
| SDK / multi-domain / vocabulary examples | Pass offline |
| Browser tabs/history/failure/replay/download/mobile/modes | Pass using bundled Playwright |
| `pip check`, `compileall -q src evaluations`, whitespace | Pass |
| Python 3.10 AST compatibility | **63 source/evaluator files** pass; runtime unavailable |

An early Phase 08 verification run recorded local I/O after its last turn was
durably scored (13/14 trajectory summary, 16/16 reports). Preserving first result
and journal, existing resume finalized the scores with identical model/DB counts.
Another Phase 06 run exited **2** with local I/O after six finished trajectories,
no active request. Its initial artifact remains; resume preserved that prefix
exactly and continued only untouched cases to 45/45. Neither database execution
failed or was retried. The underlying local I/O cause remains unverified.
Final Phase 07/08/09 runs are uninterrupted. The first post-repair full suite and
focused failures are retained; all final automated tests pass.

Wheel/sdist build, isolated installed-wheel import/examples, archive/source/
installed-byte bindings and private-artifact exclusion pass, as recorded in the
verification manifest. Actual Python 3.10 and opt-in SQL Server runtime execution
are not claimed. Historical report/measurement bytes remain preserved.

## 11. Remaining risks

No supported goal remains unfulfilled in the final valid-script Phase 08 or new
Phase 09 cohorts. The preserved original script still fails correctly on invalid
provider enums; historical D02/D03 remain unchanged and unfulfilled. Finite local
tests do not establish unrestricted language coverage or universal semantic safety.
Novel/contradictory phrases and unregistered business meaning may still clarify.

Live-model generalization, actual protocol frequency, reviewer utility and remote
usage/cost/latency remain unverified. Production SQL Server types/collation/
cancellation, actual minimum-Python/dependency compatibility and multi-read
snapshot consistency remain existing scope gaps. Two transient local I/O events
are preserved; checkpointing prevented silent repeated work, but their root cause
is not established. No unverified operational guarantee is promoted to a result.

## 12. Phase 10 recommendation — not started

If separately approved, a source-versioned real-model baseline remains the largest
unmeasured product assumption; no new preparation phase is necessary. With
authorization unavailable, prioritize **actual minimum-Python and dependency/
installed-wheel compatibility**. The SDK declares Python >=3.10 while every
measured runtime here is 3.12.0; AST parsing cannot certify imports, dependency
APIs or runtime behavior. This is independent release engineering with concrete
acceptance criteria rather than another duplicate approval/corpus exercise.

Run the unchanged offline suite and clean wheel/examples on actual Python 3.10
and the deployed runtime, across supported dependency bounds; retain every
failure, optional-extra behavior and platform result. Require zero unexplained
test/import failures, network-free base imports and unchanged report/session
contracts. Scope production SQL Server and multi-read snapshot work separately.
Do not choose a new model/framework or optimize prompts without live evidence.
No Phase 10 work begins here.

## 13. Git and preservation

Branch/revision remain unchanged; index empty, no commit/push/reset/clean/rebase.
Intentional existing edits are the three SDK modules, offline mock adapter,
README/roadmap/evaluation index and relevant SDK continuation/agent docs. Original
Phase 08 inputs/answers/freezes/approvals and all prior reference/host/scoring
definitions retain initial bytes. New tests, design/report, versioned cohorts and
measurements are additive. Exact counts and changed path list are in
`evaluations/phase09/verification.json`.

Proposed commit message:
`fix(sdk): preserve semantic requirements across clarification and refinement`
