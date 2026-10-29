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
import re
from typing import Any

from sageql.conversation import Message
from sageql.schema import Column
from sageql.sdk.evidence import OPERATION_LABELS, UnsupportedRequirement
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
    "only decorates identity groups; it cannot merge groups by a source attribute. "
    "A name-lookup qualifier is not an aggregate grouping capability. If the "
    "requested combination is unavailable, explain that it is unsupported. Never "
    "silently retain the old grouping, substitute a count/source listing, or ask "
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
    " Fixed absolute and PERCENTAGE CHANGE comparisons are supported with "
    "comparison_calculation change: select the current period as period and the "
    "reference period as comparison, numeric metrics, table, time_grain none, "
    "no dimensions or aggregate_filters and limit at least max(2, metric count). "
    "The host computes (current-reference)/reference*100 locally after execution; "
    "models never calculate results or supply formulas. Ordinary period rows do "
    "not fulfill a requested percentage change. A year supplied for two named "
    "months in the same comparison applies to both unless the user says otherwise. "
    " Entity decline rankings use comparison_calculation decrease, one registered "
    "entity_label dimension, one numeric sum/count metric, two bounded periods, "
    "table, time_grain none, no aggregate_filters, order_by absolute_decrease and "
    "descending true. The host aligns complete identity groups, fills only absent "
    "additive groups with zero, computes loss, selects strictly decreased groups "
    "with positive reference, ranks absolute loss before limiting, then fetches "
    "names. Percent loss is positive and uses the comparison period denominator. "
    "A request for greatest decrease in a measure ranks absolute loss in its unit, "
    "not current values or percentage. Use decrease even when percentage is not explicitly asked. "
    "Other grouped/time-series change calculations remain unsupported. Use none for "
    "ordinary comparisons and preserve the calculation on unchanged refinements."
    " Matching daily entity counts are supported with include_matching_day_count "
    "true: select one registered entity_label dimension, daily grain, numeric "
    "metrics, bounded periods and table. Select ordinary aggregate_filters for "
    "conditions on DAILY TOTALS. The host counts filtered daily groups per entity "
    "and period before limits and resolves names afterwards. The additional "
    "matching_day_count field is not a source-row count or a source metric. Use "
    "false for reports that do not request a count of matching days. This fixed "
    "operation supports ordinary two-period rows, not change/decrease calculations. "
    "Never omit a requested matching-day count or ask the user to calculate it. "
    "Preserve the flag on unchanged refinements and clear it when removed."
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
    comparison_calculation: str | None = None
    include_matching_day_count: bool | None = None
    unsupported_requirements: tuple[UnsupportedRequirement, ...] = ()

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
            "comparison_calculation": self.comparison_calculation,
            "include_matching_day_count": self.include_matching_day_count,
            "unsupported_requirements": [
                {"operation": item.operation, "evidence": item.evidence}
                for item in self.unsupported_requirements],
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
        if definition.aggregation == "sum_per_participant":
            return "number"
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


def normalize_unspecified_controls(intent: ReportIntent) -> ReportIntent:
    """Drop placeholder values that a model attached to controls it marked unspecified.

    Small models often fill ``comparison`` with an empty placeholder (``kind=all``
    or a month without year) while setting ``comparison_specified=false``. The
    flag is authoritative: the value is cleared, unless a change/decrease
    calculation shows the comparison was meant, which sets the flag instead.
    Malformed flag types are left for ``check_intent`` to reject.
    """
    changes: dict[str, Any] = {}
    if intent.comparison_specified is False and intent.comparison is not None:
        if intent.comparison_calculation in ("change", "decrease"):
            changes["comparison_specified"] = True
        else:
            changes["comparison"] = None
    if intent.ordering_specified is False and intent.order_by is not None:
        changes.update(order_by=None, descending=None)
    return replace(intent, **changes) if changes else intent


