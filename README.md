# SageQL

SageQL is an embedded reporting SDK: authorized users ask for reports in chat
(Persian by default, English supported), and SageQL turns each request into a
validated, deterministic, parameterized SELECT over host-registered tables.
Models never write SQL, choose joins or see result rows.

**Status (2026-10-29).** The deterministic side (authorization, compilation,
read-only execution, sessions, snapshot reads) is solid and heavily tested
offline. Request understanding is the current bottleneck. The best measured cheap
setup is `gpt-5-mini` for intent, a locally compiled report spec and no reviewer
call, at low reasoning effort: 22/27 correct synthetic reports versus 8/27 for nano
alone, in about 7 s and one model call per typical turn ([comparison](docs/MODEL_COMPARISON_NANO_MINI.md)). Next steps are in the
[roadmap](docs/ROADMAP.md) and the [improvement plan](docs/IMPROVEMENT_RECOMMENDATIONS.md).

Tests are [SQLite-first](docs/SQLITE_FIRST_TESTING.md) and run offline with
synthetic data. Native SQL Server tests need an explicit pytest flag and a
separately approved synthetic target ([procedure](docs/SQLSERVER_INTEGRATION_TESTING.md)).
Production credentials and the Rahtal `.env` are never test inputs.

Saved reports re-run with zero model calls and moving dates ([saved reports](docs/SDK_SAVED_REPORTS.md)).

Key contracts: [embedding guide](docs/SDK.md), [agents and model settings](docs/SDK_AGENTS.md),
[SQL Server execution](docs/SDK_SQL_SERVER.md), [reliability](docs/SDK_RELIABILITY.md),
[read consistency](docs/SDK_READ_CONSISTENCY.md), [value vocabulary](docs/SDK_VALUE_VOCABULARY.md),
[release](docs/SDK_RELEASE.md). Offline evaluations: [evaluations/README.md](evaluations/README.md).

SageQL is a Python SDK that a developer embeds in their backend to let authorized users create and refine reports through chat. The host registers SQL Server tables or trusted reporting views, approved metrics/dimensions/filters, model infrastructure, and per-user access policies. SageQL interprets a report specification, validates it, generates parameterized SQL itself, and returns a typed table/chart payload for your frontend.

The new `sageql.sdk` API includes persistent conversations, clarification, report refinement, revision checks and idempotent retries. SQL Server is the production adapter target; SQLite supplies an offline reference. The [embedding guide](docs/SDK.md) documents installation, configuration, the JSON contract and limits. The [architecture](docs/ARCHITECTURE.md) records the broader design. The existing staged CLI/API and Rahtal real-data pilot remain available.

Live reference hosts use `OpenAIReportAgent`: independent intent extraction fixes
the effective measures/grouping, a planner proposes a report, a reviewer checks
its meaning, and bounded
feedback can revise the plan or clarification. Registered vocabulary checks
locally preserve explicit business measures and supported period selections;
the shared agents still plan and review reports. Register another catalog to
reuse the same pipeline.
Local checks reject unavailable cross-source combinations, silent grouping changes
and repeated structured clarification after an answer. Intent extraction remains
model-dependent. Authorization, lookup uniqueness and parameterized SQL execution remain enforced
by the SDK. See the [agent contract](docs/SDK_AGENTS.md) for configuration, call
budgets, limitations and custom backends.

The [registered relationship extension](docs/SDK_RELATIONSHIPS.md) supports
management reports across host-defined dimensional sources: multiple measures,
multiple related groupings/filters, aggregate thresholds, period comparisons and
rankings after complete aggregation. The same pipeline works with employee,
customer, product or organizational catalogs. Models never invent join keys;
duplicate dimension keys fail closed. Rolling date windows such as the last
three months resolve locally. Rahtal exposes current job position on activity
reports through this general registration API.

