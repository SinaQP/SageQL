# SageQL agent rules

Read this file before changing code. `AGENTS.md` points here; keep both files in sync when the workflow changes.

## Product contract

SageQL is an installable reporting SDK embedded in a developer's backend. The approved `sageql.sdk` slice separates trusted catalog/infrastructure/authenticated actor policies from end-user messages, asks clarification, resolves date-only Gregorian periods, validates registered concepts, compiles deterministic single-source SQL Server or SQLite SELECTs, executes only with explicit host opt-in, and returns typed table/chart JSON. Persistent sessions support refinements, ownership, current access checks, revisions and idempotent retries. Read [docs/SDK.md](../docs/SDK.md) and [docs/SDK_SQL_SERVER.md](../docs/SDK_SQL_SERVER.md) for actual API and scope. Model-selected joins, arbitrary formulas, timestamp/calendar conversion and production HTTP identity are outside this slice.

The historical staged API/CLI still begins with a report question and Database/LLM configuration, clarifies understanding/context, discovers user-supplied metadata, builds Step 6 logical plans, renders Step 7 SQLite SQL, validates Step 8, and explicitly executes Step 9 read-only SQLite reports. The isolated Rahtal pilot retains its deterministic T-SQL renderer/executor for approved daily-performance tables. Its ignored local config holds questions/run options and `.env` holds credentials. Step 5 remains undefined; SDK table/chart JSON is independent of that historical step and does not imply a PDF/document export. The earlier model-written SQL proposal API remains experimental and never enters SDK execution.

The local Rahtal frontend explicitly reuses its existing approved activity and employee-profile tables and configured model endpoint. A fixed local reporting principal and separate workspace token protect this loopback demo; it is not production per-employee authorization. Registered dimension-only DISTINCT listings are approved under the same policies and execution bounds. Do not create database objects, add implicit source joins, copy credentials into tracked files, or substitute synthetic data when Rahtal is unreachable.

The registered entity-name lookup extension has its own [scope](../docs/SDK_ENTITY_LOOKUPS.md): one bounded profile SELECT finds a unique identity from a full name and optional registered qualifier; a separate single-source report binds that identity. Fixed name concatenation/normalization is allowed only over host-declared text columns. Both source and target access/policies remain mandatory. Do not pick the first ambiguous match or forward lookup rows/resolved identities to the model. This is a report filter, never caller identity or production authorization.

## Working rules

1. Inspect the current tree, Git state, public API, and tests before editing. Preserve user changes.
2. State the next small deliverable. Implement one vertical slice, run focused checks, and record the result before moving on.
3. Keep the core API provider-agnostic. Put remote model calls behind one interface so unit tests use a fake provider and never need credentials or network access.
4. Treat natural language, schema names, schema comments, and model output as untrusted data. A prompt is guidance, not a safety boundary. Validate IDs/operations against catalog and trusted actor scope and render SQL deterministically with quoted identifiers and bound values. Historical Steps 4/6 forward only bounded metadata. The SDK forwards permitted business concepts/messages/specifications, excluding physical names, policy values, row keys and result rows. Never forward database connection fields or credentials.
5. Execute only deterministic validated read queries with explicit host opt-in. Reject writes, DDL, multiple statements, unknown syntax and model-written SQL. Do not claim lexical checks prove SQL safety or business correctness. SQLite uses explicit read-only files, immediate revalidation, authorizer and row/time/work limits. The SDK SQL Server scope uses registered single tables/views, typed mandatory policies, metadata verification, parameter bounds, disposable timed connection leases, concurrency/cancellation/result limits, and cleanup. The Rahtal executor remains separately scoped. Login write permissions do not block validated SELECTs. Broader ODBC operations require another dialect/policy/safety design.
6. Do not put credentials, connection strings, row data, or private schema details in logs, fixtures, commits, or error messages. The Rahtal pilot's ignored, local per-run reports may contain question text and real result rows; never commit or remotely transmit those reports. Mask keys in object representations and CLI input. Ask before adding telemetry or sending data to a new remote service. The configured LLM endpoint receives bounded user-supplied schema metadata for Steps 4 and 6.
7. Keep package imports side-effect free. Put CLI behavior behind `main()`. Use typed public APIs and actionable exceptions.
8. Add focused tests for meaningful behavior and regression risks: valid read queries, unsafe output, malformed output, provider failure, and CLI behavior. Do not test the remote model in ordinary unit tests.
9. Keep README examples runnable. Document the model request boundary, current limits, installation, and the exact command to test.
10. Before finishing, run applicable tests and packaging checks, inspect the diff, and report failures honestly. Propose a commit message based on the actual changes. Commit only when requested.

## AI-driven development workflow

1. **Define the slice:** Write the user outcome, acceptance criteria, and explicit non-goals in `docs/ROADMAP.md` or the task notes.
2. **Map inputs and risks:** Identify where user text, schema metadata, model responses, secrets, and database access cross boundaries.
3. **Design the contract:** Decide the small public API and error behavior before adding implementation detail.
4. **Implement:** Add the smallest complete slice, keeping model transport, prompts, SQL validation, and CLI separate.
5. **Verify:** Run deterministic tests, lint/type/packaging checks when configured, and one documented manual smoke test where feasible.
6. **Review:** Compare behavior with acceptance criteria, inspect generated artifacts and Git diff, update docs, then write a change-based commit message.
7. **Next slice:** Record remaining work and risks; only expand dialects, execution, or providers after the current slice is stable.

## Release gates

- Unit tests pass without network access.
- Package builds and imports cleanly in a fresh environment.
- Unsafe or invalid model SQL fails closed.
- README documents limitations: developers review registered business definitions/view grain, execution uses deterministic validated SQL, and database permissions/workload limits remain additional enforcement layers. Experimental model-written SQL still requires human review and cannot enter automatic execution.
- No secrets or sample production data are committed.