def check_intent(intent: ReportIntent, catalog: ReportingCatalog, *, today: date | None = None) -> None:
    reason, field = "intent_constraints", "intent"
    try:
        if not isinstance(intent, ReportIntent):
            raise ValueError
        checks = (
            ("turn_kind", intent.turn_kind in ("new", "refine", "answer")),
            ("unsupported_reason", isinstance(intent.unsupported_reason, str) and len(intent.unsupported_reason) <= 2000),
            ("chart", intent.chart in (None, "table", "bar", "line", "kpi")),
            ("time_grain", intent.time_grain in (None, "none", "day", "week", "month", "quarter", "year", "jalali_month")),
            ("comparison_calculation", intent.comparison_calculation in (None, "none", "change", "decrease")),
            ("include_matching_day_count", intent.include_matching_day_count is None or type(intent.include_matching_day_count) is bool),
            ("period", intent.period is None or isinstance(intent.period, PeriodSelection)),
            ("comparison", intent.comparison is None or isinstance(intent.comparison, PeriodSelection)),
            ("comparison_specified", type(intent.comparison_specified) is bool and (intent.comparison_specified or intent.comparison is None)),
            ("ordering_specified", type(intent.ordering_specified) is bool),
            ("order_by", intent.order_by is None or (intent.ordering_specified and isinstance(intent.order_by, str))),
            ("descending", intent.descending is None or type(intent.descending) is bool),
            ("limit", intent.limit is None or (type(intent.limit) is int and 1 <= intent.limit <= 10_000)),
            ("missing", isinstance(intent.missing, tuple) and len(intent.missing) <= len(MISSING_DETAILS)
             and all(isinstance(item, str) and item in MISSING_DETAILS for item in intent.missing)
             and len(set(intent.missing)) == len(intent.missing)),
        )
        for field, valid in checks:
            if not valid:
                raise ValueError
        if (not isinstance(intent.unsupported_requirements, tuple)
                or len(intent.unsupported_requirements) > 8
                or any(not isinstance(item, UnsupportedRequirement)
                       or item.operation not in OPERATION_LABELS
                       or not isinstance(item.evidence, str) or not 1 <= len(item.evidence.strip()) <= 500
                       for item in intent.unsupported_requirements)):
            raise SDKError("invalid_interpretation", "Report requirements are invalid.",
                           stage="intent", reason="requirements")
        reason = "concept_reference"
        for refs, attribute in ((intent.metrics, "metrics"), (intent.dimensions, "dimensions")):
            field = attribute
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
        if not (intent.metrics or intent.dimensions or intent.missing or intent.unsupported_reason.strip()
                or intent.unsupported_requirements):
            raise ValueError
        reason, field = "conditions", "conditions"
        _check_conditions(intent, catalog)
        reason = "intent_constraints"
        ordering = {item.concept_id for item in (*intent.metrics, *intent.dimensions)}
        if intent.time_grain not in (None, "none"):
            ordering.add("time_bucket")
        if intent.comparison is not None:
            ordering.add("period_label")
        if intent.comparison_calculation == "decrease":
            ordering.add("absolute_decrease")
        if intent.include_matching_day_count:
            ordering.add("matching_day_count")
        field = "order_by"
        if intent.order_by is not None and intent.order_by not in ordering:
            raise ValueError
        if today is not None:
            reason = "period_selection"
            from sageql.sdk.semantics import resolve_period
            for selection in (intent.period, intent.comparison):
                if selection is not None:
                    field = "period" if selection is intent.period else "comparison"
                    resolved = resolve_period(selection, today)
                    if selection is intent.comparison and resolved.start is None:
                        raise ValueError
    except (ValueError, TypeError, AttributeError, SDKError) as error:
        if isinstance(error, SDKError) and error.stage == "intent":
            raise
        raise SDKError("invalid_interpretation", "Report intent is invalid.",
                       stage="intent", reason=reason, field=field) from None


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


def canonical_intent(intent: ReportIntent, catalog: ReportingCatalog, *,
                     messages: tuple[Message, ...] | None = None,
                     current_spec: ReportSpec | None = None) -> ReportIntent:
    """A display label already groups by its registered target identity.

    Selecting both the identity and its registered display label repeats the
    same target grouping column. Bars remove the redundant plain dimension.
    Tables do so with user-message evidence unless IDs are explicitly requested,
    preserved from the current report, or used for ordering. Distinct columns and
    multiple label mappings remain subject to normal validation.
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
    table = messages is not None and intent.chart in {None, "table"}
    if intent.chart != "bar" and not table:
        return intent
    definitions = {}
    for ref in intent.dimensions:
        dataset = next(item for item in catalog.datasets if item.id == ref.dataset_id)
        definitions[ref] = next(item for item in dataset.dimensions if item.id == ref.concept_id)
    labels = {(ref.dataset_id, item.column) for ref, item in definitions.items()
              if isinstance(item, EntityLabelDimension)}
    if not labels:
        return intent
    if table:
        users = [item.content for item in messages if item.role == "user"]
        evidence = users if intent.turn_kind == "answer" else users[-1:]
        text = " ".join(evidence).casefold().replace("\u200c", " ")
        explicit = bool(re.search(r"(?<!\w)(?:شناسه|کد|ids?|identifiers?|codes?)(?!\w)", text))
        removed = bool(re.search(r"بدون.{0,12}(?:شناسه|کد)|(?:شناسه|کد).{0,18}(?:حذف|نشان نده|نمایش نده)|"
                                r"حذف.{0,12}(?:شناسه|کد)|(?:without|remove|no).{0,15}(?:ids?|identifiers?)\b", text))
        preserve = set(current_spec.dimension_ids) if (
            current_spec is not None and intent.turn_kind in {"refine", "answer"}) else set()
        def keep_dimension(ref, item):
            if (isinstance(item, EntityLabelDimension) or (ref.dataset_id, item.column) not in labels
                    or ref.concept_id == intent.order_by):
                return True
            label = r"(?<!\w)" + re.escape(item.label.casefold().replace("\u200c", " ")) + r"(?!\w)"
            label_removed = re.search(r"(?:without|remove|no|بدون|حذف).{0,15}" + label + "|" + label
                                      + r".{0,18}(?:حذف|نشان نده|نمایش نده)", text)
            return not (removed or label_removed) and (
                explicit or ref.concept_id in preserve or re.search(label, text) is not None)

        dimensions = tuple(ref for ref, item in definitions.items() if keep_dimension(ref, item))
        return replace(intent, dimensions=dimensions)
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
            or set(spec.dimension_ids) != {item.concept_id for item in intent.dimensions}):
        return "intent_validation: report_mismatch"
    if intent.chart is not None and intent.chart != spec.chart:
        return "intent_validation: chart_mismatch"
    if intent.time_grain is not None and intent.time_grain != spec.time_grain:
        return "intent_validation: time_grain_mismatch"
    if intent.comparison_calculation is not None and intent.comparison_calculation != spec.comparison_calculation:
        return "intent_validation: comparison_calculation_mismatch"
    if intent.include_matching_day_count is not None and intent.include_matching_day_count != spec.include_matching_day_count:
        return "intent_validation: matching_day_count_mismatch"
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
        "comparison_calculation": intent.comparison_calculation,
        "include_matching_day_count": intent.include_matching_day_count,
    }, sort_keys=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()
