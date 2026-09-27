# SageQL

SageQL is a Python package for building reports step by step. The current flow starts with the user's report question, asks for clarification when needed, resolves context, selects relevant objects from a user-supplied schema catalog, plans database operations, generates and validates SQLite SQL, and can execute it against an explicitly selected SQLite file. Formatting returned rows into a report is a later step.

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

Supply the catalog path with `--catalog path/to/schema.json`, set `SCHEMA_CATALOG_PATH` in `.env`, or enter the path when prompted after context resolution. Without `--execute-sqlite`, the CLI prints SQL and validation but does not open a database connection.

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

For a locally configured daily-performance question against the Rahtal SQL Server database, use the isolated [Rahtal test app](sageql_rahtal/README.md). Edit its ignored `local_config.py` for the question and run options; credentials stay in `.env`. It saves a stage-by-stage report per run. The general SageQL CLI below remains SQLite-only; the pilot is the supported narrow SQL Server path.

## Current scope and privacy

- Conversation messages, request understanding, resolved context, and bounded user-supplied schema metadata go to the configured LLM endpoint. Planning sends the selected query space. Database host, database name, authentication method, ODBC driver, and credentials stay local. Do not use a model endpoint that should not see your schema names or descriptions.
- Context fields are the model's interpretation of the request. Step 4 verifies selected names against the supplied catalog. Step 6 validates references, joins, metric/filter coverage, and basic type/time-grain compatibility. If the request explicitly asks for all base-table rows, an inner join is changed to a left join and the repair is shown. Step 7 renders the plan deterministically. Step 8 checks the SELECT statement, selected tables/columns, required filters, explicit interpretation facts, and exact agreement with the plan. A bad SQL candidate is discarded and regenerated once with `prepare_report_query`; unresolved dates and missing required filters block execution. These checks cannot prove ambiguous business meaning, join cardinality, or that the supplied catalog matches the live file. Review those choices and use `RequiredFilter` in the Python API for mandatory tenant or policy conditions.
- The API key is hidden at the CLI prompt and masked in `LLMConfig` representations. SageQL keeps chat history in memory only; it does not save it.
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
