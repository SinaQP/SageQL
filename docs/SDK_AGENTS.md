# Bounded agent planning for the embedded SDK

The embedded SDK can delegate report interpretation to a planner and a semantic
reviewer through `OpenAIReportAgent`. Both decide from the user's conversation
and the permitted reporting concepts. They produce a complete `Interpretation`,
then the existing engine validates and executes the accepted specification using
the host's current catalog and policies. The planner and reviewer never query a
database or write SQL.

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

The slice does not add model-selected joins, arbitrary formulas, writes, new
database objects, fuzzy identity matching, new calendars, timestamp conversion,
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

Use the same trusted `LLMConfig` that the host already supplies:

```python
from sageql.sdk import OpenAIReportAgent

provider = OpenAIReportAgent(
    config,                  # Host-owned LLMConfig; never browser input.
    timeout_seconds=30,     # Shared across planning, review and revisions.
    max_revisions=1,
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
physical catalog dataclasses wholesale. The existing `Interpretation` and
complete `ReportSpec` contracts are unchanged, as are HTTP reply/report JSON and
the `SageQL` facade.

Custom backends retain typed `Decimal` and date filter values in their context
and returned specification. Vocabulary checks use the JSON representation;
local semantic validation and execution retain the original scalar types.
Remote payloads serialize those values as exact decimal strings and ISO dates.
Existing persisted typed reports can therefore be refined after switching to
the agent provider.

`OpenAIReportInterpreter` remains exported for hosts that explicitly choose the
previous interpreter and its compatibility behavior. The live reference web
host's `--sqlserver` and `--rahtal` modes now select `OpenAIReportAgent`; their
host-specific total agent timeouts are 25 and 45 seconds respectively. The
`--demo` frontend and `examples/sdk_demo.py` remain deterministic offline demos.
Changing the live provider does not change those demos into language benchmarks.

## Plan, preview, review and revise

1. **Plan:** The backend receives bounded business metadata and conversation
   context, and proposes `ready`, `needs_clarification`, or `unsupported`. A ready
   proposal contains the complete registered report specification, never a patch
   or executable statement.
2. **Check shape and vocabulary:** Strict decoding rejects invalid JSON,
   duplicate keys, non-finite numbers, extra fields, inconsistent outcomes and
   unknown IDs/operators. These failures do not trigger semantic repair.
3. **Preview a ready specification:** The orchestrator locally checks registered
   operations, types, periods, filter combinations and presentation constraints.
   It uses the already permitted catalog and a synthetic scope with no row
   policies. It neither resolves an entity nor executes a query.
4. **Review:** A separate model request compares the original business request
   with the checked proposal. Clarification and unsupported proposals also need
   review. The reviewer sees the original public proposal, never a validated
   physical report or lookup request. Approval returns the proposal unchanged.
5. **Revise within budget:** A semantic rejection supplies bounded business
   feedback to the planner. A local preview rejection supplies only
   `specification_validation: invalid_spec` or
   `specification_validation: unsupported`; raw validator exceptions and rejected
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

`max_revisions` is an integer from 0 through 3; its default is 1. Zero still runs
one planner/reviewer attempt. Ordinary success takes two model requests. Each
allowed revision can add two more, so the default allows at most four requests
and the maximum allows at most eight. A rejected local preview skips its reviewer
request and may therefore consume fewer calls.

`timeout_seconds` is finite, greater than zero and at most 180 seconds; its
default is 30. Every stage consumes the same monotonic deadline, and each remote
request receives only the remaining time. A revision does not reset the clock.
The engine's separate overall request deadline also remains in force. Custom
backends must respect their supplied timeout; the orchestrator cannot forcibly
terminate a backend that ignores it.

| Error code | Meaning and behavior |
| --- | --- |
| `invalid_interpretation` | Malformed/unknown/inconsistent proposal or review; stop without repair or execution. |
| `provider_failed` | Model transport or unexpected backend failure; stop with a safe retryable error. |
| `request_timeout` | Shared agent deadline expired; do not start another stage. |
| `agent_exhausted` | The allowed proposals never passed preview and semantic approval; stop with a safe retryable error. |
| `provider_input_limit` | Conversation, metadata, payload or schema bounds were exceeded; do not silently truncate required context. |

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

The agent tests use fake transports/backends and synthetic local fixtures. Run:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_sdk_agents.py tests/test_sdk_engine.py tests/test_sdk_provider.py tests/test_sdk_lookups.py tests/test_sdk_sessions.py tests/test_rahtal_sdk.py tests/test_sdk_web.py -q
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe examples/sdk_demo.py
.\.venv\Scripts\python.exe -m build
```

Checks cover generic registered domains, semantic revisions, necessary and
unnecessary clarification, local code-only feedback, malformed/unknown output,
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
executed no database queries. Live SQL Server execution with this new flow,
universal language understanding and real-data report correctness remain
unverified; those checks establish only the tested model scenarios.
