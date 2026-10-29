# Phase 14 — Final reliability decision: Outcome C

## Authorized V6 execution and exit decision (2026-10-28)

**Outcome C — Reliability blocked.** The authorized V6 run actually executed; it
is closed after the mandatory wrong-report stop. This completes the requested
engineering investigation, not the Phase 14 reliability acceptance criteria.
The tested AvalAI `gpt-5-nano` configuration cannot be approved for dependable,
unattended completion of the supported reporting contract. R02 improved live,
but recurring grouping failures and failed bounded recovery outweigh that narrow
success. Neither production readiness nor permission to begin Phase 15 follows.

Exact approved scope: `dist/phase14/completion/approval-scope.v6.json`, SHA256
`2127c2b69c78105033c52d4f4b7ae0a2835d5ba3ce9c649846c3ba577f74c773`.
All 20 actual calls used unchanged SDK
`df46aee74f313b26e4dbed0a9472ea62c602d61b56f3da120ffa42c913506f43`, evaluator
`c4d1db5c16ed86b30895fab07f3a7669f2b3242f730bd9c16ad274b7bec1b4ec`, endpoint
`https://api.avalai.ir/v1`, exploratory accounting and synthetic SQLite only.
Source/corpus/scope hashes and fresh output were checked before model-key access.
No Rahtal settings, production database, SQL Server or private data was accessed.
N04, R02 and R03/R04 ran in the exact approved order. No allowance was recycled.

| Separate V6 selection | Executed / planned turns | Correct supported reports | Correct conversations | Wrong accepted specifications |
|---|---:|---:|---:|---:|
| N04 development | 3/3 | 0/3 | 0/1 | 0 |
| R02 development | 4/4 | 1/1 | 1/1 | 0 |
| R03/R04 replacements | 4/6 | 3/4 attempted; 3/6 planned | 1/2 attempted, including partial R04 | 1 |

R03 completed all three reports and its conversation. R04 published an incorrect
first report, then the safety hook stopped the entire batch immediately. Its last
two turns were not executed. These separate samples are not pooled into an
accuracy estimate. Original journals, responses, first failures, frozen questions,
references and scores remain unchanged. See additive [verification V8](../evaluations/phase14/verification.v8.json),
[causal audit V5](../evaluations/phase14/causal-audit.v5.json),
[coverage ledger](../evaluations/phase14/coverage.v1.json) and
[exposure V7](../evaluations/phase14/exposure.v7.json).

## What happened at the actual boundaries

**N04:** the first Intent added Channel as an output dimension, although Channel
was a filter and the request wanted one total. Existing evidence correctly removed
that dimension from effective Intent. Both Planner attempts nevertheless repeated
the grouping and were rejected before Reviewer or any read. The single allowed
revision did not repair the known discrepancy. No base report was published;
subsequent comparison turns asked unnecessary questions and failed. Session
atomicity intentionally does not promote a failed fresh request into a successful
report context. Changing that contract would conceal the earlier failure. V6 does
not live-verify reversal correctness: its reversal was never successfully planned
and executed. V5's first two N04 reports are historical successes, not V6 successes.

**R02:** the local owner question, rejected negative answer, owner selection and
year continuation all met their frozen expectations. An invalid null-year month
was followed by the correct independent missing-year fallback. The final report
preserved Service grouping, the Channel and Technician predicates, July 2026 and
unsorted table defaults. All 13 final requirements, independent rows and fields
passed. This is actual live evidence for the clarified-table fix on this exposed
conversation, not broad conversational generalization.

**R03:** all three Persian registered-alias, filter-removal and requested-ranking
reports matched the independent specifications, fields and numerical references.

**R04:** “Give a table total of Borrowings for September 2026 with Shelf =
Scientific; no time buckets” requires no business dimension. Raw Intent and
Planner instead selected Shelf; Reviewer approved. The old evidence encoded an
empty required-dimension subset, which does not prohibit extra dimensions. Its
older whole/entire-period guard also missed generic explicit totals. The final
report therefore had an extra Shelf field. The scalar count of 3 does not excuse
this substantive report-shape failure. Both frozen dimension and field checks
matter; it is not an equivalent period representation or a policy violation.

Reviewer approved four correct candidates and one incorrect candidate. It rejected
none of the one incorrect candidate it actually saw; N04 never reached Review.
Intent/Planner/Reviewer agreement is not independent correctness evidence. Stage
all-field diagnostic mismatches involving nullable defaults or equivalent period
forms remain recorded; they are not all treated as wrong final reports.

## Shared root causes and smallest corrections

Phase 13 already observed invented time grouping, invented ranking and two wrong
Reviewer approvals. Phase 14 adds lost clarification defaults, stale comparison
roles and invented business grouping. The repeated mechanism is incomplete
request evidence at the deterministic boundary, combined with correlated model
agreement and occasionally ineffective bounded recovery. SQL authorization and
structural validity do not establish the requested business meaning.

The final SDK is `a2269c0280189c998e58c230952f7bdeb9abd5c6fdd4b13e12e299c1c52fdcae`; evaluator is unchanged.
It has **zero live calls**. Only `src/sageql/sdk/evidence.py` changed in this
continuation; public ReportSpec, persistent sessions, adapters, SQL, policies,
model, dependency and retry/token limits were preserved.

1. A private typed projection distinguishes **unspecified dimensions** from a
   **known empty complete projection**. A fresh explicit table total for one
   registered metric owner, without a positive/ambiguous grouping or ranking
   request, carries that complete projection even while an owner/year is missing.
   Known-question reconstruction retains it; an explicit new grouping replaces it.
   Effective Intent and every provider's final specification must satisfy it.
   Filters remain filters. Registered labels and predicate values are masked before
   recognizing control words. Existing grouped reports and explicit groups/ranking
   retain their meaning; legacy provider defaults outside this evidence scope remain.
2. Adjacent named-month/role relations bind **before interval connectors**. The
   same relation handles date-before-role and role-before-date, independent of
   mention order, using existing Gregorian/Jalali typed months. A role assignment
   claims its “to” connector, so an incomplete/conflicting assignment cannot fall
   through to a single date range. Missing years are not guessed; negative/literal
   declarations do not become positive selections. Genuine June-to-July ranges
   still work. Year association accounts for every supplied year rather than
   silently retaining an older year in a year-only refinement.

The second defect was independently reproduced beyond the frozen sentence. On
historical df46, “The base period is June 2026 and the comparison period is July
2026” accepted both stale reversed months and a wrong merged range. “Set the base
to June 2026 and the reference to July 2026” rejected the correct comparison and
accepted a merged June-through-July range. The final gate accepts the correct
comparison and rejects both wrong forms for both orders. These were pure local
checks, not invented native or live-model outcomes. The recognizer remains bounded
fa/en evidence, not a general natural-language parser or proof of all semantics.

No extra Planner revisions, recovery loop, new model stage, schema expansion or
sentence-specific exception was added. N04's persistently wrong Planner remains
safely blocked. More retries have no demonstrated benefit in this V6 failure.

## Offline reproduction and release verification

All 20 captured responses reproduce the original V6 turn outcomes on the exact
saved df46 source with zero divergence/network. On final source, N04 still safely
fails and R02 still succeeds under captured outputs. R03's prefix remains correct;
R04's old wrong plan is rejected before Reviewer/database, after consuming 11/12
recorded replacement responses. The next required stage is a new Planner response,
not the captured Reviewer approval. Replay stops there and fabricates nothing.
No improved live completion rate is inferred from that counterfactual.

Thirty new regressions cover three reporting domains; role word orders and years;
Gregorian/Jalali months and real intervals; conflict/negation/title/filter data;
explicit versus empty grouping; owner/year continuation; old grouped reports; and
corrected or persistently wrong model plans. The exact final test file produces
16 failures/14 passes on historical df46 and 30 passes on final source. Controlled
corrected-output R04 checks include frozen rows, fields and full specifications.
A free-form unquoted filter value is retained as data; the cross-domain presentation
case uses a quoted value to make its boundary explicit, rather than guessing a
new unquoted literal grammar.

The first implementation (73d4 source/wheel retained) broke one existing year-only
refinement test on each platform: 2,420 passed / 1 failed / 13 skipped. Its logs
remain. The corrected association rule preserves that existing behavior. No
existing test, fixture answer or frozen expectation was relaxed.

Final source passes **2,421 tests / 13 optional native skips** on Windows Python
3.10.22, Windows Python 3.12.0 and Ubuntu WSL2 Python 3.12.3. Every prior strict
semantic gate and all 14 SQLite consistency schedules pass on each platform.
Phase 03 retains its explicitly expected historical D02/D03 failures. Scripted
legacy is 14/14 reports and 12/12 conversations; independent N is 12/13 and 5/6,
with N06 still incomplete. All R replacements separately pass 9/9 reports and 4/4
conversations offline. These scripted scores are not live-model measurements.
Clean lower-bound Python 3.10 core installation imports all 45 modules and runs
both examples without OpenAI, pyodbc or network. Packaging/inventory/source checks
are recorded separately after the final documentation/evidence build.

## V6 resource accounting and performance

| Observed measurement | N04 | R02 | R03/R04 prefix |
|---|---:|---:|---:|
| Intent / Planner / Reviewer calls | 2 / 2 / 0 | 2 / 1 / 1 | 4 / 4 / 4 |
| Requirement checks | 0/39 | 13/13 | 51/52 |
| Clarification precision | 0/2 emitted | 2/2 emitted | No emitted or required questions |
| Clarification recall | No expected questions | 2/2 expected | No expected questions |
| Planner revisions / structured repairs | 1 / 0 | 0 / 0 | 0 / 0 |
| Synthetic DB executions | 0 | 1 | 4 |
| Input / completion tokens | 18,035 / 15,345 | 17,496 / 12,845 | 53,573 / 32,668 |
| Cached-input / reasoning subsets | 8,448 / 14,656 | 11,648 / 12,160 | 36,992 / 31,232 |
| Intent latency, ms | 56,764.271 | 48,393.857 | 93,581.122 |
| Planner latency, ms | 42,651.110 | 15,093.847 | 63,749.238 |
| Reviewer latency, ms | 0 | 11,327.857 | 42,510.972 |
| Summed turn latency, ms | 99,999.721 | 76,923.314 | 201,404.703 |
| DB latency, ms | 0 | 1,519.484 | 442.129 |
| Estimated USD | 0.00703975 | 0.00601280 | 0.01574585 |

