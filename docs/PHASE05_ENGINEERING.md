# Phase 05: host-owned categorical vocabulary and complete reports

Date: 2026-10-25, Asia/Tehran. Branch `main`, starting revision
`b74c10974265dcac522b3e23623e0f4f9a8ae582`. No commit or live call authorized.

## 1. Executive summary

An optional, keyword-only vocabulary on an existing filter now establishes the
business owner and canonical scalar of explicitly registered categorical terms.
It uses current permitted host definitions, not model guesses or database value
discovery. Existing free-form typed filtering remains valid.

The separately versioned workshop-values-v1 host completes the original D03
wording with Channel = Web and the independently verified **580**. Original D03
keeps its original registration, frozen report goal and zero-read clarification;
it is not silently marked completed. D02 stays safely blocked, and Phase 04's
ordering correction remains intact.

New frozen v2: **37/37 trajectories, 36/36 required reports**, zero incorrect
accepted specifications. The complete suite passes **1,837 tests, one existing
opt-in integration skip**. Original 61-case strict evaluation and all Phase 04
cohorts pass; unchanged Phase 03 remains 40/42, with D02/D03 unfulfilled.
**Live-model generalization remains unverified.** Phase 06 has not started.

## 2. Starting state and root-cause confirmation

Before production edits, required product/engineering/evaluation documents and
actual catalog, projection, grounding, phrase/evidence, intent/agent/provider,
semantic/compiler, engine and persistence paths were inspected. Starting index
was empty. Earlier reports, source changes, evaluations and tests were uncommitted,
including preexisting changes in comparison/ranking/manager tests. All are preserved.
Initial status/revision/hashes and complete source/evaluation snapshots are ignored
under `dist/phase05/starting/`; Git HEAD predates those uncommitted phases.

Starting reproduction: **1,741 passed, one skip**; strict original corpus 40/40
reports, 147 model/47 adapter calls; Phase 04 26/26 trajectories, 25/25 reports.
Standalone original D03 clarifies, with zero model/adapter calls and 0/1 report
completion under its frozen goal. The original registration has multiple eligible
text filters, but no value-to-filter association. Both unfiltered 860 and filtered
580 are authorized aggregates; choosing Channel from the word Web alone was not
independently justified. Existing Phase 04 F05 explicitly supplies Channel = Web
and still completes with 580. Source rows are not a vocabulary oracle.

## 3. Architecture and semantic contract

The preimplementation [design contract](SDK_VALUE_VOCABULARY.md) compares three
alternatives. Per-filter optional registration was selected: it retains ownership,
type/operator validation and permission projection in one existing catalog.
A separate registry duplicates owner references/projection. A resolver introduces
read/timeout/error/auth contracts without demonstrated need. Neither was added.
Existing dataclasses and matching utilities suffice; no dependency/framework.

```python
from sageql.sdk import FilterDefinition, FilterValueDefinition

channel = FilterDefinition("channel_filter", "Channel", "channel",
    value_vocabulary=(FilterValueDefinition("Web", ("Web", "Online", "آنلاین")),))
shelf = FilterDefinition("shelf_filter", "Shelf", "shelf_name",
    value_vocabulary=(FilterValueDefinition("Science", ("Scientific", "علمی")),))
```

`FilterValueDefinition(value, terms)` attaches to an existing ordinary equality
filter; it cannot introduce columns, relations, operations or authorization.
`FilterDefinition.value_vocabulary=()` is keyword-only, preserving existing
positional constructors, including FullNameFilterDefinition's name_columns.
Full-name lookup vocabulary, null and timestamp values are outside this slice.
Existing typed null predicates remain available independently.

Canonical text, integer, decimal/number, boolean and date values use existing
scalar/predicate validation. Accepted string-enum content remains protected after
JSON persistence. Alias normalization affects matching only: canonical Unicode,
case, whitespace and numeric/date meaning remain intact. There is no implicit
canonical-name alias; terms must be explicitly declared. Unknown owned values
still use normal free-form typed predicates; the list is not a mandatory enum.

