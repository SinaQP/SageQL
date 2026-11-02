"""Command line entry point."""

import argparse
import sys
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path

from sageql.core import generate_sql
from sageql import chat_cli
from sageql.errors import GenerationError
from sageql.openai_provider import OpenAIProvider

DESCRIPTION = """\
SageQL is a reporting SDK you embed in a backend: a model turns a chat message
into a typed report spec, and SageQL authorizes, compiles and runs the SQL.
Models never write SQL. Start with 'sageql demo', then the embedding guide:
https://github.com/SinaQP/SageQL/blob/main/docs/SDK.md"""

LEGACY_NOTE = ("sageql: this command is the staged 0.1 workflow and moves to 'sageql legacy {}' "
               "in 0.3; it is separate from the SDK")


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "demo":
        from sageql import demo
        return demo.main(argv[1:])
    if argv and argv[0] == "legacy":
        return _legacy(argv[1:])
    if argv and argv[0] == "chat":
        print(LEGACY_NOTE.format("chat"), file=sys.stderr)
        return chat_cli.main(argv[1:])
    if argv and not argv[0].startswith("-"):
        print(LEGACY_NOTE.format("sql"), file=sys.stderr)
        return _legacy_sql(argv)

    parser = argparse.ArgumentParser(
        prog="sageql", description=DESCRIPTION, formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="commands:\n"
               "  demo           offline Persian report conversation on synthetic data (no API key)\n"
               "  legacy chat    staged 0.1 report-planning chat\n"
               "  legacy sql     experimental model-written SQLite SQL (never used by the SDK)",
    )
    parser.add_argument("--version", action="version", version=f"sageql {_version()}")
    parser.parse_args(argv)
    parser.print_help()
    return 0


def _legacy(argv: list[str]) -> int:
    if argv and argv[0] == "chat":
        return chat_cli.main(argv[1:])
    if argv and argv[0] == "sql":
        return _legacy_sql(argv[1:])
    print("usage: sageql legacy {chat,sql} ...", file=sys.stderr)
    return 2


def _legacy_sql(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="sageql legacy sql",
        description="Experimental: ask a model to propose SQLite SQL. Not part of the SDK.",
    )
    parser.add_argument("question", help="Natural-language question")
    parser.add_argument("--schema", required=True, type=Path, help="Path to schema text")
    parser.add_argument("--model", default="gpt-5-nano", help="OpenAI model name")
    args = parser.parse_args(argv)

    try:
        schema = args.schema.read_text(encoding="utf-8")
        provider = OpenAIProvider(model=args.model)
        result = generate_sql(args.question, schema, provider)
    except (OSError, ValueError, GenerationError) as exc:
        print(f"sageql: {exc}", file=sys.stderr)
        return 1

    print(result.sql)
    if result.explanation:
        print(f"\n{result.explanation}", file=sys.stderr)
    return 0


def _version() -> str:
    try:
        return version("sageql")
    except PackageNotFoundError:
        return "unknown"


if __name__ == "__main__":
    raise SystemExit(main())
