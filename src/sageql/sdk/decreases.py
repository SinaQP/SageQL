"""Fixed complete-candidate identity decline ranking before label enrichment."""

from dataclasses import replace
from decimal import Decimal
import math

from sageql.sdk.comparisons import calculate_change
from sageql.sdk.models import (
    DatasetDefinition, EntityLabelDimension, ReportArtifact, ReportField,
    ReportSpec, SDKError,
)
from sageql.sdk.semantics import _value, column_type


def validate_decrease(spec: ReportSpec, dataset: DatasetDefinition) -> None:
    dimensions = {item.id: item for item in dataset.dimensions}
    metrics = {item.id: item for item in dataset.metrics}
    if (spec.comparison is None or len(spec.metric_ids) != 1 or len(spec.dimension_ids) != 1
            or not isinstance(dimensions[spec.dimension_ids[0]], EntityLabelDimension)
            or spec.time_grain != "none" or spec.chart != "table" or spec.aggregate_filters
            or spec.order_by != "absolute_decrease" or spec.descending is not True):
        raise SDKError("unsupported", "Decline ranking requires one label identity and additive metric with fixed absolute-loss ordering.")
    metric = metrics[spec.metric_ids[0]]
    columns = {item.name: item for item in dataset.columns}
    if (metric.aggregation not in {"sum", "count_rows", "count_distinct"}
            or metric.aggregation == "sum" and column_type(columns[metric.column].data_type) not in {"integer", "decimal", "number"}):
        raise SDKError("unsupported", "Decline ranking requires a numeric additive aggregate.")


def make_decrease_report(report: ReportArtifact, spec: ReportSpec, dataset: DatasetDefinition,
                         *, language: str, max_rows: int) -> ReportArtifact:
    """Align complete period groups, then rank exact loss before the final cap."""
    if (report.truncated or len(report.rows) > max_rows or len(report.fields) != 3
            or report.fields[2].type not in {"integer", "decimal", "number"}):
        raise SDKError("adapter_failed", "Decline ranking needs complete numeric candidate groups within host limits.")
    dimension = next(item for item in dataset.dimensions if item.id == spec.dimension_ids[0])
    family = column_type(next(item for item in dataset.columns if item.name == dimension.column).data_type)
    groups = {}
    for row in report.rows:
        period, identity, value = row
        if not isinstance(period, str) or period not in {"base", "comparison"}:
            raise SDKError("adapter_failed", "Decline ranking returned invalid period labels.")
        if identity is not None:
            _value(identity, family, "adapter_failed")
        calculate_change(value, 1)  # Validate every scalar, including excluded groups.
        values = groups.setdefault(identity, {})
        if period in values:
            raise SDKError("adapter_failed", "Decline ranking returned duplicate identity-period groups.")
        values[period] = value
    excluded = {"null_identity": 0, "missing_value": 0, "nonpositive_reference": 0, "non_decrease": 0}
    ranked = []
    for identity, values in groups.items():
        current, reference = values.get("base", 0), values.get("comparison", 0)
        absolute, percent, status = calculate_change(current, reference)
        if identity is None:
            excluded["null_identity"] += 1
        elif status == "missing_value":
            excluded["missing_value"] += 1
        elif status in {"zero_baseline", "negative_baseline"}:
            excluded["nonpositive_reference"] += 1
        elif status != "decrease":
            excluded["non_decrease"] += 1
        else:
            ranked.append((absolute.copy_negate(), identity, reference, current, percent.copy_negate()))
    ranked.sort(key=lambda row: (row[0].copy_negate(), row[1]))
    metric = report.fields[2]
    labels = report.provenance["period_labels"]
    fields = (
        report.fields[1],
        ReportField("comparison_value", labels["comparison"], metric.type, metric.unit),
        ReportField("base_value", labels["base"], metric.type, metric.unit),
        ReportField("absolute_decrease", "کاهش مطلق" if language == "fa" else "Absolute decrease", metric.type, metric.unit),
        ReportField("percent_decrease", "درصد افت" if language == "fa" else "Percentage decrease", "number", "%"),
    )
    def display_loss(value: Decimal) -> Decimal | float:
        approximate = float(value) if metric.type == "number" else None
        return approximate if approximate is not None and math.isfinite(approximate) else value
    cap = min(spec.limit, max_rows)
    rows = tuple((identity, reference, current, display_loss(loss), percent)
                 for loss, identity, reference, current, percent in ranked[:cap])
    truncated = len(ranked) > cap
    title = ("بیشترین کاهش مطلق: " if language == "fa" else "Largest absolute decrease: ") + report.title
    return replace(report, title=title, fields=fields, rows=rows, truncated=truncated,
                   provenance={**report.provenance, "comparison_calculation": "decrease",
                               "percentage_reference": "comparison", "ranking": "absolute_decrease_desc",
                               "candidate_rows": len(report.rows), "eligible_groups": len(ranked),
                               "excluded_groups": excluded,
                               "completeness": "truncated" if truncated else "complete" if rows else "empty"})
