"""Host-registered dimensional relationships and local authorization binding."""

from dataclasses import replace

from sageql.schema import Column
from sageql.sdk.models import (
    AccessScope, DatasetDefinition, DimensionDefinition, EntityLabelDimension,
    FilterDefinition, FullNameFilterDefinition, RelatedDimension, RelatedFilter,
    RelatedAttributeDimension, RelationshipDefinition, ReportingCatalog, SDKError, ValidatedRelation,
)


def _column(relation: RelationshipDefinition, identifier: str) -> str:
    return f"__rel_{relation.id}_{identifier}"


def imports(relation: RelationshipDefinition, source: DatasetDefinition):
    dimensions = {item.id: item for item in source.dimensions}
    filters = {item.id: item for item in source.filters}
    return tuple((item.id, _column(relation, item.id), dimensions[item.source_dimension_id].column)
                 for item in relation.dimensions) + tuple(
        (item.id, _column(relation, item.id), filters[item.source_filter_id].column)
        for item in relation.filters)


def _check_definitions(catalog: ReportingCatalog) -> None:
    from sageql.sdk.semantics import _id, _text, _tuple, column_type

    code = "invalid_catalog"
    _tuple(catalog.relationships, code, "Relationships must be a bounded tuple.", maximum=32)
    datasets = {item.id: item for item in catalog.datasets}
    seen = set()
    used = {item.id: {field.id.casefold() for field in (*item.metrics, *item.dimensions, *item.filters)}
            for item in catalog.datasets}
    for relation in catalog.relationships:
        if not isinstance(relation, RelationshipDefinition):
            raise SDKError(code, "A registered relationship is required.")
        for identifier in (relation.id, relation.dataset_id, relation.source_dataset_id):
            _id(identifier, code)
        if relation.id.casefold() in seen:
            raise SDKError(code, "Relationship IDs must be unique.")
        seen.add(relation.id.casefold())
        target, source = datasets.get(relation.dataset_id), datasets.get(relation.source_dataset_id)
        if target is None or source is None or source.id == target.id:
            raise SDKError(code, "A relationship needs distinct registered datasets.")
        _tuple(relation.key_pairs, code, "Relationship keys must be bounded.", maximum=4)
        if not relation.key_pairs:
            raise SDKError(code, "A relationship requires equality keys.")
        target_columns = {item.name: item for item in target.columns}
        source_columns = {item.name: item for item in source.columns}
        local_keys, remote_keys = set(), set()
        source_key_columns = {item.column for item in source.dimensions
                              if type(item) is DimensionDefinition}
        for pair in relation.key_pairs:
            if (not isinstance(pair, tuple) or len(pair) != 2
                    or any(not isinstance(name, str) for name in pair)
                    or pair[0] not in target_columns or pair[1] not in source_columns
                    or pair[0] in target.related_columns or pair[1] in source.related_columns
                    or pair[1] not in source_key_columns
                    or pair[0] in local_keys or pair[1] in remote_keys):
                raise SDKError(code, "Relationship keys must reference distinct registered scalar columns.")
            family = column_type(target_columns[pair[0]].data_type)
            if family not in {"integer", "text"} or column_type(source_columns[pair[1]].data_type) != family:
                raise SDKError(code, "Relationship keys require matching integer/text types.")
            local_keys.add(pair[0])
            remote_keys.add(pair[1])
        _tuple(relation.dimensions, code, "Related dimensions must be bounded.", maximum=32)
        _tuple(relation.filters, code, "Related filters must be bounded.", maximum=32)
        if not relation.dimensions and not relation.filters:
            raise SDKError(code, "A relationship must expose business concepts.")
        for fields, kind, definitions, reference in (
            (relation.dimensions, RelatedDimension, source.dimensions, "source_dimension_id"),
            (relation.filters, RelatedFilter, source.filters, "source_filter_id"),
        ):
            for item in fields:
                if not isinstance(item, kind):
                    raise SDKError(code, "A relationship import is invalid.")
                _id(item.id, code)
                _id(getattr(item, reference), code)
                _text(item.label, code, "An imported concept label is required.")
                original = next((field for field in definitions if field.id == getattr(item, reference)), None)
                if (original is None or isinstance(original, (EntityLabelDimension, FullNameFilterDefinition))
                        or original.column in source.related_columns):
                    raise SDKError(code, "Relationship imports require ordinary physical source concepts.")
                if item.id.casefold() in used[target.id]:
                    raise SDKError(code, "Imported concept IDs must be unique within the fact dataset.")
                used[target.id].add(item.id.casefold())
                if len(_column(relation, item.id)) > 128:
                    raise SDKError(code, "An imported column identifier exceeds the bound.")