Reject malformed tuples, bad types/operators, duplicate canonical values and
redundant normalized terms within one entry. Aliases shared across different
values/owners remain valid runtime ambiguity. Bounds: 64 entries/filter, eight
terms/entry, 120 characters/term, 1,024 entries/4,096 terms per catalog.

Matching uses complete operands, word boundaries, longest registered terms,
existing quote/polarity rules and bounded row-selection roles. Titles/examples,
ordinary metric/group labels and unrelated mentions do not create predicates.
A known prefix cannot ground a longer unknown value. Explicit owners disambiguate;
otherwise multiple eligible owners clarify. Original literal/operator/metric/date
context survives an owner answer. Conflicting filters clarify; removal/replacement/
retention use existing typed control semantics.

## 4. Implementation

| Files | Change |
| --- | --- |
| `sdk/models.py`, `sdk/__init__.py` | New exported FilterValueDefinition and additive keyword-only filter field, with sensitive repr fields suppressed. |
| `sdk/vocabulary.py` | Structural/type validation, alias resolution, canonical equivalence, private transport projection and strictly issued-reference decoding. No reads or global binding caches. |
| `sdk/semantics.py`, `relationships.py` | Validate registration/bounds; existing permission projection carries only visible filters; directed imports inherit their source vocabulary and existing dependency checks. |
| `sdk/grounding.py`, `evidence.py` | Integrate owned/ownerless alias grounding into existing filter requirements, intent anchoring and every final provider check. A fully grounded filter clears stale filter-value missing evidence. |
| `sdk/agents.py`, `provider.py` | Both standard transports serialize canonical registered predicate slots as opaque references; locally grounded requirements are available from the first call. Restore typed JSON scalars before validation. |
| `sdk/engine.py` | Omit empty new vocabulary fields from legacy catalog fingerprint serialization; opted-in changes participate in the complete fingerprint. |
| Evaluation/example/tests | Versioned hosts, frozen cases, independent reference additions, same trajectory scorer, local overhead probe, runnable two-domain example and 96 focused tests. |

No schema/session migration, new ReportSpec fields, model stages, DB retry or
compiler operation. The real model remains fallible: independent evidence anchors
intent, rejects wrong plans before review, permits bounded corrections and gates
custom providers. Source policies and deterministic SQL remain authoritative.

Additional reproduced defects fixed during development: quoted free-form literals
lost trailing whitespace; a value-only pattern crossed a clause boundary and
swallowed dates/metrics (promoted A10); registered alias prefixes could match a
longer unknown value. Tests preserve exact surface values, negative operators and
whole operands. A reproduced analytical-looking value operand no longer becomes
an unsupported-operation claim; other clauses still enforce unsupported operations.
Accepted string enums now compare consistently with their JSON scalar content,
including actual execution after provider decoding. No business answer is hard-coded.

## 5. Independent evaluation and integrity

New host profiles are separate/versioned configurations over unchanged synthetic
workshop, retail and library sources. Parent/source filter registration precedes
public relationship expansion. No Rahtal assumption or production record is copied.
Expected specs, fields, rows, types, bounds, ordering and presentation come from
host contracts and independent Python/Decimal source arithmetic, not generated SQL,
provider output or reviewer approval.

Independent examples: Web July 580/four jobs; Desk 280; Repair+Web 220; June Web
400; opening day 320; budget fee 80; half-hour tier 120; retail Books 70/five units,
Garden 45; library Science three borrowings. Unknown free-form SUM returns null,
not fabricated zero or unnecessary clarification. Every turn also checks previous
reports, reopen, receipts, permissions, read counts and unchanged source bytes.

