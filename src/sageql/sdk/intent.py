"""Business intent constraints, checked independently of a proposed report.

Intent is untrusted model output, never authority to add catalog capabilities.
These checks prove consistency with the extracted intent, not natural-language
understanding. They neither access data nor create cross-source operations.
"""

from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any

from sageql.schema import Column
from sageql.sdk.models import (
    AggregateFilter, DatasetDefinition, EntityLabelDimension, RelatedAttributeDimension, Interpretation, PeriodSelection,
    ReportingCatalog, ReportSpec, SDKError, UserFilter, json_value,
)


MISSING_DETAILS = (
    "request", "measure", "period", "year", "calendar", "grouping",
    "entity_name", "entity_qualifier", "filter_value", "comparison", "chart",
)

CAPABILITY_INSTRUCTIONS = (
    " Each report selects ONE registered fact dataset. It can include registered "
    "related attributes exposed in that dataset, with measures, multi-dimension "
    "grouping, related filters, time grouping, comparisons and metric ranking. "
    "Related attributes are ordinary grouping/filtering capabilities and require "
    "no implementation confirmation. All selected measures, "
    "grouping dimensions and filters must be available together in that dataset. "
    "Concepts in separate datasets are not automatically combinable. An entity_label "
    "only decorates identity groups; it cannot merge groups by a profile attribute. "
    "A name-lookup qualifier is not an aggregate grouping capability. If the "
    "requested combination is unavailable, explain that it is unsupported. Never "
    "silently retain the old grouping, substitute a count/profile listing, or ask "
    "permission to combine sources. User confirmation cannot enable a capability. "
    "The latest requested change takes precedence over unchanged current_spec. "
    "Every NEW aggregate report on a dataset with time needs a period supplied "
    "by the user/conversation. No supplied period does not mean all dates, even "
    "when this is a simple grouped total rather than a ranking. Ask for the "
    "period. Use all only for an explicit all-data request. A refinement preserves "
    "the current report's period unless the user changes it. Timeless reports "
    "and dimension-only listings do not require a period clarification. "
    "Short answers resolve the earlier business question; do not re-ask an answered "
    "question or treat an earlier assistant's technical suggestion as a requirement."
    " Comparing TWO explicit Jalali months is supported: select one jalali_month "
    "as period and the other independent jalali_month as comparison, with table "
    "presentation and time_grain none (or Gregorian day). Each has its supplied "
    "year/month. This is a comparison of two bounded periods, not an arbitrary "
    "Jalali range or Jalali monthly bucket. Never reject that registered capability."
)


@dataclass(frozen=True)
class ConceptRef:
    dataset_id: str
    concept_id: str


@dataclass(frozen=True)
class ReportIntent:
    """Complete effective measures/grouping, including unchanged report intent.

    References belong to their specific permitted datasets. Empty dimensions
    mean an ungrouped report, not permission to preserve an earlier grouping.
    Optional chart/time grain constrain only explicitly selected presentation.
    Period is the effective supplied/preserved selection; null denotes missing
    dates for a dated aggregate, rather than permission to use all dates.
    ``answer`` denotes a response to the pending clarification; ``new`` starts
    an independent request and may legitimately need the same kind of detail.

    Optional control constraints preserve older provider-neutral backends. None
    filter tuples mean unspecified; empty tuples explicitly require no filters.
    ``comparison_specified`` and ``ordering_specified`` allow an explicit null
    comparison/order to remove a previous control. Direction and output limit
    constrain only supplied values. Live extraction supplies effective controls.
    """

    metrics: tuple[ConceptRef, ...] = ()
    dimensions: tuple[ConceptRef, ...] = ()
    missing: tuple[str, ...] = ()
    turn_kind: str = "new"
    unsupported_reason: str = ""
    chart: str | None = None
    time_grain: str | None = None
    period: PeriodSelection | None = None
    comparison: PeriodSelection | None = None
    comparison_specified: bool = False
    filters: tuple[UserFilter, ...] | None = None
    aggregate_filters: tuple[AggregateFilter, ...] | None = None
    order_by: str | None = None
    ordering_specified: bool = False
    descending: bool | None = None
    limit: int | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "metrics": [{"dataset_id": item.dataset_id, "concept_id": item.concept_id} for item in self.metrics],
            "dimensions": [{"dataset_id": item.dataset_id, "concept_id": item.concept_id} for item in self.dimensions],
            "missing": list(self.missing), "turn_kind": self.turn_kind,
            "unsupported_reason": self.unsupported_reason,
            "chart": self.chart, "time_grain": self.time_grain,
            "period": json_value(self.period),
            "comparison": json_value(self.comparison), "comparison_specified": self.comparison_specified,
            "filters": json_value(self.filters), "aggregate_filters": json_value(self.aggregate_filters),
            "order_by": self.order_by, "ordering_specified": self.ordering_specified,
            "descending": self.descending, "limit": self.limit,
        }


