import builtins
import json
from pathlib import Path

from sageql import chat_cli
from sageql.context import ContextResolution, ResolvedContext
from sageql.discovery import DiscoverySelection
from sageql.planning import PlanProposal, ProposedJoin, ProposedMeasure
from sageql.understanding import RequestAssessment


def ready_context():
    return ContextResolution(
        True,
        ResolvedContext("last quarter", ("sales",), ("revenue",), (), ""),
        "",
    )


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

        def resolve_context(self, messages, understanding):
            assert understanding == "Sales report for last quarter."
            return ready_context()

    monkeypatch.setattr(builtins, "input", fake_input)
    monkeypatch.setattr(chat_cli.getpass, "getpass", lambda prompt: "secret")
    monkeypatch.setattr(chat_cli, "OpenAIChatProvider", FakeProvider)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    for name in ("DB_SERVER_HOST", "DB_NAME", "DB_AUTHENTICATION", "DB_ODBC_DRIVER"):
        monkeypatch.delenv(name, raising=False)

    exit_code = chat_cli.main(["--no-discovery"])
    output = capsys.readouterr()

    assert exit_code == 0
    assert prompts[0] == "What report would you like to create? "
    assert "AI> Which dates?" in output.out
    assert "Request understanding:\nSales report for last quarter." in output.out
    assert "Resolved context:" in output.out
    assert "Time period: last quarter" in output.out
    assert "secret" not in output.out + output.err


