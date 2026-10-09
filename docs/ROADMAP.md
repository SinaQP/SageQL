# SageQL roadmap

## Intent and clarification consistency correction (2026-10-08)

Outcome: a requested grouping change must be applied or explicitly reported as
unavailable; the last report must never silently replace that change. Independent
intent extraction precedes live agent planning. Local checks reject cross-source
concept combinations and candidate measures/grouping/presentation that disagree
with that extracted intent, even if a reviewer would approve them. Answered
clarifications must advance to a different missing detail or a report; the same
structured missing-detail key cannot be reissued as an answer continuation.

Acceptance: synthetic full conversations cover a table, bar refinement, supported
regrouping, unavailable regrouping, legacy pending technical confirmation,
paraphrased repeated questions, legitimate successive details, persistent restart,
idempotent retries and no database execution on rejected intent. All remote stages
share the existing deadline and permitted metadata boundary. Custom two-method
backends retain their existing contract; live OpenAI agents always extract intent.
No joins, new database objects, profile-based aggregation or calendar expansion
are introduced. Model intent extraction remains fallible; the deterministic
guarantee is consistency with its validated output, not universal language accuracy.

Verification: 810 offline tests passed and one opt-in SQL Server test was skipped.
The synthetic SDK embedding demo and JavaScript syntax check passed. The sdist
and wheel built successfully after installing the missing build backend into the
local development environment; a fresh virtual environment installed the wheel
and imported the public API, with runtime file hashes checked against source.

Interpretation-only checks with the existing configured model returned
`unsupported` for the original misspelled grouping request, its correction and
the legacy technical confirmation; no report database queries ran. A supported
table-to-bar check initially exposed the duplicate identity/name axis inherited
from the current specification. Local canonicalization now removes only a plain
identity whose target column matches its selected entity label. After that fix,
the same live check produced the expected employee-name bar with unchanged hours,
dates, ordering and limit. The failing attempts and final passing evidence remain
in ignored local files; these checks do not establish universal language accuracy.

The existing local host still needs a restart to load these changes. Automatic
tool approval rejected the stop/restart command with `blocked by policy`; that
command did not run. No database object or stored conversation was changed by
the manual verification, and no commit was created.

## Goal

Build an installable Python SDK that a developer embeds in their backend, configures with approved SQL Server datasets and infrastructure, and connects to their frontend so authorized users can create and refine reports through chat. Rahtal is a real-data integration test for that package.

The [embedded reporting architecture](ARCHITECTURE.md) records target contracts and acceptance gates. The first single-source SDK slice is implemented; [SDK.md](SDK.md) describes its actual API and limits. The historical steps below remain available; Step 5 remains undefined.

## Embedded SDK slice (implemented; live SQL Server verification pending)

**Outcome:** Install the SDK into an independent Python host and complete a frontend report conversation over a registered SQL Server table or reporting view, with a read-only SQLite reference for offline verification.

**Acceptance:** One facade and versioned reply/report contracts; trusted per-actor scope and row policies; resumable persistent sessions, idempotent requests and revision checks; registered aggregates/dimensions/filters; reproducible date-only Gregorian bounds; deterministic SQL Server compilation and metadata verification; bounded execution; truthful empty/truncated output; clarification and report refinements; a loopback reference frontend; no secrets, policy values or result rows in model requests; existing APIs and tests continue working.

**Non-goals for this slice:** Model-written SQL, model-selected joins, arbitrary expression formulas, cross-database reporting, timestamp timezone conversion, fiscal/Persian calendars, automated SQL Server security provisioning, production web authentication, and a final PDF/document layout. Broader capabilities remain separately scoped. The [SDK SQL Server execution design](SDK_SQL_SERVER.md) defines the adapter boundary; Step 5 remains undefined.

**Verification:** Offline tests cover real synthetic totals and frontend HTTP conversations, fake driver/provider boundaries, persistent clarification/refinement, policy enforcement, metadata drift, retries/concurrency, cancellation and resource cleanup. An opt-in SQL Server golden test requires a host-seeded synthetic dataset. Live provider/SQL Server and Rahtal verification are separate from these offline results.

## Live Rahtal frontend slice

**Outcome:** A local frontend uses the existing Rahtal SQL Server and configured model endpoint, including employee-name listings and activity-hour reports. The host reuses local credentials, owns one explicitly authorized local reporting principal, and exposes only the approved activity/profile columns. No database objects are provisioned.

**Acceptance:** A real interpreter selects distinct registered employee dimensions without a fake aggregate; mandatory soft-delete predicates and bounded SELECT execution remain enforced. The frontend clearly identifies Rahtal mode, accepts normal questions and refinements, and never silently falls back to synthetic data. Existing local/legacy Rahtal and sibling backend configuration can be used without copying secrets. Offline tests verify configuration, policies, listings and HTTP auth; live connectivity and conversation results are reported separately.

