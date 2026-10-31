# Bounded agent planning for the embedded SDK

## Local evidence guards

Bounded en/fa request evidence is extracted locally from the user's own words and
constrains both the normalized intent and every provider's final specification
before any database read; reviewer approval cannot waive it. It covers:

- **Concepts and exclusions:** positive, excluded, literal and unresolved
  occurrences of registered metrics/groupings; explicit exclusions and replacements;
  exact labels and specific aliases select their registered metric.
- **Filters and ordering:** explicit predicates over permitted filter labels with
  typed literal values; registered ordering targets, directions and counted limits;
  refinement cues that preserve, replace or remove current controls.
- **Periods:** named months, Jalali/Gregorian selections, relative periods,
  role/date relations and missing years. A missing year asks; it is never inferred.
- **Clarification continuation:** a pending slot is resolved from current permitted
  concepts while retaining the original requirements
  ([contract](SDK_CLARIFICATION_CONTINUATION.md)). Answers repeating an already
  asked slot fail with `clarification_stalled`.
- **Value vocabulary:** optional host-owned categorical aliases
  ([contract](SDK_VALUE_VOCABULARY.md)); standard transports send opaque references
  for registered values, never the value/alias inventory.
- **Unavailable operations:** a typed unsupported-requirement ledger returns a
  transparent `unsupported` outcome ([reliability contract](SDK_RELIABILITY.md)).

Missing owners/values, conflicts and ambiguous targets clarify before reads. These
are bounded recognizers, not a general natural-language parser, and they do not
prove the model understood the request. Business defaults and vocabulary belong to
host registrations ([integration guide](APPLICATION_INDEPENDENCE.md)).

Business defaults and domain vocabulary belong to host registrations. Shared
intent/planning/review prompts describe supported operations and consume permitted
dataset descriptions and metric terms. See the [application integration guide](APPLICATION_INDEPENDENCE.md)
for retail/library evidence and the Rahtal compatibility considerations.

The [manager extension](SDK_MANAGER_REPORTS.md) adds host business descriptions,
default measures, conservative explicit selection/ranking guards, local relative
period evidence and capability replies, and optional private stage observation.
Normal report decisions still run intent/planning/review; common capability
questions and missing explicit criteria can return clarification locally.

The [registered relationship extension](SDK_RELATIONSHIPS.md) exposes related
attributes on the fact's business catalog. Intent extraction, planning and review
can combine these with fact measures without selecting physical keys. Locally,
an unambiguous permitted source-dimension reference can canonicalize to its
registered fact import; ambiguous roles remain unresolved. Unregistered
cross-source combinations still return unsupported. Related filters, rolling
count/unit periods and aggregate filters are part of the complete ReportSpec;
the engine, rather than agents, binds source policies and compiles their SQL.

The embedded SDK extracts independent intent, then delegates report planning
and semantic review through `OpenAIReportAgent`. All stages use the user's conversation
and the permitted reporting concepts. They produce a complete `Interpretation`,
then the existing engine validates and executes the accepted specification using
the host's current catalog and policies. The planner and reviewer never query a
database or write SQL.

Registered dimensions marked `entity_label` let the planner select display names
on the existing report dataset without inventing joins or switching to a profile
listing. A name refinement preserves the current measures, dates, filters and
top-N ordering. The reviewer checks this distinction and can reject unnecessary
technical confirmation. A new ambiguous ranking needs its business criterion
and period. Label resolution happens locally after aggregation under the
[registered display contract](SDK_ENTITY_LABELS.md); neither agent sees rows,
names returned by the database or resolved identities.

This is a scoped change to the interpretation layer described in [SDK.md](SDK.md).
The [SQL Server execution contract](SDK_SQL_SERVER.md) and
[registered entity lookup contract](SDK_ENTITY_LOOKUPS.md) remain authoritative.
The historical staged API/CLI, isolated Rahtal pilot runner, and scripted offline
demos retain their existing flows.

## Outcome and acceptance

