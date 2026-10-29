# Phase 03: held-out evaluation and request-to-report completeness

Completed 2026-10-24 (Asia/Tehran), branch `main`, starting revision
`b74c10974265dcac522b3e23623e0f4f9a8ae582`.

## 1. Executive summary

**Offline evaluation complete; live-model generalization unverified.**

The independently specified evaluation adds 42 trajectories and 55 turns over
three synthetic domains. It separately scores frozen assessment, development and
pipeline cohorts using complete public specifications, actual SQLite results,
every conversation turn, persistence, replay, no-read boundaries and stage behavior.
It cannot award completion for a plausible but incomplete report.

Four scoped defects were fixed: omitted explicit grouping, refusal of an excluded
`leave out` operation, replacement retaining the old measure, and loss of an
explicitly retained current filter. On the same v2 corpus/scorer, correct supported
turns improve 35/42 to 39/42; incorrect accepted specifications fall five to two.
All eight multi-turn trajectories pass. The assessment cohort has 30/30 correct
scripted trajectories and 29/29 supported report turns.

Two controlled faults still produce incorrect accepted reports. A third request
is safely blocked when a custom provider persists in omitting grouping. Combined
evaluation deliberately exits 1, without waivers. The unchanged fixed 61-case
suite passes strict evaluation; full pytest passes **1,635 tests, one skip**.
No live calls, dependencies, framework/topology/analytics, public API, authorization
or storage-format changes. No commit. Phase 04 has not started.

## 2. Verified starting state

Mandatory reports/product/evaluation/safety documents and actual SDK intent,
phrase/evidence, business, orchestration, compiler/semantic, engine/session and
scoring paths were reviewed. Phase 02 code and tests are present. Starting branch
was `main`, index empty, with the prior uncommitted README, roadmap, SDK agent docs,
four SDK modules, new phrase module, reports/evaluations/tests. Nothing was reset,
cleaned or committed. Revision/status/file hashes are recorded locally in ignored
`dist/phase03/starting-state.json`.

Starting reproduction: 1,570 passed/one skipped; fixed evaluation 40/40 supported
reports from 61 cases, 147 transport calls, 47 adapter calls, two planning revisions,
one structured repair and zero known failures. Exact Phase 02 copies are archived
as `phase02_cases.json`/`phase02.json`. Original `evaluations/cases.json` and
`baseline.json` remain byte-identical; all Phase 01/02 records remain available.

Scope: independently measure completeness and conversational reliability, repair
safely bounded discovered failures, and prepare authorized synthetic live trials.
New analytics, production infrastructure, model SQL, general parsing/storage
redesign and Phase 04 implementation are excluded.

## 3. Evaluation architecture and ground truth

`evaluations/trajectories.py` extends the existing CLI/runner/scorer, reusing real
stage decoders, public SDK, RecordingAdapter (both SQL dialect compilers plus
read-only SQLite), persistent sessions and independent `assess`. `--suite`
separates regression, holdout, development, pipeline and combined Phase 03.

`phase03_hosts.py` adds a workshop host with existing sum/count/average operations,
three dimensions/filters and mandatory organization/void policies. Retail/library
reuse trusted registrations/seed data, not embedded expected answers. Workshop
source records independently establish July USD 860 over six jobs, 255 minutes,
June USD 500 and an exclusive August endpoint, plus void/cross-organization traps.
July Service totals are Install 500, Repair 300, Tune 60; Web totals 580/four jobs;
Technician T1 totals 200/two jobs; average minutes are 255/6 = 42.5.

`reference.py` has no SageQL imports, SQL, model output or returned-result oracle.
It computes grouping, filtering, aggregates, boundaries, comparisons, ordering and
top-N using source records and Decimal. Every turn declares its request, host/actor,
initial state, requirements/exclusions, expected classification, complete spec,
exact rows/fields/types/order/presentation/bounds. A recursive payload test prevents
answer keys or result rows entering model context.

