"""Interactive report-planning chat CLI."""

import argparse
import getpass
import json
import os
import sys

from sageql.chat_provider import OpenAIChatProvider
from sageql.catalog_input import load_catalog_file
from sageql.conversation import ChatConfig, ChatError, DatabaseConfig, LLMConfig
from sageql.context import ContextResolutionSession, ResolvedContext
from sageql.discovery import DiscoveryError, QuerySpace, discover_query_space
from sageql.planning import PlanQuality, PlanningError, QueryPlan, create_query_plan, review_query_plan
from sageql.sql_generation import SQLGenerationError, SQLQuery, generate_sql_from_plan
from sageql.understanding import RequestUnderstandingSession


def _required_input(label: str) -> str:
    while True:
        value = input(label).strip()
        if value:
            return value
        print("Please enter a value.", file=sys.stderr)


def _configured_or_input(name: str, label: str) -> str:
    return os.environ.get(name, "").strip() or _required_input(label)


def _next_message() -> str:
    return _required_input("You> ")


def _print_context(context: ResolvedContext) -> None:
    print("Resolved context:")
    print(f"  Time period: {context.time_period or 'Not specified'}")
    print(f"  Entities: {', '.join(context.entities) or 'Not specified'}")
    print(f"  Metrics: {', '.join(context.metrics) or 'Not specified'}")
    print(f"  Filters: {', '.join(context.filters) or 'Not specified'}")
    print(f"  Comparison period: {context.comparison_period or 'Not specified'}")


def _print_query_space(space: QuerySpace) -> None:
    print("Query space discovery:")
    print("  Tables/views:")
    for table in space.tables:
        print(f"    {table.key} ({table.kind.lower()})")
    print("  Columns:")
    for column in space.columns:
        print(f"    {column.key} ({column.data_type})")
    print("  Relations:")
    for relation in space.relations:
        child = ", ".join(f"{relation.child_table}.{item}" for item in relation.child_columns)
        parent = ", ".join(f"{relation.parent_table}.{item}" for item in relation.parent_columns)
        print(f"    {child} -> {parent} [{relation.name}]")
    print("  Definitions:")
    for definition in space.definitions:
        print(f"    {definition.term}: {definition.meaning} ({definition.source})")
    if not space.relations:
        print("    No relevant supplied relations selected.")
    if not space.definitions:
        print("    No relevant definitions selected or available.")


def _print_plan(plan: QueryPlan, quality: PlanQuality) -> None:
    print("\nQuery plan (logical operations, no SQL):")
    print(json.dumps(plan.operations(), indent=2, ensure_ascii=False))
    print("Plan quality:")
    for check in quality.checks_passed:
        print(f"  PASS: {check}")
    for item in quality.review_items:
        print(f"  REVIEW: {item}")
    print("  Execution: Not performed.")


def _print_sql(query: SQLQuery) -> None:
    print("\nGenerated SQLite SQL (review before execution):")
    print(query.sql)
    print("Parameters:", dict(query.parameters))
    print("Required date bindings:", ", ".join(query.required_parameters) or "None")
    print("Execution: Not performed.")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sageql chat", description="Discuss a report request with an AI assistant"
    )
    parser.add_argument("--no-discovery", action="store_true", help="stop after context resolution")
    parser.add_argument("--no-planning", action="store_true", help="stop after query-space discovery")
    parser.add_argument("--no-sql", action="store_true", help="stop after logical query planning")
    parser.add_argument("--catalog", help="path to a user-supplied schema catalog JSON file")
    args = parser.parse_args(argv)

    try:
        first_question = _required_input("What report would you like to create? ")
        print("\nDatabase configuration")
        database = DatabaseConfig(
            server_host=_configured_or_input("DB_SERVER_HOST", "Server / Host: "),
            database=_configured_or_input("DB_NAME", "Database: "),
            authentication=_configured_or_input("DB_AUTHENTICATION", "Authentication method: "),
            odbc_driver=_configured_or_input("DB_ODBC_DRIVER", "ODBC Driver: "),
        )

        print("\nLLM configuration")
        api_key = (
            os.environ.get("LLM_API_KEY")
            or os.environ.get("OPENAI_API_KEY")
            or getpass.getpass("API Key: ")
        )
        base_url = os.environ.get("LLM_BASE_URL", "").strip()
        model = os.environ.get("LLM_MODEL", "").strip()
        if not base_url:
            base_url = input("Base URL [https://api.openai.com/v1]: ").strip()
        if not model:
            model = input("Model [gpt-5-nano]: ").strip()
        llm = LLMConfig(
            api_key=api_key,
            base_url=base_url or "https://api.openai.com/v1",
            model=model or "gpt-5-nano",
        )

        config = ChatConfig(database=database, llm=llm)
        provider = OpenAIChatProvider(llm)
        conversation = RequestUnderstandingSession(config, provider)
        print("\nRequest understanding started. Type /exit to finish.\n")
        pending = first_question
        while True:
            try:
                assessment = conversation.submit(pending)
                if assessment.enough_information:
                    print(f"Request understanding:\n{assessment.request_understanding.strip()}")
                    break
                print(f"AI> {assessment.clarification_question.strip()}\n")
            except ChatError as exc:
                print(f"sageql: {exc}", file=sys.stderr)

            pending = _next_message()
            if pending.lower() in {"/exit", "/quit"}:
                return 0

        context_session = ContextResolutionSession(
            config, provider, conversation.history, assessment.request_understanding
        )
        resolution = context_session.start()
        while not resolution.ready:
            print(f"AI> {resolution.clarification_question.strip()}\n")
            answer = _next_message()
            if answer.lower() in {"/exit", "/quit"}:
                return 0
            resolution = context_session.submit(answer)
        _print_context(resolution.context)
        if not args.no_discovery:
            catalog_path = args.catalog or os.getenv("SCHEMA_CATALOG_PATH", "")
            if not catalog_path:
                catalog_path = _required_input("Schema catalog JSON path: ")
            catalog = load_catalog_file(catalog_path)
            print("\nDiscovering query space from supplied schema...")
            space = discover_query_space(catalog, provider, assessment.request_understanding,
                                         resolution.context)
            _print_query_space(space)
            if not args.no_planning:
                plan = create_query_plan(
                    assessment.request_understanding, resolution.context, space, provider
                )
                _print_plan(plan, review_query_plan(plan, resolution.context, space))
                if not args.no_sql:
                    _print_sql(generate_sql_from_plan(plan))
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\nChat ended.")
        return 0
    except (ValueError, ChatError, DiscoveryError, PlanningError, SQLGenerationError) as exc:
        print(f"sageql: {exc}", file=sys.stderr)
        return 1
