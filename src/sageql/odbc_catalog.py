"""ODBC catalog reader. Calls metadata APIs only; never queries business rows."""

import os
from collections import defaultdict
from typing import Any, Callable

from sageql.conversation import DatabaseConfig
from sageql.discovery import DiscoveryError
from sageql.schema import Column, Definition, Relation, SchemaCatalog, Table


def _field(row: Any, name: str, default: Any = None) -> Any:
    return getattr(row, name, default)


def _qualified(schema: Any, name: Any) -> str:
    return f"{schema}.{name}" if schema else str(name)


def _connection_string(config: DatabaseConfig, username: str, password: str) -> str:
    # Braced ODBC values prevent semicolons in configuration from adding options.
    def braced(value: str) -> str:
        return "{" + value.replace("}", "}}") + "}"

    auth = config.authentication.casefold().strip()
    base = (
        f"DRIVER={braced(config.odbc_driver)};"
        f"SERVER={braced(config.server_host)};DATABASE={braced(config.database)};"
    )
    if auth in {"windows", "integrated", "trusted", "windows authentication"}:
        return base + "Trusted_Connection=yes;Encrypt=yes;TrustServerCertificate=no;ApplicationIntent=ReadOnly;"
    if auth in {"sql", "sql server", "sql server authentication", "username and password"}:
        if not username or not password:
            raise DiscoveryError("DB_USERNAME and DB_PASSWORD are required for SQL authentication")
        return (
            base + f"UID={braced(username)};PWD={braced(password)};"
            "Encrypt=yes;TrustServerCertificate=no;ApplicationIntent=ReadOnly;"
        )
    raise DiscoveryError(
        "unsupported authentication method; use Windows, SQL Server, or DB_ODBC_CONNECTION_STRING"
    )


class ODBCCatalogSource:
    """Load catalog metadata using pyodbc's ODBC metadata functions."""

    def __init__(
        self,
        config: DatabaseConfig,
        *,
        schemas: tuple[str, ...] = (),
        connection_string: str = "",
        username: str = "",
        password: str = "",
        connect: Callable[..., Any] | None = None,
    ) -> None:
        self._config = config
        self._schemas = {item.casefold() for item in schemas if item.strip()}
        self._connection_string = connection_string
        self._username = username
        self._password = password
        self._connect = connect

    @classmethod
    def from_environment(cls, config: DatabaseConfig) -> "ODBCCatalogSource":
        return cls(
            config,
            schemas=tuple(part.strip() for part in os.getenv("DB_SCHEMAS", "").split(",") if part.strip()),
            connection_string=os.getenv("DB_ODBC_CONNECTION_STRING", ""),
            username=os.getenv("DB_USERNAME", ""),
            password=os.getenv("DB_PASSWORD", ""),
        )

    def load_catalog(self) -> SchemaCatalog:
        connection_string = self._connection_string or _connection_string(
            self._config, self._username, self._password
        )
        connect = self._connect
        if connect is None:
            try:
                import pyodbc
            except ImportError as exc:
                raise DiscoveryError("install the ODBC extra: pip install 'sageql[odbc]'") from exc
            connect = pyodbc.connect
        try:
            connection = connect(connection_string, timeout=10)
        except Exception as exc:
            raise DiscoveryError("database metadata connection failed; check the ODBC configuration") from exc
        try:
            return self._read_catalog(connection.cursor())
        except DiscoveryError:
            raise
        except Exception as exc:
            raise DiscoveryError("database metadata discovery failed") from exc
        finally:
            connection.close()

    def _read_catalog(self, cursor: Any) -> SchemaCatalog:
        tables: list[Table] = []
        columns: list[Column] = []
        definitions: list[Definition] = []
        for row in cursor.tables(catalog=self._config.database):
            kind = str(_field(row, "table_type", "")).upper()
            schema = str(_field(row, "table_schem", "") or "")
            name = str(_field(row, "table_name", "") or "")
            if kind not in {"TABLE", "VIEW"} or not name:
                continue
            if not self._schemas and schema.casefold() in {"sys", "information_schema"}:
                continue
            if self._schemas and schema.casefold() not in self._schemas:
                continue
            if len(tables) >= 200:
                raise DiscoveryError("database exposes over 200 tables/views; set DB_SCHEMAS to narrow discovery")
            table = Table(name=name, schema=schema, kind=kind)
            tables.append(table)
            remark = str(_field(row, "remarks", "") or "").strip()
            if remark:
                definitions.append(Definition(table.key, remark, "ODBC table remark"))

        table_keys = {table.key.casefold(): table.key for table in tables}
        for table in tables:
            for row in cursor.columns(
                catalog=self._config.database, schema=table.schema or None, table=table.name
            ):
                if (str(_field(row, "table_name", table.name)).casefold() != table.name.casefold()
                        or str(_field(row, "table_schem", table.schema) or "").casefold()
                        != table.schema.casefold()):
                    continue
                if len(columns) >= 5000:
                    raise DiscoveryError("database exposes over 5000 columns; set DB_SCHEMAS to narrow discovery")
                column = Column(
                    table.key,
                    str(_field(row, "column_name", "") or ""),
                    str(_field(row, "type_name", "") or ""),
                    bool(_field(row, "nullable", True)),
                )
                columns.append(column)
                remark = str(_field(row, "remarks", "") or "").strip()
                if remark:
                    definitions.append(Definition(column.key, remark, "ODBC column remark"))

        relation_parts: dict[tuple[str, str, str], list[tuple[int, str, str]]] = defaultdict(list)
        for table in tables:
            for row in cursor.foreignKeys(
                foreignCatalog=self._config.database,
                foreignSchema=table.schema or None,
                foreignTable=table.name,
            ):
                child_name = _qualified(_field(row, "fktable_schem"), _field(row, "fktable_name"))
                parent_name = _qualified(_field(row, "pktable_schem"), _field(row, "pktable_name"))
                if child_name.casefold() != table.key.casefold():
                    continue
                child = table_keys.get(child_name.casefold())
                parent = table_keys.get(parent_name.casefold())
                if child is None or parent is None:
                    continue
                name = str(_field(row, "fk_name", "") or "")
                if not name:
                    name = f"{child}.{_field(row, 'fkcolumn_name')} -> {parent}.{_field(row, 'pkcolumn_name')}"
                relation_parts[(name, child, parent)].append((
                    int(_field(row, "key_seq", 1)),
                    str(_field(row, "fkcolumn_name")),
                    str(_field(row, "pkcolumn_name")),
                ))
        relations = []
        for (name, child, parent), parts in relation_parts.items():
            ordered = sorted(parts)
            relations.append(Relation(
                name, child, tuple(item[1] for item in ordered),
                parent, tuple(item[2] for item in ordered),
            ))
        return SchemaCatalog(tuple(tables), tuple(columns), tuple(relations), tuple(definitions))