**Boundary:** This is a loopback, single-principal developer demo with access to approved Rahtal employee/activity data, not per-employee production authorization. Reports remain single-source: employee name listings use profiles and hours use activities with employee IDs. No model-selected joins, new reporting views, database writes or Jalali conversion.

**Live check (2026-10-05):** The existing configured model returned a valid employee-name listing without an aggregate and asked for the year on a September activity report. An authenticated HTTP conversation clarified the calendar for `1403`, then reached execution after `2025`. The local Rahtal host starts and rejects unauthenticated session requests. TCP and ODBC connection attempts to the configured SQL Server still time out; real rows, live metadata compatibility and report totals remain unverified. No synthetic fallback is used.

**Chat correction:** Assistant questions and explanations use registered readable labels and business language; technical concept IDs and report options stay in the structured specification. A straightforward employee-name request proceeds without asking the user to confirm internal options. Connection failures are identified before query execution and explain how to retry after restoring connectivity, while secrets and raw driver errors remain private.

**Correction verification:** A live interpreter replay of greeting → profiles → first and last names now clarifies the first two incomplete requests in business language and produces the correct name-list specification for the final request. Offline regressions verify readable labels, unchanged specification IDs, no query on failed connection, idempotent failure receipts and successful retry after connectivity returns. Live database reachability remains the separate blocker above.

**Local host ownership:** The frontend uses exclusive socket binding on Windows so two workspaces cannot share one port with different access tokens. A real occupied-port regression verifies that the second startup fails and preserves the running workspace's token file.

## Step 1: report-planning conversation (complete)

**Outcome:** The user enters a report question, supplies the configuration shown in the diagram, and can continue a conversation with an AI assistant about the desired report.

**Inputs**

1. A natural-language report question, followed by optional follow-up messages.
2. Configuration: Database → Server/Host, Database, Authentication method, ODBC Driver; LLM → API Key, Base URL, Model.

**Acceptance criteria**

- Python API and interactive CLI capture the first question and all configuration fields.
- A conversation keeps successful user/assistant turns in order and sends prior turns with each new question.
- Failed model calls do not enter the conversation history; the user can retry.
- The API key is masked in object representations and hidden when typed in the CLI.
- Database configuration is held locally and is not forwarded to the LLM.
- Offline tests verify the conversation, model adapter, and CLI. No database or model credentials are needed for tests.

**Boundary:** This step does not connect to the database, inspect its schema, generate SQL, or create a report. The existing SQL proposal API is an earlier experiment and remains available separately.

## Step 2: request understanding (complete)

**Outcome:** The AI determines what report the user wants. If the request is materially ambiguous, it asks one focused clarification question and reassesses the reply with full conversation history. Once sufficiently clear, the program prints a concise understanding and proceeds to Step 3.

**Acceptance criteria**

- The provider returns a structured decision: enough information, current understanding, and clarification question.
- A request ready for the next step prints `Request understanding` and proceeds to context resolution without generating a report.
- An incomplete request asks one question and preserves the conversation for the next assessment.
- Malformed or contradictory provider output fails closed; failed turns are not added to history.
- Offline tests cover ready, clarification, invalid output, and CLI behavior.

**Enough information:** The report's subject and intended result are identifiable, and any ambiguity that would materially change the report has been resolved. Optional presentation preferences can wait. Never invent missing details.

## Step 3: context resolution (complete)

**Outcome:** After request understanding, identify the user's time period, entities, metrics, filters, and comparison period. Ask one focused question when a material context detail is missing. Print the resolved context and proceed to Step 4.

**Acceptance criteria**

- A typed result contains all five fields. Absent optional filters and comparison periods remain empty.
- A ready result has a time period, including an explicit “all available data” choice; otherwise ask for it.
- The provider sees the request conversation and its understanding, but no database or LLM credentials.
- A material gap yields one clarification question; the answer is assessed with prior history.
- Ready context prints all five fields without connecting to a database or generating a report.
- Malformed or contradictory model output is rejected without advancing session history.
- Offline tests cover ready, clarification, invalid output, and CLI flow.

**Boundary:** Preserve relative time phrases such as “last quarter” as written. Converting them to exact dates requires calendar and timezone rules in a later step. Entity labels are business concepts, not verified database tables or columns.

## Step 4: query space discovery (complete)

**Outcome:** After context resolution, accept a structured catalog supplied by the package user and print relevant tables/views, columns, supplied relations, and definitions.

**Acceptance criteria**

- Accept a JSON catalog file through the CLI and the same JSON-shaped data directly through the Python API. Each table includes its columns; relations and definitions are optional.
- Consider every supplied table and column within the documented candidate limits, without silently dropping objects from the user's catalog.
- Keep schema objects in an immutable catalog and validate that columns and relations refer to real catalog objects.
- Bound the candidate metadata sent to the configured LLM. Never include server, database connection details, credentials, or row values in its request.
- Accept only IDs from the candidate catalog in the model's structured selection, rejecting unknown, duplicate, or inconsistent choices.
- Show the four categories and explicitly report when no relevant foreign keys or definitions were selected.
- Do not connect to the database in the current CLI flow. Existing Database configuration remains captured for later steps.
- Offline tests cover JSON input, model selection, invalid output, and CLI flow. No database is needed.
- `main.py --example` demonstrates the Python API from an inline question and schema dictionary; ordinary `main.py` arguments still start the interactive CLI.

