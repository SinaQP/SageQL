"""SageQL: an embedded chat reporting SDK where models never write SQL.

Start with `sageql.SageQL` and the definitions in `sageql.sdk`. The staged 0.1
API lives in `sageql.legacy`; its names still resolve here with a
DeprecationWarning and will be removed from this module in 0.3.
"""

import warnings

from sageql.conversation import LLMConfig, Message
from sageql.schema import Column, Table
from sageql.sdk import SageQL

__all__ = ["Column", "LLMConfig", "Message", "SageQL", "Table"]

_LEGACY_NAMES = frozenset({
    "Candidate", "ChatConfig", "ChatError", "ChatProvider", "ContextProvider", "ContextResolution",
    "ContextResolutionSession", "CatalogSource", "catalog_from_dict", "DatabaseConfig", "Definition",
    "DiscoveryCandidates", "DiscoveryError", "DiscoveryProvider", "DiscoverySelection", "GeneratedQuery",
    "GenerationError", "InvalidSQL", "load_catalog_file", "ODBCCatalogSource", "PlanCandidates",
    "PlanProposal", "PlanQuality", "PlanningError", "PlanningProvider", "ProposedFilter", "ProposedJoin",
    "ProposedMeasure", "QueryPlan", "QueryExecutionError", "QueryResult", "QueryValidationError",
    "QuerySpace", "Relation", "ReportConversation", "ResolvedContext", "RequestAssessment",
    "RequestUnderstandingSession", "RequiredFilter", "SQLProvider", "SQLGenerationError", "SQLQuery",
    "PreparedQuery", "ValidationResult", "SchemaCatalog", "UnderstandingProvider", "generate_sql",
    "generate_sql_from_plan", "prepare_report_query", "validate_report_query", "execute_sqlite_report",
    "discover_query_space", "create_query_plan", "review_query_plan", "validate_sql", "TSQLQuery",
    "TSQLResult", "TSQLReportError", "render_tsql_report", "validate_tsql_report", "execute_tsql_report",
})


def __getattr__(name: str):
    if name in _LEGACY_NAMES:
        warnings.warn(
            f"sageql.{name} is part of the staged 0.1 API and moves out of the top-level package "
            f"in 0.3; import it from sageql.legacy instead",
            DeprecationWarning, stacklevel=2,
        )
        from sageql import legacy
        return getattr(legacy, name)
    raise AttributeError(f"module 'sageql' has no attribute {name!r}")
