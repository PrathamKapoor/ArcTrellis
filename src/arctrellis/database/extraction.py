"""Language dispatch during the existing per-file parse lifetime."""

from arctrellis.extraction import ExtractionResult
from arctrellis.ingestion import Language, RepositoryInventory
from arctrellis.parsing import ParsedSource

from .models import DatabaseOperationObservation
from .prisma import extract_prisma_operations
from .sqlalchemy import extract_sqlalchemy_operations


def _blocked_providers(inventory: RepositoryInventory) -> frozenset[str]:
    """Reject conventional repository package collisions, including failed files."""
    blocked = set()
    for file in inventory.files:
        path = file.path.removeprefix("src/")
        if path in ("sqlalchemy.py", "sqlalchemy.pyi") or path.startswith("sqlalchemy/"):
            blocked.add("sqlalchemy")
        if path.startswith("@prisma/client/") or path in ("@prisma/client.js", "@prisma/client.ts"):
            blocked.add("prisma")
    return frozenset(blocked)


def extract_database_operations(
    parsed_source: ParsedSource,
    extraction_result: ExtractionResult,
    *,
    blocked_providers: frozenset[str] = frozenset(),
) -> tuple[DatabaseOperationObservation, ...]:
    """Extract supported source patterns; unsupported syntax is not a failure."""
    adapter = extract_sqlalchemy_operations if parsed_source.language is Language.PYTHON else extract_prisma_operations
    return adapter(parsed_source, extraction_result, blocked_providers=blocked_providers)
