"""Bounded Session operations from explicit imports and direct assignments."""

from arctrellis.extraction import ExtractionResult
from arctrellis.ingestion import Language
from arctrellis.parsing import ParsedSource, SyntaxNode

from .models import DatabaseOperationKind as Kind
from .models import DatabaseOperationObservation, make_database_operation_observation
from .syntax import SyntaxContext, provenance

SQLALCHEMY_METHODS = {
    "get": (Kind.READ, "read_capable"),
    "add": (Kind.WRITE, "staged_mutation"),
    "add_all": (Kind.WRITE, "staged_mutation"),
    "delete": (Kind.DELETE, "staged_mutation"),
    "flush": (Kind.TRANSACTION, "transaction_control"),
    "commit": (Kind.TRANSACTION, "transaction_control"),
    "rollback": (Kind.TRANSACTION, "transaction_control"),
    "execute": (Kind.UNKNOWN, "unknown"),
}
STATEMENTS = {"select": Kind.READ, "insert": Kind.WRITE, "update": Kind.WRITE, "delete": Kind.DELETE}


def _arguments(node: SyntaxNode) -> tuple[SyntaxNode, ...]:
    arguments = node.child_by_field("arguments")
    return () if arguments is None else tuple(c for c in arguments.children if c.kind != "comment")


def extract_sqlalchemy_operations(
    parsed_source: ParsedSource,
    extraction_result: ExtractionResult,
    *,
    blocked_providers: frozenset[str] = frozenset(),
) -> tuple[DatabaseOperationObservation, ...]:
    """Observe intent/capability, never SQL execution or physical tables.

    Repository callers must block known internal sqlalchemy package collisions.
    Context managers, AsyncSession, factories, typed parameters and aliases are deferred.
    """
    context = SyntaxContext(parsed_source, extraction_result)
    if parsed_source.language is not Language.PYTHON or "sqlalchemy" in blocked_providers:
        return ()
    observations = []
    sites = {(s.owner_entity_id, s.span.start_byte, s.span.end_byte): s for s in context.sites}
    for site in context.sites:
        if len(site.callee_parts) != 2 or site.callee_parts[1] not in SQLALCHEMY_METHODS:
            continue
        receiver, method = site.callee_parts
        binding = context.client(
            receiver, site.owner_entity_id, site.span.start_byte, "sqlalchemy.orm", "Session", "from", "call"
        )
        if binding is None:
            continue
        node = context.calls[site.span.start_byte, site.span.end_byte]
        args = _arguments(node)
        kind, effect = SQLALCHEMY_METHODS[method]
        target = None
        metadata = provenance(binding)
        if method == "get" and args and args[0].kind == "identifier":
            target = context.text(args[0])
        if method == "execute" and args and args[0].kind == "call":
            statement = args[0]
            parts = context.parts(statement.child_by_field("function"))
            if len(parts) == 1:
                for symbol, category in STATEMENTS.items():
                    witness = context.imported(
                        parts[0], site.owner_entity_id, statement.span.start_byte, "sqlalchemy", symbol, "from"
                    )
                    if witness is not None:
                        statement_site = sites.get(
                            (site.owner_entity_id, statement.span.start_byte, statement.span.end_byte)
                        )
                        if statement_site is None:
                            continue
                        kind, effect = category, "statement_execution"
                        metadata += (
                            ("statement_kind", symbol),
                            ("statement_import_id", witness.id),
                            ("statement_call_id", statement_site.id),
                            ("statement_start_byte", str(statement.span.start_byte)),
                            ("statement_end_byte", str(statement.span.end_byte)),
                        )
                        statement_args = _arguments(statement)
                        if statement_args and statement_args[0].kind == "identifier":
                            target = context.text(statement_args[0])
                        break
        metadata += (
            ("effect_stage", effect),
            (
                "analysis_method",
                "sqlalchemy_execute_" + dict(metadata).get("statement_kind", "unknown")
                if method == "execute"
                else "sqlalchemy_session_" + method,
            ),
        )
        if target is not None:
            metadata += (("target_basis", "source_identifier"),)
        observations.append(
            make_database_operation_observation(
                owner=context.entities[site.owner_entity_id],
                language=site.language,
                operation_kind=kind,
                provider="sqlalchemy",
                operation_name=method,
                span=site.span,
                target_name=target,
                metadata=metadata,
            )
        )
    return tuple(observations)
