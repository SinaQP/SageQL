# Embed SageQL in an application

The implemented `sageql.sdk` slice creates and refines reports over one registered SQL Server table or trusted view per dataset. The developer supplies configuration and authentication in their backend; the frontend submits messages, session IDs, request IDs, and revisions. Existing stage APIs and the Rahtal pilot remain available.

## Install and try it

Python 3.10+ is required. Install the local checkout into your backend environment:

```powershell
python -m pip install "E:\Coding\SageQL[openai,odbc]"
```

During development use `python -m pip install -e ".[openai,odbc,dev]"` from this repository. SQL Server also requires an installed Microsoft ODBC driver. The driver and connection string belong to the host configuration.

Run the complete offline embedding example or the frontend:

```powershell
.\.venv\Scripts\python.exe examples/sdk_demo.py
.\.venv\Scripts\python.exe examples/web/server.py --demo
```

The first command creates temporary synthetic data, asks a clarification question, produces a daily report, and refines it by employee. It checks tenant exclusion and exact expected totals. The second serves the chat UI at `http://127.0.0.1:8765`. See the [frontend guide](../examples/web/README.md) for live SQL Server setup. Both demos use a deterministic provider and make no remote requests.

## Configure the backend

This example expects an existing `reporting.activity_hours` view with the declared columns. The host must review its grain and formulas; it must not duplicate activity rows through joins.

```python
import os
import pyodbc
from sageql import Column, LLMConfig, SageQL, Table
from sageql.sdk import (
    AccessScope, ActorContext, DatasetAccess, DatasetDefinition,
    DimensionDefinition, FilterDefinition, MetricDefinition,
    OpenAIReportInterpreter, ReportingCatalog, RowPolicy, SDKError,
    SQLServerAdapter, SQLiteSessionStore, TimeDefinition,
)

table = Table("activity_hours", "reporting", kind="VIEW")
catalog = ReportingCatalog((DatasetDefinition(
    id="activities", label="Activities", table=table,
    columns=tuple(Column(table.key, name, kind) for name, kind in (
        ("tenant_id", "int"), ("employee", "nvarchar(200)"),
        ("activity_date", "date"), ("hours", "decimal(18,2)"),
        ("is_deleted", "bit"),
    )),
    metrics=(MetricDefinition("activity_hours", "Activity hours", "sum", "hours", "hours"),),
    dimensions=(DimensionDefinition("employee", "Employee", "employee"),),
    filters=(FilterDefinition("employee_filter", "Employee", "employee"),),
    time=TimeDefinition("activity_date"),
)),))

def policy(actor):
    if not actor.tenant_id.isdigit():
        raise SDKError("access_denied", "Authenticated tenant is required.")
    return AccessScope((DatasetAccess("activities", policies=(
        RowPolicy("tenant_id", "eq", (int(actor.tenant_id),)),
        RowPolicy("is_deleted", "eq", (False,)),
    )),), version="activity-policy-v1")

def connect():
    # A disposable handle, never an existing application transaction.
    return pyodbc.connect(os.environ["REPORTING_CONNECTION_STRING"], timeout=5)

engine = SageQL(
    catalog=catalog, database=SQLServerAdapter(connect),
    provider=OpenAIReportInterpreter(LLMConfig(
        api_key=os.environ["LLM_API_KEY"], base_url=os.environ["LLM_BASE_URL"],
        model=os.environ["LLM_MODEL"],
    )),
    policy=policy, sessions=SQLiteSessionStore("private-report-sessions.sqlite"),
    execution="validated",
)
```

Reporting IDs are simple identifiers, unique across metrics, dimensions, and filters within each dataset. `time_bucket` and `period_label` are reserved result IDs. Register only columns the adapter needs. The interpreter receives labels, business IDs, aggregate/type/unit information, available filters and time capabilities; physical names, row keys and policy-only columns are omitted from its request.

Use a dedicated reporting credential. The connection factory must bound login time and return a handle the adapter may roll back and close. The adapter verifies registered columns, compatible types and object kind before each report. It executes only its own deterministic parameterized SELECT. See the [execution scope](SDK_SQL_SERVER.md) for lifecycle, cancellation and database workload limits.

## Connect your frontend

