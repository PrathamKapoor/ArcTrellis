"""Static Prisma Client requests with direct import/constructor provenance."""

from arctrellis.extraction import ExtractionResult
from arctrellis.ingestion import Language
from arctrellis.parsing import ParsedSource

from .models import DatabaseOperationKind as Kind
from .models import DatabaseOperationObservation, make_database_operation_observation
from .syntax import SyntaxContext, provenance

PRISMA_METHODS = {
    **dict.fromkeys(
        (
            "findUnique",
            "findUniqueOrThrow",
            "findFirst",
            "findFirstOrThrow",
            "findMany",
            "count",
            "aggregate",
            "groupBy",
        ),
        Kind.READ,
    ),
    **dict.fromkeys(("create", "createMany", "update", "updateMany", "upsert"), Kind.WRITE),
    **dict.fromkeys(("delete", "deleteMany"), Kind.DELETE),
}


def extract_prisma_operations(
    parsed_source: ParsedSource,
    extraction_result: ExtractionResult,
    *,
    blocked_providers: frozenset[str] = frozenset(),
) -> tuple[DatabaseOperationObservation, ...]:
    """Recognize client requests, never promise execution or transaction outcome."""
    context = SyntaxContext(parsed_source, extraction_result)
    if parsed_source.language not in (Language.JAVASCRIPT, Language.TYPESCRIPT) or "prisma" in blocked_providers:
        return ()
    operations = []
    for site in context.sites:
        parts = site.callee_parts
        transaction = len(parts) == 2 and parts[1] == "$transaction"
        if not transaction and (len(parts) != 3 or parts[2] not in PRISMA_METHODS):
            continue
        binding = context.client(
            parts[0],
            site.owner_entity_id,
            site.span.start_byte,
            "@prisma/client",
            "PrismaClient",
            "named",
            "new_expression",
        )
        if binding is None:
            continue
        method = parts[-1]
        kind = Kind.TRANSACTION if transaction else PRISMA_METHODS[method]
        effect = "transaction_control" if transaction else "client_request"
        target = None if transaction else parts[1]
        metadata = provenance(binding) + (
            ("effect_stage", effect),
            ("analysis_method", "prisma_transaction" if transaction else "prisma_model_" + method.lower()),
        )
        if target is not None:
            metadata += (("target_basis", "prisma_model_accessor"),)
        operations.append(
            make_database_operation_observation(
                owner=context.entities[site.owner_entity_id],
                language=site.language,
                operation_kind=kind,
                provider="prisma",
                operation_name=method,
                span=site.span,
                target_name=target,
                metadata=metadata,
            )
        )
    return tuple(operations)