**Boundary:** Relations and definitions come from the user's catalog; they are not inferred from a live database. No database connection, SQL generation, row access, or report creation occurs in this step.

## Step 5: not yet defined

The user has not specified Step 5. Do not assume its purpose or claim it has been implemented.

## Step 6: query planning (complete)

**Outcome:** Turn the understood request, resolved context, and selected query space into an ordered logical operation plan. Show how the plan was checked and which choices need review before SQL generation.

**Acceptance criteria**

- A Python API and the interactive CLI produce scan, supplied-relation join, time filter, business filter, aggregate, and comparison operations when needed.
- All table, column, and relation references are selected query-space IDs. Joins must extend a connected path from the base table.
- Every resolved metric and filter is mapped once. Numeric aggregates use numeric columns when types are known; time operations use temporal columns when types are known.
- A model proposal with unknown IDs, disconnected joins, missing mappings, or a conflicting explicit time grain fails before it becomes a plan.
- A malformed or structurally invalid model plan gets at most one correction request when the provider supports it. The correction contains validator feedback, not the prior model response; a second invalid plan fails closed. Provider and pilot policy failures do not trigger correction.
- The result keeps relative time and comparison phrases symbolic. The quality view marks date boundaries, calendar/timezone rules, metric formulas, inferred filter values, and comparison calculation for review when applicable.
- `main.py --plan-demo` runs a deterministic offline example through the real plan validator and quality review. `main.py --example` runs the full model-driven path.
- No database connection, SQL generation, row access, or report creation occurs in this step.

**Boundary:** Structural validity means the plan references the supplied schema consistently. It cannot establish that the supplied schema matches a live database or that the model chose the correct business meaning. Comparison operations are placeholders until date alignment and calculations are defined.

## Step 7: SQL generation (complete)

**Outcome:** Render the validated logical plan into readable, parameterized SQLite SQL and show it in the demo and interactive flow.

**Acceptance criteria**

- Render selected tables and supplied joins, time buckets, filters, dimensions, and aggregate measures deterministically; the model does not write the SQL string.
- Quote schema, table, and column identifiers; keep filter values and date boundaries in named bind parameters.
- Accept exact ISO start and exclusive end dates from the caller. Leave named parameters marked as required when dates remain unresolved.
- Render comparison periods as labeled base and comparison rows when requested, without inventing a delta calculation.
- Validate the generated statement as a single read-only SQLite query before returning it.
- `main.py --plan-demo` prints the SQL and parameters; offline tests execute it against synthetic in-memory SQLite tables and check the returned totals.
- The package does not open a production database connection or execute the generated report query.

**Boundary:** SQLite is the only Step 7 dialect. The configured ODBC driver does not select a dialect yet. Caller-supplied bounds, join semantics, metric formulas, and filter values still need business review. SQL with required date bindings is a template until those bindings are supplied.

## Step 8: validation and safety (complete for SQLite)

**Outcome:** Check a SQL candidate before execution; discard a bad candidate and regenerate once from the structured plan when possible.

**Acceptance criteria**

- Parse one SELECT-only SQLite statement and reject invalid, multiple, or write statements.
- Check the plan's tables, columns, and relations against the selected user-supplied query space.
- Require exact agreement with a fresh deterministic rendering of the plan, including bound values. This also prevents omitted filters and added references in SQL.
- Require every resolved metric and filter, plus any caller-specified `RequiredFilter`, to appear in the plan. Check explicit time, entity, and single-metric aggregation facts when they can be matched mechanically.
- Block unbound date parameters. Report unresolved business interpretation as review items rather than claiming it is proved by syntax.
- A supplied bad SQL candidate may be discarded and regenerated once; a bad plan, missing required filter, or missing dates fails closed.
- When the request explicitly says to use all base-table rows, convert proposed inner joins to left joins and show the repair. Validation blocks an unrepaired inner join for that case.

**Boundary:** Mechanical checks cannot prove a business definition, join cardinality, or the correctness of a model's interpretation of ambiguous language.

## Step 9: query execution (complete for SQLite)

**Outcome:** An explicit API call or `--execute-sqlite` flag runs the validated query on caller-chosen SQLite files and returns bounded rows.

**Acceptance criteria**