def register_relationships(catalog: ReportingCatalog,
                           relationships: tuple[RelationshipDefinition, ...]) -> ReportingCatalog:
    """Return a catalog with reusable related business concepts on fact datasets.

    Only host code calls this function. Existing registrations cannot be silently
    replaced. Source policies are bound per request, never captured here.
    """
    from sageql.sdk.semantics import validate_catalog

    validate_catalog(catalog)
    if not isinstance(relationships, tuple):
        raise SDKError("invalid_catalog", "Relationships must be registered as a bounded tuple.")
    combined = (*catalog.relationships, *relationships)
    # Reconstruct physical declarations before re-expanding all imports.
    base = _physical_catalog(catalog)
    base = replace(base, relationships=combined)
    _check_definitions(base)
    expanded = _expand(base)
    validate_catalog(expanded)
    return expanded


def _physical_catalog(catalog: ReportingCatalog) -> ReportingCatalog:
    return replace(catalog, datasets=tuple(replace(
        item,
        columns=tuple(column for column in item.columns if column.name not in item.related_columns),
        dimensions=tuple(field for field in item.dimensions if field.column not in item.related_columns),
        filters=tuple(field for field in item.filters if field.column not in item.related_columns),
        related_columns=(),
    ) for item in catalog.datasets))


def _expand(catalog: ReportingCatalog) -> ReportingCatalog:
    datasets = {item.id: item for item in catalog.datasets}
    expanded = []
    for target in catalog.datasets:
        columns, dimensions, filters, virtual = list(target.columns), list(target.dimensions), list(target.filters), []
        for relation in catalog.relationships:
            if relation.dataset_id != target.id:
                continue
            source = datasets[relation.source_dataset_id]
            source_columns = {item.name: item for item in source.columns}
            for _, name, remote in imports(relation, source):
                columns.append(Column(target.table.key, name, source_columns[remote].data_type, nullable=True))
                virtual.append(name)
            dimensions.extend(RelatedAttributeDimension(item.id, item.label, _column(relation, item.id),
                                                       source.id, item.source_dimension_id)
                              for item in relation.dimensions)
            source_filters = {item.id: item for item in source.filters}
            filters.extend(FilterDefinition(item.id, item.label, _column(relation, item.id),
                                            source_filters[item.source_filter_id].operators)
                           for item in relation.filters)
        expanded.append(replace(target, columns=tuple(columns), dimensions=tuple(dimensions),
                                filters=tuple(filters), related_columns=tuple(virtual)))
    return replace(catalog, datasets=tuple(expanded))


def validate_relationships(catalog: ReportingCatalog) -> None:
    base = _physical_catalog(catalog)
    _check_definitions(base)
    if not catalog.relationships and not any(item.related_columns for item in catalog.datasets):
        # The provider's projected catalog retains only business equivalences.
        # It carries no executable mappings or permissions.
        return
    if _expand(base).datasets != catalog.datasets:
        raise SDKError("invalid_catalog", "Related concepts differ from their host registrations.")


