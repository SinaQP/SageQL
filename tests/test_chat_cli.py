import builtins

from sageql import chat_cli
from sageql.understanding import RequestAssessment


def test_chat_cli_collects_question_then_config_and_followup(monkeypatch, capsys):
    prompts = []
    answers = iter(
        [
            "Sales report",
            "private-host",
            "private-db",
            "Windows",
            "ODBC Driver 18",
            "https://example.test/v1",
            "demo-model",
            "Last quarter",
        ]
    )

    def fake_input(prompt):
        prompts.append(prompt)
        return next(answers)

    class FakeProvider:
        def __init__(self, llm):
            assert llm.api_key == "secret"
            assert llm.base_url == "https://example.test/v1"
            assert llm.model == "demo-model"

        def assess(self, messages):
            if len(messages) == 1:
                return RequestAssessment(False, "Sales report", "Which dates?")
            return RequestAssessment(True, "Sales report for last quarter.", "")

    monkeypatch.setattr(builtins, "input", fake_input)
    monkeypatch.setattr(chat_cli.getpass, "getpass", lambda prompt: "secret")
    monkeypatch.setattr(chat_cli, "OpenAIChatProvider", FakeProvider)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    for name in ("DB_SERVER_HOST", "DB_NAME", "DB_AUTHENTICATION", "DB_ODBC_DRIVER"):
        monkeypatch.delenv(name, raising=False)

    exit_code = chat_cli.main([])
    output = capsys.readouterr()

    assert exit_code == 0
    assert prompts[0] == "What report would you like to create? "
    assert "AI> Which dates?" in output.out
    assert "Request understanding:\nSales report for last quarter." in output.out
    assert "secret" not in output.out + output.err


def test_chat_cli_requires_each_database_field(monkeypatch, capsys):
    answers = iter(["Report", "", "host", "db", "Windows", "driver", "", ""])
    monkeypatch.setattr(builtins, "input", lambda prompt: next(answers))
    monkeypatch.setattr(chat_cli.getpass, "getpass", lambda prompt: "secret")
    monkeypatch.setattr(
        chat_cli,
        "OpenAIChatProvider",
        lambda llm: type(
            "P", (), {"assess": lambda self, messages: RequestAssessment(True, "A report.", "")}
        )(),
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    for name in ("DB_SERVER_HOST", "DB_NAME", "DB_AUTHENTICATION", "DB_ODBC_DRIVER"):
        monkeypatch.delenv(name, raising=False)

    assert chat_cli.main([]) == 0
    assert "Please enter a value." in capsys.readouterr().err


def test_chat_cli_uses_llm_environment_defaults(monkeypatch, capsys):
    answers = iter(["Report", "host", "db", "Windows", "driver"])
    monkeypatch.setattr(builtins, "input", lambda prompt: next(answers))
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    for name in ("DB_SERVER_HOST", "DB_NAME", "DB_AUTHENTICATION", "DB_ODBC_DRIVER"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(
        chat_cli.getpass,
        "getpass",
        lambda prompt: (_ for _ in ()).throw(AssertionError("should not prompt for key")),
    )

    class FakeProvider:
        def __init__(self, llm):
            assert llm.api_key == "test-key"
            assert llm.base_url == "https://example.test/v1"
            assert llm.model == "test-model"

        def assess(self, messages):
            return RequestAssessment(True, "The requested report.", "")

    monkeypatch.setattr(chat_cli, "OpenAIChatProvider", FakeProvider)

    assert chat_cli.main([]) == 0
    output = capsys.readouterr()
    assert "Request understanding:\nThe requested report." in output.out
    assert "test-key" not in output.out + output.err


def test_chat_cli_uses_database_environment_values(monkeypatch, capsys):
    prompts = []
    answers = iter(["Report"])

    def fake_input(prompt):
        prompts.append(prompt)
        return next(answers)

    monkeypatch.setattr(builtins, "input", fake_input)
    monkeypatch.setenv("DB_SERVER_HOST", "host")
    monkeypatch.setenv("DB_NAME", "db")
    monkeypatch.setenv("DB_AUTHENTICATION", "Windows")
    monkeypatch.setenv("DB_ODBC_DRIVER", "driver")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")

    class FakeProvider:
        def __init__(self, llm):
            assert llm.model == "test-model"

        def assess(self, messages):
            return RequestAssessment(True, "The requested report.", "")

    monkeypatch.setattr(chat_cli, "OpenAIChatProvider", FakeProvider)
    assert chat_cli.main([]) == 0
    assert prompts == ["What report would you like to create? "]
    assert "Request understanding:\nThe requested report." in capsys.readouterr().out
