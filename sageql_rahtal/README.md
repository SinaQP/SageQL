# SageQL test app for Rahtal daily performance

This is a local test harness for the Rahtal `Activities`, `User`, and `Person` models. It uses only the approved columns of `dbo.functionality_activities`, `dbo.authentication_user`, and `dbo.persons_person`; the live SQL Server catalog is checked before the model sees metadata. The model receives the question and bounded catalog metadata, never the database connection or result rows.

## Run a question

1. Edit `sageql_rahtal/local_config.py`. Put your question in `QUESTION`, choose `RUN_MODE = "validate"` or `"execute"`, and optionally set date bounds, row limit, database timeout, model timeout, and paths. The working file is ignored by Git; [local_config.example.py](local_config.example.py) is the reusable template. You can set `QUESTION = ""` and `QUESTION_FILE = "question.txt"` to read a separate text file instead.
2. Copy [`.env.example`](.env.example) to `.env` and add a SQL Server login with access to the approved report tables and LLM settings. Alternatively, set `ENV_FILE` in local config or pass `--env PATH`. On this workstation, the runner also finds `D:\Coding\QuerySmith\rahtal\.env` if no local `.env` exists.
3. From the SageQL root, run:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[openai,odbc]"
.\.venv\Scripts\python.exe .\sageql_rahtal\run.py
```

In `local_config.py`, set `PERIOD_START` and `PERIOD_END` for a fixed database date range. The start is inclusive and the end is exclusive. A one-off command-line override also works:

```powershell
.\.venv\Scripts\python.exe .\sageql_rahtal\run.py --period-start 2026-01-01 --period-end 2026-02-01
```

Comparison questions also need `COMPARISON_START` and `COMPARISON_END`. The runner does not guess a calendar conversion or relative date boundaries. The default `RUN_MODE = "validate"` runs through SQL validation without reading result rows; set `"execute"` or pass `--execute` to run Step 9. `--no-execute` forces validation for one run. `--question PATH` overrides `QUESTION` with a UTF-8 text file, and `--config PATH` uses a different local config file. Relative paths written *inside* local config are resolved beside that file.

`LLM_TIMEOUT_SECONDS` caps each model request (default 60 seconds), and model transport retries are disabled so a slow endpoint produces a timed failure report. `TIMEOUT_SECONDS` is the separate SQL execution limit.

If the request or its context needs clarification, the runner prints one question at `AI>` and waits for an answer at `You>`. It keeps the original question and all answers in the same session, asks again when needed, then continues through discovery, planning, SQL validation, and optional execution. An empty answer repeats the prompt. `/exit`, `/quit`, or closed input ends the incomplete run with `needs_clarification`; no query is executed. Run the command again to start a new session.

Every run saves a unique Markdown and JSON report in ignored `sageql_rahtal/reports/`. The report includes the question, clarification turns and provisional context, stage timing/status, model understanding, resolved context, checked live catalog, selected query space, original plan proposal, repairs, logical operations, generated SQL and bind values, validation checks, and up to 100 returned rows. Failed and incomplete runs save reports too. The console prints clarification prompts when needed, then status, row count, path, and a safe error. **Reports contain real question text and potentially private result rows; keep them local and access restricted.**

The SQL Server adapter accepts only an exact deterministic SELECT built from a validated SageQL plan. It checks the selected tables and columns, inserts soft-delete policies (`activity.is_deleted = 0` in `WHERE`, and `person.is_deleted = 0` in the join), binds filter/date values, revalidates before execution, and limits returned rows and query time. A login with write permissions can execute a validated report query; SageQL does not execute write SQL. The runner has no per-user row authorization, so do not expose it as a user-facing service.

`Step 5` and final formatted report generation remain undefined. This app is a diagnostic pilot for stages 1–4 and 6–9. Quality items in its report call out semantic choices that SQL checks cannot prove. A completed run is evidence for that question and dataset, not proof that other questions are correct.