Consumption totals only: **20 calls**, 89,104 input / 60,858 completion tokens,
149,962 total, 57,088 cached input and 58,048 reasoning. Subsets are not added again;
full input prices are used without a cache discount. Independently reconciled
published-rate estimate **$0.02879840**; final provider bill remains unknown.
Controller elapsed **400.656 seconds**. All per-selection/combined safeguards
remained intact. All calls returned reconciled usage, nonempty content and
`finish_reason=stop`, below the 8,192 completion cap. Null-year structured-semantic
failure still occurred; a normal stop is not proof of schema correctness.
No missing usage, length/empty response or transport uncertainty occurred in V6.
The generic replacement `runner_failure` records the safety-hook stop, not a
provider transport failure. No database/model transport operation was retried.

No unauthorized read, accepted model-authored SQL or payload-isolation violation
was observed. No genuine policy-denial turn ran, so no live denial-prevention rate
is claimed. The old request-28 transport cause, old socket-abort cause and invoices
remain unverified. SQLite does not verify SQL Server dialect execution, native
types/Decimal/date binding, ODBC, collation or SQL Server snapshot guarantees;
all 13 native integration cases remain separately optional and disabled.

## Complete coverage ledger and model decision

| Population | Latest genuine live evidence | Limitation |
|---|---|---|
| N01 | V2, 8e3c: complete, 2/2 reports | Historical source |
| N02 | V5, c7a1: complete, 2/2 reports | Historical source; failures before that retained |
| N03 | V3, ccc6: complete, 3/3 reports | Historical source |
| N04 | V6, df46: 0/3 reports | Current tested configuration fails bounded recovery |
| N05 | d1f4 continuation: only turn 1 attempted, failed | Turn 2 policy revocation/denial never ran live |
| N06 | No live turns | Current scripted conversation also incomplete |
| A01–A12 | No live turns (21 turns / 14 report goals) | Offline-only; not current-model quality evidence |
| R01 | V5, c7a1: complete, 2/2 reports | Historical source |
| R02 | V6, df46: complete, 1/1 report | Exposed development regression |
| R03 | V6, df46: complete, 3/3 reports | Now live-exposed replacement |
| R04 | V6, df46: wrong first report | Last two turns unexecuted |

The 22-case machine-readable ledger preserves every canonical first-attempt prefix,
source/evaluator/selection/corpus hashes, tags, full/partial outcomes, denial slots
and live-unexecuted turns. No snapshot/Temp duplicate is counted. Vocabulary and
opaque-reference cases are identified separately: N03 and R03 have source-specific
live evidence, A populations do not. Negative clarification replies are not policy
denials. Persistent ownership, revocation, replay, opaque-reference adversaries and
WAL consistency have offline coverage, not an inferred live-model pass rate.
All final a226 source model behavior remains live-unverified. Historical frozen
exposure text is retained; the new exposure ledger supersedes it for actual use.

**Present model suitability:** not demonstrated for reliable unattended reporting.
Repeated invented dimensions, repeated invalid periods and the failed N04 revision
support a model-capability hypothesis. However, the deterministic guard also had
real holes and even rejected a correct comparison; a stronger model alone cannot
repair those SDK defects. The observed data do not isolate a model-only cause or
prove that another model will succeed. Keep `gpt-5-nano` unchanged in this task.

**Exact next action:** select a specific stronger comparison model and explicitly
review/authorize a controlled, source-bound comparison on the fixed SDK. Use the
existing runner, identical synthetic catalogs, independent references and first-
attempt scoring. Pair nano and the selected model on exposed N04/R02/R04 development
conversations; retain the same 8,192 completion cap, deadlines, one shared repair
and one Planner revision. Define finite request/token/time/estimated-spending limits
from that model's reviewed accounting, preserve failures, and apply mandatory stop
rules. Do not silently reuse V6 or execute this design. Distinguish raw/effective
Intent, proposals, deterministic rejections, Reviewer decisions, complete reports
and conversations. A model arm improving those outcomes under identical SDK rules
would support a capability explanation; shared deterministic rejection or identical
semantic failures points back to the SDK boundary. Partial stopped arms cannot be
presented as a complete paired comparison or a statistical generalization.

Only after a qualifying comparison should a separately authorized, frozen broader
assessment include N06, A01–A12, actual policy denial and untouched wording. No new
execution-ready approval packet or framework is created here. Outcome A is barred
by wrong accepted reports and incomplete coverage; Outcome B understates the
recurring supported-request failure. **Outcome C is the final engineering decision;
the reliability objective remains blocked. Phase 15 has not begun.**

HEAD remains `b74c10974265dcac522b3e23623e0f4f9a8ae582`, branch `main`, empty index.
Earlier worktree changes and Phase 01–14 evidence remain. No commit, push, publish,
deploy or production operation occurred. Proposed commit message for this slice:
`fix: preserve total projections and bind comparison roles before ranges`.

---

The following V5 and earlier sections are preserved historical observations.
They describe their source and authorization state at that time; the V6 decision
and additive ledgers above are current.

## Historical V5 report: specific gains and stopped assessment

## Latest authorized V5 run (2026-10-28)

The user explicitly authorized `dist/phase14/completion/approval-scope.v5.json`.
Exact SDK `c7a139cc15db3a7cba64cb5011aceef818f93c24089551442848be7038de0320`
and evaluator `c4d1db5c16ed86b30895fab07f3a7669f2b3242f730bd9c16ad274b7bec1b4ec`
were verified against both prepared selections, corpus/freeze hashes and fresh
outputs before credential access. Source and contracts stayed unchanged during
all **29 real AvalAI gpt-5-nano calls**. Only synthetic SQLite hosts were used.

Development N02/N04 finished, then replacements ran until **R02 turn 4 accepted
an unrequested ordering**. That frozen-contract failure immediately closed the
entire V5 batch. Its rows happened to match the independent reference; the wrong
specification is preserved as a failure. R03/R04 were not dispatched. No unused
allowance was recycled and no subsequent changed-source live call occurred.
**Phase 14's overall reliability objective remains unmet.**

| Selection | Executed / planned turns | Correct supported reports | Correct complete conversations | Wrong accepted specifications |
|---|---:|---:|---:|---:|
| Development N02/N04 | 8/8 | 4/5 | 1/2 | 0 |
| Replacement prefix R01/R02 | 7/13 | 2/3 | 1/2 executed; R03/R04 unexecuted | 1 |

All four touched conversations ran their full turn lists; none has a partial
conversation denominator. The six unexecuted turns are R03 and R04, three each,
covering six unattempted report goals. They receive no success/failure rate.
The two selections are scored separately, without pooling development and
replacement quality or different SDK versions. Both have prior offline exposure
and familiar hosts/authorship; this is not an externally blind assessment.

The exact starting tree, enabled copies, original journals/results, 17 development
and 12 replacement responses, and closed batch ledger are preserved under
`dist/phase14/completion/live-v5/`, alongside original temporary outputs. The V5
scope and reviewed disabled packets remain byte-identical. See additive
[V7 evidence](../evaluations/phase14/verification.v7.json),
[causal audit V4](../evaluations/phase14/causal-audit.v4.json) and
[exposure V6](../evaluations/phase14/exposure.v6.json). Prior evidence is unchanged.

### Actual correction effectiveness and remaining failures

| Turns | Actual first attempts and checks | Interpretation |
|---|---|---|
| N02 / 1–3 | Correct owner question and negative-answer block. Affirmative owner answer again produced a null-year month; local validation rejected it and asked the independently known year after one Intent call, with no repair or read. | The new missing-year fallback was exercised live. |
| N02 / 4–5 | Model labeled the year answer `new`; confirmed-answer anchoring retained the original metric, filters and month. Reopened report and explicit fresh report both passed every frozen row/specification/receipt/isolation check. | 2/2 reports and full conversation correct on c7a1; V3 ccc6 had 1/2. This is a specific observed trajectory, not a statistical causal rate. |
| N04 / 1 | Intent was ungrouped; first Planner proposal reintroduced Channel grouping. It was rejected before Review. The one revision removed Channel and produced the required single Billed amount total of 280; Reviewer approved the corrected report. | Genuine successful bounded recovery; no wrong grouped report published. Intent was already correct, so this run does not isolate the grouping guard from existing Intent agreement. |
| N04 / 2 | July remained base, June became comparison and the Channel filter was retained. | Correct complete comparison report. |
| N04 / 3 | User explicitly assigned June as base and July as comparison. Intent retained the opposite roles. First Planner chose the requested roles but added `change`; revision removed that calculation and otherwise matched the user request. Both conflicted with stale effective Intent and were rejected; Reviewer and database were never reached. | Incorrect rejection. First model error was stale Intent; local evidence failed to anchor explicit role wording. |
| R01 / 1 | Two successive Intent responses contained null-year months. One shared structured repair did not repair the period; the existing independent missing-year fallback still asked the correct question. | Correct clarification, not a valid repaired Intent. |
| R01 / 2–3 | Completed the requested metric/group report and metric replacement. | 2/2 correct reports and complete conversation. |
| R02 / 1–3 | Correct owner question, correct negative block, then the confirmed-owner missing-year fallback after one malformed Intent. | Clarification continuity correct. |
| R02 / 4 | Original request was a plain table by Service. Owner/year reconstruction retained metric, dimensions, dates and both filters, but lost the original plain-table default ordering. Intent left ordering unspecified; Planner introduced `order_by=billed, descending=true`; Reviewer approved and the final gate allowed it. | Wrong accepted specification. Correct fields/types/rows do not excuse the unrequested sort; immediate batch stop. |

R02's published rows were `Repair, 220` and `Tune, 60`; billed-descending order
happened to equal this fixture's default order. Frozen requirements still require
`order_by=null, descending=false`. Only those two final requirement checks failed.
Its effective-Intent filter diagnostic also failed strict representation/order
comparison, but inspection shows both Technician exclusion and Channel predicate
were retained; final filter checks passed. No filter-loss defect is inferred from
that diagnostic. All raw stage classifications remain unchanged.

The missing comparison-role anchor was specific: existing recognition covered
`compare ... with`, `versus` and equivalents, but not affirmative statements of
which named month **is/as the base/reference/comparison**. Valid typed months were
parsed without assigning roles, leaving stale model context authoritative.
For R02, the final year reply was combined with the immediately preceding owner
answer, which contained no table wording. Plain-table metadata had not been
retained while the filter owner and year were pending. The gap affected Intent
default transfer and final provider-neutral enforcement. Reviewer also approved
the wrong ordering. These are confirmed boundary failures, not transport failures.

