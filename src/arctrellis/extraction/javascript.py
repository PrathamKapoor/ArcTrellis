"""Pure JS/TS semantic interpretation of owned normalized syntax."""

import re
from dataclasses import dataclass
from pathlib import PurePosixPath

from arctrellis.core import CodeEntity, SourceLocation
from arctrellis.core import EntityKind as K
from arctrellis.ingestion import Language
from arctrellis.parsing import ParsedSource, SyntaxNode, SyntaxSpan

from .errors import SemanticExtractionError, SourceDecodingError, UnsupportedExtractionLanguageError
from .es_imports import _es_imports, _require_import
from .ids import make_entity_id
from .models import ExtractionResult, _entity_order
from .source import _location, _span_metadata

_FUNCTIONS = {"function_declaration", "generator_function_declaration"}
_CALLABLES = {"arrow_function", "function_expression", "generator_function"}
_FIELDS = {"field_definition", "public_field_definition"}
_CLASSES = {"class_declaration", "abstract_class_declaration"}
_OMITTED_SCOPES = _CALLABLES | {
    "class",
    "method_definition",
    "interface_declaration",
    "type_alias_declaration",
    "enum_declaration",
    "ambient_declaration",
}


@dataclass(frozen=True, slots=True)
class _ScriptSource:
    parsed: ParsedSource

    def text(self, node: SyntaxNode) -> str:
        return self.parsed.bytes_for(node).decode("utf-8")

    def between(self, start: int, end: int) -> str:
        return self.parsed.source[start:end].decode("utf-8")

    def words_before(self, node: SyntaxNode, boundary: SyntaxNode) -> set[str]:
        decorators = tuple(
            c for c in node.children if c.kind == "decorator" and c.span.end_byte <= boundary.span.start_byte
        )
        start = decorators[-1].span.end_byte if decorators else node.span.start_byte
        prefix = self.between(start, boundary.span.start_byte)
        # Only modifier prefixes, not arbitrary expressions, are inspected here.
        prefix = re.sub(r"/\*.*?\*/|//[^\n\r]*", " ", prefix, flags=re.S)
        return set(re.findall(r"[A-Za-z_$][\w$]*|\*", prefix))


type _ScriptWork = tuple[SyntaxNode, CodeEntity, tuple[SyntaxNode, ...], tuple[tuple[str, str], ...], SyntaxSpan | None]


def _recovery(root: SyntaxNode) -> dict[int, bool]:
    state: dict[int, bool] = {}
    stack = [(root, False)]
    while stack:
        node, visited = stack.pop()
        if visited:
            state[id(node)] = node.is_error or node.is_missing or any(state[id(c)] for c in node.children)
        else:
            stack.append((node, True))
            stack.extend((c, False) for c in reversed(node.children))
    return state


def _cover(start: SyntaxSpan, end: SyntaxSpan) -> SyntaxSpan:
    return SyntaxSpan(
        start.start_byte, end.end_byte, start.start_line, start.start_column, end.end_line, end.end_column
    )


def _make(
    source: _ScriptSource,
    kind: K,
    name: str,
    parent: CodeEntity | None,
    span: SyntaxSpan,
    metadata: tuple[tuple[str, str], ...] = (),
    signature: str | None = None,
) -> CodeEntity:
    path, language = source.parsed.path, source.parsed.language
    qualified = path if parent is None else parent.qualified_name + ("::" if parent.kind is K.MODULE else ".") + name
    if kind is K.IMPORT:
        assert parent is not None
        qualified = parent.qualified_name + f"::import:{name}@{span.start_byte}"
    return CodeEntity(
        make_entity_id(
            language=language,
            path=path,
            kind=kind,
            qualified_name=qualified,
            start_byte=span.start_byte,
            end_byte=span.end_byte,
        ),
        kind,
        name,
        qualified,
        _location(path, span),
        parent.id if parent else None,
        language.value,
        _span_metadata(span) + metadata,
        signature,
    )


