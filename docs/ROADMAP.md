# SageQL roadmap

## Goal

Create useful reports from a user request and a configured database. Build this in user-approved steps; report generation is a later step.

## Step 1: report-planning conversation (current)

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

## Later steps (require a specific user request)

- Connect to the configured database with explicit credential handling.
- Discover approved schema and develop report requirements against real data.
- Plan, validate, run, and format a report with appropriate access controls.

## Data boundaries

The chat provider receives conversation messages and model configuration. It does not receive database host, database name, authentication method, ODBC driver, or database credentials in this step. Conversation messages are kept in memory for the life of the session. The app does not persist them.
