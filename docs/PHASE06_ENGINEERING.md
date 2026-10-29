# Phase 06: live-agent evaluation, semantic reliability and protocol verification

2026-10-26, Asia/Tehran. Branch `main`, revision
`b74c10974265dcac522b3e23623e0f4f9a8ae582`. No commit/push authorized.

## 1. Executive summary

**Phase 06 offline readiness complete; live-model reliability remains unverified.**
The existing public-SDK evaluation now has fresh frozen synthetic questions,
separate mocked protocol probes, durable first-attempt accounting/resume, exact
live-approval binding, separate request/input/output/total/time/USD budgets and
allowlisted stage/protocol diagnostics. No endpoint was contacted and no production
database or private configuration was accessed. Phase 07 has not started.

A reproduced protocol defect was corrected: unknown/altered reference strings
could be accepted as ordinary text predicates. A correlated fabricated-reference
probe published a meaningless filtered report before the fix. Standard transports
now reject reserved reference-shaped literals unless actually issued for their
current owner, and reject references in reviewer feedback. Normal free-form
filtering and canonical scalar validation remain supported.

Final frozen new cohort: **44/45 trajectories, 35/36 required reports**, zero
incorrect accepted specifications. L26 safely stalls on an owner-answer paraphrase;
it remains an unfulfilled report with unchanged expectations. Original D02/D03
also remain visibly incomplete. Readiness is not a claim of perfect semantics.

## 2. Verified baseline and Git preservation

Required phase/product/evaluation documents and actual transport, orchestration,
evidence, vocabulary, semantic/engine/session, policy/compiler and scorer code were
reviewed. Prior phases were uncommitted: 17 tracked modifications and 97 untracked
paths, empty index, unchanged HEAD. Before edits, hashes of **227 repository files**
and **34 generated evaluation JSON files**, plus complete source/evaluation/example
snapshots, were recorded under ignored `dist/phase06/starting/`.

Baseline reproduced: **1,837 passed, one opt-in SQL Server skip**; original strict
61 cases complete 40/40 reports; holdout 30/30 trajectories; Phase 04 26/26;
Phase 05 37/37 trajectories and 36/36 reports. Phase 03 stays 40/42, zero wrong
accepted specifications, expected exit 1 for D02 and original D03. Historical
corpus, reference, freeze, baseline and report bytes are preserved.

Original D03 has no value owner in its original registration and clarifies with
zero reads; its expected one-turn report remains unfulfilled. The separate
workshop-values-v1 association still produces 580. D02's nonconforming custom
provider remains blocked. None is relabeled as a completed report.

## 3. Evaluation architecture

The [preimplementation contract](PHASE06_EVALUATION_DESIGN.md) defines ownership,
privacy, approval, accounting, interruption and change rules. New tools extend
`evaluations/trajectories.py`, the existing independent Python/Decimal reference,
unchanged result scorer, real OpenAI-compatible standard agent transport, public
SageQL, persistent SQLiteSessionStore and policy-bound read-only RecordingAdapter.
Both SQL dialects compile offline; only synthetic SQLite executes.

The separate `python -m evaluations.phase06` command defaults to offline and
supports case/cohort selection, protocol mode, disabled approval preparation and
explicit live/resume paths. No alternate benchmark reporting implementation,
new runtime dependency, framework, analytical operation or SDK API is introduced.
Injected live-budget test transports are explicitly labeled mocks, never live
model measurements. Existing evaluation commands remain compatible.

An OS run lock and flushed atomic JSON journal preserve reservations before
dispatch and safe outcomes after every turn. Resume requires identical hashes,
configuration and approval, skips complete trajectories, preserves partial turns,
and never repeats an uncertain trajectory. Fully scored turns can be finalized
without reexecution. Wall time and all reservations survive restart. First
attempts cannot be overwritten by a new invocation at the same directory.

## 4. Real-model evaluation status

**Not authorized and not attempted.** The assignment explicitly requires separate
approval for the exact external evaluation. Existing credentials/endpoints are
not authorization. No secret values were read or printed, `.env` was not loaded,
and no live readiness ping, model request, endpoint switch or scripted fallback
was performed. This is an external dependency for real-model conclusions.

The [executable procedure](../evaluations/PHASE06.md) prepares a disabled draft
binding exact ordered case IDs, reviewed corpus/freeze/source/evaluator hashes,
adapter, HTTPS endpoint/model and absolute output directory. Authorization also
requires positive request/input/output/total token/time/USD ceilings, output cap,
dated reviewed price provenance/units and verified provider accounting assumptions.
Unreviewed pricing or insufficient accounting prevents live dispatch. The tool
does not independently certify prices, tokenizers, billing or human approval.

