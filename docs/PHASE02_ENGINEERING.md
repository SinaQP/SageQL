# Phase 02: semantic correctness and registered vocabulary

Completed 2026-10-24, Asia/Tehran. Starting revision:
`b74c10974265dcac522b3e23623e0f4f9a8ae582`, branch `main`.

## Executive summary

All three confirmed Phase 01 defects are resolved. Negative daily requirements
cannot authorize daily output; excluded or literal unavailable-operation phrases
do not cause a refusal; exact registered participant-mean labels no longer need
an unrelated generic word. The deterministic final engine gate applies the same
evidence to every provider before lookup/report execution.

The unchanged original 27-case cohort now produces 20/20 correct supported
reports, up from 17/20. The expanded 61-case scripted corpus produces 40/40
correct supported reports, with no known-failure waiver or unexpected regression.
The full suite passes: **1,570 passed, one existing opt-in integration skip**.
These are deterministic synthetic measurements, not live-model accuracy.

The phase adds no analytics, public specification fields, database mappings,
permissions, runtime dependencies or orchestration framework. Phase 03 is
proposed below and has not started. No commit was created.

## Starting state and reproduction

Before edits, the working tree already contained modified `README.md` and
`docs/ROADMAP.md`, plus untracked `docs/PHASE01_ENGINEERING.md`, `evaluations/`
and `tests/test_evaluations.py`. Production source was clean. Those changes were
preserved; their initial file hashes/revision are recorded in the ignored
`dist/phase02/starting-state.json`.

The required product, agent, SQL Server, application-independence, Phase 01,
roadmap and evaluation documents and the actual intent/business/evidence/engine,
provider, semantic, period, comparison and session paths were reviewed before
implementation. Initial execution reproduced 17/20 supported reports and all
three known defects; evaluation tests were 49 passed and three strict xfails.
The original corpus and baseline were copied byte-for-byte to
`evaluations/baselines/phase01_cases.json` and `phase01.json`. The Phase 01 report
now links to its archived baseline, preserving its historical measurements.

For comparable recovery counters, the original evaluator/fixtures were also run
against the original `b74c109` source in ignored `dist/phase02/before-runtime/`,
with a delegating observer counting existing events. That reconstruction has
Windows line endings; its byte hash differs from the initial mixed-line-ending
checkout. Every reconstructed Python source equals the Git revision after line
ending normalization. Its measured compact projection is
`evaluations/baselines/phase02_before.json`; no production behavior or scoring
rule was changed in that before run.

## Verified root causes

| Defect | Before: actual path to failure | Corrective design |
| --- | --- | --- |
| P01-02 / `known_negated_daily` | Grain extraction recognized the occurrence of `daily` without polarity. Intent anchoring promoted it to `day`; a matching plan and approving reviewer satisfied the same positive evidence. The final gate reused that evidence and accepted actual daily SQL/results. | Record positive grain selections separately from forbidden grains, preserve both across relevant clarification answers, and reject forbidden grains at the final provider-independent gate. |
| P01-01 / `known_negated_share` | Operation recognition and removal used different small textual rules. `do not show` could leave a positive share requirement, causing refusal before a model call. Quoted data and mixed clauses had similarly inconsistent scope. | One occurrence classifier supplies clause scope, exclusion polarity and quote role to operation, grain and vocabulary checks. Match unavailable operations per clause; retain every independently positive unavailable requirement. |
| P01-03 / `known_exact_mean_label` | `_participant_mean_requested` required a generic mean keyword as well as registered selection vocabulary. Intent already selected `Loan days per reader`, but the special-measure guard rejected that exact host concept. | Authorized, unambiguous exact labels and specific registered aliases establish the declared operation. Shared matching distinguishes participant means from row averages and does not infer a formula from wording. |

The third fixture's independent answer is `(14 + 2 + 6 + 10) / 2 = 16`.
The per-row average over those four events is `8`; both remain separately
selectable. The original grain fixture requires the complete department totals,
Books `70` and Garden `45`, rather than its three daily department groups.
These expected values come from fixture data and user requirements, not from
the faulty output or a reviewer's approval.

## Architectural decision

Separate phrase-specific fixes would preserve disagreement among grain,
operation and business guards. A general language parser or agent-framework
migration would introduce much broader contracts without evidence that they
solve this bounded correctness problem. The selected change is a small internal
occurrence classifier plus explicit evidence fields, shared by the existing
pipeline. It uses a closed English/Persian grammar and the host's actual visible
registrations. There is no new dependency or remotely evaluated decision.

