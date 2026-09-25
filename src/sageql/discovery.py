"""Find report-relevant schema objects without reading business rows."""

import re
from dataclasses import dataclass
from typing import Protocol

from sageql.context import ResolvedContext
from sageql.schema import Column, Definition, Relation, SchemaCatalog, Table


class DiscoveryError(Exception):
    """Schema discovery could not produce a trustworthy result."""


class CatalogSource(Protocol):
    def load_catalog(self) -> SchemaCatalog:
        """Read table, column, relation, and definition metadata only."""


@dataclass(frozen=True)
class DiscoveryCandidates:
    tables: dict[str, Table]
    columns: dict[str, Column]
    relations: dict[str, Relation]
    definitions: dict[str, Definition]


@dataclass(frozen=True)
class DiscoverySelection:
    table_ids: tuple[str, ...]
    column_ids: tuple[str, ...]
    relation_ids: tuple[str, ...]
    definition_ids: tuple[str, ...]


@dataclass(frozen=True)
class QuerySpace:
    tables: tuple[Table, ...]
    columns: tuple[Column, ...]
    relations: tuple[Relation, ...]
    definitions: tuple[Definition, ...]


class DiscoveryProvider(Protocol):
    def select_query_space(
        self, understanding: str, context: ResolvedContext, candidates: DiscoveryCandidates
    ) -> DiscoverySelection:
        """Select relevant candidate IDs; do not invent schema objects."""


_STOPWORDS = {"a", "all", "and", "by", "for", "from", "in", "of", "on", "per", "the", "to"}


def _tokens(text: str) -> set[str]:
    words = re.findall(r"[a-z0-9]+", re.sub(r"([a-z])([A-Z])", r"\1 \2", text))
    return {word[:-1] if word.endswith("s") and len(word) > 3 else word
            for word in (item.lower() for item in words) if word not in _STOPWORDS}


def _candidate_catalog(
    catalog: SchemaCatalog, understanding: str, context: ResolvedContext, *, supplied: bool = False
) -> DiscoveryCandidates:
    terms = _tokens(" ".join((understanding, context.time_period, *context.entities,
                              *context.metrics, *context.filters, context.comparison_period)))
    if not catalog.tables:
        raise DiscoveryError("the catalog contains no tables or views")
    table_scores: dict[str, int] = {}
    for table in catalog.tables:
        name_score = len(_tokens(table.key) & terms) * 4
        column_score = sum(bool(_tokens(col.name) & terms) for col in catalog.columns if col.table == table.key)
        definition_score = sum(bool(_tokens(item.term + " " + item.meaning) & terms)
                               for item in catalog.definitions
                               if item.term == table.key or item.term.startswith(table.key + "."))
        table_scores[table.key] = name_score + column_score + definition_score

    ordered = sorted(catalog.tables, key=lambda table: (-table_scores[table.key], table.key.casefold()))
    if supplied:
        if len(catalog.tables) > 30:
            raise DiscoveryError("supplied catalog has over 30 tables; provide a smaller relevant catalog")
        chosen = list(catalog.tables)
    elif len(ordered) <= 20:
        chosen = ordered
    else:
        chosen = [table for table in ordered if table_scores[table.key] > 0][:15]
        if not chosen:
            raise DiscoveryError("no schema names match the request; narrow the schema or add definitions")
        # Retain short FK paths so the model can see bridge tables needed for joins.
        neighbors: dict[str, set[str]] = {table.key: set() for table in catalog.tables}
        for relation in catalog.relations:
            neighbors[relation.child_table].add(relation.parent_table)
            neighbors[relation.parent_table].add(relation.child_table)
        selected = {table.key for table in chosen}
        for start in tuple(selected):
            queue = [(start, (start,))]
            while queue:
                current, path = queue.pop(0)
                if len(path) > 4:
                    continue
                for adjacent in sorted(neighbors[current]):
                    if adjacent in path:
                        continue
                    next_path = (*path, adjacent)
                    if adjacent in selected and len(selected) + len(next_path) - 2 <= 20:
                        selected.update(next_path)
                    elif len(next_path) <= 4:
                        queue.append((adjacent, next_path))
        chosen = [table for table in catalog.tables if table.key in selected]

    chosen_keys = {table.key for table in chosen}
    columns = [column for column in catalog.columns if column.table in chosen_keys]
    relations = [relation for relation in catalog.relations
                 if relation.child_table in chosen_keys and relation.parent_table in chosen_keys]
    definitions = list(catalog.definitions) if supplied else [
        definition for definition in catalog.definitions
        if any(definition.term == key or definition.term.startswith(key + ".")
               for key in chosen_keys) or bool(_tokens(definition.term) & terms)
    ]
    if len(columns) > 500 or len(relations) > 150 or len(definitions) > 200:
        raise DiscoveryError("schema candidate set is too large; supply a smaller relevant catalog")
    return DiscoveryCandidates(
        {f"t{i}": value for i, value in enumerate(chosen)},
        {f"c{i}": value for i, value in enumerate(columns)},
        {f"r{i}": value for i, value in enumerate(relations)},
        {f"d{i}": value for i, value in enumerate(definitions)},
    )


