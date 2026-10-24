"""Versioned contracts for the embedded reporting SDK.

Only the host application constructs infrastructure and access rules. Model
output is decoded into ReportSpec and validated before it can reach an adapter.
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields, is_dataclass
from datetime import date, datetime
from decimal import Decimal
import math
from threading import Event
from types import MappingProxyType
from typing import Any, Callable, Mapping, Protocol

from sageql.conversation import Message
from sageql.schema import Column, Table


Scalar = str | int | float | bool | Decimal | date | None


class SDKError(Exception):
    """A safe SDK error with a stable code, never raw driver/model details."""

    def __init__(self, code: str, message: str, *, retryable: bool = False,
                 stage: str = "", reason: str = "", field: str = "") -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable
        # Only bounded SDK vocabulary can become public diagnostic metadata.
        self.stage = stage if stage in {
            "intent", "planning", "review", "semantic_validation",
            "database_connection", "database_execution",
        } else ""
        self.reason = reason if reason in {
            "response_size", "json_syntax", "response_shape", "concept_reference",
            "period_selection", "conditions", "intent_constraints", "specification",
            "review_shape", "requirements", "request_evidence", "repeated_conflict",
            "revision_limit", "transport", "unavailable", "cleanup", "query_failed",
        } else ""
        self.field = field if field in {
            "intent", "turn_kind", "unsupported_reason", "chart", "time_grain", "metrics", "dimensions",
            "comparison_calculation", "include_matching_day_count", "period", "comparison",
            "comparison_specified", "filters", "aggregate_filters", "conditions", "order_by",
            "ordering_specified", "descending", "limit", "missing", "unsupported_requirements",
        } else ""


def json_value(value: Any) -> Any:
    """Serialize documented values losslessly; reject accidental object reprs."""
    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise SDKError("serialization_failed", "Report contains a non-finite number.")
        return value
    if isinstance(value, Decimal):
        if not value.is_finite():
            raise SDKError("serialization_failed", "Report contains a non-finite decimal.")
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: json_value(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        if any(not isinstance(key, str) for key in value):
            raise SDKError("serialization_failed", "Object keys must be text.")
        return {key: json_value(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [json_value(item) for item in value]
    raise SDKError("serialization_failed", "Report contains an unsupported value type.")


@dataclass(frozen=True)
class ActorContext:
    subject: str
    tenant_id: str = ""
    attributes: Mapping[str, str] = field(default_factory=dict, repr=False)

    def __post_init__(self) -> None:
        if not isinstance(self.subject, str) or not self.subject.strip():
            raise ValueError("actor subject is required")
        if not isinstance(self.tenant_id, str):
            raise ValueError("tenant_id must be text")
        if not isinstance(self.attributes, Mapping) or any(
            not isinstance(key, str) or not isinstance(value, str)
            for key, value in self.attributes.items()
        ):
            raise ValueError("actor attributes must map text to text")
        object.__setattr__(self, "attributes", MappingProxyType(dict(self.attributes)))


@dataclass(frozen=True)
class MetricDefinition:
    id: str
    label: str
    aggregation: str
    column: str | None = None
    unit: str = ""
    description: str = ""
    selection_terms: tuple[str, ...] = ()
    ranking_terms: tuple[str, ...] = ()
    participant_column: str | None = None


@dataclass(frozen=True)
class DimensionDefinition:
    id: str
    label: str
    column: str


@dataclass(frozen=True)
class EntityLabelDimension(DimensionDefinition):
    """Group by the local identity, then display a host-registered source label."""

    source_dataset_id: str
    source_id_dimension_id: str
    source_id_filter_id: str
    source_label_dimension_ids: tuple[str, ...]


@dataclass(frozen=True)
class RelatedAttributeDimension(DimensionDefinition):
    """Registered business equivalence, without granting an implicit relation."""

    source_dataset_id: str
    source_dimension_id: str


@dataclass(frozen=True)
class FilterDefinition:
    id: str
    label: str
    column: str
    operators: tuple[str, ...] = ("eq", "neq", "in", "is_null", "is_not_null")


@dataclass(frozen=True)
class FullNameFilterDefinition(FilterDefinition):
    """Exact normalized full-name equality over one to four declared text columns."""

    name_columns: tuple[str, ...] = ()


@dataclass(frozen=True)
class LookupQualifier:
    id: str
    label: str
    source_filter_id: str


@dataclass(frozen=True)
class EntityLookupDefinition:
    """Host-registered name-to-identity mapping; never model-selected joins."""

    id: str
    label: str
    dataset_id: str
    target_filter_id: str
    source_dataset_id: str
    source_id_dimension_id: str
    source_name_filter_id: str
    qualifiers: tuple[LookupQualifier, ...] = ()


@dataclass(frozen=True)
class TimeDefinition:
    column: str
    timezone: str = "UTC"
    calendar: str = "gregorian"
    week_start: int = 0


@dataclass(frozen=True)
class DatasetDefinition:
    id: str
    label: str
    table: Table
    columns: tuple[Column, ...]
    metrics: tuple[MetricDefinition, ...]
    dimensions: tuple[DimensionDefinition, ...] = ()
    filters: tuple[FilterDefinition, ...] = ()
    time: TimeDefinition | None = None
    version: str = "1"
    row_key: tuple[str, ...] = ()
    related_columns: tuple[str, ...] = ()
    description: str = ""
    default_metric_ids: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelatedDimension:
    """Import one permitted source dimension into a fact's business vocabulary."""

    id: str
    label: str
    source_dimension_id: str


