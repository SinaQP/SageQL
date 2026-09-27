# SageQL agent entry point

Before changing code, read [agent-rules/Agent.md](agent-rules/Agent.md). Follow its product contract, working rules, and verification workflow.

The current approved flow includes logical query planning, SQLite SQL generation, validation, and explicit read-only SQLite execution after query-space discovery. The isolated `sageql_rahtal/` pilot has a narrow SQL Server renderer and guarded executor for approved daily-performance tables only. Its ignored `local_config.py` holds questions and run options; credentials belong in `.env`. Step 5 has not been defined. Never run model-written SQL. Do not extend ODBC execution beyond the pilot without its own scope and safety design.

When reporting work, include a commit message based on the actual changes.
