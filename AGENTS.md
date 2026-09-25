# SageQL agent entry point

Before changing code, read [agent-rules/Agent.md](agent-rules/Agent.md). Follow its product contract, working rules, and verification workflow.

The current approved flow includes logical query planning, SQLite SQL generation, validation, and explicit read-only SQLite execution after query-space discovery. Step 5 has not been defined. Do not run model-written SQL or use the stored ODBC configuration to connect until an ODBC dialect and safety design are implemented.

When reporting work, include a commit message based on the actual changes.
