import json

import pytest

from sageql.catalog_input import catalog_from_dict, load_catalog_file
from sageql.context import ResolvedContext
from sageql.discovery import DiscoverySelection, discover_query_space


def supplied():
    return {
        "tables": [
            {"schema": "sales", "name": "orders", "description": "Orders",
             "columns": [{"name": "region_id", "data_type": "integer", "nullable": False},
                         {"name": "amount", "description": "Order amount"}]},
            {"schema": "sales", "name": "regions",
             "columns": [{"name": "id", "data_type": "integer"}]},
        ],
        "relations": [{"name": "fk", "child_table": "SALES.ORDERS", "child_columns": ["REGION_ID"],
                       "parent_table": "sales.regions", "parent_columns": ["id"]}],
        "definitions": [{"term": "revenue", "meaning": "Sum of order amounts"}],
    }


def test_supplied_catalog_parses_nested_columns_relations_and_definitions():
    catalog = catalog_from_dict(supplied())

    assert [table.key for table in catalog.tables] == ["sales.orders", "sales.regions"]
    assert catalog.columns[1].data_type == "unknown"
    assert catalog.relations[0].child_table == "sales.orders"
    assert catalog.relations[0].child_columns == ("region_id",)
    assert {definition.source for definition in catalog.definitions} == {
        "user table description", "user column description", "user glossary"
    }


def test_direct_catalog_is_sent_whole_to_discovery():
    data = {"tables": [{"name": f"table_{index}", "columns": [{"name": "id"}]}
                       for index in range(21)]}
    catalog = catalog_from_dict(data)

    class Provider:
        def select_query_space(self, understanding, context, candidates):
            assert len(candidates.tables) == 21
            assert len(candidates.columns) == 21
            return DiscoverySelection(("t0",), ("c0",), (), ())

    space = discover_query_space(
        catalog, Provider(), "Show table 0", ResolvedContext("2025", ("table 0",), (), (), "")
    )
    assert space.tables[0].name == "table_0"


@pytest.mark.parametrize("change", [
    lambda data: data["tables"][0]["columns"][0].update(nullable="yes"),
    lambda data: data["tables"][0].update(extra="ignored"),
    lambda data: data["relations"][0].update(parent_columns=["missing"]),
    lambda data: data["tables"].append(data["tables"][0]),
])
def test_invalid_supplied_catalog_is_rejected(change):
    data = supplied()
    change(data)
    with pytest.raises(ValueError):
        catalog_from_dict(data)


def test_load_catalog_file(tmp_path):
    path = tmp_path / "schema.json"
    path.write_text(json.dumps(supplied()), encoding="utf-8")
    assert load_catalog_file(path).tables[0].key == "sales.orders"


def test_invalid_catalog_file_does_not_echo_contents(tmp_path):
    path = tmp_path / "schema.json"
    path.write_text('{"password":"secret-token",', encoding="utf-8")
    with pytest.raises(ValueError) as error:
        load_catalog_file(path)
    assert "secret-token" not in str(error.value)