The user can express a reporting request, answer a business clarification, or
refine a saved report without depending on a keyword branch for each phrasing.
The planner selects available concepts by their business meaning. The reviewer
can detect unnecessary clarification, overlooked concepts, unsupported decisions
that have a supported alternative, or lost refinement intent, and request a
bounded revision.

The slice is accepted when these behaviors hold:

- A complete supported decision passes local preview checks and semantic review
  before being returned to the engine.
- A reviewer can reject a clarification for a detail already supplied in the
  conversation, including an unnecessary identity or lookup-confirmation question.
  It can also approve a genuinely missing business detail.
- Revisions retain the original permitted catalog, conversation, business date
  and current report context; feedback cannot grant another capability.
- Malformed output, extra SQL/code fields, unknown concepts, invalid review
  contracts and provider failures fail closed.
- Revision and elapsed-time budgets stop the loop, and no agent stage executes
  a lookup or report. Execution still requires explicit host opt-in.
- Existing ownership, current access checks, revision control, frozen periods,
  persistent refinements and idempotent request receipts continue to apply.

Explicit Persian month selections use the separately scoped
[Jalali month contract](SDK_JALALI_MONTHS.md). The model selects the stated
year/month; the host resolves Gregorian boundaries locally. Missing years still
require clarification. This does not enable general calendar conversion or
Jalali time buckets.

The slice does not add model-selected joins, arbitrary formulas, writes, new
database objects, fuzzy identity matching, timestamp conversion,
result-row reasoning, exports, production HTTP identity, or an unrestricted
database tool agent. The supported reporting operations remain explicitly
registered and deterministically compiled. Semantic review does not guarantee
that every expression is understood or that the chosen business meaning is
correct.

## Public API

The following types are exported from `sageql.sdk`:

| Type | Contract |
| --- | --- |
| `OpenAIReportAgent` | Planner/reviewer orchestration using the host-configured OpenAI-compatible Chat Completions endpoint. |
| `AgentReportInterpreter` | Provider-neutral orchestration implementing the existing `ReportProvider.interpret` interface. |
| `ReportAgentBackend` | Replaceable `plan` and `review` interface, suitable for fake offline backends or another configured model transport. |
| `AgentReview` | Immutable semantic judgment with `approved: bool` and bounded `feedback: str`. Approval requires empty feedback; rejection requires nonempty feedback. |
| `ConceptRef` | A permitted dataset/concept pair, never a physical mapping or resolved identity. |
| `UnsupportedRequirement` | An unavailable operation code and a bounded literal quotation from the user's request. It cannot register a capability or authorize execution. |
| `ReportIntent` | Complete effective measures/grouping and period, missing business details, turn kind, and optional constraints on presentation, comparison, row/aggregate filters, ordering and result limit. |

Use the same trusted `LLMConfig` that the host already supplies:

```python
from sageql.sdk import OpenAIReportAgent

provider = OpenAIReportAgent(
    config,                  # Host-owned LLMConfig; never browser input.
    timeout_seconds=30,     # Shared across planning, review and revisions.
    max_revisions=1,
    max_structured_repairs=0,  # Opt in with 1 for one repair shared by all stages.
    max_output_tokens=4096,
    language="fa",
)
# Supply provider=provider to the existing SageQL backend configuration.
```

`OpenAIReportAgent` accepts an injected client for transport tests. Clients must
support the same bounded transport configuration as `OpenAIReportInterpreter`.
Transport retries are disabled. The planner and reviewer use separate requests
to the same configured model and endpoint; no additional remote service is
introduced. The requests are separate, but their mistakes can be correlated
because they use the same model.

### Per-stage models, reasoning effort and usage

By default every stage uses `config.model` and sends no `reasoning_effort`, which
is the earlier behavior. A host can keep a cheap default model and change only the
stage that measurably needs it:

