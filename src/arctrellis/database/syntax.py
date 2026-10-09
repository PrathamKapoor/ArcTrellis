"""Temporary normalized syntax indexes; nothing here escapes extraction."""

from collections.abc import Callable
from dataclasses import dataclass

from arctrellis.calls import extract_call_sites
from arctrellis.calls.extraction import _parts
from arctrellis.core import CodeEntity, EntityKind
from arctrellis.extraction import ExtractionResult
from arctrellis.extraction.models import _entity_span
from arctrellis.extraction.python import _recovery_subtrees
from arctrellis.extraction.source import _PythonSource
from arctrellis.frameworks.extraction import _writes
from arctrellis.ingestion import Language
from arctrellis.parsing import ParsedSource, SyntaxNode


@dataclass(frozen=True, slots=True)
class Binding:
    scope_id: str
    assignment: SyntaxNode
    constructor_import: CodeEntity


class SyntaxContext:
    """Reuse canonical call ownership, with conservative per-scope binding checks."""

    def __init__(self, parsed: ParsedSource, result: ExtractionResult) -> None:
        if not isinstance(parsed, ParsedSource) or not isinstance(result, ExtractionResult):
            raise TypeError("database extraction requires ParsedSource and ExtractionResult")
        if (parsed.path, parsed.language, parsed.root.span) != (
            result.path,
            result.language,
            _entity_span(result.module),
        ):
            raise ValueError("database syntax and entities must describe the same revision")
        ExtractionResult(result.path, result.language, result.entities, result.partial)
        self.parsed, self.result = parsed, result
        self.text: Callable[[SyntaxNode], str]
        if parsed.language is Language.PYTHON:
            self.text = _PythonSource.from_parsed(parsed).text
        else:
            self.text = lambda node: parsed.bytes_for(node).decode("utf-8")
        self.sites = extract_call_sites(parsed, result)
        self.entities = {e.id: e for e in result.entities}
        self.unsafe = _recovery_subtrees(parsed.root)
        nodes = tuple(parsed.root.walk())
        self.calls = {(n.span.start_byte, n.span.end_byte): n for n in nodes if n.kind in ("call", "call_expression")}
        scopes: dict[tuple[str, int], list[CodeEntity]] = {}
        for declaration_entity in result.entities:
            if declaration_entity.kind in (EntityKind.FUNCTION, EntityKind.METHOD):
                scopes.setdefault((declaration_entity.name, _entity_span(declaration_entity).end_byte), []).append(
                    declaration_entity
                )
        # Comprehensions introduce binding environments not represented by canonical owners.
        omitted = set()
        pending = [(parsed.root, False)]
        while pending:
            node, inside = pending.pop()
            inside = inside or node.kind in (
                "list_comprehension",
                "set_comprehension",
                "dictionary_comprehension",
                "generator_expression",
            )
            if inside:
                omitted.add((node.span.start_byte, node.span.end_byte))
            pending.extend((child, inside) for child in node.children)
        self.sites = tuple(s for s in self.sites if (s.span.start_byte, s.span.end_byte) not in omitted)
        self.roots = {result.module.id: parsed.root}
        parameters: dict[str, SyntaxNode] = {}
        for node in nodes:
            name = node.child_by_field("name") or node.child_by_field("property")
            value = node.child_by_field("value")
            declaration = (
                value
                if node.kind in ("variable_declarator", "field_definition", "public_field_definition") and value
                else node
            )
            body = declaration.child_by_field("body")
            scope_candidates = scopes.get((self.text(name), node.span.end_byte), ()) if name is not None else ()
            entity = max(
                (e for e in scope_candidates if _entity_span(e).start_byte <= node.span.start_byte),
                key=lambda e: _entity_span(e).start_byte,
                default=None,
            )
            if entity is not None and body is not None and not self.unsafe[id(node)]:
                self.roots[entity.id] = body
                parameter = declaration.child_by_field("parameters") or declaration.child_by_field("parameter")
                if parameter is not None:
                    parameters[entity.id] = parameter
        self.disabled = any(n.kind in ("global_statement", "nonlocal_statement") for n in nodes)
        self.writes = {scope: _writes(root, self.text) for scope, root in self.roots.items()}
        self.imports: dict[tuple[str, str], CodeEntity] = {}
        self.assignments: dict[tuple[str, str], SyntaxNode] = {}
        for scope, parameter in parameters.items():
            for name in parameter.walk():
                if name.kind in ("identifier", "shorthand_property_identifier_pattern"):
                    self.writes[scope].setdefault(self.text(name), set()).add(
                        (name.span.start_byte, name.span.end_byte)
                    )
        for entity in result.entities:
            if entity.kind is not EntityKind.IMPORT or entity.parent_id not in self.roots:
                continue
            scope = entity.parent_id
            assert scope is not None
            metadata = dict(entity.metadata)
            if metadata.get("is_wildcard") == "true":
                self.disabled = True
            binding_name = metadata.get("binding", "")
            span = _entity_span(entity)
            self.writes[scope].setdefault(binding_name, set()).add((span.start_byte, span.end_byte))
            direct = any(
                n.kind in ("import_statement", "import_from_statement")
                and n.span.start_byte <= span.start_byte <= span.end_byte <= n.span.end_byte
                for n in self.roots[scope].children
            )
            if direct:
                self.imports[scope, binding_name] = entity
        for scope, root in self.roots.items():
            for statement in root.children:
                candidates = (
                    statement.children
                    if statement.kind in ("expression_statement", "lexical_declaration", "variable_declaration")
                    else ()
                )
                for node in candidates:
                    name = node.child_by_field("left") or node.child_by_field("name")
                    if (
                        node.kind in ("assignment", "variable_declarator")
                        and name is not None
                        and name.kind == "identifier"
                        and not self.unsafe[id(node)]
                    ):
                        self.assignments[scope, self.text(name)] = node

    def scopes(self, owner_id: str) -> tuple[str, ...]:
        scopes = []
        current = self.entities[owner_id]
        seen = set()
        while current.id not in seen:
            seen.add(current.id)
            if current.kind is not EntityKind.CLASS:
                scopes.append(current.id)
            if current.parent_id is None:
                break
            current = self.entities[current.parent_id]
        return tuple(scopes)

    def visible(self, name: str, owner_id: str) -> str | None:
        return next((scope for scope in self.scopes(owner_id) if name in self.writes.get(scope, {})), None)

    def imported(self, name: str, owner_id: str, before: int, module: str, symbol: str, form: str) -> CodeEntity | None:
        scope = self.visible(name, owner_id)
        entity = self.imports.get((scope, name)) if scope is not None else None
        if scope is None or entity is None or self.disabled:
            return None
        span = _entity_span(entity)
        if self.writes[scope][name] != {(span.start_byte, span.end_byte)} or span.end_byte > before:
            return None
        metadata = dict(entity.metadata)
        if (metadata.get("module"), metadata.get("imported_name"), metadata.get("import_form")) != (
            module,
            symbol,
            form,
        ):
            return None
        if metadata.get("relative_level", "0") != "0" or metadata.get("is_type_only") == "true":
            return None
        return entity

    def client(
        self, name: str, owner_id: str, before: int, module: str, symbol: str, form: str, constructor_kind: str
    ) -> Binding | None:
        scope = self.visible(name, owner_id)
        assignment = self.assignments.get((scope, name)) if scope is not None else None
        if scope is None or assignment is None or self.disabled:
            return None
        span = assignment.span
        if self.writes[scope][name] != {(span.start_byte, span.end_byte)} or span.end_byte > before:
            return None
        value = assignment.child_by_field("right") or assignment.child_by_field("value")
        function = (
            value.child_by_field("function") or value.child_by_field("constructor") if value is not None else None
        )
        if value is None or value.kind != constructor_kind or function is None or function.kind != "identifier":
            return None
        witness = self.imported(self.text(function), scope, span.start_byte, module, symbol, form)
        return None if witness is None else Binding(scope, assignment, witness)

    def parts(self, node: SyntaxNode | None) -> tuple[str, ...]:
        return _parts(node, self.text)


def provenance(binding: Binding) -> tuple[tuple[str, str], ...]:
    return (
        ("constructor_import_id", binding.constructor_import.id),
        ("binding_owner_id", binding.scope_id),
        ("binding_start_byte", str(binding.assignment.span.start_byte)),
        ("binding_end_byte", str(binding.assignment.span.end_byte)),
    )
