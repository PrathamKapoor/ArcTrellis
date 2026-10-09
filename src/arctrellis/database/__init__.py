"""Common operation observations and bounded static ORM adapters."""

from .extraction import extract_database_operations
from .graph import DatabaseGraphResult, materialize_database_graph
from .models import (
    DatabaseAnalysisResult,
    DatabaseOperationKind,
    DatabaseOperationObservation,
    make_database_operation_observation,
)
from .prisma import extract_prisma_operations
from .sqlalchemy import extract_sqlalchemy_operations

__all__ = [
    "DatabaseAnalysisResult",
    "DatabaseOperationKind",
    "DatabaseOperationObservation",
    "make_database_operation_observation",
    "extract_sqlalchemy_operations",
    "extract_prisma_operations",
    "extract_database_operations",
    "DatabaseGraphResult",
    "materialize_database_graph",
]