```python
provider = OpenAIReportAgent(
    config,                                   # config.model stays the default.
    stage_models={"intent": "gpt-5-mini"},    # Optional: intent, planner, reviewer.
    reasoning_effort={"intent": "low", "reviewer": "minimal"},  # Or one string for all.
    observer=log_event,
)
```

`stage_models` values are model names on the **same configured endpoint and
credentials**; no other remote service is contacted. `reasoning_effort` accepts
`minimal`, `low`, `medium` or `high`, either as one value for every stage or as a
per-stage mapping. Unset stages omit the parameter, so endpoints that do not
support it keep working. `OpenAIReportInterpreter` accepts one optional
`reasoning_effort`. Invalid stage names, empty model names and unknown efforts
raise `ValueError` at construction.

When an observer is supplied, every response that reports usage emits
`observer("model_usage", "complete", agent_stage=..., model=..., input_tokens=...,
output_tokens=..., cached_input_tokens=..., reasoning_tokens=...)`. It contains token
counts only, never prompts, responses or credentials. Hosts can price them per
model to see which stage costs the most. Missing usage emits nothing, and observer
failures never change a report decision. Changing a stage's model changes behavior
and cost; compare it on the frozen evaluation corpora before production use.

### Compiled intent and placeholder normalization

With `compile_intent=True`, a complete checked intent is compiled locally into the
`ReportSpec` (`sageql.sdk.intent.spec_from_intent`) and the planner call is skipped
on the first attempt. It compiles only when unambiguous: one dataset, nothing
missing or unavailable, a period for dated aggregates, and no unspecified control
a refinement would need to carry over. Unspecified presentation keeps the current
report's value on refinements and registered defaults otherwise. The compiled spec
must pass the same intent, request-evidence and preview checks as a planner
proposal; otherwise the planner runs in the same attempt without using a revision.
The reviewer still runs. The default is off; the reference hosts enable it.

Live intent decoding clears placeholder values on controls marked unspecified
(`normalize_unspecified_controls`): a comparison with `comparison_specified=false`
is dropped unless a change/decrease calculation shows it was meant, and an
`order_by` with `ordering_specified=false` is dropped with its direction.
Malformed flag types still fail closed.

### Optional reviewer and report interpretation

`review=False` accepts a candidate that passes every local intent, request-evidence
and preview check without the reviewer call; planner clarification/unsupported
proposals are then accepted as returned after the local intent checks. The default
keeps the reviewer. Measured live, the same-model reviewer approved every wrong
report it saw, so hosts can rely on the local gates plus a user-visible
interpretation instead.

Every report carries `provenance["interpretation"]`: deterministic phrases, built
from registered labels, for the controls the title does not show (row filters,
aggregate conditions, sort and row limit). The title already states measures,
grouping and periods. Phrases use the public spec, so identities resolved from a
name lookup never appear. The reference page shows them as «برداشت از درخواست».

### Parallel intent samples

`intent_samples` (1–3, default 1) runs independent intent extractions in parallel,
so it adds model cost but not latency. Each sample passes the same strict decoding
and normalization; the sample whose report-defining content (concepts, periods,
controls, missing details; not prose) agrees with the most others wins, the
earliest on ties. A failed or malformed sample is tolerated while another
succeeds, so one dropped connection does not fail the turn; nothing is retried and
the turn fails only when every sample fails. Structured repair is not used for
sampled extraction. The observer receives `intent_samples` with the requested,
valid and agreement counts.

`ReportIntent.unsupported_requirements` defaults to an empty tuple for existing
typed backends. The live strict schema requires this array and supports
`time_grain="jalali_month"` directly. Each unavailable requirement must quote
user text; assistant suggestions and invented evidence are rejected. A checked
unavailable operation returns `unsupported` without asking the reviewer to veto
it or executing a supported subset. Recognized fa/en operation phrases can stop
before any model call. The ledger is model-dependent for other wording/languages.
A reply that declares a ledger but also names an unregistered concept or an
invalid condition is answered from its evidence-checked ledger as `unsupported`,
not reported as an invalid reply; without checked evidence the original
`invalid_interpretation` stands. No SQL runs in either case.

