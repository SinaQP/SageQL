# Reporting evaluation foundation

Current Phase 14 conclusion: **Outcome C — reliability blocked**. Authorized V6
ran 20 real calls on df46/c4d1: separately N04 0/3 reports, R02 1/1, R03/R04 3/4
attempted (R03 complete, R04 wrong grouping and mandatory stop). Two R04 turns were
unexecuted. Final a226 fixes are offline-only. See [V8](phase14/verification.v8.json),
[causal V5](phase14/causal-audit.v5.json), [all 22 cases](phase14/coverage.v1.json),
[exposure V7](phase14/exposure.v7.json) and [the final report](../docs/PHASE14_ENGINEERING.md).
No historical/current-source scores are pooled. N06/A01–A12 and N05's denial have
no live measurement. No further scope/model is enabled; a controlled stronger-model
comparison needs its own exact review/authorization. Older status paragraphs below
are historical and do not reopen closed scopes.

The latest authorized V5 assessment ran 29 calls on c7a1/c4d1. Development N02/N04
scored 4/5 reports; separately R01/R02 scored 2/3. R02's unrequested sorting was
accepted and stopped the batch; R03/R04 remain live-unexecuted. N02 completed its
clarification trajectory, while N04's reversal was safely blocked. See
[V7 evidence](phase14/verification.v7.json), [causal audit V4](phase14/causal-audit.v4.json)
and [the report](../docs/PHASE14_ENGINEERING.md). The later df46 source has offline
fixes only; V6 is a disabled proposal separating development R02 from R03/R04.

The earlier authorized V3 assessment ran 17 calls on ccc6/c4d1 and stopped at N04
turn 1 on an accepted unrequested grouping. N03 completed 3/3 reports and exercised
period canonicalization live; N02 still failed continuation. Completion was 4/6
attempted reports. N04 comparison turns and all R replacements were unexecuted.
See [V6 evidence](phase14/verification.v6.json), [causal audit V3](phase14/causal-audit.v3.json)
and [the report](../docs/PHASE14_ENGINEERING.md). Final c7a1 fixes are offline-only;
the separate V5 proposal is disabled. V3 and earlier allowances remain closed.

The earlier approved Phase 14 V2 run dispatched 20 calls on SDK 8e3c/c4d1
and stopped at N03 turn 2: 4/6 attempted reports met the full frozen contract.
All five published reports had correct rows/bounds; one failed typed period
representation. N01 completed, N02 lost clarification context, N03 is partial,
N04 and replacements were unexecuted. See [the report](../docs/PHASE14_ENGINEERING.md),
[new causal audit](phase14/causal-audit.v2.json) and [V5 evidence](phase14/verification.v5.json).
SDK ccc6/c4d1 has subsequent offline fixes only. V2 is closed; the V3 proposal is
disabled and requires separate exact approval. No allowance is recycled. Existing
shared structured repair remains opt-in with default zero. Counterfactual replay
and scripted success are never credited as live model success.

Phase 14's first [separate legacy/new assessment](PHASE14.md) stopped on a wrong
N01 report. A separately authorized corrected-source continuation then dispatched
28 requests, completed 1/11 attempted report goals and stopped on transport failure
with uncertain usage. It accepted no wrong report; N06 and all legacy A cases
remain unexecuted. The preserved first attempts, subsequent offline-only repairs,
separate replacement cases and exact limits are in the current engineering report
and versioned Phase 14 evidence. Scripted success is separate from live quality.

Phase 13 adds an explicitly authorized [exploratory accounting option](PHASE13.md)
to the existing live runner, preserving strict mode and every offline default.
See [the current real-model report](../docs/PHASE13_ENGINEERING.md) for actual
first attempts and separately labeled correction results. Earlier phase statuses
below describe their historical execution scope.

The [SQLite-first testing guide](../docs/SQLITE_FIRST_TESTING.md) documents the
shared synthetic host builders, independent reference calculations, offline
commands and separate native SQL Server limits. Default evaluation commands use
scripted models and disposable SQLite, never Rahtal settings or production data.
Existing corpora, expected outcomes, references and historical measurements below
retain their original version/source scope.

