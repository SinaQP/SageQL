"""Validate reporting vocabulary and resolve date boundaries without a model.

Reports select a registered fact and optionally registered dimensional imports.
Models cannot invent joins or expressions; access predicates remain separate
from the specification. A host supplies ``today`` in its business timezone.
"""

from __future__ import annotations

from dataclasses import replace
from datetime import date, timedelta
from calendar import monthrange
from decimal import Decimal, InvalidOperation
import math
import re

from sageql.schema import Column, Table
from sageql.sdk.names import normalize_name
from sageql.sdk.calendars import (jalali_month_bounds, jalali_to_gregorian,
                                  gregorian_to_jalali, jalali_buckets)
from sageql.sdk.models import (
    AccessScope, AggregateFilter, DatasetAccess, DatasetDefinition, DimensionDefinition,
    EntityLabelDimension, EntityLookupDefinition, FilterDefinition, FullNameFilterDefinition, LookupQualifier,
    RelatedAttributeDimension,
    MetricDefinition, PeriodSelection, ReportSpec,
    ReportingCatalog, ResolvedPeriod, RowPolicy, SDKError, TimeDefinition,
    UserFilter, ValidatedReport,
)


_AGGREGATIONS = {"sum", "count_rows", "count_distinct", "average", "minimum", "maximum", "sum_per_participant"}
_OPERATORS = {"eq", "neq", "gt", "gte", "lt", "lte", "in", "is_null", "is_not_null"}
_GRAINS = {"none", "day", "week", "month", "quarter", "year", "jalali_month"}
_FAMILIES = {
    "integer": {"int", "integer", "tinyint", "smallint", "bigint"},
    "decimal": {"decimal", "numeric", "money", "smallmoney"},
    "number": {"float", "real", "double", "double precision"},
    "text": {"varchar", "nvarchar", "char", "nchar", "text", "ntext", "string"},
    "boolean": {"bit", "bool", "boolean"},
    "date": {"date"},
    "datetime": {"datetime", "datetime2", "smalldatetime", "datetimeoffset"},
}
_RESERVED_IDS = {"time_bucket", "period_label", "__sageql_relation_guard", "matching_day_count"}


def _fail(code: str, message: str) -> None:
    raise SDKError(code, message)


def _text(value: object, code: str, message: str, *, maximum: int = 256) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum or "\x00" in value:
        _fail(code, message)


def _id(value: object, code: str) -> None:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_-]{0,63}", value):
        _fail(code, "Reporting IDs must be bounded simple identifiers.")


def _tuple(value: object, code: str, message: str, *, maximum: int = 512) -> None:
    if not isinstance(value, tuple) or len(value) > maximum:
        _fail(code, message)


def column_type(data_type: str) -> str:
    """Return a supported scalar family from an explicitly declared SQL type.

    SQL Server ``timestamp`` is rowversion, not a date, and is unsupported.
    Timestamp configuration requires a later timezone-aware adapter contract.
    """
    if not isinstance(data_type, str) or len(data_type) > 100:
        _fail("invalid_catalog", "A column has an unsupported declared type.")
    match = re.fullmatch(r"\s*([A-Za-z][A-Za-z0-9]*(?:\s+precision)?)\s*(?:\(\s*(max|\d+)(?:\s*,\s*(\d+))?\s*\))?\s*", data_type, re.IGNORECASE)
    if not match:
        _fail("invalid_catalog", "A column has an unsupported declared type.")
    name, precision, scale = match.groups()
    name = " ".join(name.casefold().split())
    precision = precision.casefold() if precision is not None else None
    family = next((family for family, names in _FAMILIES.items() if name in names), None)
    if family is None:
        _fail("invalid_catalog", "A column has an unsupported declared type.")
    if precision is not None:
        if name in {"decimal", "numeric"}:
            if precision == "max" or not 1 <= int(precision) <= 38 or (scale is not None and not 0 <= int(scale) <= int(precision)):
                _fail("invalid_catalog", "A numeric column has invalid precision.")
        elif name in {"varchar", "nvarchar", "char", "nchar"}:
            if scale is not None or (precision == "max" and name in {"char", "nchar"}) or (precision != "max" and not 1 <= int(precision) <= (4000 if name in {"nchar", "nvarchar"} else 8000)):
                _fail("invalid_catalog", "A text column has invalid length.")
        elif name == "float":
            if precision == "max" or scale is not None or not 1 <= int(precision) <= 53:
                _fail("invalid_catalog", "A floating point column has invalid precision.")
        elif name in {"datetime2", "datetimeoffset"}:
            if precision == "max" or scale is not None or not 0 <= int(precision) <= 7:
                _fail("invalid_catalog", "A timestamp column has invalid precision.")
        else:
            _fail("invalid_catalog", "A column has unsupported type parameters.")
    return family


def _columns(dataset: DatasetDefinition) -> dict[str, Column]:
    return {column.name: column for column in dataset.columns}