- Revalidate immediately before execution and never accept an existing read-write connection.
- Open the file using SQLite `mode=ro`; attach named schema files explicitly using the same mode; enable `query_only` and a restrictive SQLite authorizer.
- Permit reads only from supplied selected tables and columns and the functions used by the renderer. Deny writes, attachment, pragmas, and other actions from the report query.
- Bound returned rows, elapsed time, and SQLite virtual-machine work. Mark truncated results, close connections, and sanitize database errors.
- `main.py --plan-demo` creates a synthetic temporary database, executes the SQL read-only, prints rows, and removes the file. Tests cover validation failures, repair, authorization limits, and execution.

**Boundary:** SQLite is the only executable dialect. ODBC connection fields captured earlier are not used by Step 9. Read-only local file access does not replace database permissions or human review of report semantics. Report formatting is still a later step.

## Rahtal daily-performance integration pilot

**Outcome:** A person edits the ignored `sageql_rahtal/local_config.py` to set the question and run options, runs `sageql_rahtal/run.py`, and receives a unique Markdown and JSON report for each run. A tracked example config and `--question` file override support reuse. The report records input, model stages, schema discovery, plan and repairs, deterministic T-SQL, validation, timings, and bounded query results or the reason the run stopped.

**Acceptance criteria:** Verify the approved `Activities`, `User`, and `Person` catalog against live SQL Server metadata. Exclude nonapproved private fields. Keep database connection settings and rows out of model requests. Read question, mode, bounds, and limits from local config while keeping secrets in `.env`; reject malformed values and incomplete date pairs before model calls. Bound each model request and disable transport retries so endpoint stalls become timed failure reports. Apply activity and profile soft-delete policies in generated SQL. Revalidate the exact SQL and ordered parameters before execution. Allow a login with table-write permission to execute validated SELECT reports. Save reports on success, clarification, and failure. Offline tests cover policy SQL, local config, and both privileged and read-only logins; a manual smoke test uses real data only when available.

**Current finding:** The configured local Rahtal login has effective `INSERT`, `UPDATE`, and `DELETE` on the approved tables. A first live SELECT completed before this was discovered; the former permission guard blocked later execution with that login. The guard has been removed, while query validation remains in place. A later `--no-execute` run completed through SQL validation with the sample question and recorded a policy repair plus removal of unused joins. The default local-config run also completed through SQL validation on 2026-09-27 and saved a per-stage report. The local config and reports directory are ignored by Git.

**Clarification continuation:** The runner keeps the understanding and context sessions open while a terminal user answers focused questions. Each turn retains the original request and prior answers, records the provisional context locally, and resumes the same pipeline after a ready context. Offline tests cover multiple turns, validation and execution after clarification, and closed input. The session is in memory for one invocation; `/exit` and closed input save an incomplete report without querying data. SQL validation and execution guards remain unchanged.

## Later steps (require a specific user request)

- Add declared-grain safe joins, timestamp/calendar semantics and report export only as separately scoped slices.
- Define the historical Step 5 if the staged CLI needs it. SDK table/chart JSON already exists independently.

## Persian conversation and report defaults

Outcome: the embedded SDK and local reporting frontend default to Persian.
Acceptance: Persian model instructions cover greetings, clarification, refinements,
digits and letter variants; deterministic greetings/errors/titles and built-in
date headers use Persian; shipped catalogs use Persian business labels/units;
the browser uses RTL and Persian display digits without changing JSON values.
Hosts can explicitly select English for SDK/provider presentation. Offline tests
cover Persian multi-turn reports, literal Unicode filters, persistence/retries,
and unchanged authorization/SQL boundaries. No calendar conversion, translation
of arbitrary host labels or row values, new model endpoint, or broader SQL scope.

Verification (2026-10-06): 480 Python tests passed, 1 opt-in SQL Server test
skipped. Offline Chrome/Playwright checks passed for Persian RTL, exact decimal
display, Gregorian dates, tabs/history, retries and mobile width. The Persian
SDK embedding smoke test, isolated package build and fresh-wheel import passed.
The active development environment lacks `hatchling`, so `--no-isolation` is
unavailable there; the normal isolated build succeeds. Live configured model/
SQL Server Persian understanding had not yet been verified at that stage;
the employee-name check below records the subsequent live verification.

## Employee-name activity requests

Outcome: resolve a supplied employee name using the permitted profile source,
then run the approved activity report without asking for an internal employee ID.
The [scoped lookup design](SDK_ENTITY_LOOKUPS.md) defines registration, exact
normalized full-name matching, ambiguity, data boundaries and verification.
Acceptance includes unique/duplicate names, job qualifiers, Persian spacing and
letter variants, current source/target policies, bounded lookup reads, offline
regression tests and persistent name-based refinements/retries. No model-selected
join, new database object, fuzzy identity selection or broader activity columns.

Live verification (2026-10-06): the configured interpreter correctly selected
the employee-name filter, all three registered activity measures, `last_month`,
daily grouping and table for the user's Persian request. A first interpretation
returned invalid output and failed closed; a separate manual attempt succeeded.
Executing that validated specification against the configured SQL Server resolved
the name and returned 27 daily rows through separate profile/activity SELECTs,
without asking for an ID. No rows or derived identities were sent to the model;
production names and responses remain only in ignored local smoke-test files.

