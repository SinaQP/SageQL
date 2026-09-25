"""Parse schema metadata supplied by the package user."""

import json
from pathlib import Path
from typing import Any, Mapping

from sageql.schema import Column, Definition, Relation, SchemaCatalog, Table


_MAX_FILE_BYTES = 1_000_000


def _object(value: Any, required: set[str], optional: set[str], label: str) -> Mapping[str, Any]:
    if not isinstance(value, dict) or not required <= value.keys() or value.keys() - required - optional:
        raise ValueError(f"{label} has missing or unexpected fields")
    return value


def _array(value: Any, label: str, *, maximum: int, nonempty: bool = False) -> list[Any]:
    if not isinstance(value, list) or len(value) > maximum or (nonempty and not value):
        raise ValueError(f"{label} must be a JSON array with 1 to {maximum} items" if nonempty
                         else f"{label} must be a JSON array with at most {maximum} items")
    return value


def _text(value: Any, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or len(value) > 2000 or (not allow_empty and not value.strip()):
        raise ValueError(f"{label} must be text")
    if any(ord(character) < 32 for character in value if character not in "\n\t"):
        raise ValueError(f"{label} contains invalid control characters")
    return value.strip()


def _identifier(value: Any, label: str, *, allow_empty: bool = False) -> str:
    result = _text(value, label, allow_empty=allow_empty)
    if len(result) > 256 or "\n" in result or "\t" in result:
        raise ValueError(f"{label} must be a single-line identifier")
    return result


def catalog_from_dict(data: Mapping[str, Any]) -> SchemaCatalog:
    """Validate a JSON-shaped catalog with tables, columns, relations, and definitions."""
    root = _object(data, {"tables"}, {"relations", "definitions"}, "catalog")
    tables: list[Table] = []
    columns: list[Column] = []
    definitions: list[Definition] = []
    for index, raw_table in enumerate(_array(root["tables"], "tables", maximum=200, nonempty=True)):
        label = f"tables[{index}]"
        item = _object(raw_table, {"name", "columns"}, {"schema", "kind", "description"}, label)
        table = Table(
            name=_identifier(item["name"], label + ".name"),
            schema=_identifier(item.get("schema", ""), label + ".schema", allow_empty=True),
            kind=_identifier(item.get("kind", "TABLE"), label + ".kind").upper(),
        )
        tables.append(table)
        if "description" in item:
            definitions.append(Definition(
                table.key, _text(item["description"], label + ".description"),
                "user table description",
            ))
        for col_index, raw_column in enumerate(
            _array(item["columns"], label + ".columns", maximum=500, nonempty=True)
        ):
            col_label = f"{label}.columns[{col_index}]"
            col = _object(raw_column, {"name"}, {"data_type", "nullable", "description"}, col_label)
            nullable = col.get("nullable", True)
            if type(nullable) is not bool:
                raise ValueError(f"{col_label}.nullable must be a boolean")
            column = Column(
                table=table.key,
                name=_identifier(col["name"], col_label + ".name"),
                data_type=_identifier(col.get("data_type", "unknown"), col_label + ".data_type"),
                nullable=nullable,
            )
            columns.append(column)
            if "description" in col:
                definitions.append(Definition(
                    column.key, _text(col["description"], col_label + ".description"),
                    "user column description",
                ))
    if len(columns) > 5000:
        raise ValueError("catalog has too many columns")

    table_names = {table.key.casefold(): table.key for table in tables}
    column_names = {(column.table.casefold(), column.name.casefold()): column.name
                    for column in columns}
    relations: list[Relation] = []
    for index, raw_relation in enumerate(_array(root.get("relations", []), "relations", maximum=500)):
        label = f"relations[{index}]"
        item = _object(raw_relation,
                       {"name", "child_table", "child_columns", "parent_table", "parent_columns"},
                       set(), label)
        child_raw = _identifier(item["child_table"], label + ".child_table")
        parent_raw = _identifier(item["parent_table"], label + ".parent_table")
        child = table_names.get(child_raw.casefold(), child_raw)
        parent = table_names.get(parent_raw.casefold(), parent_raw)
        def relation_columns(field: str, table: str) -> tuple[str, ...]:
            values = _array(item[field], label + "." + field, maximum=32, nonempty=True)
            return tuple(
                column_names.get((table.casefold(), name.casefold()), name)
                for name in (_identifier(value, label + "." + field) for value in values)
            )
        relations.append(Relation(
            name=_identifier(item["name"], label + ".name"),
            child_table=child,
            child_columns=relation_columns("child_columns", child),
            parent_table=parent,
            parent_columns=relation_columns("parent_columns", parent),
        ))

    for index, raw_definition in enumerate(_array(root.get("definitions", []), "definitions", maximum=500)):
        label = f"definitions[{index}]"
        item = _object(raw_definition, {"term", "meaning"}, set(), label)
        definitions.append(Definition(
            _identifier(item["term"], label + ".term"),
            _text(item["meaning"], label + ".meaning"),
            "user glossary",
        ))
    try:
        return SchemaCatalog(tuple(tables), tuple(columns), tuple(relations), tuple(definitions))
    except ValueError as exc:
        raise ValueError(f"invalid catalog structure: {exc}") from exc


def load_catalog_file(path: str | Path) -> SchemaCatalog:
    """Load a UTF-8 JSON catalog without echoing file contents in errors."""
    try:
        with Path(path).open("rb") as handle:
            content = handle.read(_MAX_FILE_BYTES + 1)
    except OSError as exc:
        raise ValueError("could not read schema catalog file") from exc
    if len(content) > _MAX_FILE_BYTES:
        raise ValueError("schema catalog file is too large")
    try:
        data = json.loads(content.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("schema catalog must be valid UTF-8 JSON") from exc
    return catalog_from_dict(data)