@dataclass(frozen=True)
class RelatedFilter:
    id: str
    label: str
    source_filter_id: str


@dataclass(frozen=True)
class RelationshipDefinition:
    """Host-owned equality mapping; never decoded from model/browser output."""

    id: str
    dataset_id: str
    source_dataset_id: str
    key_pairs: tuple[tuple[str, str], ...]
    dimensions: tuple[RelatedDimension, ...] = ()
    filters: tuple[RelatedFilter, ...] = ()


@dataclass(frozen=True)
class ReportingCatalog:
    datasets: tuple[DatasetDefinition, ...]
    version: str = "1"
    lookups: tuple[EntityLookupDefinition, ...] = ()
    relationships: tuple[RelationshipDefinition, ...] = ()
    preferred_calendar: str = "gregorian"
    ambiguous_ranking_terms: tuple[str, ...] = ()


@dataclass(frozen=True)
class RowPolicy:
    column: str
    operator: str
    values: tuple[Scalar, ...] = ()


@dataclass(frozen=True)
class DatasetAccess:
    dataset_id: str
    metric_ids: tuple[str, ...] | None = None
    dimension_ids: tuple[str, ...] | None = None
    filter_ids: tuple[str, ...] | None = None
    policies: tuple[RowPolicy, ...] = ()


@dataclass(frozen=True)
class AccessScope:
    datasets: tuple[DatasetAccess, ...]
    version: str = "1"


@dataclass(frozen=True)
class PeriodSelection:
    kind: str
    start: str | None = None
    end: str | None = None
    year: int | None = None
    month: int | None = None
    count: int | None = None
    unit: str | None = None


@dataclass(frozen=True)
class ResolvedPeriod:
    start: date | None
    end: date | None


@dataclass(frozen=True)
class UserFilter:
    filter_id: str
    operator: str
    values: tuple[Scalar, ...] = ()


@dataclass(frozen=True)
class AggregateFilter:
    """Typed condition on a selected aggregate, evaluated after grouping."""

    metric_id: str
    operator: str
    values: tuple[Scalar, ...] = ()


@dataclass(frozen=True)
class ReportSpec:
    dataset_id: str
    metric_ids: tuple[str, ...]
    dimension_ids: tuple[str, ...] = ()
    filters: tuple[UserFilter, ...] = ()
    period: PeriodSelection = field(default_factory=lambda: PeriodSelection("all"))
    time_grain: str = "none"
    chart: str = "table"
    order_by: str | None = None
    descending: bool = False
    limit: int = 100
    comparison: PeriodSelection | None = None
    aggregate_filters: tuple[AggregateFilter, ...] = ()
    comparison_calculation: str = "none"
    include_matching_day_count: bool = False

    def to_dict(self) -> dict[str, Any]:
        return json_value(self)

    @classmethod
    def from_dict(cls, value: Any) -> ReportSpec:
        """Decode only the complete specified shape; never ignore extra keys."""
        def record(raw: Any, kind: type) -> dict[str, Any]:
            names = {item.name for item in fields(kind)}
            if kind is PeriodSelection and isinstance(raw, dict) and set(raw) == names - {"count", "unit"}:
                raw = {**raw, "count": None, "unit": None}
            if kind is ReportSpec and isinstance(raw, dict):
                # Only these additive fields may be absent in legacy receipts.
                optional = {"aggregate_filters": [], "comparison_calculation": "none",
                            "include_matching_day_count": False}
                if set(raw) <= names and names - set(raw) <= set(optional):
                    raw = {**{key: default for key, default in optional.items() if key not in raw}, **raw}
            if not isinstance(raw, dict) or set(raw) != names:
                raise SDKError("invalid_spec", "Report specification has invalid fields.")
            return dict(raw)

        data = record(value, cls)
        for name in ("metric_ids", "dimension_ids"):
            raw = data[name]
            if not isinstance(raw, list) or any(not isinstance(item, str) for item in raw):
                raise SDKError("invalid_spec", "Report IDs must be arrays of text.")
            data[name] = tuple(raw)
        if not isinstance(data["filters"], list):
            raise SDKError("invalid_spec", "Report filters must be an array.")
        filters_list = []
        for raw in data["filters"]:
            item = record(raw, UserFilter)
            if not isinstance(item["values"], list):
                raise SDKError("invalid_spec", "Filter values must be an array.")
            item["values"] = tuple(item["values"])
            filters_list.append(UserFilter(**item))
        data["filters"] = tuple(filters_list)
        if not isinstance(data["aggregate_filters"], list):
            raise SDKError("invalid_spec", "Aggregate filters must be an array.")
        aggregate_filters = []
        for raw in data["aggregate_filters"]:
            item = record(raw, AggregateFilter)
            if not isinstance(item["values"], list):
                raise SDKError("invalid_spec", "Aggregate filter values must be an array.")
            aggregate_filters.append(AggregateFilter(item["metric_id"], item["operator"], tuple(item["values"])))
        data["aggregate_filters"] = tuple(aggregate_filters)
        data["period"] = PeriodSelection(**record(data["period"], PeriodSelection))
        if data["comparison"] is not None:
            data["comparison"] = PeriodSelection(**record(data["comparison"], PeriodSelection))
        return cls(**data)


