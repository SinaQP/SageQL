# SageQL roadmap

## Per-stage model selection and usage accounting (2026-10-29)

Recommendation P0-1 from [the improvement plan](IMPROVEMENT_RECOMMENDATIONS.md).
`OpenAIReportAgent` accepts optional `stage_models` (intent/planner/reviewer) and
`reasoning_effort` (one value or per stage) on the same configured endpoint;
`OpenAIReportInterpreter` accepts one optional effort. Defaults are unchanged:
`config.model` everywhere and no effort parameter. Observers now receive
`model_usage` token counts per stage (no content). The goal is to keep the cheap
default and replace a model only for a stage that measurably fails. Offline tests
only; no live model comparison has run. That needs separate explicit approval,
and the live evaluation budget still assumes one approved model.

## Phase 14 final decision — Outcome C: reliability blocked (2026-10-28)

Authorized V6 actually ran 20 AvalAI gpt-5-nano calls on exact df46/c4d1 and closed
at R04's wrong accepted grouping. Keep scores separate: N04 0/3 reports, R02 1/1
with a complete conversation, R03/R04 3/4 attempted (3/6 planned), with R03 complete
and R04's last two turns unexecuted. No unauthorized read was observed. N04's
bounded revision failed, so comparison reversal was not demonstrated live.

Final a226 SDK evidence distinguishes a known empty total projection from an
unspecified subset and binds explicit period roles before range connectors. These
fixes are offline-only; no further live call or recycled allowance occurred.
All 2,421 tests/13 native skips, historical semantic gates and 14 SQLite schedules
pass on Windows 3.10/3.12 and Ubuntu 3.12. Scripted N06 remains incomplete. Earlier
intermediate year-refinement failure logs are retained. See [the final report](PHASE14_ENGINEERING.md)
and [V8 evidence](../evaluations/phase14/verification.v8.json).

N06, A01–A12, N05's denial and R04's remaining turns lack live coverage; historical
N01/N02/N03/R01 successes do not verify the new source. No production-readiness or
Phase 15 acceptance follows. Next: select a stronger comparison model and review
an explicit source-bound paired development assessment on the fixed SDK, then a
separately authorized broader assessment if justified. No model switch or new live
scope is authorized or prepared by this conclusion. Preserve current architecture,
security and frozen evidence; no commit/push/deploy.

## Phase 14 authorized V5 — specific gains, replacement safety stop (2026-10-28)

Exact c7a1/c4d1 ran 29 calls: N02/N04 completed 4/5 reports and 1/2 conversations;
separately R01/R02 completed 2/3 reports and 1/2 conversations. N02's confirmed-year
fallback was exercised live and its full conversation completed. N04 recovered
from a repeated extra-grouping plan and completed the first comparison, but its
explicit reversal was blocked by stale Intent roles. R02 accepted an unrequested
sort, triggering the frozen stop even though rows matched. R03/R04's six turns
were unexecuted. No broader quality or Phase 14 completion claim is supported.

Offline df46/c4d1 anchors explicit base/reference month roles and preserves plain
table defaults through confirmed owner/year clarification. A broader initial
constraint broke 14 legacy tests and clean smoke; those failures are preserved
and the final rule retains host-defined defaults outside this continuation.
Exact captured replay reproduces all 29 responses; corrected replay requires
unavailable new model responses and is not live success. See
[the report](PHASE14_ENGINEERING.md) and additive V7 evidence.

Disabled `dist/phase14/completion/approval-scope.v6.json` separates N04 and now-
development R02 from live-unexecuted R03/R04. It needs its own exact approval;
V5 is closed and its allowance cannot be reused. Model, token caps, recovery
budgets and SQL/authorization architecture remain unchanged. No production
access, native SQL Server execution, commit, push, deploy or Phase 15.

Final df46 verification passes 2,391 tests / 13 native skips, all semantic gates
and 14 SQLite schedules on Windows Python 3.10/3.12 and Ubuntu Python 3.12.
Clean core imports/examples pass. A first Windows 3.12 loopback HTTP abort is
preserved; isolated and fresh full gates pass, with cause unresolved.

## Historical Phase 14 V3 verification (2026-10-28)

Exact ccc6/c4d1 V3 ran 17 calls / 9 turns, then stopped on N04 turn 1's accepted
extra Channel grouping. Completion was 4/6 attempted reports; one of two fully
executed conversations succeeded, plus partial N04. N03 completed all three
reports and directly exercised equal-range-to-month canonicalization twice.
N02 still failed its year continuation after malformed Intent and an empty
8,192-token repair. R01–R04 and N04's comparison turns were unexecuted; 15/24
planned turns received no score. The report-shape failure is retained even though
the filtered amount was 280. V3 is closed; no allowance is reusable.

Final c7a1/c4d1 changes preserve the original invalid-period diagnostic for a
confirmed pending-year fallback and forbid extra grouping on explicit fresh
whole-period totals. Valid model clarification sequencing and explicit grouping
remain compatible. Historical replay reproduces all 17 outputs; corrected replay
is offline-only and does not fabricate a corrected Planner. Full release evidence,
retained intermediate failure and new focused regressions are in
[the report](PHASE14_ENGINEERING.md) and additive V6 evidence. No current-source
live improvement is claimed. Phase 14's overall reliability objective is unmet.

Disabled final `dist/phase14/completion/approval-scope.v5.json` proposes N02/N04
then R01–R04 with separate scores, exact c7a1/c4d1 and fresh outputs. V4 remains
as a superseded compatibility-fix draft. Another dispatch needs its own exact
authorization. No production access, native SQL Server execution, publication,
commit, push, deploy or Phase 15.

Final verification passes 2,374 tests / 13 native skips, every semantic gate and
all 14 SQLite schedules on Windows Python 3.10/3.12 and Ubuntu Python 3.12.
Clean installation and package evidence remain separate from real model quality.

## Historical Phase 14 V2 verification (2026-10-28)

The explicitly approved 8e3c/c4d1 V2 scope ran 20 real calls / 10 turns, then
stopped at N03 turn 2. Complete frozen-contract completion was 4/6 attempted
report goals. Five published reports had correct numerical rows and bounds; one
failed the typed `month` versus equal-bounds `range` contract. The frozen result
and stop are preserved. N01 completed; N02 lost pending-answer context. One of two
fully executed conversations succeeded, plus one partial N03. N04 and replacements
were not dispatched; 17/27 planned turns remain unexecuted. No live results from
different SDK sources are pooled.

Offline corrections confirm pending-answer roles and canonicalize exactly equal
ranges only to user-evidenced fixed periods. Provider session context still freezes
Gregorian periods to ranges. Final SDK ccc6dae1/c4d1 passes 2,360 tests / 13 native
skips, every semantic gate and all 14 SQLite schedules on Windows Python 3.10/3.12
and Ubuntu Python 3.12. Exact historical replay preserves all 20 responses and
outcomes; corrected-source replay is explicitly counterfactual. No corrected-source
live calls occurred. V5 evidence and the current [report](PHASE14_ENGINEERING.md)
record intermediate failures, actual $0.02323205 estimated usage and limitations.

V2 is closed. Disabled `dist/phase14/completion/approval-scope.v3.json` proposes
N02–N04 then R01–R04 with separate scores, ccc6/c4d1 and fresh outputs; the earlier
allowance is not reusable. Preparation does not authorize dispatch. N06 remains
scripted-incomplete and live-unexecuted; A01–A12 remain live-unexecuted. No
production, commit, push, deploy or Phase 15.

## Historical Phase 14 completion preparation (2026-10-28)

Audit the preserved 28-call attempt at the actual failing boundaries. Keep strict
decoding and default recovery settings; make the existing opt-in structured repair
receive bounded validation feedback, transfer known output defaults to Planner,
and correct demonstrated current-period comparison anchoring. Distinguish agent
exhaustion from transport failures without exposing raw exceptions. Reuse frozen
corpora, SQLite fixtures and independent oracles. Run all release gates and prepare
one disabled, exact source/evaluator-bound targeted verification packet. No new
model dispatch, credential access, production access, Phase 15 or publication is
authorized by this preparation task.

Final source `8e3c0356…` and evaluator `c4d1db5c…` have complete offline evidence:
2,346 tests / 13 native skips, all semantic gates and 14 SQLite schedules on each
of Windows Python 3.10/3.12 and Ubuntu Python 3.12. Default scripted N improves to
12/13 reports and 5/6 conversations; N06 remains incomplete and live-unexecuted.
The separate targeted one-repair contracts pass N01–N04 10/10 reports and R01–R04
9/9. V4 evidence preserves intermediate failures and the original 28-call results.
Disabled `dist/phase14/completion/approval-scope.v2.json` proposes N01–N04 then
R01–R04, 160 requests / 45 minutes / $8 estimates. New exact approval is required
under the user's continuation §10; no new model request or credential read occurred.

## Phase 14 corrected-source continuation — partial live evidence (2026-10-28)

The separately authorized exact `d1f48054…` source ran N01 followed by N02–N05.
Request 28 failed without usage and closed the batch through the existing
transport/accounting guard: 15 turns, 1/11 supported reports complete, no wrong
accepted report, 25 remaining turns unexecuted including every legacy A case.
N01 asked for a year and retained Units/Department/September after reopening,
but malformed Planner output prevented completion. Later owner/vocabulary,
period-structure and unnecessary-clarification failures remain visible. Reviewer
approved one wrong clarification; no wrong ready report was published.

Captured-response replay reproduces the baseline with no network. Subsequent
offline fixes bind an affirmative filter-owner answer repeated with its pending
literal and recognize a terminal Persian copula only around a whole registered
alias. Prompt guidance clarifies existing period/unique-ID/default-limit rules;
strict decoding, policies and read boundaries remain intact. New exact source
`c60b35c5…` has no live verification. All older scopes/corpora/results are preserved.
Four separately frozen replacement cases remain live-ineligible; their scripted
success is not live generalization. Estimated recorded usage costs $0.03642790;
with the failed-call reservation the closed ledger is $0.04102815, billing unknown.
See [the current report](PHASE14_ENGINEERING.md) and additive Phase 14 V3 evidence
for exact denominators and final offline release results. No Phase 15 or deployment.
Final release gates passed 2,323 tests / 13 native skips on Windows Python 3.10,
Windows Python 3.12 and Ubuntu WSL2 Python 3.12, with 14/14 SQLite consistency
schedules and all previous semantic gates in each runtime. The clean core-only
wheel smoke passed. Scripted N01–N06 remains incomplete at 11/13 reports and
4/6 conversations (N04/N06), separate from the measured live failures.

## Phase 14 live assessment — safety-stopped, offline repair verified (2026-10-27)

**Partial live baseline measured; full assessment incomplete.** The user approved
the exact 18-trajectory / 40-turn scope. N01 turn 1 failed instead of asking for
a missing year. Its reopened year reply then became an annual revenue report,
approved by Reviewer, instead of September Units by Department. The existing
safety hook saved this wrong attempt and stopped the batch after four calls;
N01 turn 3, N02–N06 and all A01–A12 remain live-unexecuted.

Actual AvalAI `gpt-5-nano` usage: 16,658 input / 8,702 completion tokens, estimated
$0.00431370, billed cost unverified. No production access or Rahtal `.env` read.
Baseline, scope, questions/answers and every response are preserved. N01 is now
development-exposed. The old approval cannot authorize corrected-source execution.

Targeted offline corrections ask for a missing year after the observed invalid
partial period, preserve affirmative year answers and “for each” grouping, and
prevent context-free years from executing invented reports across providers.
Exact captured-output replay changes wrong publication into zero-read rejection;
no successful model repair is fabricated. Corrected-source live comparison and
broader reliability remain unmeasured; a separate scope is required.

Post-fix verification: **2,295 passed / 13 native skips** on Windows Python
3.10/3.12 and Ubuntu WSL2 Python 3.12, with all existing semantic gates and fourteen
SQLite consistency schedules passing. The clean core wheel smoke also passes.

See [the Phase 14 report](PHASE14_ENGINEERING.md),
[procedure](../evaluations/PHASE14.md) and
[historical readiness evidence](../evaluations/phase14/verification.v1.json) and
[live/repair evidence](../evaluations/phase14/verification.v2.json).
Existing scripted legacy/new contracts remain 12/12 and 2/6 trajectories; supported
incompletions are retained. Phase 15 has not begun; no commit, push or deployment.

