# Phase 04: provider-neutral filter and ordering grounding

Date: 2026-10-25 (Asia/Tehran). Revision `b74c10974265dcac522b3e23623e0f4f9a8ae582`,
branch `main`. No commit or live call was authorized or made.

## 1. Executive summary

Explicit, independently grounded categorical predicates and ordering constraints
now survive fallible extraction, planning and review, and gate **every provider's
new ready specification** before any lookup or report read. The implementation
extends the existing evidence/intent/final-validation paths, without a new public
API, session migration, dependency, execution retry or analytical operation.

P02 completes correctly through bounded planning recovery. D03 cannot return its
incorrect unfiltered 860, but the original one-turn request remains **unfulfilled**:
its unchanged registration supplies no evidence associating the literal with a
particular filter. It clarifies with zero reads. Supplying the filter identity in
a separately frozen continuation produces 580. D02 remains safely blocked.

Thus Phase 04's safety improvements are implemented, but **the full completion
acceptance criteria are not met**. The unchanged Phase 03 corpus measures 40/42
correct supported turns and trajectories, not the projected 41/42. Wrong accepted
specifications fall from two to zero. Its expected-report classifications remain
unchanged; clarification and blocking are not credited as report completion.

The new frozen corpus passes 26/26 trajectories and 25/25 required report turns.
The complete suite passes **1,741 tests, one optional SQL Server integration skip**.
These are scripted synthetic results; live-model generalization is unverified.

## 2. Verified starting state and investigation

Starting index was empty; the seven previously modified tracked paths were
`README.md`, `docs/ROADMAP.md`, `docs/SDK_AGENTS.md`, and SDK `agents.py`,
`business.py`, `engine.py`, `evidence.py`. Prior reports, `evaluations/`, the phrase
module and three test modules were untracked. All were preserved. Before edits,
ignored `dist/phase04/starting/state.json` recorded revision, branch, status,
file hashes and test results; source/evaluation snapshots are alongside it.
No preexisting file was removed. Phase 04 did not alter the starting README,
`business.py`, `engine.py` or original semantic-evidence tests.

The mandatory agent/product/engineering/evaluation documentation and actual
phrase, evidence, business, intent, agent, provider, model, semantic/compiler,
engine/session and independent-reference paths were inspected. The actual flow
is permission projection/current-spec revalidation, user evidence, intent
normalization/anchoring, planning consistency/preview/evidence checks, review,
engine authorization/prepare/final evidence validation, optional lookup,
canonical parameterized reads, local result processing and atomic publication.
Review approval is not an execution or authorization boundary.

Starting reproduction, before production changes:

| Check | Result |
| --- | --- |
| `python -m pytest -q` | 1,635 passed, one skip, 45.11 s |
| Original 61-case `--strict` | 40/40 required reports; zero regressions; 147 transport/47 adapter calls |
| Unchanged Phase 03 fixture/driver | 39/42 trajectories and supported reports; two wrong accepted specifications; failures D02, D03, P02 |

The original starting measurement is `phase04_before_phase03.json`. Comparable
before/after runs use the same improved stage-aware driver/scorer and identical
frozen corpus. Starting-source package hash is
`812ea3261efbbf6a71afe2882128621489de1b5c15a35095a7dda4f2641ceb53`;
final package hash is
`ba999e1a895c3d5bea820640727d13302c44755ddbf3cd453704cb5f525f4e38`.
The comparable evaluator hash matches on both sides. The baseline is reproduced
from preserved local sources, not reconstructed from Git HEAD, which predates the
uncommitted earlier phases.

## 3. Root-cause analysis

### D03: categorical filter omission

1. Original request: `Billed amount for Web only in July 2026.`
2. The unchanged workshop registration has three text filters, Channel, Service
   and Technician, supporting equality/inequality/membership. `FilterDefinition`
   has an ID, label, column and operator list; it has no value enum, value aliases
   or filter-selection aliases. Values are free-form typed literals. Related
   filters import the existing contract; authorized name lookups are separate.