Offline verification (2026-10-06): 514 tests passed and 1 opt-in synthetic SQL
Server test was skipped. Lookup regressions cover actual SQLite totals, SQL
Server parameter/cleanup and diagnostic redaction boundaries, persistent
refinements, ambiguity, source/target policy changes and malformed adapter output.
The isolated sdist/wheel build and fresh-wheel import/public-contract/name
normalization smoke check passed.

## Name-lookup clarification progress

Outcome: a named employee activity request proceeds to the registered lookup
without asking for an internal ID or repeated permission to search by name.
Acceptance: interpret the original request and follow-up answers together;
correct an invalid ID/search-confirmation question once within the existing
provider deadline; validate the corrected specification through the ordinary
engine; stop safely if correction still stalls. Genuine missing dates/names and
host-generated missing/ambiguous-match questions remain available. Regression
checks use a fake model transport and policy-bound synthetic data. No new
lookup matching, SQL scope, identity exposure or external service is introduced.

Verification (2026-10-06): the focused provider/lookup regressions and full
offline suite pass; isolated sdist/wheel builds and the synthetic SDK embedding
smoke pass. The configured Rahtal model returned the expected complete daily
activity specifications for both a direct synthetic full-name request and a
conversation containing the prior mistaken ID/lookup questions followed by
«با اسمش». A request without a name asked for the missing name. These live
interpretation checks executed no database queries and do not establish live
report totals or universal model correctness. The running loopback host was
restarted with its existing configuration, workspace token and session store.

## Data boundaries

The historical chat provider receives conversation messages and model configuration. In Step 4 it also receives bounded table/column/relation metadata and definitions; Step 6 receives understanding, context and selected metadata. It does not receive database connection fields or row values. Historical CLI sessions are in memory. The SDK interpreter receives only permitted business metadata, messages and current report specifications; it omits physical names, policies and result rows. SDK session stores explicitly persist messages and report rows under host control.

## Rahtal local execution diagnostics

Frontend follow-up: put the existing trace in a separate **Steps & logs** tab
beside the report result. Keep each completed attempt available within the current
chat, with a readable stage timeline, durations, raw event details and a local JSON
download. Switching tabs or attempts must not submit a message or query data.
New chat clears the trace history; failures retain the latest successful result.
This slice consumes the existing redacted diagnostics only, adds no new backend
logging or telemetry, and does not implement historical Step 5 or live progress.

Verification (2026-10-06): offline Chrome/Playwright check passed for tabs,
keyboard navigation, attempt history, failure result retention, cached retries,
JSON download, text-only trace rendering, mobile width and other host modes.
The isolated package build passed. Full Python suite: 468 passed, 1 skipped,
5 failed on English-text expectations affected by concurrent Persian-language
changes outside this frontend slice. No live Rahtal/model query was run.

User outcome: inspect the test frontend's interpretation, validated report
conditions, deterministic SQL, execution stages, counts and safe failures.
Acceptance: authenticated Rahtal responses show an attempt trace; ignored local
JSON files record stage progress; empty results and cached replies are explained;
no credentials, personal filters or rows enter diagnostics, and no extra SQL is
executed. Other SDK/HTTP modes retain their contracts. This does not infer the
root cause of empty data or add policy-bypassing diagnostic queries.

## Bounded agent report interpretation

**Outcome:** Interpret user requests, clarification answers and refinements
through a planner and semantic reviewer over the permitted registered catalog.
The planner can reconsider a rejected proposal without a separate keyword or
regular-expression branch for every phrasing. The scoped contract and public
interfaces are documented in [SDK_AGENTS.md](SDK_AGENTS.md).

**Acceptance:** `AgentReportInterpreter` implements the existing `ReportProvider`
interface over a replaceable `ReportAgentBackend`; `AgentReview` carries a bounded
semantic judgment and `OpenAIReportAgent` uses the existing configured endpoint.
Each proposal passes strict shape/vocabulary checks and a local ready-report
preview before semantic review. A review rejection can produce a complete
revision; local semantic-validation feedback contains only fixed error codes.
Malformed output, extra SQL/code fields and unknown concepts fail closed rather
than being repaired. `max_revisions` is 0 through 3, default 1; at most eight model
requests share one deadline, default 30 seconds and bounded to 180 seconds.
Unapproved attempts end with safe `agent_exhausted` feedback. Fake transports and
synthetic fixtures cover budgets, context, data exclusion, count-only preview,
policy enforcement, persistent refinements and idempotent receipts.

**Boundaries:** The preview uses a policy-free synthetic scope only to check
permitted vocabulary and operations. Empty-column count-only projections use
private preview scaffolding that is neither serialized nor executed. The engine
still authorizes against the full trusted catalog/current actor policies,
resolves registered names locally, compiles deterministic SQL, and requires
explicit execution opt-in. No physical names, policies, credentials, rows or
resolved identities enter planner/reviewer requests. No model-selected joins,
arbitrary formulas, new objects, broader calendars, unrestricted database tools,
production authentication or historical Step 5 is introduced.