def _validate_dataset(dataset: DatasetDefinition) -> None:
    code = "invalid_catalog"
    if not isinstance(dataset, DatasetDefinition) or not isinstance(dataset.table, Table):
        _fail(code, "A registered dataset and table are required.")
    _id(dataset.id, code)
    _text(dataset.label, code, "Dataset labels must be bounded text.")
    _text(dataset.version, code, "A dataset version is required.", maximum=100)
    if not isinstance(dataset.description, str) or len(dataset.description) > 2000 or "\x00" in dataset.description:
        _fail(code, "A dataset description must be bounded business text.")
    _tuple(dataset.default_metric_ids, code, "Default metrics must be bounded.", maximum=16)
    _tuple(dataset.metrics, code, "Metrics must be bounded.", maximum=256)
    if any(not isinstance(metric, MetricDefinition) for metric in dataset.metrics):
        _fail(code, "A registered metric definition is required.")
    for metric in dataset.metrics:
        _id(metric.id, code)
    if (any(not isinstance(key, str) or key not in {m.id for m in dataset.metrics}
            for key in dataset.default_metric_ids)
            or len(set(dataset.default_metric_ids)) != len(dataset.default_metric_ids)):
        _fail(code, "Default metrics must be distinct registered measures.")
    _text(dataset.table.name, code, "A valid physical table name is required.", maximum=128)
    if not isinstance(dataset.table.schema, str) or len(dataset.table.schema) > 128 or "\x00" in dataset.table.schema or not isinstance(dataset.table.kind, str) or dataset.table.kind not in {"TABLE", "VIEW"}:
        _fail(code, "A dataset must register one table or view.")
    _tuple(dataset.columns, code, "Dataset columns must be a bounded tuple.")
    if not dataset.columns:
        _fail(code, "A dataset must declare its physical columns.")
    names = set()
    for column in dataset.columns:
        if not isinstance(column, Column) or not isinstance(column.table, str) or column.table.casefold() != dataset.table.key.casefold():
            _fail(code, "All columns must belong to the dataset's registered table.")
        _text(column.name, code, "A physical column name is invalid.", maximum=128)
        if column.name.casefold() in names or type(column.nullable) is not bool:
            _fail(code, "Dataset column declarations are inconsistent.")
        names.add(column.name.casefold())
        column_type(column.data_type)
    columns = _columns(dataset)
    _tuple(dataset.related_columns, code, "Related column declarations must be bounded.")
    if (len(set(dataset.related_columns)) != len(dataset.related_columns)
            or any(not isinstance(name, str) or name not in columns for name in dataset.related_columns)):
        _fail(code, "Related columns must reference distinct registered projections.")
    _tuple(dataset.row_key, code, "Dataset row keys must be a tuple.")
    if any(not isinstance(name, str) or name not in columns for name in dataset.row_key) or len(set(dataset.row_key)) != len(dataset.row_key):
        _fail(code, "Dataset row keys must reference registered columns.")
    if set(dataset.row_key).intersection(dataset.related_columns):
        _fail(code, "Fact row keys cannot contain related projections.")
    ids = set()
    for definitions, kind in ((dataset.metrics, MetricDefinition), (dataset.dimensions, DimensionDefinition), (dataset.filters, FilterDefinition)):
        _tuple(definitions, code, "Reporting definitions must be bounded tuples.", maximum=256)
        for definition in definitions:
            if not isinstance(definition, kind):
                _fail(code, "A reporting definition has an invalid type.")
            _id(definition.id, code)
            _text(definition.label, code, "Reporting labels must be bounded text.")
            if definition.id.casefold() in ids or definition.id.casefold() in _RESERVED_IDS:
                _fail(code, "Reporting IDs must be unique and cannot use reserved fields.")
            ids.add(definition.id.casefold())
            if kind is MetricDefinition and definition.aggregation == "count_rows":
                if definition.column is not None:
                    _fail(code, "A row count must not supply a source column.")
            elif not isinstance(definition.column, str) or definition.column not in columns:
                _fail(code, "Reporting definitions must reference registered physical columns.")
            if kind is MetricDefinition:
                if not isinstance(definition.description, str) or len(definition.description) > 1000 or "\x00" in definition.description:
                    _fail(code, "Metric descriptions must be bounded business text.")
                for terms in (definition.selection_terms, definition.ranking_terms):
                    _tuple(terms, code, "Measure terms must be bounded.", maximum=16)
                    for term in terms:
                        _text(term, code, "Measure terms must be bounded business phrases.", maximum=100)
                if definition.column in dataset.related_columns:
                    _fail(code, "Measures must retain the physical fact grain.")
                if not isinstance(definition.aggregation, str) or definition.aggregation not in _AGGREGATIONS or not isinstance(definition.unit, str) or len(definition.unit) > 100 or "\x00" in definition.unit:
                    _fail(code, "A metric has an unsupported aggregate or unit.")
                if definition.aggregation == "sum_per_participant":
                    if (not isinstance(definition.participant_column, str)
                            or definition.participant_column not in columns
                            or definition.participant_column in dataset.related_columns
                            or column_type(columns[definition.participant_column].data_type) not in {"integer", "text"}):
                        _fail(code, "Participant means require a physical integer or text identity column.")
                elif definition.participant_column is not None:
                    _fail(code, "Only participant means may declare a participant column.")
                if definition.column is not None:
                    family = column_type(columns[definition.column].data_type)
                    if definition.aggregation in {"sum", "average", "sum_per_participant"} and family not in {"integer", "decimal", "number"}:
                        _fail(code, "Numeric aggregates require numeric source columns.")
                    if definition.aggregation in {"minimum", "maximum"} and family == "boolean":
                        _fail(code, "Boolean minimum and maximum are unsupported.")
                    if family == "datetime":
                        _fail("unsupported", "Timestamp reporting requires explicit timezone support.")
            elif column_type(columns[definition.column].data_type) == "datetime":
                _fail("unsupported", "Timestamp reporting requires explicit timezone support.")
            if isinstance(definition, EntityLabelDimension):
                for identifier in (definition.source_dataset_id, definition.source_id_dimension_id,
                                   definition.source_id_filter_id):
                    _id(identifier, code)
                _tuple(definition.source_label_dimension_ids, code, "Entity label fields must be bounded.", maximum=4)
                if (not definition.source_label_dimension_ids
                        or any(not isinstance(item, str) for item in definition.source_label_dimension_ids)
                        or len(set(definition.source_label_dimension_ids)) != len(definition.source_label_dimension_ids)):
                    _fail(code, "Entity labels require one to four distinct source dimensions.")
            if isinstance(definition, RelatedAttributeDimension):
                _id(definition.source_dataset_id, code)
                _id(definition.source_dimension_id, code)
            if kind is FilterDefinition:
                _tuple(definition.operators, code, "Filter operators must be a tuple.", maximum=9)
                if not definition.operators or any(not isinstance(operator, str) or operator not in _OPERATORS for operator in definition.operators) or len(set(definition.operators)) != len(definition.operators):
                    _fail(code, "A filter has unsupported operators.")
                if isinstance(definition, FullNameFilterDefinition):
                    _tuple(definition.name_columns, code, "Name columns must be a bounded tuple.", maximum=4)
                    if (not 1 <= len(definition.name_columns) <= 4
                            or definition.operators != ("eq",)
                            or definition.column != definition.name_columns[0]
                            or any(not isinstance(name, str) or name not in columns
                                   or column_type(columns[name].data_type) != "text"
                                   for name in definition.name_columns)
                            or len(set(definition.name_columns)) != len(definition.name_columns)):
                        _fail(code, "Full-name filters require one to four distinct text columns and equality only.")
    if not dataset.metrics and not dataset.dimensions:
        _fail(code, "A dataset must register at least one metric or dimension.")
    if dataset.time is not None:
        time = dataset.time
        if not isinstance(time, TimeDefinition) or not isinstance(time.column, str) or time.column not in columns:
            _fail(code, "Time configuration must reference a registered column.")
        if time.column in dataset.related_columns:
            _fail(code, "Time configuration must retain the physical fact date.")
        if column_type(columns[time.column].data_type) != "date":
            _fail("unsupported", "Only date columns support SDK time operations.")
        if time.calendar != "gregorian" or type(time.week_start) is not int or time.week_start != 0:
            _fail("unsupported", "Only the Gregorian calendar with Monday weeks is supported.")
        _text(time.timezone, code, "A business timezone label is required.", maximum=100)