3. The user supplies a literal restriction, but no filter label. No registration
   independently associates that literal with Channel rather than another text
   concept. Source records are not an authorized linguistic vocabulary oracle.
4. The controlled extractor first loses the restriction by returning empty
   filters. Original canonicalization/anchoring has no new positive predicate
   requirement: it can only preserve an explicitly retained **current** typed
   condition, and this is a fresh report.
5. The planner returns the unfiltered target and the reviewer approves it.
   Intent consistency agrees with the omitted predicate. The old final gate has
   no independently grounded categorical condition to compare.
6. Structural validation, policies and compilation correctly accept that broader
   report. The canonical aggregate sums permitted July source rows to 860. With
   the intended Channel equality parameter it instead sums to 580. Both exclude
   void/other-organization facts and the exclusive August endpoint. Correct SQL
   for the broader report is still the wrong report.

The smallest justified fix recognizes the bounded value-only restriction as
unresolved and clarifies before calls/reads. A custom provider returning even a
plausible filtered spec cannot provide the missing independent association. New
F05 answers `Use Channel = Web`, then returns the independently verified 580.
This is a distinct two-turn completion, not a rewrite of D03's frozen goal.

Completing unchanged D03 automatically would require trusting model semantics,
core domain inference, unauthorized value discovery or a new host vocabulary
contract absent from the fixture. None is silently introduced. Optional host
vocabulary could be a future reviewed extension; static enums must not become a
global prerequisite for valid free-form values.

### P02: ordering disagreement

Original request: `July 2026 Billed amount by Service, highest amounts first.`
Extraction deliberately leaves ordering unspecified (`order_by=None`,
`ordering_specified=False`, `descending=None`). The planner selects billed amount
ascending; review approves it. Old intent consistency has no direction to
enforce, and old request evidence has no sort constraint. Compilation faithfully
returns Tune 60, Repair 300, Install 500.

New evidence binds the unique requested registered metric and descending
direction. Effective intent is anchored; the wrong first proposal is rejected
locally. One existing planning revision returns Install 500, Repair 300, Tune 60,
and only that proposal reaches review/execution. Custom providers are checked
by the engine even without intent extraction or review.

Additional defects found while testing were literal analytical words accidentally
acting as instructions, normalization changing parameter spelling/whitespace,
stale controls after metric/group changes, and rejecting a sort excluding its
metric column. These have focused regressions. Existing thresholds (`at least`),
directional ranges (`highest to lowest`), registered ranking aliases and the
separate fixed absolute-decline operation retain their existing meanings.

## 4. Semantic architecture and ownership

`grounding.py` extracts bounded controls over the **permitted catalog** and
revalidated public current spec. It never accepts provider proposals/results as
evidence, queries values, chooses physical mappings or grants capabilities.
`RequestEvidence` owns the effective contract; the same contract anchors intent,
checks agent proposals and independently checks the final engine specification.

| Internal field | Owner/invariant |
| --- | --- |
| `filter_requirements` | Tuple of business dataset owner plus existing `UserFilter`. Carries registered identity, declared operator and validated literal value(s). Required predicates on the same filter are compared together through existing typed condition keys. |
| `ordering` | One dataset owner, selected business target (null explicitly clears), optional direction and optional counted limit. Null direction/limit imposes no invented value. |
| `pending_filter_value` | User literal/operator awaiting an owner, local only. A known local clarification can bind an explicitly supplied permitted label. |
| `pending_filter` | Permitted owner/filter/operator awaiting a typed literal. A bounded literal answer or explicit predicate completes it. |
| Existing `excluded_filters` | Removal of a filter property, distinct from a `neq` row condition. |
| Existing `retained_filters` | Compatible explicit-current retention evidence. Combined with new predicates without discarding an explicitly kept condition. |

All added evidence fields have compatible empty/null defaults. No new model JSON
fields or stored session fields are required. Pending state is reconstructed from
user history and recognized local clarification questions; assistant suggestions
do not supply business values, periods or concepts. Original requests still
constrain continuation replies and survive store reopen.