@dataclass(frozen=True)
class Interpretation:
    status: str
    spec: ReportSpec | None = None
    question: str = ""
    message: str = ""
    clarification_key: str = ""
    continues_clarification: bool = False


@dataclass(frozen=True)
class ValidatedReport:
    dataset: DatasetDefinition
    spec: ReportSpec
    access: DatasetAccess
    period: ResolvedPeriod
    comparison_period: ResolvedPeriod | None
    as_of: date
    related_sources: tuple[ValidatedRelation, ...] = ()


@dataclass(frozen=True)
class ValidatedRelation:
    definition: RelationshipDefinition
    source: DatasetDefinition
    access: DatasetAccess
    column_pairs: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ExecutionLimits:
    max_rows: int = 500
    query_timeout_seconds: float = 10.0
    request_timeout_seconds: float = 60.0
    max_message_chars: int = 8_000
    max_history_messages: int = 40

    def __post_init__(self) -> None:
        if type(self.max_rows) is not int or not 1 <= self.max_rows <= 10_000:
            raise ValueError("max_rows must be from 1 to 10000")
        for name in ("query_timeout_seconds", "request_timeout_seconds"):
            value = getattr(self, name)
            maximum = 300 if name == "query_timeout_seconds" else 900
            if type(value) not in (float, int) or not math.isfinite(value) or not 0 < value <= maximum:
                raise ValueError(f"{name} must be finite and from 0 to {maximum} seconds")
        if type(self.max_message_chars) is not int or not 1 <= self.max_message_chars <= 100_000:
            raise ValueError("max_message_chars must be a positive bounded integer")
        if type(self.max_history_messages) is not int or not 3 <= self.max_history_messages <= 40:
            raise ValueError("max_history_messages must be from 3 to 40 to retain clarification context")


@dataclass(frozen=True)
class ReportField:
    id: str
    label: str
    type: str
    unit: str = ""


@dataclass(frozen=True)
class AdapterResult:
    fields: tuple[ReportField, ...]
    rows: tuple[tuple[Scalar, ...], ...]
    truncated: bool


@dataclass(frozen=True)
class ReportArtifact:
    id: str
    session_id: str
    revision: int
    title: str
    fields: tuple[ReportField, ...]
    rows: tuple[tuple[Any, ...], ...]
    visualization: Mapping[str, Any]
    provenance: Mapping[str, Any]
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return json_value(self)


@dataclass(frozen=True)
class Reply:
    session_id: str
    revision: int
    status: str
    text: str
    clarification: str | None = None
    report: ReportArtifact | None = None
    error: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "contract_version": 1,
            "session_id": self.session_id,
            "revision": self.revision,
            "status": self.status,
            "assistant": {"text": self.text},
            "clarification": self.clarification,
            "report": self.report.to_dict() if self.report else None,
            "error": json_value(self.error),
        }


class ReportProvider(Protocol):
    def interpret(
        self, messages: tuple[Message, ...], current_spec: ReportSpec | None,
        catalog: ReportingCatalog, today: date,
    ) -> Interpretation:
        """Interpret against permitted metadata only; never receive result rows."""


class DatabaseAdapter(Protocol):
    def execute(
        self, report: ValidatedReport, limits: ExecutionLimits,
        *, cancel: Event | None = None,
    ) -> AdapterResult:
        """Revalidate and compile a trusted specification before bounded execution."""


ReportPolicy = Callable[[ActorContext], AccessScope]