def _intent_dataset(intent: ReportIntent, catalog: ReportingCatalog) -> DatasetDefinition | None:
    identifiers = {item.dataset_id for item in intent.metrics} or {item.dataset_id for item in intent.dimensions}
    return (next(item for item in catalog.datasets if item.id == next(iter(identifiers)))
            if len(identifiers) == 1 else None)


def _condition_family(dataset: DatasetDefinition, identifier: str, *, aggregate: bool) -> str:
    from sageql.sdk.semantics import column_type
    if aggregate:
        definition = next(item for item in dataset.metrics if item.id == identifier)
        if definition.aggregation in {"count_rows", "count_distinct"}:
            return "integer"
        family = column_type(next(item for item in dataset.columns if item.name == definition.column).data_type)
        return "decimal" if family == "integer" and definition.aggregation in {"sum", "average"} else family
    definition = next((item for item in dataset.filters if item.id == identifier), None)
    if definition is None:  # Registered virtual names/qualifiers are text equality.
        return "text"
    return column_type(next(item for item in dataset.columns if item.name == definition.column).data_type)


def _check_conditions(intent: ReportIntent, catalog: ReportingCatalog) -> None:
    from sageql.sdk.semantics import _predicate
    dataset = _intent_dataset(intent, catalog)
    for conditions, kind, aggregate in ((intent.filters, UserFilter, False),
                                        (intent.aggregate_filters, AggregateFilter, True)):
        if conditions is None:
            continue
        if not isinstance(conditions, tuple) or len(conditions) > 32 or (conditions and dataset is None):
            raise ValueError
        definitions = ({item.id: item.operators for item in dataset.filters} if dataset and not aggregate else {})
        if dataset and not aggregate:
            for lookup in catalog.lookups:
                if lookup.dataset_id == dataset.id:
                    definitions.update({lookup.id: ("eq",), **{item.id: ("eq",) for item in lookup.qualifiers}})
        seen = set()
        for condition in conditions:
            if not isinstance(condition, kind) or not isinstance(condition.operator, str):
                raise ValueError
            identifier = condition.metric_id if aggregate else condition.filter_id
            if (not isinstance(identifier, str)
                    or (aggregate and identifier not in {item.concept_id for item in intent.metrics
                                                        if item.dataset_id == dataset.id})
                    or (not aggregate and (identifier not in definitions or condition.operator not in definitions[identifier]))
                    or (identifier, condition.operator) in seen):
                raise ValueError
            seen.add((identifier, condition.operator))
            if (not isinstance(condition.values, tuple) or len(condition.values) > 100
                    or any(isinstance(value, str) and len(value) > 1000 for value in condition.values)):
                raise ValueError
            family = _condition_family(dataset, identifier, aggregate=aggregate)
            data_type = {"integer": "bigint", "decimal": "decimal", "number": "float",
                         "text": "nvarchar", "date": "date", "boolean": "bit"}[family]
            _predicate(Column(dataset.table.key, "intent_value", data_type), condition.operator,
                       condition.values, "invalid_interpretation")


def _condition_keys(conditions: tuple[UserFilter, ...] | tuple[AggregateFilter, ...],
                    dataset: DatasetDefinition | None = None, *, aggregate: bool = False) -> set[tuple[Any, ...]]:
    result = set()
    for condition in conditions:
        identifier = condition.metric_id if aggregate else condition.filter_id
        family = _condition_family(dataset, identifier, aggregate=aggregate) if dataset else None
        values = []
        for value in condition.values:
            if family in {"integer", "decimal", "number"}:
                try:
                    number = Decimal(str(value))
                    values.append(("number", number) if number.is_finite() else ("invalid_number",))
                except (InvalidOperation, ValueError):
                    values.append(("invalid_number",))
            else:
                rendered = json_value(value)
                values.append((type(rendered).__name__, rendered))
        values = tuple(values)
        # Conjunction order and IN member order do not alter the report.
        result.add((identifier, condition.operator, frozenset(values) if condition.operator == "in" else values))
    return result