def validate_catalog(catalog: ReportingCatalog) -> None:
    """Fail before model requests when trusted configuration is inconsistent."""
    if not isinstance(catalog, ReportingCatalog):
        _fail("invalid_catalog", "A reporting catalog is required.")
    _text(catalog.version, "invalid_catalog", "A catalog version is required.", maximum=100)
    if not isinstance(catalog.preferred_calendar, str) or catalog.preferred_calendar not in {"gregorian", "jalali"}:
        _fail("invalid_catalog", "The preferred reporting calendar is unsupported.")
    _tuple(catalog.ambiguous_ranking_terms, "invalid_catalog", "Ranking terms must be bounded.", maximum=16)
    for term in catalog.ambiguous_ranking_terms:
        _text(term, "invalid_catalog", "Ranking terms must be bounded business phrases.", maximum=100)
    _tuple(catalog.datasets, "invalid_catalog", "Catalog datasets must be a bounded tuple.", maximum=100)
    if not catalog.datasets:
        _fail("invalid_catalog", "At least one dataset must be registered.")
    ids = set()
    for dataset in catalog.datasets:
        _validate_dataset(dataset)
        if dataset.id.casefold() in ids:
            _fail("invalid_catalog", "Dataset IDs must be unique.")
        ids.add(dataset.id.casefold())
    _validate_labels(catalog)
    _validate_lookups(catalog)
    from sageql.sdk.relationships import validate_relationships
    validate_relationships(catalog)


def _validate_labels(catalog: ReportingCatalog) -> None:
    datasets = {item.id: item for item in catalog.datasets}
    for target in catalog.datasets:
        for label in target.dimensions:
            if not isinstance(label, EntityLabelDimension):
                continue
            source = datasets.get(label.source_dataset_id)
            if source is None or source.id == target.id or source.time is not None:
                _fail("invalid_catalog", "Entity labels require a distinct timeless source.")
            dimensions = {item.id: item for item in source.dimensions}
            identity = dimensions.get(label.source_id_dimension_id)
            key_filter = next((item for item in source.filters if item.id == label.source_id_filter_id), None)
            if (identity is None or isinstance(identity, EntityLabelDimension)
                    or key_filter is None or isinstance(key_filter, FullNameFilterDefinition)
                    or key_filter.column != identity.column or "in" not in key_filter.operators):
                _fail("invalid_catalog", "Entity labels require a scalar identity dimension and matching IN filter.")
            family = column_type(_columns(target)[label.column].data_type)
            if family not in {"integer", "text"} or column_type(_columns(source)[identity.column].data_type) != family:
                _fail("invalid_catalog", "Entity label identities must use matching integer/text types.")
            for identifier in label.source_label_dimension_ids:
                dimension = dimensions.get(identifier)
                if (dimension is None or isinstance(dimension, EntityLabelDimension)
                        or column_type(_columns(source)[dimension.column].data_type) != "text"
                        or dimension.id == identity.id):
                    _fail("invalid_catalog", "Entity label parts must be registered scalar text dimensions.")


