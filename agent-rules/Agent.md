# SageQL agent rules

Read this file before changing code. `AGENTS.md` points here; keep both files in sync when the workflow changes.

## Product contract

SageQL's end goal is report creation. The current user-approved workflow begins with the user's report question and accepts two configuration groups: Database (Server/Host, Database, Authentication method, ODBC Driver) and LLM (API Key, Base URL, Model). Assess whether the conversation contains enough information to understand the request, asking focused clarification questions as needed. Then resolve time period, entities, metrics, filters, and comparison period. Next, accept a structured table/column catalog from the package user and identify relevant tables, columns, supplied relations, and definitions. Step 6 builds a validated logical plan; Step 7 renders parameterized SQLite SQL; Step 8 validates the SQL against its plan, schema, required filters, and explicit request; Step 9 executes only on an explicitly chosen read-only SQLite file with bounded results and work. The isolated Rahtal pilot adds a deterministic T-SQL renderer and guarded SQL Server executor for its approved daily-performance tables. Its ignored local config holds the question and run options; `.env` holds credentials. Step 5 has not been defined. Do not claim a final formatted report was created. The earlier SQLite SQL proposal API remains experimental; never run its model-written SQL automatically.

## Working rules

1. Inspect the current tree, Git state, public API, and tests before editing. Preserve user changes.
2. State the next small deliverable. Implement one vertical slice, run focused checks, and record the result before moving on.
3. Keep the core API provider-agnostic. Put remote model calls behind one interface so unit tests use a fake provider and never need credentials or network access.
4. Treat natural language, schema names, schema comments, and model output as untrusted data. A prompt is guidance, not a safety boundary. Validate selected schema IDs against the metadata catalog, logical operations against the selected query space, and generated SQL separately before returning it. Build Step 7 SQL deterministically from the plan, quote identifiers, and bind values as parameters. Forward only bounded table/column/relation/definition metadata to the model for Steps 4 and 6; never forward database connection fields or credentials.
5. Default to read-only SQLite statements. Reject multiple statements, writes, DDL, transactions, pragmas, database attachment, and unknown syntax. Do not claim a lexical check is a complete SQL security sandbox. Step 9 SQLite execution requires an explicit SQLite path, a read-only URI connection, validation immediately before execution, a restrictive SQLite authorizer, and row/time/work limits. The Rahtal SQL Server pilot requires exact deterministic T-SQL, an approved catalog, revalidation before execution, and bounded execution. SQL Server login write permissions do not block a validated report query. Never silently execute model-written SQL. Other ODBC scopes need their own dialect and safety design.
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
- README documents limitations, including that generated SQL requires human review and database permissions remain the final enforcement layer.
- No secrets or sample production data are committed.
