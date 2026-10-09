"""Policy-bound display labels, resolved locally after identity aggregation."""

from dataclasses import replace
from threading import Event
from typing import Callable

from sageql.sdk.models import (
    AccessScope, AdapterResult, DatabaseAdapter, EntityLabelDimension, ExecutionLimits,
    ReportArtifact, ReportSpec, ReportingCatalog, SDKError, UserFilter, ValidatedReport,
)
from sageql.sdk.semantics import _value, column_type, validate_report


def resolve_labels(
    catalog: ReportingCatalog, prepared: ValidatedReport, artifact: ReportArtifact,
    scope: AccessScope, database: DatabaseAdapter, limits: ExecutionLimits, *,
    cancel: Event, check_access: Callable[[], None], language: str,
) -> ReportArtifact:
    """Replace only display cells; never rerank, regroup or expose rows to a model."""
    selected = [item for item in prepared.dataset.dimensions
                if isinstance(item, EntityLabelDimension) and item.id in prepared.spec.dimension_ids]
    if not selected:
        return artifact
    definition = selected[0]  # validate_report permits at most one.
    index = next(i for i, field in enumerate(artifact.fields) if field.id == definition.id)
    source = next(item for item in catalog.datasets if item.id == definition.source_dataset_id)
    access = next(item for item in scope.datasets if item.dataset_id == source.id)
    family = column_type(next(item for item in prepared.dataset.columns
                              if item.name == definition.column).data_type)
    identities = {}
    for row in artifact.rows:
        if row[index] is not None:
            _value(row[index], family, "entity_label_failed")
            identities[row[index]] = None
    keys = tuple(identities)
    names: dict[object, str] = {}
    batch_size = min(100, limits.max_rows)
    fields = (definition.source_id_dimension_id, *definition.source_label_dimension_ids)
    for offset in range(0, len(keys), batch_size):
        batch = keys[offset:offset + batch_size]
        spec = ReportSpec(source.id, (), dimension_ids=fields, filters=(
            UserFilter(definition.source_id_filter_id, "in", batch),
        ), limit=limits.max_rows)
        report = validate_report(source, spec, access, today=prepared.as_of)
        check_access()
        result = database.execute(report, limits, cancel=cancel)
        check_access()
        if (not isinstance(result, AdapterResult) or type(result.truncated) is not bool
                or result.truncated or len(result.rows) > limits.max_rows
                or tuple(item.id for item in result.fields) != fields
                or any(len(row) != len(fields) for row in result.rows)):
            raise SDKError("entity_label_failed", "Entity labels returned an incomplete or invalid result.")
        for row in result.rows:
            identity, *parts = row
            _value(identity, family, "entity_label_failed")
            if identity not in batch or any(part is not None and (
                not isinstance(part, str) or len(part) > 4000 or "\x00" in part
            ) for part in parts):
                raise SDKError("entity_label_failed", "Entity labels returned an invalid value.")
            name = " ".join(part.strip() for part in parts if part is not None and part.strip())
            if not name:
                continue
            if len(name) > 4000:
                raise SDKError("entity_label_failed", "Entity label exceeds the text limit.")
            if identity in names and names[identity] != name:
                raise SDKError("entity_label_conflict", "Multiple display names match one report identity.")
            names[identity] = name
    unavailable = "نام در دسترس نیست" if language == "fa" else "Name unavailable"
    rows = tuple(tuple(names.get(value, unavailable) if i == index else value
                       for i, value in enumerate(row)) for row in artifact.rows)
    return replace(artifact, fields=tuple(
        replace(field, type="text") if i == index else field for i, field in enumerate(artifact.fields)
    ), rows=rows, provenance={**artifact.provenance, "entity_labels": {
        "dimension_id": definition.id, "source_dataset_id": source.id,
        "source_dataset_version": source.version,
        "unavailable_rows": sum(row[index] not in names for row in artifact.rows),
    }})
