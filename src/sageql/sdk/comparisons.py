"""Fixed local change calculation; no model formulas or new SQL operations."""

from __future__ import annotations

from decimal import Context, Decimal, DecimalException, ROUND_HALF_EVEN, localcontext
import math
import re
from typing import TYPE_CHECKING

from sageql.conversation import Message
from sageql.sdk.models import DatasetDefinition, ReportArtifact, ReportSpec, Scalar, SDKError

if TYPE_CHECKING:
    from sageql.sdk.intent import ReportIntent


def decline_ranking_requested(text: str) -> bool:
    """Shared bounded cue for the separately registered absolute-loss ranking."""
    return bool(re.search(r"(?:بیشترین|most|largest|greatest).{0,35}(?:کاهش|افت|decrease|decline|drop)|"
                          r"(?:کاهش|افت|decrease|decline|drop).{0,35}(?:بیشترین|most|largest|greatest)", text))


def comparison_evidence_context(intent: ReportIntent, messages: tuple[Message, ...],
                                current_spec: ReportSpec | None) -> ReportIntent:
    """A percentage request must not silently become an ordinary comparison.

    Normalize whole-period totals and the separately scoped entity decline
    ranking. Other grouped change requests keep their requested breakdown.
    """
    from dataclasses import replace
    text = next((item.content for item in reversed(messages) if item.role == "user"), "")
    text = " ".join(text.casefold().replace("\u200c", " ").split())
    requested = bool(re.search(r"درصد.{0,40}(?:تغییر|افزایش|کاهش|رشد)|(?:تغییر|افزایش|کاهش|رشد).{0,40}درصد|"
                               r"percent(?:age)?.{0,30}(?:change|increase|decrease|growth)", text))
    calculation = intent.comparison_calculation
    removed = bool(re.search(r"بدون.{0,12}درصد|درصد.{0,25}(?:حذف|نشان نده|نمایش نده)|حذف.{0,12}درصد|"
                            r"(?:without|remove|no).{0,15}percent", text))
    decline_rank = decline_ranking_requested(text)
    percentage_rank = bool(re.search(r"(?:بیشترین|بالاترین).{0,10}درصد|بیشترین.{0,16}(?:افت|کاهش).{0,6}درصدی|"
                                     r"(?:رتبه|مرتب|ترتیب).{0,20}درصد|(?:highest|largest|greatest).{0,10}percent|"
                                     r"(?:rank|sort).{0,15}percent", text))
    if (percentage_rank and intent.dimensions and intent.comparison is not None
            and (decline_rank or calculation == "decrease")):
        raise SDKError("unsupported", "Percentage-loss ranking is not registered; only absolute-loss ranking is supported.")
    if decline_rank and intent.comparison is not None and len(intent.dimensions) == 1:
        calculation = "decrease"
    elif removed:
        calculation = "none"
        requested = False
    elif requested and calculation != "decrease":
        calculation = "change"
    elif (calculation is None and intent.turn_kind in {"refine", "answer"}
          and current_spec is not None and intent.comparison is not None):
        calculation = current_spec.comparison_calculation
    explicit_breakdown = bool(re.search(r"به تفکیک|روز به روز|ماه به ماه|هفته به هفته|روزانه|هفتگی|"
                                        r"\b(?:daily|weekly|breakdown|group(?:ed)? by|month by month)\b", text))
    changes = {"comparison_calculation": calculation}
    if calculation == "decrease":
        changes.update(order_by="absolute_decrease", ordering_specified=True, descending=True)
        if intent.limit is None:
            changes["limit"] = (current_spec.limit if current_spec is not None
                                and intent.turn_kind in {"refine", "answer"} else 100)
        if not explicit_breakdown:
            changes["time_grain"] = "none"
    if (calculation == "change" and intent.comparison is not None and not intent.dimensions
            and not explicit_breakdown and (requested or intent.time_grain in {None, "none"})):
        changes["time_grain"] = "none"
    return replace(intent, **changes)


def validate_comparison_calculation(spec: ReportSpec, dataset: DatasetDefinition) -> None:
    from sageql.sdk.semantics import column_type
    if not isinstance(spec.comparison_calculation, str) or spec.comparison_calculation not in {"none", "change", "decrease"}:
        raise SDKError("invalid_spec", "Unknown comparison calculation.")
    if spec.comparison_calculation == "none":
        return
    if spec.comparison_calculation == "decrease":
        from sageql.sdk.decreases import validate_decrease
        validate_decrease(spec, dataset)
        return
    if (spec.comparison is None or not spec.metric_ids or spec.dimension_ids
            or spec.time_grain != "none" or spec.chart != "table" or spec.aggregate_filters):
        raise SDKError("unsupported", "Change calculation requires two ungrouped aggregate periods in a table.")
    if type(spec.limit) is not int or spec.limit < max(2, len(spec.metric_ids)):
        raise SDKError("invalid_spec", "The result limit must fit both periods and all selected measures.")
    columns = {item.name: item for item in dataset.columns}
    metrics = {item.id: item for item in dataset.metrics}
    for identifier in spec.metric_ids:
        metric = metrics[identifier]
        if metric.aggregation not in {"count_rows", "count_distinct"} and column_type(columns[metric.column].data_type) not in {"integer", "decimal", "number"}:
            raise SDKError("unsupported", "Change calculation requires numeric aggregates.")