There are 13 public-spec field checks per supported turn, plus complete data,
provenance and state checks. No returned report means zero field credit. The field
fraction is diagnostic: completion requires every applicable check. A trajectory
passes only when all planned turns pass; first failure cannot be erased. Empty
rates/tokens/cost are undefined, not zero. See [the full evaluation guide](../evaluations/PHASE03.md)
for exact scoring definitions and commands.

## 4. Freeze, corrections and exposure

The first 40 cases were frozen in `cases.v1.json`/`freeze.v1.json` before agent
execution. `phase03_initial_v1.json` preserves first results, including harness
errors. Independent contract review corrected H22: a policy-filtered registered
LEFT JOIN dimension retains its visible borrowing fact with NULL Shelf. The
initial reference omitted that fact. Reference grouping ties also needed their
deterministic ascending order. D01's static queue mistakenly sent a plan to the
review decoder; stage-aware scripts now approve an admitted wrong plan or repair
when a deterministic gate requests another proposal. Original inputs/oracle/results
and reasons remain in `phase03/history/` and `corrections.v2.json`.

H12/H25 were used for targeted SDK fixes and promoted to development. Independently
authored H31/H32 replace them. V2 freezes **30 assessment, six development, six
pipeline trajectories** before executing that revision. The assessment includes
28 previously exposed cases plus two replacements: it is not permanently secret
or untouched. No final assessment case was used for a targeted production fix.
Versioned hashes reject changed frozen inputs. No business answer was changed
to conceal an SDK failure. Reviewer instrumentation was also corrected to count
approval of a legitimate candidate followed by injected DB failure as correct.

## 5. Held-out and separate cohort results

Ordinary scripted cases receive correct selections; development/pipeline cases
inject declared faults. These numbers measure enforcement/execution/scoring,
not unseen-language generalization.

| Metric | Assessment | Development | Pipeline | Combined |
| --- | ---: | ---: | ---: | ---: |
| Trajectories / turns | 30 / 40 | 6 / 9 | 6 / 6 | 42 / 55 |
| Correct trajectories | 30/30 | 4/6 | 5/6 | 39/42 |
| Correct supported complete turns | 29/29 | 7/9 | 3/4 | 39/42 |
| Correct / returned reports | 29/29 | 7/8 | 3/4 | 39/41 |
| Satisfied field requirements | 377/377 | 103/117 | 51/52 | 531/546 |
| Correct / returned clarifications | 4/4 | 0/0 undefined | 0/0 undefined | 4/4 |
| Correct / requested unsupported | 5/5 | 0/0 undefined | 0/0 undefined | 5/5 |
| Correct zero-read denials | 2/2 | 0/0 undefined | 0/0 undefined | 2/2 |
| Incorrect accepted specifications | 0 | 1 | 1 | 2 |
| Injected operational failures | 0 | 0 | 2 | 2 |
| Intent / planning / review calls | 36 / 32 / 32 | 8 / 10 / 8 | 6 / 8 / 7 | 50 / 50 / 47 |
| Adapter calls | 29 | 8 | 5 | 42 |
| Planning revisions | 0 | 2 | 3 | 5 |
| Local scenario total, ms | 757.277 | 210.672 | 120.874 | 1038.146 |

No unnecessary clarification or incorrect unsupported classification remains in
these final runs. There are zero structured repairs/reconsiderations. Usage is
absent for all 147 combined transport calls; tokens/USD cost are undefined.
Separate cohort timings need not sum and establish no speedup or provider SLA.

Coverage includes English/Persian/mixed language, managerial/informal requests,
multiple metrics/filters, ranking, dates, exact vocabulary, quotes/exclusions,
missing year/period/measure/comparison, unavailable formulas/relationships/time/
concepts, tenant/injection attempts, denial/revocation and conversation changes.
The small English-heavy corpus cannot estimate population language accuracy.

