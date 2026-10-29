# Phase 08 engineering report — 2026-10-26

## 1. Executive summary

**Phase 08 live-evaluation preflight ready; external execution awaiting explicit authorization.**

Completion level **A (Preflight Ready)**. Levels B (live baseline measured) and C
(reliability improvement demonstrated) are not reached. Zero real-model requests
were sent. No real-agent accuracy, protocol compliance, reviewer utility, token,
latency, cost or billing result can be claimed. No production SDK code was changed.
The supplied brief requires exact authorization separately from this assignment.

The existing Phase 06 infrastructure was reused. A focused fresh selection of
14 trajectories/23 turns, split pilot/assessment packets, independent expected
reports, disabled approval configurations and explicit no-dispatch probes are
ready for review. Public provider/accounting evidence has gaps; the packets
cannot authorize dispatch until those prerequisites and human approval are met.

## 2. Starting baseline and preservation

Started on `main`, HEAD `b74c10974265dcac522b3e23623e0f4f9a8ae582`, empty index,
17 tracked modifications / 156 untracked files. All earlier phases remain
uncommitted. Before new files, `dist/phase08/starting/state.json` recorded 286
repository hashes and 565 earlier measurement JSON hashes; source/evaluation/docs
snapshots were copied into ignored starting storage. No reset, clean, rebase,
unrelated deletion, commit or push. Existing Phase 01–07 reports, product rules,
SDK contracts, pipeline, reference/scoring, frozen hosts/corpora, transport,
approval/budget/journal and persistent paths were reviewed.

SDK source remains exactly the Phase 07 aggregate hash
`1f4fe6d4e99933a2636fd2f1ccb16c0ca82004d2178be136c3e3fedffab06c06`.
Final verification reproduces original Phase 06 **45/45 trajectories, 36/36
reports** and Phase 07 **27/27, 24/24**, both zero wrong accepted specs/unauthorized
reads. The full suite is **2,048 passed / one optional SQL Server skip**: the
existing 2,038 plus ten narrowly scoped wrapper/readiness checks.

## 3. Existing evaluation readiness

Real path: `evaluations.phase08` loads/merges frozen local selection and answer
keys → unchanged `phase06.run` → exact `validate_approval` → lock/journal/reservation
→ observed SDK Chat Completions client → public SageQL/agent intent/planner/review
→ deterministic evidence/access/spec checks → synthetic read-only SQLite →
independent scorer → checkpointed outcome. No production SQL Server is needed.

Current infrastructure already binds source/evaluator/corpus/freeze/selection,
endpoint/model, output directory, synthetic scope, positive request/input/output/
total/time/USD ceilings and reviewed accounting/pricing. Approval validation
precedes credential lookup and client creation. Every call is durably reserved
before dispatch. Usage settlement records actual fields; missing/failed/uncertain
usage retains conservative reservations. Invalid usage/bound violations stop
further dispatch. No model/DB retry or automatic provider fallback was added.

Atomic journals, exclusive OS locks, first-attempt preservation and controlled
resume remain unchanged. An interrupted active trajectory retains completed turns
and uncertain work is never repeated. Time includes restart pauses. Cancellation
is cooperative; this is not certified invoice control or a provider kill switch.

Only a small selection adapter was added, with the existing post-turn hook stopping
after a scored incorrect published report, wrong accepted spec, unauthorized read
or payload-isolation violation. The shared runner saves the turn before this hook;
its existing generic runner failure then records interruption. The scored turn
identifies the actual violation. There is no competing orchestrator or journal.

## 4. Authorization and live execution

No explicit live approval is present. Only `.env` lines for nonsecret endpoint/
model configuration were selected: **AvalAI / https://api.avalai.ir/v1 /
gpt-5-nano**. API keys were neither read nor printed. No endpoint ping, Models API,
token-counting call, live model, production DB or real-account request was made.
Public documentation lookup is distinct from model dispatch.

[The approval guide](../evaluations/PHASE08.md) and disabled pilot/assessment JSON
files contain exact scenario IDs, hashes, limits and output paths. Pilot permits
at most 12 requests, 250,000 input / 49,152 output / 299,152 total tokens, 300 s,
$0.25; assessment at most 120 requests, 2,000,000 / 491,520 / 2,491,520 tokens,
1,800 s, $1.00. Both cap each completion at 4,096 tokens. No variability/repetition
trial is included. These are proposed ceilings, not consumed usage.

Both packets are disabled; pricing/accounting remain unreviewed. Exact CLI
preflight for each returns **2 before evaluation-key access**, with no client,
live directory, live journal or dispatch. A unit check also rejects merely
flipping authorization without pricing/accounting review. Live artifacts remain
absent. Existing credentials do not satisfy the approval requirement.

## 5. Corpus, ground truth and real-agent correctness