def test_chat_cli_requires_each_database_field(monkeypatch, capsys):
    answers = iter(["Report", "", "host", "db", "Windows", "driver", "", ""])
    monkeypatch.setattr(builtins, "input", lambda prompt: next(answers))
    monkeypatch.setattr(chat_cli.getpass, "getpass", lambda prompt: "secret")
    monkeypatch.setattr(
        chat_cli,
        "OpenAIChatProvider",
        lambda llm: type(
            "P",
            (),
            {
                "assess": lambda self, messages: RequestAssessment(True, "A report.", ""),
                "resolve_context": lambda self, messages, understanding: ready_context(),
            },
        )(),
    )
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("LLM_BASE_URL", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    for name in ("DB_SERVER_HOST", "DB_NAME", "DB_AUTHENTICATION", "DB_ODBC_DRIVER"):
        monkeypatch.delenv(name, raising=False)

    assert chat_cli.main(["--no-discovery"]) == 0
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

        def resolve_context(self, messages, understanding):
            return ready_context()

    monkeypatch.setattr(chat_cli, "OpenAIChatProvider", FakeProvider)

    assert chat_cli.main(["--no-discovery"]) == 0
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

        def resolve_context(self, messages, understanding):
            return ready_context()

    monkeypatch.setattr(chat_cli, "OpenAIChatProvider", FakeProvider)
    assert chat_cli.main(["--no-discovery"]) == 0
    assert prompts == ["What report would you like to create? "]
    assert "Request understanding:\nThe requested report." in capsys.readouterr().out


def test_chat_cli_asks_context_clarification(monkeypatch, capsys):
    answers = iter(["Show revenue by region", "Last quarter"])
    monkeypatch.setattr(builtins, "input", lambda prompt: next(answers))
    monkeypatch.setenv("DB_SERVER_HOST", "host")
    monkeypatch.setenv("DB_NAME", "db")
    monkeypatch.setenv("DB_AUTHENTICATION", "Windows")
    monkeypatch.setenv("DB_ODBC_DRIVER", "driver")
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")

    class FakeProvider:
        def __init__(self, llm):
            pass

        def assess(self, messages):
            return RequestAssessment(True, "Revenue by region.", "")

        def resolve_context(self, messages, understanding):
            if len(messages) == 2:
                return ContextResolution(
                    False,
                    ResolvedContext("", ("sales", "region"), ("revenue",), (), ""),
                    "Which time period?",
                )
            assert messages[-1].content == "Last quarter"
            return ready_context()

    monkeypatch.setattr(chat_cli, "OpenAIChatProvider", FakeProvider)

    assert chat_cli.main(["--no-discovery"]) == 0
    output = capsys.readouterr().out
    assert "AI> Which time period?" in output
    assert "Resolved context:" in output
    assert "Time period: last quarter" in output
    assert "Comparison period: Not specified" in output


def test_chat_cli_prints_verified_query_space(monkeypatch, capsys, tmp_path):
    monkeypatch.setattr(builtins, "input", lambda prompt: "Revenue by region in 2025")
    for name, value in {
        "DB_SERVER_HOST": "private-host",
        "DB_NAME": "private-db",
        "DB_AUTHENTICATION": "Windows",
        "DB_ODBC_DRIVER": "driver",
        "LLM_API_KEY": "secret",
        "LLM_BASE_URL": "https://example.test/v1",
        "LLM_MODEL": "demo-model",
    }.items():
        monkeypatch.setenv(name, value)

    schema_path = tmp_path / "schema.json"
    schema_path.write_text(json.dumps({
        "tables": [
            {"schema": "sales", "name": "orders", "description": "Customer orders",
             "columns": [{"name": "region_id", "data_type": "int"}]},
            {"schema": "sales", "name": "regions",
             "columns": [{"name": "id", "data_type": "int"}]},
        ],
        "relations": [{"name": "fk_orders_region", "child_table": "sales.orders",
                       "child_columns": ["region_id"], "parent_table": "sales.regions",
                       "parent_columns": ["id"]}],
    }), encoding="utf-8")

    class Provider:
        def __init__(self, llm):
            pass

        def assess(self, messages):
            return RequestAssessment(True, "Revenue by region in 2025", "")

        def resolve_context(self, messages, understanding):
            return ContextResolution(True, ResolvedContext("2025", ("region",), ("revenue",), (), ""), "")

        def select_query_space(self, understanding, context, candidates):
            return DiscoverySelection(tuple(candidates.tables), tuple(candidates.columns),
                                      tuple(candidates.relations), tuple(candidates.definitions))

    monkeypatch.setattr(chat_cli, "OpenAIChatProvider", Provider)
    assert chat_cli.main(["--catalog", str(schema_path), "--no-planning"]) == 0
    output = capsys.readouterr().out
    assert "Query space discovery:" in output
    assert "sales.orders (table)" in output
    assert "sales.orders.region_id (int)" in output
    assert "sales.orders.region_id -> sales.regions.id" in output
    assert "Customer orders" in output
    assert "secret" not in output


def test_chat_cli_prints_query_plan_and_quality(monkeypatch, capsys):
    monkeypatch.setattr(builtins, "input", lambda prompt: "Monthly sum of order amount by region in 2025")
    for name, value in {
        "DB_SERVER_HOST": "unused-host", "DB_NAME": "unused-db",
        "DB_AUTHENTICATION": "unused", "DB_ODBC_DRIVER": "unused",
        "LLM_API_KEY": "secret", "LLM_BASE_URL": "https://example.test/v1",
        "LLM_MODEL": "demo",
    }.items():
        monkeypatch.setenv(name, value)

    class Provider:
        def __init__(self, llm):
            pass

        def assess(self, messages):
            return RequestAssessment(True, "Monthly sum of order amount by region in 2025", "")

        def resolve_context(self, messages, understanding):
            return ContextResolution(True, ResolvedContext(
                "monthly 2025", ("region",), ("sum of order amount",), (), ""
            ), "")

        def select_query_space(self, understanding, context, candidates):
            return DiscoverySelection(tuple(candidates.tables), tuple(candidates.columns),
                                      tuple(candidates.relations), tuple(candidates.definitions))

        def propose_query_plan(self, understanding, context, candidates):
            tables = {table.key: key for key, table in candidates.tables.items()}
            columns = {column.key: key for key, column in candidates.columns.items()}
            return PlanProposal(
                tables["sales.orders"],
                (ProposedJoin(next(iter(candidates.relations)), tables["sales.regions"], "left"),),
                columns["sales.orders.order_date"], "month",
                (columns["sales.regions.name"],),
                (ProposedMeasure("sum of order amount", "sum", columns["sales.orders.amount"]),),
                (),
            )

    monkeypatch.setattr(chat_cli, "OpenAIChatProvider", Provider)
    schema_path = Path(__file__).resolve().parents[1] / "schema.example.json"
    assert chat_cli.main(["--catalog", str(schema_path)]) == 0
    output = capsys.readouterr().out
    assert '"operation": "scan"' in output
    assert '"operation": "aggregate"' in output
    assert "Plan quality:" in output
    assert "Execution: Not performed." in output
    assert "secret" not in output
