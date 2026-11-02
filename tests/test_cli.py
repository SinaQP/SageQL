import json
import warnings

import pytest

import sageql
from sageql import cli
from sageql.legacy import Candidate


class FakeProvider:
    def __init__(self, model):
        assert model == "test-model"

    def generate(self, question, schema_text):
        assert question == "count orders"
        assert "orders" in schema_text
        return Candidate("SELECT COUNT(*) FROM orders", "Counts orders")


def test_legacy_sql_prints_query(tmp_path, monkeypatch, capsys):
    schema = tmp_path / "schema.sql"
    schema.write_text("CREATE TABLE orders(id INTEGER);", encoding="utf-8")
    monkeypatch.setattr(cli, "OpenAIProvider", FakeProvider)
    exit_code = cli.main(["legacy", "sql", "count orders", "--schema", str(schema), "--model", "test-model"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "SELECT COUNT(*) FROM orders\n"
    assert "Counts orders" in captured.err
    assert "moves to" not in captured.err


def test_old_question_form_still_works_with_a_notice(tmp_path, monkeypatch, capsys):
    schema = tmp_path / "schema.sql"
    schema.write_text("CREATE TABLE orders(id INTEGER);", encoding="utf-8")
    monkeypatch.setattr(cli, "OpenAIProvider", FakeProvider)
    exit_code = cli.main(["count orders", "--schema", str(schema), "--model", "test-model"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "SELECT COUNT(*) FROM orders\n"
    assert "sageql legacy sql" in captured.err


def test_old_chat_form_still_works_with_a_notice(monkeypatch, capsys):
    monkeypatch.setattr(cli.chat_cli, "main", lambda argv: 7 if argv == ["--x"] else 1)
    assert cli.main(["chat", "--x"]) == 7
    assert "sageql legacy chat" in capsys.readouterr().err
    assert cli.main(["legacy", "chat", "--x"]) == 7
    assert capsys.readouterr().err == ""


def test_cli_reports_missing_schema(tmp_path, capsys):
    exit_code = cli.main(["legacy", "sql", "question", "--schema", str(tmp_path / "missing.sql")])
    assert exit_code == 1
    assert "sageql:" in capsys.readouterr().err


def test_bare_command_describes_the_sdk_without_a_model(capsys):
    assert cli.main([]) == 0
    out = capsys.readouterr().out
    assert "Models never write SQL" in out and "sageql demo" in out and "legacy sql" in out


def test_unknown_legacy_subcommand_is_a_usage_error(capsys):
    assert cli.main(["legacy"]) == 2
    assert "usage: sageql legacy" in capsys.readouterr().err


def test_demo_runs_offline_and_shows_policy_bound_sql(capsys):
    assert cli.main(["demo"]) == 0
    out = capsys.readouterr().out
    assert "[needs clarification]" in out and out.count("[report ready]") == 2
    assert 't."tenant_id" = ?' in out and "Other tenant" not in out


def test_demo_json_prints_final_reply(capsys):
    assert cli.main(["demo", "--json"]) == 0
    reply = json.loads(capsys.readouterr().out)
    assert reply["status"] == "report_ready"
    assert reply["report"]["rows"] == [["Alex", "7"], ["Sam", "2.5"]]


def test_top_level_exports_only_the_sdk_front_door():
    assert sorted(sageql.__all__) == ["Column", "LLMConfig", "Message", "SageQL", "Table"]
    with warnings.catch_warnings():
        warnings.simplefilter("error")
        from sageql import Column, LLMConfig, Message, SageQL, Table  # noqa: F401


def test_legacy_names_still_resolve_with_a_deprecation_warning():
    from sageql import legacy
    with pytest.warns(DeprecationWarning, match="sageql.legacy"):
        assert sageql.generate_sql is legacy.generate_sql
    with pytest.raises(AttributeError):
        sageql.not_a_name  # noqa: B018