The [guide](../evaluations/PHASE08.md) maps every category. The sample uses only
existing retail/library/workshop hosts/facts and approved operations. Two pilot
cases precede twelve assessment cases. There are 16 required reports, five
clarification goals, one unsupported and one denial. Inputs and answer keys are
separate frozen files; complete specs, numeric rows, field types, filters,
boundaries, presentation, sort/limits and exclusions are local scorer material.
The existing Python/Decimal reference independently computes results without
SDK SQL or model/reviewer output. Comparison uses the existing reference once.

Initial business questions are new relative to old corpora; generic short answers
may recur. All cases are locally authored/contract-reviewed and offline exposed,
with no live exposure, external blind-review claim or targeted production tuning.
Existing regression/development/protocol populations remain separate.

V1's initial contract run scored 7/14 trajectories and 7/16 reports, with a local
A07 authoring bug: comparison composition duplicated an operation already present
in the reference. V2 corrects only that answer-key composition, retaining all
questions, requested specs and report goals. Both versions/freezes and first
artifact remain. V2 scores **8/14 trajectories and 8/16 reports**, zero wrong
accepted specs/unauthorized reads. This is **an offline contract finding, not an
agent understanding score**. Six incomplete trajectories remain visible and no
safe block is counted as a fulfilled report. Real-model correctness is unavailable.

## 6. Agent stage analysis

Real intent/planner/reviewer observations: **none**. The existing observation path
can record decoded/effective intent, each proposal, reviewer decisions, revisions,
first disagreements, deterministic interceptions and final outcomes. Strict stage
agreement can flag omitted defaults or equivalent representations; it is a
diagnostic and does not independently prove linguistic meaning.

Several new contract failures occur with **zero model calls** on the affected
turn. They cannot honestly be blamed on model extraction or reviewer quality.
Later scripted intent errors can be cascades after an earlier failed turn, not
independent root causes. No prompt/topology/model tuning or recovery-limit change
was made before a real baseline. Reviewer rejection rates are unmeasured, not 100%.

## 7. Opaque references and privacy

No real-model reference behavior was observed. The existing Phase 06 protocol
cohort still passes 14/14. Issued/unissued/altered/wrong-owner/display references,
ordinary canonical scalars and recovery retain their current rules and counters.
The new sample's alias cases can exercise issuance through standard serializers
if subsequently authorized; no private inventory is added to model input.

Model payloads remain bounded user/permitted business context. Expected rows,
answer keys, result datasets, physical mappings, policies, credentials and private
identities are not supplied. Measurement storage remains allowlisted IDs/hashes/
counts/booleans/reasons/timings/usage; no raw exception or new remote telemetry.
Synthetic answer fixtures are local reference data, never production records.

## 8. Multi-turn reliability

The new sample covers consecutive owner/year questions, short and conversational
answers, Persian aliases, ranking criterion, metric replacement, retained/removed
filters, group/date changes, sort reversal and reopening. Existing runner replay
checks assert identical cached receipts without new model/database work; earlier
reports remain independently retrievable. A09's revoked scope is a local denial
test and cannot measure real-model refusal behavior.

Existing Phase 07 tests cover current catalog/vocabulary revisions, access changes,
both stores and atomic publication. All remain green. New unsupported report goals
are not substituted for incomplete supported turns; a later correct result never
erases an earlier wrong question or report. Actual conversational model reliability
remains unmeasured.

## 9. Usage, cost and latency

Actual evaluation requests: **0**; real stage calls, usage/token details, cost,
provider invoice and latency are **unavailable**. Proposed ceilings do not count
as observations. The offline scripts intentionally provide no usage metadata.