def _declaration(
    source: _ScriptSource,
    node: SyntaxNode,
    parent: CodeEntity,
    span: SyntaxSpan,
    decorators: tuple[SyntaxNode, ...],
    exports: tuple[tuple[str, str], ...],
    binding: SyntaxNode | None = None,
    form: str = "declaration",
    container: SyntaxNode | None = None,
) -> tuple[CodeEntity, SyntaxNode] | None:
    name = binding or node.child_by_field("name")
    body = node.child_by_field("body")
    is_class = node.kind in _CLASSES or node.kind == "class"
    if name is None or name.kind not in (
        "identifier",
        "type_identifier",
        "property_identifier",
        "private_property_identifier",
    ):
        return None
    if body is None or (is_class and body.kind != "class_body"):
        return None
    if not is_class and node.child_by_field("parameters") is None and node.child_by_field("parameter") is None:
        return None
    kind = K.CLASS if is_class else (K.METHOD if form in ("method", "callable_field") else K.FUNCTION)
    own_decorators = tuple(c for c in node.children if c.kind == "decorator")
    decorators = decorators + own_decorators
    header_start = (
        binding.span.start_byte
        if binding
        else (own_decorators[-1].span.end_byte if own_decorators else node.span.start_byte)
    )
    if form == "callable_field":
        assert container is not None
        container_decorators = tuple(c for c in container.children if c.kind == "decorator")
        header_start = container_decorators[-1].span.end_byte if container_decorators else container.span.start_byte
    header = source.between(header_start, body.span.start_byte).strip()
    if not header:
        return None
    metadata = tuple((f"decorator.{i}", source.text(c)) for i, c in enumerate(decorators)) + exports
    if not is_class:
        modifier_boundary = (
            node.child_by_field("name") or node.child_by_field("parameters") or node.child_by_field("parameter")
        )
        assert modifier_boundary is not None
        words = source.words_before(node, modifier_boundary)
        metadata += (
            ("declaration_form", form),
            ("is_async", str("async" in words).lower()),
            ("is_generator", str(node.kind.startswith("generator_") or "*" in words).lower()),
        )
        if kind is K.METHOD:
            member_words = source.words_before(container, name) if container is not None else words
            metadata += (
                ("is_static", str("static" in member_words).lower()),
                ("is_getter", str("get" in words).lower()),
                ("is_setter", str("set" in words).lower()),
                ("is_constructor", str(source.text(name) == "constructor" and form == "method").lower()),
            )
    return _make(source, kind, source.text(name), parent, span, metadata, header), body


