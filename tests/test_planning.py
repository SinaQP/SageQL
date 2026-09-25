import pytest

from sageql.context import ResolvedContext
from sageql.discovery import QuerySpace
from sageql.planning import (
    PlanProposal, PlanningError, ProposedFilter, ProposedJoin, ProposedMeasure,
    create_query_plan, review_query_plan,
)
from sageql.schema import Column, Definition, Relation, Table


def space():
    return QuerySpace(
        (Table("orders", "sales"), Table("regions", "sales")),
        (
            Column("sales.orders", "amount", "decimal"),
            Column("sales.orders", "order_date", "date"),
            Column("sales.orders", "region_id", "integer"),
            Column("sales.regions", "region_id", "integer"),
            Column("sales.regions", "name", "text"),
        ),
        (Relation("fk_orders_region", "sales.orders", ("region_id",),
                  "sales.regions", ("region_id",)),),
        (Definition("revenue", "Sum of sales.orders.amount", "user glossary"),),
    )


def context():
    return ResolvedContext("monthly 2025", ("region",), ("revenue",), (), "")


def proposal(**changes):
    values = {
        "base_table_id": "t0",
        "joins": (ProposedJoin("r0", "t1", "left"),),
        "time_column_id": "c1",
        "time_grain": "month",
        "dimensions": ("c4",),
        "measures": (ProposedMeasure("revenue", "sum", "c0"),),
        "filters": (),
    }
    values.update(changes)
    return PlanProposal(**values)


class Provider:
    def __init__(self, result):
        self.result = result

    def propose_query_plan(self, understanding, resolved, candidates):
        assert resolved == context()
        assert [table.key for table in candidates.tables.values()] == ["sales.orders", "sales.regions"]
        return self.result


def test_plan_has_ordered_operations_and_quality_review():
    query_space = space()
    resolved = context()
    plan = create_query_plan("Monthly revenue by region for 2025", resolved, query_space,
                             Provider(proposal()))
    operations = plan.operations()

    assert [item["operation"] for item in operations] == [
        "scan", "join", "filter_time", "aggregate"
    ]
    assert operations[0]["table"] == "sales.orders"
    assert operations[1]["type"] == "left"
    assert operations[1]["child_keys"] == ["sales.orders.region_id"]
    assert operations[2]["period_phrase"] == "monthly 2025"
    assert operations[3]["group_by"] == ["sales.regions.name"]
    assert operations[3]["measures"][0]["function"] == "sum"

    quality = review_query_plan(plan, resolved, query_space)
    assert quality.structurally_valid
    assert len(quality.checks_passed) == 3
    assert any("exact date boundaries" in item for item in quality.review_items)


def test_explicit_formula_in_understanding_needs_no_formula_review():
    resolved = ResolvedContext("monthly 2025", ("region",), ("sales.orders.amount",), (), "")
    class FormulaProvider:
        def propose_query_plan(self, understanding, context, candidates):
            return proposal(measures=(ProposedMeasure("sales.orders.amount", "sum", "c0"),))

    plan = create_query_plan(
        "Monthly sum of sales.orders.amount by region for 2025",
        resolved, space(), FormulaProvider()
    )
    quality = review_query_plan(plan, resolved, space())
    assert not any("business formula" in item for item in quality.review_items)


def test_all_base_rows_repair_inner_join_to_left_join():
    plan = create_query_plan(
        "Monthly revenue by region for 2025, using all orders",
        context(), space(), Provider(proposal(joins=(ProposedJoin("r0", "t1", "inner"),)))
    )
    assert plan.joins[0].join_type == "left"
    assert any("preserve all requested base rows" in item for item in plan.repairs)


@pytest.mark.parametrize("bad", [
    proposal(base_table_id="t99"),
    proposal(joins=(ProposedJoin("r0", "t0", "left"),)),
    proposal(joins=()),
    proposal(time_column_id="c99"),
    proposal(time_grain="year"),
    proposal(dimensions=("c99",)),
    proposal(dimensions=({},)),
    proposal(measures=()),
    proposal(measures=(ProposedMeasure("revenue", "count_rows", None),)),
    proposal(measures=(ProposedMeasure("revenue", "sum", "c4"),)),
    proposal(measures=(ProposedMeasure("invented", "sum", "c0"),)),
    proposal(filters=(ProposedFilter("invented", "c0", "eq", ("x",)),)),
])
def test_rejects_unsupported_or_incomplete_operations(bad):
    with pytest.raises(PlanningError):
        create_query_plan("Monthly revenue by region for 2025", context(), space(), Provider(bad))


def test_filter_and_comparison_are_preserved_as_logical_operations():
    resolved = ResolvedContext("2025", ("region",), ("revenue",), ("Completed orders only",), "2024")
    class FilterProvider:
        def propose_query_plan(self, understanding, context, candidates):
            return proposal(
                time_grain="none",
                filters=(ProposedFilter("Completed orders only", "c2", "eq", ("Completed",)),),
            )

    plan = create_query_plan("Revenue by region, completed orders only, 2025 versus 2024",
                             resolved, space(), FilterProvider())
    assert [item["operation"] for item in plan.operations()][-2:] == ["aggregate", "compare_periods"]
    assert plan.operations()[3]["source_phrase"] == "Completed orders only"
    quality = review_query_plan(plan, resolved, space())
    assert any("comparison-period alignment" in item for item in quality.review_items)
    assert any("Check that filter values" in item for item in quality.review_items)


def test_count_all_rows_needs_no_time_column():
    resolved = ResolvedContext("all available data", ("orders",), ("order count",), (), "")
    query_space = QuerySpace((Table("orders"),), (Column("orders", "id", "integer"),), (), ())
    class CountProvider:
        def propose_query_plan(self, understanding, context, candidates):
            return PlanProposal("t0", (), "", "none", (),
                                (ProposedMeasure("order count", "count_rows", ""),), ())

    plan = create_query_plan("Count orders over all available data", resolved,
                             query_space, CountProvider())
    assert [item["operation"] for item in plan.operations()] == ["scan", "aggregate"]
    assert plan.operations()[1]["measures"][0]["column"] == ""


def test_provider_failure_is_sanitized():
    class FailingProvider:
        def propose_query_plan(self, understanding, context, candidates):
            raise RuntimeError("private schema detail")

    with pytest.raises(PlanningError, match="provider failed") as error:
        create_query_plan("Monthly revenue by region", context(), space(), FailingProvider())
    assert "private schema detail" not in str(error.value)
