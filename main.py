"""Run SageQL's interactive report-planning conversation."""

from pathlib import Path

from dotenv import load_dotenv

from sageql.chat_cli import main as chat_main


def main() -> int:
    load_dotenv(dotenv_path=Path(__file__).resolve().parent / ".env", override=False)
    return chat_main()


if __name__ == "__main__":
    raise SystemExit(main())