def discover_query_space(
    source: CatalogSource | SchemaCatalog,
    provider: DiscoveryProvider,
    understanding: str,
    context: ResolvedContext,
) -> QuerySpace:
    """Load metadata, let the model choose candidates, and validate every choice."""
    if not understanding.strip():
        raise ValueError("request understanding must not be empty")
    supplied = isinstance(source, SchemaCatalog)
    if supplied:
        catalog = source
    else:
        try:
            catalog = source.load_catalog()
        except DiscoveryError:
            raise
        except Exception as exc:
            raise DiscoveryError("schema catalog load failed") from exc
    if not isinstance(catalog, SchemaCatalog):
        raise DiscoveryError("catalog source returned invalid metadata")
    candidates = _candidate_catalog(catalog, understanding, context, supplied=supplied)
    try:
        selection = provider.select_query_space(understanding, context, candidates)
    except DiscoveryError:
        raise
    except Exception as exc:
        raise DiscoveryError("query-space model selection failed") from exc
    if not isinstance(selection, DiscoverySelection):
        raise DiscoveryError("model returned an invalid query-space selection")
    groups = (
        (selection.table_ids, candidates.tables),
        (selection.column_ids, candidates.columns),
        (selection.relation_ids, candidates.relations),
        (selection.definition_ids, candidates.definitions),
    )
    for ids, available in groups:
        if (not isinstance(ids, tuple) or any(not isinstance(item, str) for item in ids)
                or len(ids) != len(set(ids)) or any(item not in available for item in ids)):
            raise DiscoveryError("model selected an unknown or duplicate schema item")
    tables = tuple(candidates.tables[item] for item in selection.table_ids)
    columns = tuple(candidates.columns[item] for item in selection.column_ids)
    relations = tuple(candidates.relations[item] for item in selection.relation_ids)
    definitions = tuple(candidates.definitions[item] for item in selection.definition_ids)
    selected_keys = {table.key for table in tables}
    if not tables or not columns:
        raise DiscoveryError("model did not select usable tables and columns")
    if any(column.table not in selected_keys for column in columns):
        raise DiscoveryError("model selected columns without their tables")
    if any(relation.child_table not in selected_keys or relation.parent_table not in selected_keys
           for relation in relations):
        raise DiscoveryError("model selected a relation without its tables")
    selected_columns = {column.key.casefold() for column in columns}
    if any(
        f"{relation.child_table}.{child}".casefold() not in selected_columns
        or f"{relation.parent_table}.{parent}".casefold() not in selected_columns
        for relation in relations
        for child, parent in zip(relation.child_columns, relation.parent_columns)
    ):
        raise DiscoveryError("model selected a relation without its join columns")
    return QuerySpace(tables, columns, relations, definitions)