def _extract(parsed: ParsedSource, language: Language) -> ExtractionResult:
    if not isinstance(parsed, ParsedSource):
        raise TypeError("parsed_source must be ParsedSource")
    if parsed.language is not language:
        raise UnsupportedExtractionLanguageError(f"extraction requires language {language.value}")
    if parsed.root.kind != "program":
        raise SemanticExtractionError("JS/TS source requires a normalized program root")
    try:
        SourceLocation(parsed.path, 1, 1)
    except ValueError as error:
        raise SemanticExtractionError("source path is not representable by canonical SourceLocation") from error
    try:
        parsed.source.decode("utf-8")
    except UnicodeError as error:
        raise SourceDecodingError(f"cannot decode UTF-8 source {parsed.path}") from error
    source = _ScriptSource(parsed)
    recovery = _recovery(parsed.root)
    class_members = {
        id(child)
        for node in parsed.root.walk()
        if node.kind == "class_body"
        for child in node.children
        if child.kind == "method_definition"
    }
    module = _make(source, K.MODULE, PurePosixPath(parsed.path).stem, None, parsed.root.span)
    entities = [module]
    partial = parsed.has_errors or recovery[id(parsed.root)]
    # Work item: node, semantic parent, decorators, export metadata, span override.
    stack: list[_ScriptWork] = [(c, module, (), (), None) for c in reversed(parsed.root.children)]
    candidates = (
        _FUNCTIONS
        | _CLASSES
        | _FIELDS
        | {"method_definition", "variable_declarator", "import_statement", "export_statement"}
    )
    while stack:
        node, parent, decorators, exports, override = stack.pop()
        if node.is_error or node.is_missing or (node.kind in candidates and recovery[id(node)]):
            partial = True
            continue
        if node.kind == "export_statement":
            exported_node = node.child_by_field("declaration")
            if exported_node is not None:
                annotations = tuple(c for c in node.children if c.kind == "decorator")
                words = source.words_before(node, exported_node)
                flags = (("is_exported", "true"), ("is_default_export", str("default" in words).lower()))
                stack.append((exported_node, parent, annotations, flags, node.span if annotations else None))
            continue
        if node.kind == "import_statement":
            bindings = _es_imports(source, node)
            if bindings is None:
                partial = True
            else:
                entities.extend(_make(source, K.IMPORT, b.name, parent, b.node.span, b.metadata) for b in bindings)
            continue
        if node.kind == "variable_declarator" or node.kind in _FIELDS:
            name = node.child_by_field("name") or node.child_by_field("property")
            value = node.child_by_field("value")
            if node.kind == "variable_declarator":
                imported = _require_import(source, node)
                if imported:
                    entities.append(_make(source, K.IMPORT, imported.name, parent, node.span, imported.metadata))
                    continue
            stable = name is not None and name.kind in (
                "identifier",
                "property_identifier",
                "private_property_identifier",
            )
            field = node.kind in _FIELDS
            if stable and value is not None and (value.kind in _CALLABLES or (not field and value.kind == "class")):
                form = "callable_field" if field else "callable_binding"
                annotations = decorators + tuple(c for c in node.children if c.kind == "decorator")
                declaration = _declaration(
                    source,
                    value,
                    parent,
                    override or node.span,
                    annotations,
                    exports,
                    name,
                    form,
                    container=node if field else None,
                )
                if declaration is None:
                    partial = True
                    continue
                entity, body = declaration
                entities.append(entity)
                stack.append((body, entity, (), (), None))
            # Never enter the unrepresented anonymous initializer scope.
            continue
        if node.kind in _FUNCTIONS | _CLASSES or (
            node.kind == "method_definition" and id(node) in class_members and parent.kind is K.CLASS
        ):
            form = "method" if node.kind == "method_definition" else "declaration"
            declaration = _declaration(source, node, parent, override or node.span, decorators, exports, form=form)
            if declaration is None:
                # Computed method names are deliberately omitted, not recovery.
                name = node.child_by_field("name")
                if name is None or name.kind != "computed_property_name":
                    partial = True
                continue
            entity, body = declaration
            entities.append(entity)
            stack.append((body, entity, (), (), None))
            continue
        if node.kind in _OMITTED_SCOPES:
            continue
        if node.kind == "class_body":
            pending_decorators = []
            work: list[_ScriptWork] = []
            for child in node.children:
                if child.kind == "decorator":
                    pending_decorators.append(child)
                elif child.kind != "comment":
                    annotations = tuple(pending_decorators)
                    span = _cover(annotations[0].span, child.span) if annotations else None
                    work.append((child, parent, annotations, (), span))
                    pending_decorators = []
            stack.extend(reversed(work))
        else:
            stack.extend((c, parent, (), exports, None) for c in reversed(node.children))
    return ExtractionResult(parsed.path, language, (module, *sorted(entities[1:], key=_entity_order)), partial)


def extract_javascript_entities(parsed_source: ParsedSource) -> ExtractionResult:
    """Extract single-file JavaScript/JSX declarations and static import sites."""
    return _extract(parsed_source, Language.JAVASCRIPT)


def extract_typescript_entities(parsed_source: ParsedSource) -> ExtractionResult:
    """Extract TS/TSX values; interfaces/type aliases/enums remain syntax-only."""
    return _extract(parsed_source, Language.TYPESCRIPT)