### Independent measurements and reasoning investigation

| Measurement | Development | Replacement prefix |
|---|---:|---:|
| Exact report requirement checks | 52/65 | 37/39 |
| Clarification precision / recall | 2/2 emitted; 2/2 expected | 3/3 emitted; 3/3 expected |
| Intent / Planner / Reviewer calls | 6 / 7 / 4 | 6 / 3 / 3 |
| Correct / incorrect Reviewer approvals | 4 / 0 | 2 / 1 |
| Planner revisions | 2: one useful, one unable to resolve stale Intent | 0 |
| Shared structured repairs | 0 | 1; repeated invalid period, then independent fallback |
| Synthetic database executions | 4 | 3 |
| Tokens: input / completion | 74,945 / 45,928 | 51,153 / 34,535 |
| Cached input / reasoning subsets | 55,168 / 43,520 | 40,448 / 33,024 |
| Intent / Planner / Reviewer latency (ms) | 120,398.369 / 145,961.416 / 37,340.201 | 129,822.676 / 61,362.739 / 26,606.046 |
| Summed turn latency (ms) | 304,526.455 | 218,227.447 |
| Database latency (ms) | 50.208 | 21.417 |
| Independently reconciled estimated USD | 0.02211845 | 0.01637165 |

Totals for consumption accounting are **126,098 input / 80,463 completion tokens**,
206,561 total. Cached input 95,616 is already part of input and reasoning 76,544
is already part of completion. No double counting or cache discount is applied.
The total published-rate estimate is **$0.03849010**; actual billing is unknown.
Controller elapsed time was **536.047 seconds**. All approved per-selection and
combined request/token/deadline/estimated spending safeguards stayed intact.

All 29 calls returned reconciled usage and `finish_reason=stop`. Maximum completion
was 4,485 for development and 4,891 for replacements, below the unchanged 8,192
cap. There was **no recurrent reasoning-token exhaustion, empty output, length
finish, transport uncertainty or missing usage**. Malformed partial months did
recur. Do not confuse that cross-field protocol problem with the earlier V3
empty reasoning-saturated repair. The R01 repair was unsuccessful as model repair
even though its final local clarification was correct. No token/model/retry limit
was increased. No database or transport operation was automatically retried.

There were 18 vocabulary issuance events and 14 valid returned predicates, with
no observed fabricated/modified/wrong-owner reference, accepted model SQL,
payload-isolation failure or unauthorized read. No denied-policy turn ran in this
prefix; no live authorization-denial rate is claimed. Rahtal settings, production
databases and private data were not accessed. The replacement `runner_failure`
was the safety-hook interruption, not provider transport failure.

### Corrections after the closed V5 run

The final offline SDK is
`df46aee74f313b26e4dbed0a9472ea62c602d61b56f3da120ffa42c913506f43`;
evaluator remains c4d1 above. It has **no live execution**. The bounded local
recognizer now assigns two validated named months by explicit affirmative roles,
independent of mention order. It reuses Gregorian/Jalali month operations;
negative/quoted/literal roles do not bind, missing years are not guessed and
duplicate roles require clarification. It changes no calculation, filter, metric
or grouping and does not accept arbitrary ranges/formulas.

Plain-table metadata is captured while a known date/filter detail is pending and
retained through confirmed owner/year reconstruction. A local internal flag marks
the resulting clarified-table defaults, so both agent checks and final custom-
provider validation reject an unrequested sort in that continuation. Explicit
requested sorting, existing ranked reports and non-table charts keep their roles.
There is no general prohibition on grouping, sorting or legacy host-defined
provider defaults. No public API, persistent schema, SQL, policy, adapter,
infrastructure, credential behavior, model, dependency or recovery budget changed.

Exact historical replay on saved c7a1 reproduced all 29 responses and all 15
turn outcomes with zero divergence/network. Final-source counterfactual replay
consumes all 17 development outputs, then needs a new Reviewer response for the
now-correct reversal plan. Replacement replay consumes 11/12 outputs and rejects
the added sort before the captured wrong approval; it needs a new corrected plan.
Both changed paths stop without publishing the affected report or reading its
database. No model response or improved live accuracy is invented. Controlled
valid-output regressions separately complete N04 and R02 against frozen numerical
and full specification expectations.

Seventeen new regressions fail 10/pass 7 on historical c7a1. The first implementation
applied a new ordering constraint too broadly: 14 existing tests failed on each
runtime (2,376 passed/13 skips), and clean library-example smoke failed. Its d61d
source/wheel/logs are retained. The final guard is limited to confirmed owner
continuations; existing expectations and host-defined defaults were preserved.
The focused compatibility suite then passed 261 tests. No existing test or
frozen question/reference answer was edited.

Final source passed **2,391 tests / 13 native skips** on Windows Python 3.10.22,
Windows Python 3.12.0 and Ubuntu WSL2 Python 3.12.3, with every strict/historical
semantic gate and all 14 SQLite consistency schedules. Sessions/replay, policies
and opaque references are included. Scripted legacy remains 14/14 reports and
12/12 conversations; default independent N remains 12/13 reports and 5/6
conversations, with N06 incomplete. The disabled next scope separately passes
N04 3/3 reports, development R02 1/1, and R03/R04 6/6, all offline. Clean core-only
installation imports 45 modules and runs both examples without OpenAI/ODBC/network.

One df46 Windows 3.12 full attempt had an oversized-body loopback HTTP test abort
with WinError 10053 while expecting 413 (2,390 passed/13 skips). The five isolated
body checks and a fresh complete gate passed without source, test or timeout
changes. Cause is unresolved; the failed log remains. This was not a model or
database retry and is not attributed to production or the semantic corrections.

Final verification and wheel/sdist inventory results are recorded in V7 and
`dist/phase14/completion/live-v5/package-verification.json`. SQLite remains development proof, not evidence
of native SQL Server/ODBC types, collation or snapshot isolation. All native tests
remain optional and disabled.

### Recommended next scope and Git state

The closed V5 approval rejects the changed source before credential/client/network
access (zero counters). A separate **disabled** V6 proposal at
`dist/phase14/completion/approval-scope.v6.json` binds df46/c4d1 and separates three
selections: N04 development, now-live-exposed R02 development, then live-unexecuted
R03/R04 replacements. N02 and R01 are omitted after completing their trajectories.
The original questions/oracles are unchanged; R02's historical frozen exposure
text is superseded by the new ledger rather than edited.

The proposal preserves one shared repair, one Planner revision, 8,192 completion
tokens and existing call/turn deadlines. Proposed selection ceilings are
40 calls/10 minutes/$2, 40/10/$2, 80/25/$4, totaling the same 160/45 minutes/$8
estimated safeguards and combined token ceilings. It is not approved or executed.
No historical allowance is transferable. Prioritize a real comparison of the two
new fixes and unexecuted replacements; N06's scripted incompletion, N06/A01–A12
live assessment and the old request-28 cause/bill remain outstanding. This small
exposed sample supports no statistical generalization or automatic model change.

HEAD remains `b74c10974265dcac522b3e23623e0f4f9a8ae582`, branch `main`, empty index.
Two SDK modules changed in this continuation, with focused tests and additive
evidence/docs. All prior Git changes and evaluation evidence are preserved.
No commit, push, publication, deployment or Phase 15 occurred. Proposed commit:
`fix: anchor comparison roles and preserve clarified table defaults`.

## Historical authorized V3 run (2026-10-28)

The user explicitly approved `dist/phase14/completion/approval-scope.v3.json`.
The exact ccc6/c4d1 source-bound AvalAI `gpt-5-nano` assessment made **17 real
requests / 9 turns**, then stopped at **N04 turn 1** on an incorrect accepted
specification. **4/6 attempted supported report goals completed correctly.**
N03 completed all three reports, directly exercising the fixed-period correction.
N02 still failed its continuation. N04 added an unrequested Channel grouping;
this is a substantive report-shape failure, not an equivalent-period difference.
R01–R04 were never dispatched. **Phase 14's reliability goal remains unmet.**

The live SDK was
`ccc6dae186ccb424138f8d3832a2bd8ff72d5dfe334ce991cf8178d4c56ad680`;
the evaluator remained
`c4d1db5c16ed86b30895fab07f3a7669f2b3242f730bd9c16ad274b7bec1b4ec`.
Subsequent offline corrections produced SDK
`c7a139cc15db3a7cba64cb5011aceef818f93c24089551442848be7038de0320`.
That final SDK has **no live execution**. V3 is closed; none of its unused
allowance was reused. No model, corpus, answers, retry budget or per-call limit
changed during execution. The enabled approval copies, exact starting tree,
all 17 original responses, journal, original scores and closed batch ledger remain
under `dist/phase14/completion/live-v3/`; original temporary outputs also remain.
The historical V3 scope and disabled review manifests are unchanged.

See additive [V6 evidence](../evaluations/phase14/verification.v6.json),
[causal audit V3](../evaluations/phase14/causal-audit.v3.json) and
[exposure V5](../evaluations/phase14/exposure.v5.json). All earlier evidence and
the historical sections below are retained.

### Actual first attempts and stop

| Case / turns | Observed behavior | Frozen outcome |
|---|---|---|
| N02 / 1–2 | Correct local owner question; negative `Not Channel.` correctly stalled. Neither turn used a model or database. | Correct clarification and deliberate block |
| N02 / 3 | Intent returned a month with null year. Strict decoding rejected it. The one authorized structured repair returned empty content after using all 8,192 completion tokens as reasoning. The resulting `response_size` error replaced the original period diagnostic, preventing the existing known-year fallback. | Incorrect rejection; no Planner, Reviewer or read |
| N02 / 4 | The year answer did not recover the failed owner continuation; pending clarification stalled. | Supported report incomplete; no model or read |
| N02 / 5 | Explicit fresh June Completed jobs total completed. | 1/2 reports, conversation incorrect |
| N03 / 1 | Registered Persian alias/copula resolved correctly. Local evidence removed unrequested monthly buckets from raw Intent. | Correct filtered report |
| N03 / 2–3 | Raw Intent and Planner selected equal-bounds ranges for filter removal and ranking. SDK restored the user-selected fixed month before Reviewer approval. Dates, vocabulary ownership, filters, groups, ranking, receipts and all independent report checks passed. | 3/3 reports, complete correct conversation |
| N04 / 1 | Intent invented `channel` as an output dimension from `Channel = Counter`. Planner retained it and Reviewer approved. Positive-only grouping evidence did not prohibit the additional dimension, so final local validation also accepted it. | Wrong fields/types/rows and specification; immediate batch stop |
| N04 / 2–3, R01–R04 | Not dispatched after the stop. | 15/24 planned turns unexecuted; no live score |