The live generic SQL Server web host and Rahtal SDK frontend select the new agent
provider. `OpenAIReportInterpreter` remains available for explicit compatibility;
the historical staged flow, isolated pilot runner and scripted demos retain their
existing behavior. Planning and review are separate requests to the same
configured model, so correlated mistakes remain possible. Extra requests add
latency and usage cost; neither semantic approval nor this scope promises that
every natural-language request is understood.

**Verification (2026-10-06):** All 79 focused agent tests passed; the full offline
suite passed with 642 tests and one opt-in synthetic SQL Server test skipped.
The isolated sdist/wheel build, fresh-wheel install/public agent imports and
documented synthetic SDK embedding smoke passed. Independent review found and
fixed typed Decimal/date filter compatibility; regressions cover custom agent
outputs and persistent switching from an existing provider.

The existing configured model completed two interpretation-only checks: a daily
request with a synthetic full name selected all three registered activity
measures, `last_month` and daily grouping; a greeting returned clarification.
Both used the new planning/review flow. These checks made no database calls and
transmitted no lookup results or production rows. Live SQL Server execution with
this flow and universal language correctness remain unverified.

## Rahtal request timeout increase (2026-10-07)

Outcome: give slow local Rahtal report requests more time to finish. Acceptance:
the shared model interpretation budget is 180 seconds, the overall request
deadline is 240 seconds, and each SQL execution is capped at 30 seconds.
Scope: only the Rahtal SDK frontend defaults; retain row bounds, deterministic
execution, policies and finite deadlines. Offline setup and HTTP tests verify
the integration; live model/database performance is not verified by these tests.

## Registered entity-label dimensions (2026-10-07)

Outcome: employee rankings can refine from IDs to names without changing their
measures, dates or top-N. Acceptance and boundaries are specified in
[SDK_ENTITY_LABELS.md](SDK_ENTITY_LABELS.md). Implement a host-registered display
dimension, policy-bound bounded post-aggregation reads, provider capability
metadata and Rahtal registration. Verify duplicates, missing/conflicting names,
access revocation, persistence, retries and model data exclusion. No joins,
new database objects, hardcoded conversation routing or broader authorization.

Verification: 682 offline tests passed, one opt-in synthetic SQL Server test
skipped. The isolated sdist/wheel build, fresh-wheel installation/imports and
documented SDK demo passed. The configured real model replayed the supplied
name-refinement/confirmation conversation, preserving its existing activity-hours
metric, descending order and top ten. Real Rahtal execution returned ten named
rows through two bounded SELECTs, with unchanged metric values/order and no
missing labels; no production names/rows were printed or sent to the model.
A separate new ambiguous-ranking check eventually requested criterion/period;
another attempt exhausted the bounded review loop. These checks demonstrate the
tested behavior, not universal natural-language reliability. Existing user
timeout changes were retained. No commit was created.
The existing loopback frontend was restarted with its original workspace token
and persisted session store; `/config` confirms authenticated Rahtal mode on
port 8766. Start a new chat for the updated catalog.

## Rahtal company report 2: complete conversations and explicit Jalali months (2026-10-08)

Outcome: show each manager conversation through its final real SDK result, replay
the two questioned examples, and add more complex reports using Persian months.
The first report separated clarification and completion onto different pages;
both quoted conversations had successful later turns. Presentation now keeps
the full conversation and its final status together.

The scoped implementation adds local deterministic `jalali_month` resolution
under [SDK_JALALI_MONTHS.md](SDK_JALALI_MONTHS.md), explicit selection provenance
and persisted refinements. Model prompts select month/year; they never convert
dates. Gregorian storage/daily buckets, policies and deterministic SQL remain.
A narrowly classified ordering inconsistency can consume the existing bounded
agent revision budget; malformed/unknown output still fails closed. Planner-only
reproductions established a strict ordering rejection, not token truncation;
the exact subtype of the historical failures cannot be proven from saved traces.
Verification and live evidence are recorded below when the slice is complete.

Additional planner-only diagnosis of the original Gregorian two-month comparison
reproduced `invalid_interpretation` with `finish_reason=length`, 4,096 completion
tokens, 4,096 reasoning tokens and zero output bytes. That concrete replay
exhausted the output budget; it does not establish a single cause for every
historical failure. The named-employee Jalali comparison's separate planner
replay passed strict validation with 4,036 completion tokens (3,904 reasoning);
a subsequent full-interpretation attempt stopped at planning with the same
4,096-token reasoning-only exhaustion, before any reviewer request. These
diagnostics executed no database query and retained only fixed structural
categories, counts and source hashes in ignored local report-2 files.