def check_intent(intent: ReportIntent, catalog: ReportingCatalog, *, today: date | None = None) -> None:
    try:
        if (not isinstance(intent, ReportIntent)
                or intent.turn_kind not in ("new", "refine", "answer")
                or not isinstance(intent.unsupported_reason, str)
                or len(intent.unsupported_reason) > 2000
                or intent.chart not in (None, "table", "bar", "line", "kpi")
                or intent.time_grain not in (None, "none", "day", "week", "month", "quarter", "year")
                or (intent.period is not None and not isinstance(intent.period, PeriodSelection))
                or (intent.comparison is not None and not isinstance(intent.comparison, PeriodSelection))
                or type(intent.comparison_specified) is not bool
                or (not intent.comparison_specified and intent.comparison is not None)
                or type(intent.ordering_specified) is not bool
                or (intent.order_by is not None and (not intent.ordering_specified or not isinstance(intent.order_by, str)))
                or (intent.descending is not None and type(intent.descending) is not bool)
                or (intent.limit is not None and (type(intent.limit) is not int or not 1 <= intent.limit <= 10_000))
                or not isinstance(intent.missing, tuple) or len(intent.missing) > len(MISSING_DETAILS)
                or any(not isinstance(item, str) or item not in MISSING_DETAILS for item in intent.missing)
                or len(set(intent.missing)) != len(intent.missing)):
            raise ValueError
        for refs, attribute in ((intent.metrics, "metrics"), (intent.dimensions, "dimensions")):
            if not isinstance(refs, tuple) or len(refs) > 16:
                raise ValueError
            seen = set()
            for ref in refs:
                if (not isinstance(ref, ConceptRef) or not isinstance(ref.dataset_id, str)
                        or not isinstance(ref.concept_id, str)):
                    raise ValueError
                dataset = next((item for item in catalog.datasets if item.id == ref.dataset_id), None)
                if (dataset is None or ref.concept_id not in {item.id for item in getattr(dataset, attribute)}
                        or ref in seen):
                    raise ValueError
                seen.add(ref)
        if not (intent.metrics or intent.dimensions or intent.missing or intent.unsupported_reason.strip()):
            raise ValueError
        _check_conditions(intent, catalog)
        ordering = {item.concept_id for item in (*intent.metrics, *intent.dimensions)}
        if intent.time_grain not in (None, "none"):
            ordering.add("time_bucket")
        if intent.comparison is not None:
            ordering.add("period_label")
        if intent.order_by is not None and intent.order_by not in ordering:
            raise ValueError
        if today is not None:
            from sageql.sdk.semantics import resolve_period
            for selection in (intent.period, intent.comparison):
                if selection is not None:
                    resolved = resolve_period(selection, today)
                    if selection is intent.comparison and resolved.start is None:
                        raise ValueError
    except (ValueError, TypeError, AttributeError, SDKError):
        raise SDKError("invalid_interpretation", "Report intent is invalid.") from None


def period_context(intent: ReportIntent, catalog: ReportingCatalog,
                   current_spec: ReportSpec | None) -> ReportIntent:
    """Require a structured effective period for dated aggregates, not listings.

    An omitted period cannot silently become all data. Existing time clarification
    slots remain specific (e.g. year); a regrouping inherits its current period.
    Natural-language extraction remains fallible, but intent/planning now share
    the same typed period requirement instead of contradicting each other.
    """
    datasets = {ref.dataset_id for ref in intent.metrics}
    if len(datasets) != 1 or intent.period is not None:
        return intent
    dataset = next(item for item in catalog.datasets if item.id == next(iter(datasets)))
    if dataset.time is None:
        return intent
    if {"period", "year", "calendar"}.intersection(intent.missing):
        return intent
    if (intent.turn_kind in {"refine", "answer"} and current_spec is not None
            and current_spec.dataset_id == dataset.id):
        return replace(intent, period=current_spec.period)
    return replace(intent, missing=(*intent.missing, "period"))


def unavailable_intent(intent: ReportIntent, catalog: ReportingCatalog, language: str) -> Interpretation | None:
    refs = (*intent.metrics, *intent.dimensions)
    if len({item.dataset_id for item in refs}) > 1:
        labels = []
        for ref in refs:
            dataset = next(item for item in catalog.datasets if item.id == ref.dataset_id)
            concept = next(item for item in (*dataset.metrics, *dataset.dimensions) if item.id == ref.concept_id)
            if concept.label not in labels:
                labels.append(concept.label)
        message = (
            "گزارش درخواستی به ترکیب «" + "، ".join(labels) + "» نیاز دارد؛ این ترکیب در قابلیت‌های ثبت‌شدهٔ فعلی پشتیبانی نمی‌شود. میزبان باید منبع گزارش مناسب را ثبت کند."
            if language == "fa" else
            "The requested combination of " + ", ".join(labels)
            + " is not available together in a registered report. The host must register a suitable reporting source."
        )
        return Interpretation("unsupported", message=message)
    # A model's unsupported explanation is advisory. Only deterministic catalog
    # incompatibility bypasses planning/review; supported operations deserve review.
    return None


