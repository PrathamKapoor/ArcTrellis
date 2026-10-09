"""Recognize a bounded static naming/callback subset within the parse lifetime."""

from dataclasses import replace

from arctrellis.calls.extraction import _extract_call_sites, _optional_call
from arctrellis.calls.ids import _identity
from arctrellis.core import CodeEntity, EntityKind
from arctrellis.extraction import ExtractionResult
from arctrellis.extraction.models import _entity_span
from arctrellis.extraction.python import _recovery_subtrees
from arctrellis.extraction.source import _location
from arctrellis.ingestion import Language
from arctrellis.parsing import ParsedSource, SyntaxNode, SyntaxSpan

from .models import TestObservation, _test_entity, _test_order


def _callback_shadows(parsed: ParsedSource, callback: SyntaxNode) -> set[str]:
    """Over-approximate local binding contradictions; never choose a target."""
    shadows: set[str] = set()
    for node in callback.walk():
        fields: tuple[SyntaxNode, ...] = ()
        if node.kind in ("formal_parameters", "required_parameter", "optional_parameter"):
            fields = (node,)
        elif node.kind in ("variable_declarator", "function_declaration", "class_declaration", "catch_clause"):
            bound = node.child_by_field("name") or node.child_by_field("parameter")
            fields = () if bound is None else (bound,)
        elif node.kind in ("assignment_expression", "augmented_assignment_expression", "update_expression"):
            bound = node.child_by_field("left") or node.child_by_field("argument")
            fields = () if bound is None else (bound,)
        for field in fields:
            shadows.update(parsed.bytes_for(n).decode("utf-8") for n in field.walk() if n.kind == "identifier")
    parameter = callback.child_by_field("parameter")
    if parameter is not None:
        shadows.update(parsed.bytes_for(n).decode("utf-8") for n in parameter.walk() if n.kind == "identifier")
    return shadows


def extract_test_observations(parsed: ParsedSource, result: ExtractionResult) -> tuple[TestObservation, ...]:
    if not isinstance(parsed, ParsedSource) or not isinstance(result, ExtractionResult):
        raise TypeError("test extraction requires parsed source and extraction result")
    if (parsed.path, parsed.language, parsed.root.span) != (result.path, result.language, _entity_span(result.module)):
        raise ValueError("test extraction requires the same source revision")
    observations = []

    def observe(name: str, parent: str, declaration: str | None, node_span: SyntaxSpan) -> TestObservation:
        identity = _identity(
            "arctrellis-test-v1",
            parsed.language.value,
            parsed.path,
            "declaration" if declaration else "callback",
            declaration,
            parent,
            node_span.start_byte,
            node_span.end_byte,
            name,
        )
        return TestObservation(
            identity,
            parsed.path,
            parsed.language,
            name,
            parent,
            declaration,
            _location(parsed.path, node_span),
            node_span,
        )

    if parsed.language is Language.PYTHON:
        entities = {e.id: e for e in result.entities}
        for entity in result.entities:
            parent = entities.get(entity.parent_id) if entity.parent_id is not None else None
            if (
                entity.kind in (EntityKind.FUNCTION, EntityKind.METHOD)
                and entity.name.startswith("test_")
                and parent is not None
                and (
                    parent.kind is EntityKind.MODULE
                    or (parent.kind is EntityKind.CLASS and parent.name.startswith("Test"))
                )
            ):
                observation = observe(entity.name, parent.id, entity.id, _entity_span(entity))
                observations.append(
                    replace(
                        observation, metadata=tuple((k, v) for k, v in entity.metadata if k.startswith("decorator_"))
                    )
                )
    else:
        unsafe = _recovery_subtrees(parsed.root)
        # Only direct expression statements at module/suite scope. No traversal
        # into production functions, arbitrary callbacks or control scopes.
        pending = [(parsed.root, set[str]())]
        roots: list[tuple[SyntaxNode, CodeEntity]] = []
        shadowed: dict[str, set[str]] = {}
        while pending:
            scope, suite_shadows = pending.pop()
            for statement in scope.children:
                if statement.kind != "expression_statement" or unsafe[id(statement)]:
                    continue
                call = next((c for c in statement.children if c.kind == "call_expression"), None)
                if call is None:
                    continue
                function, arguments = call.child_by_field("function"), call.child_by_field("arguments")
                if function is None or function.kind != "identifier" or arguments is None:
                    continue
                if _optional_call(parsed, call, function, arguments):
                    continue
                api = parsed.bytes_for(function).decode("utf-8")
                args = tuple(c for c in arguments.children if c.kind != "comment")
                if api not in ("test", "it", "describe") or len(args) != 2 or args[0].kind != "string":
                    continue
                literal = parsed.bytes_for(args[0]).decode("utf-8")
                if len(literal) < 3 or literal[0] not in "\"'" or literal[-1] != literal[0] or "\\" in literal:
                    continue
                name = literal[1:-1]
                if not name.strip() or name != name.strip():
                    continue
                callback = args[1]
                body = callback.child_by_field("body")
                if callback.kind not in ("arrow_function", "function_expression") or body is None:
                    continue
                if api == "describe":
                    if body.kind == "statement_block":
                        pending.append((body, suite_shadows | _callback_shadows(parsed, callback)))
                    continue
                observation = observe(name, result.module.id, None, call.span)
                owner = _test_entity(observation)
                roots.append((body, owner))
                shadowed[owner.id] = suite_shadows | _callback_shadows(parsed, callback)
                observations.append(observation)
        calls = _extract_call_sites(parsed, result, tuple(roots)) if roots else ()
        observations = [
            replace(
                o,
                callback_calls=tuple(
                    c for c in calls if c.owner_entity_id == o.id and c.callee_parts[0] not in shadowed[o.id]
                ),
            )
            for o in observations
        ]
    return tuple(sorted(observations, key=_test_order))