V1 froze 24 development/12 assessment trajectories. First assessment was 11/12,
with safe A10 continuation failure and no wrong accepted spec. Its requests/answers,
freeze and first result are preserved. A10 was promoted before targeted repair;
A13 independently replaces it. Final v2 has **25 development/12 assessment** cases,
45 turns and 36 required reports. Eleven assessment inputs had previous exposure;
one is a replacement. No claim of an untouched blind benchmark. No answer was
weakened, prior goal relabeled or known-failure waiver introduced.

Comparable runs use the identical v2 host declarations, data, requests, answer keys
and final evaluator. The old SDK lacks the new public registration type; an
evaluation-only passive FilterDefinition subclass carries the same declarations
which that starting SDK ignores. This is explicitly an unsupported-feature before
condition, not a claim that the old native API consumed the registry. Its source
hash matches the exact captured Phase 04 sources:
`ba999e1a895c3d5bea820640727d13302c44755ddbf3cd453704cb5f525f4e38`.

| Comparable v2 metric | Starting SDK | Final SDK |
| --- | ---: | ---: |
| Correct trajectories | 14/37 | 37/37 |
| Complete supported report turns | 10/36 | 36/36 |
| Correct / returned reports | 10/11 | 36/36 |
| Satisfied field requirements | 130/468 | 468/468 |
| Incorrect accepted specifications | 1 | 0 |
| Correct / returned clarifications | 5/27 | 5/5 |
| Unnecessary clarifications | 22 | 0 |
| Correct guard blocks / zero-read denials | 1 / 1 | 3 / 1 |
| Intent / planning / review calls | 14 / 14 / 10 | 37 / 41 / 36 |
| Planning revisions | 2 | 4 |
| Adapter calls | 11 | 36 |
| Local scenario total ms | 638.949 | 1244.682 |
| Local control probe mean ms / probes | 0.471 / 45 | 0.547 / 45 |

No structured repairs/reconsiderations or incorrect unsupported classifications.
Usage is absent: token/cost estimates are undefined, not zero. More completed
reports account for additional calls; vocabulary performs **zero lookup reads**.
Local concurrent scripted timings are not remote latency or speedup evidence.

Final development: **25/25 trajectories, 25/25 reports**, 33 turns, 26/30/25 stage
calls, 25 adapter calls. Final assessment: **12/12 trajectories, 11/11 reports**,
12 turns, 11/11/11 stage calls and 11 reads. Three intentional blocks are not report
completion. V02's negative guard is not completion credit for original D03.

Historical cohorts stay separate: fixed 61 strict cases 40/40 reports; old Phase
03 assessment 30/30 trajectories and 29/29 reports; old development 4/6 trajectories,
7/9 reports; pipeline 6/6 trajectories, 4/4 reports; combined 40/42 reports/trajectories
with zero wrong accepted specs. Phase 04 remains 26/26 trajectories, 25/25 reports,
including its unchanged explicit-owner continuation. All historical bytes remain.

## 6. Multi-turn reliability

All **seven new multi-turn trajectories** (15 turns) pass, versus 0/7 before.
They test owner clarification, value replacement/removal, metric replacement,
period changes with retained conditions, explicit new reports, reopen and revocation.
Each turn is checked; later success cannot erase earlier failure. Existing typed
conditions remain applicable only under the user/context rules. Model suggestions
never establish an owner or canonical value. Free-form owner answers stay typed.

Changing vocabulary content invalidates saved-report/cache compatibility even with
the same catalog version string; the focused test confirms denied old retrieval,
request_conflict on the old receipt and no new read. Empty optional fields preserve
legacy fingerprints. No stored receipt is recalculated or automatically replayed.
Hosts should version material semantic changes and start a new session when needed.

## 7. Agent pipeline and local performance

Controlled faults cover omitted intent predicates, wrong planner filters/scalars,
approval of any wrongly admitted proposal, bounded correction, persistent failure
and custom-provider violations. Three recoverable first proposals complete after
one allowed revision; a persistent omission stops after the existing allowance.
No wrong proposal reaches a database. There are four total revisions including the
persistent guard. No additional model stage or automatic execution retry.

