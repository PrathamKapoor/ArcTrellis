"""Deterministic orchestration: structured intent, canonical selection, evidence.

The governing rule of this package is that a lexical score is not entity
identity. Retrieval finds candidate entities; selection decides which canonical
entity the caller meant; the existing structural-query engine executes; the
bundle reports exactly what repository evidence supports (D-142).

Nothing here interprets natural language, executes target code, mutates the
analyzed snapshot or adds a graph relationship.
"""

from __future__ import annotations

from .errors import (
    AnalysisPipelineError,
    InvalidQueryLimitError,
    InvalidQueryRequestError,
    OrchestrationError,
    OrchestrationInvariantError,
    UnsupportedIntentError,
)
from .evidence import build_bundle, entity_candidate, entity_summary, path_evidence
from .execution import ExecutionOutcome, execute_plan
from .models import (
    CALLABLE_KINDS,
    DATABASE_OPERATION_KINDS,
    ENDPOINT_SCOPES,
    SCHEMA_VERSION,
    BundleStatus,
    EntityCandidate,
    EntitySummary,
    EvidenceBundle,
    EvidenceDetail,
    IntentSpec,
    PathEvidence,
    PlanStep,
    QueryIntent,
    QueryPlan,
    QueryRequest,
    RelationshipEvidence,
    SelectionBasis,
    SelectionResult,
    SelectionStatus,
    SelectorForm,
    intent_spec,
)
from .pipeline import AnalysisCounts, AnalysisSnapshot, analyze_repository
from .planning import build_plan
from .runner import run_query
from .selection import SearchCandidates, search_candidates, select_canonical_entity


def plan_query(request: QueryRequest) -> QueryPlan:
    """Translate a validated request into its deterministic plan."""
    return build_plan(request)


__all__ = [
    "CALLABLE_KINDS",
    "DATABASE_OPERATION_KINDS",
    "ENDPOINT_SCOPES",
    "SCHEMA_VERSION",
    "AnalysisCounts",
    "AnalysisPipelineError",
    "AnalysisSnapshot",
    "BundleStatus",
    "EntityCandidate",
    "EntitySummary",
    "EvidenceBundle",
    "EvidenceDetail",
    "ExecutionOutcome",
    "IntentSpec",
    "InvalidQueryLimitError",
    "InvalidQueryRequestError",
    "OrchestrationError",
    "OrchestrationInvariantError",
    "PathEvidence",
    "PlanStep",
    "QueryIntent",
    "QueryPlan",
    "QueryRequest",
    "RelationshipEvidence",
    "SearchCandidates",
    "SelectionBasis",
    "SelectionResult",
    "SelectionStatus",
    "SelectorForm",
    "UnsupportedIntentError",
    "analyze_repository",
    "build_bundle",
    "build_plan",
    "entity_candidate",
    "entity_summary",
    "execute_plan",
    "intent_spec",
    "path_evidence",
    "plan_query",
    "run_query",
    "search_candidates",
    "select_canonical_entity",
]
