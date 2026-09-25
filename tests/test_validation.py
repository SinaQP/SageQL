import pytest

from sageql import InvalidSQL, validate_sql


@pytest.mark.parametrize(
    "sql",
    [
        "SELECT id FROM orders",
        "WITH recent AS (SELECT id FROM orders) SELECT id FROM recent",
        "SELECT id FROM orders UNION SELECT id FROM archived_orders",
    ],
)
def test_accepts_read_queries(sql):
    assert validate_sql(sql) == sql


@pytest.mark.parametrize(
    "sql",
    [
        "",
        "DELETE FROM orders",
        "UPDATE orders SET id = 1",
        "CREATE TABLE bad (id INT)",
        "DROP TABLE orders",
        "PRAGMA writable_schema = ON",
        "ATTACH DATABASE 'other.db' AS other",
        "SELECT 1 INTO new_table",
        "SELECT 1; DELETE FROM orders",
        "SELECT FROM",
        "```sql\nSELECT 1\n```",
    ],
)
def test_rejects_unsafe_or_invalid_sql(sql):
    with pytest.raises(InvalidSQL):
        validate_sql(sql)