Five reports were published; four met every report check. N04 requested one Billed
amount total, with fields `[billed]` and expected row `280`. The extra Channel
field/group makes the published report wrong even though the filtered amount was
still 280. The date bounds, metric, filter and other selections were correct.
The raw `extraction_failure` origin correctly identifies the first grouping error;
Planner, Reviewer and deterministic validation all subsequently failed to stop it.
This failure was not a database authorization violation.

One of three attempted conversations succeeded, including the partial N04 in
that denominator. Among the two fully executed conversations, one succeeded.
Exact report-requirement satisfaction was **64/78**. Clarification precision was
**1/1 emitted**, but recall was only **1/2 expected**: the missing-year question
was never delivered. Reviewer approved four correct candidates and one incorrect
grouped candidate; no candidate was rejected by Reviewer. There were no Planner
revisions or Intent reconsiderations. The one structured repair failed to produce
usable content. Failure isolation remains insufficient for a broad quality claim.

The raw stage scores are retained: decoded Intent 2/7, effective Intent 4/5,
proposal 2/5. These are strict frozen diagnostics before defaults/canonicalization,
not five distinct language-understanding errors: two raw N03 range proposals were
correctly canonicalized before review, and nullable raw defaults can fail those
diagnostics. The confirmed semantic interpretation error was N04's extra grouping;
N02 failed cross-field decoding and then output completeness.

### Correction effectiveness and comparison limits

N03's fixed-period correction was **exercised live twice**: the recorded model
ranges became exactly equal user-requested typed months, and all final frozen
checks passed. In V2, N03 turn 2 had failed that typed contract; its third turn
was unexecuted. No expected answer was weakened. Explicit-range and unequal-range
negative controls remain offline coverage, not additional authorized live cases.

N02's confirmed-answer role correction was not reached on turn 3 because model
decoding failed first. Its 1/2 completion on ccc6 does not establish improvement
over the 8e3c conversation's 1/2: the first failing boundary changed from a wrong
measure question to malformed/empty model output. N04 comparison and reversal
turns remain live-unexecuted in V3. R01–R04 have no live denominator. V2's 4/6 and
V3's 4/6 cover different prefixes; they are not a pooled or causal improvement
rate. These cases have development/offline exposure and are not externally blind.

### Usage, latency and boundaries

There were **7 Intent / 5 Planner / 5 Reviewer** calls. All 17 had reconciled
usage; 16 ended with `stop`, one with `length` and no visible content. Summed
usage was **74,601 input / 49,876 completion tokens** (124,477 total). Cached
input 46,464 is part of input; reasoning 48,000 is part of completion. Independent
published-rate estimation is **$0.02368045**, with no cache discount. Actual
provider billing remains unknown. This was an explicit exploratory estimate,
not a guaranteed billing cap or a transport/usage-uncertainty stop.

Stage latency totaled 180,293.202 ms for Intent, 106,201.461 ms for Planner and
51,191.629 ms for Reviewer. Summed turn latency was 338,581.068 ms; controller
elapsed time was 349.594 seconds. Five bounded synthetic reads totaled 238.547 ms.
All approved request/token/time/estimated spending limits remained intact.

Observed unauthorized reads, accepted model SQL and payload-isolation failures
were zero. Eleven vocabulary issuance events yielded five valid returned
predicates, with no fabricated, modified or wrong-owner reference. The one
malformed-JSON protocol event came from the empty repair. No denied-policy turn
was executed, so no live authorization-denial rate is claimed. Rahtal settings,
production databases and private data were not accessed. There were no automatic
transport/database retries or subsequent live calls after the safety stop.

### Targeted offline corrections after V3

For a locally confirmed clarification answer whose remaining missing detail is
the year, an invalid model period now reaches the existing known-year fallback
before structured repair can replace its diagnostic. The first malformed period
is rejected, the correct year question is asked and no date is invented. Valid
Intent still follows its existing Planner/Reviewer path. Empty/transport failures
and unrelated malformed responses do not gain this fallback. No retry allowance
or default changed.

For a fresh dated plain table with an explicit metric and whole/entire-period
total wording, no requested business groups and no grouping/ranking cue, local
evidence excludes added output dimensions. Existing Intent anchoring and final
provider-neutral evidence checks enforce it; a filter owner remains a filter.
Requested `by`/`for each` groups, current grouped reports, quoted predicate values,
negation and unresolved grouping cues retain their roles. No join, formula,
catalog, policy, SQL, schema, API or production connection behavior changed.

Historical replay on the saved ccc6 tree reproduced all 17 responses and nine
turn outcomes without divergence or network. Final-source counterfactual replay
uses N02's original first invalid response and asks the year without consuming
the empty repair. N04 consumes its original Intent and wrong Planner response,
rejects the extra grouping and requests an unavailable corrected plan; it stops
without review or database access. The captured approval is unused. **That replay
does not claim a completed report or new model judgment.** Controlled valid-output
tests separately complete all three frozen N04 comparison turns numerically.

The final 14 new regressions fail 8/pass 6 on the historical source and pass on
the corrected source. Initial new-test fixture mistakes were corrected and their
logs retained. An intermediate pre-model year question broke one existing shared
response-stream compatibility test on each runtime (2,373 passed/13 skips). That
approach and its d907 source/wheel/logs were retained and rejected; valid call
sequencing is preserved by the final fallback change. No existing tests or
reference expectations were changed.

All three final runtimes passed **2,374 tests / 13 optional native skips**:
Windows Python 3.10.22, Windows Python 3.12.0 and Ubuntu WSL2 Python 3.12.3.
Details are in V6 and `dist/phase14/completion/live-v3/`: strict and historical
semantic gates, all 14 SQLite schedules, persistent sessions/replay, policies and
references. Scripted legacy remains 14/14 reports and 12/12 conversations; default
independent N remains 12/13 reports and 5/6 conversations, with N06 incomplete.
The final one-repair proposal separately passes N02/N04 5/5 reports and 2/2
conversations, and R01–R04 9/9 and 4/4. These are offline scores.
Clean core-only installation
imports 45 modules and runs both synthetic examples without OpenAI/ODBC/network.
Native SQL Server stays gated; SQLite supplies no native type, ODBC, collation
or SQL Server snapshot guarantee. Final wheel/sdist verification is recorded in
`dist/phase14/completion/live-v3/package-verification.json`.

### Next assessment and Git state

The changed source rejects the closed V3 approval before credential/client/network
access (zero counters). A separate disabled final proposal,
`dist/phase14/completion/approval-scope.v5.json`, binds c7a1/c4d1 and proposes
N02/N04, then R01–R04 with separate scores and fresh outputs. It omits completed
N01/N03 development trajectories. It retains the existing shared repair, deadlines,
token limits and 160-request / 45-minute / $8 estimated safeguards. The intermediate
disabled V4 draft is preserved but superseded following compatibility correction.
Preparation is not execution authorization; no further calls were dispatched.

The next priority is real verification of the known-year fallback and rejection
of added grouping, followed by a separate replacement result. N04's live comparison
reliability, all replacement performance, N06 and A01–A12 remain unverified;
N06 also retains its scripted incompletion. The old request-28 transport cause
and final bills remain unknown. This evidence does not establish that changing
the model or token cap would fix these failures; either experiment needs its own
explicit scope. Phase 15 has not begun.

HEAD remains `b74c10974265dcac522b3e23623e0f4f9a8ae582`, branch `main`, empty index.
All prior working changes, frozen questions/oracles and previous JSON evidence
are preserved. This execution changed only two SDK modules, added focused tests
and additive evidence, and updated documentation. No commit, push, publish or
deployment occurred. Proposed commit:
`fix: preserve year clarification and reject unrequested report grouping`.

## Historical authorized V2 run (2026-10-28)

The user explicitly approved the exact
`dist/phase14/completion/approval-scope.v2.json`. The real AvalAI `gpt-5-nano`
pipeline executed **20 requests / 10 turns** on synthetic SQLite and then stopped
the entire batch at N03 turn 2 under its frozen incorrect-specification rule.
**4/6 attempted supported report goals met the complete frozen contract.** Five
reports were published and all five had independently correct numerical rows and
date bounds. One retained the right dates as `range` where the frozen contract
required `month`; this strict typed mismatch remains a failure in the original
results. It is not evidence of incorrect business totals.

N01 completed all three turns correctly. N02 completed all five turns but lost
the clarification context on turns 3–4. N03 completed two of three turns before
the stop. Thus **1/2 fully executed conversations succeeded**, with one additional
partial conversation; the raw runner's 1/3 includes that partial denominator.
N03 turn 3, N04's three turns and all 13 replacement turns were unexecuted:
**17/27 planned turns**. They receive no live success or failure credit. There
were no further dispatches, automatic repeats or use of the unused allowance.

The source tested live was
`8e3c03564c4169c521531713aec01c86293ca2f0063f43a0e03d260eb13159b2`,
with evaluator
`c4d1db5c16ed86b30895fab07f3a7669f2b3242f730bd9c16ad274b7bec1b4ec`.
The later corrected SDK is
`ccc6dae186ccb424138f8d3832a2bd8ff72d5dfe334ce991cf8178d4c56ad680`.
**The later SDK has offline verification only.** Results from different sources
are not pooled into an improvement rate. The exposed development prefix is not
a blind independent quality assessment.

Additive [V5 evidence](../evaluations/phase14/verification.v5.json),
[per-turn causal audit](../evaluations/phase14/causal-audit.v2.json) and
[exposure ledger](../evaluations/phase14/exposure.v4.json) retain these distinctions.
The exact starting tree, enabled approval copies, all 20 captured responses,
journal, results and closed batch ledger remain under
`dist/phase14/completion/live/`. The original temporary output is also retained.
The disabled V2 review packets and approved scope are byte-preserved.

### What the model actually did