Only after exact preflight does the CLI access an evaluation key and construct
the existing client, with zero retries and sequential requests. Only natural
assessment scenarios are eligible; injected response faults cannot run live.

## 5. Agent stage findings

Mock scripts establish enforcement and measurement, not natural-language accuracy.
Diagnostics preserve decoded and effective intent, each proposal, review decisions,
first disagreement, later detection, safe error codes and final accepted outcome.
Canonical values stay in memory while comparisons emit only boolean checks.

Controlled omitted intent and wrong-filter plans recover within existing limits.
Persistent omission blocks. One deliberately rejecting reviewer rejects a correct
proposal, causing an unproductive revision; no claim of reviewer superiority is
supported. Final new measurements show 38 correct approvals, one false rejection,
zero wrong approvals, and no wrong plan reaching review. The wrong-plan rejection
rate therefore has a zero denominator and is unavailable, not 100% success.

Stage period diagnostics compare equivalent month/range boundaries independently
and treat genuinely missing periods/years as missing. Earlier diagnostic versions
incorrectly flagged frozen range representations and the implicit owner-clarification category; its measurement is retained in
`phase06_stage_diagnostics_before_correction.json`. This changes diagnostics, not
report expectations or score denominators. Optional/default field agreement is
reported as stage target agreement, not live reasoning accuracy.

No prompt, model assignment or agent topology was optimized. The production
changes address locally reproduced reference validation, with focused failing
tests before implementation; live semantic optimization has no baseline yet.

## 6. Vocabulary and opaque references

Four fabricated/altered-token unit probes and reviewer-feedback validation first
failed (53 passing/five failing focused tests). The previous decoder restored
known references but let unknown reference-shaped text continue as a scalar.
With correlated intent/plan approval and no independently required predicate,
P14 published a report using an invented filter value. The independent scorer
correctly classified it as an unexpected incorrect accepted specification.

The decoder now rejects the reserved `__sageql_value` namespace, including tested
case, leading-underscore and separator alterations, unless a token was issued in current structured input
for that dataset/filter. This applies even if no vocabulary is visible. References
in question/message/unsupported text and reviewer feedback reject safely. Review
uses the same restoration check. Unknown concept IDs/SQL fields still fail their
existing schema/concept checks. Public error-code families remain unchanged.

The 14 protocol trajectories cover valid issuance, fabrication, modification,
wrong owner/context, omission, display text, metric-ID confusion, malformed and
duplicate JSON, extra SQL, provider failure and canonical scalar return. Final:
**14/14 trajectories**, two correct reports, eleven correct blocks and one safe
injected operational failure. Blocks/failures are not report completions.

Canonical scalar return remains valid if ordinary semantic requirements are met;
the feature does not enforce a token-only response format. Identical token spelling
reissued in current context has current meaning. Arbitrary obfuscation is not a
universal token detector; final provider-independent semantics remain necessary.
The reserved transport namespace is an explicit narrow compatibility restriction,
not a mandatory enumeration of free-form business values.

## 7. Multi-turn reliability

Five new multi-turn trajectories cover 18 turns: long retail/library refinements,
metric/value/group/order/period changes, filter retention/removal, explicit new
reports, clarification answers, revocation, persisted reopen and cached replay.
Four trajectories pass; L26's second turn remains blocked with clarification_stalled.
Its original metric, grouping, period and expected report remain in the frozen
fixture. Later success cannot erase an earlier incorrect turn.

Real SQLite session stores are reopened, previous reports are checked, denied old
reports remain denied, and identical request IDs add no model/database calls.
Existing vocabulary-revision tests still reject incompatible saved reports and
receipts without reads, including a same-version registration change. No session
schema change, stale-report recalculation or automatic database retry is added.

## 8. Independent correctness results

Fresh v4: 45 trajectories/58 turns across three independent hosts: 26 assessment,
five development and 14 protocol. Report expectations use authored synthetic source
facts and the preserved independent reference arithmetic, never generated SQL,
provider/reviewer judgments or returned rows. Exact specs, types, rows, ordering,
date boundaries, presentation, exclusions and persistent/replay invariants are
checked. Every submitted turn contributes its own outcome.