def relation_allowed(relation: RelationshipDefinition, source: DatasetDefinition, access,
                     *, concept_id: str) -> bool:
    permitted_dimensions = {item.id for item in source.dimensions
                            if access.dimension_ids is None or item.id in access.dimension_ids}
    # At least one permitted ordinary business dimension for each physical key.
    if any(not any(type(item) is DimensionDefinition and item.column == key
                   and item.id in permitted_dimensions for item in source.dimensions)
           for _, key in relation.key_pairs):
        return False
    dimension = next((item for item in relation.dimensions if item.id == concept_id), None)
    if dimension is not None:
        return dimension.source_dimension_id in permitted_dimensions
    condition = next((item for item in relation.filters if item.id == concept_id), None)
    return condition is not None and (access.filter_ids is None or condition.source_filter_id in access.filter_ids)


def bind_relationships(catalog: ReportingCatalog, prepared, scope: AccessScope):
    selected = {*prepared.spec.dimension_ids, *(item.filter_id for item in prepared.spec.filters)}
    datasets = {item.id: item for item in catalog.datasets}
    accesses = {item.dataset_id: item for item in scope.datasets}
    bound = []
    for relation in catalog.relationships:
        if relation.dataset_id != prepared.dataset.id:
            continue
        fields = imports(relation, datasets[relation.source_dataset_id])
        chosen = tuple((local, remote) for identifier, local, remote in fields if identifier in selected)
        if not chosen:
            continue
        source = datasets[relation.source_dataset_id]
        access = accesses.get(source.id)
        if access is None or any(not relation_allowed(relation, source, access, concept_id=identifier)
                                 for identifier, _, _ in fields if identifier in selected):
            raise SDKError("access_denied", "Related reporting concepts are unavailable under current access rules.")
        bound.append(ValidatedRelation(relation, source, access, chosen))
    return replace(prepared, related_sources=tuple(bound))


def validate_bound_relationships(report) -> None:
    """Adapter boundary: reject forged, missing or over-permitted bindings."""
    from sageql.sdk.semantics import _validate_dataset, _validate_access

    if not isinstance(report.related_sources, tuple) or len(report.related_sources) > 32:
        raise SDKError("invalid_spec", "Related sources must be bounded validated bindings.")
    selected = {*report.spec.dimension_ids, *(item.filter_id for item in report.spec.filters)}
    required = {item.column for item in (*report.dataset.dimensions, *report.dataset.filters)
                if item.id in selected and item.column in report.dataset.related_columns}
    provided = set()
    seen = set()
    for bound in report.related_sources:
        if not isinstance(bound, ValidatedRelation) or bound.definition.id in seen:
            raise SDKError("invalid_spec", "Related source binding is invalid.")
        seen.add(bound.definition.id)
        _validate_dataset(bound.source)
        _validate_access(bound.source, bound.access)
        physical = _physical_catalog(ReportingCatalog((report.dataset, bound.source)))
        registration = replace(physical, relationships=(bound.definition,))
        _check_definitions(registration)
        if (bound.definition.dataset_id != report.dataset.id
                or bound.definition.source_dataset_id != bound.source.id):
            raise SDKError("invalid_spec", "Related source binding identifies a different dataset.")
        declared = imports(bound.definition, bound.source)
        expected = tuple((local, remote) for identifier, local, remote in declared if identifier in selected)
        if not expected or expected != bound.column_pairs:
            raise SDKError("invalid_spec", "Related columns differ from their registered mapping.")
        for identifier, local, remote in declared:
            if local not in required:
                continue
            target_field = next((item for item in (*report.dataset.dimensions, *report.dataset.filters)
                                 if item.id == identifier), None)
            local_column = next((item for item in report.dataset.columns if item.name == local), None)
            source_column = next(item for item in bound.source.columns if item.name == remote)
            if (target_field is None or target_field.column != local or local_column is None
                    or local_column.data_type != source_column.data_type
                    or not relation_allowed(bound.definition, bound.source, bound.access, concept_id=identifier)):
                raise SDKError("access_denied", "Related columns are unavailable or inconsistent.")
        provided.update(local for local, _ in expected)
    if provided != required:
        raise SDKError("invalid_spec", "Report requires complete related source bindings.")
