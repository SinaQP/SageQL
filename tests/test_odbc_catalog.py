from types import SimpleNamespace as Row

import pytest

from sageql.conversation import DatabaseConfig
from sageql.discovery import DiscoveryError
from sageql.odbc_catalog import ODBCCatalogSource


def config(authentication="Windows"):
    return DatabaseConfig("private-host", "private-db", authentication, "ODBC Driver 18 for SQL Server")


class Cursor:
    def __init__(self):
        self.calls = []

    def tables(self, **kwargs):
        self.calls.append(("tables", kwargs))
        return [
            Row(table_schem="sales", table_name="orders", table_type="TABLE", remarks="Customer orders"),
            Row(table_schem="sales", table_name="regions", table_type="TABLE", remarks=""),
            Row(table_schem="sys", table_name="internal", table_type="SYSTEM TABLE", remarks=""),
        ]

    def columns(self, **kwargs):
        self.calls.append(("columns", kwargs))
        if kwargs["table"] == "orders":
            return [
                Row(column_name="region_id", type_name="int", nullable=False, remarks=""),
                Row(column_name="revenue", type_name="decimal", nullable=True, remarks="Booked revenue"),
                Row(table_schem="sales", table_name="orders_archive", column_name="not_ours",
                    type_name="int", nullable=True, remarks=""),
            ]
        return [Row(column_name="id", type_name="int", nullable=False, remarks="")]

    def foreignKeys(self, **kwargs):
        self.calls.append(("foreignKeys", kwargs))
        if kwargs["foreignTable"] != "orders":
            return []
        return [Row(fktable_schem="sales", fktable_name="orders", fkcolumn_name="region_id",
                    pktable_schem="sales", pktable_name="regions", pkcolumn_name="id",
                    fk_name="fk_orders_region", key_seq=1)]


class Connection:
    def __init__(self):
        self.fake_cursor = Cursor()
        self.closed = False

    def cursor(self):
        return self.fake_cursor

    def close(self):
        self.closed = True


def test_odbc_reads_metadata_only_and_closes_connection():
    connection = Connection()
    seen = []

    def connect(connection_string, **kwargs):
        seen.append((connection_string, kwargs))
        return connection

    catalog = ODBCCatalogSource(config(), schemas=("sales",), connect=connect).load_catalog()
    assert connection.closed
    assert [table.key for table in catalog.tables] == ["sales.orders", "sales.regions"]
    assert len(catalog.columns) == 3
    assert catalog.relations[0].child_columns == ("region_id",)
    assert {(definition.term, definition.meaning) for definition in catalog.definitions} == {
        ("sales.orders", "Customer orders"),
        ("sales.orders.revenue", "Booked revenue"),
    }
    assert {method for method, _ in connection.fake_cursor.calls} == {"tables", "columns", "foreignKeys"}
    assert "Trusted_Connection=yes" in seen[0][0]
    assert "private-host" in seen[0][0]


def test_sql_auth_password_not_exposed_in_error():
    def fail_connect(*args, **kwargs):
        raise RuntimeError("secret-password in connection error")

    source = ODBCCatalogSource(config("SQL Server"), username="alice", password="secret-password",
                               connect=fail_connect)
    with pytest.raises(DiscoveryError) as error:
        source.load_catalog()
    assert "secret-password" not in str(error.value)


def test_sql_auth_requires_credentials():
    with pytest.raises(DiscoveryError, match="DB_USERNAME"):
        ODBCCatalogSource(config("SQL Server"), connect=lambda *a, **k: None).load_catalog()
