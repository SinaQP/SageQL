# Phase 07 engineering report — 2026-10-26

## 1. Executive summary

**Phase 07 offline evaluation complete; live-model generalization unverified.**

The exact L26 continuation now produces its independently expected report.
Clarification answers resolve the pending slot while retaining original metrics,
grouping, predicates, periods, comparisons, exclusions, ordering and limits.
Bounded English/Persian answer handling is shared across registered domains;
negative answers, questions, conflicting choices and unknown meaning do not
become positive selections. No analytics, permissions or model stages were added.

Original unchanged Phase 06 v4 improves from **44/45 to 45/45 trajectories** and
**35/36 to 36/36 required reports**. New Phase 07 v2 independently improves from
**10/27 to 27/27 trajectories** and **8/24 to 24/24 required reports**. Both
populations have zero incorrect accepted specifications and unauthorized reads.
All **2,038 automated tests pass**, with one optional SQL Server integration skip.
The original historical D02/D03 remain unfulfilled under their original contracts.

No live authorization exists. No external model request, production query,
database-object change, commit or push was performed. Phase 08 has not begun.

## 2. Starting baseline and exact root cause

Starting branch `main`, HEAD `b74c10974265dcac522b3e23623e0f4f9a8ae582`;
index empty, 17 tracked modifications and 135 untracked files from prior phases.
Before repair, `dist/phase07/starting/state.json` recorded 265 repository hashes
and 79 earlier generated evaluation JSON hashes. The uncommitted SDK, evaluations
and examples were copied into ignored `dist/phase07/starting/`; old HEAD was not
substituted for that source. Baseline tests: 1,956 passed / one skip in 57.39 s.
The isolated captured SDK reproduced 44/45, 35/36, zero wrong accepted reports.

The unchanged frozen L26 request is:

> For July 2026 show Billed amount by Service for Portal only.

`workshop-ambiguous-v1` permits the existing workshop concepts. Portal is a
host-declared categorical term for Web under both Channel and Service. The user
must supply its owner. `I mean Channel.` selects Channel, preserving Billed amount,
Service grouping and July 2026. The independent answer is Install / 300,
Repair / 220, Tune / 60, bounded by `[2026-07-01, 2026-08-01)`; an ungrouped 580
does not satisfy this report.

Two defects precede the stalled guard:

1. Vocabulary grounding recognizes ambiguous Portal correctly. A legacy ownerless
   `for ... only` fallback then starts at the initial **For July**. It overwrites
   the pending literal with `July 2026 show Billed amount by Service for` and masks
   those original requirements. Initial independent evidence loses metric,
   grouping and period. This is the first loss of business meaning.
2. The pending-owner fallback recognizes only an exact label or `Use <label>`.
   Natural affirmative wrappers do not resolve the slot. The provider repeats the
   local filter question and the unchanged `clarification_stalled` guard blocks
   the repeated missing detail. Merely adding one English phrase would bind the
   corrupted literal and leave the first defect intact.

| Before-repair contrast | Observed result |
| --- | --- |
| `Channel`, `Use Channel` | Bind the corrupted operand, then intent response-shape block; zero reads |
| `I mean Channel`, `The Channel filter`, `منظورم Channel است` | Pending owner unresolved; `clarification_stalled`; zero reads |
| Custom provider using corrupted operand, wrong measure/period/group | A synthetic probe accepted a wrong report; missing evidence did not constrain it |

The stores already preserve pending origin, question and keys. Rollback restores
the claimed snapshot on failure; cached receipts prevent repeated work. No store
defect or migration requirement was found. See the unchanged Phase 06 fixture,
the retained baseline, `dist/phase07/audit/contrast-before.json`, the initial
33-failure/15-pass regression run and the design written before production repair.

## 3. Clarification architecture and alternatives

The [scoped design](SDK_CLARIFICATION_CONTINUATION.md) retains existing messages,
pending metadata and typed current specification. Local request evidence
reconstructs the outstanding request from user messages under the **current**
permitted catalog. Assistant wording identifies only the missing slot; it cannot
supply a value, measure, year or authorization. Only known local questions and
bounded existing year questions trigger continuation reconstruction.

A shared choice recognizer reads short affirmative or rejected clauses against
registered labels and existing selection terms. Exactly one positive candidate
may resolve a slot. Negative-only answers do not choose an alternative by
elimination; questions and unconfirmed quotations remain unresolved. Parsed
choice spans are consumed as answer roles, preserving remaining source text
without lowercasing or rewriting exact literals. Thus `not Service` in an owner
answer does not remove Service grouping. A quoted text-filter value remains data.

