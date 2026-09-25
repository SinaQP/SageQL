"""Validated, immutable database metadata used by query-space discovery."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Table:
    name: str
    schema: str = ""
    kind: str = "TABLE"

    @property
    def key(self) -> str:
        return f"{self.schema}.{self.name}" if self.schema else self.name


@dataclass(frozen=True)
class Column:
    table: str
    name: str
    data_type: str
    nullable: bool = True

    @property
    def key(self) -> str:
        return f"{self.table}.{self.name}"


@dataclass(frozen=True)
class Relation:
    name: str
    child_table: str
    child_columns: tuple[str, ...]
    parent_table: str
    parent_columns: tuple[str, ...]


@dataclass(frozen=True)
class Definition:
    term: str
    meaning: str
    source: str


@dataclass(frozen=True)
class SchemaCatalog:
    tables: tuple[Table, ...]
    columns: tuple[Column, ...]
    relations: tuple[Relation, ...] = ()
    definitions: tuple[Definition, ...] = ()

    def __post_init__(self) -> None:
        tables = {table.key.casefold(): table for table in self.tables}
        if len(tables) != len(self.tables):
            raise ValueError("duplicate table names in schema catalog")
        columns = {column.key.casefold(): column for column in self.columns}
        if len(columns) != len(self.columns):
            raise ValueError("duplicate column names in schema catalog")
        for table in self.tables:
            if not table.name.strip() or table.kind.upper() not in {"TABLE", "VIEW"}:
                raise ValueError("invalid table metadata")
        for column in self.columns:
            if (
                column.table.casefold() not in tables
                or not column.name.strip()
                or not column.data_type.strip()
            ):
                raise ValueError("invalid column metadata")
        for relation in self.relations:
            if (
                not relation.name.strip()
                or relation.child_table.casefold() not in tables
                or relation.parent_table.casefold() not in tables
                or not relation.child_columns
                or len(relation.child_columns) != len(relation.parent_columns)
            ):
                raise ValueError("invalid relation metadata")
            for child, parent in zip(relation.child_columns, relation.parent_columns):
                if (
                    f"{relation.child_table}.{child}".casefold() not in columns
                    or f"{relation.parent_table}.{parent}".casefold() not in columns
                ):
                    raise ValueError("relation references an unknown column")
        for definition in self.definitions:
            if not all((definition.term.strip(), definition.meaning.strip(), definition.source.strip())):
                raise ValueError("invalid definition metadata")
