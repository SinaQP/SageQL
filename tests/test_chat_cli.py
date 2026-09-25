import builtins

from sageql import chat_cli


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
            "/exit",
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

        def reply(self, messages):
            return "Which dates?" if len(messages) == 1 else "Understood."

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
    assert "AI> Understood." in output.out
    assert "secret" not in output.out + output.err


def test_chat_cli_requires_each_database_field(monkeypatch, capsys):
    answers = iter(["Report", "", "host", "db", "Windows", "driver", "", "", "/exit"])
    monkeypatch.setattr(builtins, "input", lambda prompt: next(answers))
    monkeypatch.setattr(chat_cli.getpass, "getpass", lambda prompt: "secret")
    monkeypatch.setattr(chat_cli, "OpenAIChatProvider", lambda llm: type("P", (), {"reply": lambda self, messages: "Hello"})())
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    for name in ("DB_SERVER_HOST", "DB_NAME", "DB_AUTHENTICATION", "DB_ODBC_DRIVER"):
        monkeypatch.delenv(name, raising=False)

    assert chat_cli.main([]) == 0
    assert "Please enter a value." in capsys.readouterr().err


def test_chat_cli_uses_llm_environment_defaults(monkeypatch, capsys):
    answers = iter(["Report", "host", "db", "Windows", "driver", "/exit"])
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

        def reply(self, messages):
            return "Which date range?"

    monkeypatch.setattr(chat_cli, "OpenAIChatProvider", FakeProvider)

    assert chat_cli.main([]) == 0
    output = capsys.readouterr()
    assert "Which date range?" in output.out
    assert "test-key" not in output.out + output.err


def test_chat_cli_uses_database_environment_values(monkeypatch, capsys):
    prompts = []
    answers = iter(["Report", "/exit"])

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

        def reply(self, messages):
            return "Which date range?"

    monkeypatch.setattr(chat_cli, "OpenAIChatProvider", FakeProvider)
    assert chat_cli.main([]) == 0
    assert prompts == ["What report would you like to create? ", "You> "]
    assert "Which date range?" in capsys.readouterr().out
