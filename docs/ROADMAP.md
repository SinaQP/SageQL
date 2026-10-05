# SageQL roadmap

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

## Data boundaries

The historical chat provider receives conversation messages and model configuration. In Step 4 it also receives bounded table/column/relation metadata and definitions; Step 6 receives understanding, context and selected metadata. It does not receive database connection fields or row values. Historical CLI sessions are in memory. The SDK interpreter receives only permitted business metadata, messages and current report specifications; it omits physical names, policies and result rows. SDK session stores explicitly persist messages and report rows under host control.
