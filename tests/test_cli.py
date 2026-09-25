from sageql import Candidate
from sageql import cli


def test_cli_prints_query(tmp_path, monkeypatch, capsys):
    schema = tmp_path / "schema.sql"
    schema.write_text("CREATE TABLE orders(id INTEGER);", encoding="utf-8")

    class FakeProvider:
        def __init__(self, model):
            assert model == "test-model"

        def generate(self, question, schema_text):
            assert question == "count orders"
            assert "orders" in schema_text
            return Candidate("SELECT COUNT(*) FROM orders", "Counts orders")

    monkeypatch.setattr(cli, "OpenAIProvider", FakeProvider)
    exit_code = cli.main(["count orders", "--schema", str(schema), "--model", "test-model"])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert captured.out == "SELECT COUNT(*) FROM orders\n"
    assert "Counts orders" in captured.err


def test_cli_reports_missing_schema(tmp_path, capsys):
    exit_code = cli.main(["question", "--schema", str(tmp_path / "missing.sql")])
    assert exit_code == 1
    assert "sageql:" in capsys.readouterr().err