The Rahtal host now explicitly supplies `max_output_tokens=8192`; generic SDK
defaults, the shared 180-second interpretation deadline, the 240-second request
deadline, strict decoding and revision limits remain unchanged. Fake transport
tests verify that empty length-exhausted output still fails without replanning;
host setup tests verify the explicit budget. This adds no generic retry and
does not accept partial model output or enable any new query operation.

Business-intent QA then found a distinct semantic issue in the monthly all-data
top-24 example: a model-selected date range excluded the current partial month
and the last day of September. Report-ready status and strict SQL validation do
not establish business correctness. Shared planner/reviewer guidance now keeps
output limits separate from periods: explicit all-data requests retain `all`,
and latest-N groups use ordering/limit rather than invented dates. No keyword
router or model-data feedback is introduced. A local scenario acceptance audit
checks requested measures, effective periods, grouping, ordering and limits;
the full demonstration is rerun after this prompt correction.

Final verification: 772 offline tests passed and one opt-in synthetic SQL Server
test was skipped. The documented synthetic SDK embedding demo passed. Independent
Node Intl checks matched 7,200 Jalali boundary conversions with no differences.
The label-leak test now checks exact scalar identities rather than accidental
identity substrings inside randomly generated report UUIDs.

The final live run contains 11 completed scenarios and 21 actual turns: 15 report
responses, three clarification responses and three failed attempts. The three
failures were followed by explicit new attempts with identical manager messages
in the same sessions; their errors and receipts remain in the report. All five
run archives retain 59 turns, including two earlier report-ready responses with
incorrect business periods. Final acceptance passed 401 scenario-intent checks,
46 numerical checks and 142 evidence-selection checks. These are demonstration
acceptance checks, not a universal language-correctness guarantee or a new SDK
automatic retry mechanism. Further work should measure planner/reviewer semantic
accuracy and failure rates across a broader held-out set.

The reviewed company report has 35 pages, with all pages visually inspected;
native Persian HTML and a UTF-8 transcript accompany the PDF for reliable copying.
Real local evidence, session receipts, source snapshots and replay scripts remain
ignored and contain no bundled credentials. Two isolated packaging attempts were
blocked while obtaining hatchling from PyPI; a current wheel/fresh-install check
is therefore unverified. Source imports and tests do not substitute for that
release gate. No commit was created.

## Registered relationships and general management reports (2026-10-09)

User outcome: management reports can aggregate a fact's measures by explicitly
registered attributes from other sources, refine them in conversation, and rank
the final groups. Implement the reusable contract in SDK_RELATIONSHIPS.md;
register the existing Rahtal activity/profile relationship as a host integration.
Also resolve parameterized rolling date windows locally rather than asking the
model to calculate three-month date arithmetic. Preserve previous local changes.
No model-written SQL, guessed joins, new database objects, unregistered formulas
or promise of unlimited report capabilities. Verification results follow below.

Implemented reusable host registrations, composite equality keys, independent
dimensional sources, source-aware permission pruning, unambiguous business-intent
equivalences, deterministic guarded SQL Server/SQLite compilation, physical
metadata checks on all active sources and persistent conversation refinements.
Added typed post-aggregate conditions and locally resolved rolling Gregorian
count/unit windows. Rahtal imports current position and its filter on activities;
it creates no database objects. Existing local edits were preserved.

Verification: 51 new focused tests passed; the final offline suite passed with
861 tests and one opt-in synthetic SQL Server test skipped. The existing
synthetic embedding demo and git diff whitespace check passed. Live configured
model checks selected the correct rolling window/ranking, refined to job
position, and added the >100-hour aggregate condition. A canonical real Rahtal
SQL Server report passed with five groups and no truncation; private rows and
credentials were not printed or copied into tracked artifacts.

The isolated package build could not obtain hatchling from PyPI because of
network read timeouts. Building sdist and wheel with the installed build runtime
(`--no-isolation`) succeeded. A fresh wheel target installation and public
imports passed using the existing dependency runtime; a fully fresh dependency
environment remains unverified. No commit was created.

Suggested commit message for this extension:
`feat(sdk): add registered relationships, aggregate filters, and rolling periods`

## Align effective intent periods with necessary clarification (2026-10-09)

The exact reported job-position request matched failed receipts in a fresh local
session (revision zero, no messages/current report). The persisted trace records
intent_mismatch but does not retain stage proposals, so historical rejected
outputs are not reconstructed. Interpretation-only replay exposed a second
failure: the intent omitted period and missing details, and planner/reviewer
accepted all dates without user evidence. The old intent prompt required periods
for new rankings while planning required them for any dated aggregate.

Add an effective typed PeriodSelection to ReportIntent and share the dated
aggregate requirement across intent/planning/review. Locally add a period missing
slot if a new dated aggregate has no period; inherit the current period only for
same-dataset refinements/answers without a changed time clarification. Check
accepted ready periods against effective resolved bounds. Preserve focused year/
calendar questions, all-data requests, timeless counts, dimension-only listings
and normal revision/time/access boundaries. No question-specific routing, relaxed
intent guard or database operations are added.