To supply another backend, construct
`AgentReportInterpreter(backend, timeout_seconds=30, max_revisions=1)`. The
backend methods receive the existing conversation, current public specification,
permitted catalog, business date and remaining timeout:

```python
def plan(messages, current_spec, catalog, today, *, feedback, timeout_seconds):
    # Return an Interpretation using only permitted registered concepts.
    ...

def review(messages, current_spec, catalog, today, decision, *, timeout_seconds):
    # Return AgentReview(True) or AgentReview(False, "Business feedback").
    ...
```

`feedback` is a tuple of bounded advisory strings. A backend must honor the
remaining timeout and curate its remote payload; it must not serialize the
physical catalog dataclasses wholesale. Complete `ReportSpec`, HTTP reply/report
JSON and the `SageQL` facade remain unchanged. `Interpretation` adds optional
`clarification_key` and `continues_clarification` fields, defaulting to empty/false
for existing providers. They are internal progress metadata, not HTTP fields.

Live OpenAI agents always run `understand` before planning. Custom backends can
opt into the same checks by implementing:

```python
def understand(messages, current_spec, catalog, today, *, timeout_seconds):
    # Return ReportIntent with complete effective selections, including any
    # unchanged selections inherited from current_spec. No report candidate is
    # available at this stage. References can expose an unavailable combination.
    ...

def plan(messages, current_spec, catalog, today, *, feedback, timeout_seconds, intent):
    ...

def review(messages, current_spec, catalog, today, decision, *, timeout_seconds, intent):
    ...
```

An intent-aware backend may also implement
reconsider(messages, current_spec, catalog, today, *, feedback, timeout_seconds)
to return a new ReportIntent after repeated local conflicts. Feedback contains
only a fixed conflict code. The same original permitted context and remaining
deadline apply; request evidence and capability checks are reapplied. This method
is optional and is called at most once within the existing planning budget.

Two-method custom backends retain their original plan/review behavior; they do
not gain independent intent enforcement automatically. `OpenAIReportInterpreter`
also retains its earlier single-interpreter path. Neither compatibility path
should be described as offering the live agent's independent intent gate.

Custom backends retain typed `Decimal` and date filter values in their context
and returned specification. Vocabulary checks use the JSON representation;
local semantic validation and execution retain the original scalar types.
Remote payloads serialize those values as exact decimal strings and ISO dates.
Existing persisted typed reports can therefore be refined after switching to
the agent provider.

`OpenAIReportInterpreter` remains exported for hosts that explicitly choose the
previous interpreter and its compatibility behavior. The live reference web
host's `--sqlserver` and `--rahtal` modes now select `OpenAIReportAgent`; their
host-specific total agent timeouts are 25 and 600 seconds respectively. Rahtal
allows three revisions within that shared budget and a 660-second overall request.
The `--demo` frontend and `examples/sdk_demo.py` remain deterministic offline demos.
Changing the live provider does not change those demos into language benchmarks.

## Plan, preview, review and revise

Before planning, a separate strict request extracts `ReportIntent` without seeing
a proposed report. References are validated against the actor's permitted catalog.
If the effective measures and grouping require different datasets, the host
returns a localized `unsupported` explanation before planning or database reads.
A registered label decorates identities; it cannot group measures by another
profile attribute. Confirming an earlier assistant's unsupported suggestion
cannot authorize a source combination. Model-proposed `unsupported_reason`
is advisory: it goes through planning and semantic review, so an incorrect
capability claim can be reconsidered within the normal revision/deadline budget.
Only locally detected incompatible dataset references finish before planning.
Two independently supplied explicit Jalali months are supported as the base
and comparison periods of a table; they do not require a multi-month Jalali range.

For an explicitly requested bar chart, a raw identity dimension selected together
with its registered entity label repeats the same target grouping column. The
host locally canonicalizes that pair to the display label before planning.
This preserves group membership and aggregates while providing a single axis.
Other grouping columns and distinct label mappings are never discarded. The
physical equivalence stays out of the model payload.