Phase 09 adds [semantic continuation repair evidence](PHASE09.md), exposed
development promotions and frozen replacements. Same-script/source comparisons
separate SDK corrections from invalid mock metadata; original cases and first
results remain intact. This is offline evidence, with no live authorization.

Phase 08 prepares a [focused real-model pilot and exact disabled approval packets](PHASE08.md)
using the same Phase 06 runtime. Completion is preflight only; external execution
awaits authorization and accounting review. New offline incompletions remain
visible and do not represent real-model accuracy.

Phase 07 adds [clarification-continuation evaluation](PHASE07.md), preserves
exposed L26 as development and freezes independent library replacements. Its
offline command reuses the durable Phase 06 runner; historical populations and
results remain separate. See [the engineering report](../docs/PHASE07_ENGINEERING.md).

Phase 06 adds fresh synthetic assessment/development/protocol cohorts, durable
first-attempt checkpoints, exact live approval and request/input/output/time/USD
accounting. Run the separately gated command in [the Phase 06 guide](PHASE06.md).
Offline readiness is verified; live-model reliability remains unverified. The new
assessment retains its unfulfilled L26 continuation and returns exit 1 honestly.

Phase 05 adds separately versioned optional-vocabulary hosts and frozen cohorts.
See [the Phase 05 guide](PHASE05.md) for provenance, exact denominators, privacy
and commands. Earlier corpus/baseline/freeze bytes remain preserved.

Current Phase 04 filter/order measurements and reproduction instructions are in
[PHASE04.md](PHASE04.md). Earlier corpus files, freezes, expectations and baseline
records remain preserved. The combined Phase 03 suite still exits 1 for D02 and
D03; its pipeline cohort now passes. A blocked/clarified supported report is not
credited as completed.

Phase 03 adds separately frozen trajectory suites, independent reference data,
stage diagnostics and reviewed/budgeted live opt-in. See [the Phase 03 guide](PHASE03.md).
The 61 original regression cases and Phase 02 baseline below remain unchanged;
current regression measurements are in `baselines/phase03_regression.json`.

