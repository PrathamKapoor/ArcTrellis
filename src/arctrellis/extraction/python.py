"""Pure normalized-Python-to-entity transformation; no resolution or I/O."""

from pathlib import PurePosixPath

from arctrellis.core import CodeEntity, EntityKind, SourceLocation
from arctrellis.ingestion import Language
from arctrellis.parsing import ParsedSource, SyntaxNode, SyntaxSpan
from .errors import SemanticExtractionError, UnsupportedExtractionLanguageError
from .ids import make_entity_id
from .imports import _import_bindings
from .models import ExtractionResult, _entity_order
from .source import _location, _PythonSource, _span_metadata


def _recovery_subtrees(root: SyntaxNode) -> dict[int, bool]:
    # Object identity indexes temporary traversal state, never canonical IDs.
    recovery: dict[int, bool] = {}
    pending = [(root, False)]
    while pending:
        node, visited = pending.pop()
        if visited:
            recovery[id(node)] = node.is_error or node.is_missing or any(recovery[id(c)] for c in node.children)
        else:
            pending.append((node, True))
            pending.extend((child, False) for child in reversed(node.children))
    return recovery


def _entity(source: _PythonSource, kind: EntityKind, name: str, qualified: str,
            span: SyntaxSpan, parent: CodeEntity | None,
            metadata: tuple[tuple[str, str], ...] = (), signature: str | None = None) -> CodeEntity:
    path = source.parsed.path
    return CodeEntity(id=make_entity_id(language=Language.PYTHON, path=path, kind=kind,
                      qualified_name=qualified, start_byte=span.start_byte, end_byte=span.end_byte),
                      kind=kind, name=name, qualified_name=qualified, location=_location(path, span),
                      parent_id=parent.id if parent else None, language="python",
                      metadata=_span_metadata(span) + metadata, signature=signature)


def _lexical_name(parent: CodeEntity, name: str) -> str:
    separator = "::" if parent.kind is EntityKind.MODULE else "."
    return parent.qualified_name + separator + name


def _declaration(source: _PythonSource, node: SyntaxNode, parent: CodeEntity,
                 span: SyntaxSpan, decorators: tuple[SyntaxNode, ...]) -> CodeEntity | None:
    name, body = node.child_by_field("name"), node.child_by_field("body")
    if name is None or name.kind != "identifier" or body is None or body.kind != "block" or not body.children:
        return None
    if node.kind == "function_definition" and node.child_by_field("parameters") is None:
        return None
    kind = EntityKind.CLASS if node.kind == "class_definition" else (
        EntityKind.METHOD if parent.kind is EntityKind.CLASS else EntityKind.FUNCTION)
    signature = source.signature(node, body)
    metadata = tuple((f"decorator.{index}", source.text(decorator)) for index, decorator in enumerate(decorators))
    if kind in (EntityKind.FUNCTION, EntityKind.METHOD):
        metadata += (("is_async", "true" if signature.split()[0] == "async" else "false"),)
    text = source.text(name)
    return _entity(source, kind, text, _lexical_name(parent, text), span, parent, metadata, signature)


def extract_python_entities(parsed_source: ParsedSource) -> ExtractionResult:
    """Extract lexical Python declarations/import bindings without executing code.

    Recovery anywhere inside a declaration suppresses it and its semantic subtree;
    unaffected siblings survive. IDs reproduce a revision, not arbitrary edits.
    The operation reads only immutable normalized syntax and already-owned bytes.
    """
    if not isinstance(parsed_source, ParsedSource):
        raise TypeError("parsed_source must be ParsedSource")
    if parsed_source.language is not Language.PYTHON:
        raise UnsupportedExtractionLanguageError("Python extraction requires language python")
    if parsed_source.root.kind != "module":
        raise SemanticExtractionError("Python source requires a normalized module root")
    try:
        SourceLocation(parsed_source.path, 1, 1)
    except ValueError as error:
        raise SemanticExtractionError("source path is not representable by canonical SourceLocation") from error
    source = _PythonSource.from_parsed(parsed_source)
    recovery = _recovery_subtrees(parsed_source.root)
    module = _entity(source, EntityKind.MODULE, PurePosixPath(parsed_source.path).stem,
                     parsed_source.path, parsed_source.root.span, None)
    entities = [module]
    partial = parsed_source.has_errors or recovery[id(parsed_source.root)]
    pending = [(child, module, None, ()) for child in reversed(parsed_source.root.children)]
    while pending:
        node, parent, override, decorators = pending.pop()
        if node.is_error or node.is_missing:
            partial = True
            continue
        if node.kind in ("decorated_definition", "class_definition", "function_definition",
                         "import_statement", "import_from_statement", "future_import_statement") and recovery[id(node)]:
            partial = True
            continue
        if node.kind == "decorated_definition":
            definition = node.child_by_field("definition")
            if definition is None or definition.kind not in ("class_definition", "function_definition"):
                partial = True
                continue
            annotations = tuple(child for child in node.children if child.kind == "decorator")
            pending.append((definition, parent, node.span, annotations))
        elif node.kind in ("class_definition", "function_definition"):
            declaration = _declaration(source, node, parent, override or node.span, decorators)
            if declaration is None:
                partial = True
                continue
            entities.append(declaration)
            body = node.child_by_field("body")
            pending.extend((child, declaration, None, ()) for child in reversed(body.children))
        elif node.kind in ("import_statement", "import_from_statement", "future_import_statement"):
            bindings = _import_bindings(source, node)
            if bindings is None:
                partial = True
                continue
            for binding in bindings:
                qualified = parent.qualified_name + f"::import:{binding.name}@{binding.node.span.start_byte}"
                entities.append(_entity(source, EntityKind.IMPORT, binding.name, qualified,
                                        binding.node.span, parent, binding.metadata))
        else:
            pending.extend((child, parent, None, ()) for child in reversed(node.children))
    ordered = (module, *sorted(entities[1:], key=_entity_order))
    return ExtractionResult(parsed_source.path, Language.PYTHON, ordered, partial)