| Case / turns | Actual first-attempt behavior | Complete-contract result |
|---|---|---|
| N01 / 1–3 | Initial null-year month was invalid; the one shared structured repair returned a valid missing-period Intent. Planner asked the year, then completed the Units/Department report and the ungrouped Net sales refinement. No duplicate metric or unjustified limit was accepted. | 2/2 reports; 1/1 conversation |
| N02 / 1–2 | Asked the correct filter-owner question locally; the negative answer `Not Channel.` correctly stalled without a model call or read. | Correct clarification and deliberate block |
| N02 / 3–4 | Correct owner/reference and metric were extracted, but Intent labeled the answer `new`. The local explicit-measure guard then inspected only the latest answer and asked for a measure instead of the missing year. The next year answer did not recover the report. | Wrong clarification, then incomplete supported report; zero reads |
| N02 / 5 | Explicit fresh June Completed jobs total completed correctly. | 1/2 reports over this conversation |
| N03 / 1 | Persian registered alias and attached copula resolved to the correct opaque reference; fixed-month filtered report completed. | Correct report |
| N03 / 2 | Filter removal preserved measure, grouping and exact September bounds. Intent and Planner selected `range`; Reviewer approved. The strict frozen specification expected `month`. Every row/type/field/presentation/receipt/isolation check passed. | Typed specification failure; immediate batch stop |
| N03 / 3, N04, R01–R04 | Not dispatched after the stop. | Unexecuted |

The raw scorer records one incorrect accepted specification and one wrong
Reviewer approval. Those classifications are preserved. The causal audit shows
an upstream context representation issue: the existing session contract freezes
Gregorian periods to absolute ranges before supplying `current_spec` to providers.
The Reviewer approved an equivalent range, not a different date interval. The
scorer's `review_failure` label alone does not establish that the Reviewer changed
or misread the business dates. No frozen answer was relaxed to remove this failure.

### Measured usage, recovery and safety

There were **8 Intent / 6 Planner / 6 Reviewer** calls, all with usable usage and
`finish_reason=stop`. Recorded usage totals **87,129 input / 47,189 completion
tokens** (134,318 total). Cached input 61,056 is a subset of input; reasoning
44,928 is a subset of completion, neither is added again. Independently summed
published-rate estimates are **$0.02323205**, without a cache discount. Provider
billing remains unknown; this is exploratory accounting, not a guaranteed bill.
The 160-request / 45-minute / $8 estimated stops were not approached.

Intent latency totaled 143,358.553 ms, Planner 129,936.225 ms and Reviewer
58,422.919 ms. Summed turn latency was 333,290.782 ms; controller elapsed time
was 340.14 seconds. Five synthetic reads totaled 641.159 ms. The existing one
shared structured repair was used once (N01 turn 1); there were no Planner
revisions, Intent reconsiderations, transport retries or database retries.
There were two correct clarifications out of three expected, and two correct
out of four emitted. The negative-owner block was correct.

No unauthorized reads, accepted model SQL, payload-isolation failures, fabricated
references, wrong-owner references or usage-uncertain calls were observed.
Seven reference issuance events yielded three valid returned predicates.
No denied-policy turn was executed in this prefix, so it supplies no live
authorization-denial rate. Synthetic-only results do not prove production safety,
SQL Server native types, ODBC behavior, collation or native snapshot isolation.
Rahtal settings and production databases were not accessed. The batch's
`runner_failure` is the safety-hook interruption, not a transport failure.

### Corrections after the stop, verified offline

The confirmed pending-answer role now overrides a model's `new` tag only when
local evidence has actually resolved a previously pending slot. Negative,
conflicting and unknown owner choices remain unresolved; an explicit new-report
reset still starts a new report. This retains the original explicit measure and
other requirements through an affirmative owner/year continuation.

A separate local canonicalization keeps a user-selected fixed Gregorian or Jalali
month/year when the model supplies an exactly equal date range. It applies before
Reviewer review and again at the provider-neutral engine boundary. It changes
only the representation, never dates, filters, grouping, limits or metrics.
For an inherited frozen range it requires the most recent explicit selection in
bounded user history and matching effective dates. Later relative/ambiguous date
instructions stop that recovery; assistant prose supplies no dates. Missing or
truncated supporting history does not justify canonicalization. Explicit user
ranges remain ranges and unequal ranges still fail ordinary evidence validation.

An intermediate attempt to retain fixed Gregorian periods in provider session
context broke five existing compatibility tests on each runtime. That approach
was rejected, with its source/wheel/logs retained. The final change preserves the
existing range-freezing contract, including relative dates across business-clock
changes. No existing tests, expected answers, public schema, adapter, policy,
database/session format, dependency, retry budget or production behavior changed.

Exact historical replay against the saved 8e3c source consumed all 20 unchanged
responses and reproduced every outcome with no divergence and no network.
Final-source N03 replay consumed six unchanged captured outputs and produced two
strictly correct reports. This is a **counterfactual offline replay**: the later
Reviewer payload changes, so the captured approval is not new model judgment.
The N02 full continuation is verified using controlled scripted responses, not
invented model responses or a claimed live success.

All three final environments passed **2,360 tests / 13 optional native SQL Server
skips**: Windows Python 3.10.22, Windows Python 3.12.0 and Ubuntu WSL2 Python 3.12.3.
Every strict/historical semantic gate and all 14 SQLite consistency schedules
passed with their documented retained incompletions. Scripted legacy remains
14/14 reports and 12/12 conversations; default independent N remains 12/13 reports
and 5/6 conversations, with N06 incomplete. New one-repair scripted checks pass
N02–N04 8/8 reports and 3/3 conversations; separately R01–R04 9/9 and 4/4. These
are offline scores. Fourteen focused regressions cover the two new causes and
negative/relative/range controls. Clean core-only installation imports 45 modules
and runs both examples without OpenAI, ODBC or network. Final package/inventory
verification is recorded in `dist/phase14/completion/live/package-verification.json`.

### Remaining work and next exact proposal

The approved V2 batch is closed. The changed source rejects its old approval
before credential access, client construction or network (all counters zero).
A separate **disabled** proposal, `dist/phase14/completion/approval-scope.v3.json`,
binds ccc6/c4d1, N02–N04 then R01–R04 with separate scores and fresh directories.
It omits the now-completed N01 development conversation. It retains one shared
repair, one Planner revision, no retries, the same per-call limits and combined
160-request / 45-minute / $8 estimated safeguards. Disabled preflight counters
are all zero. It is preparation only; no dispatch or reuse of the prior allowance
is authorized. Another live comparison would require its own exact approval.

Real completion after the new fixes, N03's remaining ranking turn, N04 comparisons
on this source and all replacements remain unverified live. N06 is still
scripted-incomplete; N05's prior missing-usage transport cause/bill remains unknown;
N06 and A01–A12 remain live-unexecuted. Prioritize those measured completion gaps
and a separate replacement score before any broad quality claim. This limited run
does not establish that changing models would resolve them.

HEAD remains `b74c10974265dcac522b3e23623e0f4f9a8ae582`, branch `main`, with an
empty index and the prior working changes preserved. Only three SDK modules were
changed after this live run, plus focused tests and additive evidence/docs.
No production access, native integration enablement, commit, push, deployment or
Phase 15 occurred. Proposed commit message:
`fix: preserve typed periods and confirmed clarification context`.

## Historical preparation for the V2 scope (2026-10-28)

The starting SDK was `c60b35c5…`, with 2,323 passing offline tests. Its real-model
predecessor `d1f48054…` completed only 1/11 attempted reports and 0/4 complete
conversations before request 28 failed. **Those live results have not improved
by measurement:** this continuation authorized offline engineering and preparation,
with a new exact approval required before any external model dispatch.

The complete per-turn audit is [`causal-audit.v1.json`](../evaluations/phase14/causal-audit.v1.json).
It records each original requirement, frozen expected result/specification, actual
Intent/Planner/Reviewer outputs, safe errors, database activity and first failure
boundary for all 15 executed turns. Every captured first output and historical
classification remains unchanged. N06 and A01–A12 remain live-unexecuted.

### Confirmed causes and bounded corrections

| Failure class | Confirmed boundary | Resulting correction / limit |
|---|---|---|
| N01 duplicate metric | Strict Planner specification decoding | Reject original candidate; opted-in existing repair now receives fixed validation feedback, then the replacement must pass all checks |
| N01 repeated limit 1 | Nullable extracted limit left the known default implicit | A fresh plain table with unspecified limit carries 100 in effective Intent; candidates are still rejected if they disagree |
| N02 owner plus repeated literal | Existing local choice grammar | Previous repair retained and tested, including negative/conflicting/unknown choices, other missing details and reopen |
| N03 Persian copula | Local whole-alias boundary | Previous exact alias/canonical/quoted-literal protections retained; malformed periods remain a separate failure |
| N03/N04 fixed month with rolling unit | Schema permits cross-field combinations rejected by semantic checks | Existing single opt-in repair receives period/field diagnostics; no fields or dates are silently changed |
| N04 “compare that total with June” | Local evidence replaced the current base with the new reference month | Bounded affirmative current-report references preserve the current base and select the explicit new comparison; no current report asks for its base |
| N04 “same Channel restriction” | Explicit retained filter was not recognized | Preserve the current registered filter through that bounded retention wording; policies remain independently checked |
| N03 exhaustion labeled transport | Evaluator diagnosis grouped all failed statuses together | New diagnostics distinguish exhausted agent recovery, provider transport and deadlines; old scored files are untouched |
| N05 request 28 | No recorded response/usage or specific HTTP error | Cause remains unknown; future typed SDK exceptions expose only fixed timeout/connection/rate-limit/server/client categories |

The new SDK is
`8e3c03564c4169c521531713aec01c86293ca2f0063f43a0e03d260eb13159b2`.
The new evaluator is
`c4d1db5c16ed86b30895fab07f3a7669f2b3242f730bd9c16ad274b7bec1b4ec`.
Neither has live verification. N01's recorded first Intent in the 28-call run
was a valid null period plus missing period/year; Planner asked the year and
Reviewer approved. That live observation did not exercise the earlier rejected
partial-month fallback and does not isolate a causal improvement from model variance.

The existing `max_structured_repairs=1` option still has one allowance shared by
Intent, Planner and Reviewer. Its default remains zero. Planning/review revisions
remain bounded at the existing default one. Intent repair uses the existing
reconsider method with fixed allowlisted diagnostics; Planner repair retains its
existing feedback and adds a fixed diagnostic. No rejected values, raw exception
text or responses enter that feedback. Reviewer repair keeps the same checked
candidate. Transport/empty output, authorization and database execution are not
retried. Repeated malformed or semantically wrong proposals still fail closed.