## Phase 13 real-model SQLite pilot — measured and corrected (2026-10-27)

The user explicitly authorized exploratory accounting and bounded engineering
comparisons, superseding the earlier $0.25/accounting condition. The existing
runner now has an explicit exploratory option; strict mode remains default.
Ordinary pytest/CI/evaluations remain offline. No production database or Rahtal
`.env` was read. Earlier disabled packets and
[the zero-dispatch v1 record](../evaluations/phase13/verification.v1.json) are preserved.

Actual AvalAI `gpt-5-nano` exposed two failures: invented time grouping and Planner
ranking after Intent marked sorting unspecified. Reviewer approved both. Scoped
evidence/Intent fixes reject these paths before execution; exact captured-response
comparisons reproduce that change without fabricated model responses. A broader
intermediate ordering rule failed compatibility checks and was narrowed; those
failures remain recorded, with no changed answer keys or examples.

Final source completes **P01/P02 2/2 and 26/26 requirements**, with zero wrong
accepted specs and six calls. All four source-versioned attempts remain separate:
22 calls, 88,788 input / 43,466 completion tokens, estimated $0.02182580 at published
rates; account charges remain unverified. No accuracy score is pooled across runs.

Final offline verification: **2,250 passes / 13 native skips** on Windows Python
3.10/3.12 and Ubuntu WSL2 Python 3.12; fourteen SQLite consistency schedules and
existing semantic gates pass with historical D02/D03 preserved. Fresh core wheel
imports/examples and archive checks are documented in
[the Phase 13 report](PHASE13_ENGINEERING.md) and
[versioned evidence](../evaluations/phase13/verification.v2.json).

This is an exposed technical pilot. Genuine multi-turn clarification, opaque
references, unfamiliar language and broader Reviewer quality remain live-unmeasured.
A01–A12 was not enabled; no model switch, Phase 14, commit, push or deployment.

## SQLite-first automated testing (2026-10-27)

The [testing workflow](SQLITE_FIRST_TESTING.md) reuses the existing synthetic
retail/library/workshop builders, independent reference calculations, evaluation
cohorts and controlled SQLite WAL schedules. Ordinary pytest now guards external
connections and private environment files; native SQL Server tests additionally
require `--run-sqlserver-integration` in the actual command and their original
separate approval. Ambient opt-ins and `PYTEST_ADDOPTS` cannot activate native work.

The audit reproduced the default native activation gap using synthetic unused
settings, before any driver/credential access. Focused regressions cover both
native paths, explicit approval retention, inherited pytest options, guard dispatch
and isolated reusable SQLite fixtures. No SDK adapter/production connection,
public API, dependency or business semantics changed. Native ODBC/type/collation/
isolation/cleanup, production capacity and live-model quality remain separately
unverified. Phase 01–12 evidence and native test bodies are preserved. See the
[new measurements](../evaluations/testing/sqlite-first.v1.json); no production
configuration, live database, model endpoint, commit or push is used for this task.

## Phase 12 native SQL Server verification — blocked (2026-10-27)

**Level A: Native verification remains blocked.** After initially excluding the
live Rahtal target, the user explicitly authorized a limited production read-only
assessment. The existing `.env` was read locally and left unchanged. One secure,
short-timeout connection attempt failed with SQLSTATE 08001 before any SQL ran.
No retry, relaxed certificate validation, business-source read or write occurred.
The existing Phase 11 suite is retained: its thirteen approval checks pass,
missing/disabled approval blocks before credentials/driver/network, and all twelve
native cases skip. The starting full suite reproduces 2,201 passes / 13 skips.

The [Phase 12 report](PHASE12_ENGINEERING.md) and
[current results](../evaluations/phase12/verification.v2.json) preserve the
[earlier blocked record](../evaluations/phase12/verification.v1.json) and distinguish native
gaps from offline regressions. No SDK/test-framework change is justified by absent
native observations. Documentation and release readiness retain blocked native
types/isolation/cancellation/cleanup and unverified pooling/workload/live models.

Next dependencies: resolve the connection failure securely, verify independent
read-only access before source reads, and separately approve an isolated synthetic
target for the full native suite. Phase 12 is not fully complete; Phase 13 has not
started. Fixture writes, concurrency/stress/cancellation experiments and automatic
configuration/permission changes remain prohibited on production. No commit or publication.

## Phase 11 report read consistency (2026-10-27)

Implemented the [additive consistency contract](SDK_READ_CONSISTENCY.md) and
[scoped architecture/evidence](PHASE11_ENGINEERING.md). A deterministic SQLite
schedule first reproduces mixed committed states. Host-selected snapshot mode
now keeps lookup, main SQL and all label batches on one supported transaction,
with cleanup before publication and current policy checks outside the snapshot.
Compatibility execution remains available and is explicitly labeled in new
provenance. Strong mode cannot replay a compatibility receipt or silently fall
back. No arbitrary SQL/formula/relationship or database option is introduced.

Actual installed Python 3.10 execution exposed the new scope's unsupported
`set_authorizer(None)` use. A focused failing regression precedes a callable
metadata/cleanup repair; read-only file mode and business-query allowlists remain.
Final 3.10.22 Windows, 3.12.0 development and 3.12.3 Ubuntu WSL2 suites each pass
2,201 tests; 13 real SQL Server checks are explicitly skipped. Fourteen controlled
SQLite schedules pass their contracts, including intentional compatibility skew
and safe failure cases. Historical Phase03 D02/D03, original/corrected Phase08
scripts and all Phase01–10 evidence remain preserved.

SQL Server fake-driver lifecycle checks pass. The separately gated
[synthetic suite](PHASE11_SQLSERVER_TESTING.md) is prepared but has no approved
target/operations and has not run. Real SQL Server execution remains unverified;
SQLite and mocks do not certify native isolation/cancellation/cleanup or pooling.
Hosted CI and live-model generalization remain unexecuted. No production DB,
external model, commit, push or publication occurred.

Phase 12 recommendation (not started): authorize an isolated synthetic SQL Server
target and run the existing suite with actual driver/version/cleanup evidence;
verify pooling/reset separately. A separately authorized real-model baseline is
still valuable. Do not repeat fixture/approval preparation or start Phase 12
without a new request.

## Phase 10 runtime compatibility and release engineering (2026-10-27)

Completed the [scoped compatibility work](PHASE10_ENGINEERING.md), with a
[versioned machine-readable matrix](../evaluations/compatibility/phase10.v2.json)
and [repeatable installation/release gates](SDK_RELEASE.md). Actual Windows
CPython 3.10.22 through the measured 3.15.2 releases pass the original full
2,119-test baseline; Python 3.10 uses exact core floors sqlglot 26.0.0 / dotenv
1.2.0. Ubuntu WSL2 3.12.3 passes the baseline and new release-tool tests.
Wheel/sdist/editable, core-only isolation, optional lower/current imports and
minimum build tools are measured. SDK source, public API and dependency ranges
are unchanged. Phase 06 explicitly selects all 45 cases; historical Phase 03
D02/D03 and original/corrected Phase 08 script evidence remain intact.

Public PyPI SDK resolution encountered concrete timeout/DNS failures; measured
installs use hashed cached wheels and identified upstream tag builds, never
copied installed dependencies. This remains a release follow-up. New GitHub
Actions gates are pinned and pass local actionlint/command checks; hosted runs
are unexecuted. Finite patch-version and WSL coverage do not certify all future
runtimes, native Linux deployments or every optional native-wheel combination.

Phase 11 recommendation (not started): separately scope and authorize synthetic
SQL Server runtime and multi-read snapshot consistency verification. Real SQL
Server execution remains unverified. A live-model baseline still requires its
separate explicit authorization; no additional approval/corpus preparation phase
is needed. No production database operation, live-model call, commit or push.

## Phase 09 semantic continuation (2026-10-26)

Completed the [scoped deterministic repairs](PHASE09_ENGINEERING.md) with an
[explicit contract](PHASE09_SEMANTIC_DESIGN.md) and
[versioned evaluation](../evaluations/PHASE09.md). Owner/year, measure/grain and
related-source grouping requirements retain distinct roles. Criterion answers,
metric/group replacements, explicit direction plus top-N, plural quoted examples
and terminal filter corrections now preserve the intended report.

A11's unissued-reference rejection was correct for a wrongly grounded literal;
fixing local modifier parsing resolves it without weakening opaque validation.
Separately, original A04/A06 mock metadata emitted invalid `refinement`; script
v2 converts only author metadata to valid `refine`. Actual provider decoding stays
strict. Original questions/specs/answers/scorer and every first result remain.

Same valid-script Phase08 comparison: **8/14 → 14/14 trajectories**, **10/16 →
16/16 reports**. Historical observed original script remains 8/14 and 8/16; final
SDK against that untouched script is **12/14 and 12/16**, still rejecting its
invalid enums. These are separate cells, not one claimed unchanged experiment.
New Phase09 v2: **1/13 → 13/13**, **7/18 → 18/18 reports**, development7/7,
replacement assessment6/6. R01's exposed first failure was promoted and R07 frozen
before its targeted correction. No blind/live generalization claim.

Also closed reproduced custom-provider wrong-report paths for changed dates,
invented retained filters, extra selected metrics and unconfirmed question answers.
All final measured cohorts have zero wrong accepted specs/unauthorized reads.
**2,119 tests pass / one optional SQL Server skip**; original Phase06 45/45 and
36/36 reports, Phase07 27/27 and 24/24, strict/holdout/Phase04/05 remain passing.
Original D02/D03 remain visible. First local I/O interruptions and controlled
non-reexecuting resume evidence remain; their root cause is unverified.

No public API/session schema, runtime dependency, model stage, production DB,
permission or compiler expansion. Existing disabled live packets remain unchanged
and stale for the modified source. No external model call or commit/push.

Phase10 recommendation (not started): when live authorization remains unavailable,
verify actual minimum-Python/dependency/installed-wheel compatibility against the
declared >=3.10 contract. Require full offline tests/imports/examples across the
supported bounds without private-data/network side effects. A separately approved
real-model baseline can use reviewed current source/exposure; it needs no duplicate
preparation phase. Avoid model/prompt/framework changes without measured evidence.

## Phase 08 real-model preflight (2026-10-26)

**Completion level A only: preflight ready, external execution awaiting explicit
authorization.** [Report](PHASE08_ENGINEERING.md),
[selection/approval guide](../evaluations/PHASE08.md). Reused Phase 06 transport,
scorer, journals, exact approval and budget controls. Frozen focused selection:
14 trajectories / 23 turns / 16 report goals across three existing domains;
two pilot cases precede twelve assessment cases. No SDK runtime change, external
model request, production query or new dependency. No empirical accuracy/cost/
latency or reviewer-effectiveness claim.

Disabled packets bind AvalAI `https://api.avalai.ir/v1`, `gpt-5-nano`, exact ordered
selection/hash/source/directory and all ceilings. Pilot: 12 calls / 300 s / $0.25;
assessment: 120 calls / 1,800 s / $1.00, separately reviewed. Both reject before
key access. Human authorization and pricing/accounting review remain prerequisites;
public rates do not prove input/framing/reasoning/fees guarantees for the route.

Existing regressions pass: 2,048 tests / one optional SQL Server skip, Phase06
45/45 and 36/36 reports, Phase07 27/27 and 24/24 reports. Original D02/D03 stay
visible and unchanged. New offline contract review exposes six incomplete
trajectories (8/14 complete, 8/16 reports), including zero-model-call local
clarification/context failures. These are not real-model defects or success rates.
V1 oracle duplicated comparison composition; v2 corrects only that answer key,
preserving questions, goals, versions and first failures. No production tuning.

Backlog: confirmed P2 local wrong-detail/preempted clarification for A03/A04,
stalled criterion answer A05, replacement A06 and quoted role A10; A11's scripted/
local interaction needs diagnosis. No confirmed real-model defect exists without
live evidence. Unsupported share-of-total remains outside the registered scope.
Provider usage/pricing guarantees, runtime Python3.10/SQL Server and multi-read
snapshots remain unverified assumptions, not measured regressions.

