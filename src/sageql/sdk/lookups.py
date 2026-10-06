"""Resolve host-registered entity names through separate policy-bound reads."""

from dataclasses import dataclass, replace
from datetime import date
from threading import Event
from typing import Callable

from sageql.sdk.models import (
    AccessScope, AdapterResult, DatabaseAdapter, EntityLookupDefinition, ExecutionLimits,
    ReportSpec, ReportingCatalog, SDKError, UserFilter, ValidatedReport,
)
from sageql.sdk.names import normalize_name
from sageql.sdk.semantics import column_type, permitted_catalog, validate_report


@dataclass(frozen=True)
class LookupRequest:
    definition: EntityLookupDefinition
    source: ValidatedReport


def prepare_request(
    catalog: ReportingCatalog, spec: ReportSpec, scope: AccessScope, today: date,
) -> tuple[ValidatedReport, LookupRequest | None]:
    """Validate the original specification without performing a lookup read.

    The placeholder is validation-only; it must never enter adapter execution.
    Its type allows the existing target-report validators to check every other
    operation before the lookup. Only resolve_request supplies an actual ID.
    """
    if not isinstance(spec, ReportSpec) or not isinstance(spec.filters, tuple) or len(spec.filters) > 32:
        raise SDKError("invalid_spec", "A bounded report specification is required.")
    visible = permitted_catalog(catalog, scope)
    dataset = next((item for item in catalog.datasets if item.id == spec.dataset_id), None)
    access = next((item for item in scope.datasets if item.dataset_id == spec.dataset_id), None)
    if dataset is None or access is None:
        raise SDKError("access_denied", "Report dataset is unavailable for this caller.")
    declared = tuple(item for item in catalog.lookups if item.dataset_id == spec.dataset_id)
    available = {item.id: item for item in visible.lookups if item.dataset_id == spec.dataset_id}
    lookup_ids = {item.id for item in declared}
    qualifier_ids = {item.id for lookup in declared for item in lookup.qualifiers}
    selected: dict[str, UserFilter] = {}
    normal = []
    for condition in spec.filters:
        if not isinstance(condition, UserFilter) or not isinstance(condition.filter_id, str):
            raise SDKError("invalid_spec", "A registered report filter is required.")
        if condition.filter_id not in lookup_ids | qualifier_ids:
            normal.append(condition)
            continue
        if (condition.filter_id in selected or condition.operator != "eq"
                or not isinstance(condition.values, tuple) or len(condition.values) != 1
                or not isinstance(condition.values[0], str) or not condition.values[0].strip()
                or len(condition.values[0]) > 256 or "\x00" in condition.values[0]):
            raise SDKError("invalid_spec", "Name and qualifier selections require bounded text equality.")
        selected[condition.filter_id] = condition
    named = [item for item in declared if item.id in selected]
    if not selected:
        return validate_report(dataset, spec, access, today=today), None
    if len(named) != 1:
        raise SDKError("invalid_spec", "Select one registered entity name with its optional qualifiers.")
    definition = available.get(named[0].id)
    if definition is None:
        raise SDKError("access_denied", "Entity lookup is unavailable under current access rules.")
    permitted_ids = {definition.id, *(item.id for item in definition.qualifiers)}
    if any(identifier not in permitted_ids for identifier in selected):
        raise SDKError("access_denied", "An entity qualifier is unavailable under current access rules.")
    if not normalize_name(selected[definition.id].values[0]):
        raise SDKError("invalid_spec", "A nonempty entity name is required.")
    if any(item.filter_id == definition.target_filter_id for item in normal):
        raise SDKError("invalid_spec", "Do not combine an entity name and a separate identity selection.")
    target_filter = next(item for item in dataset.filters if item.id == definition.target_filter_id)
    family = column_type(next(item for item in dataset.columns if item.name == target_filter.column).data_type)
    placeholder = UserFilter(definition.target_filter_id, "eq", (0 if family == "integer" else "",))
    prepared = validate_report(dataset, replace(spec, filters=(*normal, placeholder)), access, today=today)
    source = next(item for item in catalog.datasets if item.id == definition.source_dataset_id)
    source_access = next(item for item in scope.datasets if item.dataset_id == source.id)
    conditions = [UserFilter(definition.source_name_filter_id, "eq", selected[definition.id].values)]
    conditions += [UserFilter(item.source_filter_id, "eq", selected[item.id].values)
                   for item in definition.qualifiers if item.id in selected]
    source_spec = ReportSpec(source.id, (), dimension_ids=(definition.source_id_dimension_id,),
                             filters=tuple(conditions), limit=2)
    source_report = validate_report(source, source_spec, source_access, today=today)
    return prepared, LookupRequest(definition, source_report)


def resolve_request(
    prepared: ValidatedReport, lookup: LookupRequest, database: DatabaseAdapter,
    limits: ExecutionLimits, *, cancel: Event, check_access: Callable[[], None], language: str,
) -> tuple[ValidatedReport | None, str]:
    """Resolve a unique ID locally; never forward candidates to a provider."""
    check_access()
    result = database.execute(lookup.source, limits, cancel=cancel)
    check_access()
    if (not isinstance(result, AdapterResult) or type(result.truncated) is not bool
            or len(result.rows) > min(2, limits.max_rows)
            or tuple(item.id for item in result.fields) != (lookup.definition.source_id_dimension_id,)
            or any(len(row) != 1 for row in result.rows)):
        raise SDKError("lookup_failed", "Entity lookup returned an invalid result.")
    # The source DISTINCT query must complete; never choose the first candidate.
    if result.truncated or len(result.rows) > 1:
        qualifiers = lookup.definition.qualifiers
        detail = qualifiers[0].label if qualifiers else ("نام کامل‌تر" if language == "fa" else "a more specific full name")
        return None, (f"چند کارمند با این نام در اطلاعات مجاز پیدا شد. لطفاً {detail} را مشخص کنید."
                      if language == "fa" else
                      f"Multiple employees match this name. Please specify {detail}.")
    if not result.rows or result.rows[0][0] is None:
        return None, ("کارمندی با این نام در اطلاعات مجاز پیدا نشد. لطفاً نام و نام خانوادگی را کامل‌تر یا با املای دیگری بنویسید."
                      if language == "fa" else
                      "No reportable employee matches this name. Please check the full name or its spelling.")
    identity = result.rows[0][0]
    spec = prepared.spec
    concrete = replace(spec, filters=tuple(
        UserFilter(item.filter_id, "eq", (identity,)) if item.filter_id == lookup.definition.target_filter_id else item
        for item in spec.filters
    ))
    return validate_report(prepared.dataset, concrete, prepared.access, today=prepared.as_of), ""