A per-turn local probe measures filter_controls independently of remote/DB work.
An additional five-sample benchmark on short synthetic text measures 0..1,024 values
and up to 4,096 terms. Final medians: 0.331 ms (none), 0.772 (32 entries), 1.202 (64),
3.861 (256), 14.143 (1,024). The maximum recorded largest-catalog sample is 93.815 ms,
including cold matcher compilation. A local escaped-term index avoids thousands
of separate regex compilations; bindings remain per-call and permission-scoped.
These are bounded workload observations, not whole-SDK or production SLAs.

## 8. Security and compatibility

Only permitted definitions influence grounding; denied target/source filters and
dependencies cannot gain access through an alias. Row policies, current actor
ownership, scope revalidation, cardinality checks, result completeness, cancellation,
execution opt-in and canonical parameterized SELECTs are unchanged. SQL Server
parameters are compiled offline; no production DB/object/permission is modified.

New vocabulary is local-only, with no sharing flag or remote inventory. Standard
model payloads expose only already permitted concept IDs/operators and opaque
scalar references for independently grounded/current predicates. Canonical values
are restored locally before checks/SQL; unissued/wrong-owner references fail, and
references cannot appear as model-generated display text. Tests audit intent,
plan, review, legacy interpretation and current context after JSON persistence,
including string-enum values. User-entered terms remain ordinary conversation text;
the SDK does not add unrelated aliases/canonical values through metadata.

Custom providers/backends remain trusted host code with Python catalog/spec access
and must curate their own external serialization. Final semantic/authorization
checks still constrain them. This feature supplies no new per-value RBAC: hosts
must scope their catalogs/filters if even local mapping existence requires it.
No model-written SQL, dynamic scanning/resolver, result/identity feedback, telemetry,
new service or runtime dependency. Safe errors/artifacts omit raw values and secrets.

Public constructors remain compatible; the new field is keyword-only. Parent
relationships preserve policy/type rules. Canonical values and free-form values
are validated, not treated as an enforced enum. Python 3.10 syntax is checked;
runtime execution on 3.10 is unverified. Session/report JSON formats are unchanged.
The declared value-reference protocol is transport-internal, not stored report data.

## 9. Verification

Actual final checks use the existing Python 3.12 environment. Measurement commands
also use explicit `--output evaluations/baselines/phase05_*.json` paths; fixed records
use `--compact`. Earlier snapshots are never overwritten.

```powershell
.\.venv\Scripts\python.exe -m pytest -q --junitxml=dist/phase05/final-tests.xml
.\.venv\Scripts\python.exe -m pytest tests/test_sdk_value_vocabulary.py -q
.\.venv\Scripts\python.exe -m evaluations --strict
.\.venv\Scripts\python.exe -m evaluations --strict --cohort phase01
.\.venv\Scripts\python.exe -m evaluations --strict --cohort phase02
.\.venv\Scripts\python.exe -m evaluations --suite holdout --strict
.\.venv\Scripts\python.exe -m evaluations --suite development
.\.venv\Scripts\python.exe -m evaluations --suite pipeline --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase03
.\.venv\Scripts\python.exe -m evaluations --suite phase04 --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase04_development --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase04_assessment --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase05 --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase05_development --strict
.\.venv\Scripts\python.exe -m evaluations --suite phase05_assessment --strict
.\.venv\Scripts\python.exe -m evaluations.phase05_benchmark --output evaluations/baselines/phase05_overhead.json
.\.venv\Scripts\python.exe examples/sdk_demo.py
.\.venv\Scripts\python.exe examples/multi_domain.py
.\.venv\Scripts\python.exe examples/value_vocabulary.py
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src evaluations examples/value_vocabulary.py
$env:NODE_PATH='C:\Users\Sina\.cache\codex-runtimes\codex-primary-runtime\dependencies\node\node_modules'
node tests/web_tabs.cjs
git diff --check
```