### Filter contract

Recognized constructions include permitted-label equality (`Channel = value`,
`equals`, `is`, Persian `برابر`/`مساوی`), explicit category exclusion/inequality,
label-directed only/filter/for constructions, parenthesized/bracketed `IN` lists,
and bounded replace/remove/retain instructions. Values use the existing physical
column type locally and existing predicate validation. Text parameters preserve
original case, Unicode and internal whitespace; typed numbers/dates use the
supported local normalization. Unknown text values are valid literals, not a reason
to discover values from the database. Complete empty aggregates remain possible.

Longest registered labels and fact context resolve imported-concept collisions;
distinct plausible owners remain ambiguous. Titles/examples and grouping-only
mentions do not create predicates. Quoted direct selections are data in their
predicate role. The entire literal span is masked before metric/date/grain/
unsupported-operation/order interpretation, including analytical words inside it.

Bounded value-only forms (`for X only`, `include only X`, Persian `فقط برای X`)
require an explicit owner or unique applicable current typed condition. A mere
word occurrence or a model-selected association cannot establish that owner.
This is not a general parser for every bare category phrase. More complex
unrecognized requests continue through existing interpretation/review; they are
not falsely claimed as independently grounded.

Conjunctive supported predicates are retained together. Contradictory equality,
membership/exclusion or remove/retain instructions clarify. Missing/invalid types
or owners cannot become successful ready reports. Negated membership does not
turn into positive membership: the currently unavailable operation is transparent
unsupported. No new `NOT IN` capability is registered.

### Ordering contract

Highest/largest/most and lowest/smallest/least, explicit ascending/descending,
supported Persian equivalents, fixed directional ranges, top/bottom counts and
bounded counted highest/lowest constructions ground direction/limit. `first`
alone supplies neither a metric nor direction; `at least` remains a threshold.
An adjacent explicit registered sort target wins; otherwise a unique requested
metric, applicable current metric, unique host default or sole registered metric
can ground the target. Multiple requested plausible metrics clarify rather than
being arbitrarily reduced to a default.

Sorting a registered dimension does not invent numeric ranking. Missing direction
on `sort by Service` stays unspecified. Resolved entity-label sorting remains
unsupported under the existing public contract. Existing group-before-limit
compilation and stable ascending tie keys are unchanged. Secondary sort requests
are unsupported; no multi-column public order interface is added. The registered
absolute-decline cue is shared with `comparisons.py` so it retains its fixed local
operation rather than being reinterpreted as ordinary metric sorting.

Explicit refinement cues retain applicable current filters/order/limit, replace
the specified category or metric target, reverse an existing order, or clear it.
Removing ranking also clears its obsolete counted limit to the existing default
100. A removed/replaced grouping does not force an obsolete sort field. Explicit
new-report cues do not inherit old controls. Unrecognized references/pronouns are
outside this narrow independently enforced grammar.

### Alternatives considered

Prompt/reviewer-only enforcement cannot catch correlated agreement or custom
providers. A mandatory enum would break valid free-form hosts and cannot repair
the unchanged fixture. Database discovery would add unauthorized reads/privacy
and latency concerns. A general parser, public/session migration or parallel
requirement framework would be substantially larger. Extending existing evidence
with existing predicates and one internal sort record preserves a clear owner
and reuses the existing bounded orchestration/final gate.

## 5. Implementation

Phase 04 production changes are `grounding.py`, `evidence.py`, `phrases.py`, one
catalog argument at the agent evidence check, and extraction of the existing
decline cue into a shared helper in `comparisons.py`. `ScopedText.surface` maps
normalized matching offsets back to the original user string; inequalities are
not mistaken for exclamation-clause boundaries. Negative sorting mentions do not
remove requested output columns.

