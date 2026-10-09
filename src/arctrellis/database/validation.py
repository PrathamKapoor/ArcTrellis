"""Source-free validation of retained canonical owners, calls and import witnesses."""

from arctrellis.calls.models import CallSite
from arctrellis.core import CodeEntity, EntityKind
from arctrellis.extraction.models import _entity_span

from .models import DatabaseOperationKind as Kind
from .models import DatabaseOperationObservation, make_database_operation_observation
from .prisma import PRISMA_METHODS
from .sqlalchemy import SQLALCHEMY_METHODS, STATEMENTS


def _ancestors(owner: CodeEntity, entities: dict[str, CodeEntity]) -> set[str]:
    ancestors = set()
    while owner.id not in ancestors:
        ancestors.add(owner.id)
        if owner.parent_id is None:
            break
        owner = entities[owner.parent_id]
    return ancestors


def validate_database_observation(
    operation: DatabaseOperationObservation,
    entities: dict[str, CodeEntity],
    sites: dict[tuple[str, int, int], CallSite],
    blocked: frozenset[str],
) -> None:
    """Validate structural proof; this cannot reconstruct syntax or certify runtime identity."""
    owner = entities.get(operation.owner_entity_id)
    if owner is None or operation.provider in blocked:
        raise ValueError("database operation requires an unblocked canonical owner/provider")
    recreated = make_database_operation_observation(
        owner=owner,
        language=operation.language,
        operation_kind=operation.operation_kind,
        provider=operation.provider,
        operation_name=operation.operation_name,
        span=operation.span,
        target_name=operation.target_name,
        metadata=operation.metadata,
    )
    if recreated != operation or operation.owner_kind is not owner.kind:
        raise ValueError("database owner coordinates/identity disagree")
    site = sites.get((owner.id, operation.span.start_byte, operation.span.end_byte))
    if site is None or site.span != operation.span or site.location != operation.location:
        raise ValueError("database observation requires its exact canonical invocation")
    metadata = dict(operation.metadata)
    if metadata.get("binding_name") != site.callee_parts[0]:
        raise ValueError("database binding name must match its actual invocation receiver")
    ancestry = _ancestors(owner, entities)
    binding_owner = entities.get(metadata.get("binding_owner_id", ""))
    witness = entities.get(metadata.get("constructor_import_id", ""))
    if binding_owner is None or binding_owner.id not in ancestry or binding_owner.kind is EntityKind.CLASS:
        raise ValueError("database constructor binding must be in an execution ancestor")
    if (
        witness is None
        or witness.kind is not EntityKind.IMPORT
        or witness.parent_id not in _ancestors(binding_owner, entities)
    ):
        raise ValueError("database constructor requires an ancestor import witness")
    w = dict(witness.metadata)
    try:
        start, end = int(metadata["binding_start_byte"]), int(metadata["binding_end_byte"])
    except (KeyError, ValueError) as error:
        raise ValueError("database binding coordinates are required") from error
    span = _entity_span(binding_owner)
    if (
        not span.start_byte <= start < end <= span.end_byte
        or end > operation.span.start_byte
        or _entity_span(witness).end_byte > start
    ):
        raise ValueError("database binding must precede the invocation inside its owner")
    if witness.location is None or witness.location.file_path != operation.path or witness.language != owner.language:
        raise ValueError("database witness must describe the same file/language")
    expected: tuple[Kind | None, str] | None
    if operation.provider == "sqlalchemy":
        expected_import = ("sqlalchemy.orm", "Session", "from")
        if (
            operation.language.value != "python"
            or len(site.callee_parts) != 2
            or site.callee_parts[-1] != operation.operation_name
        ):
            raise ValueError("SQLAlchemy requires a direct session invocation")
        expected = SQLALCHEMY_METHODS.get(operation.operation_name)
        if expected is None:
            raise ValueError("unsupported SQLAlchemy method")
        method = "sqlalchemy_session_" + operation.operation_name
        if operation.operation_name == "execute":
            statement = metadata.get("statement_kind")
            expected = (
                (Kind.UNKNOWN, "unknown")
                if statement is None
                else (STATEMENTS.get(statement, Kind.UNKNOWN), "statement_execution")
            )
            method = "sqlalchemy_execute_" + (statement or "unknown")
            if statement is not None:
                try:
                    statement_start = int(metadata["statement_start_byte"])
                    statement_end = int(metadata["statement_end_byte"])
                except (KeyError, ValueError) as error:
                    raise ValueError("classified execute requires exact statement call coordinates") from error
                statement_site = sites.get((owner.id, statement_start, statement_end))
                statement_import = entities.get(metadata.get("statement_import_id", ""))
                sm = {} if statement_import is None else dict(statement_import.metadata)
                if (
                    statement_site is None
                    or statement_site.id != metadata.get("statement_call_id")
                    or statement_site.callee_parts != (sm.get("binding"),)
                    or not operation.span.start_byte < statement_start < statement_end < operation.span.end_byte
                ):
                    raise ValueError("statement invocation proof must lie inside its actual execute call")
                if (
                    statement not in STATEMENTS
                    or statement_import is None
                    or statement_import.kind is not EntityKind.IMPORT
                    or statement_import.parent_id not in ancestry
                    or (sm.get("module"), sm.get("imported_name"), sm.get("import_form"), sm.get("relative_level"))
                    != ("sqlalchemy", statement, "from", "0")
                    or _entity_span(statement_import).end_byte > operation.span.start_byte
                ):
                    raise ValueError("classified execute requires an actual statement import")
        if operation.target_name is not None and metadata.get("target_basis") != "source_identifier":
            raise ValueError("SQLAlchemy targets are source identifiers only")
    elif operation.provider == "prisma":
        expected_import = ("@prisma/client", "PrismaClient", "named")
        if (
            operation.language.value not in ("javascript", "typescript")
            or w.get("is_type_only") != "false"
            or w.get("module_literal") not in ('"@prisma/client"', "'@prisma/client'")
        ):
            raise ValueError("Prisma requires a value import in JavaScript/TypeScript")
        transaction = operation.operation_name == "$transaction"
        expected = (
            (Kind.TRANSACTION, "transaction_control")
            if transaction
            else (PRISMA_METHODS.get(operation.operation_name), "client_request")
        )
        method = "prisma_transaction" if transaction else "prisma_model_" + operation.operation_name.lower()
        if transaction:
            if (
                len(site.callee_parts) != 2
                or site.callee_parts[-1] != "$transaction"
                or operation.target_name is not None
            ):
                raise ValueError("Prisma transaction requires a direct client invocation")
        elif (
            len(site.callee_parts) != 3
            or site.callee_parts[1:] != (operation.target_name, operation.operation_name)
            or metadata.get("target_basis") != "prisma_model_accessor"
        ):
            raise ValueError("Prisma model operation requires its actual static accessor")
    else:
        raise ValueError("unsupported database provider")
    if (w.get("module"), w.get("imported_name"), w.get("import_form")) != expected_import or w.get(
        "relative_level", "0"
    ) != "0":
        raise ValueError("database constructor import provenance disagrees")
    if (operation.operation_kind, metadata.get("effect_stage")) != expected or metadata.get(
        "analysis_method"
    ) != method:
        raise ValueError("database operation category/effect/method disagrees with adapter contract")
