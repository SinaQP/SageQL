"""Deterministic report interpretation phrases (filters, conditions, sort, limit)."""
from decimal import Decimal

from sageql.sdk import AggregateFilter, PeriodSelection, ReportSpec, UserFilter
from sageql.sdk.engine import _interpretation
from test_sdk_intent import catalog


def dataset(identifier):
    return next(item for item in catalog().datasets if item.id == identifier)


def test_conditions_sort_and_limit_use_registered_labels():
    spec = ReportSpec("activities", ("hours",), ("unit",), period=PeriodSelection("last_month"),
                      aggregate_filters=(AggregateFilter("hours", "gt", (Decimal("10"),)),),
                      order_by="hours", descending=True, limit=5)
    assert _interpretation(spec, dataset("activities"), catalog(), "fa") == [
        "ساعات فعالیت بیشتر از 10", "مرتب بر اساس ساعات فعالیت (نزولی)", "حداکثر 5 ردیف"]
    assert _interpretation(spec, dataset("activities"), catalog(), "en") == [
        "ساعات فعالیت > 10", "sorted by ساعات فعالیت (descending)", "at most 5 rows"]


def test_row_filters_and_defaults():
    spec = ReportSpec("employees", ("people",), filters=(UserFilter("identity_filter", "in", (3, 4)),))
    assert _interpretation(spec, dataset("employees"), catalog(), "en") == ["شناسه is one of 3, 4"]
    plain = ReportSpec("activities", ("hours",), period=PeriodSelection("last_month"))
    assert _interpretation(plain, dataset("activities"), catalog(), "fa") == []