Within the existing revision budget, fixed `intent_validation` feedback rejects
candidate measures/grouping that differ from the complete extracted intent,
explicit chart/time-grain mismatches, ready reports with missing information and
clarification when no business detail is missing. These candidates never reach
the reviewer or database. Exhausted intent repair returns non-retryable
`intent_mismatch`; the last successful report remains available. This prevents
an approving reviewer from overriding a locally detected intent mismatch.

The same local gate checks comparison periods, row filters, aggregate thresholds,
sort field/direction and requested limits when independently extracted. It compares
resolved bounds while preserving explicit Jalali selections, treats conjunction
and IN-member order as equivalent, and normalizes numeric values by registered
type. Fixed mismatch codes contain no scalar values. A lost threshold, reversed
ranking, changed top-N or retained explicitly removed comparison must be repaired
before review or execution.

For provider-neutral compatibility, new controls are optional in `ReportIntent`:
`filters` / `aggregate_filters` set to `None` leave those controls unconstrained;
an empty tuple requires their removal. `comparison_specified=True` constrains
`comparison`, including `None` for explicit removal. `ordering_specified=True`
similarly constrains `order_by`, including removal. Non-null `descending` and
`limit` constrain direction and the row cap. The live strict JSON shape requires
all control fields, and its instructions extract effective user/conversation
constraints and preserve refinements. Unknown concepts, invalid operators,
malformed values and unbounded controls fail closed. Older two-method backends
still have no independent intent gate. These checks establish consistency with
the extraction; they cannot prove that extraction understood the original text.

An accepted clarification receives a stable key from its missing-detail slots
and concept references, without retaining its phrasing. Sessions persist that
key and the bounded key history for the pending request. A following `answer`
that asks for slots already seen in that pending request fails with
non-retryable `clarification_stalled`, even if the question is paraphrased or the
process restarted; alternating between earlier topics is also stopped. At most
16 distinct answer-continuation keys are retained. A different missing detail may proceed; a fresh `new` request
may need the same slot again. Success/unsupported clears the key. Sessions from
before the change remain readable; their first clarification has no saved key.
Registered lookup questions still follow their existing resolver contract.

Intent extraction remains model-dependent. Local enforcement proves agreement
with the extracted references, not perfect understanding of natural language.
It does not independently verify extraction of literal filters, dates, ranking
criteria or the semantics of host-defined measures. Effective period agreement
is checked locally; extracting the user's intended period remains fallible.
All stages retain the same permitted-data
boundary and shared deadline; no result rows or resolved identities are sent.

Planner and reviewer guidance distinguishes reporting periods from output limits.
An explicit all-data request retains `period="all"` even when the output is the
latest N monthly groups. Ordering and a row limit select those groups; neither
today's date nor the limit authorizes an invented date cutoff. This guidance is
not a deterministic guarantee of business meaning. Report-ready status confirms
the checked query path, not that a model selected the intended month, measures
or presentation; the Rahtal demonstration separately verifies its scenario
acceptance constraints against saved specifications and actual bounds.

1. **Plan:** The backend receives bounded business metadata and conversation
   context, and proposes `ready`, `needs_clarification`, or `unsupported`. A ready
   proposal contains the complete registered report specification, never a patch
   or executable statement.
2. **Check shape and vocabulary:** Strict decoding rejects invalid JSON,
   duplicate keys, non-finite numbers, extra fields, inconsistent outcomes and
   unknown IDs/operators. These failures do not trigger semantic repair. A
   registered ordering field that is absent from the candidate's selected
   output has one narrow repair path: reject that candidate and send only
   `specification_validation: invalid_ordering` to the planner within the
   existing revision budget. This includes an inactive `time_bucket` or
   `period_label`; wholly unknown ordering IDs still fail immediately. The
   rejected candidate never reaches review or execution.
