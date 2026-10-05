# Reference reporting application

This dependency-free HTTP host demonstrates embedding `sageql.sdk` in an
application backend. The frontend asks business questions, answers clarification
questions, displays tables and charts, and refines the latest successful report.
The server supplies the catalog, authenticated actor, policies, provider, and
database adapter. Browser requests never configure database/model infrastructure
or tenant identity.

## Offline demonstration

For the actual Rahtal database with a real model, run:

```powershell
.\.venv\Scripts\python.exe sageql_rahtal/web.py --env-file E:\Coding\rahtal-be\.env --port 8766
```

Open `http://127.0.0.1:8766` and sign in using the local token saved to `.venv/rahtal-web/host-token.txt`. This registers the existing approved Rahtal profile/activity sources, not the generic sample view. See the [Rahtal guide](../../sageql_rahtal/README.md#local-frontend-on-the-real-database) for its configuration, scope and network requirements. `python examples/web/server.py --rahtal --env-file ...` is equivalent.

The `--demo` mode below is explicitly synthetic and scripted:

From the repository root, after installing the package:

```powershell
.\.venv\Scripts\python.exe examples/web/server.py --demo
```

Open [the local reporting workspace](http://127.0.0.1:8765). The demo creates a
temporary synthetic SQLite database and uses a deterministic interpreter. It
makes no model requests or production database connections. Stop it with Ctrl+C;
the temporary database is removed.

Try this conversation:

1. `Daily activity hours for September`
2. Answer the year clarification with `2026`.
3. `Group it by employee instead`
4. `Show the total as one number`

The first report contains September 1–15, 2026. The refined employee totals are
Alex: `81` hours and Sam: `52.5` hours. A separate tenant's `9999` hours and a
deleted activity's `8888` hours are synthetic test rows excluded by mandatory
server policies. Refinement retains the September period.

The offline interpreter supports this narrow activity-hour demonstration,
Gregorian named month/year periods, simple relative periods, grouping by day,
month, or employee, tables, and a total metric card. It deliberately declines
unavailable calculations and employee filtering. SQL Server mode uses the
configured model interpreter for the approved vocabulary.

## SQL Server host configuration

Install the optional adapters into the host environment:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[openai,odbc]"
```

The operating system also needs the SQL Server ODBC driver selected in your
connection string. Configure a developer-reviewed reporting table or view with
the following registered columns. The view must preserve one activity per row;
the host developer owns the meaning and grain of any joins inside that view.

| Column | Supported type | Purpose |
| --- | --- | --- |
| `id` | Integer | Activity row key |
| `tenant_id` | Integer | Mandatory authenticated tenant scope |
| `employee` | Text | Approved employee grouping and filtering |
| `activity_date` | SQL Server `date` | Gregorian business date |
| `hours` | Decimal | Registered sum of activity hours |
| `is_deleted` | Integer | Mandatory `0` active-record condition |

Export these settings in the host process before starting the server, or pass an
explicit local `--env-file`. The sample does not implicitly read `.env` files or
accept settings from the frontend. Exported process settings take priority over
the explicitly selected file.
Keep actual credentials in ignored local configuration or your host secret
manager.

| Setting | Required/default |
| --- | --- |
| `SAGEQL_SQLSERVER_CONNECTION_STRING` | Required; trusted ODBC connection string |
| `SAGEQL_HOST_TOKEN` | Required; 32–128 URL-safe letters, digits, `-`, or `_` |
| `SAGEQL_HOST_SUBJECT` | Required; authenticated principal's stable subject |
| `SAGEQL_HOST_TENANT_ID` | Required; the principal's integer tenant scope |
| `SAGEQL_REPORT_SCHEMA` | `dbo` |
| `SAGEQL_REPORT_TABLE` | `sageql_activities_view` |
| `SAGEQL_REPORT_KIND` | `VIEW`; use `TABLE` when registering a physical table |
| `SAGEQL_API_KEY` | Required; falls back to `LLM_API_KEY`, then `OPENAI_API_KEY` |
| `SAGEQL_BASE_URL` | `LLM_BASE_URL` fallback, then `https://api.openai.com/v1` |
| `SAGEQL_MODEL` | `LLM_MODEL` fallback, then `gpt-5-nano` |

Generate a local workspace access token in your host process, for example:

```powershell
$env:SAGEQL_HOST_TOKEN = .\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(32))"
```

Then start explicit SQL Server mode:

```powershell
.\.venv\Scripts\python.exe examples/web/server.py --sqlserver
```

To use an ignored local environment file explicitly:

```powershell
.\.venv\Scripts\python.exe examples/web/server.py --sqlserver --env-file .env
```

The existing project's `LLM_API_KEY`, `LLM_BASE_URL`, and `LLM_MODEL` settings are
accepted. The new host connection, principal, token, and reporting view settings
must still be supplied; the sample does not reuse Rahtal infrastructure silently.

The browser asks for the workspace access token. It sends it once to the local
host and receives an `HttpOnly`, `SameSite=Strict` session cookie. API clients may
instead send `Authorization: Bearer <workspace token>`. A successful sign-in
always maps to the configured server subject and tenant; neither the token body
nor chat text can select another tenant. The token is a reference host login,
not a database password or model API key.

The host binds only `127.0.0.1`; `--port` changes the local port. It rejects
unexpected Host/Origin headers, unsupported request fields, duplicate JSON keys,
non-finite JSON values, and bodies larger than 16 KiB. It limits concurrent POST
requests and returns safe errors. The model receives bounded permitted business
metadata and conversation text. Connection settings, mandatory policy values,
compiler-only columns, and result rows stay in the backend.

For production, integrate the engine into your application's own authenticated
HTTP framework. Replace this single-principal example with a trusted identity
lookup and policy callback on each request. The backend must establish identity
before calling `create_session`, `submit`, or `get_report`. Apply your own TLS,
login/session lifecycle, request budgets, storage permissions, and retention.
The engine independently checks session ownership, current authorization, and
report access. See [the SQL Server scope and lifecycle design](../../docs/SDK_SQL_SERVER.md).

## HTTP contract

Successful responses use the versioned `Reply.to_dict()` contract. The frontend
renders returned labels and values as text; chart configuration references report
field IDs and never contains executable code.

| Route | Input/outcome |
| --- | --- |
| `GET /config` | Public reference mode and whether sign-in is required |
| `POST /auth` | Rahtal and SQL Server modes: `{ "token": "..." }` |
| `POST /report-sessions` | Empty JSON object; returns a new session and revision `0` |
| `POST /report-sessions/{id}/messages` | `message`, `request_id`, `expected_revision` only |
| `GET /report-sessions/{id}` | Authorized resume revision, pending question, last report ID |
| `GET /report-sessions/{id}/reports/{report_id}` | Report after current ownership/scope checks |

The client retains the same `request_id` and revision when retrying a lost HTTP
response, so the SDK can return the original result without executing twice. A
completed retryable failure requires a new request ID. Failed refinements retain
the prior successful report. The reference frontend keeps its session in memory;
a reload starts a new conversation. Applications may configure a persistent
session store and implement their own resume and retention flow.

The chart presents at most 60 returned rows, with an explicit note when the table
contains more. It displays the actual returned decimal strings in tables and
metric cards; chart geometry uses approximate browser numeric values. Truncated
results are labeled incomplete, and empty reports say no matching data.

## Verification

Run the offline provider and HTTP conversation checks:

```powershell
.\.venv\Scripts\python.exe -m pytest tests/test_sdk_provider.py tests/test_sdk_web.py -q
```

These tests exercise the real orchestration, policy application, SQLite adapter,
JSON contract, clarification/refinement, duplicate requests, synthetic totals,
token authentication, origin controls, and request bounds. They do not connect
to SQL Server or call a remote model. SQL Server integration and Rahtal real-data
verification are separate checks.