Phase09 recommendation (not started): if live approval remains unavailable,
repair the demonstrated deterministic clarification/context failures with captured
before-source evidence, promoted regressions/replacements, complete independent
reports and zero wrong accepts/unauthorized reads. This is product work rather
than another preparation phase. Finish Phase08's unchanged pilot/baseline if
authorized before choosing agent or prompt optimizations.

## Phase 07 clarification continuation (2026-10-26)

**Offline complete; live-model generalization unverified.** The
[engineering report](PHASE07_ENGINEERING.md),
[scoped contract](SDK_CLARIFICATION_CONTINUATION.md) and
[evaluation guide](../evaluations/PHASE07.md) record the verified L26 repair.
An ownerless fallback previously swallowed the original measure/group/date;
contextual answer parsing then rejected natural positive choices. Both causes
are repaired with current registered evidence, preserving other constraints.

Also fixed demonstrated wrong-report paths involving negative wrappers, reset
questions, sort label collisions, owner revocation/reinterpretation, stale custom
controls after reset and unsupported clauses lost during value completion.
No new analytics, permission, model stage, dependency or persistent schema.

Identical original Phase 06 v4: **44/45 → 45/45 trajectories**, **35/36 → 36/36
reports**; original protocol 14/14 and multi-turn 5/5. New frozen v2: **10/27 →
27/27 trajectories**, **8/24 → 24/24 reports**, assessment 13/13, development
14/14, zero wrong accepted specifications or unauthorized reads. L26 and exposed
Persian A07 are development; A01/A14 are independent library replacements.
Original v1 and first failures remain; A13's clarification annotation correction
does not alter report goals or numerical answers. Original D02/D03 remain visible
and unfulfilled under unchanged contracts. Older strict/holdout/Phase04/05 pass.

Verification: **2,038 tests pass / one optional SQL Server skip**; both stores,
reopen/replay/current vocabulary, custom-provider gates, examples, browser and
offline package checks. Prior work and measurement bytes remain preserved;
no commit or push. Unknown paraphrases and unregistered meanings can still need
clarification; live language/model reliability remains unmeasured.

Recommended Phase 08 (not started): separately authorized synthetic live-agent
evaluation with fresh exposure-tracked cases and exact budgets. Measure complete
reports, wrong accepts, isolation, stage faults/recovery, calls, latency/cost and
every failed first attempt before choosing model or prompt changes. Require zero
incorrect accepted reports/unauthorized reads. Approval is a separate dependency;
if unavailable, scope the existing runtime/SQL Server matrix independently.

## Phase 06 live-agent evaluation readiness (2026-10-26)

**Offline readiness complete; live-model reliability remains unverified.**
The [engineering report](PHASE06_ENGINEERING.md), [design](PHASE06_EVALUATION_DESIGN.md)
and [executable guide](../evaluations/PHASE06.md) describe fresh frozen synthetic
assessment/development/protocol cohorts, independent result scoring, durable
first-attempt/restart records, exact approval and separate request/input/output/
total/time/USD budgets. No live authorization or external model/production call.

Fixed a reproduced incorrect-report path: fabricated/altered reserved value
references could become ordinary text predicates under correlated model output.
The decoder now rejects invalid reserved references, including changed leading
underscores/separators/case, and references in reviewer feedback. Current issuance,
ownership and final semantic/access checks still apply. No new analytics, prompt/
topology rewrite, dependency, permission or SDK/session API change.

Measured same-corpus before/after: 41/45 to **44/45 trajectories**, unchanged
**35/36 required reports**, one to **zero wrong accepted specifications**. New
protocol cohort 14/14; development 5/5; assessment 25/26 trajectories and 29/30
reports. L26's owner-answer paraphrase still stalls safely and remains a failed
report goal, not completion credit. Original D02/D03 remain incomplete; old 61
strict and Phase 04/05 cohorts still pass. Scripted results are not model accuracy.

Verification: **1,956 tests pass / one optional SQL Server skip**, 119 new tests,
96 vocabulary tests, examples/browser/dependency/compilation/package/installed-wheel
checks pass. Earlier source/evidence is preserved. Transient legacy CLI failures,
first diagnostic mistakes and unknown causes remain recorded; final entrypoint
runs have their expected exits. Source and evaluator hashes bind measurements.

Highest-value Phase 07 proposal: scoped clarification-continuation reliability
for the new confirmed completeness gap; promote exposed L26 and freeze a fresh
replacement before targeting it. Require correct metric/date/group/filter retention,
ambiguity, reopen/replay and final gates without host-meaning guesses. Keep a
separately authorized synthetic live baseline ready; actual model understanding,
reviewer utility/cost, Python 3.10 runtime, production SQL Server and multi-read
snapshot behavior remain unverified. No Phase 07 implementation or commit/push.

## Phase 05 optional host-owned value vocabulary (2026-10-25)

Implemented the [optional per-filter contract](SDK_VALUE_VOCABULARY.md): typed
canonical values, bounded aliases, ambiguity, current permission projection,
relationship-source inheritance and provider-neutral evidence enforcement.
Standard transports protect canonical predicate values with local references;
no alias/value inventory or dynamic database enumeration is introduced. Free-form
typed filters and default empty-vocabulary fingerprints remain compatible.

[Phase 05 report](PHASE05_ENGINEERING.md): 1,837 tests pass/one opt-in skip;
new frozen v2 has 37/37 trajectories, 36/36 required reports, zero wrong accepted
specifications. One exposed assessment was promoted with a replacement; original
versions and every earlier corpus/baseline/freeze remain. Exact source arithmetic,
model/adapter calls, local matching overhead and privacy checks are documented.

The original D03 is still unfulfilled with its unchanged metadata and frozen goal.
The distinct workshop-values-v1 contract supplies Web -> Channel and completes
the same wording with 580. This resolves the optional registration capability,
not the absent business knowledge of an unchanged host. D02 remains safely blocked;
Phase 04 ordering remains correct. Existing Phase 03/04 completion is 40/42 and
26/26 trajectories respectively, with no wrong accepted specifications.

Remaining priorities: authorized synthetic live evaluation of vocabulary/reference
handling and refinement (unverified, high product impact); Python 3.10/live SQL
Server matrix (unverified); bounded large-vocabulary cold latency (measured, no
production SLA); multi-read snapshots (separate design). Static registration cannot
replace missing host semantics or force a nonconforming provider to complete.
Phase 06 is recommended, not started. No live call, commit or push.

## Phase 04 provider-neutral filter and ordering grounding (2026-10-25)

Outcome: enforce independently grounded categorical predicates, sort targets,
directions and counted limits through effective intent, bounded planning and the
final gate for every provider, before any data read. Preserve registered policies,
parameterized compilation, existing public/session contracts and earlier artifacts.
See [the engineering report](PHASE04_ENGINEERING.md) and
[reproducible evaluation guide](../evaluations/PHASE04.md).

Non-goals: general language parsing, database value discovery, mandatory enumerated
filter vocabularies, new joins/formulas, secondary ordering, storage migrations,
live model/database calls and Phase 05 implementation.

Verified status: P3-06/P02 resolves through a local rejection and bounded repair.
P3-05/D03 can no longer publish the incorrect unfiltered report, but its original
one-turn completion remains **unfulfilled**. The unchanged host has three free-form
text filters and no registered evidence linking the value to its owner. It asks
for the filter identity; the new two-turn continuation then returns the correct
580. No hard-coded value mapping or query is used to invent that association.
D02 remains blocked, with zero reads. Phase 03 improves 39/42 to 40/42 complete
supported turns/trajectories, with zero wrong accepted specifications. The frozen
26-case Phase 04 cohort separately tests explicit predicates, ambiguity, ordering,
repair and persistent refinements. This is scripted offline evidence.

| Priority/evidence | Current status and next action |
| --- | --- |
| P1 P3-06/P02, wrong accepted sort | Resolved and verified: explicit target/direction/limit evidence; wrong candidates rejected before review/execution. |
| P1 P3-05/D03, omitted categorical restriction | Incorrect success prevented. Original one-turn report is still incomplete; clarify the missing business owner. Consider an optional host-owned value/alias contract only under a separately reviewed scope. |
| Safe residual D02 | Persistent custom provider still refuses to conform to explicit grouping; do not count its block as report completion. |
| P2 P4-01, analytical words/Unicode inside literal values | Fixed: source-indexed normalization preserves exact parameters while masking their instructional role. Focused data/predicate tests and both dialects verify this. |
| P2 P4-02, stale refinement controls | Fixed for bounded keep/change/replace/reverse/remove instructions. Reconstruct pending controls from user history; do not migrate sessions. Unrecognized reference language remains a limitation. |
| Unverified live generalization and runtime matrix | Offline scripted tests cannot establish these. Existing reviewed synthetic live procedure remains opt-in; Python 3.10 runtime and real SQL Server are unverified. |

Phase 05 recommendation: request-to-report completeness and an optional,
privacy-reviewed host value-to-concept vocabulary contract, followed by explicitly
authorized live synthetic evaluation. Targets: keep wrong accepted specs at zero;
resolve D03's owner without core domain inference or mandatory global enumerations;
measure first-attempt supported completion and excess clarification separately.
This recommendation follows the remaining measured semantic gap; snapshot
consistency, scalability and orchestration changes have weaker evidence in this
run. No Phase 05 work or commit is authorized or started.

Verification: 1,741 offline tests pass with one optional SQL Server skip; the
106 focused filter/order tests, examples, browser regressions, dependency/compile
checks, wheel/sdist builds and isolated installed-wheel smoke pass. Python 3.10
syntax passes; its runtime and live SQL Server/model behavior remain unverified.

Suggested commit message:
`fix: ground categorical filters and ordering across report providers`

## Phase 03 completeness and held-out evaluation (2026-10-24)

Offline evaluation complete; live-model generalization unverified. The
[engineering report](PHASE03_ENGINEERING.md) and [evaluation guide](../evaluations/PHASE03.md)
record independent source arithmetic, freezes/corrections/exposure, separate
cohort results and remaining findings. Phase 01/02 archives are preserved;
the original 61 cases remain unchanged and pass strict evaluation.

Resolved and tested: P3-01 grouping omission (agent repair/custom-provider pre-read
block), P3-02 excluded `leave out` operation, P3-03 replacement retaining the old
measure, P3-04 explicitly retained typed filter lost during refinement. V2 has
30 assessment, six development and six pipeline trajectories; H12/H25 were promoted
after exposure, with two replacements. Comparable supported turns improve 35/42
to 39/42; multi-turn correctness improves 6/8 to 8/8.

| Priority/evidence | Impact/root cause | Proposed work/tests/complexity |
| --- | --- | --- |
| P1 confirmed P3-05: D03 accepts 860 instead of Web-only 580 under correlated faults | New categorical values lack independent filter grounding; natural frequency unknown | Scope typed value/filter grounding; collision, quote, exclusion and permission tests across hosts. Medium/high. |
| P1 confirmed P3-06: P02 approves ascending instead of requested descending | Ordering can remain absent from extracted constraints; controlled frequency only | Scope typed metric/direction evidence, multiple-metric ambiguity and refinement tests. Medium. |
| Safe residual D02: persistent custom-provider error | Final gate prevents reads; cannot fulfill requested report | Host returns a conforming spec; preserve safety test, no automatic DB retry. Low. |
| Unverified live generalization | Scripted selections do not measure language understanding | Authorized synthetic trials with request/token/time/USD caps and first-attempt records. Evaluation work. |

Phase 04 recommendation: reviewed provider-neutral filter/ordering requirement
grounding and complete-report tests. Do not hard-code answers or broaden analytics
to clear these failing experiments. Snapshot consistency, runtime matrix and long
context work retain separate status. No Phase 04 implementation or commit.

## Phase 02 semantic evidence and registered vocabulary (2026-10-24)

Resolved P01-02 (negated grain executing daily reports), P01-01 (negated/literal
share terms incorrectly unsupported), and P01-03 (exact registered participant
mean requiring an extra generic word). Original requests/expected data remain
unchanged; all three now pass normally, with no xfails or evaluation waivers.