3. **Preview a ready specification:** The orchestrator locally checks registered
   operations, types, periods, filter combinations and presentation constraints.
   It uses the already permitted catalog and a synthetic scope with no row
   policies. It neither resolves an entity nor executes a query.
4. **Review:** A separate model request compares the original business request
   with the checked proposal. Clarification and unsupported proposals also need
   review. The reviewer sees the original public proposal, never a validated
   physical report or lookup request. The extracted intent accompanies planning
   and review. Approval returns the checked proposal, with internal progress
   metadata added for intent-aware clarifications.
5. **Revise within budget:** A semantic rejection supplies bounded business
   feedback to the planner. A local preview rejection supplies only
   `specification_validation: invalid_spec` or
   `specification_validation: unsupported`. The ordering repair above supplies
   only its fixed `invalid_ordering` code; raw validator exceptions and rejected
   specification values are not used as validation feedback. A revised proposal
   undergoes the same checks and review.

A timeless, count-only catalog can legitimately have no visible physical columns
after access pruning. A private preview copy supplies synthetic scaffolding for
that case so full physical catalog validation does not incorrectly reject the
permitted row-count concept. This scaffolding is used only in local preview
validation: it never enters model metadata, lookup resolution, saved reports,
compilation or execution. The original catalog/proposal is used for the agent
requests and the returned result.

The engine subsequently validates the accepted proposal against the full trusted
catalog and current actor scope. It performs any registered name resolution
locally, compiles a deterministic parameterized SELECT, and executes only when
the developer has set `execution="validated"`. The synthetic preview scope and
reviewer's approval have no authority over authentication or mandatory policies.
Current access checks still run around the remote interpretation and database
execution boundaries.

## Budgets and safe errors

All dated aggregate requests require an effective period, including ordinary
grouped totals. The live intent schema requires a `period` field: complete
PeriodSelection when supplied/preserved, null for missing/ambiguous dates.
Local normalization adds missing `period` if neither a period nor a specific
year/calendar clarification exists. Same-dataset refinements/answers inherit
the current period unless a time detail is being clarified; new requests do not
inherit unrelated dates. Timeless counts and dimension-only listings need no
period question. Explicit `all` remains supported; absence never defaults to it.
Ready proposals must preserve effective resolved bounds, with Jalali month
selections retaining their explicit calendar representation. Invalid periods
use existing fixed validation feedback and revision budgets. Custom intent-aware
backends should populate the new period field for supplied dates; legacy
plan/review-only backends retain their existing contract.

`max_revisions` is an integer from 0 through 3; its default is 1. Zero still runs
one planning attempt, with review only if local checks pass. Live agent success
takes three model requests: intent, planning and review. Each allowed revision
can add two more, so the default allows at most five requests and the maximum
allows at most nine without structured repair. Reconsideration can replace a
skipped review after two repeated local intent conflicts; it happens at most
once within the same planning budget. An unavailable intent can finish after
one request, or recognized unsupported evidence can finish without model calls.
The optional max_structured_repairs=1 adds at most one request across all stages
and keeps the original deadline. It defaults to zero; Rahtal explicitly enables
one. Empty/oversized output, invalid requirement evidence, transport failures
and database operations are never automatically retried. Legacy
two-method backends retain their two/four/eight call budgets. A rejected local preview or known inactive
ordering skips its reviewer request and may therefore consume fewer calls. An
ordering repair consumes the same revision allowance as a semantic repair; it
adds no retry budget and does not reset the deadline.

`timeout_seconds` is finite, greater than zero and at most 600 seconds; its
default is 30. Every stage consumes the same monotonic deadline, and each remote
request receives only the remaining time. A revision does not reset the clock.
The engine's separate overall request deadline also remains in force. Custom
backends must respect their supplied timeout; the orchestrator cannot forcibly
terminate a backend that ignores it.

ExecutionLimits accepts an overall request timeout up to 900 seconds while SQL
query timeout remains independently capped at 300 seconds. Its generic defaults
remain 60 and 10 seconds, respectively. Longer interpretation budgets do not
extend each database query or reset the shared deadline after a rejection.

