"""Embedded reporting SDK. Infrastructure is configured by the host application."""

from sageql.sdk.models import (
    AccessScope, ActorContext, AdapterResult, DatabaseAdapter, DatasetAccess, DatasetDefinition,
    DimensionDefinition, EntityLookupDefinition, ExecutionLimits, FilterDefinition,
    FullNameFilterDefinition, Interpretation, LookupQualifier,
    MetricDefinition, PeriodSelection, Reply, ReportArtifact, ReportField,
    ReportingCatalog, ReportPolicy, ReportProvider, ReportSpec, ResolvedPeriod, RowPolicy,
    SDKError, TimeDefinition, UserFilter, ValidatedReport,
)
from sageql.sdk.engine import SageQL
from sageql.sdk.adapters import SQLServerAdapter, SQLiteAdapter
from sageql.sdk.provider import OpenAIReportInterpreter
from sageql.sdk.agents import AgentReportInterpreter, AgentReview, OpenAIReportAgent, ReportAgentBackend
from sageql.sdk.sessions import InMemorySessionStore, SQLiteSessionStore, SessionStore

__all__ = [
    "AccessScope", "ActorContext", "AdapterResult", "DatabaseAdapter", "DatasetAccess", "DatasetDefinition",
    "DimensionDefinition", "EntityLookupDefinition", "ExecutionLimits", "FilterDefinition",
    "FullNameFilterDefinition", "Interpretation", "LookupQualifier",
    "MetricDefinition", "PeriodSelection", "Reply", "ReportArtifact", "ReportField",
    "ReportingCatalog", "ReportPolicy", "ReportProvider", "ReportSpec", "ResolvedPeriod", "RowPolicy",
    "SDKError", "TimeDefinition", "UserFilter", "ValidatedReport",
    "SageQL", "SQLServerAdapter", "SQLiteAdapter", "OpenAIReportInterpreter",
    "InMemorySessionStore", "SQLiteSessionStore", "SessionStore",
    "AgentReportInterpreter", "AgentReview", "OpenAIReportAgent", "ReportAgentBackend",
]