Implemented bounded shared phrase scope, quote roles, registered-vocabulary
matching and explicit exclusions; enforce them in intent normalization and every
provider's final gate. Contradictory/missing selections clarify. Registered filter
removal differs from grouping removal. Raw grouping over the registered report
date cannot bypass a daily exclusion. Known pending semantic questions preserve
user evidence across restart/answers, including subsequent year clarification.
False unavailable-ledger entries are removed from effective planner context;
active unavailable requirements remain terminal. No SQL/analytics/auth expansion.

The [Phase 02 report](PHASE02_ENGINEERING.md) records reproduction, corrective
design, all verification and residual limits. The expanded 61-case corpus passes
strict evaluation; original-cohort completion is 20/20 and additions are scored
separately. Original Phase 01 snapshots are retained in `evaluations/baselines/`.
Additional regressions found during this phase (pending-date loss, generic-mean
exclusions, filter/group role confusion, raw-date grouping and effective ledger
consistency) are fixed and tested, rather than deferred as unfinished Phase 02.

Phase 03 recommendation: independently grounded held-out request-to-report
completeness evaluation, with explicitly opted-in live synthetic trials and a
reviewed typed pending-evidence/version contract if the evidence warrants it.
Snapshot consistency and Python/dependency matrix work retain their separate
backlog status. Phase 03 has not started. No commit was created.

## Phase 01 engineering audit and evaluation foundation (2026-10-24)

Outcome: establish a verified architecture/baseline and an independent, repeatable
report evaluation gate. Scope and results are in [the engineering report](PHASE01_ENGINEERING.md)
and [evaluation instructions](../evaluations/README.md). Keep production reporting
behavior and security boundaries unchanged. New analytics, parser changes,
framework migrations and live service calls are excluded. Confirmed defects have
strict expected-failure regressions and an evidence-ranked follow-up backlog;
Phase 02 is recommended, not started. No commit was created.

## Application-independent reporting (2026-10-15)

Outcome: integrate independent business applications through host configuration,
without editing the reusable engine. Preserve all existing working changes and
the Rahtal integration. Baseline: 1,225 offline tests passed, one opt-in SQL Server
test skipped.

Acceptance: shared interpretation, clarification and result text derive business
meaning from permitted registrations; no employee/activity defaults in reusable
prompts or repair logic. Demonstrate retail and library reporting with different
schemas, registered relationships, policy restrictions, clarification/refinement,
canonical SQL, actual read-only SQLite execution and table/chart JSON. Verify SQL
Server compilation, failures, permission changes, lookup ambiguity and installable
package boundaries. Keep models isolated from physical schema, policies and rows.

Design: retain the existing catalog/provider/policy/adapter contracts. Move
Rahtal semantics into its existing dataset descriptions and metric vocabulary.
Generalize local vocabulary repairs and entity messages; no application switch,
new service or arbitrary expression interface is required.

Non-goals: new database engines, formulas/joins/calendars, production identity,
live private data access or claims of model accuracy from scripted offline tests.
Record focused and final verification in `docs/APPLICATION_INDEPENDENCE.md`.

Implemented generic shared instructions, host-derived measure/identity vocabulary,
neutral/registered-label replies, and one-to-four-column full-name registration.
Rahtal retains its business rules in its catalog. Added standalone retail/library
hosts and 42 acceptance cases covering real agents with fake transport, both SQL
compilers, actual read-only SQLite execution, authorization, lookup ambiguity,
labels, refinements/retries, persistence, schema/cardinality failures and payload
isolation. See [the implementation report](APPLICATION_INDEPENDENCE.md).

Verification: 1,267 tests passed; one optional SQL Server test skipped. Existing
and multi-domain demos, Chrome frontend regressions, source/wheel builds using
installed build dependencies, and fresh installed-wheel host runs passed. The
fresh environment reused existing required dependency distributions; full remote
dependency resolution remains unverified because PyPI downloads failed. Imports
and host runs required no Rahtal, Django, OpenAI or ODBC installation and no network.
Diff whitespace checks passed. No commit was made.

Suggested commit message:
`refactor: make reporting interpretation application independent`

## Matching daily workload groups and prior-question regression (2026-10-15)

Outcome: run the exact tenth question on configured Rahtal model/data; show each
qualifying employee/date/total with that employee's full matching-day count.
Recheck the previously requested organization totals, monthly comparison, decline
ranking, top-ten ranking and position means; preserve existing working changes.

Baseline: intent extracted the daily employee totals, but planning repeatedly
asked unnecessary clarification or failed review because the matching-day count
has no registered operation. The final result was blocked with intent_mismatch.

Design: the separately scoped [matching-day operation](SDK_MATCHING_DAY_COUNTS.md)
adds a false-by-default typed flag to daily entity tables. Group first, apply
ordinary aggregate conditions, window-count matching groups per identity/period,
then order/limit and resolve names. No special question/table/threshold routing.

Acceptance: strict > threshold on complete daily sums, count before output caps,
separate identities with equal names, unknown IDs/nulls, current policies and
labels, persistent refinements/removal/retries, safe strict/legacy schemas, both
dialects and exact source verification. Existing report SQL/results must retain
their behavior while the flag is false. Keep real evidence ignored locally.

Non-goals: arbitrary windows/formulas/partitions, additional source relationships,
timestamp conversion, computed-count filtering, database objects/writes, model SQL
or result transmission to models. Counted long days do not prove productivity.

Implemented the additive strict/legacy specification flag, optional intent
constraint and shared user-evidence check, scoped semantic validation, canonical
window count, typed adapter-result checks and post-limit label enrichment. Active
computed-count ordering is validated locally. Ordinary specifications default to
false and retain their previous SQL/result columns.

The configured Rahtal model/SQL Server rerun completed. An independent bounded
fact read, separate policy-bound name read and local daily aggregation matched
every qualifying identity/date/total and the per-entity matching-day count.
No live rows or identities are recorded in tracked files.

The five earlier exact questions (organization totals, monthly change, employee
decline, top-ten employees and position means) were rerun through the real
configured model and independently checked against current source rows. The
rolling question correctly uses the new business date. One initial decline
attempt failed closed on an invalid planner response after review; its rerun
completed and matched the source. This is recorded separately from numerical
correctness and does not establish deterministic model availability or latency.

Added 37 synthetic cases spanning separate domains, variable measures/thresholds,
complete daily sums, strict boundaries, equal names, unknown identities/durations,
both compilers, comparisons, count-before-limit, permissions, invalid adapter
counts, ordering, strict/legacy schemas and persisted retries/removal/refinements.
The existing prior-question scenarios remain in the complete suite. Browser
coverage checks Persian dates, four visible columns, complete counts on truncated
detail rows and unchanged JSON precision. The verified live JSON was also rendered
and visually inspected.

Verification: 1,225 Python tests passed; one optional synthetic SQL Server test was
skipped. Browser regressions, source/wheel builds, final installed-wheel imports
and count compilation, and `git diff --check` passed. No commit was created.

Focused command: `.venv/Scripts/python.exe -m pytest tests/test_sdk_matching_day_counts.py -q`.

Suggested commit message:
`feat: add filtered daily entity counts`

## Intent and clarification consistency correction (2026-10-08)

Outcome: a requested grouping change must be applied or explicitly reported as
unavailable; the last report must never silently replace that change. Independent
intent extraction precedes live agent planning. Local checks reject cross-source
concept combinations and candidate measures/grouping/presentation that disagree
with that extracted intent, even if a reviewer would approve them. Answered
clarifications must advance to a different missing detail or a report; the same
structured missing-detail key cannot be reissued as an answer continuation.

Acceptance: synthetic full conversations cover a table, bar refinement, supported
regrouping, unavailable regrouping, legacy pending technical confirmation,
paraphrased repeated questions, legitimate successive details, persistent restart,
idempotent retries and no database execution on rejected intent. All remote stages
share the existing deadline and permitted metadata boundary. Custom two-method
backends retain their existing contract; live OpenAI agents always extract intent.
No joins, new database objects, profile-based aggregation or calendar expansion
are introduced. Model intent extraction remains fallible; the deterministic
guarantee is consistency with its validated output, not universal language accuracy.

Verification: 810 offline tests passed and one opt-in SQL Server test was skipped.
The synthetic SDK embedding demo and JavaScript syntax check passed. The sdist
and wheel built successfully after installing the missing build backend into the
local development environment; a fresh virtual environment installed the wheel
and imported the public API, with runtime file hashes checked against source.

Interpretation-only checks with the existing configured model returned
`unsupported` for the original misspelled grouping request, its correction and
the legacy technical confirmation; no report database queries ran. A supported
table-to-bar check initially exposed the duplicate identity/name axis inherited
from the current specification. Local canonicalization now removes only a plain
identity whose target column matches its selected entity label. After that fix,
the same live check produced the expected employee-name bar with unchanged hours,
dates, ordering and limit. The failing attempts and final passing evidence remain
in ignored local files; these checks do not establish universal language accuracy.

The existing local host still needs a restart to load these changes. Automatic
tool approval rejected the stop/restart command with `blocked by policy`; that
command did not run. No database object or stored conversation was changed by
the manual verification, and no commit was created.

## Goal

Build an installable Python SDK that a developer embeds in their backend, configures with approved SQL Server datasets and infrastructure, and connects to their frontend so authorized users can create and refine reports through chat. Rahtal is a real-data integration test for that package.

The [embedded reporting architecture](ARCHITECTURE.md) records target contracts and acceptance gates. The first single-source SDK slice is implemented; [SDK.md](SDK.md) describes its actual API and limits. The historical steps below remain available; Step 5 remains undefined.

## Embedded SDK slice (implemented; live SQL Server verification pending)

**Outcome:** Install the SDK into an independent Python host and complete a frontend report conversation over a registered SQL Server table or reporting view, with a read-only SQLite reference for offline verification.

**Acceptance:** One facade and versioned reply/report contracts; trusted per-actor scope and row policies; resumable persistent sessions, idempotent requests and revision checks; registered aggregates/dimensions/filters; reproducible date-only Gregorian bounds; deterministic SQL Server compilation and metadata verification; bounded execution; truthful empty/truncated output; clarification and report refinements; a loopback reference frontend; no secrets, policy values or result rows in model requests; existing APIs and tests continue working.

**Non-goals for this slice:** Model-written SQL, model-selected joins, arbitrary expression formulas, cross-database reporting, timestamp timezone conversion, fiscal/Persian calendars, automated SQL Server security provisioning, production web authentication, and a final PDF/document layout. Broader capabilities remain separately scoped. The [SDK SQL Server execution design](SDK_SQL_SERVER.md) defines the adapter boundary; Step 5 remains undefined.

**Verification:** Offline tests cover real synthetic totals and frontend HTTP conversations, fake driver/provider boundaries, persistent clarification/refinement, policy enforcement, metadata drift, retries/concurrency, cancellation and resource cleanup. An opt-in SQL Server golden test requires a host-seeded synthetic dataset. Live provider/SQL Server and Rahtal verification are separate from these offline results.

## Live Rahtal frontend slice

**Outcome:** A local frontend uses the existing Rahtal SQL Server and configured model endpoint, including employee-name listings and activity-hour reports. The host reuses local credentials, owns one explicitly authorized local reporting principal, and exposes only the approved activity/profile columns. No database objects are provisioned.

**Acceptance:** A real interpreter selects distinct registered employee dimensions without a fake aggregate; mandatory soft-delete predicates and bounded SELECT execution remain enforced. The frontend clearly identifies Rahtal mode, accepts normal questions and refinements, and never silently falls back to synthetic data. Existing local/legacy Rahtal and sibling backend configuration can be used without copying secrets. Offline tests verify configuration, policies, listings and HTTP auth; live connectivity and conversation results are reported separately.

**Boundary:** This is a loopback, single-principal developer demo with access to approved Rahtal employee/activity data, not per-employee production authorization. Reports remain single-source: employee name listings use profiles and hours use activities with employee IDs. No model-selected joins, new reporting views, database writes or Jalali conversion.

**Live check (2026-10-05):** The existing configured model returned a valid employee-name listing without an aggregate and asked for the year on a September activity report. An authenticated HTTP conversation clarified the calendar for `1403`, then reached execution after `2025`. The local Rahtal host starts and rejects unauthenticated session requests. TCP and ODBC connection attempts to the configured SQL Server still time out; real rows, live metadata compatibility and report totals remain unverified. No synthetic fallback is used.