The classifier normalizes case, Persian/Arabic letter and digit variants, ZWNJ
and apostrophes, then classifies matched occurrences as positive, negative,
literal or unresolved. Punctuation, contrast and a bounded set of new action
clauses delimit scope. Prefix and Persian postfix exclusions are supported.
Quoted titles/names/examples are data; quoted direct selections are requirements;
an unresolved quote asks a local question. A negative word elsewhere in the
message never grants permission to ignore an independently positive operation.

Registered concept matching uses word boundaries and longest containing phrases.
Tied phrases identifying different visible concepts remain ambiguous. Generic
`mean`/`average` vocabulary is not sufficient deterministic evidence to choose
between distinct averages. An exact permitted label or specific alias selects
only its host-declared aggregation, even if its words include `Daily` or
`Share of total`; those words cannot register another capability.

## Implementation and semantic invariants

| File | Responsibility and resulting behavior |
| --- | --- |
| `src/sageql/sdk/phrases.py` (new) | Shared normalization, bounded occurrence scope/polarity and quote roles, existing grain vocabulary, registered concept matching and ambiguity detection. No SQL, calendar conversion or authorization logic. |
| `src/sageql/sdk/evidence.py` | Separate positive/negative selections; clause-local operation checks; fixed local clarification questions; consistent requirement-ledger validation; exclusions in intent anchoring and final feedback. Reconstruct known pending semantic evidence from persisted messages without a session-schema change. |
| `src/sageql/sdk/business.py` | Use the shared vocabulary/polarity for restricted metric selection. Accept exact labels/aliases, retain explicitly selected independent row averages, respect exclusions and use shared grain evidence. |
| `src/sageql/sdk/agents.py` | Use current-report context, ask safe evidence questions before planning, and validate model ledger entries against user evidence. Active unavailable requirements remain terminal; excluded/literal records are removed from effective planner/reviewer context. |
| `src/sageql/sdk/engine.py` | Supply current-report context to the existing final evidence gate for every provider, after access/spec preparation and before lookup/report queries. |

The following rules are independently tested:

- `monthly, not daily` selects month and forbids day. Positive and excluded
  occurrences of the same selection clarify. An unqualified `not daily` needs a
  replacement unless actual context and an explicit whole-period/group-removal
  instruction or another unambiguous grouping establish the existing `none`
  semantics. The engine never chooses a new grain from the exclusion alone.
- A raw registered dimension over the dataset's report-date column cannot
  evade a daily exclusion by setting `time_grain="none"`. An explicit conflict
  with that dimension clarifies; an incorrect custom-provider result is blocked.
- Metric, dimension and ordinary-filter exclusions constrain the final spec.
  `Remove Department filter` removes the predicate while preserving grouping;
  removing the grouping preserves an independently requested filter. Generic
  average removal uses one current registered average when unique and otherwise
  clarifies rather than silently retaining or choosing a mean.
- Positive share/ratio/formula/hourly requests remain unavailable within the
  existing contracts. Negating share cannot conceal a subsequent positive ratio,
  absence calculation or share request. Registered labels retain their declared
  meaning; they do not grant arbitrary formulas.
- The typed unavailable-requirement ledger remains validated evidence, never a
  capability registry. Evidence must occur in the relevant user message scope;
  invented evidence fails safely. Negative/literal entries cannot reappear as
  positive requirements in effective planner/reviewer input. Unknown positive
  unavailable evidence retains the existing fail-closed ledger behavior.
- Known pending grouping/measure/quote questions retain original positive dates,
  metrics and exclusions across a restart and answer. Explicit quote-role answers
  resolve a single ambiguous quoted referent. An unrelated answer retains the
  unresolved exclusion and reaches the existing stalled-clarification behavior.
  A subsequent year-only answer binds the most recent incomplete **user** named
  month, never an assistant-suggested year, another month or the clock.
- Wrong intent, plan and reviewer agreement cannot override the final gate.
  Bounded planning repair may propose a valid report; rejected candidates cause
  no adapter read. No failed database operation is automatically replayed.

Additional concrete regressions discovered during this phase were reproduced and
fixed: pending-date loss, sequential grain/year context loss, generic-mean
exclusion, filter/group role confusion, raw-date grouping bypass and inactive
ledger entries surviving into effective context. They are covered by focused
tests and are not deferred Phase 02 work.

## Independent regression protection