Full suite: **1,837 passed, one skipped**, zero errors/xfails/unexplained failures,
50.47 seconds console time. Focused new tests: **96 passed**. Existing filter/order,
semantic, compiler, security, sessions, Rahtal ranking/manager and browser regressions
run and pass. The skip remains the explicitly opted-in synthetic SQL Server test.
All required evaluation commands exit 0 except historical development/combined
Phase 03, which correctly exit 1 for D02/D03. No failure classification is hidden.
One concurrent final-record batch stopped at Phase 04 with CLI exit 2 and its
generic input/dependency diagnostic. Direct and CLI replays against identical
source passed all 26 trajectories; the sequential rerun of every remaining command
also completed with the expected exits. The transient cause was not established;
no source/fixture/expected-result change was used to make the rerun pass.

Examples, pip check and compileall pass. The new example prints independent retail
120 USD and library 20 days under mandatory policies, with no model/network.

Wheel/sdist builds pass with `python -m build --no-isolation --outdir
dist/phase05/packages` (using the local virtualenv interpreter). The isolated
`python -X utf8 dist/phase05/package_smoke_final.py` check creates a fresh venv,
installs the wheel with `--no-index --no-deps`, and checks dependencies. It imports
all **44 installed modules** and runs copied ordinary/two-domain vocabulary
examples with sockets blocked and no checkout imports. Only already installed base
dependencies are copied locally; no online dependency-resolution claim is made.
The wheel has 49 members and the sdist 228; archive checks find no credentials,
private config/reports, virtualenv or generated dist artifacts. Wheel/installed
source and final sdist public-file bytes match the checkout.

Both vocabulary freeze versions validate. **53 protected earlier files** match
their captured bytes, including historical JSON, independent reference/host code,
Phase 01–04 reports and unrelated prior edits. Python 3.10 AST parsing succeeds
for 60 source/evaluation/new-test/example files; this is syntax evidence only.
Final package-source hashes match every new measurement, before/after corpus,
freeze and evaluator hashes match, HEAD/index remain unchanged, and whitespace
checks pass.

## 10. Remaining risks

Live-model behavior, opaque-reference compliance in a real configured model,
unrestricted English/Persian interpretation, production SQL Server behavior,
Python 3.10 runtime and multi-read snapshot consistency remain unverified.
Static vocabulary does not solve missing host knowledge automatically: unknown
ownerless values still clarify, and nonconforming custom providers can remain
unfulfilled. Original D02/D03 stay visibly incomplete. No known reproduced Phase
05 defect remains in the tested contract. The grammar/configuration bounds and
local-only privacy boundary are explicit; no universal language or scaling claim.

## 11. Phase 06 recommendation (not started)

Prioritize **explicitly authorized synthetic live evaluation of vocabulary/refinement
and private-reference handling**. Deterministic evidence now satisfies the new
host contract, but scripted outcomes cannot measure model interpretation, useful
clarifications or protocol compliance. Freeze fresh independently grounded prompts,
use reviewed endpoints/models and request/token/time/USD budgets, keep every first
attempt/failure, score complete results and stage origins, and preserve existing
regressions. Measure reference copying, ambiguity, unsupported requests and longer
refinements across hosts without exposing private inventories or results.

Choose model/topology changes only after controlled comparisons show value. Python/
SQL Server runtime matrices and large-catalog cold latency are separate priorities;
snapshot design still requires its own scope. No live authorization is inferred
and no Phase 06 implementation or infrastructure change was begun.

## 12. Git status

Still `main` at the original revision. No commit, push, reset or rebase. Index
remains empty. Earlier modified files, tests and untracked artifacts are preserved.
Phase 05 changes models/exports, validation/relationship inheritance, grounding,
evidence, standard transport serialization and catalog fingerprint compatibility;
adds the vocabulary module, 96 tests, example, design/report/evaluation docs and
versioned fixtures/measurements. Generated `dist/phase05/` remains ignored.

Proposed commit message:
`feat(sdk): add private host-owned filter value vocabulary`