| Error code | Meaning and behavior |
| --- | --- |
| `invalid_interpretation` | Malformed/unknown/inconsistent proposal or review; fail closed unless the host opted into one shared structured repair. Empty/oversized output and requirement evidence are never repaired. Existing narrow ordering repair remains available; the agent's narrow internal known-but-inactive ordering classification described above. The single interpreter still returns this public code for that invalid ordering. |
| `provider_failed` | Model transport or unexpected backend failure; stop with a safe retryable error. |
| `request_timeout` | Shared agent deadline expired; do not start another stage. |
| `agent_exhausted` | The allowed proposals never passed local checks and semantic approval, including exhausted known inactive ordering repairs; stop with a safe retryable error. |
| `provider_input_limit` | Conversation, metadata, payload or schema bounds were exceeded; do not silently truncate required context. |
| `intent_mismatch` | A candidate still conflicts with the extracted intent after bounded repair; no query runs and no automatic retry is suggested. |
| `clarification_stalled` | An answer continuation repeats the same structured missing detail; preserve the prior session state and ask for a complete request instead of repeating the question. |

Additional existing SDK configuration/access errors retain their contracts. The
engine preserves the last successful report after a failed turn. Retrying an
identical request ID uses its saved receipt; an intentional new attempt after a
returned failure uses a new request ID. The orchestration loop does not retry a
database query.

Additional planner/reviewer requests increase model usage, cost and latency
relative to a single interpreter request. Hosts should select revision and
timeout budgets for their configured endpoint and workload. There is no fixed
price assumption or claim that extra review always improves a model's answer.

## Data and risk boundaries

The configured endpoint receives only permitted business IDs/labels, permitted
aggregate/type/unit/filter/time capabilities, bounded user/assistant messages,
the public current specification, the proposal and bounded feedback. User text,
labels, model output and feedback remain untrusted. Prompts describe the intended
behavior; deterministic validation supplies the operational boundary.

Remote payloads exclude credentials, connection fields, physical table/schema/
column mappings, mandatory policy values, row keys, result rows and identities
derived from lookup results. Literal names and other user-provided filter values
remain conversation/specification input. A lookup result never becomes planner
or reviewer context. Sessions still persist messages and report rows locally
under host-owned storage rules; this slice adds no default telemetry.

Semantic approval is fallible. It cannot verify that a view's grain or formula is
correct, prove that a name exists, inspect report totals, or extend access. The
host remains responsible for registered business definitions, authentication,
database permissions, execution opt-in and workload limits. Bounded review
reduces dependence on special-case wording without making the reporting language
or database operations unlimited.

## Verification

Verification of the intent correction (2026-10-08): 810 offline tests passed,
one opt-in SQL Server test was skipped, and the synthetic embedding demo, JS
syntax check, package build and fresh-wheel imports passed. Three unavailable
conversation turns and a supported identity/name table-to-bar refinement passed
interpretation-only checks with the configured model after the redundant-axis
correction. No report SQL ran during those model checks. Details and the failed
pre-correction attempt are recorded in [ROADMAP.md](ROADMAP.md).