**Chat correction:** Assistant questions and explanations use registered readable labels and business language; technical concept IDs and report options stay in the structured specification. A straightforward employee-name request proceeds without asking the user to confirm internal options. Connection failures are identified before query execution and explain how to retry after restoring connectivity, while secrets and raw driver errors remain private.

**Correction verification:** A live interpreter replay of greeting → profiles → first and last names now clarifies the first two incomplete requests in business language and produces the correct name-list specification for the final request. Offline regressions verify readable labels, unchanged specification IDs, no query on failed connection, idempotent failure receipts and successful retry after connectivity returns. Live database reachability remains the separate blocker above.

**Local host ownership:** The frontend uses exclusive socket binding on Windows so two workspaces cannot share one port with different access tokens. A real occupied-port regression verifies that the second startup fails and preserves the running workspace's token file.

## Step 1: report-planning conversation (complete)

**Outcome:** The user enters a report question, supplies the configuration shown in the diagram, and can continue a conversation with an AI assistant about the desired report.

**Inputs**

1. A natural-language report question, followed by optional follow-up messages.
2. Configuration: Database → Server/Host, Database, Authentication method, ODBC Driver; LLM → API Key, Base URL, Model.

**Acceptance criteria**

- Python API and interactive CLI capture the first question and all configuration fields.
- A conversation keeps successful user/assistant turns in order and sends prior turns with each new question.
- Failed model calls do not enter the conversation history; the user can retry.
- The API key is masked in object representations and hidden when typed in the CLI.
- Database configuration is held locally and is not forwarded to the LLM.
- Offline tests verify the conversation, model adapter, and CLI. No database or model credentials are needed for tests.

**Boundary:** This step does not connect to the database, inspect its schema, generate SQL, or create a report. The existing SQL proposal API is an earlier experiment and remains available separately.

## Step 2: request understanding (complete)

**Outcome:** The AI determines what report the user wants. If the request is materially ambiguous, it asks one focused clarification question and reassesses the reply with full conversation history. Once sufficiently clear, the program prints a concise understanding and proceeds to Step 3.

**Acceptance criteria**

- The provider returns a structured decision: enough information, current understanding, and clarification question.
- A request ready for the next step prints `Request understanding` and proceeds to context resolution without generating a report.
- An incomplete request asks one question and preserves the conversation for the next assessment.
- Malformed or contradictory provider output fails closed; failed turns are not added to history.
- Offline tests cover ready, clarification, invalid output, and CLI behavior.

**Enough information:** The report's subject and intended result are identifiable, and any ambiguity that would materially change the report has been resolved. Optional presentation preferences can wait. Never invent missing details.

## Step 3: context resolution (complete)

**Outcome:** After request understanding, identify the user's time period, entities, metrics, filters, and comparison period. Ask one focused question when a material context detail is missing. Print the resolved context and proceed to Step 4.

**Acceptance criteria**

- A typed result contains all five fields. Absent optional filters and comparison periods remain empty.
- A ready result has a time period, including an explicit “all available data” choice; otherwise ask for it.
- The provider sees the request conversation and its understanding, but no database or LLM credentials.
- A material gap yields one clarification question; the answer is assessed with prior history.
- Ready context prints all five fields without connecting to a database or generating a report.
- Malformed or contradictory model output is rejected without advancing session history.
- Offline tests cover ready, clarification, invalid output, and CLI flow.

**Boundary:** Preserve relative time phrases such as “last quarter” as written. Converting them to exact dates requires calendar and timezone rules in a later step. Entity labels are business concepts, not verified database tables or columns.

## Step 4: query space discovery (complete)

**Outcome:** After context resolution, accept a structured catalog supplied by the package user and print relevant tables/views, columns, supplied relations, and definitions.

**Acceptance criteria**

- Accept a JSON catalog file through the CLI and the same JSON-shaped data directly through the Python API. Each table includes its columns; relations and definitions are optional.
- Consider every supplied table and column within the documented candidate limits, without silently dropping objects from the user's catalog.
- Keep schema objects in an immutable catalog and validate that columns and relations refer to real catalog objects.
- Bound the candidate metadata sent to the configured LLM. Never include server, database connection details, credentials, or row values in its request.
- Accept only IDs from the candidate catalog in the model's structured selection, rejecting unknown, duplicate, or inconsistent choices.
- Show the four categories and explicitly report when no relevant foreign keys or definitions were selected.
- Do not connect to the database in the current CLI flow. Existing Database configuration remains captured for later steps.
- Offline tests cover JSON input, model selection, invalid output, and CLI flow. No database is needed.
- `main.py --example` demonstrates the Python API from an inline question and schema dictionary; ordinary `main.py` arguments still start the interactive CLI.

**Boundary:** Relations and definitions come from the user's catalog; they are not inferred from a live database. No database connection, SQL generation, row access, or report creation occurs in this step.

## Step 5: not yet defined

The user has not specified Step 5. Do not assume its purpose or claim it has been implemented.

## Step 6: query planning (complete)

**Outcome:** Turn the understood request, resolved context, and selected query space into an ordered logical operation plan. Show how the plan was checked and which choices need review before SQL generation.

**Acceptance criteria**

- A Python API and the interactive CLI produce scan, supplied-relation join, time filter, business filter, aggregate, and comparison operations when needed.
- All table, column, and relation references are selected query-space IDs. Joins must extend a connected path from the base table.
- Every resolved metric and filter is mapped once. Numeric aggregates use numeric columns when types are known; time operations use temporal columns when types are known.
- A model proposal with unknown IDs, disconnected joins, missing mappings, or a conflicting explicit time grain fails before it becomes a plan.
- A malformed or structurally invalid model plan gets at most one correction request when the provider supports it. The correction contains validator feedback, not the prior model response; a second invalid plan fails closed. Provider and pilot policy failures do not trigger correction.
- The result keeps relative time and comparison phrases symbolic. The quality view marks date boundaries, calendar/timezone rules, metric formulas, inferred filter values, and comparison calculation for review when applicable.
- `main.py --plan-demo` runs a deterministic offline example through the real plan validator and quality review. `main.py --example` runs the full model-driven path.
- No database connection, SQL generation, row access, or report creation occurs in this step.

**Boundary:** Structural validity means the plan references the supplied schema consistently. It cannot establish that the supplied schema matches a live database or that the model chose the correct business meaning. Comparison operations are placeholders until date alignment and calculations are defined.

## Step 7: SQL generation (complete)

**Outcome:** Render the validated logical plan into readable, parameterized SQLite SQL and show it in the demo and interactive flow.

**Acceptance criteria**

- Render selected tables and supplied joins, time buckets, filters, dimensions, and aggregate measures deterministically; the model does not write the SQL string.
- Quote schema, table, and column identifiers; keep filter values and date boundaries in named bind parameters.
- Accept exact ISO start and exclusive end dates from the caller. Leave named parameters marked as required when dates remain unresolved.
- Render comparison periods as labeled base and comparison rows when requested, without inventing a delta calculation.
- Validate the generated statement as a single read-only SQLite query before returning it.
- `main.py --plan-demo` prints the SQL and parameters; offline tests execute it against synthetic in-memory SQLite tables and check the returned totals.
- The package does not open a production database connection or execute the generated report query.

**Boundary:** SQLite is the only Step 7 dialect. The configured ODBC driver does not select a dialect yet. Caller-supplied bounds, join semantics, metric formulas, and filter values still need business review. SQL with required date bindings is a template until those bindings are supplied.

## Step 8: validation and safety (complete for SQLite)

**Outcome:** Check a SQL candidate before execution; discard a bad candidate and regenerate once from the structured plan when possible.

**Acceptance criteria**

- Parse one SELECT-only SQLite statement and reject invalid, multiple, or write statements.
- Check the plan's tables, columns, and relations against the selected user-supplied query space.
- Require exact agreement with a fresh deterministic rendering of the plan, including bound values. This also prevents omitted filters and added references in SQL.
- Require every resolved metric and filter, plus any caller-specified `RequiredFilter`, to appear in the plan. Check explicit time, entity, and single-metric aggregation facts when they can be matched mechanically.
- Block unbound date parameters. Report unresolved business interpretation as review items rather than claiming it is proved by syntax.
- A supplied bad SQL candidate may be discarded and regenerated once; a bad plan, missing required filter, or missing dates fails closed.
- When the request explicitly says to use all base-table rows, convert proposed inner joins to left joins and show the repair. Validation blocks an unrepaired inner join for that case.

**Boundary:** Mechanical checks cannot prove a business definition, join cardinality, or the correctness of a model's interpretation of ambiguous language.

## Step 9: query execution (complete for SQLite)

**Outcome:** An explicit API call or `--execute-sqlite` flag runs the validated query on caller-chosen SQLite files and returns bounded rows.

**Acceptance criteria**

- Revalidate immediately before execution and never accept an existing read-write connection.
- Open the file using SQLite `mode=ro`; attach named schema files explicitly using the same mode; enable `query_only` and a restrictive SQLite authorizer.
- Permit reads only from supplied selected tables and columns and the functions used by the renderer. Deny writes, attachment, pragmas, and other actions from the report query.
- Bound returned rows, elapsed time, and SQLite virtual-machine work. Mark truncated results, close connections, and sanitize database errors.
- `main.py --plan-demo` creates a synthetic temporary database, executes the SQL read-only, prints rows, and removes the file. Tests cover validation failures, repair, authorization limits, and execution.

**Boundary:** SQLite is the only executable dialect. ODBC connection fields captured earlier are not used by Step 9. Read-only local file access does not replace database permissions or human review of report semantics. Report formatting is still a later step.

## Rahtal daily-performance integration pilot

**Outcome:** A person edits the ignored `sageql_rahtal/local_config.py` to set the question and run options, runs `sageql_rahtal/run.py`, and receives a unique Markdown and JSON report for each run. A tracked example config and `--question` file override support reuse. The report records input, model stages, schema discovery, plan and repairs, deterministic T-SQL, validation, timings, and bounded query results or the reason the run stopped.

**Acceptance criteria:** Verify the approved `Activities`, `User`, and `Person` catalog against live SQL Server metadata. Exclude nonapproved private fields. Keep database connection settings and rows out of model requests. Read question, mode, bounds, and limits from local config while keeping secrets in `.env`; reject malformed values and incomplete date pairs before model calls. Bound each model request and disable transport retries so endpoint stalls become timed failure reports. Apply activity and profile soft-delete policies in generated SQL. Revalidate the exact SQL and ordered parameters before execution. Allow a login with table-write permission to execute validated SELECT reports. Save reports on success, clarification, and failure. Offline tests cover policy SQL, local config, and both privileged and read-only logins; a manual smoke test uses real data only when available.

**Current finding:** The configured local Rahtal login has effective `INSERT`, `UPDATE`, and `DELETE` on the approved tables. A first live SELECT completed before this was discovered; the former permission guard blocked later execution with that login. The guard has been removed, while query validation remains in place. A later `--no-execute` run completed through SQL validation with the sample question and recorded a policy repair plus removal of unused joins. The default local-config run also completed through SQL validation on 2026-09-27 and saved a per-stage report. The local config and reports directory are ignored by Git.

**Clarification continuation:** The runner keeps the understanding and context sessions open while a terminal user answers focused questions. Each turn retains the original request and prior answers, records the provisional context locally, and resumes the same pipeline after a ready context. Offline tests cover multiple turns, validation and execution after clarification, and closed input. The session is in memory for one invocation; `/exit` and closed input save an incomplete report without querying data. SQL validation and execution guards remain unchanged.

## Later steps (require a specific user request)

- Add declared-grain safe joins, timestamp/calendar semantics and report export only as separately scoped slices.
- Define the historical Step 5 if the staged CLI needs it. SDK table/chart JSON already exists independently.

## Persian conversation and report defaults

Outcome: the embedded SDK and local reporting frontend default to Persian.
Acceptance: Persian model instructions cover greetings, clarification, refinements,
digits and letter variants; deterministic greetings/errors/titles and built-in
date headers use Persian; shipped catalogs use Persian business labels/units;
the browser uses RTL and Persian display digits without changing JSON values.
Hosts can explicitly select English for SDK/provider presentation. Offline tests
cover Persian multi-turn reports, literal Unicode filters, persistence/retries,
and unchanged authorization/SQL boundaries. No calendar conversion, translation
of arbitrary host labels or row values, new model endpoint, or broader SQL scope.

