r"""Runnable SageQL example.

From this directory:
    .\.venv\Scripts\python.exe main.py --example
    .\.venv\Scripts\python.exe main.py --plan-demo

The example uses EXAMPLE_SCHEMA below and the LLM settings in .env. Edit that
dictionary to supply your own tables, columns, relations, and definitions.
The plan demo runs without an API key or external database. It creates a
temporary SQLite file for read-only execution and removes it afterward.
Running without --example starts the interactive CLI, which accepts a JSON file.
"""

import os
import json
import sqlite3
import sys
import tempfile
from contextlib import closing
from pathlib import Path

from dotenv import load_dotenv

from sageql import (
    ChatConfig,
    ChatError,
    ContextResolutionSession,
    DatabaseConfig,
    DiscoveryError,
    LLMConfig,
    PlanCandidates,
    PlanProposal,
    PlanningError,
    SQLGenerationError,
    QueryExecutionError,
    QueryValidationError,
    ProposedJoin,
    ProposedMeasure,
    QuerySpace,
    RequestUnderstandingSession,
    ResolvedContext,
    catalog_from_dict,
    discover_query_space,
    create_query_plan,
    review_query_plan,
    prepare_report_query,
    execute_sqlite_report,
)
from sageql.chat_cli import main as chat_main
from sageql.chat_provider import OpenAIChatProvider


ROOT = Path(__file__).resolve().parent
EXAMPLE_QUESTION = (
    "Create a monthly report for 2025 showing the sum of sales.orders.amount "
    "grouped by sales.regions.name, using all orders and no comparison period."
)
# Supply the table and column structure here. These names are synthetic.
EXAMPLE_SCHEMA = {
    "tables": [
        {
            "schema": "sales",
            "name": "orders",
            "columns": [
                {"name": "order_id", "data_type": "integer", "nullable": False},
                {"name": "region_id", "data_type": "integer", "nullable": False},
                {"name": "amount", "data_type": "decimal"},
                {"name": "order_date", "data_type": "date"},
            ],
        },
        {
            "schema": "sales",
            "name": "regions",
            "columns": [
                {"name": "region_id", "data_type": "integer", "nullable": False},
                {"name": "name", "data_type": "text"},
            ],
        },
    ],
    "relations": [
        {
            "name": "fk_orders_region",
            "child_table": "sales.orders",
            "child_columns": ["region_id"],
            "parent_table": "sales.regions",
            "parent_columns": ["region_id"],
        }
    ],
    "definitions": [
        {"term": "revenue", "meaning": "In this example, revenue is the sum of sales.orders.amount."}
    ],
}


def _answer(question: str) -> str:
    """Show one clarification question and collect the user's answer."""
    print(f"AI> {question}")
    while True:
        answer = input("You> ").strip()
        if answer.lower() in {"/exit", "/quit"}:
            raise EOFError
        if answer:
            return answer
        print("Please enter an answer, or type /exit.", file=sys.stderr)


def _show_plan(plan, quality) -> None:
    print("\nQuery planning operations (not SQL):")
    print(json.dumps(plan.operations(), indent=2, ensure_ascii=False))
    print("Plan quality:")
    for check in quality.checks_passed:
        print(f"  PASS: {check}")
    for item in quality.review_items:
        print(f"  REVIEW: {item}")


def _show_sql(query) -> None:
    print("\nGenerated SQLite SQL (review before execution):")
    print(query.sql)
    print("Parameters:", dict(query.parameters))
    print("Required date bindings:", ", ".join(query.required_parameters) or "None")


def _show_validation(validation) -> None:
    print("Validation:")
    for check in validation.checks_passed:
        print(f"  PASS: {check}")
    for item in validation.issues:
        print(f"  BLOCK: {item}")
    for item in validation.review_items:
        print(f"  REVIEW: {item}")


def run_plan_demo() -> int:
    """Show planning, validation, and read-only execution on synthetic data."""
    catalog = catalog_from_dict(EXAMPLE_SCHEMA)
    space = QuerySpace(catalog.tables, catalog.columns, catalog.relations, catalog.definitions)
    context = ResolvedContext(
        "monthly 2025", ("sales.regions.name",), ("sum of sales.orders.amount",), (), ""
    )

    class DemoProvider:
        def propose_query_plan(
            self, understanding: str, resolved: ResolvedContext, candidates: PlanCandidates
        ) -> PlanProposal:
            tables = {table.key: key for key, table in candidates.tables.items()}
            columns = {column.key: key for key, column in candidates.columns.items()}
            return PlanProposal(
                base_table_id=tables["sales.orders"],
                joins=(ProposedJoin(next(iter(candidates.relations)), tables["sales.regions"], "left"),),
                time_column_id=columns["sales.orders.order_date"],
                time_grain="month",
                dimensions=(columns["sales.regions.name"],),
                measures=(ProposedMeasure(
                    "sum of sales.orders.amount", "sum", columns["sales.orders.amount"]
                ),),
                filters=(),
            )

    print("Offline planning demo: a fixed proposal validated against EXAMPLE_SCHEMA.")
    try:
        plan = create_query_plan(EXAMPLE_QUESTION, context, space, DemoProvider())
        _show_plan(plan, review_query_plan(plan, context, space))
        prepared = prepare_report_query(
            plan, context, space, period_bounds=("2025-01-01", "2026-01-01")
        )
        _show_sql(prepared.query)
        _show_validation(prepared.validation)
        with tempfile.TemporaryDirectory(prefix="sageql-demo-") as folder:
            database_path = Path(folder) / "synthetic.sqlite"
            with closing(sqlite3.connect(database_path)) as connection:
                connection.execute("CREATE TABLE orders (order_id INTEGER, region_id INTEGER, amount DECIMAL, order_date DATE)")
                connection.execute("CREATE TABLE regions (region_id INTEGER, name TEXT)")
                connection.executemany("INSERT INTO regions VALUES (?, ?)", [(1, "North"), (2, "South")])
                connection.executemany("INSERT INTO orders VALUES (?, ?, ?, ?)", [
                    (1, 1, 10, "2025-01-15"), (2, 1, 20, "2025-01-20"),
                    (3, 2, 7, "2025-02-03"), (4, 1, 99, "2024-12-31"),
                ])
                connection.commit()
            result = execute_sqlite_report(
                database_path, prepared.query, plan, context, space,
                attached_schemas={"sales": database_path},
            )
            print("Synthetic read-only execution:")
            print("  Columns:", result.columns)
            for row in result.rows:
                print("  Row:", row)
            print("  Truncated:", result.truncated)
        return 0
    except (ValueError, PlanningError, SQLGenerationError,
            QueryValidationError, QueryExecutionError) as exc:
        print(f"sageql: {exc}", file=sys.stderr)
        return 1