V1/V2 input/freezes and first partial results remain. V2 adds the error code required
by the existing blocked-outcome scorer; no request, classification or report answer
changes. V3 additionally freezes missing-business-detail keyword alternatives for
every clarification. The unchanged report scorer is wrapped with this stricter
Phase 06-only check; a question about the wrong detail receives no clarification
credit. Keywords are bounded lexical evidence, not a proof of arbitrary free-text
meaning. V4 independently retires L11: its requested custom title has no SDK
ReportSpec operation, and the old oracle did not grade that requirement. L11 and
all prior measurements remain preserved; fresh L27 tests a quoted title example
without requesting unsupported title customization. No custom-title capability
is claimed. The final before/after both use this same v4 selection. Initial mocks accidentally copied request-only reference instructions
into strict responses; that harness defect was corrected. An unrelated-context
fault initially reused an actually issued token; the corrected probe supplies the
unissued source-owner token. Both initial measured records are retained. No model
has seen the corpus; all assessment questions now have offline exposure. L26 was
not used to target a semantic production fix. Protocol probes are development
evidence. No untouched blind or live benchmark claim is made.

Comparable final before/after use the same corpus, final driver/scorer and declared
host configuration. The before SDK is the exact captured Phase 05 source, hash
`46b195e9f2b4fd46b0f362b7afe5af90f10a23edc31450dceebea8032b415af5`.
Artifacts bind the final evaluator/corpus/freeze hashes identically.

| Metric | Before | After |
| --- | ---: | ---: |
| Correct trajectories | 41/45 | 44/45 |
| Complete required reports | 35/36 | 35/36 |
| Correct / returned reports | 35/36 | 35/35 |
| Field requirements | 455/468 | 455/468 |
| Incorrect accepted specifications | 1 | 0 |
| Correct clarifications | 6/6 | 6/6 |
| Correct unsupported / zero-read denials | 1 / 2 | 1 / 2 |
| Correct blocks | 9 | 12 |
| Injected operational failures | 1 | 1 |
| Intent / planning / review calls | 51 / 58 / 40 | 51 / 55 / 39 |
| Planning revisions / adapter calls | 7 / 36 | 5 / 35 |

Assessment: 25/26 trajectories, 29/30 reports. Development: 5/5 trajectories,
4/4 reports and one intentional block. Protocol: 14/14 trajectories, 2/2 reports.
The final cohort still exits 1 for L26. Original 61 strict cases and Phase 04/05
remain passing. Phase 03 still exits 1 for D02/D03. No known-failure waiver,
expected-outcome weakening or unsupported/block credit makes these numbers pass.

## 9. Performance and cost

Final scripted all-corpus uses **145 stage calls / 35 complete reports**; before
uses 149 / 35. The fixed no-retry budget terminates invalid references earlier.
Three of four development turns with revisions recover; the persistent fault does
not. One additional persistent protocol omission consumes a revision without a
report. No structured repair, intent reconsideration or database retry occurred.

Final all-corpus local scenario time is **1,528.797 ms**, versus **1,871.151 ms**
before. Final stage totals are intent **6.785**, planning **5.838**, review **1.972**
ms. Adapter time is **250.880 ms**; recovery model calls total **0.676 ms**.
Adapter timing includes offline compilation checks and SQLite execution; it is
not isolated server-query time. Recovery timing sums calls flagged after recovery
begins, excluding local validation/setup. Identified cohort records retain their
own independently measured times. They are single local scripted runs,
not remote latency or throughput/speedup evidence. Setup and later cache probes
are excluded from scenario times. Clarification turnaround is unmeasured.

All scripted usage metadata is absent: **0/145 coverage**, tokens, cached/reasoning
detail, estimated cost and provider-billed cost are unavailable. Fictional usage
and prices are confined to unit tests. Real-model tokens, prices, cost per completed
report, economic feasibility and provider invoices remain unverified.

Live accounting reserves serialized request/schema bytes plus reviewed overhead
and capped output at reviewed worst applicable rates before dispatch. Complete
valid usage adjusts reservations; cached/reasoning details remain subsets. Missing,
invalid or failed/uncertain usage retains reservations; invalid/over-bound accounting
stops further calls. Request/time/token/USD ceilings and interrupted reservations
are tested. This is conservative local accounting with provider attestations,
not a mathematically certified token or billing cap.

## 10. Changes and regression verification

