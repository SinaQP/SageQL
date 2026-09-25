"""Interactive report-planning chat CLI."""

import argparse
import getpass
import os
import sys

from sageql.chat_provider import OpenAIChatProvider
from sageql.conversation import ChatConfig, ChatError, DatabaseConfig, LLMConfig, ReportConversation


def _required_input(label: str) -> str:
    while True:
        value = input(label).strip()
        if value:
            return value
        print("Please enter a value.", file=sys.stderr)


def _configured_or_input(name: str, label: str) -> str:
    return os.environ.get(name, "").strip() or _required_input(label)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="sageql chat", description="Discuss a report request with an AI assistant"
    )
    parser.parse_args(argv)

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

        conversation = ReportConversation(
            ChatConfig(database=database, llm=llm), OpenAIChatProvider(llm)
        )
        print("\nChat started. Type /exit to finish.\n")
        pending = first_question
        while True:
            try:
                answer = conversation.ask(pending)
                print(f"AI> {answer}\n")
            except ChatError as exc:
                print(f"sageql: {exc}", file=sys.stderr)

            pending = input("You> ").strip()
            while not pending:
                pending = input("You> ").strip()
            if pending.lower() in {"/exit", "/quit"}:
                return 0
    except (EOFError, KeyboardInterrupt):
        print("\nChat ended.")
        return 0
    except (ValueError, ChatError) as exc:
        print(f"sageql: {exc}", file=sys.stderr)
        return 1