`tests/test_sdk_filter_order_grounding.py` adds 106 cases including real policy-
bound SQLite results, both SQL dialect binds, collisions, aliases for metric
ordering, free-form types, exact Unicode, quoted analytical words, missing values,
bounded recovery, persistent faults, custom providers, new-report reset, failed
revision preservation, receipts, counted limits and unsupported secondary sorts.
Existing Phase 03 pipeline assertions now verify local preemption and successful
repair. One observer test includes the newly meaningful evidence-correction event.
A preexisting numerical test intentionally fetching 20 candidates now actually
asks for 20 instead of contradicting its own ten-row request. No frozen assessment
request, expected data, waiver or scorer rule was changed.

Evaluation changes add the versioned Phase 04 cohorts/loader/CLI options and
stage-aware ordering faults. The driver previously could feed reviewer JSON to
the planner when a newly enforced gate retried early. It now preserves the same
first faulty proposal and reviewer behavior while answering each actual stage.
Comparable starting-source runs use the same driver and reproduce the historical
baseline. Artifact package hashes now identify the actual imported source, and
new suites identify their own corpus/freeze rather than Phase 03's files.

## 6. Independent evaluation

All previous corpus, freezes, corrections and baseline bytes remain intact.
New expectations were frozen before running the changed SDK. F/O development
cases guide fixes; five A assessment contrasts are separate and were not promoted
as unseen live-language evidence. Reference arithmetic consumes independently
authored synthetic source records, never returned SQL/results or model approvals.

| Same Phase 03 corpus/scorer/driver | Starting sources | Final sources |
| --- | ---: | ---: |
| Correct complete supported turns / trajectories | 39/42 | 40/42 |
| Correct / returned reports | 39/41 | 40/40 |
| Wrong accepted specifications | 2 | 0 |
| Satisfied individual fields | 531/546 | 520/546 |
| Filter field completeness | 40/42 | 40/42 |
| Order target / direction / limit completeness | 41/42, 40/42, 41/42 | 40/42 each |
| Required clarifications correctly answered | 4/4 | 4/4 |
| Additional clarification against original report goals | 0 | 1 (D03) |
| Correct unavailable outcomes / zero-read denials | 5/5, 2/2 | 5/5, 2/2 |
| Intent / planning / review transport calls | 50 / 50 / 47 | 49 / 50 / 45 |
| Planning revisions / structured repairs | 5 / 0 | 6 / 0 |
| Adapter calls (including injected failure) | 42 | 41 |
| Local scenario total, ms | 1251.084 | 1295.859 |

Field fractions decrease because the old wrong D03 report earned partial field
credit; its new non-report correctly receives zero. Neither partial field credit
nor an extra clarification is hidden or substituted for complete-report accuracy.
The original scorer calls D03's clarification unnecessary relative to its frozen
one-turn report goal. That label is retained even though investigation establishes
that the unchanged registration cannot independently resolve its owner.

| New frozen cohort | Starting sources | Final sources |
| --- | ---: | ---: |
| Correct trajectories | 10/26 | 26/26 |
| Correct required reports | 15/25 | 25/25 |
| Wrong accepted specifications (includes non-report goals) | 12 | 0 |
| Filter completeness | 20/25 | 25/25 |
| Order target / direction / limit completeness | 24/25, 19/25, 24/25 | 25/25 each |
| Correct clarifications | 2/3 returned | 5/5 returned |
| Intent / planning / review calls | 30 / 27 / 27 | 26 / 36 / 25 |
| Planning revisions / structured repairs | 0 / 0 | 10 / 0 |
| Adapter calls | 27 | 25 |
| Local scenario total, ms | 751.832 | 824.186 |

Final new development: 21/21 trajectories, 21/21 required reports (28 total turns).
Final new assessment: 5/5 trajectories, 4/4 required reports (five turns), no
planning revisions. The three blocked custom/persistent-provider controls are
separate safe blocks, not reports. The old holdout remains 30/30 trajectories and
29/29 reports. Old development remains 4/6 trajectories, 7/9 reports; old pipeline
improves to 6/6 trajectories and 4/4 reports.

Starting/final records are `evaluations/baselines/phase04_*.json`; detailed local
command logs are ignored under `dist/phase04/`. Latencies are single concurrent
local scripted measurements and establish no speedup or provider SLA. Scripted
usage coverage is zero; tokens and money cost remain undefined, not zero.