def _validate_lookups(catalog: ReportingCatalog) -> None:
    code = "invalid_catalog"
    _tuple(catalog.lookups, code, "Entity lookups must be a bounded tuple.", maximum=16)
    datasets = {item.id: item for item in catalog.datasets}
    used = {item.id: {definition.id.casefold() for definition in
                     (*item.metrics, *item.dimensions, *item.filters)} for item in catalog.datasets}
    for lookup in catalog.lookups:
        if not isinstance(lookup, EntityLookupDefinition):
            _fail(code, "A registered entity lookup is required.")
        for identifier in (lookup.id, lookup.dataset_id, lookup.target_filter_id,
                           lookup.source_dataset_id, lookup.source_id_dimension_id,
                           lookup.source_name_filter_id):
            _id(identifier, code)
        _text(lookup.label, code, "An entity lookup label is required.")
        target, source = datasets.get(lookup.dataset_id), datasets.get(lookup.source_dataset_id)
        if target is None or source is None or target.id == source.id:
            _fail(code, "An entity lookup must register distinct source and target datasets.")
        target_filter = next((item for item in target.filters if item.id == lookup.target_filter_id), None)
        source_id = next((item for item in source.dimensions if item.id == lookup.source_id_dimension_id), None)
        source_name = next((item for item in source.filters if item.id == lookup.source_name_filter_id), None)
        if (target_filter is None or isinstance(target_filter, FullNameFilterDefinition)
                or "eq" not in target_filter.operators or source_id is None
                or not isinstance(source_name, FullNameFilterDefinition)):
            _fail(code, "An entity lookup needs registered identity and full-name concepts.")
        family = column_type(_columns(target)[target_filter.column].data_type)
        if (family not in {"integer", "text"}
                or column_type(_columns(source)[source_id.column].data_type) != family):
            _fail(code, "Lookup identity and target filter must use the same integer/text type.")
        _tuple(lookup.qualifiers, code, "Lookup qualifiers must be a bounded tuple.", maximum=4)
        for definition in (lookup, *lookup.qualifiers):
            if definition is not lookup and not isinstance(definition, LookupQualifier):
                _fail(code, "A registered lookup qualifier is required.")
            _id(definition.id, code)
            _text(definition.label, code, "A lookup filter label is required.")
            if definition.id.casefold() in used[target.id] or definition.id.casefold() in _RESERVED_IDS:
                _fail(code, "Lookup filter IDs must be unique within the target dataset.")
            used[target.id].add(definition.id.casefold())
            if definition is not lookup:
                qualifier = next((item for item in source.filters if item.id == definition.source_filter_id), None)
                if (qualifier is None or isinstance(qualifier, FullNameFilterDefinition)
                        or "eq" not in qualifier.operators
                        or column_type(_columns(source)[qualifier.column].data_type) != "text"):
                    _fail(code, "Lookup qualifiers must reference registered text equality filters.")


def _selected_ids(selected: tuple[str, ...] | None, definitions: tuple, *, code: str) -> None:
    if selected is None:
        return
    _tuple(selected, code, "Permitted reporting IDs must be a tuple.", maximum=256)
    if any(not isinstance(item, str) for item in selected) or len(set(selected)) != len(selected) or any(item not in {definition.id for definition in definitions} for item in selected):
        _fail(code, "Access rules contain unknown or duplicate reporting IDs.")


def _iso_date(value: object, code: str) -> date:
    if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        _fail(code, "Date values must use YYYY-MM-DD.")
    try:
        return date.fromisoformat(value)
    except ValueError:
        _fail(code, "A date value is invalid.")


def _value(value: object, family: str, code: str) -> None:
    valid = False
    if family == "text":
        valid = isinstance(value, str) and len(value) <= 4000 and "\x00" not in value
    elif family == "boolean":
        valid = type(value) is bool
    elif family == "integer":
        valid = type(value) is int and -(2**63) <= value < 2**63
    elif family in {"decimal", "number"}:
        valid = type(value) in {int, float, Decimal} or (family == "decimal" and isinstance(value, str))
        if valid:
            try:
                rendered = str(value)
                valid = len(rendered) <= 100
                parsed = Decimal(rendered) if valid else Decimal("NaN")
                valid = valid and parsed.is_finite()
                if family == "number":
                    valid = valid and math.isfinite(float(value))
                elif valid:
                    # Bound the actual parameter, including zero exponents:
                    # short scientific notation can still expand enormously
                    # when an ODBC driver binds a DECIMAL value.
                    digits, exponent = parsed.as_tuple().digits, parsed.as_tuple().exponent
                    scale = max(-exponent, 0)
                    integer_digits = max(len(digits) + exponent, 0)
                    valid = -38 <= exponent <= 38 and len(digits) <= 38 and integer_digits + scale <= 38
            except (InvalidOperation, ValueError, OverflowError):
                valid = False
    elif family == "date":
        if type(value) is date:
            valid = True
        elif isinstance(value, str):
            _iso_date(value, code)
            valid = True
    if not valid:
        _fail(code, "A filter value does not match its registered scalar type.")