Existing date/grain parsing and typed vocabulary validation remain responsible
for those contracts. No general translation, fuzzy lookup, owner guessing or
unrestricted parser is introduced. A typed persistent pending-state schema was
considered but rejected: reconstruction and targeted parsing fix the demonstrated
faults without changing saved sessions. Model-only prompting would leave custom
providers outside enforcement. Disabling stalled guards would only repeat errors.
A framework migration, extra model stage and third-party dependency are unjustified.

## 4. Implementation

Changes relative to the captured Phase 06 tree:

| File | Responsibility |
| --- | --- |
| `src/sageql/sdk/phrases.py` | Source-preserving span removal, contextual registered choices, bounded affirmative value wrappers, shared explicit reset detection |
| `src/sageql/sdk/grounding.py` | Vocabulary precedence; overlapping bounded ownerless selectors; contextual owner/value binding; shared reset grammar |
| `src/sageql/sdk/evidence.py` | Reconstruct and merge original requirements; consume answer roles; measure/sort selection; current-owner checks; reset defaults and unsupported-operation preservation |
| `src/sageql/sdk/engine.py` | Explicit new-report context boundary within the existing transactional request |
| `evaluations/phase06.py` | Optional corpus root/version; original defaults, configuration keys, journal/approval behavior retained |
| New Phase 07 loader/assets/tests/docs | Reuse the durable runner and independent scorer; no alternative execution path |

The ownerless fallback cannot cross protected business evidence or overwrite an
already grounded operand. Known-filter answers preserve exact quoted bytes and
local canonicalization. Metric and sort choices use current registered concepts;
a metric/dimension label collision remains ambiguous rather than favoring metrics.
After access changes, a previously ambiguous operand cannot silently switch to
another now-unique owner when the user's answer names the revoked owner.

An explicit reset clears working current/pending/history context but preserves
saved reports. An internal evidence marker follows its clarification chain and
enforces grounded predicates, absent ordering/direction and default limit 100
unless the fresh request supplies those controls. It does not persist into normal
later refinements. Questions about starting over and negative instructions do not
reset. Failures roll back the working reset through the existing atomic path.

Review also confirmed and repaired wrapped `I mean no` becoming a literal,
question-as-reset, sort-target label collision, stale-owner reinterpretation,
stale custom-provider controls after reset, and separate answer-clause requirements
being erased by known-filter resolution (metrics, grouping, grain and unsupported
operations). These are semantic wrong-report paths,
not demonstrated row-policy or SQL authorization bypasses. Focused tests preserve
their exact failure conditions and enforce zero reads on incompatible proposals.

## 5. Independent evaluation and integrity

L26 was copied unchanged into development before targeted repair. A01, the new
library Science/Shelf/September scenario, was frozen independently as its
replacement and completes three borrowings across reopening. New v1 was frozen
before SDK repair: 26 trajectories / 59 turns, 13 assessment / 13 development.
Its first execution completed 24/26 trajectories and 22/23 reports, zero wrong
accepted specifications. That first artifact is retained.

A07 exposed the supported Persian answer `فیلتر Department را می‌گویم.` Its exact
turns and report expectation were promoted to development **before** the generic
suffix repair. Independent library History/Shelf A14 was frozen as replacement
before execution, requiring one borrowing. Separately, A13's first clarification
legitimately requested the missing measure. Its v1 annotation allowed only
grouping words despite declaring both details missing. V2 corrects that annotation
to permit either question without changing requests, report goals, target specs
or data. V1 files/results remain unchanged. V2 honestly records freezing after
initial repair and before the A07 repair; these are local synthetic assessments,
not externally blind or live measurements.

Comparable runs use the same final runner/scorer, host/reference files and corpus,
with isolated captured SDK versus final SDK. Expected rows come from unchanged
Python/Decimal reference arithmetic over synthetic source facts, never SDK SQL
or reviewer agreement. Both compilers, actual read-only SQLite, policies, standard
transport codecs, persistence and replay are exercised.

| Population | Before | After | Required reports before → after |
| --- | --- | --- | --- |
| Original Phase 06 v4 | 44/45 | **45/45** | 35/36 → **36/36** |
| Original assessment | 25/26 | **26/26** | Historical denominator retained |
| Original development / protocol | 5/5, 14/14 | **5/5, 14/14** | No weakened protocol expectations |
| New Phase 07 v2, 61 turns | 10/27 | **27/27** | 8/24 → **24/24** |
| New assessment | 6/13 | **13/13** | 6/13 → **13/13** |
| New development | 4/14 | **14/14** | 2/11 → **11/11** |

Original requirement completeness improves 455/468 → 468/468; new completeness
104/312 → 312/312. All 27 new expected clarifications are correct. Final new
outcomes: 24 reports, 27 clarifications, nine intentional blocks, one denial.
Both populations retain zero wrong accepted specifications, unauthorized reads,
accepted model-SQL attempts and payload-isolation failures. Supported report
goals never receive completion credit for a safe block or unsupported result.