## 6. Multi-turn and agent pipeline findings

Eight trajectories (21 turns) test year clarification, successive grouping/date/
filter changes, unsupported reformulation, replacement, comparison changes,
revocation, earlier reports, reopen and replay. They improve **6/8 to 8/8** complete
trajectories. The six assessment conversations are 6/6; two development conversations
improve after fixes. Every turn's result/state is checked; cached submissions add
no execution, earlier reports remain intact, and revocation denies prior reports.

Allowlisted diagnostics compare decoded/effective intent, proposals and review
with independent requirements. Failure origin distinguishes extraction/context,
planning and review; outcomes distinguish semantic blocks, wrong accepted specs/
data, incomplete results, clarification/refusal, authorization and operations.

Pipeline experiments: P01 rejects/repairs one wrong sort; P02 approves one wrong
sort; P03 rejects a correct proposal then approves it; P04 catches wrong grouping
locally before review and repairs it. Review counts are one incorrect rejection,
one incorrect approval, one correct rejection, four correct approvals. There is
one useful and one unproductive reviewer-driven revision. These injected outcomes
are not a live reviewer error rate. No stage/model topology comparison occurred,
so changing topology/model assignments would be unsupported by this evidence.

## 7. Confirmed defects and fixes

| Finding | Verified root cause | Focused correction |
| --- | --- | --- |
| P3-01 grouping omission, D01/D02 | Correlated stages/custom provider could return total 860 instead of three Service groups; positive dimensions were not independently enforced. | Shared registered grouping evidence anchors intent and checks every final provider spec. Fact scoping/longest matching avoid source-label collisions. Agent repairs; persistent custom-provider error blocks before reads. |
| P3-02 excluded operation, promoted H12 | `leave out share of total` remained positive unavailable evidence. | Extend shared scoped exclusion cues; retain independently positive unsupported checks. The independent supported report now completes. |
| P3-03 replacement, promoted H25 | Both labels in `Replace Billed amount with Completed jobs` became positive; anchoring restored the old measure. | Bounded replacement roles exclude the old concept and select the new one, preserving later exclusions. Three-turn data/state and contrast tests pass. |
| P3-04 retained filter, D04 | Replacing a measure while explicitly keeping Channel could drop Web and count six jobs instead of four. | Retain the existing typed condition only when explicitly requested; anchor intent and final specs without interpreting a new value. English/Persian, conflict/clarification, restart and real-data tests pass. |

Beyond preserved Phase 02 work, production changes are confined to `phrases.py`
and `evidence.py`, with internal additive defaulted evidence fields. Existing shared
scope and the provider-neutral gate are smaller than duplicated phrase patches,
a general parser or framework/storage redesign. No dependency was justified.

Comparable v2 before/after uses identical final scorer/corpus/fixtures. The before
run loads the exact Phase 02 installed sources in an ignored isolated directory;
its hash matches the initial source hash
`b0353dc9689c4fceab56ccf10757d10ecde952efe04dac17508d6dc3edada7ca`.

| Comparable metric | Before | After |
| --- | ---: | ---: |
| Correct supported turns | 35/42 | 39/42 |
| Correct / returned reports | 35/40 | 39/41 |
| Correct trajectories | 35/42 | 39/42 |
| Field requirements | 515/546 | 531/546 |
| Incorrect accepted specs | 5 | 2 |
| Incorrect unsupported | 1 | 0 |
| Intent / planning / review calls | 49 / 48 / 45 | 50 / 50 / 47 |
| Adapter calls / revisions | 41 / 4 | 42 / 5 |
| Structured repairs / reconsiderations | 0 / 0 | 0 / 0 |
| Local scenario total ms | 1042.865 | 1038.146 |

Previously refused reports now complete and rejected proposals are repaired, adding
calls. No database operation is retried. Full stage timings/turns/hashes are retained
in `evaluations/baselines/phase03_*.json`; local timings are not production benchmarks.