def run_example() -> int:
    """Demonstrate the public API from question to generated SQLite SQL."""
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Set LLM_API_KEY in .env or the environment before running --example.", file=sys.stderr)
        return 1

    try:
        # Database fields are part of the configuration. This example uses
        # the supplied catalog and never opens a connection.
        database = DatabaseConfig(
            server_host=os.getenv("DB_SERVER_HOST") or "not-connected",
            database=os.getenv("DB_NAME") or "example",
            authentication=os.getenv("DB_AUTHENTICATION") or "not-used",
            odbc_driver=os.getenv("DB_ODBC_DRIVER") or "not-used",
        )
        llm = LLMConfig(
            api_key=api_key,
            base_url=os.getenv("LLM_BASE_URL") or "https://api.openai.com/v1",
            model=os.getenv("LLM_MODEL") or "gpt-5-nano",
        )
        config = ChatConfig(database=database, llm=llm)
    except ValueError as exc:
        print(f"sageql: {exc}", file=sys.stderr)
        return 1

    try:
        # Input: the package user supplies table/column structure above.
        catalog = catalog_from_dict(EXAMPLE_SCHEMA)
        provider = OpenAIChatProvider(llm)

        # Step 1: ask for a report. Step 2: clarify its meaning if necessary.
        understanding = RequestUnderstandingSession(config, provider)
        print(f"User request: {EXAMPLE_QUESTION}\n")
        assessment = understanding.submit(EXAMPLE_QUESTION)
        while not assessment.enough_information:
            assessment = understanding.submit(_answer(assessment.clarification_question))
        print(f"Request understanding: {assessment.request_understanding}\n")

        # Step 3: resolve time, entities, metrics, filters, and comparison period.
        context_session = ContextResolutionSession(
            config, provider, understanding.history, assessment.request_understanding
        )
        resolution = context_session.start()
        while not resolution.ready:
            resolution = context_session.submit(_answer(resolution.clarification_question))
        print(f"Resolved context: {resolution.context}\n")

        # Step 4: select only objects that exist in the supplied catalog.
        space = discover_query_space(
            catalog, provider, assessment.request_understanding, resolution.context
        )
        print("Selected query space:")
        print("  Tables:", [table.key for table in space.tables])
        print("  Columns:", [column.key for column in space.columns])
        print("  Relations:", [relation.name for relation in space.relations])
        print("  Definitions:", [definition.term for definition in space.definitions])

        # Step 6: plan operations. Step 5 has not been defined in this prototype.
        plan = create_query_plan(
            assessment.request_understanding, resolution.context, space, provider
        )
        quality = review_query_plan(plan, resolution.context, space)
        _show_plan(plan, quality)
        # This fixed example names calendar year 2025 explicitly. Other time
        # phrases need caller-supplied bounds before the query can be used.
        prepared = prepare_report_query(
            plan, resolution.context, space,
            period_bounds=("2025-01-01", "2026-01-01")
        )
        _show_sql(prepared.query)
        _show_validation(prepared.validation)
        print("Execution: Not performed; this example has no database file.")
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\nExample stopped.", file=sys.stderr)
        return 1
    except (ValueError, ChatError, DiscoveryError, PlanningError, SQLGenerationError,
            QueryValidationError) as exc:
        print(f"sageql: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    load_dotenv(dotenv_path=ROOT / ".env", override=False)
    args = sys.argv[1:] if argv is None else argv
    if args in (["--help"], ["-h"]):
        print("Usage: python main.py --example")
        print("       python main.py --plan-demo")
        print("       python main.py --catalog PATH")
        print("       python main.py --no-discovery")
        print("       python main.py --no-planning")
        print("       python main.py --no-sql")
        print("       python main.py --catalog PATH --period-start YYYY-MM-DD --period-end YYYY-MM-DD --execute-sqlite PATH [--sqlite-schema NAME=PATH]")
        return 0
    if args == ["--example"]:
        return run_example()
    if args == ["--plan-demo"]:
        return run_plan_demo()
    return chat_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