Verification (2026-10-06): 480 Python tests passed, 1 opt-in SQL Server test
skipped. Offline Chrome/Playwright checks passed for Persian RTL, exact decimal
display, Gregorian dates, tabs/history, retries and mobile width. The Persian
SDK embedding smoke test, isolated package build and fresh-wheel import passed.
The active development environment lacks `hatchling`, so `--no-isolation` is
unavailable there; the normal isolated build succeeds. Live configured model/
SQL Server Persian understanding had not yet been verified at that stage;
the employee-name check below records the subsequent live verification.

## Employee-name activity requests

Outcome: resolve a supplied employee name using the permitted profile source,
then run the approved activity report without asking for an internal employee ID.
The [scoped lookup design](SDK_ENTITY_LOOKUPS.md) defines registration, exact
normalized full-name matching, ambiguity, data boundaries and verification.
Acceptance includes unique/duplicate names, job qualifiers, Persian spacing and
letter variants, current source/target policies, bounded lookup reads, offline
regression tests and persistent name-based refinements/retries. No model-selected
join, new database object, fuzzy identity selection or broader activity columns.

Live verification (2026-10-06): the configured interpreter correctly selected
the employee-name filter, all three registered activity measures, `last_month`,
daily grouping and table for the user's Persian request. A first interpretation
returned invalid output and failed closed; a separate manual attempt succeeded.
Executing that validated specification against the configured SQL Server resolved
the name and returned 27 daily rows through separate profile/activity SELECTs,
without asking for an ID. No rows or derived identities were sent to the model;
production names and responses remain only in ignored local smoke-test files.

Offline verification (2026-10-06): 514 tests passed and 1 opt-in synthetic SQL
Server test was skipped. Lookup regressions cover actual SQLite totals, SQL
Server parameter/cleanup and diagnostic redaction boundaries, persistent
refinements, ambiguity, source/target policy changes and malformed adapter output.
The isolated sdist/wheel build and fresh-wheel import/public-contract/name
normalization smoke check passed.

## Name-lookup clarification progress

Outcome: a named employee activity request proceeds to the registered lookup
without asking for an internal ID or repeated permission to search by name.
Acceptance: interpret the original request and follow-up answers together;
correct an invalid ID/search-confirmation question once within the existing
provider deadline; validate the corrected specification through the ordinary
engine; stop safely if correction still stalls. Genuine missing dates/names and
host-generated missing/ambiguous-match questions remain available. Regression
checks use a fake model transport and policy-bound synthetic data. No new
lookup matching, SQL scope, identity exposure or external service is introduced.

Verification (2026-10-06): the focused provider/lookup regressions and full
offline suite pass; isolated sdist/wheel builds and the synthetic SDK embedding
smoke pass. The configured Rahtal model returned the expected complete daily
activity specifications for both a direct synthetic full-name request and a
conversation containing the prior mistaken ID/lookup questions followed by
«با اسمش». A request without a name asked for the missing name. These live
interpretation checks executed no database queries and do not establish live
report totals or universal model correctness. The running loopback host was
restarted with its existing configuration, workspace token and session store.

## Data boundaries

The historical chat provider receives conversation messages and model configuration. In Step 4 it also receives bounded table/column/relation metadata and definitions; Step 6 receives understanding, context and selected metadata. It does not receive database connection fields or row values. Historical CLI sessions are in memory. The SDK interpreter receives only permitted business metadata, messages and current report specifications; it omits physical names, policies and result rows. SDK session stores explicitly persist messages and report rows under host control.

## Rahtal local execution diagnostics

Frontend follow-up: put the existing trace in a separate **Steps & logs** tab
beside the report result. Keep each completed attempt available within the current
chat, with a readable stage timeline, durations, raw event details and a local JSON
download. Switching tabs or attempts must not submit a message or query data.
New chat clears the trace history; failures retain the latest successful result.
This slice consumes the existing redacted diagnostics only, adds no new backend
logging or telemetry, and does not implement historical Step 5 or live progress.

Verification (2026-10-06): offline Chrome/Playwright check passed for tabs,
keyboard navigation, attempt history, failure result retention, cached retries,
JSON download, text-only trace rendering, mobile width and other host modes.
The isolated package build passed. Full Python suite: 468 passed, 1 skipped,
5 failed on English-text expectations affected by concurrent Persian-language
changes outside this frontend slice. No live Rahtal/model query was run.

User outcome: inspect the test frontend's interpretation, validated report
conditions, deterministic SQL, execution stages, counts and safe failures.
Acceptance: authenticated Rahtal responses show an attempt trace; ignored local
JSON files record stage progress; empty results and cached replies are explained;
no credentials, personal filters or rows enter diagnostics, and no extra SQL is
executed. Other SDK/HTTP modes retain their contracts. This does not infer the
root cause of empty data or add policy-bypassing diagnostic queries.

## Bounded agent report interpretation

**Outcome:** Interpret user requests, clarification answers and refinements
through a planner and semantic reviewer over the permitted registered catalog.
The planner can reconsider a rejected proposal without a separate keyword or
regular-expression branch for every phrasing. The scoped contract and public
interfaces are documented in [SDK_AGENTS.md](SDK_AGENTS.md).

**Acceptance:** `AgentReportInterpreter` implements the existing `ReportProvider`
interface over a replaceable `ReportAgentBackend`; `AgentReview` carries a bounded
semantic judgment and `OpenAIReportAgent` uses the existing configured endpoint.
Each proposal passes strict shape/vocabulary checks and a local ready-report
preview before semantic review. A review rejection can produce a complete
revision; local semantic-validation feedback contains only fixed error codes.
Malformed output, extra SQL/code fields and unknown concepts fail closed rather
than being repaired. `max_revisions` is 0 through 3, default 1; at most eight model
requests share one deadline, default 30 seconds and bounded to 180 seconds.
Unapproved attempts end with safe `agent_exhausted` feedback. Fake transports and
synthetic fixtures cover budgets, context, data exclusion, count-only preview,
policy enforcement, persistent refinements and idempotent receipts.

**Boundaries:** The preview uses a policy-free synthetic scope only to check
permitted vocabulary and operations. Empty-column count-only projections use
private preview scaffolding that is neither serialized nor executed. The engine
still authorizes against the full trusted catalog/current actor policies,
resolves registered names locally, compiles deterministic SQL, and requires
explicit execution opt-in. No physical names, policies, credentials, rows or
resolved identities enter planner/reviewer requests. No model-selected joins,
arbitrary formulas, new objects, broader calendars, unrestricted database tools,
production authentication or historical Step 5 is introduced.

The live generic SQL Server web host and Rahtal SDK frontend select the new agent
provider. `OpenAIReportInterpreter` remains available for explicit compatibility;
the historical staged flow, isolated pilot runner and scripted demos retain their
existing behavior. Planning and review are separate requests to the same
configured model, so correlated mistakes remain possible. Extra requests add
latency and usage cost; neither semantic approval nor this scope promises that
every natural-language request is understood.

**Verification (2026-10-06):** All 79 focused agent tests passed; the full offline
suite passed with 642 tests and one opt-in synthetic SQL Server test skipped.
The isolated sdist/wheel build, fresh-wheel install/public agent imports and
documented synthetic SDK embedding smoke passed. Independent review found and
fixed typed Decimal/date filter compatibility; regressions cover custom agent
outputs and persistent switching from an existing provider.

The existing configured model completed two interpretation-only checks: a daily
request with a synthetic full name selected all three registered activity
measures, `last_month` and daily grouping; a greeting returned clarification.
Both used the new planning/review flow. These checks made no database calls and
transmitted no lookup results or production rows. Live SQL Server execution with
this flow and universal language correctness remain unverified.

## Rahtal request timeout increase (2026-10-07)

Outcome: give slow local Rahtal report requests more time to finish. Acceptance:
the shared model interpretation budget is 180 seconds, the overall request
deadline is 240 seconds, and each SQL execution is capped at 30 seconds.
Scope: only the Rahtal SDK frontend defaults; retain row bounds, deterministic
execution, policies and finite deadlines. Offline setup and HTTP tests verify
the integration; live model/database performance is not verified by these tests.

## Registered entity-label dimensions (2026-10-07)

Outcome: employee rankings can refine from IDs to names without changing their
measures, dates or top-N. Acceptance and boundaries are specified in
[SDK_ENTITY_LABELS.md](SDK_ENTITY_LABELS.md). Implement a host-registered display
dimension, policy-bound bounded post-aggregation reads, provider capability
metadata and Rahtal registration. Verify duplicates, missing/conflicting names,
access revocation, persistence, retries and model data exclusion. No joins,
new database objects, hardcoded conversation routing or broader authorization.

Verification: 682 offline tests passed, one opt-in synthetic SQL Server test
skipped. The isolated sdist/wheel build, fresh-wheel installation/imports and
documented SDK demo passed. The configured real model replayed the supplied
name-refinement/confirmation conversation, preserving its existing activity-hours
metric, descending order and top ten. Real Rahtal execution returned ten named
rows through two bounded SELECTs, with unchanged metric values/order and no
missing labels; no production names/rows were printed or sent to the model.
A separate new ambiguous-ranking check eventually requested criterion/period;
another attempt exhausted the bounded review loop. These checks demonstrate the
tested behavior, not universal natural-language reliability. Existing user
timeout changes were retained. No commit was created.
The existing loopback frontend was restarted with its original workspace token
and persisted session store; `/config` confirms authenticated Rahtal mode on
port 8766. Start a new chat for the updated catalog.

## Rahtal company report 2: complete conversations and explicit Jalali months (2026-10-08)

Outcome: show each manager conversation through its final real SDK result, replay
the two questioned examples, and add more complex reports using Persian months.
The first report separated clarification and completion onto different pages;
both quoted conversations had successful later turns. Presentation now keeps
the full conversation and its final status together.

The scoped implementation adds local deterministic `jalali_month` resolution
under [SDK_JALALI_MONTHS.md](SDK_JALALI_MONTHS.md), explicit selection provenance
and persisted refinements. Model prompts select month/year; they never convert
dates. Gregorian storage/daily buckets, policies and deterministic SQL remain.
A narrowly classified ordering inconsistency can consume the existing bounded
agent revision budget; malformed/unknown output still fails closed. Planner-only
reproductions established a strict ordering rejection, not token truncation;
the exact subtype of the historical failures cannot be proven from saved traces.
Verification and live evidence are recorded below when the slice is complete.

Additional planner-only diagnosis of the original Gregorian two-month comparison
reproduced `invalid_interpretation` with `finish_reason=length`, 4,096 completion
tokens, 4,096 reasoning tokens and zero output bytes. That concrete replay
exhausted the output budget; it does not establish a single cause for every
historical failure. The named-employee Jalali comparison's separate planner
replay passed strict validation with 4,036 completion tokens (3,904 reasoning);
a subsequent full-interpretation attempt stopped at planning with the same
4,096-token reasoning-only exhaustion, before any reviewer request. These
diagnostics executed no database query and retained only fixed structural
categories, counts and source hashes in ignored local report-2 files.

The Rahtal host now explicitly supplies `max_output_tokens=8192`; generic SDK
defaults, the shared 180-second interpretation deadline, the 240-second request
deadline, strict decoding and revision limits remain unchanged. Fake transport
tests verify that empty length-exhausted output still fails without replanning;
host setup tests verify the explicit budget. This adds no generic retry and
does not accept partial model output or enable any new query operation.

Business-intent QA then found a distinct semantic issue in the monthly all-data
top-24 example: a model-selected date range excluded the current partial month
and the last day of September. Report-ready status and strict SQL validation do
not establish business correctness. Shared planner/reviewer guidance now keeps
output limits separate from periods: explicit all-data requests retain `all`,
and latest-N groups use ordering/limit rather than invented dates. No keyword
router or model-data feedback is introduced. A local scenario acceptance audit
checks requested measures, effective periods, grouping, ordering and limits;
the full demonstration is rerun after this prompt correction.

