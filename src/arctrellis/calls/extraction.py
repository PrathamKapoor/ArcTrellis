"""Body-aware, iterative extraction from normalized syntax and canonical scopes."""

from collections.abc import Callable

from arctrellis.core import EntityKind
from arctrellis.extraction import ExtractionResult
from arctrellis.extraction.models import _entity_span
from arctrellis.extraction.python import _recovery_subtrees
from arctrellis.extraction.source import _location, _PythonSource
from arctrellis.ingestion import Language
from arctrellis.parsing import ParsedSource, SyntaxNode

from .errors import CallExtractionError
from .ids import make_call_site_id
from .models import CalleeKind, CallSite, _site_order

_DECLARATIONS = {
    "function_definition",
    "class_definition",
    "function_declaration",
    "generator_function_declaration",
    "class_declaration",
    "abstract_class_declaration",
    "method_definition",
}
_CALLABLES = {"arrow_function", "function_expression", "generator_function"}
_FIELDS = {"field_definition", "public_field_definition"}
_OMITTED = _CALLABLES | {
    "lambda",
    "class",
    "decorator",
    "parameters",
    "formal_parameters",
    "interface_declaration",
    "type_alias_declaration",
    "enum_declaration",
    "ambient_declaration",
}


def _parts(node: SyntaxNode | None, text: Callable[[SyntaxNode], str]) -> tuple[str, ...]:
    parts = []
    while node is not None:
        if node.kind in ("identifier", "this"):
            parts.append(text(node))
            return tuple(reversed(parts)) if all(p.replace("$", "_").isidentifier() for p in parts) else ()
        if node.kind not in ("attribute", "member_expression") or node.child_by_field("optional_chain"):
            return ()
        member = node.child_by_field("attribute") or node.child_by_field("property")
        if member is None or member.kind not in ("identifier", "property_identifier"):
            return ()
        parts.append(text(member))
        node = node.child_by_field("object")
    return ()


def _optional_call(parsed: ParsedSource, node: SyntaxNode, function: SyntaxNode, arguments: SyntaxNode) -> bool:
    # Anonymous optional punctuation survives in bytes; comments/type arguments
    # have owned spans and must not be interpreted as invocation punctuation.
    cursor = function.span.end_byte
    fragments = []
    for child in node.children:
        if child.kind in ("comment", "type_arguments") and cursor <= child.span.start_byte < arguments.span.start_byte:
            fragments.append(parsed.source[cursor : child.span.start_byte])
            cursor = child.span.end_byte
    fragments.append(parsed.source[cursor : arguments.span.start_byte])
    return b"?." in b"".join(fragments)


def extract_call_sites(parsed_source: ParsedSource, extraction_result: ExtractionResult) -> tuple[CallSite, ...]:
    """Extract stable callee spellings, never declarations or resolved targets.

    Only represented function/method bodies and executable module statements are
    visited as execution scopes. Headers and class execution are omitted. Dynamic
    invocation callees are skipped; their ordinary argument expressions may survive.
    """
    if not isinstance(parsed_source, ParsedSource) or not isinstance(extraction_result, ExtractionResult):
        raise TypeError("call extraction requires ParsedSource and ExtractionResult")
    parsed, result = parsed_source, extraction_result
    if (parsed.path, parsed.language, parsed.root.span) != (result.path, result.language, _entity_span(result.module)):
        raise CallExtractionError("source and semantic result must describe the same file/root revision")
    ExtractionResult(result.path, result.language, result.entities, result.partial)
    if parsed.language is Language.PYTHON:
        text = _PythonSource.from_parsed(parsed).text
    else:
        parsed.source.decode("utf-8")

        def text(node: SyntaxNode) -> str:
            return parsed.bytes_for(node).decode("utf-8")

    scopes = {
        (e.parent_id, e.name, _entity_span(e).end_byte): e
        for e in result.entities
        if e.kind in (EntityKind.CLASS, EntityKind.FUNCTION, EntityKind.METHOD)
    }
    visited = set()
    unsafe = _recovery_subtrees(parsed.root)
    sites = []
    pending = [(parsed.root, result.module)]
    while pending:
        node, parent = pending.pop()
        if node.is_error or node.is_missing:
            continue
        if node.kind == "decorated_definition":
            definition = node.child_by_field("definition")
            if definition is not None and not unsafe[id(node)]:
                pending.append((definition, parent))
            continue
        declaration, name = node, node.child_by_field("name")
        is_binding = node.kind == "variable_declarator" or node.kind in _FIELDS
        if is_binding:
            value = node.child_by_field("value")
            name = name or node.child_by_field("property")
            if value is not None and value.kind in _CALLABLES | {"class"}:
                declaration = value
            else:
                # Class fields are definition-time execution, not method bodies.
                if node.kind not in _FIELDS and value is not None:
                    pending.append((value, parent))
                    if name is not None:
                        pending.append((name, parent))
                continue
        if node.kind in _DECLARATIONS or is_binding:
            if unsafe[id(node)]:
                continue
            scope = scopes.get((parent.id, text(name), node.span.end_byte)) if name is not None else None
            body = declaration.child_by_field("body")
            if scope is not None and body is not None:
                span = _entity_span(scope)
                if span.start_byte > node.span.start_byte:
                    raise CallExtractionError("semantic scope does not cover its declaration")
                visited.add(scope.id)
                pending.append((body, scope))
            elif is_binding and node.kind not in _FIELDS and name is not None:
                pending.append((name, parent))
            continue
        if node.kind in _OMITTED:
            continue
        if node.kind == "new_expression":
            arguments = node.child_by_field("arguments")
            if arguments is not None:
                pending.append((arguments, parent))
            continue
        if node.kind in ("call", "call_expression"):
            if parent.kind is EntityKind.CLASS:
                continue
            function, arguments = node.child_by_field("function"), node.child_by_field("arguments")
            parts = _parts(function, text)
            # Optional-call punctuation may be anonymous and absent from normalized children.
            optional = (
                function is not None and arguments is not None and _optional_call(parsed, node, function, arguments)
            )
            if parts and not unsafe[id(node)] and not optional:
                kind = CalleeKind.NAME if len(parts) == 1 else CalleeKind.MEMBER
                sites.append(
                    CallSite(
                        make_call_site_id(parsed.language, parsed.path, parent.id, kind, parts, node.span),
                        parsed.path,
                        parsed.language,
                        parent.id,
                        kind,
                        parts,
                        _location(parsed.path, node.span),
                        node.span,
                    )
                )
            if arguments is not None:
                pending.append((arguments, parent))
            continue
        pending.extend((c, parent) for c in reversed(node.children))
    if visited != {e.id for e in scopes.values()}:
        raise CallExtractionError("semantic scopes do not match normalized declarations")
    return tuple(sorted(sites, key=_site_order))