Your authenticated endpoint obtains an `ActorContext` from trusted server identity, then calls these methods. Never construct the actor from browser-submitted tenant or user fields.

```python
actor = ActorContext(subject=authenticated_user.id, tenant_id=authenticated_user.tenant_id)
created = engine.create_session(actor)
payload = created.to_dict()

reply = engine.submit(
    session_id=created.session_id,
    message="Daily activity hours for September", actor=actor,
    request_id="client-generated-unique-id", expected_revision=created.revision,
)
payload = reply.to_dict()  # JSON-safe HTTP response, contract_version=1.

resume = engine.get_session(created.session_id, actor)
if reply.report:
    report = engine.get_report(created.session_id, reply.report.id, actor).to_dict()
```

`session_ready`, `needs_clarification`, `report_ready`, `unsupported`, `blocked`, and `failed` are the reply statuses. Every reply supplies `session_id`, `revision`, assistant text, optional clarification, optional report and optional safe error. A report supplies fields/units, rows, a table/bar/line/KPI specification, effective periods and provenance, plus truncation/completeness. Decimal values serialize as strings and dates as ISO strings; retain that precision in tables and treat chart numeric conversions as display approximations. Result rows are never sent to the interpreter.

After clarification or a successful report, submit the next message with the returned revision and a new request ID. On a lost HTTP response, retry the identical request with the same ID and expected revision. A completed retry returns the cached reply without another model or database call. A deliberate retry after a returned failure uses a new ID. Revision conflicts require reloading session metadata. Failed revisions preserve the previous successful report.

The built-in stores allow one active turn per session and retain the last 20 reports and 100 full request replies. Older IDs remain tombstones and return `request_retired`, so they cannot repeat execution. A session accepts at most 1,000 request IDs; create a new session after that limit. An expired turn returns an interrupted-request receipt; the package cannot infer whether a driver finished an interrupted read. Store files contain messages and report rows and require host-owned access, backup and retention rules. The package does not log transcripts or emit telemetry by default.

Successful report periods are frozen to explicit dates for later refinements. The host can inject `clock=lambda: ...` returning a `date` in its business timezone; the default is today's UTC date. A non-UTC `TimeDefinition` requires an explicit clock, since date-only storage has no timestamp conversion. Conversation history is bounded to 3–40 messages. Pending original requests and earlier clarification answers are carried forward as bounded context; if that context exceeds the configured message limit, start a new session with a complete question.

## Implemented scope

Metrics support `sum`, `count_rows`, `count_distinct`, `average`, `minimum`, and `maximum` where types permit. User and mandatory filters support equality, inequality, ordered comparisons, `in`, and null checks. Policies are independent of the model-selected filters. Date-only Gregorian periods support explicit ranges/months/years and current/previous days, weeks, months, quarters and years. Weeks start Monday; range ends are exclusive. Comparisons return labeled base/comparison rows as a table. Grouping, metric ordering and bounded top-N are supported; omitted dates are never inferred from an ambiguous month.

For a names/category list, use empty `metric_ids` with nonempty registered `dimension_ids`, `chart="table"`, `time_grain="none"`, and no comparison. The result contains distinct dimension combinations and still applies all current access policies, user filters and result bounds. Timeless sources use period `all`. The real model interpreter understands this listing shape; the offline keyword demo remains deliberately scripted. The [Rahtal frontend](../sageql_rahtal/README.md#local-frontend-on-the-real-database) connects existing approved sources and the existing model configuration.

Each report queries one registered table/view. Model-selected joins, arbitrary formulas, timestamp timezone conversion, fiscal/Persian calendars, calculated comparison deltas, exports and production HTTP authentication remain future work. The SQLite reference uses ISO date storage and SQLite numeric affinity; it does not guarantee SQL Server fixed-point arithmetic. SQL Server cancellation is cooperative and driver-dependent; row caps do not bound source aggregation work.

## Verify

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m build --no-isolation
```

Ordinary tests are offline. The optional SQL Server golden test is described in [the adapter tests](../tests/test_sdk_adapters.py); it requires an explicitly marked synthetic database and known seeded rows. It performs only reads and does not run the model. Rahtal remains a separate local real-data pilot with ignored credentials/config/reports. Offline success does not establish live provider or driver compatibility.