Final verification: 772 offline tests passed and one opt-in synthetic SQL Server
test was skipped. The documented synthetic SDK embedding demo passed. Independent
Node Intl checks matched 7,200 Jalali boundary conversions with no differences.
The label-leak test now checks exact scalar identities rather than accidental
identity substrings inside randomly generated report UUIDs.

The final live run contains 11 completed scenarios and 21 actual turns: 15 report
responses, three clarification responses and three failed attempts. The three
failures were followed by explicit new attempts with identical manager messages
in the same sessions; their errors and receipts remain in the report. All five
run archives retain 59 turns, including two earlier report-ready responses with
incorrect business periods. Final acceptance passed 401 scenario-intent checks,
46 numerical checks and 142 evidence-selection checks. These are demonstration
acceptance checks, not a universal language-correctness guarantee or a new SDK
automatic retry mechanism. Further work should measure planner/reviewer semantic
accuracy and failure rates across a broader held-out set.

The reviewed company report has 35 pages, with all pages visually inspected;
native Persian HTML and a UTF-8 transcript accompany the PDF for reliable copying.
Real local evidence, session receipts, source snapshots and replay scripts remain
ignored and contain no bundled credentials. Two isolated packaging attempts were
blocked while obtaining hatchling from PyPI; a current wheel/fresh-install check
is therefore unverified. Source imports and tests do not substitute for that
release gate. No commit was created.

## Registered relationships and general management reports (2026-10-09)

User outcome: management reports can aggregate a fact's measures by explicitly
registered attributes from other sources, refine them in conversation, and rank
the final groups. Implement the reusable contract in SDK_RELATIONSHIPS.md;
register the existing Rahtal activity/profile relationship as a host integration.
Also resolve parameterized rolling date windows locally rather than asking the
model to calculate three-month date arithmetic. Preserve previous local changes.
No model-written SQL, guessed joins, new database objects, unregistered formulas
or promise of unlimited report capabilities. Verification results follow below.

Implemented reusable host registrations, composite equality keys, independent
dimensional sources, source-aware permission pruning, unambiguous business-intent
equivalences, deterministic guarded SQL Server/SQLite compilation, physical
metadata checks on all active sources and persistent conversation refinements.
Added typed post-aggregate conditions and locally resolved rolling Gregorian
count/unit windows. Rahtal imports current position and its filter on activities;
it creates no database objects. Existing local edits were preserved.

Verification: 51 new focused tests passed; the final offline suite passed with
861 tests and one opt-in synthetic SQL Server test skipped. The existing
synthetic embedding demo and git diff whitespace check passed. Live configured
model checks selected the correct rolling window/ranking, refined to job
position, and added the >100-hour aggregate condition. A canonical real Rahtal
SQL Server report passed with five groups and no truncation; private rows and
credentials were not printed or copied into tracked artifacts.

The isolated package build could not obtain hatchling from PyPI because of
network read timeouts. Building sdist and wheel with the installed build runtime
(`--no-isolation`) succeeded. A fresh wheel target installation and public
imports passed using the existing dependency runtime; a fully fresh dependency
environment remains unverified. No commit was created.

Suggested commit message for this extension:
`feat(sdk): add registered relationships, aggregate filters, and rolling periods`

## Align effective intent periods with necessary clarification (2026-10-09)

The exact reported job-position request matched failed receipts in a fresh local
session (revision zero, no messages/current report). The persisted trace records
intent_mismatch but does not retain stage proposals, so historical rejected
outputs are not reconstructed. Interpretation-only replay exposed a second
failure: the intent omitted period and missing details, and planner/reviewer
accepted all dates without user evidence. The old intent prompt required periods
for new rankings while planning required them for any dated aggregate.

Add an effective typed PeriodSelection to ReportIntent and share the dated
aggregate requirement across intent/planning/review. Locally add a period missing
slot if a new dated aggregate has no period; inherit the current period only for
same-dataset refinements/answers without a changed time clarification. Check
accepted ready periods against effective resolved bounds. Preserve focused year/
calendar questions, all-data requests, timeless counts, dimension-only listings
and normal revision/time/access boundaries. No question-specific routing, relaxed
intent guard or database operations are added.

Verification: 874 offline tests passed and one opt-in synthetic SQL Server test
was skipped. Configured-model replay returned the necessary clarification, then
selected job-position grouping and a three-month rolling period after the answer.
The active loopback host on port 8768 was restarted with its existing workspace
token and persistent sessions; the separate host on 8766 was left running.
The same two-turn HTTP conversation returned clarification without SQL, followed
by a real SQL Server report with six groups and no truncation. Saved original
period selection and the conversation's intentionally frozen date bounds were
both verified; no result rows or credentials were printed or added to tracked
files.

The current sdist/wheel build passed using the installed build runtime with
`--no-isolation`; fresh wheel-target installation and public typed-period imports
passed using existing dependencies. The earlier isolated build's network timeout
still leaves a completely fresh dependency environment unverified. Diff whitespace
checks passed. No commit was created.

Suggested commit message:
`fix(sdk): align intent periods with aggregate clarification`

## Increase the live reporting budget (2026-10-09)

User outcome: allow complex live report interpretation more time and repair
opportunities. The latest local failed trace ended in agent_exhausted after
about 77 seconds, before its 180-second deadline. Raise Rahtal's shared model
budget to 600 seconds, its overall request to 660 seconds and revisions from one
to three. Extend trusted SDK model-timeout acceptance to 600 seconds and overall
request limits to 900 seconds; keep query limits independently capped at 300
seconds and Rahtal SQL at 30 seconds. Default generic SDK budgets, strict report
checks, transport no-retry settings and finite repair/deadline behavior remain.
Verify the higher boundaries and shared deadline with offline fake transports,
then activate the existing local host while preserving its token/session state.

Verification: 266 focused tests and the complete 882-test offline suite passed;
one opt-in synthetic SQL Server test was skipped. A fake clock exercised four
proposals/three revisions over 480 seconds while preserving the decreasing shared
deadline. Transport tests verified the 600-second timeout with automatic retries
disabled; overall request and independent SQL bounds were checked. Current
sdist/wheel builds passed with the installed build runtime (`--no-isolation`),
and fresh wheel-target imports passed using existing dependencies. A completely
fresh dependency environment remains unverified after the previously recorded
network failures. The host on 8768 was restarted with the existing token and
sessions; authenticated access to a saved session passed. No live semantic report
replay was run in this timeout-only slice, and larger budgets do not guarantee
semantic agreement. Diff whitespace checks passed. No commit was created.

Suggested commit message:
`fix(rahtal): increase bounded report interpretation and repair budgets`

## Verify a managerial workload conversation (2026-10-09)

Outcome: compare Shahrivar/Mordad 1405 workload by current position, drill down
to employee names, select up to ten employees below 80 recorded hours in
Shahrivar, and show the same selection in a bar chart. The report describes
recorded workload and includes employees with activity, not productivity or
the complete roster. Acceptance and runnable local check are in
[SDK_MANAGEMENT_REPORT.md](SDK_MANAGEMENT_REPORT.md).

The configured model initially returned an incorrect unsupported claim about
two explicit Jalali months. Shared capability guidance and review of prose-only
unsupported claims corrected this case. Add bounded optional effective intent
controls for comparison, row/aggregate filters, ordering/direction and limit;
strict live decoding and fixed local feedback reject silent losses before
review/execution. Explicit empty controls remove earlier constraints, while
defaults preserve existing custom-backend compatibility.

Add a local live-check CLI with an independent Python arithmetic oracle over
bounded, policy-bound SDK source-grain reads. Private sessions/source/reply/spec
artifacts and HTML remain ignored and local. No result rows go to the model.
The frontend adds a managerial example and displays both comparison names and
execution ranges without changing stable JSON period row keys.

Independent review reproduced tied top-N drift when display dimensions were
reordered. Deterministic metric ranking now prioritizes entity-label identity
ties before other categories, preserving explicit primary ordering and time/
period ties. Regression coverage reverses employee/position column order with
more than ten equal-hour employees, then verifies the chart selects the same ten.

All four configured-model/real-SQL Server turns matched the local source oracle;
final compiler replay of those accepted specifications matched again without
new model calls. The final complete offline suite passed: 971 tests and one
optional synthetic SQL Server skip. JavaScript syntax, whitespace, installed-
runtime package builds and fresh-wheel-target imports passed; completely fresh
dependency installation was not checked. Interim Windows socket test aborts
passed on rerun and did not recur in the final complete suite.

Activated the updated authenticated frontend on port 8770 using separate private
state/token under `.venv/rahtal-management-web/`; existing hosts were preserved.
No database objects or writes, new remote service, credentials or private result
rows were added to tracked files. Existing changes were preserved; no commit.

Suggested commit message:
`feat: add verified Rahtal workload reports and preserve SDK intent`

## Manager-friendly activity reports (2026-10-11)

Requested outcome: managers can report total recorded work by employee and
activity topic, compare periods, and use Persian business dates naturally.
Register the existing TitleActivity source through a fixed many-to-one mapping;
do not discover arbitrary sources or create database objects. Add distinct
participant counts for topic totals. Register workload defaults and require an
explicit request before selecting average duration. Friendly capability answers
and locally generated report summaries must explain the measure and period.

Extend the date-only contract to explicit Jalali ranges/years, relative Persian
months/years and rolling Persian months, and bounded Jalali monthly grouping.
The host computes conversions and month boundaries; models select typed calendar
operations only. Missing years in named months remain clarifications. Relative
periods freeze on success. Verify leap days, year rollover, aggregation before
ranking, policies and relationship cardinality, persistence, strict provider
schemas and frontend Persian date rendering with synthetic offline coverage.

Non-goals: inferred productivity scores, arbitrary formulas, model-selected
joins, timestamp conversion, unbounded calendar grouping, production employee
identity, or transmitting database rows to the model.

Implemented the registered activity-topic relationship, total-hour/activity-count
defaults and explicit-average/ranking vocabulary checks. Capability and vague
quality questions now receive immediate local replies. Added local Persian
range/year/relative resolution and bounded monthly SQL buckets in both adapters;
saved regroupings keep their dates, explicit date changes take precedence, and
rolling window counts cannot silently become time-series row limits. The Rahtal
frontend shows Persian dates, exact execution bounds and manager examples.
Private diagnostics now distinguish intent, planning, review and business checks
using validated business selections and fixed error codes, without model prose
or result values.

Verification (2026-10-11): 1,042 offline Python tests passed and one opt-in
synthetic SQL Server test was skipped. Chrome/Playwright frontend regressions
passed, including Persian dates, precise decimal strings, rounded float display,
topic/trend examples, history/retries and mobile layout. Source and wheel builds
passed; an isolated wheel installation imported the public SDK and new local
calendar helpers successfully.

Live checks used the existing configured model and SQL Server: the capability
reply, topic/employee contributions, topic-only refinement, focused quality
clarification and six-month Persian monthly chart succeeded. Contribution and
regrouped totals, and the sum of the monthly chart, matched independent scalar
source queries. The chart retained all seven intersecting Persian months without
truncation. Initial live failures exposed rolling-period/full-month confusion,
date drift during regrouping, and Gregorian/Persian grain disagreement; local
evidence checks and regression tests now cover those specific cases. This does
not establish universal language understanding. Private results remain ignored.

The follow-up quality conversation also completed after the user selected total
hours: the original six-month Persian window was retained and the top person's
recorded-hours measure matched a separate identity-grouped ranking query. The
configured model initially mislabeled that short answer as a new request; the
known local criterion question now preserves its conversation context. Local
capability/criterion replies took under one second; the tested model-backed
reports still took approximately 47–64 seconds.

The updated authenticated frontend runs at http://127.0.0.1:8771 with separate
local state under `.venv/rahtal-manager-web/`; other hosts were preserved. No
database objects or writes were added. No commit was created.

Suggested commit message:
`feat: add topic-aware managerial reports and Persian calendar support`

## Verify organization totals for Shahrivar 1405 (2026-10-11)

Outcome: submit the exact requested organization summary through the configured
Rahtal interpreter and check recorded hours, activity rows and distinct active
participants separately against a bounded, policy-bound source read.