`tests/test_sdk_semantic_evidence.py` adds 101 focused tests. They cover English
and Persian positive/negative contrasts, quote roles and role answers, mixed
clauses, conflicts, replacement-free exclusions, custom providers, correlated
wrong model stages, exact vocabulary/aliases/descriptive terms in two unrelated
hosts, overlapping/colliding terms, unregistered boundaries, denied concepts,
separate means, Gregorian/Jalali data, refinements, session reopen, cached
receipts, preserved successful reports and no-read boundaries.

The corpus grows from 27 to 61 cases: 34 additions, independently expecting
20 reports, five clarifications and nine unsupported outcomes. All original IDs,
requests and `expect` dictionaries are unchanged, asserted against the archive.
Only resolved known-issue markers/outcome waivers were removed. The original
wrong-daily script still starts with wrong intent and a wrong daily plan; a
correct revision is appended within the existing budget. Separate custom-provider
and correlated-agreement tests prove that the wrong specification cannot execute.

Expected full rows/fields/order, periods and presentation are checked, alongside
actual adapter calls, accepted public specs, saved reports and idempotent replies.
Retail September totals are Books `70`, Garden `45`, total `115`, units `14`;
tenant/deleted rows and the exclusive October endpoint are excluded. A second
host's participant mean is `16`, row average `8`; the retail participant metric
is `115 / 2 = 57.5`. The Jalali 1405-06 oracle has fixed independent boundaries
`[2026-08-23, 2026-09-23)`. Result-mutating scorer tests continue to reject wrong
totals/groups, missing fields/rows, truncation and wrong presentation.

## Evaluation: comparable original cohort

The archived Phase 01 record remains unchanged. The observer-instrumented before
run and final `--cohort phase01` run use the same 27 IDs and independently
supported denominator of 20. Model-call changes include the deliberately
incorrect proposals; no evaluation assertion is weakened to make them pass.

| Metric | Before | After, original 27 |
| --- | ---: | ---: |
| Supported completion / verified completeness | 17/20 (85%) | 20/20 (100%) |
| Semantic correctness among returned reports | 17/18 | 20/20 |
| Correct clarifications / returned clarifications | 1/2 | 1/1 |
| Unsupported classification accuracy | 22/23 | 23/23 |
| Correct unsupported outcomes | 2 | 2 |
| Correct zero-read denials | 1/1 | 1/1 |
| Correct invalid-output blocks | 1 | 1 |
| Injected operational-failure outcomes | 2 | 2 |
| Recoverable-fault scenarios completed | 2/2 | 2/2 |
| Known supported-task defects | 3 | 0 |
| Unexpected regressions | 0 | 0 |
| Non-cached SDK submissions | 29 | 29 |
| Model transport calls | 72 | 78 |
| Calls per non-cached submission | 72/29 | 78/29 |
| Adapter calls, including injected failure | 22 | 24 |
| Planning revisions | 1 | 2 |
| Structured repair attempts | 1 | 1 |
| Intent reconsiderations | 0 | 0 |
| Local scenario latency, total / median ms | 782.466 / 25.349 | 730.845 / 28.652 |

The two formerly refused supported reports now reach execution; rejection and
repair of the wrong daily plan also adds model work. This explains the higher
calls without database retries. The before/after latency values are single
separate local scripted runs, excluding fixture construction/cache probes.
They establish neither a speed improvement nor a remote-service SLA.

## Evaluation: additions and combined corpus

| Metric | 34 additions only | All 61 |
| --- | ---: | ---: |
| Correct supported complete reports | 20/20 | 40/40 |
| Correct reports / returned reports | 20/20 | 40/40 |
| Correct clarifications / returned clarifications | 5/5 | 6/6 |
| Correct unsupported outcomes | 9 | 11 |
| Unsupported classification accuracy | 34/34 | 57/57 |
| Correct denials / unauthorized fixtures | 0/0 (undefined rate) | 1/1 |
| Correct invalid-output blocks | 0 | 1 |
| Injected operational failures | 0 | 2 |
| Recoverable-fault scenarios completed | 0/0 (undefined rate) | 2/2 |
| Known failures / unexpected regressions | 0 / 0 | 0 / 0 |
| Non-cached submissions | 40 | 69 |
| Model calls | 69 | 147 |
| Adapter calls | 23 | 47 |
| Revisions / structured repairs / reconsiderations | 0 / 0 / 0 | 2 / 1 / 0 |
| Local scenario latency, total / median ms | 886.933 / 26.8645 | 1576.060 / 27.819 |

