"""Embedded reporting SDK. Infrastructure is configured by the host application."""

from sageql.sdk.models import (
    AccessScope, ActorContext, AdapterResult, DatabaseAdapter, DatasetAccess, DatasetDefinition,
    DimensionDefinition, EntityLabelDimension, EntityLookupDefinition, ExecutionLimits, FilterDefinition,
    FullNameFilterDefinition, Interpretation, LookupQualifier,
    MetricDefinition, PeriodSelection, Reply, ReportArtifact, ReportField,
    ReportingCatalog, ReportPolicy, ReportProvider, ReportSpec, ResolvedPeriod, RowPolicy,
    SDKError, TimeDefinition, UserFilter, ValidatedReport,
    AggregateFilter, RelatedDimension, RelatedFilter, RelationshipDefinition,
)
from sageql.sdk.engine import SageQL
from sageql.sdk.adapters import SQLServerAdapter, SQLiteAdapter
from sageql.sdk.provider import OpenAIReportInterpreter
from sageql.sdk.agents import AgentReportInterpreter, AgentReview, OpenAIReportAgent, ReportAgentBackend
from sageql.sdk.sessions import InMemorySessionStore, SQLiteSessionStore, SessionStore
from sageql.sdk.intent import ConceptRef, ReportIntent
from sageql.sdk.evidence import UnsupportedRequirement
from sageql.sdk.relationships import register_relationships

__all__ = [
    "AccessScope", "ActorContext", "AdapterResult", "DatabaseAdapter", "DatasetAccess", "DatasetDefinition",
    "DimensionDefinition", "EntityLabelDimension", "EntityLookupDefinition", "ExecutionLimits", "FilterDefinition",
    "FullNameFilterDefinition", "Interpretation", "LookupQualifier",
    "MetricDefinition", "PeriodSelection", "Reply", "ReportArtifact", "ReportField",
    "ReportingCatalog", "ReportPolicy", "ReportProvider", "ReportSpec", "ResolvedPeriod", "RowPolicy",
    "SDKError", "TimeDefinition", "UserFilter", "ValidatedReport",
    "SageQL", "SQLServerAdapter", "SQLiteAdapter", "OpenAIReportInterpreter",
    "InMemorySessionStore", "SQLiteSessionStore", "SessionStore",
    "AgentReportInterpreter", "AgentReview", "OpenAIReportAgent", "ReportAgentBackend",
    "ConceptRef", "ReportIntent", "UnsupportedRequirement",
    "RelatedDimension", "RelatedFilter", "RelationshipDefinition", "register_relationships",
    "AggregateFilter",
]