Verification: 874 offline tests passed and one opt-in synthetic SQL Server test
was skipped. Configured-model replay returned the necessary clarification, then
selected job-position grouping and a three-month rolling period after the answer.
The active loopback host on port 8768 was restarted with its existing workspace
token and persistent sessions; the separate host on 8766 was left running.
The same two-turn HTTP conversation returned clarification without SQL, followed
by a real SQL Server report with six groups and no truncation. Saved original
period selection and the conversation's intentionally frozen date bounds were
both verified; no result rows or credentials were printed or added to tracked
files.

The current sdist/wheel build passed using the installed build runtime with
`--no-isolation`; fresh wheel-target installation and public typed-period imports
passed using existing dependencies. The earlier isolated build's network timeout
still leaves a completely fresh dependency environment unverified. Diff whitespace
checks passed. No commit was created.

Suggested commit message:
`fix(sdk): align intent periods with aggregate clarification`

## Increase the live reporting budget (2026-10-09)

User outcome: allow complex live report interpretation more time and repair
opportunities. The latest local failed trace ended in agent_exhausted after
about 77 seconds, before its 180-second deadline. Raise Rahtal's shared model
budget to 600 seconds, its overall request to 660 seconds and revisions from one
to three. Extend trusted SDK model-timeout acceptance to 600 seconds and overall
request limits to 900 seconds; keep query limits independently capped at 300
seconds and Rahtal SQL at 30 seconds. Default generic SDK budgets, strict report
checks, transport no-retry settings and finite repair/deadline behavior remain.
Verify the higher boundaries and shared deadline with offline fake transports,
then activate the existing local host while preserving its token/session state.

Verification: 266 focused tests and the complete 882-test offline suite passed;
one opt-in synthetic SQL Server test was skipped. A fake clock exercised four
proposals/three revisions over 480 seconds while preserving the decreasing shared
deadline. Transport tests verified the 600-second timeout with automatic retries
disabled; overall request and independent SQL bounds were checked. Current
sdist/wheel builds passed with the installed build runtime (`--no-isolation`),
and fresh wheel-target imports passed using existing dependencies. A completely
fresh dependency environment remains unverified after the previously recorded
network failures. The host on 8768 was restarted with the existing token and
sessions; authenticated access to a saved session passed. No live semantic report
replay was run in this timeout-only slice, and larger budgets do not guarantee
semantic agreement. Diff whitespace checks passed. No commit was created.

Suggested commit message:
`fix(rahtal): increase bounded report interpretation and repair budgets`

## Verify a managerial workload conversation (2026-10-09)

Outcome: compare Shahrivar/Mordad 1405 workload by current position, drill down
to employee names, select up to ten employees below 80 recorded hours in
Shahrivar, and show the same selection in a bar chart. The report describes
recorded workload and includes employees with activity, not productivity or
the complete roster. Acceptance and runnable local check are in
[SDK_MANAGEMENT_REPORT.md](SDK_MANAGEMENT_REPORT.md).

The configured model initially returned an incorrect unsupported claim about
two explicit Jalali months. Shared capability guidance and review of prose-only
unsupported claims corrected this case. Add bounded optional effective intent
controls for comparison, row/aggregate filters, ordering/direction and limit;
strict live decoding and fixed local feedback reject silent losses before
review/execution. Explicit empty controls remove earlier constraints, while
defaults preserve existing custom-backend compatibility.

Add a local live-check CLI with an independent Python arithmetic oracle over
bounded, policy-bound SDK source-grain reads. Private sessions/source/reply/spec
artifacts and HTML remain ignored and local. No result rows go to the model.
The frontend adds a managerial example and displays both comparison names and
execution ranges without changing stable JSON period row keys.

Independent review reproduced tied top-N drift when display dimensions were
reordered. Deterministic metric ranking now prioritizes entity-label identity
ties before other categories, preserving explicit primary ordering and time/
period ties. Regression coverage reverses employee/position column order with
more than ten equal-hour employees, then verifies the chart selects the same ten.

All four configured-model/real-SQL Server turns matched the local source oracle;
final compiler replay of those accepted specifications matched again without
new model calls. The final complete offline suite passed: 971 tests and one
optional synthetic SQL Server skip. JavaScript syntax, whitespace, installed-
runtime package builds and fresh-wheel-target imports passed; completely fresh
dependency installation was not checked. Interim Windows socket test aborts
passed on rerun and did not recur in the final complete suite.

Activated the updated authenticated frontend on port 8770 using separate private
state/token under `.venv/rahtal-management-web/`; existing hosts were preserved.
No database objects or writes, new remote service, credentials or private result
rows were added to tracked files. Existing changes were preserved; no commit.

Suggested commit message:
`feat: add verified Rahtal workload reports and preserve SDK intent`