def _predicate(column: Column, operator: str, values: tuple, code: str) -> None:
    if not isinstance(operator, str) or operator not in _OPERATORS:
        _fail(code, "A filter operator is unsupported.")
    _tuple(values, code, "Filter values must be a bounded tuple.", maximum=100)
    expected = 0 if operator in {"is_null", "is_not_null"} else None if operator == "in" else 1
    if (expected is not None and len(values) != expected) or (operator == "in" and not values):
        _fail(code, "A filter has the wrong number of values.")
    family = column_type(column.data_type)
    if family == "datetime":
        _fail("unsupported", "Timestamp filters require explicit timezone support.")
    if family == "boolean" and operator in {"gt", "gte", "lt", "lte"}:
        _fail(code, "Ordering predicates on boolean values are unsupported.")
    for value in values:
        _value(value, family, code)


def _validate_access(dataset: DatasetDefinition, access: DatasetAccess) -> None:
    if not isinstance(access, DatasetAccess) or access.dataset_id != dataset.id:
        _fail("invalid_scope", "Access rules must identify a registered dataset.")
    for selected, definitions in ((access.metric_ids, dataset.metrics), (access.dimension_ids, dataset.dimensions), (access.filter_ids, dataset.filters)):
        _selected_ids(selected, definitions, code="invalid_scope")
    _tuple(access.policies, "invalid_scope", "Row policies must be a bounded tuple.", maximum=100)
    columns = _columns(dataset)
    for policy in access.policies:
        if not isinstance(policy, RowPolicy) or not isinstance(policy.column, str) or policy.column not in columns:
            _fail("invalid_scope", "Row policies must reference registered columns.")
        if policy.column in dataset.related_columns:
            _fail("invalid_scope", "Related source policies belong to the source dataset.")
        _predicate(columns[policy.column], policy.operator, policy.values, "invalid_scope")


def validate_scope(catalog: ReportingCatalog, scope: AccessScope) -> None:
    """Check trusted authorization before any metadata crosses the model boundary."""
    validate_catalog(catalog)
    if not isinstance(scope, AccessScope):
        _fail("invalid_scope", "A trusted access scope is required.")
    _text(scope.version, "invalid_scope", "An access policy version is required.", maximum=100)
    _tuple(scope.datasets, "invalid_scope", "Permitted datasets must be a bounded tuple.", maximum=100)
    datasets = {dataset.id: dataset for dataset in catalog.datasets}
    seen = set()
    for access in scope.datasets:
        if not isinstance(access, DatasetAccess) or not isinstance(access.dataset_id, str) or access.dataset_id not in datasets or access.dataset_id in seen:
            _fail("invalid_scope", "Access rules contain unknown or duplicate datasets.")
        seen.add(access.dataset_id)
        _validate_access(datasets[access.dataset_id], access)


def permitted_catalog(catalog: ReportingCatalog, scope: AccessScope) -> ReportingCatalog:
    """Expose only permitted reporting definitions, never compiler-only columns."""
    validate_scope(catalog, scope)
    datasets = {dataset.id: dataset for dataset in catalog.datasets}
    from sageql.sdk.relationships import relation_allowed
    accesses = {item.dataset_id: item for item in scope.datasets}
    related = {(relation.dataset_id, item.id): relation
               for relation in catalog.relationships for item in (*relation.dimensions, *relation.filters)}

    def related_allowed(dataset_id, identifier):
        relation = related.get((dataset_id, identifier))
        if relation is None:
            return True
        access = accesses.get(relation.source_dataset_id)
        return access is not None and relation_allowed(
            relation, datasets[relation.source_dataset_id], access, concept_id=identifier)
    permitted = []
    for access in scope.datasets:
        dataset = datasets[access.dataset_id]
        metrics = tuple(item for item in dataset.metrics if access.metric_ids is None or item.id in access.metric_ids)
        dimensions = tuple(item for item in dataset.dimensions
                           if (access.dimension_ids is None or item.id in access.dimension_ids)
                           and related_allowed(dataset.id, item.id))
        if not metrics and not dimensions:
            continue
        filters = tuple(item for item in dataset.filters
                        if (access.filter_ids is None or item.id in access.filter_ids)
                        and related_allowed(dataset.id, item.id))
        needed = {item.column for item in (*metrics, *dimensions, *filters) if item.column is not None}
        needed.update(item.participant_column for item in metrics if item.participant_column is not None)
        needed.update(name for item in filters if isinstance(item, FullNameFilterDefinition)
                      for name in item.name_columns)
        if dataset.time:
            needed.add(dataset.time.column)
        permitted.append(replace(dataset, metrics=metrics, dimensions=dimensions, filters=filters,
                                 default_metric_ids=tuple(key for key in dataset.default_metric_ids
                                                          if key in {m.id for m in metrics}),
                                 columns=tuple(column for column in dataset.columns if column.name in needed),
                                 row_key=(), related_columns=()))
    by_id = {item.id: item for item in permitted}
    # A display capability is visible only while every source dependency is
    # permitted. Ordinary access to the target identity does not grant names.
    def label_allowed(label: EntityLabelDimension) -> bool:
        source = by_id.get(label.source_dataset_id)
        return (source is not None
                and {label.source_id_dimension_id, *label.source_label_dimension_ids}
                <= {item.id for item in source.dimensions}
                and label.source_id_filter_id in {item.id for item in source.filters})

    permitted = [replace(item, dimensions=tuple(
        dimension for dimension in item.dimensions
        if not isinstance(dimension, EntityLabelDimension) or label_allowed(dimension)
    )) for item in permitted]
    permitted = [item for item in permitted if item.metrics or item.dimensions]
    by_id = {item.id: item for item in permitted}
    lookups = []
    for lookup in catalog.lookups:
        target, source = by_id.get(lookup.dataset_id), by_id.get(lookup.source_dataset_id)
        if (target is None or source is None
                or lookup.target_filter_id not in {item.id for item in target.filters}
                or lookup.source_id_dimension_id not in {item.id for item in source.dimensions}
                or lookup.source_name_filter_id not in {item.id for item in source.filters}):
            continue
        qualifiers = tuple(item for item in lookup.qualifiers
                           if item.source_filter_id in {definition.id for definition in source.filters})
        lookups.append(replace(lookup, qualifiers=qualifiers))
    return ReportingCatalog(tuple(permitted), catalog.version, tuple(lookups),
                            preferred_calendar=catalog.preferred_calendar,
                            ambiguous_ranking_terms=catalog.ambiguous_ranking_terms)


