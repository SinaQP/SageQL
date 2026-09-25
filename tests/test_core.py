import pytest

from sageql import Candidate, GenerationError, InvalidSQL, generate_sql


class FakeProvider:
    def __init__(self, candidate):
        self.candidate = candidate
        self.calls = []

    def generate(self, question, schema):
        self.calls.append((question, schema))
        return self.candidate


def test_generates_validated_query():
    provider = FakeProvider(Candidate("SELECT COUNT(*) FROM orders", "Counts orders"))

    result = generate_sql("How many orders?", "CREATE TABLE orders (id INTEGER);", provider)

    assert result.sql == "SELECT COUNT(*) FROM orders"
    assert result.explanation == "Counts orders"
    assert provider.calls == [
        ("How many orders?", "CREATE TABLE orders (id INTEGER);")
    ]


@pytest.mark.parametrize("question,schema", [(" ", "table"), ("question", " ")])
def test_rejects_empty_input_before_provider(question, schema):
    provider = FakeProvider(Candidate("SELECT 1"))
    with pytest.raises(ValueError):
        generate_sql(question, schema, provider)
    assert provider.calls == []


def test_rejects_unsafe_candidate():
    with pytest.raises(InvalidSQL):
        generate_sql("remove data", "CREATE TABLE t(x);", FakeProvider(Candidate("DELETE FROM t")))


def test_wraps_provider_failure():
    class BrokenProvider:
        def generate(self, question, schema):
            raise RuntimeError("internal credential detail")

    with pytest.raises(GenerationError, match="model provider failed"):
        generate_sql("question", "schema", BrokenProvider())