Records: `evaluations/baselines/phase07_initial_v1.json`, `phase07_before_v2.json`,
`phase07_all.json`, `phase07_phase06_before.json`, `phase07_phase06.json`.
Corpus/freeze SHA256s: Phase 06 `2592b5fe171b746f758cf093649b463a9c3f103f49c03d16600ee7914804cda3`
/ `4e62237611dbce72f63004ae2dac453cd7bb23c8092b6ecba9f56906062bd5eb`;
Phase 07 `1b2095f0ae0bdcfb4999fa0497a4bfb73e0a0e0afd5de537b7876925869b0622`
/ `9ed92147d51d34a4a4953906ac9c05408d4032e8c748ef6096743e8deb4e4a54`.
Before SDK `ce9838e621e15248faf2cb656c640db8a2336ae5191dc134769e15dc458da70a`;
final SDK `1f4fe6d4e99933a2636fd2f1ccb16c0ca82004d2178be136c3e3fedffab06c06`.
Shared evaluator `5685582e9fae45e8f9f9f52ae0229597ce80226c8b31ce4355ca1eb60277f9dc`.

## 6. Multi-turn, persistence and replay

Original multi-turn trajectories improve 4/5 → 5/5; all 27 new multi-turn
trajectories pass. New 70-case continuation tests and 12 evaluation/review tests
cover direct and conversational English/Persian choices, literal values, missing
year, grain, metric criterion and ordering target. They include multiple metrics,
typed predicates, exclusions, comparison periods, related-source filters,
direction/top-N, invalid then valid answer, empty/unrelated/contradictory/quoted
responses, two consecutive questions and previous successful report preservation.

Both InMemorySessionStore and SQLiteSessionStore pass reopen, failed-refinement
recovery, cached receipts, explicit resets and later normal refinements. Replays
do not call the model or database. Current catalog version changes preserve
still-valid pending semantics but invalidate old receipts. A changed vocabulary
mapping from Portal/Web to Portal/Direct rejects a stale custom Web proposal,
then accepts the current Direct proposal with independently correct empty rows.
Current access revocation cannot be repaired by an alternate visible owner.
Earlier saved-report retrieval/revocation and ownership tests remain green.

Final new corpus has seven `clarification_stalled` errors, all expected unresolved
negative/question/conflicting/unknown-answer guards; none belongs to a required
report continuation. Before had 18, including valid supported answers. Original
L26's stalled error is eliminated. Invalid answers retain rollback semantics;
users retry deliberately with a new request ID. No uncertain operation is replayed.

## 7. Agent pipeline findings and measurements

Deterministic reconstruction constrains effective intent, planning and every
ready result, including custom providers. Wrong metric/group/filter/value/date/
direction/limit proposals cannot pass because a reviewer approves them. Correct
providers complete without an extra question. Persistently incompatible providers
terminate within existing limits before reads. The protocol cohort remains 14/14.

Original stage calls remain **51 intent / 55 planning / 39 review**, with five
planning revisions; the new successful L26 read needs no additional model call.
New v2 uses **27 / 27 / 25** calls, one revision; before used 16 / 9 / 9 because
many valid continuations stopped before planning. More completed reports explain
the higher new total; this is not a remote-model efficiency improvement. The new
corpus deliberately detects one bad decoded intent and two bad proposals. Its
reviewer approves 25 valid proposals; wrong-plan rejection utility has a zero
denominator and is unmeasured. Existing original injected faults remain visible.

Original local scenario time 1,666.127 → 1,725.038 ms; new 1,169.417 → 1,636.938 ms.
Adapter calls 35 → 36 and 8 → 24 respectively, matching completed report goals.
New successful reports use 79/24 = 3.292 stage calls across the entire population;
original 145/36 = 4.028. These are single local scripted runs, including concurrent
verification activity, not latency SLAs or remote-model benchmarks. No token,
cost, real clarification turnaround or remote generalization measurement exists.
The reused durable runner retains locking, atomic first-attempt journals, budgets,
controlled resume and the unchanged separate live-approval contract. The new CLI
is offline-only. No failed database operation is automatically retried.

## 8. Security and compatibility

Public constructors, provider protocol, ReportSpec, session/report JSON and error
families remain compatible. No persistent schema or dependency change. Current
actor/catalog projection, tenant/source policies, execution opt-in, opaque value
references, deterministic parameterized SELECT compilation, limits, deadlines,
completeness, atomic publication and ownership/idempotency checks remain.
Models select permitted concepts, never physical mappings, SQL or authority.
Result rows, private identities, canonical inventories, policies and credentials
do not enter model stages. Safe evaluation logs retain IDs/hashes/counts/reasons,
not raw provider errors or private rows. Synthetic reference facts remain local.
No new external transmission or telemetry was added.

## 9. Regression and package verification

