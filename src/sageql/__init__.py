"""Public API for SageQL."""

from sageql.core import Candidate, GeneratedQuery, SQLProvider, generate_sql
from sageql.conversation import (
    ChatConfig,
    ChatError,
    ChatProvider,
    DatabaseConfig,
    LLMConfig,
    Message,
    ReportConversation,
)
from sageql.context import ContextProvider, ContextResolution, ContextResolutionSession, ResolvedContext
from sageql.catalog_input import catalog_from_dict, load_catalog_file
from sageql.discovery import (
    CatalogSource, DiscoveryCandidates, DiscoveryError, DiscoveryProvider,
    DiscoverySelection, QuerySpace, discover_query_space,
)
from sageql.odbc_catalog import ODBCCatalogSource
from sageql.planning import (
    PlanCandidates, PlanProposal, PlanQuality, PlanningError, PlanningProvider,
    ProposedFilter, ProposedJoin, ProposedMeasure, QueryPlan, create_query_plan,
    review_query_plan,
)
from sageql.schema import Column, Definition, Relation, SchemaCatalog, Table
from sageql.sql_generation import SQLGenerationError, SQLQuery, generate_sql_from_plan
from sageql.report_validation import (
    PreparedQuery, QueryValidationError, RequiredFilter, ValidationResult,
    prepare_report_query, validate_report_query,
)
from sageql.execution import QueryExecutionError, QueryResult, execute_sqlite_report
from sageql.errors import GenerationError, InvalidSQL
from sageql.validation import validate_sql
from sageql.understanding import RequestAssessment, RequestUnderstandingSession, UnderstandingProvider

__all__ = [
    "Candidate",
    "ChatConfig",
    "ChatError",
    "ChatProvider",
    "ContextProvider",
    "ContextResolution",
    "ContextResolutionSession",
    "CatalogSource",
    "catalog_from_dict",
    "Column",
    "DatabaseConfig",
    "Definition",
    "DiscoveryCandidates",
    "DiscoveryError",
    "DiscoveryProvider",
    "DiscoverySelection",
    "GeneratedQuery",
    "GenerationError",
    "InvalidSQL",
    "LLMConfig",
    "load_catalog_file",
    "Message",
    "ODBCCatalogSource",
    "PlanCandidates",
    "PlanProposal",
    "PlanQuality",
    "PlanningError",
    "PlanningProvider",
    "ProposedFilter",
    "ProposedJoin",
    "ProposedMeasure",
    "QueryPlan",
    "QueryExecutionError",
    "QueryResult",
    "QueryValidationError",
    "QuerySpace",
    "Relation",
    "ReportConversation",
    "ResolvedContext",
    "RequestAssessment",
    "RequestUnderstandingSession",
    "RequiredFilter",
    "SQLProvider",
    "SQLGenerationError",
    "SQLQuery",
    "PreparedQuery",
    "ValidationResult",
    "SchemaCatalog",
    "Table",
    "UnderstandingProvider",
    "generate_sql",
    "generate_sql_from_plan",
    "prepare_report_query",
    "validate_report_query",
    "execute_sqlite_report",
    "discover_query_space",
    "create_query_plan",
    "review_query_plan",
    "validate_sql",
]