def _month(year: int, month: int) -> ResolvedPeriod:
    if type(year) is not int or type(month) is not int or not 1 <= year <= 9998 or not 1 <= month <= 12:
        _fail("invalid_spec", "A month selection needs a supported year and month.")
    start = date(year, month, 1)
    end = date(year + 1, 1, 1) if month == 12 else date(year, month + 1, 1)
    return ResolvedPeriod(start, end)


def resolve_period(period: PeriodSelection, today: date) -> ResolvedPeriod:
    """Resolve inclusive start/exclusive end boundaries from an injected date."""
    if not isinstance(period, PeriodSelection) or not isinstance(period.kind, str) or type(today) is not date:
        _fail("invalid_spec", "A period selection and business date are required.")
    supplied = {name for name in ("start", "end", "year", "month", "count", "unit") if getattr(period, name) is not None}
    required = {"range": {"start", "end"}, "jalali_range": {"start", "end"},
                "jalali_year": {"year"}, "month": {"year", "month"},
                "jalali_month": {"year", "month"}, "year": {"year"},
                "rolling": {"count", "unit"}, "jalali_rolling": {"count", "unit"}}.get(period.kind, set())
    if supplied != required:
        _fail("invalid_spec", "A period selection contains missing or contradictory fields.")
    if period.kind == "all":
        return ResolvedPeriod(None, None)
    if period.kind == "jalali_range":
        def persian_date(value):
            if not isinstance(value, str) or not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", value):
                raise ValueError
            return jalali_to_gregorian(*map(int, value.split("-")))
        try:
            start, last = persian_date(period.start), persian_date(period.end)
            if start > last:
                raise ValueError
            return ResolvedPeriod(start, last + timedelta(days=1))
        except ValueError:
            _fail("invalid_spec", "A Jalali range needs valid inclusive Persian start/end dates.")
    if period.kind == "jalali_year":
        try:
            start = jalali_month_bounds(period.year, 1)[0]
            end = jalali_month_bounds(period.year, 12)[1]
            return ResolvedPeriod(start, end)
        except ValueError:
            _fail("invalid_spec", "A Jalali year requires an integer year from 1300 through 1499.")
    if period.kind in {"this_jalali_month", "last_jalali_month", "this_jalali_year", "last_jalali_year", "jalali_rolling"}:
        try:
            year, month, day = gregorian_to_jalali(today)
            if period.kind.endswith("jalali_month"):
                if period.kind == "last_jalali_month":
                    year, month = (year - 1, 12) if month == 1 else (year, month - 1)
                return ResolvedPeriod(*jalali_month_bounds(year, month))
            if period.kind.endswith("jalali_year"):
                year -= period.kind == "last_jalali_year"
                return ResolvedPeriod(jalali_month_bounds(year, 1)[0], jalali_month_bounds(year, 12)[1])
            if (type(period.count) is not int or not 1 <= period.count <= 1200
                    or not isinstance(period.unit, str) or period.unit not in {"day", "week", "month", "quarter", "year"}):
                raise ValueError
            end = today + timedelta(days=1)
            if period.unit in {"day", "week"}:
                start = end - timedelta(days=period.count * (7 if period.unit == "week" else 1))
                gregorian_to_jalali(start)
            else:
                count = period.count * {"month": 1, "quarter": 3, "year": 12}[period.unit]
                shifted_year, shifted_month = divmod(year * 12 + month - 1 - count, 12)
                bounds = jalali_month_bounds(shifted_year, shifted_month + 1)
                start = bounds[0] + timedelta(days=min(day, (bounds[1] - bounds[0]).days) - 1)
            return ResolvedPeriod(start, end)
        except (ValueError, OverflowError):
            _fail("invalid_spec", "The relative Jalali period is outside supported date/count bounds.")
    if period.kind == "range":
        start, end = _iso_date(period.start, "invalid_spec"), _iso_date(period.end, "invalid_spec")
        if start >= end:
            _fail("invalid_spec", "The exclusive end date must follow the start date.")
        return ResolvedPeriod(start, end)
    if period.kind == "month":
        return _month(period.year, period.month)
    if period.kind == "jalali_month":
        try:
            start, end = jalali_month_bounds(period.year, period.month)
        except ValueError:
            _fail("invalid_spec", "A Jalali month requires year 1300 through 1499 and month 1 through 12.")
        return ResolvedPeriod(start, end)
    if period.kind == "year":
        if type(period.year) is not int or not 1 <= period.year <= 9998:
            _fail("invalid_spec", "A year selection needs a supported explicit year.")
        return ResolvedPeriod(date(period.year, 1, 1), date(period.year + 1, 1, 1))
    try:
        if period.kind == "rolling":
            if (type(period.count) is not int or not 1 <= period.count <= 1200
                    or not isinstance(period.unit, str) or period.unit not in {"day", "week", "month", "quarter", "year"}):
                _fail("invalid_spec", "A rolling period requires a bounded positive count and registered unit.")
            end = today + timedelta(days=1)
            if period.unit in {"day", "week"}:
                start = end - timedelta(days=period.count * (7 if period.unit == "week" else 1))
            else:
                months = period.count * {"month": 1, "quarter": 3, "year": 12}[period.unit]
                month_index = today.year * 12 + today.month - 1 - months
                year, zero_month = divmod(month_index, 12)
                month = zero_month + 1
                start = date(year, month, min(today.day, monthrange(year, month)[1]))
            return ResolvedPeriod(start, end)
        if period.kind in {"today", "yesterday"}:
            start = today - timedelta(days=period.kind == "yesterday")
            return ResolvedPeriod(start, start + timedelta(days=1))
        if period.kind in {"this_week", "last_week"}:
            start = today - timedelta(days=today.weekday() + (7 if period.kind == "last_week" else 0))
            return ResolvedPeriod(start, start + timedelta(days=7))
        if period.kind == "this_month":
            return _month(today.year, today.month)
        if period.kind == "last_month":
            return _month(today.year - (today.month == 1), 12 if today.month == 1 else today.month - 1)
        if period.kind in {"this_year", "last_year"}:
            year = today.year - (period.kind == "last_year")
            return resolve_period(PeriodSelection("year", year=year), today)
        if period.kind in {"this_quarter", "last_quarter"}:
            month = ((today.month - 1) // 3) * 3 + 1
            year = today.year
            if period.kind == "last_quarter":
                year, month = (year - 1, 10) if month == 1 else (year, month - 3)
            start = _month(year, month).start
            end = date(year + 1, 1, 1) if month == 10 else date(year, month + 3, 1)
            return ResolvedPeriod(start, end)
    except (ValueError, OverflowError):
        _fail("invalid_spec", "The relative period exceeds supported date boundaries.")
    _fail("unsupported", "The selected period kind is unsupported.")


def validate_report(dataset: DatasetDefinition, spec: ReportSpec, access: DatasetAccess, *, today: date) -> ValidatedReport:
    """Validate a model specification against vocabulary and trusted row policy."""
    _validate_dataset(dataset)
    _validate_access(dataset, access)
    if not isinstance(spec, ReportSpec) or spec.dataset_id != dataset.id:
        _fail("invalid_spec", "A report must identify its registered dataset.")
    for selected, definitions, allowed in ((spec.metric_ids, dataset.metrics, access.metric_ids), (spec.dimension_ids, dataset.dimensions, access.dimension_ids)):
        _tuple(selected, "invalid_spec", "Selected reporting IDs must be bounded tuples.", maximum=32)
        if any(not isinstance(item, str) for item in selected) or len(set(selected)) != len(selected) or any(item not in {definition.id for definition in definitions} for item in selected):
            _fail("invalid_spec", "The report selects unknown or duplicate reporting IDs.")
        if allowed is not None and any(item not in allowed for item in selected):
            _fail("access_denied", "A requested reporting field is unavailable.")
    if not spec.metric_ids and not spec.dimension_ids:
        _fail("invalid_spec", "A report needs at least one registered metric or dimension.")
    _tuple(spec.aggregate_filters, "invalid_spec", "Aggregate conditions must be bounded.", maximum=32)
    metrics = {item.id: item for item in dataset.metrics}
    seen_aggregates = set()
    for condition in spec.aggregate_filters:
        if (not isinstance(condition, AggregateFilter) or not isinstance(condition.metric_id, str)
                or condition.metric_id not in spec.metric_ids
                or not isinstance(condition.operator, str)):
            _fail("invalid_spec", "An aggregate condition must reference a selected metric.")
        key = (condition.metric_id, condition.operator)
        if key in seen_aggregates:
            _fail("invalid_spec", "Duplicate aggregate conditions are unsupported.")
        seen_aggregates.add(key)
        metric = metrics[condition.metric_id]
        family = "integer" if metric.aggregation in {"count_rows", "count_distinct"} else column_type(_columns(dataset)[metric.column].data_type)
        if metric.aggregation == "sum_per_participant":
            family = "number"
        if metric.aggregation in {"sum", "average"} and family == "integer":
            family = "decimal"
        output_type = {"integer": "bigint", "number": "float", "decimal": "decimal",
                       "text": "nvarchar", "date": "date", "boolean": "bit"}[family]
        _predicate(Column(dataset.table.key, "aggregate", output_type), condition.operator, condition.values, "invalid_spec")
    label_ids = {item.id for item in dataset.dimensions if isinstance(item, EntityLabelDimension)}
    if len(label_ids.intersection(spec.dimension_ids)) > 1:
        _fail("unsupported", "A report supports one registered entity-label dimension.")
    if isinstance(spec.order_by, str) and spec.order_by in label_ids:
        _fail("unsupported", "Sorting by resolved entity labels is unsupported; order by a metric instead.")
    _tuple(spec.filters, "invalid_spec", "User filters must be a bounded tuple.", maximum=32)
    definitions = {definition.id: definition for definition in dataset.filters}
    columns = _columns(dataset)
    seen = set()
    for condition in spec.filters:
        if not isinstance(condition, UserFilter) or not isinstance(condition.filter_id, str) or condition.filter_id not in definitions:
            _fail("invalid_spec", "A report filter is not registered.")
        if not isinstance(condition.operator, str):
            _fail("invalid_spec", "A report filter operator must be text.")
        key = (condition.filter_id, condition.operator)
        if key in seen:
            _fail("invalid_spec", "Duplicate report filter predicates are unsupported.")
        seen.add(key)
        if access.filter_ids is not None and condition.filter_id not in access.filter_ids:
            _fail("access_denied", "A requested report filter is unavailable.")
        definition = definitions[condition.filter_id]
        if condition.operator not in definition.operators:
            _fail("invalid_spec", "A report filter uses an unregistered operator.")
        _predicate(columns[definition.column], condition.operator, condition.values, "invalid_spec")
        if isinstance(definition, FullNameFilterDefinition):
            value = condition.values[0]
            if not isinstance(value, str) or len(value) > 256 or not normalize_name(value):
                _fail("invalid_spec", "A full-name selection requires a bounded nonempty name.")
    if not isinstance(spec.time_grain, str) or spec.time_grain not in _GRAINS or not isinstance(spec.chart, str) or spec.chart not in {"table", "line", "bar", "kpi"}:
        _fail("unsupported", "The requested time grain or presentation is unsupported.")
    if not spec.metric_ids and (spec.chart != "table" or spec.time_grain != "none" or spec.comparison is not None):
        _fail("unsupported", "Dimension listings require a table without time grouping or comparison.")
    if type(spec.limit) is not int or not 1 <= spec.limit <= 10000 or type(spec.descending) is not bool:
        _fail("invalid_spec", "A report requires a bounded row limit and explicit sort direction.")
    period = resolve_period(spec.period, today)
    comparison = resolve_period(spec.comparison, today) if spec.comparison is not None else None
    if (any(selection is not None and "jalali" in selection.kind
            for selection in (spec.period, spec.comparison))
            and spec.time_grain not in {"none", "day", "jalali_month"}):
        _fail("unsupported", "Use daily dates or explicit Jalali monthly grouping for Persian periods.")
    if spec.time_grain == "jalali_month":
        try:
            buckets = set(jalali_buckets(period.start, period.end))
            if comparison is not None:
                buckets.update(jalali_buckets(comparison.start, comparison.end))
            if len(buckets) > 120:
                raise ValueError
        except ValueError:
            _fail("unsupported", "Jalali monthly grouping needs bounded periods spanning at most 120 months.")
    if (period.start is not None or spec.time_grain != "none" or comparison is not None) and dataset.time is None:
        _fail("unsupported", "This dataset has no configured date field.")
    if comparison is not None and (period.start is None or comparison.start is None):
        _fail("invalid_spec", "Comparisons require two explicit bounded periods.")
    if type(spec.include_matching_day_count) is not bool:
        _fail("invalid_spec", "Matching-day count selection must be boolean.")
    if spec.include_matching_day_count:
        labels = [item for item in dataset.dimensions
                  if isinstance(item, EntityLabelDimension) and item.id in spec.dimension_ids]
        if (spec.time_grain != "day" or spec.chart != "table" or not spec.metric_ids
                or len(spec.dimension_ids) != 1 or len(labels) != 1
                or period.start is None or spec.comparison_calculation != "none"):
            _fail("unsupported", "Matching-day counts require bounded daily entity tables without fixed change calculations.")
    fields = {*spec.metric_ids, *spec.dimension_ids}
    if spec.time_grain != "none":
        fields.add("time_bucket")
    if comparison is not None:
        fields.add("period_label")
    if spec.comparison_calculation == "decrease":
        fields.add("absolute_decrease")
    if spec.include_matching_day_count:
        fields.add("matching_day_count")
    if spec.order_by is not None and (not isinstance(spec.order_by, str) or spec.order_by not in fields):
        _fail("invalid_spec", "Sorting must reference a selected report field.")
    if spec.chart != "table":
        if comparison is not None or len(spec.metric_ids) != 1:
            _fail("unsupported", "This presentation requires one metric without comparison.")
        if spec.chart == "kpi" and (spec.dimension_ids or spec.time_grain != "none"):
            _fail("unsupported", "A metric card requires a scalar aggregate.")
        if spec.chart == "line" and (spec.time_grain == "none" or spec.dimension_ids):
            _fail("unsupported", "A line chart requires a date series without additional dimensions.")
        if spec.chart == "bar" and len(spec.dimension_ids) + (spec.time_grain != "none") != 1:
            _fail("unsupported", "A bar chart requires one category or date grouping.")
    from sageql.sdk.comparisons import validate_comparison_calculation
    validate_comparison_calculation(spec, dataset)
    return ValidatedReport(dataset, spec, access, period, comparison, today)
