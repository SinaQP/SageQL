from pathlib import Path

import main as app_main
from sageql.context import ContextResolution, ResolvedContext
from sageql.discovery import DiscoverySelection
from sageql.planning import PlanProposal, ProposedJoin, ProposedMeasure
from sageql.understanding import RequestAssessment


def test_main_loads_local_env_without_overriding_shell(monkeypatch):
    calls = []
    monkeypatch.setattr(app_main, "load_dotenv", lambda **kwargs: calls.append(kwargs))
    monkeypatch.setattr(app_main, "chat_main", lambda argv: calls.append(argv) or 0)

    assert app_main.main([]) == 0
    assert calls == [
        {
            "dotenv_path": Path(app_main.__file__).resolve().parent / ".env",
            "override": False,
        },
        [],
    ]


def test_main_forwards_interactive_arguments(monkeypatch):
    monkeypatch.setattr(app_main, "load_dotenv", lambda **kwargs: None)
    monkeypatch.setattr(app_main, "chat_main", lambda argv: argv)
    assert app_main.main(["--catalog", "own-schema.json"]) == ["--catalog", "own-schema.json"]


def test_main_help_shows_example_and_interactive_modes(monkeypatch, capsys):
    monkeypatch.setattr(app_main, "load_dotenv", lambda **kwargs: None)
    assert app_main.main(["--help"]) == 0
    assert "--example" in capsys.readouterr().out


def test_example_runs_public_api_with_supplied_catalog(monkeypatch, capsys):
    monkeypatch.setattr(app_main, "load_dotenv", lambda **kwargs: None)
    monkeypatch.setenv("LLM_API_KEY", "test-key")
    monkeypatch.setenv("LLM_BASE_URL", "https://example.test/v1")
    monkeypatch.setenv("LLM_MODEL", "test-model")

    class Provider:
        def __init__(self, llm):
            assert llm.model == "test-model"

        def assess(self, messages):
            assert messages[-1].content == app_main.EXAMPLE_QUESTION
            return RequestAssessment(True, "Monthly order amount by region for 2025.", "")

        def resolve_context(self, messages, understanding):
            return ContextResolution(
                True, ResolvedContext("2025", ("region",), ("amount",), (), ""), ""
            )

        def select_query_space(self, understanding, context, candidates):
            return DiscoverySelection(
                tuple(candidates.tables), tuple(candidates.columns),
                tuple(candidates.relations), tuple(candidates.definitions)
            )

        def propose_query_plan(self, understanding, context, candidates):
            tables = {value.key: key for key, value in candidates.tables.items()}
            columns = {value.key: key for key, value in candidates.columns.items()}
            return PlanProposal(
                tables["sales.orders"],
                (ProposedJoin(next(iter(candidates.relations)), tables["sales.regions"], "left"),),
                columns["sales.orders.order_date"], "month",
                (columns["sales.regions.name"],),
                (ProposedMeasure("amount", "sum", columns["sales.orders.amount"]),),
                (),
            )

    monkeypatch.setattr(app_main, "OpenAIChatProvider", Provider)
    assert app_main.main(["--example"]) == 0
    output = capsys.readouterr().out
    assert "Request understanding:" in output
    assert "Resolved context:" in output
    assert "sales.orders" in output
    assert "fk_orders_region" in output
    assert '"operation": "aggregate"' in output
    assert "Plan quality:" in output
    assert "Generated SQLite SQL" in output
    assert "SUM(t0.\"amount\")" in output
    assert "'period_start': '2025-01-01'" in output
    assert "test-key" not in output


def test_example_requires_api_key(monkeypatch, capsys):
    monkeypatch.setattr(app_main, "load_dotenv", lambda **kwargs: None)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    assert app_main.main(["--example"]) == 1
    assert "Set LLM_API_KEY" in capsys.readouterr().err


def test_plan_demo_runs_without_model_or_database(monkeypatch, capsys):
    monkeypatch.setattr(app_main, "load_dotenv", lambda **kwargs: None)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.setattr(app_main, "OpenAIChatProvider", lambda *args: (_ for _ in ()).throw(
        AssertionError("offline demo must not call the model")
    ))

    assert app_main.main(["--plan-demo"]) == 0
    output = capsys.readouterr().out
    assert "Offline planning demo" in output
    assert '"operation": "join"' in output
    assert "Plan quality:" in output
    assert "REVIEW: Confirm exact date boundaries" in output
    assert "Generated SQLite SQL" in output
    assert "LEFT JOIN" in output
    assert "Required date bindings: None" in output
    assert "Execution: Not performed." in output