## 8. Live-model evaluation

**Not authorized and not executed.** Existing configuration was not approval.
No endpoint availability check, billable call or Rahtal/production query occurred.

[The exact procedure](../evaluations/PHASE03.md#exact-opt-in-live-procedure-not-executed)
and disabled approval template require explicit evaluation approval, matching
reviewed endpoint/model, global request/token/time/USD limits and reviewed pricing
provenance. Keys remain environment-only; `.env` is never loaded. Only eligible
synthetic holdouts run; controls are excluded/listed. No fallback, endpoint switch
or transport retry. Checkpoints retain failures, existing live output paths are
rejected and unexecuted work is explicit.

Prompt-byte/output reservations enforce accounted caps before dispatch; usage,
when supplied, adjusts them. This cannot certify arbitrary provider tokenization
or billing. Local mocked unavailable-client/usage/pricing tests prove caps, failure
preservation and no fallback; they are not live measurements or real prices.

## 9. Regression verification

Final commands use the existing Python 3.12.0 environment; no separate lint/type
gate is configured. Measurement commands additionally select explicit baseline
`--output` paths; fixed records use `--compact` without changing scores.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=dist/phase03/final-tests.xml
.\.venv\Scripts\python.exe -m pytest tests/test_evaluations.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_sdk_semantic_evidence.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_phase03_evaluations.py -q
.\.venv\Scripts\python.exe -m evaluations --strict
.\.venv\Scripts\python.exe -m evaluations --strict --cohort phase01
.\.venv\Scripts\python.exe -m evaluations --strict --cohort phase02
.\.venv\Scripts\python.exe -m evaluations --suite holdout --strict
.\.venv\Scripts\python.exe -m evaluations --suite development
.\.venv\Scripts\python.exe -m evaluations --suite pipeline
.\.venv\Scripts\python.exe -m evaluations --suite phase03
.\.venv\Scripts\python.exe examples/sdk_demo.py
.\.venv\Scripts\python.exe examples/multi_domain.py
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src evaluations
$env:NODE_PATH='C:\Users\Sina\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
node tests/web_tabs.cjs
.\.venv\Scripts\python.exe -m build --no-isolation --outdir dist/phase03/packages
.\.venv\Scripts\python.exe -X utf8 dist/phase03/package_smoke.py
git diff --check
```

Outcomes:

- Full suite: **1,635 passed, one skipped**, no errors/xfails/unexplained failures,
  39.25 seconds. Skip: existing opt-in live synthetic SQL Server integration.
- Focused: evaluation 88, Phase 02 semantic 101, Phase 03 65 tests, all passing.
  New tests cover reference/scoring/freezes/exposure, all assessment trajectories,
  fixes, stage judgments, replay/state/denial, payload isolation and live caps.
- Fixed 61 and both historical cohorts: strict exit 0, unchanged populations,
  40/40 total reports, 147 transport/47 adapter calls. Assessment exit 0.
  Development/pipeline/combined exit 1, retaining D02/D03/P02. These are measured
  product limits, not hidden xfails or unexplained pytest failures.
- SDK/host examples, pip check, compileall and browser tabs/history/failures/receipts/
  download/mobile/modes pass. Full suite covers SQL/compiler/security/session paths.
- Wheel/sdist and isolated installed-wheel smoke pass: 42 package modules import;
  both copied host examples run with sockets blocked. The fresh venv reuses only
  installed sqlglot/dotenv; online dependency resolution is unverified. Optional
  OpenAI/ODBC extras are absent. Wheel excludes evaluation tooling; sdist includes
  final docs/frozen assets and excludes `.env`, private config/reports, venv/dist.
  Python 3.10 grammar parses; its runtime is untested here.
- Final source/baseline/freeze/archive preservation hashes and whitespace pass.

## 10. Security and compatibility

Host authentication, permissions, row policies, relationships, parameterized SQL,
execution opt-in, cardinality and completeness checks are unchanged. SQL Server
compilation runs offline; only synthetic SQLite executes. No production identity,
object, record or infrastructure modification. Models cannot submit executable SQL
or physical mappings. Current authorization/revocation and cached/saved-report
access checks remain effective.

Payload tests exclude answers/results and physical/policy-only values. Artifacts
retain allowlisted IDs, boolean checks, classifications, stage counts/timings/usage
and hashes; no prompts, SQL, rows, credentials or raw exceptions. No new service,
telemetry, runtime dependency or orchestration framework.

Public constructors/report/session formats, error families, Gregorian/Jalali
support, dialects and Python declaration remain compatible. Existing saved receipts
are not retroactively recalculated. Intentional changes enforce tested requirements
or clarify conflicts. The evaluation-only old unbudgeted regression live command
now rejects execution; live trials use reviewed/budgeted holdouts instead.

## 11. Remaining risks and Phase 04 recommendation

| Priority/status | Evidence/impact/likelihood | Root cause / proposal / tests / effort |
| --- | --- | --- |
| P1 confirmed open P3-05 | D03 correlates wrong stages: Web-only should return 580, but accepted all-channel 860. Natural frequency unmeasured. | New categorical values lack independent filter grounding. Scope typed grounding/registered value semantics; test collisions, quotes, negatives, permissions and three hosts. Medium/high. |
| P1 confirmed open P3-06 | P02 approves ascending despite highest-first request; exact rows/spec fail. Controlled frequency only. | Ordering can remain unspecified in intent. Scope typed metric/direction evidence, multi-metric ambiguity and refinements. Medium. |
| Safe residual D02 | Final gate blocks omitted grouping with zero reads; report request stays unfulfilled. | Host provider must return a conforming spec. Retain safety regression; no automatic DB retry. |
| Unverified generalization | Scripted selection delivery cannot measure live extraction/reasoning. | Authorized held-out synthetic trials, separate first attempts and stage origins. Evaluation effort. |
| Existing limitations | English-heavy small corpus; complex implicit constraints/discourse, SQL Server/Python 3.10 runtimes and multi-read snapshots unverified. | Broader assessment and runtime matrix; separately scoped state/snapshot work if evidenced. |

The two wrong accepted reports are explicitly open, reproducible with unchanged
expectations and failing CLI outcomes. They are not counted as completed fixes.
Generic categorical/order grounding needs a reviewed contract: values can belong
to several filters, quotations can be data and several metrics can be ranked.
Hard-coding Web or a highest-first sentence would conceal the gap. Phase 03 repairs
the smaller proven registered-group/replacement/exclusion/current-typed-filter cases.

Recommend Phase 04 prioritize **provider-neutral filter and ordering requirement
grounding**, before analytics/topology expansion. Acceptance: design/version the
internal contract first; make D03/P02 correct or transparently clarify/block before
reads, while never crediting incomplete output; test ambiguous values/metrics,
positive/negative/refinement contrasts across hosts, collisions and revoked access;
retain fixed cohorts and frozen replacement assessments. Run explicitly authorized
live trials separately to measure prevalence. No silent constraint loss, unauthorized
read or result-to-model feedback. Do not assume storage/public API changes are
necessary before design. **Phase 04 has not started.**

## 12. Git status

Still `main` at the initial revision; no commit/push/reset/rebase. Prior Phase 01/02
work remains. Tracked changes remain README, roadmap, SDK agent docs and four
previously modified SDK modules. Phase 03 extends evidence and the untracked phrase
module. New groups: this report, evaluation guide/reference/host/trajectory tools,
frozen/history/config/baseline assets and `tests/test_phase03_evaluations.py`.
`dist/phase03/` is ignored.

Proposed commit message:
`fix(sdk): ground report requirements and add frozen trajectory evaluation`