[AvalAI's model page](https://docs.avalai.org/fa/models/gpt-5-nano) lists standard
text input/output prices of $0.05/$0.40 per million tokens; these observed candidate
rates appear in the disabled packets. They do not establish effective account
pricing, route fees or exact billing. The effective date and pricing review remain
required. Cached input is conservatively priced at the full input rate for bounds.

The proposed 4,096-token framing allowance is **not independently verified**.
[Provider accounting guidance](https://docs.avalai.org/en/guides/token-counting)
describes hidden framing/schema/reasoning contributions and usage reconciliation;
it provides no quantitative guarantee for this exact route/account. Operator
evidence for a conservative full-input bound, reasoning-inclusive caps/usage and
no unpriced fees remains mandatory. If unavailable, dispatch stays prohibited.
No claim of a hard provider billing cap or actual invoice verification is made.

## 10. Confirmed findings and corrections

| Finding | Evidence / disposition |
| --- | --- |
| Evaluation authoring defect, corrected | A07 duplicated comparison fields/rows despite the existing reference already handling comparisons. Preserve v1, correct only local oracle in v2. No SDK change. |
| P2 deterministic clarification incompleteness | A03/A04 first ask a grouping question despite outstanding owner/year details; A03 later completes but its first turn remains wrong. A04's answer stalls. Both first turns dispatch zero model calls. |
| P2 deterministic answer/context preemption | A05's measure answer stalls; A06's first metric-replacement refinement and A10's explicit quoted-example request clarify locally with zero calls. These are reproducible supported-goal incompletions/bounded-grammar limits, not measured model failures. Exact root diagnosis and corrections are deferred. |
| Unresolved scripted/local interaction | A11's conversational conflict correction reaches intent then response-shape failure. One synthetic observation does not establish real-model failure or a complete SDK root cause. Preserve it for diagnosis. |
| Environmental test defect, corrected | One new test used Windows default encoding to read Persian JSON. Explicit UTF-8 fixes the test only; first failure retained. |
| External prerequisites, not a code defect | Human authorization and exact provider accounting guarantees are absent. Do not weaken the existing gate or infer authorization. |

These incomplete goals are retained, not removed/reclassified to improve scores.
No wrong accepted report or security breach was observed in the new contract
check. Runtime changes before live collection would alter the intended baseline;
no production repair or broad speculative refactor was made in this phase.

## 11. Security and compatibility

No SDK public API, session schema, model stage, dependency, policy, SQL compiler,
execution opt-in, timeout, authorization, row policy, opaque-reference boundary or
production data changed. No arbitrary joins/SQL, private-result feedback, failed
DB retry or framework migration. Trusted actor identities remain host supplied.
The new wrapper is evaluation-only and uses the original exact approval gate.

SDK byte preservation is verified against the initial snapshot. Packaging includes
the local guides/fixtures, excludes credentials/ignored reports/environments and
imports the installed wheel with network blocked. Public-doc browsing sent no
repository payload or private data to a model/provider endpoint.

## 12. Regression verification

| Executed check | Actual result |
| --- | --- |
| `python -m pytest -q` | **2,048 passed / one optional SQL Server skip**, 65.92 s |
| Existing evaluator/session readiness selection | **145 passed** |
| New focused readiness checks | **10 pass** in final full suite |
| `python -m evaluations --strict` | **61/61**, exit 0 |
| `--suite holdout --strict` | **30/30**, exit 0 |
| `--suite phase04 --strict` | **26/26**, exit 0 |
| `--suite phase05 --strict` | **37/37**, exit 0 |
| `--suite phase03 --strict` | **40/42**, expected exit **1**, original D02/D03 |
| Phase 06 / Phase 07 all-corpus commands | **45/45, 36/36 reports** / **27/27, 24/24 reports**, exit 0 |
| New v2 offline contract exercise | **8/14, 8/16 reports**, expected documented exit **1**, six retained incomplete trajectories |
| Exact disabled pilot and assessment preflight | Both exit **2**, zero key reads or live artifacts |
| SDK, multi-domain, vocabulary examples | Pass offline |
| `pip check`, `compileall -q src evaluations` | Pass |
| Python 3.10 syntax | **62 source/evaluator files** pass AST; actual 3.10 runtime unverified |

Wheel/sdist build, isolated installed-wheel imports/examples, archive/current-source
byte checks, whitespace and all earlier-work hashes are recorded in
`evaluations/phase08/verification.json`. Generated logs, original failed runs,
snapshots and fresh environments remain ignored under `dist/phase08/`.
No ordinary test command contacts a model or uses production SQL Server.

## 13. Remaining risks

No empirical model baseline exists. Provider schema compatibility, actual usage
semantics, per-account rate limits/routing, cost, bilingual generalization,
reference compliance and reviewer benefit remain unverified. Public documentation
and scripted transport success cannot replace a pilot. No automatic provider/model
switch is authorized if a pilot fails. Small eventual samples are exploratory.

New deterministic incompletions can preempt the model and must be distinguished
from agent failures. Historical D02/D03 remain safely unfulfilled under unchanged
contracts. Runtime Python 3.10, production SQL Server behavior and multi-read
snapshot consistency remain existing unverified scope. Local filesystem access
controls are host responsibilities; journals are not tamper-proof billing ledgers.

## 14. Phase 09 recommendation — not started

If live approval is supplied, first finish the unchanged Phase 08 pilot/baseline
before selecting agent optimizations. Do not treat another preparation phase as
an empirical result. If authorization remains unavailable, prioritize **scoped
deterministic clarification/context correctness** for the newly reproduced
zero-call failures. This is independent product engineering with demonstrated
business impact, not duplicate evaluation preparation or speculative model tuning.

Acceptance: preserve captured Phase 08 baseline and incomplete goals; promote
cases used for targeted repair and freeze replacements before tuning; trace the
first loss of user meaning; complete the independent owner/year, ranking-answer,
replacement and quoted-role reports without guessing; preserve current periods,
filters/groups/order, custom-provider gates, reopen/replay and all historical
cohorts; zero wrong accepted reports or unauthorized reads. Diagnose A11 separately
before choosing a fix. A real minimum-Python/installed-wheel matrix is the next
release-engineering priority; no Phase 09 work begins here.

## 15. Git status

Still `main` at the original revision, index empty, no commit/push. SDK and all
prior corpora/freezes/baselines retain starting bytes; only README, ROADMAP and
evaluation index documentation are intentionally extended. New Phase 08 assets,
loader, readiness tests and report are additive. The verification manifest lists
exact preserved counts and final tracked/untracked totals.

Proposed commit message:
`test(evals): prepare gated real-model pilot and record Phase 08 readiness findings`
