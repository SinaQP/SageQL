"""Command line entry point."""

import argparse
import sys
from pathlib import Path

from sageql.core import generate_sql
from sageql import chat_cli
from sageql.errors import GenerationError
from sageql.openai_provider import OpenAIProvider


def main(argv: list[str] | None = None) -> int:
    if argv is None:
        argv = sys.argv[1:]
    if argv and argv[0] == "chat":
        return chat_cli.main(argv[1:])

    parser = argparse.ArgumentParser(
        prog="sageql",
        description="Propose SQLite SQL or run 'sageql chat' to plan a report",
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


if __name__ == "__main__":
    raise SystemExit(main())
