r"""Runnable SageQL example.

From this directory:
    .\.venv\Scripts\python.exe main.py --example

The example uses EXAMPLE_SCHEMA below and the LLM settings in .env. Edit that
dictionary to supply your own tables, columns, relations, and definitions.
Running without --example starts the interactive CLI, which accepts a JSON file.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from sageql import (
    ChatConfig,
    ChatError,
    ContextResolutionSession,
    DatabaseConfig,
    DiscoveryError,
    LLMConfig,
    RequestUnderstandingSession,
    catalog_from_dict,
    discover_query_space,
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


def run_example() -> int:
    """Demonstrate the public API from question to selected schema objects."""
    api_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not api_key:
        print("Set LLM_API_KEY in .env or the environment before running --example.", file=sys.stderr)
        return 1

    try:
        # Database fields are part of the planned configuration, but Step 4
        # uses the supplied JSON catalog and never opens a connection.
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
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\nExample stopped before discovery completed.", file=sys.stderr)
        return 1
    except (ValueError, ChatError, DiscoveryError) as exc:
        print(f"sageql: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> int:
    load_dotenv(dotenv_path=ROOT / ".env", override=False)
    args = sys.argv[1:] if argv is None else argv
    if args in (["--help"], ["-h"]):
        print("Usage: python main.py --example")
        print("       python main.py --catalog PATH")
        print("       python main.py --no-discovery")
        return 0
    if args == ["--example"]:
        return run_example()
    return chat_main(args)


if __name__ == "__main__":
    raise SystemExit(main())