## 7. Multi-turn and agent pipeline reliability

Wrong extraction is anchored from original evidence even when its predicates are
empty. Wrong plans are rejected through existing intent/evidence checks before
review. An approving reviewer cannot waive a mismatch. Correct proposals still
use the ordinary three calls; no extra model request is introduced for an
unambiguous correct named predicate/order. One later valid proposal can complete
within the existing revision/deadline budget. A persistently wrong provider
publishes nothing and executes no report. Database failures are never retried.

All eight original multi-turn trajectories continue to pass. New F07/O10/F05 and
focused tests verify metric changes retaining categories, category replacement,
removal, order reversal/date retention/ranking removal, store reopen, saved specs,
earlier reports and replay without new calls. Failed refinements retain the last
successful report/revision and their receipt cannot re-execute. Pending owner,
literal and ordering-target answers retain original periods and requirements.

In the comparable old pipeline, P01/P02's faulty proposal reached review, which
respectively rejected/approved it. The new gate preempts both; only the repaired
correct proposal reaches review. This is not evidence of improved reviewer or live
model reasoning. Structured repair and intent reconsideration counts remain zero;
semantic planning revisions are reported separately.

## 8. Security and compatibility

Only permitted business concepts and a currently authorized public prior spec
enter grounding. Final host validation still checks dataset applicability,
registered operator/scalar types, allowed IDs, source relationship policies and
execution opt-in. Scope is recalculated before interpreting/executing and on
saved reads/replays. Hidden filter requests remain denied without reads.

There are no grounding database reads. Canonical SQLite/T-SQL SELECT compilation,
parameter binding, group-before-limit behavior, stable tie keys, source policies,
lookup/label candidate bounds, cancellation and atomic publication are unchanged.
Injection-like literals are proven bound parameters in both dialects, not SQL.
Cross-tenant and voided workshop traps remain excluded. Existing authorization,
compiler, metadata, relationship, lookup, session and fake-ODBC suites pass.

No physical mappings, policy values, credentials, resolved identities or result
rows are added to model payloads/diagnostics. User literals and public current
conditions use the already approved business context; diagnostics contain fixed
reason codes. Custom host transports remain responsible for their own remote
serialization. The engine gate is independent of their implementation.

Public constructor/protocol/model/report JSON and stored session schema remain
unchanged. Formerly admitted conflicting ready specs now block or revise, an
intentional correctness behavior change. Existing cached receipts and historical
reports retain their stored semantics; no retroactive data/session rewrite or
software-version migration is attempted.

## 9. Regression verification

All commands use the existing Python 3.12.0 environment. No new dependency,
telemetry or configured remote service was introduced.

| Command/check actually performed | Result |
| --- | --- |
| `python -m pytest -q --junitxml=dist/phase04/final-tests.xml` | 1,741 passed, one optional SQL Server skip; 45.79 s |
| `python -m evaluations --strict` | 61 cases; 40/40 reports; no regression/waiver |
| Same with `--cohort phase01` / `phase02` | 20/20 reports in each separate cohort |
| `--suite holdout --strict` | Exit 0; 30/30 trajectories |
| `--suite development` | Exit 1; D02 and D03 remain unfulfilled |
| `--suite pipeline` | Exit 0; 6/6 trajectories |
| `--suite phase03` | Exit 1; 40/42; precisely D02 and D03 |
| `--suite phase04 --strict`, development/assessment separately | Exit 0; 26/26, 21/21 and 5/5 trajectories |
| `examples/sdk_demo.py`, `examples/multi_domain.py` | Both pass; actual synthetic reports/refinements |
| `python -m pip check` | No broken requirements |
| `python -m compileall -q src evaluations` | Pass |
| `node tests/web_tabs.cjs` with existing Playwright runtime | Pass: tabs, history, failures, cache, downloads, mobile, modes |
| Wheel/sdist `python -m build --no-isolation` | Pass using installed build dependencies |
| Fresh installed-wheel import/host smoke and archive inventory | Pass: 43 installed modules; both domain demos; socket connections blocked; 48 wheel/195 sdist members; no private artifacts |
| Python 3.10 AST syntax parse | Pass, 54 package/evaluation/new-test Python files |
| `git diff --check` and original-file hash review | Pass; no preexisting file removed; frozen inputs unchanged |