The fixed [participant-mean metric](docs/SDK_PARTICIPANT_MEANS.md) supports a
registered amount divided by distinct participating identities in the same group.
For example, Rahtal uses it for average recorded hours per participating employee,
while ordinary average activity duration keeps its own meaning.
Only trusted hosts register the source columns; models choose the business ID.

[Matching-day counts](docs/SDK_MATCHING_DAY_COUNTS.md) can accompany daily entity
reports: group registered measures, apply typed aggregate conditions, count the
remaining days per identity/period, then sort/limit and resolve names. Thresholds
and periods remain report inputs. The additive flag defaults to false, preserving
organization totals, comparisons, rankings and per-participant means.

Persian is the default conversation and report presentation language. The
reference frontend uses RTL, Persian labels and display digits. Ask naturally,
for example «نام کارکنان را نشان بده» or «ساعات فعالیت روزانه در سپتامبر ۲۰۲۶».
English input remains supported; hosts can explicitly select English output.
Register Persian business labels for your own datasets; see the
[language contract](docs/SDK.md#persian-by-default). Dates still use the approved
Gregorian storage and grouping. The [explicit Jalali month extension](docs/SDK_JALALI_MONTHS.md)
accepts a Persian month and year and resolves date bounds locally; broader Solar
Hijri grouping and timestamp conversion remain outside its scope.

## Try the embedded report flow

To use the **existing Rahtal SQL Server database and real model**, run:

```powershell
.\.venv\Scripts\python.exe sageql_rahtal/web.py --port 8766
```

Open `http://127.0.0.1:8766`. The server saves a local workspace token in `.venv/rahtal-web/host-token.txt`; use it in the sign-in dialog. This mode reads the registered existing employee/profile, activity and activity-topic tables and never falls back to synthetic data. It defaults to total recorded work and Persian business dates, including bounded monthly trends. See the [Rahtal frontend instructions](sageql_rahtal/README.md#local-frontend-on-the-real-database) and [manager reporting contract](docs/SDK_MANAGER_REPORTS.md). VPN access to the configured SQL Server is required when it is on the internal network.

The following offline commands exercise the same SDK using synthetic data and a scripted interpreter:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[openai,odbc,dev]"
.\.venv\Scripts\python.exe examples/sdk_demo.py
.\.venv\Scripts\python.exe examples/multi_domain.py
.\.venv\Scripts\python.exe examples/web/server.py --demo
```

Open `http://127.0.0.1:8765`, ask «ساعات فعالیت روزانه در سپتامبر», answer «۲۰۲۶», then request «به تفکیک کارمند نمایش بده». English versions of these requests also work. This uses synthetic data and a deterministic interpreter without credentials or remote calls. The [frontend guide](examples/web/README.md) also covers SQL Server mode. The first SDK slice queries one registered table/view per dataset; reviewed reporting views can contain business joins. Model-selected joins, arbitrary formulas, timestamp conversion, calendars beyond the explicit Jalali month extension and production authentication are outside this slice. The scripted offline demo does not interpret Persian month names; the configured model host supports the extension.

Registered dimension-only reports can list employee names without adding an aggregate. The sections below document the earlier staged workflow. Its experimental model-written SQL API is separate from the SDK engine.

The [application integration guide](docs/APPLICATION_INDEPENDENCE.md) documents
the reviewed boundaries and executable retail/library fixtures. Each host supplies
its own schema, business definitions, relationships and authenticated policies.
The same SDK produces sales totals, borrowing counts and loan-duration reports;
single-column product names/book titles and multi-column personal names use the
same bounded lookup contract. The offline examples use scripted providers.

Rahtal also resolves a supplied employee full name before filtering daily
activity reports. The host registers this lookup explicitly; users do not need
an employee ID. Duplicate names ask for job position, and each policy-bound read
still queries one source without joins. See the [lookup scope](docs/SDK_ENTITY_LOOKUPS.md).

Grouped activity reports and employee rankings can also display full names using
a host-registered `EntityLabelDimension`. The SDK ranks identities first, then
fetches names locally under profile policies; duplicate profiles cannot multiply
hours and names never enter model context. See the [display-label scope](docs/SDK_ENTITY_LABELS.md).

## Inspect planning, SQL, validation, and execution without an API key

Run the deterministic example to see a checked plan, parameterized SQL, validation results, and rows from a synthetic SQLite database:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e .
.\.venv\Scripts\python.exe main.py --plan-demo
```

The output lists operations, `PASS` and `REVIEW` checks, generated SQLite SQL and parameters, then two result rows. This mode uses the synthetic schema and fixed proposal in [main.py](main.py). It creates a temporary database, executes through the same read-only path as the public API, and removes the file afterward. It needs no model or credentials. Run `.\.venv\Scripts\python.exe -m pytest -q` to check valid and rejected plans.

## Run from `main.py`

Python 3.10 or newer is required. In PowerShell, from this repository:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[openai]"
Copy-Item .env.example .env
notepad .env
.\.venv\Scripts\python.exe main.py --example
```

Put your API key in the `LLM_API_KEY` field of `.env`. The example contains the AvalAI Base URL and `gpt-5-nano` model. `main.py --example` runs `EXAMPLE_QUESTION` through the public API using the inline `EXAMPLE_SCHEMA` dictionary, then prints the plan, generated SQLite SQL, and validation. Edit those two values in [main.py](main.py) to try your own case. The fixed example binds calendar year 2025 as `2025-01-01` through the exclusive end `2026-01-01`. It does not execute because no real database file is supplied. `.env` is ignored by Git, and existing shell environment variables take precedence over the file. The OpenAI extra is unnecessary for offline tests or a custom provider.

## Start a report conversation

Without `--example`, the main file starts the interactive CLI. It asks for your report question first, then uses the configuration from `.env` and prompts for missing fields. Run it with your catalog:

```powershell
.\.venv\Scripts\python.exe main.py --catalog my-schema.json
```

You can also run the installed CLI directly if you set environment variables yourself:

```powershell
sageql chat
```

The CLI first asks what report you want. It then collects these fields:

| Database | LLM |
| --- | --- |
| Server / Host | API Key |
| Database | Base URL |
| Authentication method | Model |
| ODBC Driver | |

If the request is unclear, answer the AI's clarification question at `You>`. Once understood, the program prints `Request understanding:` and resolves five context fields: time period, entities, metrics, filters, and comparison period. It asks another focused question if a material context detail is missing. A time period is required; “all available data” is a valid answer. Empty optional filters and comparison periods print as `Not specified`. Relative phrases such as “last quarter” are preserved, not converted to exact dates. Step 4 loads the catalog; Step 6 prints the plan; Step 7 prints SQLite SQL; Step 8 prints validation results. Step 9 runs only when you pass `--execute-sqlite`. Unresolved dates appear as required `:period_start` and `:period_end` bindings and block execution. Step 5 has not been defined. Type `/exit` to stop early. Use `--no-discovery`, `--no-planning`, or `--no-sql` to stop at an earlier step. Without environment overrides, the Base URL defaults to `https://api.openai.com/v1` and the model to `gpt-5-nano`. A custom Base URL receives your API key, so use an endpoint you trust.

Supply the catalog path with `--catalog path/to/schema.json`, set `SCHEMA_CATALOG_PATH` in `.env`, or enter the path when prompted after context resolution. Without `--execute-sqlite`, the CLI prints SQL and validation but does not open a database connection. If the model returns an invalid logical plan, planning can request one corrected proposal using validator feedback. The corrected proposal must pass the same checks before SQL generation or execution.

### Execute on a SQLite file

For a file whose tables match your catalog, provide exact date bounds and an explicit database path:

```powershell
.\.venv\Scripts\python.exe main.py --catalog schema.example.json `
  --period-start 2025-01-01 --period-end 2026-01-01 `
  --execute-sqlite path\to\your.sqlite `
  --sqlite-schema sales=path\to\your.sqlite
```

The sample catalog uses the `sales` schema name, so the command maps that name to a SQLite file. Omit `--sqlite-schema` for unqualified tables; repeat it for separate named schema files. The date end is exclusive. For comparisons, also pass `--comparison-start` and `--comparison-end`. The default result limit is 50 rows; set `--max-rows` up to 10,000. SageQL marks truncated results. It enforces a five-second and one-million-step query limit. These flags execute only SQLite SQL; the configured ODBC host, database, authentication, and driver are not used for this path.

### Schema catalog format

See [schema.example.json](schema.example.json) for a runnable synthetic example. The top-level `tables` array is required. Each table needs a `name` and nonempty `columns` array. `schema`, `kind` (`TABLE` or `VIEW`), and `description` are optional. Each column needs a `name`; `data_type`, `nullable`, and `description` are optional. An omitted data type is recorded as `unknown`. `relations` and `definitions` are optional:

```json
{
  "tables": [
    {
      "schema": "sales",
      "name": "orders",
      "columns": [
        {"name": "amount", "data_type": "decimal"},
        {"name": "ordered_at", "data_type": "date"}
      ]
    }
  ],
  "definitions": [
    {"term": "revenue", "meaning": "Define revenue for your own database here."}
  ]
}
```

For a relation, add `name`, `child_table`, `child_columns`, `parent_table`, and `parent_columns` as shown in the example file. Table references use `schema.table` (or just `table` when no schema is supplied). The arrays of child and parent columns must line up positionally. The parser rejects missing references, duplicate names, unexpected fields, and malformed JSON. It does not check whether supplied names match a real database yet.

Send at most 30 relevant tables, 500 total columns, 150 relations, and 200 definitions to one discovery request. SageQL rejects a larger candidate set rather than silently omitting supplied objects.

For the tested AvalAI configuration, set the non-secret defaults and let the CLI ask for the key privately:

```powershell
$env:LLM_BASE_URL = "https://api.avalai.ir/v1"
$env:LLM_MODEL = "gpt-5-nano"
sageql chat
```

## Python API

```python
import os

from dotenv import load_dotenv
from sageql import (
    ChatConfig,
    ContextResolutionSession,
    DatabaseConfig,
    LLMConfig,
    RequestUnderstandingSession,
    load_catalog_file,
    discover_query_space,
    create_query_plan,
    review_query_plan,
    prepare_report_query,
    execute_sqlite_report,
)
from sageql.chat_provider import OpenAIChatProvider

load_dotenv()
database = DatabaseConfig(
    server_host="not-connected",
    database="example",
    authentication="not-used",
    odbc_driver="not-used",
)
llm = LLMConfig(
    api_key=os.environ["LLM_API_KEY"],
    base_url=os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1"),
    model=os.environ.get("LLM_MODEL", "gpt-5-nano"),
)
config = ChatConfig(database=database, llm=llm)
provider = OpenAIChatProvider(llm)
conversation = RequestUnderstandingSession(config, provider)
assessment = conversation.submit(
    "Create a monthly report for 2025 showing the sum of sales.orders.amount "
    "grouped by sales.regions.name, using all orders and no comparison period."
)
while not assessment.enough_information:
    print(assessment.clarification_question)
    assessment = conversation.submit(input("You> "))
print("Request understanding:", assessment.request_understanding)

context_session = ContextResolutionSession(
    config, provider, conversation.history, assessment.request_understanding
)
resolution = context_session.start()
while not resolution.ready:
    print(resolution.clarification_question)
    resolution = context_session.submit(input("You> "))
print("Resolved context:", resolution.context)

catalog = load_catalog_file("schema.example.json")
space = discover_query_space(catalog, provider, assessment.request_understanding, resolution.context)
print("Tables:", [table.key for table in space.tables])
print("Columns:", [column.key for column in space.columns])
print("Relations:", [relation.name for relation in space.relations])
print("Definitions:", [definition.term for definition in space.definitions])

plan = create_query_plan(
    assessment.request_understanding, resolution.context, space, provider
)
quality = review_query_plan(plan, resolution.context, space)
print("Operations:", plan.operations())
print("Structural checks:", quality.checks_passed)
print("Review before SQL:", quality.review_items)

prepared = prepare_report_query(
    plan, resolution.context, space, period_bounds=("2025-01-01", "2026-01-01")
)
print("SQLite SQL:\n", prepared.query.sql)
print("Bind parameters:", dict(prepared.query.parameters))
print("Validation:", prepared.validation.checks_passed, prepared.validation.review_items)

# After supplying a real SQLite file whose tables match the catalog:
# result = execute_sqlite_report(
#     "path/to/your.sqlite", prepared.query, plan, resolution.context, space,
#     attached_schemas={"sales": "path/to/your.sqlite"},
# )
# print(result.columns, result.rows, result.truncated)
```

`conversation.history` contains successful user and assistant turns. You can inject another object with `assess(messages)`, `resolve_context(messages, understanding)`, `select_query_space(understanding, context, candidates)`, and `propose_query_plan(understanding, context, candidates)` methods to use a different provider or test offline.

## Rahtal live test pilot

For a locally configured daily-performance question against the Rahtal SQL Server database, use the isolated [Rahtal test app](sageql_rahtal/README.md). Edit its ignored `local_config.py` for the question and run options; credentials stay in `.env`. It saves a stage-by-stage report per run. The historical general CLI remains SQLite-only; the pilot and the separately scoped SDK adapter provide SQL Server paths.

## Current scope and privacy

- Conversation messages, request understanding, resolved context, and bounded user-supplied schema metadata go to the configured LLM endpoint. Planning sends the selected query space. Database host, database name, authentication method, ODBC driver, and credentials stay local. Do not use a model endpoint that should not see your schema names or descriptions.
- Context fields are the model's interpretation of the request. Step 4 verifies selected names against the supplied catalog. In Step 6 the model selects resolved metrics and filters by temporary IDs; SageQL restores their original phrases and validates references, joins, metric/filter coverage, and basic type/time-grain compatibility. If the request explicitly asks for all base-table rows, an inner join is changed to a left join and the repair is shown. Step 7 renders the plan deterministically. Step 8 checks the SELECT statement, selected tables/columns, required filters, explicit interpretation facts, and exact agreement with the plan. A bad SQL candidate is discarded and regenerated once with `prepare_report_query`; unresolved dates and missing required filters block execution. These checks cannot prove ambiguous business meaning, join cardinality, or that the supplied catalog matches the live file. Review those choices and use `RequiredFilter` in the Python API for mandatory tenant or policy conditions.
- The API key is hidden at the CLI prompt and masked in `LLMConfig` representations. Historical CLI history stays in memory. SDK stores explicitly persist messages and report rows under host-controlled permissions and retention.
- Definitions come from user-supplied descriptions and glossary entries. Relations come from user-supplied relation entries. SageQL does not invent business definitions or joins.
- The general CLI executes only with `--execute-sqlite`. It opens files with SQLite `mode=ro`, validates again, restricts reads with an authorizer, and caps returned rows and work. Filter and date values are bind parameters. A comparison-period operation yields labeled rows, while alignment and delta calculation still need definition. The separate Rahtal pilot supports its approved SQL Server scope; arbitrary ODBC schemas are not supported by that runner.
- The earlier experimental SQLite SQL proposal command is still available as `sageql "question" --schema schema.sql`, but it is separate from the report conversation.

## Development

Read [`agent-rules/Agent.md`](agent-rules/Agent.md) for the AI development workflow and [`docs/ROADMAP.md`](docs/ROADMAP.md) for the implementation slices.

```powershell
python -m pip install -e ".[dev]"
python -m pytest
python -m build
```

Live model comparisons are separately approved runs of the shared evaluation
runner; see `python -m evaluations.model_comparison --help` and
[the latest results](docs/MODEL_COMPARISON_NANO_MINI.md). Ordinary tests and
offline runs make no external model calls.