def canonical_intent(intent: ReportIntent, catalog: ReportingCatalog) -> ReportIntent:
    """A bar axis can display the label of an already selected identity group.

    Selecting both the identity and its registered display label repeats the
    same target grouping column. For a bar, retain the label and remove only
    that redundant plain identity dimension. Distinct grouping columns and
    multiple label mappings remain unchanged and undergo normal validation.
    The physical equivalence is checked locally, never exposed to the model.
    """
    metric_datasets = {item.dataset_id for item in intent.metrics}
    if len(metric_datasets) == 1:
        fact_id = next(iter(metric_datasets))
        fact = next(item for item in catalog.datasets if item.id == fact_id)
        effective = []
        for ref in intent.dimensions:
            equivalents = [item for item in fact.dimensions if isinstance(item, RelatedAttributeDimension)
                           and item.source_dataset_id == ref.dataset_id
                           and item.source_dimension_id == ref.concept_id]
            # Two roles pointing at the same source attribute remain ambiguous.
            # The model must choose their separate registered business concepts.
            effective.append(ConceptRef(fact_id, equivalents[0].id)
                             if ref.dataset_id != fact_id and len(equivalents) == 1 else ref)
        intent = replace(intent, dimensions=tuple(dict.fromkeys(effective)))
    if intent.chart != "bar":
        return intent
    definitions = {}
    for ref in intent.dimensions:
        dataset = next(item for item in catalog.datasets if item.id == ref.dataset_id)
        definitions[ref] = next(item for item in dataset.dimensions if item.id == ref.concept_id)
    labels = {(ref.dataset_id, item.column) for ref, item in definitions.items()
              if isinstance(item, EntityLabelDimension)}
    dimensions = tuple(ref for ref, item in definitions.items()
                       if isinstance(item, EntityLabelDimension) or (ref.dataset_id, item.column) not in labels)
    return replace(intent, dimensions=dimensions)


def intent_feedback(intent: ReportIntent, decision: Interpretation, *, today: date | None = None,
                    catalog: ReportingCatalog | None = None) -> str | None:
    """Fixed local feedback only; no raw values/errors cross the model boundary."""
    if decision.status == "needs_clarification":
        return None if intent.missing else "intent_validation: unnecessary_clarification"
    if decision.status != "ready":
        return None
    if intent.missing:
        return "intent_validation: missing_information"
    spec = decision.spec
    for selected, proposed, mismatch in ((intent.period, spec.period, "period_mismatch"),
                                         (intent.comparison, spec.comparison, "comparison_mismatch")):
        if selected is None:
            continue
        from sageql.sdk.semantics import resolve_period
        try:
            same_period = (proposed is not None and
                           (resolve_period(selected, today) == resolve_period(proposed, today)
                            if today is not None else selected == proposed))
        except SDKError as error:
            if error.code not in {"invalid_spec", "unsupported"}:
                raise
            return "specification_validation: " + error.code
        if (not same_period or ((selected.kind == "jalali_month" or proposed.kind == "jalali_month")
                                and selected != proposed)):
            return "intent_validation: " + mismatch
    if intent.comparison_specified and intent.comparison is None and spec.comparison is not None:
        return "intent_validation: comparison_mismatch"
    if (any(item.dataset_id != spec.dataset_id for item in (*intent.metrics, *intent.dimensions))
            or set(spec.metric_ids) != {item.concept_id for item in intent.metrics}
            or set(spec.dimension_ids) != {item.concept_id for item in intent.dimensions}
            or (intent.chart is not None and intent.chart != spec.chart)
            or (intent.time_grain is not None and intent.time_grain != spec.time_grain)):
        return "intent_validation: report_mismatch"
    dataset = _intent_dataset(intent, catalog) if catalog is not None else None
    for selected, proposed, aggregate, mismatch in (
        (intent.filters, spec.filters, False, "filter_mismatch"),
        (intent.aggregate_filters, spec.aggregate_filters, True, "aggregate_filter_mismatch"),
    ):
        if selected is not None and _condition_keys(selected, dataset, aggregate=aggregate) != _condition_keys(
                proposed, dataset, aggregate=aggregate):
            return "intent_validation: " + mismatch
    if ((intent.ordering_specified and intent.order_by != spec.order_by)
            or (intent.descending is not None and intent.descending != spec.descending)):
        return "intent_validation: ordering_mismatch"
    if intent.limit is not None and intent.limit != spec.limit:
        return "intent_validation: limit_mismatch"
    return None


def clarification_key(intent: ReportIntent) -> str:
    content = json.dumps({
        "metrics": sorted((item.dataset_id, item.concept_id) for item in intent.metrics),
        "dimensions": sorted((item.dataset_id, item.concept_id) for item in intent.dimensions),
        "missing": sorted(intent.missing),
        "period": json_value(intent.period),
        "comparison": json_value(intent.comparison), "comparison_specified": intent.comparison_specified,
        "filters": json_value(intent.filters), "aggregate_filters": json_value(intent.aggregate_filters),
        "order_by": intent.order_by, "ordering_specified": intent.ordering_specified,
        "descending": intent.descending, "limit": intent.limit,
    }, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
