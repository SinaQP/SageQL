  # Phase 13 — Real-model synthetic SQLite pilot (2026-10-27)
  
  ## 1. Verified starting baseline
  
  Started from `main`, HEAD `b74c10974265dcac522b3e23623e0f4f9a8ae582`, empty index,
  with earlier uncommitted Phase 01–12 and SQLite-first work. Before this continuation,
  357 nonignored files were copied/hashed under `dist/phase13-exploratory/starting/`:
  25 tracked modifications and 227 untracked files. The starting offline baseline was
  2,212 passes / 13 native SQL Server skips. Earlier Phase 13's accounting-blocked
  [`verification.v1.json`](../evaluations/phase13/verification.v1.json) remains unchanged.
  Initial SDK digest: `460eb7424baaf5d0e86235b9803eb96faf98a3de6e43bd6651cdb2b951aeef8e`.
  
  ## 2. Authorization and achieved outcome
  
  The user subsequently authorized exploratory accounting, accepted uncertain charges,
  removed the $0.25 requirement and authorized bounded live diagnosis and improvements.
  This supersedes the conditional accounting blocker. Strict accounting attestations
  were not fabricated, and production access remains outside this task.
  
  **Real-model baseline measured; two targeted pilot repairs demonstrated.** Final
  source completes P01/P02 **2/2**, with 26/26 requirements and zero wrong accepted
  specifications. First failures remain recorded. Improvement is scoped to an exposed
  pilot, not a blind assessment or production-readiness claim. Phase 14 has not begun.
  
  Per experiment: at most 12 requests, 600 seconds, 250,000 input / 98,304 output /
  348,304 combined tokens, 8,192 completion tokens per call and a $5 published-rate
  estimated-cost stop. HTTP/agent deadlines are 90 seconds; the SDK request deadline
  is 240 seconds, bounded by remaining run time. Before final verification the
  controller also capped accumulated dispatches at 28; actual total is 22. These
  safeguards cannot guarantee provider billing or recall remotely processed work.
  
  ## 3. Provider, model and credential boundary
  
  All calls used AvalAI `https://api.avalai.ir/v1`, exact `gpt-5-nano`, Chat Completions
  and the actual OpenAIReportAgent. No injected mock transport or alternate model.
  Routed backend revision and account charges remain unverified. Only the root `.env`
  model-key setting was read for credentials, held in the live child process and
  removed afterward. Neither configuration file was edited. Rahtal `.env`, SQL Server,
  private report archives and employee records were not read.
  
  The [AvalAI model page](https://docs.avalai.org/en/models/gpt-5-nano), observed on
  2026-10-27, lists $0.05 input / $0.40 output per million text tokens and $0.005 cached
  input. Estimates use the full input rate. The
  [token guide](https://docs.avalai.org/en/guides/token-counting) does not establish a
  complete framing/input bound. Published rates do not verify invoices or unpriced-fee
  absence. Exploratory packets explicitly record `guaranteed_bound=false` and
  `provider_billing_verified=false`, with observed price dates rather than fabricated
  effective dates. Actual billed USD remains null.
  
  ## 4. Corpus versions and exposure
  
  Reused unchanged Phase 08 v2: 14 trajectories / 23 turns / 16 report goals across
  retail, library and workshop. Only **P01/P02** ran live. Questions, answer keys,
  host builders, Python/Decimal references and scorer were not edited. All cases
  already had offline exposure; pilot cases now also have live development exposure.
  A01–A12 remain live-unexecuted.
  
  Pilot selection: `2c1cb5b81c2fd28042a919d014659590014de524457c6bb1497692a19da4cf58`;
  corpus: `f915e30613ccf2609386a608b0b433fd8919501db7b221529dc42452f4d45b48`;
  freeze: `c2c84188dbcdf0db5ec2dead8ecee435dcd99af0ce4c3fd736d4394fb80c4011`.
  Each packet binds actual SDK/evaluator hashes, endpoint/model, selection and output.
  Fresh local temporary output directories were copied into ignored storage only after
  completion. Durable reservations preceded dispatch; no original journal was resumed.
  
  ## 5. Actual execution and first attempts
  
  | Preserved run | Calls | Correct executed goals | Wrong accepted specs | Observation |
  |---|---:|---:|---:|---|
  | `pilot-first` | 3 | 0/1; P02 unexecuted | 1 | P01 invented monthly grouping; safety stop |
  | `pilot-corrected` | 6 | 1/2 | 1 | P01 corrected; P02 invented descending metric ordering |
  | `pilot-final` (intermediate SDK) | 7 | 2/2 | 0 | Unnecessary comparison clarification locally rejected and repaired |
  | `pilot-release` (final SDK) | 6 | 2/2 | 0 | Both first planning proposals correct; no revision |
  
  The first two experiments failed safety gates. Their scored turns survive generic
  `runner_failure` stop classification. Comparisons used distinct source-bound packets
  and directories under the user's engineering authorization. No failed model transport
  or DB operation was automatically retried. Accuracy is not pooled across versions.
  
  The initial runner overcounted untouched trajectories when a safety stop left a
  scored active turn. That original artifact still says two untouched trajectories;
  its actual turn evidence shows P01 executed and only P02 untouched. A focused
  regression verifies corrected counters without rewriting the original record.
  
  ## 6. Report correctness and independent arithmetic
  
  P01 requests September 2026 Net sales in a table. Independent expected output is
  one decimal `revenue` field, total **115**, with September 1 inclusive / October 1
  exclusive bounds. The original amount and period were correct, but an extra time
  bucket made its fields and specification incorrect.
  
  P02 requests July 2026 Completed jobs for each Service. Expected groups are
  **Install 2, Repair 3, Tune 1**, with July 1 / August 1 bounds and the canonical
  unspecified-order specification. The first P02 attempt had correct counts but
  invented `order_by=jobs_count, descending=true`, failing ordering/spec checks.
  The scorer was not relaxed to accept it.
  
  The final run matches full specifications, fields, types, rows, ordering, date
  bounds, presentation, nontruncation, policy-visible data and persistence checks.
  Each report used one synthetic SQLite read. Before/after database file hashes
  matched. Idempotent replay produced no additional model or database work.
  
  ## 7. Clarification and conversation evidence
  
  In the intermediate seven-call run, P01's first Planner response unnecessarily
  asked whether the user wanted a comparison. Existing Intent validation rejected
  that question before publication; one bounded revision produced the correct report.
  Final source needed no revision and showed no clarification.
  
  This pilot contains no genuine missing-detail or multi-turn refinement trajectory.
  Necessary English/Persian questions, answer/context retention, semantic replacement,
  reopening after clarification and broad conversation reliability remain
  **live-unmeasured**. Offline synthetic assertions retain that coverage. Pilot
  saved-report retrieval and idempotent request replay passed.
  
  ## 8. Intent, Planner and Reviewer
  
  Original P01 Intent confused a reporting month with monthly grouping; Planner
  repeated it and Reviewer approved. In P02, Intent marked ordering unspecified,
  but Planner introduced ranking and Reviewer approved. Reviewer approved **two
  incorrect candidates** across the four experiments; it is not a correctness boundary.
  Final proposals were both independently correct and both approved. No incorrect
  proposal reached Reviewer in that run, so its detection effectiveness has no
  positive denominator there.
  
  Historical stage diagnostics compare nullable Intent controls directly with
  materialized ReportSpec defaults: null limit versus 100, null direction versus
  false. They retain 0/2 all-field Intent matches in the successful final run. Those
  representation differences are not incorrect final limits/directions. Counters
  were not rewritten. Final independent specification/numerical/completeness scores
  remain unchanged. The earlier unnecessary planning question remains visible too.
  
  ## 9. Deterministic correctness and security gates
  
  Original wrong reports were structurally valid, authorized synthetic SELECTs;
  SQL validation alone did not prove business correctness. The evaluation hook
  checkpointed each wrong report and stopped subsequent work. New dated-table
  evidence anchors time grouping; the observed unspecified-Intent ordering path is
  frozen before planning/review. Exact captured-response offline comparisons against
  preserved and final SDKs reproduce old wrong publication and new zero-read rejection
  for **both** failures. Transcript divergence stops without inventing a new response.
  
  Final live results show zero wrong accepted specs, unauthorized reads, payload
  isolation failures or model-SQL acceptance. There are no denied-request scenarios
  here, so no broad authorization-prevention rate follows. Models receive permitted
  synthetic business context, without physical mappings, identities, policy scalars
  or result rows. Both adapters, policies, host execution opt-in and SQL restrictions
  remain supported. No production connection or operation occurred.
  
  ## 10. Opaque-reference observations
  
  Pilot questions issued **zero opaque value references**. No fabricated, modified
  or wrong-owner reference appeared, but compliance/recovery remains unmeasured,
  not 100% reliable. Vocabulary assessment cases remain live-unexecuted. Codecs,
  ownership checks and offline adversarial tests are unchanged.
  
  ## 11. Actual usage, latency and cost estimates
  
  All 22 dispatched calls returned valid usage. Reasoning tokens are a subset of
  completion tokens; cached input is a subset of input. Neither is added again.
  No missing usage was recorded as zero. Reasoning-inclusive account billing and
  provider invoices remain independently unverified.
  
  | Run | Input | Completion | Estimated USD | Controller seconds |
  |---|---:|---:|---:|---:|
  | First baseline | 12,260 | 6,118 | 0.00306020 | 69.563 |
  | Time-grouping correction | 24,017 | 12,444 | 0.00617845 | 88.891 |
  | Intermediate plain-table correction | 28,496 | 14,708 | 0.00730800 | 117.391 |
  | Final compatible source | 24,015 | 10,196 | 0.00527915 | 83.610 |
  | Total resources | 88,788 | 43,466 | **0.02182580** | 359.455 |
  
  Totals include 41,280 reported reasoning and 61,952 cached-input tokens, without
  cache discounts. Calls: Intent 7, Planner 8, Reviewer 7. Final report latency:
  P01 40.498 seconds; P02 39.624 seconds. Final stage totals: Intent 35.952 seconds,
  Planner 33.373 seconds, Reviewer 10.560 seconds; SQLite execution about 39.865 ms.
  Controller elapsed includes setup/checkpoints and differs from report/model latency.
  No controlled speed comparison or guaranteed spending cap is claimed.
  
  ## 12. Confirmed defects and targeted changes
  
  The existing runner gained explicit exploratory mode, while strict remains default
  with its original approval fields/attestations. Drafts remain disabled. Unknown or
  invalid usage, transport failure, output-cap violation, recording failure and
  exhausted limits stop subsequent dispatch. Visible assistant-output recording is
  bounded and opt-in; headers, credentials, requests and provider exception bodies
  are excluded. [Commands and contract](../evaluations/PHASE13.md).
  
  SDK changes are limited to scoped dated-table evidence and Intent instructions:
  a reporting period does not request time grouping; an unspecified Intent sort
  cannot turn into Planner ranking for the observed fresh plain-table path. Explicit
  semantic sorts, time breakdowns and current-report refinements are preserved.
  Quoted/negated phrases, predicate literals and registered labels retain their roles.
  
  A broader first ordering rule caused 14 regressions and failed the installed library
  example. Those failed runs remain preserved. Narrowing the fix to unspecified typed
  Intent controls restored existing explicit semantic sort selections. No example,
  frozen answer, scorer or existing test was changed to hide failures. New regressions
  exercise before-read rejection, bounded repair, independent totals and controls.
  
  Final 45-module SDK digest:
  `e64e611ad9434d11059745d806a02dbb4be00607c1daa82c3bbf06946de0dbe2`.
  Final evaluator digest:
  `10b2780d1808798b3647df4cd5739ed7e4c5f6c5f57f886a6181dd21896a3f9b`.
  Final live packet and clean installed-core smoke use that SDK. No new dependency,
  agent stage, evaluator framework or transport/DB retry was introduced.
  
  ## 13. Offline regression, packages and preservation
  
  Final full pytest: **2,250 passed / 13 native skips** in each of Windows Python
  3.10.22, Windows Python 3.12.0 and Ubuntu WSL2 Python 3.12.3. All final semantic
  commands and fourteen SQLite consistency schedules pass on each runtime.
  
  The final matrix and command/log hashes are recorded in
  [`verification.v2.json`](../evaluations/phase13/verification.v2.json): full offline
  pytest, strict/held-out/Phase 03–09 gates, fourteen SQLite consistency schedules,
  Windows Python 3.10/3.12 and appropriate Linux checks. Historical Phase 03 D02/D03
  remain expected exit-1 failures. Native SQL Server cases stay separately skipped.
  
  The clean core-only Python 3.10 wheel installation outside the checkout imports all
  45 modules and runs both documented synthetic examples without OpenAI, ODBC or
  pytest installed. Archive/source consistency and whitespace checks are separately
  recorded. Earlier frozen cases/answers, references, test-policy guards, native-test
  bodies and versioned evidence are byte-preserved. Raw visible responses remain in
  ignored local storage; public records contain hashes and safe technical outcomes.
  
  ## 14. Remaining risks and unverified behaviors
  
  Two exposed single-turn cases cannot establish broad language quality, conversation
  intelligence, operational reliability or production readiness. No independent live
  assessment, variability estimate or statistical significance is claimed.
  
  The sort guard covers unspecified Intent controls. An incorrectly explicit semantic
  sort may still need additional evidence/review; this is not a universal absence-of-
  ordering parser. Reviewer approved two wrong reports, and one Planner unnecessarily
  asked about comparisons. A stronger model has not been compared or proven superior.
  Provider billing, framing bounds and backend routing remain uncertain.
  
  SQLite cannot verify native SQL Server precision/types, ODBC Unicode/binding,
  collation, TLS/permissions, RCSI/SNAPSHOT schedules, native cancellation, pooling or
  production workloads. Native tests remain disabled and have no invented results.
  
  ## 15. Next priority and Phase 14 recommendation
  
  The authorized pilot and targeted investigation are complete. A01–A12 assessment
  was not enabled. Next evidence should come from separately scoped untouched
  clarification, vocabulary, negation, multilingual and authorization trajectories,
  with first-attempt and Reviewer-detection measures. If Reviewer misses persist,
  compare a stronger model on a frozen independent selection before adopting it.
  Quality takes priority over token minimization; deterministic validation remains
  mandatory. Phase 14 was not started.
  
  ## 16. Git status and proposed commit
  
  Original branch/revision and empty index are preserved. Earlier user changes remain;
  only scoped evaluator, SDK evidence/instructions, regression tests and documentation
  changed. No commit, push, publication, deployment or private data export occurred.
  
  Proposed commit: `fix: verify live SQLite pilot and enforce dated table intent`.