Acceptance: all three requested activity metrics, no employee/topic grouping or
extra user filter, the supplied Persian month/year with Gregorian boundaries
2026-08-23 inclusive and 2026-09-23 exclusive, and one complete aggregate row.
Count participants by distinct non-null activity identities, including repeat
activities only once per person; employee-profile counts are a different measure.
Test deleted/out-of-period rows, null durations/identities and equal profile names
with synthetic fixtures. Inspect the displayed result and preserve float data
while rounding presentation. Correct product behavior only if evidence shows a
defect. Keep all live rows, transcripts and source checks in ignored local state.

Non-goals: new organization authorization, new sources, database writes/objects,
model SQL, productivity scores or sending source rows to the model.

Result: the configured real interpreter returned all three requested measures
at organization grain for the correct month. A bounded host-only DISTINCT read
of existing activity row/actor/date/hour columns matched each measure through
independent Python summation, row counting and a non-null identity set. No
reporting defect was found for this request; real outputs remain ignored locally.

Added seven synthetic acceptance cases for organization totals, source policies,
month boundaries, null/empty aggregates, participant identity semantics and
planner repair before execution. Frontend coverage checks all three labels,
rounded float presentation and unchanged JSON precision. A full-suite run also
exposed an existing flaky identity-redaction assertion that confused random UUID
digits with a resolved source identity. It now checks business payloads while
explicitly exercising UUIDs with and without the colliding digits.

Verification: 1,050 Python tests passed; one opt-in synthetic SQL Server test was
skipped. Chrome frontend regressions and source/wheel builds passed.

Focused command: `.venv/Scripts/python.exe -m pytest tests/test_rahtal_organization.py tests/test_sdk_labels.py -q`.
Browser command: `node tests/web_tabs.cjs` with the bundled Node packages on
`NODE_PATH` when Playwright is not locally installed. No commit was created.

Suggested commit message:
`test: verify Rahtal organization totals and stabilize identity checks`

## Monthly absolute and percentage change (2026-10-11)

Outcome: the exact second manager question returns Shahrivar 1405 versus Mordad
1405 total hours/activity counts and each absolute/percentage change. The current
contract lacks this calculation and planner/reviewer revisions cannot repair it.
Implement the bounded [comparison-change contract](SDK_COMPARISON_CHANGES.md):
a typed fixed operation over two complete ungrouped numeric aggregate rows,
calculated locally after the existing policy-bound deterministic SELECT.

Acceptance: correct two month bounds and reference direction, both requested
measures, no fabricated percent or silent omission, null/zero/negative reference
semantics, precise decimal calculations, safe limits, persisted refinements and
retries, strict model schemas, and readable percentage presentation. Verify live
period values independently from bounded source rows before calculating changes.

Non-goals: model formulas/SQL, grouped/time-series alignment, new sources/joins,
database writes, production authorization or result transmission to a model.

Result: the original configured-model attempt exhausted planner/reviewer
revisions because the contract could return two totals but had no percentage
operation. Added `comparison_calculation=change`, strict provider/intent fields,
semantic validation and a fixed local result transformation. A subsequent live
failure also exposed whole-period monthly wording becoming monthly buckets;
bounded local evidence retains explicit percentage requests and whole-period
grain while preserving requested breakdowns. Unsupported shapes now reach
semantic feedback for normal planner repair instead of failing interpretation.

The final configured interpreter and existing SQL Server execution returned both
requested months/measures and each absolute/percentage change. A separate bounded
host-only source read independently matched all period totals and changes without
truncation. The reference is the comparison month and calculations precede
rounding. Real values/transcripts remain in ignored local run artifacts.

Forty synthetic comparison cases cover numeric/reference edge cases, malformed
adapter results, strict/legacy specifications, policies/month boundaries, planner
repair, conversation refinements, persisted receipts and idempotent retries.
Arithmetic has its own bounded Decimal context, including precision, rounding
and traps. Browser regressions cover exact decimal percentage rounding, signs,
large/exponent values, undefined zero-reference results and Persian headers.

Verification: 1,090 Python tests passed; one opt-in synthetic SQL Server test was
skipped. Chrome frontend regressions, source/wheel builds and isolated imports
from a freshly installed wheel passed. `git diff --check` passed. No commit was
created.

Suggested commit message:
`feat: add deterministic period comparison changes`

## Employee activity declines (2026-10-11)

Outcome: run the exact third question against configured Rahtal model/data and
verify each employee's two month totals, absolute hour loss and percent loss.
Initial live plans selected employee label plus comparison change, which the
ungrouped contract rejects. Add [entity-decrease scope](SDK_ENTITY_DECREASES.md).

Acceptance: identity alignment, largest absolute loss before output limits and
name enrichment, positive percent against reference, missing-month/null handling,
same real policies, complete finite candidate reads, strict intent/specification,
persistence/refinement/retry behavior, no results in model requests. Independently
check real source rows and names; private evidence stays ignored locally.

Non-goals: percentage ranking, arbitrary formulas/grouping, new sources/joins,
database writes, profile universe or production authorization.

Result: the baseline ended with `intent_mismatch` after repeatedly proposing an
unsupported grouped change. Implemented the separate fixed `decrease` operation,
strict spec/intent/schema support, complete identity candidates under host caps,
local precise absolute-loss ranking before output limits, and existing label
enrichment afterwards. Missing groups are zero only for additive measures;
existing nulls remain unknown. Candidate truncation and malformed groups fail
closed. The ordinary output default prevents two periods being mistaken for a
two-entity cap; explicit percentage-ranking wording cannot silently become
absolute ranking.

Two subsequent real configured-model/SQL Server executions produced the same
complete ranking. Independent bounded source reads and separate policy-bound
profile reads matched every displayed name, both month totals, absolute/percent
loss and order. No private values or identities are recorded here; evidence
remains in ignored per-run artifacts. Live model latency varied substantially
between those successful runs, so this verifies correctness, not a latency SLA.

Added 33 synthetic cases for identity alignment, absolute versus percentage
ordering, exact decimal ties, missing/unknown values, count measures, same names,
conflicting/denied profiles, access changes, complete candidate caps, malformed
results, planner repair, persistent retrieval/refinement and cached retries.
Browser coverage verifies Persian period headings, positive percent loss,
unaltered JSON precision, separate equal-name rows and all five columns visible
at desktop width. Visual review exposed wide nowrap headers hiding the percent
column; headers now wrap while table cells retain horizontal scrolling as needed.

Verification: 1,123 Python tests passed; one optional synthetic SQL Server test
was skipped. Browser regressions, screenshot inspection, source/wheel builds,
fresh installed-wheel imports and `git diff --check` passed. No commit was made.

Focused command: `.venv/Scripts/python.exe -m pytest tests/test_sdk_entity_decreases.py tests/test_sdk_comparison_changes.py -q`.

Suggested commit message:
`feat: add verified employee activity decline rankings`

## Top recorded-hour employees over three months (2026-10-11)

Outcome: submit the exact fourth question through the configured Rahtal model
and SQL Server, independently verify the top ten identities, total recorded
hours, activity count, average recorded duration and policy-bound names. Correct
only defects established by the run or meaningful acceptance checks.

Acceptance: the host's three-month rolling Persian period through its business
date, one employee label dimension, all three explicitly requested metrics,
descending total-hour order with stable identity ties, limit ten after grouping,
names fetched afterwards, no topic/position/date grouping or comparison. Verify
boundaries, deleted rows, averages/null durations, equal names, more/fewer than
ten identities, and planner repair before execution. Keep live evidence ignored.

Non-goals: new sources, authorization, joins/formulas, productivity claims,
database writes or transmitting source identities/rows/names to the model.

Observed defect: the first live result had correct three metrics/window/top-ten
ordering but selected both the registered employee label and its underlying plain
identity dimension, displaying an unrequested identity column. Existing intent
canonicalization removes this redundant grouping only for bar charts. Extend it
to table intent with actual user-message evidence: preserve explicit ID requests,
current identity columns on unchanged refinements and identity ordering; otherwise
retain the label alone when both map to the same registered target column. This
changes requested display selection, not identity aggregation or permissions.

The corrected configured-model/SQL Server run produced one label and all three
requested measures with the same complete ordering. A separate bounded host-only
read matched every name, sum, count and average against all in-scope activity
rows. Fewer than ten active identities were correctly returned without invented
employees. The saved rolling period spans three Persian months through the host
business date; refinements preserve those resolved bounds. Private results and
source evidence remain in ignored local artifacts.

Added sixteen synthetic acceptance cases for group-before-limit selection,
total-hour versus count/average ranking, stable boundary ties, separate equal-name
identities, null durations, date/policy boundaries, more/fewer/empty results,
wrong-plan repair, explicit ID display/removal, and persistent retries/refinements.
Browser coverage checks four Persian columns, rounding without JSON mutation,
ten-row truncation and fewer-row completeness, and the exact date caption.

Verification: 1,139 Python tests passed; one opt-in synthetic SQL Server test was
skipped. Browser regressions and screenshot inspection, source/wheel builds,
freshly installed-wheel isolated imports and `git diff --check` passed. No commit
was created.

Focused command: `.venv/Scripts/python.exe -m pytest tests/test_rahtal_employee_ranking.py -q`.

Suggested commit message:
`fix: omit unrequested employee IDs from ranking tables`

## Workload by current job position (2026-10-11)

Outcome: run the exact sixth question for Shahrivar 1405 through the configured
Rahtal model and SQL Server. Verify each current job position's total hours and
mean hours per distinct participating employee against independent source reads.

Observed failure: the baseline returned totals and participant counts but omitted
the explicitly requested mean, even after review. It also added a monthly bucket
to a single-month position report. The existing average metric describes activity
duration, not a mean over employees. Define the separately scoped, host-registered
sum-per-participant aggregate before adding its Rahtal business concept.

Acceptance: deterministic sum divided by the distinct participating identities
in the same filtered fact group; no average of activity durations or profile
headcount. Keep existing policies, registered current-position relationship and
duplicate-source guard. Group before filters/order/limits. Missing identities or
an undefined denominator yield unknown, not a fabricated mean. Explicit user
evidence must preserve the requested mean and avoid an unrequested time bucket.
Verify unequal contributions, inactive/deleted profiles, nulls, boundaries,
permission failures, model payload isolation and persistent conversations.

Non-goals: arbitrary ratios/formulas, new source relationships or database objects,
historical positions, missing-employee universe expansion, model SQL or result data
in model context. Private live evidence remains ignored locally.

Implemented [the fixed registered aggregate](SDK_PARTICIPANT_MEANS.md) with a
host-only participant column, numeric/fact-grain validation, permitted catalog
projection, typed aggregate filtering and deterministic guarded compilation in
both dialects. The output is explicitly approximate numeric arithmetic; missing
identities/undefined counts produce null. Existing sums/averages and relationship
guards retain their behavior. Rahtal's catalog version changes; stale reports
remain subject to the existing compatibility checks.

Host phrase evidence plus an averaging word retains the requested business
concept even when intent extraction drops it. A generic activity average cannot
replace it; explicitly requested additional averages and temporal breakdowns are
preserved. Latest removal wording overrides older clarification evidence. No
new permission or model-provided expression is introduced.

The corrected configured-model/SQL Server run returned the requested two measures
per current position with no unnecessary month column. Independent bounded reads
of fact rows and policy-visible profile counts/positions matched every total,
distinct participating count and mean. The baseline independently failed the
mean-completeness checks. All live source rows/results remain ignored locally.

Added 49 synthetic cases covering unequal participation, activity versus entity
means, unknown/zero/negative amounts, unknown identities, integer division,
schema/permission rejection, imported-column rejection, complete grouping before
ranking/filtering, duplicate profile guards, exact date boundaries, planner
repair, explicit comparison/monthly denominators and persistent retries/refinements.
Browser regressions verify labeled units, display rounding without JSON mutation,
unknown values and visible column widths. The verified live report JSON was also
rendered and visually inspected in the frontend.

Verification: 1,188 Python tests passed; one opt-in synthetic SQL Server test was
skipped. Browser regressions, source/wheel builds, isolated imports/compilation
from the freshly installed final wheel and `git diff --check` passed. No commit
was created.

Focused command: `.venv/Scripts/python.exe -m pytest tests/test_sdk_participant_means.py tests/test_rahtal_position_workload.py -q`.

Suggested commit message:
`feat: add verified workload means per participating employee`