The Planner schema bounds arrays but does not enforce selected-ID uniqueness or
period-kind field relationships; those remain strict SDK checks. Why a model chose
a duplicate or repeated limit is not knowable from outputs alone. Making the
known default explicit and supplying validation feedback addresses the demonstrated
information gap; its effect on actual model completion still needs live measurement.

Future transport categories use already-loaded optional SDK exception classes,
without importing/initializing an SDK on an unrelated injected failure. They
never expose URLs, headers, bodies, request IDs or exception text. These are
coarse categories consistent with [official OpenAI error documentation](https://developers.openai.com/api/docs/guides/error-codes),
not a retrospective diagnosis of request 28. Accounting still stops on missing
usage or transport uncertainty and retains its reservation.

### Reproduction, compatibility and remaining limitations

Historical replay loaded the exact saved d1f48054 SDK/evaluator tree outside the
checkout and reproduced all 27 recorded outputs and every turn outcome, with
network blocked. Current-source replay of the N01 prefix consumes five captured
responses, rejects the malformed plan, then stops when repair requests an
unavailable response. No corrected response or live success is fabricated.

Controlled valid-replacement tests verify SQLite numerical rows, strict rejection,
finite repair, session receipt replay, period anchoring and negative/literal
comparison controls. The first focused reproduction failed seven tests and
passed two before fixes. The later focused suite passed 301 tests. An intermediate
Windows 3.12 full run had two provider-failure baseline failures while Windows
3.10/Linux passed; its isolated rerun passed. A cold optional-SDK import was found
on the diagnostic path (3.621-second standalone failure scenario). The final
handler removes that unnecessary initialization and has a guard test. Deadline
interference under concurrent load is suspected, not a proven explanation of the
intermediate failures. That source, failed log and superseded disabled V1 packet
are preserved separately.

Final release results, all runtime/source identities and remaining scripted
incompletions are recorded in additive [`verification.v4.json`](../evaluations/phase14/verification.v4.json).
All three final environments passed **2,346 tests / 13 optional native skips**:
Windows Python 3.10.22, Windows Python 3.12.0 and Ubuntu WSL2 Python 3.12.3.
Every previous strict/historical semantic gate and all 14 SQLite consistency
schedules passed in each. Frozen N01–N06 with default repair still reports one
incomplete trajectory, N06: **12/13 reports, 5/6 conversations**. This is offline
evidence, not a success/failure rate for the live-unexecuted N06. Scripted legacy
remains **14/14 reports, 12/12 conversations**. At the proposed one-repair setting,
N01–N04 passes **10/10 reports, 4/4 conversations**, and R01–R04 separately passes
**9/9 reports, 4/4 conversations**. The 23 new focused regressions include a guard
against optional-SDK initialization during error classification. Final clean-core
installation imports all 45 modules and runs both examples without OpenAI/ODBC.
The clean core-only install and final wheel/sdist checks are in
`dist/phase14/completion/`. Native SQL Server remains disabled; SQLite establishes
no native SQL Server/ODBC/isolation guarantees. No API, catalog, policy, adapter,
database/session schema, dependency or production connection design changed.
Public error reasons gain only five fixed transport categories.

### New exact targeted approval packet

Prepared **disabled** `dist/phase14/completion/approval-scope.v2.json` using the
existing approval infrastructure. V1 is retained and superseded after the cold-import
correction. V2 binds the final SDK/evaluator above, exact frozen hashes and fresh
output directories. Provider/model remain AvalAI / `https://api.avalai.ir/v1` /
`gpt-5-nano`, explicit exploratory accounting, one shared structured repair and
one Planner revision. Original N/A questions/answers are unchanged.

| Selection | Cases | Turns | Report goals | Ceilings |
|---|---|---:|---:|---|
| Development regressions | N01–N04, original v2 | 14 | 10 | 80 requests / 1,350 s / $4 estimated |
| Replacements, separate score | R01–R04, v3 | 13 | 9 | 80 requests / 1,350 s / $4 estimated |

Combined: **160 requests / 2,700 seconds / $8 estimated spending stop**, 3,000,000
input / 1,310,720 completion / 4,310,720 total tokens. Per call: 8,192 completion
tokens / 120-second timeout; SDK turn deadline 240 seconds. These are finite
ceilings, not targets or billing guarantees. Published-rate estimates retain
unverified framing/billing and full input pricing. No earlier allowance is reused.

Half the cases and nearly half the turns are replacement trajectories. R v3 changes
only eligibility/exposure metadata for review, retaining all v2 questions and
expected answers. V1/v2 remain live-ineligible and preserved. V3 eligibility does
not authorize dispatch. These replacements have offline exposure and familiar
authors/fixtures; no blind-generalization claim is made. Both disabled selections
were rejected before credential reads, environment-file reads, client construction,
network dispatch or output-directory creation. Approval records and source hashes
must match exactly before execution. No credentials were read for this task.

The proposed batch stops on wrong accepted reports, security violations or
transport/usage uncertainty and never repeats a failed live case automatically.
N06 and A01–A12 are outside this targeted scope and retain future live eligibility.
The remaining priority is actual full-trajectory completion on the new source,
then separately approved broader/stronger-model assessment if warranted. No Phase
15, commit, push or deployment occurred. Original Git changes and prior evidence
remain intact; the index is empty.

Proposed commit: `fix: improve bounded report recovery and comparison context`.

## Earlier corrected-source live continuation — preserved account

## Current continuation result (2026-10-27/28)

**Partial real-model evidence: conversation reliability remains insufficient.**
The separately authorized corrected-source run dispatched 28 AvalAI `gpt-5-nano`
requests. Request 28 failed at the transport boundary without a response/usage
record; the existing exploratory accounting guard stopped further dispatch.
There was no automatic retry. N05's revocation turn, N06 and all A01–A12 remained
unexecuted. This was an accounting stop, not another wrong-report safety stop.

The 15 executed turns contained **1/11 completed supported reports**, **zero wrong
accepted specifications**, and zero observed unauthorized reads or payload
isolation failures. Four complete conversations all failed at least one goal;
N05 was partial. The one published report matched its independent specification,
fields, numerical rows, date bounds, policies and saved-report/receipt checks.
Its success required the already configured bounded Planner revision. These
small denominators do not establish production readiness or authorization-denial
coverage. The earlier wrong annual report remains a separate preserved failure.

New additive evidence is [`verification.v3.json`](../evaluations/phase14/verification.v3.json).
V1 readiness, V2 first live failure, original approval packets, all frozen N/A
questions and expected answers, journals and visible first responses are intact.
Sections 1–16 below retain the earlier assessment's historical account.

### Exact authorized source and execution boundary

Live SDK: `d1f480543ec32c4552422b1f606b22e3319b7230f0620b5e507b235f2b87da75`.
Evaluator: `973c4317db37581949ac47523174b84d84030e20bfd6cab5d7e29b43e902cb08`.
The fresh packet `dist/phase14/approval-scope.corrected.v1.json` bound these digests,
the unchanged selection/corpus/freeze hashes, exact endpoint/model, exploratory
accounting and fresh temporary output directories. Original packets were not
edited. Per selection: 120 requests, 1,800 seconds, $5 estimated stop, 2,000,000
input / 983,040 completion / 2,983,040 total tokens, 8,192 completion tokens per
call, 120-second call and 240-second SDK deadlines. Combined ceilings retained
240 requests / 3,600 seconds / $10 estimates and both selections' token sums.

N01 ran first, then unchanged N02–N05. N01's safe failures did not meet the
wrong-accepted/security stop condition. The transport/accounting stop prevented
Stage C entirely. Batch elapsed: **547.656 seconds**. Captures, journal, approvals,
starting tree and the closed batch ledger are under `dist/phase14/continuation/`.
No additional live experiment or execution on the subsequently changed SDK ran.

### Separate populations and actual first outcomes

| Population/case | Turns executed/planned | Supported reports complete/attempted | Actual observations |
|---|---:|---:|---|
| N01, development regression | 3/3 | 0/2 | Correct year question; year answer retains Units/Department/September 2026; malformed duplicate-metric plan blocked; replacement report's invented limit 1 blocked twice |
| N02, assessment prefix | 5/5 | 1/2 | Correct filter-owner question; negative owner blocked; affirmative owner answer stalls locally; year remains stalled; explicit new June jobs total succeeds after limit correction |
| N03, assessment prefix | 3/3 | 0/3 | First Intent has invalid month `unit` and unresolved Persian value suffix; later refinements lack rolled-back original context; unnecessary clarifications and Reviewer exhaustion |
| N04, assessment prefix | 3/3 | 0/3 | Two invalid period structures; later comparison refinement asks for clarification instead of reporting |
| N05, partial assessment | 1/2 | 0/1 | Intent completed; Planner transport failed; revocation/override turn unexecuted |
| N06 | 0/3 | unmeasured | No dispatch |
| A01–A12, legacy | 0/21 | unmeasured | No dispatch; separate legacy output directory absent |

N01 is exposed development evidence, not independent generalization. Separately,
the N02–N05 prefix completed **1/9** attempted report goals and **0/3** complete
conversations, plus one incomplete conversation. Across N01 and that prefix,
two of three expected clarification goals were correct; two other clarifications
were unnecessary. Clarification precision was **2/4**, recall **2/3**. Recovery completed **1/4**
turns with a revision. No structured repair/reconsideration loop was enabled.
There are **25 unexecuted turns** across the original 40-turn scope.

### First loss of meaning and Reviewer observations

N01's missing-year/context repair worked as far as clarification, reopened
conversation and the decoded Units/Department/September selection. Local evidence
also corrected an invented monthly time grain. The next Planner returned
`metric_ids=[units, units]` and limit 1; strict decoding rejected the duplicate
before review/read. The following explicit ungrouped Net sales request repeatedly
received limit 1 instead of the required default 100. Deterministic evidence
rejected it. Thus context retention improved, but report completion did not.

N02 first lost progress in deterministic clarification management, before model
dispatch: the affirmative choice grammar accepted a bare owner but not the owner
repeated with its pending literal ("Use the Channel filter for Portal"). A known
year was consequently unable to advance the still-pending owner question.
The independent new-report reset worked. Its first Planner candidate had limit 1;
the existing semantic revision produced limit 100 and the correct report.

N03/N04 first failed in Intent protocol structure: a fixed month had `unit=month`,
which is valid only for a rolling window. Those rejected requests correctly
rolled back session state. Later short refinements therefore lacked the original
failed request; this is not evidence of saved-report corruption. N03 also exposed
a local parsing defect: unquoted "تاریخی باشد" included the copula in the value,
so it did not bind the host's registered "تاریخی" alias. N03's last turn exhausted
the bounded agent revisions. The generic scorer labels that operational failure
as transport-related; its actual safe error is `agent_exhausted`, distinct from
N05's real `provider_failed` / planning / transport failure. The exact HTTP cause
of request 28 was not retained and cannot be established from these records.

Reviewer evaluated six candidates: **3/4 incorrect candidates rejected**, **1/4
incorrect candidates approved**, **2/2 correct candidates approved**, **0/2 false
rejections**. Its wrong approval was an unnecessary period clarification in N03,
not a ready report. The payload replay confirms that upstream rejection had
removed the original request from this later context. Reviewer is not credited
with seeing information it did not receive. No incorrect ready report reached
publication. Stage counters comparing nullable extraction fields with complete
specification defaults must not be read as a blanket zero-percent Intent score.

Opaque references had two observed issuance/use events, with **2/2 valid returned
predicate uses** and no observed fabricated/modified/wrong-owner reference. This
is narrow Channel-filter evidence; Persian alias completion and adversarial
reference handling are not established by it. No denied reporting turn ran, so
authorization-prevention accuracy has denominator zero.

### Usage, latency and uncertainty

| Stage | Requests | Responses with usage | Input tokens | Completion tokens | Stage latency |
|---|---:|---:|---:|---:|---:|
| Intent | 11 | 11 | 48,082 | 47,523 | 285.562 s |
| Planner | 11 | 10 | 45,182 | 19,358 | 194.747 s |
| Reviewer | 6 | 6 | 20,294 | 9,994 | 59.252 s |
| Total | **28** | **27** | **113,558** | **76,875** | **539.560 s** |

All 27 recorded responses report `stop`. Reasoning tokens **73,664** are a subset
of completion, and cached input **79,616** a subset of input; neither is added
twice. Independently summing captured usage at the observed
[AvalAI prices](https://docs.avalai.org/en/models/gpt-5-nano), using full input rates
without a cache discount, gives **$0.03642790**. The failed call retains a
26,469-input / 8,192-completion reservation estimated at **$0.00460025**. The closed
ledger therefore records **$0.04102815 charged-or-reserved estimate**, with one
uncertain request. Actual billed USD is unknown. No estimate is a billing cap.

The failed Planner call lasted 64.944 seconds; it was not retried. Total measured
SQLite execution was 437.155 ms, one synthetic SELECT. N01 submission latencies
were 35.764 / 34.626 / 42.461 seconds. The measured work was model-dominated;
no controlled performance comparison or native SQL Server result is claimed.

### Targeted subsequent offline corrections

Exact captured-response replay consumed all 27 recorded visible responses and
reproduced every recorded turn outcome on the live-tested source, with sockets
blocked. At request 28 it explicitly records absence of a response; no success
or response was fabricated. Replay artifacts retain permitted synthetic payloads
for context inspection and never contain request headers or credentials.

Only two SDK modules changed after that baseline. An ungrouped total would return
one aggregate row with either limit 1 or 100; the existing frozen contract still
requires the default 100 when no output count was requested. Its oracle was not
relaxed to turn the observed default mismatch into a successful report.

- Grounding now recognizes an affirmative pending filter owner repeated with the
  **same** pending literal. It reuses existing polarity/ambiguity checks; questions,
  negative/conflicting/unknown owners, changed values and quoted examples do not
  resolve that pending selection. Other missing details and exclusions survive.
- Unquoted terminal Persian copulas can be removed only when the remaining whole
  phrase matches exactly one registered alias. Full registered phrases and quoted
  or unregistered free-form values keep their exact literal meaning.
- Shared prompt instructions explicitly require kind-specific period fields,
  unique selected IDs and default limit 100 for an ungrouped total. These are
  instructions, not new validation guarantees. Malformed captured structures
  still fail before Reviewer/database access. No new recovery loop was added.

Post-baseline SDK:
`c60b35c5d381ae5624a78e5d710d7c2ffcbb4a1c01175f45867a7303311affac`.
The evaluator remains unchanged. Public APIs, adapters, production configuration,
authorization and SQL validation are unchanged. There was no additional live run
on this source. Fresh exact authorization would be necessary for such a run.

The new continuation suite has 24 focused tests; the pre-fix reproduction had
9 failures / 10 passes. One preliminary test incorrectly expected raw Portal
instead of the host's canonical Web; that new test was corrected against the
existing host definition. Frozen N/A expectations were never changed. The final
focused conversation/vocabulary suite passed 317 tests before adding the two
malformed-output guards, which are included in the full suite.

Four replacement trajectories R01–R04 were separately frozen with different
wording/report requirements over existing synthetic hosts. They are live-ineligible
and have no execution authorization. V1 and its first result retain an author
error: R02 expected an obsolete generic error code for the negative answer.
V2 documents that metadata correction and adds the N04 period replacement;
all V1 questions/report answers remain intact. Offline V1 completed 6/6 reports
and 2/3 conversations; V2 completed **9/9 reports and 4/4 conversations**. These are
scripted contracts over familiar fixtures, not real-model or externally blind
generalization measurements. See `evaluations/phase14_replacements/` and the
additive [exposure ledger](../evaluations/phase14/exposure.v2.json).

### Final verification and remaining work

The complete offline release gates passed on Windows Python 3.10.22,
Windows Python 3.12.0 and Ubuntu WSL2 Python 3.12.3: **2,323 tests / 13 native
skips in each runtime**, all previous semantic gates and 14/14 SQLite consistency
schedules in each runtime. Exact commands, source hashes and timings are recorded
in V3 evidence. A clean core-only Python 3.10 wheel install imports all 45 modules
and runs both synthetic examples without OpenAI, ODBC or pytest installed.
Final wheel/sdist inventory and build checks are recorded in
`dist/phase14/continuation/package-verification.json`. Native SQL Server remains
separately disabled. Frozen scripted A01–A12 retained
14/14 supported reports and 12/12 conversations. Scripted N01–N06 improved from
9/13 reports and 2/6 conversations to **11/13 and 4/6**, with N04/N06 still incomplete.
Those offline gaps are retained, not counted as successful reports.

Before a readiness claim, complete a newly scoped live assessment on an exact
source, address remaining comparison/ranking and conversational failures, and
assess a more capable model under its own controlled scope if desired. The
current evidence does not compare models or establish prompt-fix efficacy live.
Keep authorization-denial/reference attacks, provider failure behavior and full
conversation completion visible in that assessment. Never recycle either closed
batch's remaining allowance. Phase 15 has not begun.

All work used synthetic SQLite. No Rahtal `.env`, production database, private
business records, SQL Server native suite, commit, push or deployment was used.
SQLite cannot verify SQL Server dialect/native types, ODBC binding/Unicode,
collation, TLS/permissions, native SNAPSHOT/RCSI concurrency or production workloads.

Proposed commit: `fix: resolve explicit clarification owners and registered Persian value suffixes`.

## Historical first assessment — original scope (sections 1–16)

## 1. Verified starting baseline

Started from `main`, HEAD `b74c10974265dcac522b3e23623e0f4f9a8ae582`, empty index,
with all earlier uncommitted work preserved. Before dispatch, copied/hashed the
nonignored tree under `dist/phase14/live/starting/`. Phase 13's four attempts and
Phase 14's readiness evidence remain unchanged. The historical readiness record is
[`verification.v1.json`](../evaluations/phase14/verification.v1.json).

Baseline SDK: `e64e611ad9434d11059745d806a02dbb4be00607c1daa82c3bbf06946de0dbe2`;
baseline evaluator: `973c4317db37581949ac47523174b84d84030e20bfd6cab5d7e29b43e902cb08`.
The pre-live offline suite passed 2,272 tests with 13 separately gated native skips.

## 2. Approved scope and actual achieved level

The user explicitly approved `dist/phase14/approval-scope.v1.json`: AvalAI,
`https://api.avalai.ir/v1`, exact `gpt-5-nano`, Chat Completions, exploratory
accounting, N01–N06 before A01–A12. Per selection: 120 requests / 1,800 seconds /
$5 estimated spending stop, retaining the approved token limits. Combined ceilings:
240 requests / 3,600 seconds / $10 estimated stops. Billing uncertainty was accepted.
The original scope and disabled packets remain intact; enabled copies change only
authorization ID, authorization boolean and uncertainty acceptance.

**Partial Level B: actual live evidence measured; the larger baseline is incomplete.**
The first selection stopped immediately after N01 turn 2 accepted an incorrect
report. Four model calls executed. N01 turn 3, N02–N06 and all A01–A12 remain
live-unexecuted. The legacy output directory was never created. Full Level B and
Level C are not claimed. Offline fixes were implemented; a corrected-source live
comparison requires a separate explicit scope and was not performed. Phase 15
was not started.

## 3. Corpus and exposure

Approved selection: 18 trajectories / 40 turns / 27 report goals. Legacy A01–A12
is unchanged Phase 08 v2, with prior offline exposure. New N01–N06 v2 has six
locally authored trajectories / 19 turns / 13 report goals over familiar synthetic
retail/library/workshop hosts. No external blind authorship or unfamiliar data
population is claimed.

All questions, report answers, references and freeze files remain byte-preserved.
V1/V2 author metadata corrections predate this live run and remain separate from
SDK repairs. N01 is now development-exposed; its first two turns were executed,
its third was not. [The additive exposure ledger](../evaluations/phase14/exposure.v1.json)
records that status. Independent replacement wording must be frozen before any
future generalization claim after tuning N01. No new generalization claim is made.

## 4. Actual live correctness and stopping behavior

| N01 turn | Expected | Observed | Classification |
|---|---|---|---|
| 1: Units for each Department in September; asks which year to supply | Year clarification | Intent returned a month with null year and missing `period`; strict semantic decoding blocked it | Incorrect rejection, zero reads |
| 2: “Use 2026, please.”, after reopening | September 2026 Units grouped by Department | Intent selected annual Net sales; Planner proposed it; Reviewer approved; one synthetic SELECT executed | Wrong accepted, incomplete report |
| 3 and subsequent cases | Frozen remaining goals | Not executed after safety checkpoint | Unmeasured |

Observed supported completion **0/1**, correct expected clarification **0/1** and
incorrect accepted specification **1**. Two of 40 planned turns were executed;
38 are untouched. Only one of 27 planned report goals was attempted. These are
small observed denominators, not a zero-percent broad capability estimate.

The scorer detected wrong metric, missing Department grouping and wrong period;
fields, types and rows also failed. Frozen expected values for the supported
report are Books 5 / Garden 9, with September 1 inclusive / October 1 exclusive
bounds. The accepted candidate selected ungrouped revenue over all of 2026.
The existing hook saved the scored turn before raising its safety stop. The
controller then prohibited the second selection. Original journal/results retain
`runner_failure`, the safe generic classification of the stop; detailed checks
identify the semantic failure. No failed call or query was automatically retried.

## 5. Clarification and conversation findings

The missing-year request was not turned into a valid question. Its failed request
rolled back session mutation, including that user message, as the existing atomic
failure contract requires. After reopening, the year reply had neither a current
report nor a pending original request. It became an underspecified new request
from which the model invented annual revenue.

An offline replay through the preserved SDK confirms the original question is
absent from the second Intent payload. After repair, it is retained through a
real pending year question. The rollback policy itself was preserved. Report
replay matched the same cached receipt without extra model/DB work, including the
original wrong report; idempotency alone is not semantic correctness.

No genuine successful year-resolution trajectory, Persian live clarification,
filter refinement, negative-answer recovery or complete multi-turn report was
measured. Those remaining scenarios are explicitly live-unexecuted.

## 6. Vocabulary and opaque references

N01 uses the original retail host and issued **zero opaque value references**.
Valid/fabricated/wrong-owner reference performance is unmeasured. No alias inventory,
private policy scalar, physical mapping or report row was sent to the model.
Offline Phase 06 protocol checks and the frozen Phase 14 vocabulary scenarios remain
intact; their scripted results do not become live compliance measurements.

## 7. Intent, Planner and Reviewer effectiveness

Intent call 1 identified Units/Department but supplied an invalid incomplete date.
The earliest causal failure was converting that ordinary missing detail into a
blocked request with no pending conversation context. Intent call 2 then chose a
new annual revenue report from a year-only message. Planner retained that invented
meaning and Reviewer approved it: **one incorrect approval out of one reviewed
incorrect candidate**. There were no correct candidates in this live Reviewer
sample, so false-rejection/valid-approval rates have zero denominators.

Reviewer no longer had the original business request in its context. The root cause
therefore includes upstream context loss and missing request-sufficiency enforcement;
this result cannot be attributed solely to Reviewer seeing and ignoring the original
request. Phase 13's two wrong approvals remain separate real observations. No
reviewer guarantee or larger-model superiority is inferred.

## 8. Deterministic safety findings

Structural validation correctly refused the null-year month, but a safe reporting
conversation should have asked for the missing year. Later SQL validation correctly
compiled an authorized annual revenue query, yet that query did not represent the
user's report. Trusted policies and deterministic SQL do not establish business
meaning when the reporting context has already been lost.

The new provider-independent engine boundary asks for report details when an
isolated affirmative year has no current or pending report context. It prevents
all providers from inventing a default report in that specific path. Existing
reports may still receive year refinements; registered numeric business labels
remain usable. “For each” now supplies the same registered grouping requirement
as “by”; quoted/filter-literal occurrences retain their roles.

Actual unauthorized reads, payload isolation failures and model-written SQL
acceptance were zero. No denial scenario ran, so no broad authorization-prevention
rate is claimed. The one source read was synthetic and policy-bound. Source file
hashes matched before/after; no production database was accessed.

## 9. Confirmed root causes and offline reproduction

Focused regressions initially reproduced 13 failures with six passing safety cases.
The first defect is narrowly identified by `invalid_interpretation`, reason
`period_selection`, field `period`, while independent user evidence already says
that a named month needs its year. The second is a year-only request being permitted
to execute model-selected defaults after a failed request left no context. The
third supporting gap was failure to anchor explicit “for each” grouping.

Exact captured-output replay over the two actually executed turns reproduces the
baseline's wrong publication and one database read. On the corrected SDK, turn 1
becomes a year question and the recorded annual plan is rejected with zero database
reads and no wrong publication. The replay stops when its requested repair has no
recorded response; it does not fabricate a successful model revision. This is an
offline causal comparison, not a new model call or live completion improvement.

The new focused suite covers valid completion with independent quantities and
bounds, reopened SQLite sessions, cached replay, repeated ambiguity limits,
provider-neutral refusal of invented defaults, registered numeric labels, existing
report year refinements, and negative/question/example/conflicting-year rejection.
Unknown concepts and malformed JSON remain blocked.

## 10. Targeted implementation changes

Four SDK files changed. The agent converts only the observed, independently
confirmed missing-year period-validation error into a local year question. The
invalid period is not accepted and no additional model request is made. Existing
malformed-output handling, registered-concept checks and repair limits remain.

A bounded affirmative-year recognizer accepts existing answer wrappers and polite
English/Persian clauses, preserving the original month through clarification.
Question, negative, quoted-example and conflicting-year forms do not supply a year.
The engine adds the before-provider isolated-year guard described above. The local
registered grouping recognizer adds “for each”. No business-specific metric synonym,
model-written SQL, new agent stage, persistent schema, public API, adapter change,
provider switch, runtime dependency or extra retry/revision loop was introduced.

Baseline SDK: `e64e611ad9434d11059745d806a02dbb4be00607c1daa82c3bbf06946de0dbe2`.
Corrected SDK: `d1f480543ec32c4552422b1f606b22e3319b7230f0620b5e507b235f2b87da75`.
The baseline evaluator remains unchanged. Old enabled approval is rejected against
the corrected source before credential/client access. No further live dispatch ran.

## 11. Provider usage, latency and estimated cost

All four actual responses reported valid usage and `stop` finish reasons. Requested
provider/model were AvalAI / exact `gpt-5-nano`; routed backend revision and invoice
remain independently unverified.

| Stage | Calls | Input tokens | Completion tokens | Model latency |
|---|---:|---:|---:|---:|
| Intent | 2 | 8,783 | 5,290 | 35.884 s |
| Planner | 1 | 4,462 | 2,620 | 18.549 s |
| Reviewer | 1 | 3,413 | 792 | 6.835 s |
| Total | **4** | **16,658** | **8,702** | **61.268 s** |

Reported reasoning: 8,256 tokens, a subset of completion; cached input: 4,352,
a subset of input. They are not counted twice. At the approved observed rates
of $0.05 input / $0.40 completion per million tokens, charging all input at the
full rate, the estimate is **$0.00431370**. Actual billed USD remains null. No
missing usage or bound anomaly occurred. Public rate provenance remains the
[AvalAI model page](https://docs.avalai.org/en/models/gpt-5-nano); it does not establish
a verified invoice or framing guarantee.

Submission latency was 22.069 s for the rejected first turn and 39.305 s for the
wrong report. SQLite execution totaled 17.045 ms. Batch controller elapsed was
64.094 s, including setup/checkpoints. Models dominated this small sample; no
controlled performance improvement or latency optimization is claimed.

## 12. Complete regression verification

Final full pytest passes **2,295 tests / 13 native skips** on Windows Python
3.12.0, Windows Python 3.10.22 and Ubuntu WSL2 Python 3.12.3. All existing semantic
release commands and fourteen SQLite schedules pass in each environment.

The new 23-case recovery suite and 486 focused conversation/Intent/reliability tests
pass. Complete verification, exact timings, commands and source hashes are recorded
in [`verification.v2.json`](../evaluations/phase14/verification.v2.json). It includes
full pytest, strict/held-out and Phase 03–09 gates, fourteen SQLite consistency
schedules, Windows Python 3.10/3.12 and Linux verification. Native SQL Server remains
13 separately gated skips; historical Phase 03 D02/D03 retain their expected exit 1.

Frozen A01–A12 still passes its scripted contract; N01–N06 still reports 2/6
trajectories and 9/13 supported reports, with the same four incomplete cases. The
scripted suite already supplied a valid first Intent and therefore did not reveal
the actual malformed-date/context-loss path. Those offline numbers are not a
corrected-source live comparison. No assessment answers or existing tests changed.

The corrected runtime wheel is clean-installed with core-only lower-bound Python
3.10 dependencies outside the checkout. All 45 modules and both synthetic examples
pass without OpenAI, ODBC or pytest installed. Wheel/sdist inventories, runtime
source consistency and whitespace checks are separately recorded.

## 13. Model comparison

No alternative model/provider or corrected-source real-model comparison was executed.
The approved baseline stopped at its required safety gate. The observed Reviewer
miss and Phase 13 history justify preparing a controlled stronger-Reviewer comparison,
but no production model change is supported by comparative evidence yet. Any such
experiment needs its own frozen cases, exact source/model/context and explicit limits.

## 14. Remaining risks and limitations

The full independent live baseline is incomplete: 17 of 19 new turns and all 21
legacy turns remain unexecuted. Vocabulary, bilingual quality, authorization-denial
behavior and broad conversation reliability remain live-unmeasured. N01 is now a
repair target rather than untouched assessment evidence.

The fixes close reproduced year/context/grouping paths; they do not prove arbitrary
natural-language equivalence or Reviewer intelligence. Unregistered business aliases
such as “Units” versus the host label “Units sold” still depend on semantic
interpretation. Other model-agreement errors and existing offline N02/N03/N04/N06
gaps remain possible. No generalized production-readiness claim is made.

Provider accounting/framing and actual billing remain unverified. SQLite cannot
verify native SQL Server types/precision, ODBC Unicode/binding, collation,
TLS/permissions, RCSI/SNAPSHOT concurrency, cancellation, pooling or production
workloads. No native result was invented.

## 15. Next engineering priority

Deliver this preserved safety-stopped baseline and the tested offline correction.
A separate exact scope is required before any corrected-source live experiment or
continuation. Freeze replacement assessment wording before further generalization
claims after N01 tuning; retain N01 as an exposed development regression. Do not
silently retry the stopped batch, recycle its remaining allowance, switch models
or begin Phase 15. Correctness remains more important than call-count reduction.

## 16. Git status and proposed commit

Original branch/HEAD and empty index remain. Starting user changes, frozen corpus,
independent oracles, prior reports, readiness record and all raw first attempts are
preserved. Credentials stayed in the authorized child process; Rahtal `.env` and
production data were not read. No commit, push, publication or deployment occurred.

Proposed commit: `fix: preserve missing-year clarification and reject context-free year reports`.