Each column comes from its own measured run; timings need not sum. No live model
or live SQL Server call was made. The historical six PASS/four UNSUPPORTED
classifications retain their Phase 01 artifact-only provenance; they were not
rerun or promoted to independently recomputed accuracy.

Runner-generated compact records are `evaluations/baseline.json`,
`evaluations/baselines/phase02_original.json` and `phase02_added.json`.
Full traces stay in ignored `dist/phase02/`. Current records bind corpus,
evaluator, host fixture and source hashes. Recovery counters count actual
observer events. `--compact` removes detailed trajectories without changing
scores; `--cohort phase01|phase02` prevents denominator mixing. Default output
moves to `dist/phase02/evaluation.json`, preserving Phase 01 generated evidence.

## Verification commands and actual outcomes

Commands use the existing Windows `.venv`, Python 3.12.0, sqlglot 30.19.0,
python-dotenv 1.2.3, OpenAI 2.54.0, pyodbc 5.3.0 and pytest 9.1.1. No dependency
was added. The project configures pytest/build; no separate lint/type gate is
configured. All final commands below exit successfully.

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_sdk_semantic_evidence.py -q
.\.venv\Scripts\python.exe -m pytest tests/test_evaluations.py -q
.\.venv\Scripts\python.exe -m evaluations
.\.venv\Scripts\python.exe -m evaluations --strict --output dist/phase02/strict.json
.\.venv\Scripts\python.exe -m evaluations --strict --compact --output evaluations/baseline.json
.\.venv\Scripts\python.exe -m evaluations --strict --cohort phase01 --compact --output evaluations/baselines/phase02_original.json
.\.venv\Scripts\python.exe -m evaluations --strict --cohort phase02 --compact --output evaluations/baselines/phase02_added.json
.\.venv\Scripts\python.exe -m pytest -q --junitxml=dist/phase02/final-tests.xml
.\.venv\Scripts\python.exe examples/sdk_demo.py
.\.venv\Scripts\python.exe examples/multi_domain.py
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src evaluations
$env:NODE_PATH='C:\Users\Sina\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
node tests/web_tabs.cjs
.\.venv\Scripts\python.exe -m build --no-isolation --outdir dist/phase02/packages
.\.venv\Scripts\python.exe -X utf8 dist/phase02/package_smoke.py
git diff --check
```

- Focused semantic tests: **101 passed**; evaluation tests: **88 passed**.
- Normal and strict evaluations: **61 cases, zero known failures/regressions**.
  Both strict cohorts also pass. `--output` selects the artifact path;
  `--compact` only changes artifact detail.
- Full suite: **1,570 passed, one skipped**, zero errors/failures, 36.034 seconds
  in the final JUnit record. The skip is the existing explicitly opted-in live
  synthetic SQL Server integration; fake-ODBC/compiler/security/session tests run.
- SDK demo and both independent-host examples pass; retail/library clarification,
  authorized reporting and refinement produce their independently expected rows.
- Existing environment `pip check` and compileall pass. An additional AST parse
  with `feature_version=(3, 10)` passes all 49 package/evaluator/changed-test files.
  Python 3.10 runtime execution was unavailable and is not claimed.
- Browser regressions pass: tabs, history, failures, receipts, downloads, mobile
  and reporting modes. No frontend source changed.
- Wheel and sdist build successfully. An isolated venv installs the wheel with
  `--no-index --no-deps`, checks dependencies, imports all 42 installed package
  modules and runs the standalone retail/library example with sockets blocked.
  Its two base dependencies are copied from the verified existing environment;
  this verifies package isolation, not new online dependency resolution. Optional
  OpenAI/ODBC extras are absent. Archive inspection confirms wheel-only package
  contents, the new module, sdist evaluation/tests/docs, and no `.env`, local
  config, private reports, build outputs or virtual environment.
- Final diff/whitespace and baseline/hash checks pass, including unchanged
  archived Phase 01 snapshots. Generated working artifacts remain ignored.

The first failing reproductions and intermediate failing runs were diagnostic
steps, not hidden exclusions. Every final production/test change is covered by
the passing final suite and current measured baseline.

## Security and compatibility assessment

Public constructors/methods, ReportSpec, intent/requirement public records,
session JSON/schema, error-code families, host registrations, SQL compilers and
adapter contracts are unchanged. Internal evidence gains additive defaulted
fields. Existing Gregorian/Jalali conversion remains local; no model date
conversion or inferred missing named-month year is introduced.

The engine still checks current actor scope and prepares the authorized spec,
then enforces original-request evidence before any entity lookup/report read.
Trusted host registrations still own sources, relationships, policies and metric
semantics. Exact vocabulary cannot authorize a hidden concept. Deterministic
parameterized SELECT generation, execution opt-in, cardinality, cancellation,
row/work limits and result completeness checks remain in their existing paths.
Tests cover both SQLite results and SQL Server compilation/fake adapter behavior.
No result rows/identities, physical mappings, policy values or secrets were added
to model context, errors or evaluation output. There is no new service/telemetry,
production identity work, database object or production data modification.

Intentional behavior changes are correction of the three defects, enforcement of
tested exclusions, and clarification for scoped conflicts or unresolved choices.
Some requests that formerly returned the wrong report now clarify or fail the
final gate when a custom provider persists in a conflicting specification.
That behavior is necessary to preserve request correctness.

Persistence/idempotency and prior-success preservation are tested across reopen
and replay. Previously stored reports and cached request receipts keep their
original content; upgrading does not retroactively recalculate a historical wrong
report. A deliberate new submission/request ID is required for another attempt.
No automatic replay or report-fingerprint migration is introduced.

## Remaining risks and limitations

1. **Language coverage:** this is bounded, tested English/Persian evidence, not
   general natural-language understanding. Novel paraphrases, complex nested or
   double negation, multiple ambiguous quoted referents and broader discourse
   may need clarification or additional scoped evidence work. Existing unrelated
   context-repair heuristics remain; the phase does not prove every sentence.
2. **Live-model generalization:** scripted 40/40 demonstrates enforcement and
   execution for these fixtures. It cannot estimate unseen model extraction,
   long-context completeness or natural-language reasoning accuracy. No live
   measurements or production latency claims are available.
3. **Runtime/database matrix:** Python 3.10 syntax is checked but its runtime is
   untested here. Real SQL Server decimal/collation/isolation/cancellation behavior
   still needs its explicit synthetic integration environment. Existing multi-read
   snapshot consistency limitations remain host/adapter work, not resolved here.
4. **Stored evidence versions:** known pending semantic questions are reconstructed
   from messages under the unchanged session schema. Future changes to wording or
   more complex pending choices may justify a reviewed typed/versioned contract.
   Old successful receipts intentionally retain their original results.

There is no remaining reproduced Phase 02 defect or unexplained final test
failure. Broader limitations above are explicitly bounded claims, not assertions
of universal semantic correctness.

## Phase 03 proposal (not implemented)

Prioritize **held-out request-to-report completeness evaluation** before new
analytics or framework changes. The phase's concrete failures involved a valid
report answering the wrong question and evidence lost over clarification; the
scripted gate now passes but cannot measure unseen language performance.

Proposed acceptance criteria:

- Author a held-out, independently grounded English/Persian set across unrelated
  host catalogs, with exact expected outputs/ambiguities and complete requested
  requirements. Keep original and expanded Phase 02 cohorts as fixed regressions.
- Run explicit opt-in live trials using only reviewed synthetic prompts/data,
  separately from deterministic fault injection. Retain failures and report exact
  completion, completeness, clarification/refusal, calls/repairs and cost/latency
  denominators; record endpoint/model/version without secrets. No scripted fallback.
- Test longer refinements and sequential missing details against provider-neutral
  gates, saved reports and replay. If reproduced evidence loss justifies a typed
  pending-evidence/version contract, design and scope it before changing storage.
- Keep zero unauthorized reads, no model SQL/results exposure, complete result
  checks and no automatic database retries as release gates. Choose any live
  accuracy target only after measuring the held-out baseline.

Snapshot consistency and Python/dependency matrix work remain separate backlog
items. No Phase 03 implementation, capability expansion or live run is authorized
by this recommendation alone.

## Git status and proposed commit

Still on `main` at the starting revision. No commit, push or repository reset.
The original uncommitted Phase 01 work remains in the working tree, with its
history archived and the relevant documentation extended for this phase.

Tracked modifications: `README.md`, `docs/ROADMAP.md`, `docs/SDK_AGENTS.md`,
`src/sageql/sdk/agents.py`, `business.py`, `engine.py` and `evidence.py`.
Untracked groups: `docs/PHASE01_ENGINEERING.md`, `docs/PHASE02_ENGINEERING.md`,
`evaluations/`, `src/sageql/sdk/phrases.py`, `tests/test_evaluations.py` and
`tests/test_sdk_semantic_evidence.py`. `dist/phase02/` is ignored.

Proposed change-based commit message:
`fix(sdk): enforce scoped exclusions and registered vocabulary`
