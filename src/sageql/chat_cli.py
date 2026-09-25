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
from sageql.report_validation import QueryValidationError, validate_report_query
from sageql.sql_generation import SQLGenerationError, SQLQuery, generate_sql_from_plan
from sageql.execution import QueryExecutionError, execute_sqlite_report
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


def _schema_paths(values: list[str]) -> dict[str, str]:
    paths = {}
    for value in values:
        name, separator, path = value.partition("=")
        if not separator or not name or not path or name in paths:
            raise ValueError("--sqlite-schema must be a unique NAME=PATH entry")
        paths[name] = path
    return paths


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sageql chat", description="Discuss a report request with an AI assistant"
    )
    parser.add_argument("--no-discovery", action="store_true", help="stop after context resolution")
    parser.add_argument("--no-planning", action="store_true", help="stop after query-space discovery")
    parser.add_argument("--no-sql", action="store_true", help="stop after logical query planning")
    parser.add_argument("--catalog", help="path to a user-supplied schema catalog JSON file")
    parser.add_argument("--period-start", help="inclusive ISO date for the report period")
    parser.add_argument("--period-end", help="exclusive ISO date for the report period")
    parser.add_argument("--comparison-start", help="inclusive ISO date for the comparison period")
    parser.add_argument("--comparison-end", help="exclusive ISO date for the comparison period")
    parser.add_argument("--execute-sqlite", metavar="PATH", help="execute on this SQLite file read-only")
    parser.add_argument("--sqlite-schema", action="append", default=[], metavar="NAME=PATH",
                        help="attach a named SQLite schema file read-only; repeat as needed")
    parser.add_argument("--max-rows", type=int, default=50, help="maximum rows returned when executing")
    args = parser.parse_args(argv)
    if args.execute_sqlite and (args.no_discovery or args.no_planning or args.no_sql):
        parser.error("--execute-sqlite requires discovery, planning, and SQL generation")
    if bool(args.period_start) != bool(args.period_end):
        parser.error("provide both --period-start and --period-end")
    if bool(args.comparison_start) != bool(args.comparison_end):
        parser.error("provide both --comparison-start and --comparison-end")

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
                    period_bounds = ((args.period_start, args.period_end)
                                     if args.period_start else None)
                    comparison_bounds = ((args.comparison_start, args.comparison_end)
                                         if args.comparison_start else None)
                    query = generate_sql_from_plan(
                        plan, period_bounds=period_bounds, comparison_bounds=comparison_bounds
                    )
                    _print_sql(query)
                    validation = validate_report_query(query, plan, resolution.context, space)
                    print("Validation:")
                    for check in validation.checks_passed:
                        print(f"  PASS: {check}")
                    for issue in validation.issues:
                        print(f"  BLOCK: {issue}")
                    if args.execute_sqlite:
                        if not validation.valid:
                            raise QueryValidationError("query must pass validation before execution")
                        result = execute_sqlite_report(
                            args.execute_sqlite, query, plan, resolution.context, space,
                            attached_schemas=_schema_paths(args.sqlite_schema),
                            max_rows=args.max_rows,
                        )
                        print("Read-only SQLite result:")
                        print("  Columns:", result.columns)
                        for row in result.rows:
                            print("  Row:", row)
                        print("  Truncated:", result.truncated)
                    else:
                        print("Execution: Not performed.")
        return 0
    except (EOFError, KeyboardInterrupt):
        print("\nChat ended.")
        return 0
    except (ValueError, ChatError, DiscoveryError, PlanningError, SQLGenerationError,
            QueryValidationError, QueryExecutionError) as exc:
        print(f"sageql: {exc}", file=sys.stderr)
        return 1