Actual evaluation commands additionally use explicit `--output` paths under
`evaluations/baselines/` to retain these measurements, with `--compact` only for
the three regression records. Exact local logs are in `dist/phase04/`.

The optional real SQL Server integration was not configured or run. Python 3.10
runtime is unavailable; syntax parsing is not runtime certification. Isolated
remote build dependency resolution and the full dependency/runtime matrix are
unverified. Scripted/browser checks are local synthetic checks, not a live model
or production Rahtal exercise.

The fresh wheel environment used `pip --no-index --no-deps` and copied only the
already installed sqlglot/python-dotenv distributions. With `-I`, no repository
imports or optional OpenAI/ODBC/Rahtal dependencies were used. All package modules
and a copied standalone host demo ran with socket connections blocked; fresh
`pip check` passed. Local scripts are `dist/phase04/package_smoke_final.py` and
`verify_evaluations.py`. Package code is compared to the final source and the
tested installed wheel after the final documentation-only archive refresh.

## 10. Remaining risks and acceptance status

D03 remains a supported desired report without sufficient independent ownership
evidence in its unchanged one-turn fixture. It requires clarification or a
separately scoped host registration extension. D02 still has an uncooperative
custom provider. These two failures remain visible and make combined Phase 03
exit 1. P02 and explicit supported filter scenarios complete correctly; no known
wrong accepted spec remains in the measured cohorts.

The recognizer is a bounded English/Persian contract, not a completeness proof for
unrestricted natural language, complex disjunctions, arbitrary filter aliases,
all pronouns or every bare category phrase. Unrecognized language retains existing
model interpretation/review limitations. Text collation, multi-read snapshot
consistency, production workload/driver behavior, broader Python compatibility
and live language accuracy are not established by SQLite/scripted checks.

Full Phase 04 success is not claimed: original D03 completion and hence the
projected 41/42 result are not achieved. Its safe clarification is explicit and
separately measured, not relabeled unsupported or credited as completion.

## 11. Phase 05 recommendation

Prioritize request-to-report completeness with a reviewed **optional host-owned
value-to-concept vocabulary** design, followed by explicitly authorized synthetic
live evaluation. The remaining confirmed P1 semantic ownership gap has direct
report impact; no measured scalability or orchestration bottleneck in this run
justifies placing those changes first. General parsing or mandatory enum design
would be a larger and less compatible response to this evidence.

Targets: preserve zero wrong accepted specifications and the 61-case strict
cohort; complete the D03 business request using an authorized owner or a correct
clarification continuation; measure first-attempt completion, clarification
precision and provider calls across three domains; retain independent frozen
outcomes and privacy boundaries. Obtain separate explicit request/token/time/cost
approval before any live test. Snapshot consistency and runtime/dependency matrix
work remain valuable separately scoped backlog items. **Phase 05 was not started.**

## 12. Git status and commit message

Revision and branch are unchanged; index remains empty. Existing tracked changes
to README, roadmap, agent docs, agents/business/engine/evidence remain present.
Phase 04 additionally modifies `comparisons.py`, the two existing ranking/observer
tests, prior evaluation guide/runner/CLI and Phase 03 pipeline assertions. New files
include this report/guide, `grounding.py`, the filter/order tests, the versioned
Phase 04 corpus/freeze/loader and `phase04_*.json` measurement records. Earlier
untracked Phase 01–03 files remain untracked and preserved. Full starting/current
status and Phase 04-only hash/diff evidence are recorded locally in
`dist/phase04/final-state.json` and `production-changes.patch`.

No reset, clean, rebase, commit, push or unrelated overwrite was performed.

Suggested commit message:
`fix: ground categorical filters and ordering across report providers`