Fresh dated table requests use period totals unless the user explicitly requests
a time breakdown. A named month supplies date bounds, not a monthly grouping.
Scoped local evidence anchors Intent and gates final specifications independently
of Reviewer approval. Existing time grouping is preserved for refinements; explicit
daily/monthly breakdowns and quoted/negated presentation phrases keep their roles.
A fresh plain-table Intent with unspecified sorting is constrained to null sort
and ascending direction before planning. Explicit semantic sorts remain supported.
A rejected partial model period can become a local year question when independent
user evidence already establishes that missing detail. No provider retry is added.
Affirmative year replies retain the known pending month and registered “for each”
grouping. The engine asks for report details when a year-only message has no report
context, including after a failed request; existing refinements and numeric business
labels remain supported.
Pending filter-owner answers may repeat the same pending literal with an explicit
affirmative choice. Negative/question/ambiguous choices do not bind an owner.
When local evidence confirms resolution of a pending slot, its answer role takes
precedence over a model's new-request tag; explicit new-report resets retain their
role. This preserves the earlier explicit measure during owner/year continuation.
For a confirmed answer with a known remaining missing year, an invalid model
period reaches the existing year-question fallback before structured repair can
mask that diagnostic. Valid Intent retains normal Planner/Reviewer sequencing;
empty output or transport errors do not gain this fallback.
A fresh dated table explicitly requesting whole-period totals with no grouping
or ranking cue cannot acquire an output dimension from a filter owner. This is
anchored locally and enforced again for custom providers. Explicit groups,
existing grouped reports, quoted values and negated wording retain their roles.
Fixed month/year periods may be canonicalized from a model range only when both
resolve to exactly the same dates and bounded user evidence proves that fixed
selection. Provider session context still freezes Gregorian periods to ranges.
Later relative or ambiguous date instructions prevent recovery of an older fixed
selection; explicit user ranges remain ranges. This does not accept changed dates
or relax final evidence, authorization or SQL checks.
Two validated named months with explicit affirmative `is/as the base` and
`is/as the comparison/reference` roles are anchored by role, not mention order.
Negative/title/predicate text supplies no role, missing years still require
clarification and duplicate roles are ambiguous. This adds no formula or calendar
operation. Plain-table defaults can be retained while an owner/year is pending;
confirmed owner continuations enforce their unsorted table requirement before
publication. Explicit sorting, current ranked reports and historical host-defined
defaults outside that continuation retain their existing behavior.
Unquoted terminal Persian copulas are grammar only around a whole, uniquely
registered value alias; quoted/free-form text and full registered phrases retain
their exact value. The prompts describe kind-specific period fields, unique IDs
and default output limits; strict decoding still rejects malformed model output.

The agent tests use fake transports/backends and synthetic local fixtures.

Opted-in structured repair now sends only fixed validation feedback for Intent
and Planner failures; the single shared allowance and default zero remain.
A fresh plain table carries its known default output limit into effective Intent.
Affirmative comparisons to the current total retain its base period; missing
current context requires clarification. Transport diagnostics use fixed categories
from already-loaded SDK exception types, without importing optional clients,
echoing exceptions or retrying calls. See the latest Phase 14 evidence for the
offline/live distinction and exact approval requirements.

Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_sdk_intent.py tests/test_sdk_agents.py tests/test_sdk_engine.py tests/test_sdk_provider.py tests/test_sdk_jalali_provider.py tests/test_sdk_lookups.py tests/test_sdk_sessions.py tests/test_rahtal_sdk.py tests/test_sdk_web.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe examples/sdk_demo.py
.\.venv\Scripts\python.exe -m build
```

Checks cover generic registered domains, semantic revisions, necessary and
unnecessary clarification, local code-only feedback, narrowly repaired inactive
ordering, malformed/unknown output that still aborts, explicit Jalali selections,
bounded attempts, shared deadlines, provider failure, physical-data exclusion,
count-only projected catalogs, policy-bound execution, disabled execution,
revocation during review, cached retries and persistent refinements. Existing
adapter tests continue to verify deterministic SQL and resource bounds.

Verification (2026-10-06): 79 focused agent tests and the full offline suite
(642 passed, one opt-in SQL Server test skipped) passed. The isolated package
build, fresh-wheel install/public imports and documented synthetic embedding
smoke passed. See [ROADMAP.md](ROADMAP.md) for the complete verification record.

Two interpretation-only checks with the existing configured model passed: a
synthetic full-name daily request selected the registered activity measures and
last-month daily grouping, and a greeting asked for reporting intent. They
executed no database queries. Those checks establish only the tested model
scenarios, not universal language understanding or real-data report correctness.
Real database demonstrations and their private results are recorded separately
in ignored local Rahtal report directories.