Final commands and outcomes (fresh Phase 07 output paths):

| Check | Result |
| --- | --- |
| `python -m pytest -q` | **2,038 passed / one optional SQL Server skip**, 56.57 s |
| Phase 06 evaluator + vocabulary tests | **215 passed** |
| Focused continuation/evaluation modules | **82 cases**, all included in full suite |
| `python -m evaluations --strict` | **61/61**, 40/40 reports, exit 0 |
| `--suite holdout --strict` | **30/30**, 29/29 reports, exit 0 |
| `--suite phase04 --strict` | **26/26**, 25/25 reports, exit 0 |
| `--suite phase05 --strict` | **37/37**, 36/36 reports, exit 0 |
| `--suite phase03 --strict` | **40/42**, exit **1**, original D02/D03 retained |
| `python -m evaluations.phase06 --cohort all` | **45/45**, 36/36 reports, exit 0 |
| `python -m evaluations.phase07 --cohort all` | **27/27**, 24/24 reports, exit 0 |
| SDK / multi-domain / vocabulary examples | Pass offline |
| `pip check`, `compileall -q src evaluations` | Pass |
| `node tests/web_tabs.cjs` | Pass with bundled Playwright via NODE_PATH |
| Python 3.10 AST parse | 61 source/evaluator files pass; actual 3.10 runtime unavailable |

The first browser invocation failed because Playwright was outside default Node
resolution; configuring the already bundled package path completed the same test.
The first full post-repair suite found one genuine regression: `۱۴۰۵ شمسی` was
blocked by broader year-question reconstruction. The shared year-answer grammar
now accepts existing شمسی/میلادی suffixes and combines original user evidence
with that answer. The original Jalali restart test and final full suite pass;
the failed run remains under `dist/phase07/final-tests.xml`.

Wheel/sdist and isolated installed-wheel results, final preservation counts and
archive/source byte bindings are recorded in the delivery verification manifest
`evaluations/phase07/verification.json`. Build and installed smoke remain offline,
without optional OpenAI/ODBC extras or remote dependency resolution. No claim is
made about an unexecuted production SQL Server or Python 3.10 runtime matrix.

## 10. Remaining risks

| Priority / status | Evidence and business implication |
| --- | --- |
| High impact, unverified | Live-model extraction, clarification language coverage, reviewer usefulness, latency and cost have no authorized observations. Scripted success cannot establish these. |
| Historical supported incompleteness | Original D02 still blocks missing grouping; original D03 still needs owner knowledge absent from its unchanged host. The distinct vocabulary-enabled host remains separate. |
| Bounded grammar | Unknown paraphrases, negative-only elimination, ambiguous labels and unregistered associations can remain unresolved. No claim of unrestricted English/Persian understanding. |
| Existing operational scope | Production SQL Server types/collation/cancellation, actual Python 3.10 runtime and multi-read snapshot consistency remain unverified. |
| Evaluation exposure | L26 and A07 are development; v2 timing and the A13 annotation correction are explicit. Local authored assessments are finite and are not independently administered live trials. |

No supported report goal remains unfulfilled in the unchanged Phase 06 or new
Phase 07 populations. The counterexample tests add finite evidence, not a proof
that every possible provider or utterance preserves meaning.

## 11. Phase 08 recommendation — not started

Prioritize a **separately authorized synthetic live-agent baseline**. This is now
the largest unmeasured product assumption: the complete scripted path works, but
actual extraction, reference compliance, reviewer recovery and bilingual answers
have no measurements. There is no demonstrated need for model/framework migration
or performance tuning before obtaining those observations.

Acceptance: review exact provider/model/endpoint, fresh exposure-tracked corpus,
storage and request/token/time/USD budgets; retain every first attempt and usage
gap; compare independent complete reports, clarifications, wrong accepted results,
stage faults/recovery, calls, latency and cost. Require zero incorrect accepted
reports, unauthorized reads or private-payload leaks; report supported-completion
failures transparently and promote exposed assessments before targeted changes.
Do not use an offline mock to replace failed live work. If approval remains
unavailable, a separately scoped runtime/SQL Server compatibility matrix is the
next independent offline engineering priority. No Phase 08 implementation begins.

## 12. Git and preservation

Branch and revision remain unchanged; the index is empty. No commit, push, reset,
clean, rebase or unrelated overwrite. Intentional edits to existing prior files
are limited to the four SDK modules, optional evaluator metadata, the current
L26 success assertion and relevant README/SDK/evaluation/roadmap documentation.
Original corpora/freezes, reference calculations, host contracts and all earlier
measurement JSON files retain their starting bytes. New design, report, tests,
versioned evaluations and measurements are additive. Exact counts and changed
path list appear in `evaluations/phase07/verification.json`.

Proposed commit message:
`fix(sdk): preserve request constraints across clarification continuations`