Run from the checkout using the supported development environment:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_evaluations.py -q
.\.venv\Scripts\python.exe -m evaluations
.\.venv\Scripts\python.exe -m evaluations --strict
.\.venv\Scripts\python.exe -m evaluations --strict --cohort phase01
.\.venv\Scripts\python.exe -m evaluations --strict --cohort phase02
.\.venv\Scripts\python.exe -m evaluations --strict --compact --output evaluations/baseline.json
.\.venv\Scripts\python.exe -m evaluations --case retail_change --output dist/phase02/change.json
```

The default runner writes `dist/phase02/evaluation.json` and prints measured
summary metrics. It executes 61 synthetic scenarios through the public SDK,
real intent/planner/reviewer decoding, both SQL compilers, read-only SQLite,
persistent sessions, saved-report retrieval and cached request receipts. No
credentials, internet or SQL Server are needed. The pytest corpus explicitly
blocks socket connections. Output artifacts contain classifications, checks,
stage metadata, public concept IDs, dates, timings and hashes, without user text,
filters, policy scalars, SQL, row values or credentials.

Exit codes: `0` matches the recorded baseline; `1` differs from it; `2` cannot
complete because of input/configuration/dependency errors. `--strict` also exits
`1` if a future explicitly documented known-failure waiver remains. Phase 02
resolves all three Phase 01 defects: their original expected outcomes remain
unchanged, their waivers/xfails are removed, and strict mode now passes. The
original wrong daily intent/plan remain in the script, followed by one valid
revision within the existing budget; the rejected candidate issues no SQL.
Expected operational faults are still classified `operational_failure`, with
separate assertions for safe errors, no reads/replay and no partial publication.

## Ground truth and limitations

`cases.json` holds requests, tags, specification overrides and independently
authored expected fields, rows, periods, presentation and intended outcome.
The existing `examples/multi_domain.py` supplies two host catalogs and seed data;
neither host's embedded expected rows are the report scoring oracle. The library
conversation's prerequisite is additionally checked against the existing example.
For example, permitted retail lines total 70 for Books and 45 for Garden; excluded
tenant/deleted lines and the exclusive October endpoint must not enter September.
The participant mean is (14 + 2 + 6 + 10) / 2 = 16, distinct from a row average.
The fixed change fixture is (70 - 700) / 700 * 100 = -90%.
Jalali 1405-06 uses fixed independent Gregorian boundaries
`[2026-08-23, 2026-09-23)` rather than calling the calendar code for its oracle.

Scripted responses are generated from specified scenario selections, including
deliberately wrong plans, correlated model mistakes, malformed output and
transport/database failures. They are **not measurements of live natural-language
understanding**. Expectations are not derived from the returned SQL/results or a
reviewer approval. Exact Decimal comparison ignores formatting scale, preserves
precision and rejects nonfinite values. Text/dates/order remain exact. The scorer
has independent result mutation tests: wrong totals/groups, absent rows/metrics,
truncation, wrong presentation and empty success text must fail.

The stage trace records decoded/effective intent and proposals/reviews separately;
validated query metadata records the real adapter inputs. Accepted public specs,
fixed expected periods, actual rows, report JSON, persisted retrieval and receipts
are checked. This does not prove the correctness of every business sentence in an
assistant reply. Normal successful replies are generated locally from registered
labels, periods and sorting; their presence/error shape is checked here. Richer
free-text semantic scoring, more languages and paraphrases remain future work.

The ordinary suite retains broader coverage for relationships, cardinality,
declines, matching-day counts, calendars, policies, cancellation and failures.
This corpus is a representative cross-layer gate, not a replacement for those
unit/integration tests. SQLite numerics and fake ODBC tests do not establish live
SQL Server decimal, collation, isolation or cancellation behavior.

## Outcome and metric definitions

| Outcome | Meaning |
| --- | --- |
| `correct_report` | Intended supported request; checked spec, exact data/order/fields, dates, presentation, declared truncation and invariants match. |
| `correct_clarification` | Fixture independently requires clarification and the reply supplies the expected business detail. |
| `correct_unsupported` | Fixture requests an unavailable capability, returns an explanation and publishes no report/reads. |
| `correct_denial` | Unauthorized request gets `access_denied`, without reads. |
| `correct_block` | Deliberately invalid output fails with the expected safe validation code. |
| `incorrect_rejection` | Supported/clarifiable request gets the wrong refusal/question/block. |
| `semantic_error` | Report returned with wrong selections, values, grouping, order or presentation. |
| `incomplete` | Required fields absent, unexpected truncation, or inconsistent partial publication. |
| `operational_failure` | Provider/database/request failed; never credited as report completion. |
| `unexpected_report` | A report was published for a request expected to clarify/refuse/deny/block. |

All rates include numerator and denominator; empty populations have `value=null`.

- Supported completion and verified report completeness: correct complete reports
  / all fixtures independently requiring a report (including known failures).
- Semantic correctness: correct reports / returned `report_ready` responses.
- Clarification precision: correct clarifications / all returned clarifications.
- Unsupported classification accuracy: correct binary supported-or-unavailable
  classification / report, clarification and unsupported fixtures. This is not
  overall task accuracy; a failed supported request can still be correctly
  classified as not unsupported.
- Unauthorized prevention: correct zero-read denials / unauthorized fixtures.
- Recovery effectiveness: correct reports / fixtures with an injected recoverable
  fault. Transport/database faults have no automatic replay and are excluded.
- Regression count: deviations from each explicit baseline outcome or violated
  safety/state invariant. Known failures are counted separately. This is one
  revision's regression count; a longitudinal regression frequency is unmeasured.
- Model calls: actual transport invocations, including failed calls and repairs.
  Per-request mean divides by non-cached SDK submissions. Database calls count
  adapter invocations, including failed ones and lookup/label reads.
- Latency: measured elapsed milliseconds for a scenario's submissions (including
  conversation turns), excluding fixture construction and subsequent cache/read
  probes. Per-turn timings/calls are also retained. Scripted latency is not a
  remote model SLA or a production database benchmark.

`baseline.json` is the compact measured current Phase 02 record. Full generated
traces stay in ignored `dist/phase02/`. Hashes bind the corpus, host fixtures, evaluator
and package source so later results can be compared against an identified state.
`--compact` projects measured results without changing scores or denominators.
Actual planning revisions, structured repairs and intent reconsiderations are
now counted separately from whether a recoverable-fault scenario succeeded.

## Comparable cohorts and preserved Phase 01 evidence

`baselines/phase01.json` and `baselines/phase01_cases.json` preserve the exact
original measurements/corpus. The 27 original requests and expected results are
unchanged; tests assert this. `--cohort phase01` selects those same IDs and same
20 supported-task denominator. `--cohort phase02` selects only the 34 additions.
Default/all reports the expanded 61-case corpus separately. New cases cover
en/fa exclusions, quoted requirements/data, mixed unsupported clauses, ambiguity,
ordinary and Jalali grouping, distinct means, filter/dimension/grain refinements,
ledger consistency, and clarification answers. Targeted tests additionally cover
custom-provider bypasses, raw date grouping, vocabulary collisions/authorization,
generic mean removal and preservation across sequential missing details.

Measured records:

- `baselines/phase02_before.json`: original SDK source from `b74c109`, original
  evaluator and 27 cases copied to an ignored isolated directory; a delegating
  observer counted recovery events. It reproduces 17/20 supported reports, 72
  model calls, 22 adapter calls, one revision and one structured repair.
- `baselines/phase02_original.json`: final implementation, original 27 IDs;
  20/20 supported reports, 78 model calls and 24 adapter calls, no waivers.
- `baselines/phase02_added.json`: the 34 additions alone; 20/20 reports, five
  correct clarifications and nine correct unsupported outcomes.
- `baseline.json`: all 61; 40/40 reports, six correct clarifications, eleven
  correct unsupported outcomes, one denial, one invalid-output block and two
  intentionally injected operational failures. No unexpected regression.

Before/after calls increase because two previously refused reports now complete
and the wrong daily proposal is rejected and repaired. No failed query is retried.
All values are scripted measurements, not live language scores. Each cohort run
has separately measured timing; its milliseconds need not sum to another run.

## Opt-in live-model evaluation

Explicitly supply a reviewed endpoint and model using `SAGEQL_EVAL_API_KEY`,
`SAGEQL_EVAL_BASE_URL` and `SAGEQL_EVAL_MODEL`, then run:

```powershell
.\.venv\Scripts\python.exe -m evaluations --suite holdout --live --case H01 --live-approval dist/phase03/live-approval.json --output dist/phase03/live-first-H01.json
```

Phase 03 additionally requires explicit evaluation authorization, a reviewed
matching approval file and whole-run budgets; the old regression live entry point
now rejects calls. Follow [the exact live procedure](PHASE03.md#exact-opt-in-live-procedure-not-executed).
Only `--live` constructs a remote client; normal runs never load `.env` or private
host configuration. Only repository-owned synthetic questions/business metadata
are sent to that endpoint. The live path uses the same expected data and actual
local SQLite, never SQL Server or real application data. It counts actual calls,
including failures, with the agent's shared 30-second budget and zero transport
retries. Scripted fault cases are excluded from this language evaluation. Use
`--case` to bound cost. Live failures are retained; there is no scripted fallback.
Live mode requires the existing `openai` extra. **Not executed in Phases 01 or 02.**

## Historical Rahtal evidence

The original exact ten questions, expected results, replies, interpretation/query
captures and verification scripts are available locally under the existing
ignored `sageql_rahtal/reports/phase3_20261015` directory. Inspect their evidence
consistency without contacting a model/database:

```powershell
.\.venv\Scripts\python.exe -m evaluations --history sageql_rahtal/reports/phase3_20261015 --output dist/phase01/history.json
```

This imports the exact questions in memory, checks identity/text/status/bounds
consistency, inventories captures and exports only allowlisted metadata/hashes.
The recorded classifications are six PASS and four UNSUPPORTED. It does **not**
rerun questions, regenerate reference data or independently recompute historical
numeric accuracy. The original recorded verification booleans remain labeled as
recorded evidence. A new checkout without private artifacts cannot reproduce
that historical run; missing files fail explicitly instead of creating questions.
The tracked synthetic corpus never copies private questions, names or rows.