| Files | Purpose |
| --- | --- |
| `sdk/vocabulary.py`, `sdk/agents.py` | Reserved-reference rejection and review-feedback validation; no business phrase/answer patch. |
| `evaluations/phase06.py` | Separate offline/protocol/live CLI, frozen selection/configuration, stricter clarification-detail checks, first outcomes and approved resume. |
| `evaluations/phase06_runtime.py` | Durable journal/OS lock, exact approval, conservative budgets and adapter usage decoding. |
| `evaluations/phase06_transport.py` | Mock protocol probes and safe observation of actual SDK transport calls. |
| `evaluations/trajectories.py`, `runner.py` | Additive injected transport/turn checkpoints, safe rejected-response diagnostics, semantic period checks and adapter timing. |
| `evaluations/phase06/`, baselines | Versioned fresh inputs, freezes, disabled approval example and preserved/comparable measurements. |
| New tests/docs, README/roadmap/agent/vocabulary guides | Reproducible commands, honest outcomes, contract limits and targeted regression coverage. |

Final Python 3.12 checks: **1,956 passed, one skipped**, no xfails or unexplained
pytest failures, 52.79 seconds console time. The 119 new
Phase 06 tests and all 96 vocabulary tests pass. The optional skip remains the
explicitly opted-in synthetic SQL Server integration.