def calculate_change(current: Scalar, reference: Scalar) -> tuple[Decimal | None, Decimal | None, str]:
    """Return (absolute Decimal, percent Decimal, fixed status) before rounding.

    A 400-digit context covers SQL decimals and the entire finite float range.
    It is bounded and independent of a calling application's decimal context.
    """
    def number(value: Scalar) -> Decimal | None:
        if value is None:
            return None
        if (type(value) not in {int, float, Decimal}
                or type(value) is int and value.bit_length() > 1024
                or type(value) is float and not math.isfinite(value)):
            raise ValueError
        result = Decimal(str(value))
        if (not result.is_finite() or len(result.as_tuple().digits) > 400
                or result and not -400 <= result.adjusted() <= 400):
            raise ValueError
        return result

    try:
        left, right = number(current), number(reference)
        if left is None or right is None:
            return None, None, "missing_value"
        with localcontext(Context(prec=400, rounding=ROUND_HALF_EVEN)):
            absolute = left - right
            if right == 0:
                return absolute, None, "zero_baseline"
            if right < 0:
                return absolute, None, "negative_baseline"
            percent = absolute / right * 100
            # A finite, bounded result is mandatory even for custom adapters.
            number(absolute)
            number(percent)
            status = "increase" if absolute > 0 else "decrease" if absolute < 0 else "unchanged"
            return absolute, percent, status
    except (ValueError, TypeError, DecimalException, OverflowError):
        raise SDKError("adapter_failed", "Comparison contains invalid numeric values.") from None


def change_status_label(status: str, language: str) -> str:
    labels = {
        "fa": {"increase": "افزایش", "decrease": "کاهش", "unchanged": "بدون تغییر",
               "missing_value": "دادهٔ کافی برای محاسبه نیست",
               "zero_baseline": "مبنای صفر؛ درصد تعریف نمی‌شود",
               "negative_baseline": "مبنای منفی؛ درصد محاسبه نمی‌شود"},
        "en": {"increase": "Increase", "decrease": "Decrease", "unchanged": "Unchanged",
               "missing_value": "Missing aggregate value", "zero_baseline": "Zero reference; percentage undefined",
               "negative_baseline": "Negative reference; percentage unavailable"},
    }
    return labels[language][status]


def make_change_report(report: ReportArtifact, spec: ReportSpec, *, language: str,
                       max_rows: int) -> ReportArtifact:
    """Pivot the two validated aggregate rows into one fixed row per measure."""
    from dataclasses import replace
    from sageql.sdk.models import ReportField
    if (report.truncated or len(report.rows) != 2
            or len(spec.metric_ids) > min(spec.limit, max_rows)
            or any(field.type not in {"integer", "decimal", "number"} for field in report.fields[1:])):
        raise SDKError("adapter_failed", "Comparison requires both complete numeric period totals.")
    periods = {}
    for row in report.rows:
        if not isinstance(row[0], str) or row[0] not in {"base", "comparison"} or row[0] in periods:
            raise SDKError("adapter_failed", "Comparison returned invalid period rows.")
        periods[row[0]] = row[1:]
    labels = report.provenance["period_labels"]
    fields = (
        ReportField("metric_label", "شاخص" if language == "fa" else "Measure", "text"),
        ReportField("comparison_value", labels["comparison"], "number"),
        ReportField("base_value", labels["base"], "number"),
        ReportField("absolute_change", "تغییر" if language == "fa" else "Absolute change", "number"),
        ReportField("percent_change", "درصد تغییر" if language == "fa" else "Percentage change", "number", "%"),
        ReportField("change_status", "وضعیت تغییر" if language == "fa" else "Change status", "text"),
    )
    rows, statuses = [], []
    for index, metric in enumerate(report.fields[1:]):
        current, reference = periods["base"][index], periods["comparison"][index]
        absolute, percent, status = calculate_change(current, reference)
        # Float sources retain their existing concise numeric presentation.
        if metric.type == "number" and absolute is not None:
            approximate = float(absolute)
            if math.isfinite(approximate):
                absolute = approximate
        label = metric.label + (f" ({metric.unit})" if metric.unit else "")
        rows.append((label, reference, current, absolute, percent, change_status_label(status, language)))
        statuses.append({"metric_id": metric.id, "status": status})
    title = ("تغییر مطلق و درصدی: " if language == "fa" else "Absolute and percentage change: ") + report.title
    return replace(report, title=title, fields=fields, rows=tuple(rows), provenance={
        **report.provenance, "comparison_calculation": "change",
        "percentage_reference": "comparison", "change_statuses": statuses,
    })
