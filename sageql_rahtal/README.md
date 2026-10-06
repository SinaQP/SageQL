# SageQL test app for Rahtal daily performance

The local SDK frontend defaults to Persian conversation, report labels/units and
RTL layout. Try «نام کارکنان را نشان بده» or «ساعات فعالیت روزانه در سپتامبر ۲۰۲۶».
The configured model receives Persian understanding/refinement instructions;
literal names and filter values remain exact. Dates stay Gregorian; Solar Hijri
calendar conversion is not part of this integration. The SDK and historical
model providers default to Persian prose; developer CLI/diagnostic machine
fields remain stable. See the [SDK language contract](../docs/SDK.md#persian-by-default).

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

## Local frontend on the real database

The new local frontend uses `sageql.sdk` with the existing Rahtal database and the configured real model interpreter. It does not use the offline keyword demo and does not create a reporting view or write database rows.

```powershell
.\.venv\Scripts\python.exe sageql_rahtal/web.py --env-file E:\Coding\rahtal-be\.env --port 8766
```

Open `http://127.0.0.1:8766`. Sign in with the generated local workspace token stored at `.venv/rahtal-web/host-token.txt`. The token protects the loopback reporting host and is separate from the database/model credentials. An explicitly configured `RAHTAL_HOST_TOKEN` (or process `SAGEQL_HOST_TOKEN`) takes precedence; optional `RAHTAL_HOST_SUBJECT` selects the trusted host principal. No principal or tenant may be supplied by browser requests.

The known configuration locations, when no `--env-file` is provided, are `sageql_rahtal/.env`, the SageQL root `.env`, the adjacent `rahtal-be/.env`, and the historical `D:/Coding/QuerySmith/rahtal/.env`. Set `RAHTAL_ENV_FILE` to select an explicit file. Exported `RAHTAL_*` settings override file settings. The sibling backend's existing `DB_HOST`, `DB_NAME`, `DB_USERNAME`, `DB_PASSWORD`, optional `DB_PORT`, `AVALAI_API_KEY`, and `AVALAI_BASE_URL` are mapped locally; its declared ODBC Driver 17 is the default for this format. A Rahtal-format file retains Driver 18 by default. Set `RAHTAL_LLM_MODEL` to override the default `gpt-5-nano` for the sibling format. Credentials are read from their original file and are never copied to tracked configuration.

Supported questions include:

- “Show my employees' names.” This returns distinct first/last name combinations from non-deleted profiles. Include employee IDs when different employees share a name.
- “Show employee names and job positions.”
- “How many employee profiles are there?”
- “Daily activity hours for September.” Answer the model's year clarification with a Gregorian year.
- “Show activity hours by employee ID for all available data.”
- “Now show the total instead.”
- «تمام اطلاعات فعالیت‌های روزانه کارمند موردنظر در ماه گذشته» with their full
  name. The host resolves the name and returns the registered daily measures
  (hours, count and average) without asking for an internal ID.
- If that full name matches multiple identities, answer the job-position
  clarification; the engine combines that qualifier with the original name.

Names and hours come from separate approved sources. A registered name lookup
performs a bounded profile SELECT first, then applies the unique employee ID to
the activity SELECT. Multiword surnames, spaces/ZWNJ and Arabic/Persian ي/ی, ك/ک
variants are handled by fixed exact normalized matching. Missing names ask for
correction; ambiguous matches ask for job position and never pick the first row.
Profiles are not assumed unique per user; DISTINCT identity lookup prevents
duplicate profiles from multiplying hours. Both reads independently enforce
`is_deleted = 0`, deadlines, metadata verification and result bounds. Names/IDs
returned by the lookup are not sent to the model. See the
[scope](../docs/SDK_ENTITY_LOOKUPS.md). Grouping all employees' hours by name still
needs a reviewed relationship/view design; this extension filters one employee.
Listing outputs and 'all information' remain limited to registered fields and
daily measures, not arbitrary source rows or unregistered activity descriptions.

Chat uses readable field labels such as “first name” and “last name.” If the host cannot connect to Rahtal, it explains the database/VPN connection failure and offers a retry; it does not claim a report query ran. Restore connectivity before retrying. Real database reports cannot be verified while the SQL Server endpoint is unreachable.

The host uses one fixed local administrator reporting principal with access to the approved Rahtal datasets. It binds only `127.0.0.1`, requires its workspace token, checks request origins, and cannot serve as production employee authorization. Private session state and report rows are saved under ignored `.venv/rahtal-web/`; protect and delete them according to local retention needs. The model receives permitted business metadata and conversation/specifications, never database credentials, physical table names, mandatory policy values or returned names/rows.

The live chat now uses `OpenAIReportAgent`. A planning request is followed by
semantic review on the same configured model; one revision is allowed within
the existing shared 45-second interpretation budget. Clarification review uses
the registered capabilities and conversation, rather than recognizing particular
employee-question phrases. Normal turns use two model calls; engine validation,
bounded name lookup and deterministic execution remain unchanged. See the
[agent scope](../docs/SDK_AGENTS.md). The historical pilot runner keeps its
separate staged provider.

The connection requires access to the configured SQL Server network. A VPN that only proxies browser traffic may not route this private database endpoint. A SQL login timeout is a connectivity failure; this mode never substitutes sample data. Gregorian date-only reporting is supported; ambiguous years such as 1403 require calendar clarification, and confirmed Jalali dates need Gregorian bounds until explicit conversion support is implemented.

### Local execution diagnostics

In the right-hand report panel, switch between **Report result** and
**Steps & logs**. After each chat turn, the logs tab shows the
interpreter outcome, validated dataset/concepts, redacted user filters,
mandatory soft-delete policy, resolved dates, deterministic compiled SQL,
connection/metadata checks, actual report SQL and ordered parameter types,
fetch counts, cleanup, errors, and stage durations. Expand a step to see its raw
events. Incomplete stages say “No completion recorded”; they are not shown as
successful. The **Attempt** selector retains clarification, refinement, failure
and retry traces for the current chat. **Download logs** saves the selected
redacted trace as JSON. A retry of a completed request is identified as a cached
reply and does not claim that SQL ran again. Logs appear after the response;
switching tabs, selecting attempts and downloading logs do not query the database.
The latest successful table/chart stays in the result tab after a failed turn.
New chat clears the browser's attempt list, and a reload starts a new conversation;
the private saved trace files remain available locally.

Each HTTP attempt also saves a unique JSON trace under
`.venv/rahtal-web/diagnostics/`, updated as stages progress. The trace ID shown
in the browser matches the filename. Logging is limited to the authenticated
local Rahtal test host; SDK reply/storage contracts and other host modes are
unchanged. Restart the server and reload the page after updating the checkout.

These explicitly requested local diagnostics include the deterministic report
SQL's physical identifiers. They exclude connection settings, credentials,
question/model text, personal filter values and returned rows. Ordered binds
show the result cap, booleans and date bounds; other scalar values are redacted.
Keep this ignored directory local and delete traces according to your retention
needs. Traces are never sent to the model or an external logging service. If
trace storage fails, the browser still receives diagnostics and reporting keeps
its normal behavior.

An empty result means the SELECT returned zero rows. The trace makes its source
and conditions inspectable; it cannot prove which condition caused the empty
result. No extra query removes policies or probes unrestricted data.

Offline verification:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_rahtal_sdk.py tests/test_sdk_web.py -q
```

Those tests use synthetic connections/providers. Live SQL Server and real-model checks must be reported separately.

`Step 5` and final formatted report generation remain undefined. This app is a diagnostic pilot for stages 1–4 and 6–9. Quality items in its report call out semantic choices that SQL checks cannot prove. A completed run is evidence for that question and dataset, not proof that other questions are correct.