Verification used the following entrypoints/options. Measurement invocations add
explicit output paths; the final baseline helper invokes the same CLI `main(argv)`
functions in one process, retaining every expected nonzero product outcome:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=dist/phase06/final-tests.xml
.\.venv\Scripts\python.exe -m pytest tests/test_phase06_evaluations.py -q --junitxml=dist/phase06/focused-final.xml
.\.venv\Scripts\python.exe -m pytest tests/test_sdk_value_vocabulary.py -q
.\.venv\Scripts\python.exe -m evaluations --strict
.\.venv\Scripts\python.exe -m evaluations --strict --cohort phase01
.\.venv\Scripts\python.exe -m evaluations --strict --cohort phase02
.\.venv\Scripts\python.exe -m evaluations --suite holdout --strict
.\.venv\Scripts\python.exe -m evaluations --suite development --strict
.\.venv\Scripts\python.exe -m evaluations --suite pipeline --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase03 --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase04 --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase04_development --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase04_assessment --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase05 --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase05_development --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase05_assessment --strict
.\.venv\Scripts\python.exe -m evaluations.phase06 --cohort all --output dist/phase06/after-v2
.\.venv\Scripts\python.exe -m evaluations.phase06 --mode protocol --cohort protocol --output dist/phase06/v4-delivery-protocol
.\.venv\Scripts\python.exe -I dist/phase06/before-runtime/measure.py
.\.venv\Scripts\python.exe dist/phase06/final_evidence.py
.\.venv\Scripts\python.exe examples/sdk_demo.py
.\.venv\Scripts\python.exe examples/multi_domain.py
.\.venv\Scripts\python.exe examples/value_vocabulary.py
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src evaluations
$env:NODE_PATH='C:\Users\Sina\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
node tests/web_tabs.cjs
.\.venv\Scripts\python.exe -m build --no-isolation --outdir dist/phase06/packages
.\.venv\Scripts\python.exe -X utf8 dist/phase06/package_smoke.py
git diff --check
```

The final helper selects new `dist/phase06/v4-delivery-<cohort>` directories and
`evaluations/baselines/phase06_*.json` outputs. Final Phase 06 all/assessment exit 1
for L26; development/protocol exit 0. Original regression/holdout/Phase 04/05 and
both original regression cohorts exit 0; old Phase 03 development/combined exit 1
for D02/D03. All expected outcomes remain visible. Before reproduction requires
the captured uncommitted Phase 05 source; it is not reconstructed from old HEAD.

Three standalone legacy batches stopped with the generic older CLI exit 2 (twice
Phase 05 development, once combined Phase 03). Available partial checkpoints and
safe diagnostics are retained. Twenty direct development repetitions and thirty
CLI diagnostic repetitions did not reproduce it; the cause remains unknown.
The final complete entrypoint sequence passes every expected exit without changing
questions, answers or SDK behavior to conceal those errors. No failed database
operation is automatically retried. The Phase 06 journal separately retains safe
runner reason codes and completed turns if an unexpected infrastructure error
interrupts evaluation; resume never repeats uncertain work.

The disabled approval-preparation CLI exits 0. Attempting the local live preflight
with that unauthorized draft exits 2 before creating a journal/client or sending
a request. No external trial is attempted.

Examples, dependency check, compileall and browser tabs/history/failure/cached
retry/download/mobile/modes checks pass. Python 3.10 AST parsing passes 62 files;
its runtime is unavailable. No new dependency or install extra was required.

Wheel/sdist build passes without remote build isolation. A fresh venv installs
the wheel with `--no-index --no-deps`, reusing only already installed base
sqlglot/dotenv dependencies. With sockets blocked, all **44 installed modules**
import and copied retail/library ordinary and vocabulary examples pass. Optional
OpenAI/ODBC extras are absent; online dependency resolution is not verified.
Archive inventory: 49 wheel / 266 sdist members, zero private/generated artifacts.
Final archive/source/installed bytes, source/evaluator/corpus/freeze bindings and
preservation/whitespace checks pass. Generated helpers/environments remain ignored.

## 11. Security and compatibility

Public SDK constructors, registrations, ReportSpec/session/report JSON, error-code
families, provider protocols, SQL adapters/compilers and Python >=3.10 declaration
remain. The intentional change rejects invalid reserved transport strings. Earlier
valid free-form, canonical, multilingual, Gregorian/Jalali and vocabulary behavior
continues through existing regressions.

The model cannot write executable SQL, select physical mappings, add relations,
authorize concepts or waive policies. Current actor/source access, execution
opt-in, deterministic parameterization, result completeness, cancellation, atomic
publication and idempotency remain enforced. No database object/production data or
permission changes. No result/private identity feedback to models.

Allowlisted records contain IDs, hashes, counts, boolean checks, reason codes,
timing and available usage. A boolean `rows` check is not row data. No prompts,
SQL, canonical/alias inventories, credentials, physical mappings, policies, raw
provider exceptions or remote telemetry are added. Output/journals require host
filesystem protection; they are trusted local state, not tamper-resistant billing.
Custom providers remain trusted integrations needing their own serialization audit.

## 12. Remaining risks

| Priority / status | Evidence and limit |
| --- | --- |
| High impact, unverified | Live-model extraction, private-reference compliance, actual reviewer utility, language generalization, latency and cost have no authorized measurements. |
| P2 confirmed completeness gap | L26's owner paraphrase stalls safely; one supported report remains unfulfilled, zero reads. This is not an authorization or wrong-report failure. |
| Resolved protocol defect; live frequency unknown | Fabricated/altered reserved tokens could become ordinary predicates; regression probes now reject them. Finite tests do not prove every obfuscation or utterance. |
| Environmental/operational | Generic transient older-evaluator failures and restart behavior are documented in final verification; fresh frozen runs never hide failures or auto-retry database operations. |
| Existing unverified scope | Python 3.10 runtime, production SQL Server numeric/collation/cancellation behavior and multi-read snapshot consistency remain unverified. |
| Accounting assumptions | Arbitrary provider tokenizers, hidden fees and ignored deadlines cannot be certified locally. Unsupported accounting blocks live preflight. |

## 13. Phase 07 recommendation (not started)

Prioritize **scoped clarification-continuation completeness**, informed by L26,
while keeping separately authorized synthetic live assessment ready. The newly
confirmed issue is a safe supported-request failure; reference acceptance was the
higher-severity defect and is now fixed. There is no evidence for framework,
model/topology migration or broad performance work.

Promote L26 before targeting a fix and freeze a fresh replacement assessment.
Test equivalent owner answers across unrelated hosts/languages, genuine ambiguity,
contradictory answers, reopen, date/group/negative/filter retention and final gates
for custom providers. Acceptance: complete the independently expected report,
preserve existing cohorts and persistent/replay behavior, zero incorrect accepted
reports/unauthorized reads, and no host-meaning guesses. Introduce a typed pending
state/schema only if reproduced evidence justifies it. If live approval is later
available, record all first attempts and failures under the new exact budgets;
choose model or prompt changes from those measurements. No Phase 07 work began.

## 14. Git status

Still `main` at the original revision; index empty. No commit, push, reset, clean,
rebase or unrelated overwrite. All earlier phases remain uncommitted and preserved.
Phase 06 changes only two SDK modules, the existing evaluation runner/trajectory
instrumentation and the documented evaluation/docs/tests/assets. Generated working
copies, synthetic SQLite data, journals and build environments stay under ignored
`dist/phase06/`. Final status: **17 tracked modifications / 135 untracked files**,
including all prior phases. **218 earlier repository files** outside the nine
explicitly changed paths and all **34 earlier generated evaluation JSON files**
match their starting hashes. All four new freezes validate; HEAD/index are unchanged.

Proposed commit message:
`fix(sdk): validate opaque references and add durable live-evaluation readiness`
