from types import SimpleNamespace

import pytest

from sageql.context import ResolvedContext
from sageql.discovery import DiscoveryError, DiscoverySelection, discover_query_space
from sageql.schema import Column, Definition, Relation, SchemaCatalog, Table


def catalog():
    return SchemaCatalog(
        tables=(Table("orders", "sales"), Table("regions", "sales")),
        columns=(
            Column("sales.orders", "region_id", "int"),
            Column("sales.orders", "revenue", "decimal"),
            Column("sales.orders", "ordered_at", "datetime"),
            Column("sales.regions", "id", "int"),
            Column("sales.regions", "name", "varchar"),
        ),
        relations=(Relation("fk_orders_region", "sales.orders", ("region_id",),
                            "sales.regions", ("id",)),),
        definitions=(Definition("sales.orders.revenue", "Booked revenue", "ODBC column remark"),),
    )


def context():
    return ResolvedContext("2025", ("region",), ("revenue",), (), "")


def test_discovers_existing_tables_columns_relations_and_definitions():
    class Source:
        def load_catalog(self):
            return catalog()

    class Provider:
        def select_query_space(self, understanding, resolved, candidates):
            assert resolved == context()
            assert "secret" not in str(candidates)
            assert {table.key for table in candidates.tables.values()} == {"sales.orders", "sales.regions"}
            return DiscoverySelection(
                tuple(candidates.tables),
                tuple(candidates.columns),
                tuple(candidates.relations),
                tuple(candidates.definitions),
            )

    result = discover_query_space(Source(), Provider(), "Revenue by region in 2025", context())
    assert {table.key for table in result.tables} == {"sales.orders", "sales.regions"}
    assert result.relations[0].name == "fk_orders_region"
    assert result.definitions[0].meaning == "Booked revenue"


@pytest.mark.parametrize("selection", [
    DiscoverySelection(("invented",), (), (), ()),
    DiscoverySelection(("t0", "t0"), (), (), ()),
    DiscoverySelection(("t0",), ("c0",), (), ()),
    DiscoverySelection(("t0",), (), ("r0",), ()),
    DiscoverySelection(("t0",), (), (), ()),
    DiscoverySelection(("t0", "t1"), ("c1",), ("r0",), ()),
    DiscoverySelection((), (), (), ()),
])
def test_rejects_hallucinated_or_inconsistent_selection(selection):
    class Source:
        def load_catalog(self):
            return catalog()

    class Provider:
        def select_query_space(self, understanding, resolved, candidates):
            return selection

    with pytest.raises(DiscoveryError):
        discover_query_space(Source(), Provider(), "Revenue by region", context())


def test_catalog_rejects_nonexistent_relation_column():
    with pytest.raises(ValueError, match="unknown column"):
        SchemaCatalog(
            (Table("orders"), Table("regions")),
            (Column("orders", "region_id", "int"), Column("regions", "id", "int")),
            (Relation("fk", "orders", ("other_id",), "regions", ("id",)),),
        )


def test_large_catalog_shortlist_keeps_matching_tables():
    tables = tuple(Table(f"unrelated_{index}") for index in range(25)) + (Table("revenue"),)
    columns = tuple(Column(table.key, "id", "int") for table in tables)
    class Source:
        def load_catalog(self):
            return SchemaCatalog(tables, columns)
    class Provider:
        def select_query_space(self, understanding, resolved, candidates):
            assert [table.key for table in candidates.tables.values()] == ["revenue"]
            return DiscoverySelection(("t0",), ("c0",), (), ())

    result = discover_query_space(Source(), Provider(), "Revenue in 2025", context())
    assert result.tables[0].name == "revenue"
