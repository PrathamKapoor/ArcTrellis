"""Normalized static HTTP syntax with explicit constructor/import provenance."""

from bisect import bisect_right
from collections.abc import Callable
from dataclasses import replace

from arctrellis.calls.extraction import _optional_call, _parts
from arctrellis.core import CodeEntity, EntityKind
from arctrellis.extraction import ExtractionResult
from arctrellis.extraction.models import _entity_span
from arctrellis.extraction.python import _recovery_subtrees
from arctrellis.extraction.source import _location, _PythonSource
from arctrellis.ingestion import Language
from arctrellis.parsing import ParsedSource, SyntaxNode

from .errors import FrameworkExtractionError
from .ids import _observation_id
from .models import HTTP_METHODS, Framework, FrameworkBinding, HttpRouteObservation, _route_order

type _Text = Callable[[SyntaxNode], str]
_SCOPES = frozenset(
    (
        "function_definition",
        "class_definition",
        "function_declaration",
        "generator_function_declaration",
        "class_declaration",
        "class",
        "function_expression",
        "generator_function",
        "arrow_function",
        "method_definition",
    )
)


def _literal(node: SyntaxNode | None, text: _Text) -> str | None:
    if node is None or node.kind != "string":
        return None
    spelling = text(node)
    if len(spelling) < 2 or spelling[0] not in ("'", '"') or spelling[-1] != spelling[0]:
        return None
    value = spelling[1:-1]
    if "\\" in value or "\n" in value or "\r" in value or spelling[0] in value:
        return None
    return value


def _arguments(call: SyntaxNode) -> tuple[SyntaxNode, ...]:
    args = call.child_by_field("arguments")
    return () if args is None else tuple(n for n in args.children if n.kind != "comment")


def _writes(root: SyntaxNode, text: _Text) -> dict[str, set[tuple[int, int]]]:
    """Conservative module/class-level binding writes; never enter callable bodies."""
    writes: dict[str, set[tuple[int, int]]] = {}
    pending = list(root.children)
    while pending:
        node = pending.pop()
        if node.kind == "decorated_definition":
            definition = node.child_by_field("definition")
            if definition is not None:
                pending.append(definition)
            continue
        if node.kind in _SCOPES:
            name = node.child_by_field("name")
            if name is not None:
                writes.setdefault(text(name), set()).add((node.span.start_byte, node.span.end_byte))
            continue
        target = None
        if node.kind in (
            "assignment",
            "augmented_assignment",
            "assignment_expression",
            "augmented_assignment_expression",
        ):
            target = node.child_by_field("left")
        elif node.kind == "variable_declarator":
            target = node.child_by_field("name")
        elif node.kind in ("for_statement", "for_in_statement"):
            target = node.child_by_field("left")
        elif node.kind in ("delete_statement", "update_expression"):
            target = node.child_by_field("argument") or (node.children[0] if node.children else None)
        elif node.kind == "named_expression":
            target = node.child_by_field("name")
        elif node.kind == "as_pattern":
            target = node.child_by_field("alias")
        elif node.kind == "case_pattern":
            # Pattern capture syntax can bind names. Reject any potentially
            # affected receiver; interpreting complete match patterns is deferred.
            target = node
        if target is not None:
            parts = _parts(target, text)
            if parts:
                writes.setdefault(parts[0], set()).add((node.span.start_byte, node.span.end_byte))
            elif target.kind in (
                "tuple_pattern",
                "list_pattern",
                "pattern_list",
                "array_pattern",
                "object_pattern",
                "as_pattern_target",
                "case_pattern",
            ):
                for name in target.walk():
                    if name.kind in ("identifier", "shorthand_property_identifier_pattern"):
                        writes.setdefault(text(name), set()).add((node.span.start_byte, node.span.end_byte))
        pending.extend(node.children)
    return writes


def _constructor_import(site: CodeEntity) -> tuple[Framework, str] | None:
    m = dict(site.metadata)
    if m.get("is_type_only") == "true":
        return None
    if m.get("import_form") == "from" and m.get("relative_level") == "0":
        if m.get("module") == "fastapi" and m.get("imported_name") in ("FastAPI", "APIRouter"):
            return Framework.FASTAPI, m["imported_name"]
        if m.get("module") == "flask" and m.get("imported_name") == "Flask":
            return Framework.FLASK, "Flask"
    if (
        m.get("module") == "express"
        and m.get("module_literal") in ('"express"', "'express'")
        and m.get("import_form") in ("default", "require")
    ):
        return Framework.EXPRESS, "express"
    return None


def _bindings(
    parsed: ParsedSource, result: ExtractionResult, text: _Text, unsafe: dict[int, bool]
) -> dict[str, tuple[Framework, FrameworkBinding]]:
    writes = _writes(parsed.root, text)
    imports: dict[str, list[CodeEntity]] = {}
    statements = parsed.root.children
    starts = [n.span.start_byte for n in statements]
    for entity in result.entities:
        if entity.kind is EntityKind.IMPORT and entity.parent_id == result.module.id:
            if dict(entity.metadata).get("is_wildcard") == "true":
                return {}
            imported_binding = dict(entity.metadata).get("binding", "")
            if imported_binding:
                span = _entity_span(entity)
                writes.setdefault(imported_binding, set()).add((span.start_byte, span.end_byte))
                position = bisect_right(starts, span.start_byte) - 1
                statement = statements[position] if position >= 0 else None
                if (
                    statement is not None
                    and statement.kind
                    in ("import_statement", "import_from_statement", "lexical_declaration", "variable_declaration")
                    and span.end_byte <= statement.span.end_byte
                ):
                    imports.setdefault(imported_binding, []).append(entity)
    candidates: list[SyntaxNode] = []
    for statement in parsed.root.children:
        if statement.kind in ("expression_statement", "lexical_declaration", "variable_declaration"):
            candidates.extend(statement.children)
    bindings = {}
    for node in candidates:
        if node.kind not in ("assignment", "variable_declarator") or unsafe[id(node)]:
            continue
        name = node.child_by_field("left") or node.child_by_field("name")
        value = node.child_by_field("right") or node.child_by_field("value")
        if name is None or name.kind != "identifier" or value is None or value.kind not in ("call", "call_expression"):
            continue
        local_name = text(name)
        if not _parts(name, text) or len(writes.get(local_name, ())) != 1:
            continue
        parts = _parts(value.child_by_field("function"), text)
        if not parts or len(parts) > 2:
            continue
        sites = imports.get(parts[0], [])
        if len(sites) != 1 or len(writes.get(parts[0], ())) != 1:
            continue
        site = sites[0]
        if dict(site.metadata).get("import_form") == "require" and writes.get("require"):
            continue
        constructor = _constructor_import(site)
        if constructor is None or _entity_span(site).end_byte > node.span.start_byte:
            continue
        framework, kind = constructor
        if len(parts) == 2:
            if framework is not Framework.EXPRESS or parts[1] != "Router":
                continue
            kind = "Router"
        arguments = value.child_by_field("arguments")
        function = value.child_by_field("function")
        if arguments is None or function is None or _optional_call(parsed, value, function, arguments):
            continue
        binding = FrameworkBinding(
            local_name, site.id, kind, node.span, "local" if kind in ("APIRouter", "Router") else "declared"
        )
        bindings[local_name] = framework, binding
    return bindings


def _observe(
    parsed: ParsedSource,
    result: ExtractionResult,
    framework: Framework,
    binding: FrameworkBinding,
    node: SyntaxNode,
    methods: tuple[str, ...],
    path: str | None,
    reference: tuple[str, ...],
    handler: CodeEntity | None,
    kind: str,
    pre_count: int = 0,
    handler_binding_supported: bool = True,
) -> HttpRouteObservation:
    route = HttpRouteObservation(
        "pending",
        parsed.path,
        parsed.language,
        framework,
        result.module.id,
        binding,
        methods,
        path if path is not None and path.startswith("/") else None,
        reference,
        None if handler is None else _entity_span(handler),
        _location(parsed.path, node.span),
        node.span,
        kind,
        pre_count,
        handler_binding_supported,
    )
    return replace(route, id=_observation_id(route))


def _python_routes(
    parsed: ParsedSource,
    result: ExtractionResult,
    bindings: dict[str, tuple[Framework, FrameworkBinding]],
    text: _Text,
    unsafe: dict[int, bool],
) -> list[HttpRouteObservation]:
    handlers = {
        (e.name, _entity_span(e).start_byte, _entity_span(e).end_byte): e
        for e in result.entities
        if e.kind in (EntityKind.FUNCTION, EntityKind.METHOD)
    }
    routes = []
    class_ends = {e.id: _entity_span(e).end_byte for e in result.entities if e.kind is EntityKind.CLASS}
    class_imports: dict[int, set[str]] = {}
    for entity in result.entities:
        if entity.kind is EntityKind.IMPORT and entity.parent_id in class_ends:
            assert entity.parent_id is not None
            class_imports.setdefault(class_ends[entity.parent_id], set()).add(dict(entity.metadata).get("binding", ""))
    pending: list[tuple[SyntaxNode, frozenset[str]]] = [(n, frozenset()) for n in reversed(parsed.root.children)]
    while pending:
        node, hidden = pending.pop()
        if node.kind == "class_definition" or (
            node.kind == "decorated_definition"
            and (definition := node.child_by_field("definition")) is not None
            and definition.kind == "class_definition"
        ):
            definition = node if node.kind == "class_definition" else node.child_by_field("definition")
            if unsafe[id(node)] or definition is None:
                continue
            body = definition.child_by_field("body")
            if body is not None:
                shadowed = (
                    hidden | frozenset(_writes(body, text)) | frozenset(class_imports.get(definition.span.end_byte, ()))
                )
                pending.extend((n, shadowed) for n in reversed(body.children))
            continue
        if node.kind != "decorated_definition" or unsafe[id(node)]:
            continue
        definition = node.child_by_field("definition")
        name = None if definition is None else definition.child_by_field("name")
        handler = None if name is None else handlers.get((text(name), node.span.start_byte, node.span.end_byte))
        if handler is None:
            continue
        for decorator in node.children:
            if decorator.kind != "decorator" or not decorator.children:
                continue
            call = decorator.children[0]
            if call.kind != "call":
                continue
            parts = _parts(call.child_by_field("function"), text)
            if len(parts) != 2 or "*" in hidden or parts[0] in hidden or parts[0] not in bindings:
                continue
            framework, binding = bindings[parts[0]]
            if binding.span.end_byte > decorator.span.start_byte:
                continue
            verb = parts[1]
            if not (
                framework is Framework.FASTAPI
                and verb in {m.lower() for m in HTTP_METHODS}
                or framework is Framework.FLASK
                and verb == "route"
            ):
                continue
            args = _arguments(call)
            positional = tuple(a for a in args if a.kind != "keyword_argument")
            path = _literal(positional[0], text) if positional else None
            methods: tuple[str, ...] = (verb.upper(),) if verb != "route" else ("GET",)
            keywords: dict[str, list[SyntaxNode]] = {}
            for arg in args:
                key = arg.child_by_field("name") if arg.kind == "keyword_argument" else None
                value = arg.child_by_field("value")
                if key is not None and value is not None:
                    keywords.setdefault(text(key), []).append(value)
            path_key = "rule" if framework is Framework.FLASK else "path"
            supplied_paths = keywords.get(path_key, [])
            if not positional and len(supplied_paths) == 1:
                path = _literal(supplied_paths[0], text)
            if (
                len(positional) > 1
                or positional
                and supplied_paths
                or len(supplied_paths) > 1
                or ("path" if path_key == "rule" else "rule") in keywords
                or any(a.kind in ("list_splat", "dictionary_splat") for a in args)
                or any(len(values) > 1 for values in keywords.values())
            ):
                path = None
            if "methods" in keywords:
                values = keywords["methods"]
                if (
                    framework is not Framework.FLASK
                    or verb != "route"
                    or len(values) != 1
                    or values[0].kind not in ("list", "tuple", "set")
                ):
                    methods = ()
                else:
                    raw = [_literal(v, text) for v in values[0].children if v.kind != "comment"]
                    methods = (
                        tuple(sorted({v.upper() for v in raw if v is not None}))
                        if raw and all(v is not None and v.upper() in HTTP_METHODS for v in raw)
                        else ()
                    )
            routes.append(
                _observe(
                    parsed, result, framework, binding, decorator, methods, path, (handler.name,), handler, "decorator"
                )
            )
    return routes


def _reference_support(
    parsed: ParsedSource, result: ExtractionResult, text: _Text
) -> Callable[[tuple[str, ...]], bool]:
    writes = _writes(parsed.root, text)
    declarations: dict[str, set[tuple[int, int]]] = {}
    direct: list[SyntaxNode] = []

    for statement in parsed.root.children:
        if statement.kind == "export_statement":
            direct.extend(statement.children)
        else:
            direct.append(statement)
    for statement in direct:
        if statement.kind in ("function_declaration", "generator_function_declaration"):
            name = statement.child_by_field("name")
            if name is not None:
                declarations.setdefault(text(name), set()).add((statement.span.start_byte, statement.span.end_byte))
        elif statement.kind in ("lexical_declaration", "variable_declaration"):
            for declarator in statement.children:
                name = declarator.child_by_field("name")
                if declarator.kind == "variable_declarator" and name is not None and name.kind == "identifier":
                    declarations.setdefault(text(name), set()).add(
                        (declarator.span.start_byte, declarator.span.end_byte)
                    )
    represented: dict[str, set[tuple[int, int]]] = {}
    require_bindings: set[str] = set()
    for entity in result.entities:
        if entity.parent_id == result.module.id and entity.kind in (EntityKind.FUNCTION, EntityKind.IMPORT):
            span = _entity_span(entity)
            entity_binding = (
                dict(entity.metadata).get("binding", "") if entity.kind is EntityKind.IMPORT else entity.name
            )
            represented.setdefault(entity_binding, set()).add((span.start_byte, span.end_byte))
            if entity.kind is EntityKind.IMPORT and dict(entity.metadata).get("import_form") == "require":
                require_bindings.add(entity_binding)

    def supported(reference: tuple[str, ...]) -> bool:
        if not reference:
            return False
        root = reference[0]
        known = represented.get(root, set())
        safe = writes.get(root, set()).issubset(known) and (
            not declarations.get(root) or known.issubset(declarations.get(root, set()))
        )
        if known and writes.get(root) and not known.issubset(declarations.get(root, set())):
            safe = False
        if root in require_bindings and writes.get("require"):
            safe = False
        return safe

    return supported


def _express_routes(
    parsed: ParsedSource,
    result: ExtractionResult,
    bindings: dict[str, tuple[Framework, FrameworkBinding]],
    text: _Text,
    unsafe: dict[int, bool],
) -> list[HttpRouteObservation]:
    routes = []
    supported_reference = _reference_support(parsed, result, text)
    for statement in parsed.root.children:
        if statement.kind != "expression_statement":
            continue
        for call in statement.children:
            if call.kind != "call_expression" or unsafe[id(call)]:
                continue
            function, arguments = call.child_by_field("function"), call.child_by_field("arguments")
            parts = _parts(function, text)
            if len(parts) != 2 or parts[0] not in bindings or parts[1] not in {m.lower() for m in HTTP_METHODS}:
                continue
            framework, binding = bindings[parts[0]]
            if (
                binding.span.end_byte > call.span.start_byte
                or function is None
                or arguments is None
                or _optional_call(parsed, call, function, arguments)
            ):
                continue
            args = _arguments(call)
            if len(args) < 2:
                # Express get(name) reads an application setting, not a route.
                continue
            path = _literal(args[0], text) if args else None
            reference = _parts(args[-1], text) if len(args) > 1 else ()
            if any(
                a.kind in ("number", "string", "true", "false", "null", "undefined", "object", "regex")
                for a in args[1:]
            ):
                path = None
            supported = not reference or supported_reference(reference)
            routes.append(
                _observe(
                    parsed,
                    result,
                    framework,
                    binding,
                    call,
                    (parts[1].upper(),),
                    path,
                    reference,
                    None,
                    "direct_call",
                    max(0, len(args) - 2),
                    supported,
                )
            )
    return routes


def extract_framework_observations(
    parsed_source: ParsedSource, extraction_result: ExtractionResult
) -> tuple[HttpRouteObservation, ...]:
    """Recognize route syntax from unique module bindings without target selection.

    Literal paths contain no escapes, interpolation or concatenation. Router paths
    remain local. Dynamic paths/method collections retain unsupported observations.
    Callable factories, nested registrations and unbound receivers are omitted.
    """
    if not isinstance(parsed_source, ParsedSource) or not isinstance(extraction_result, ExtractionResult):
        raise TypeError("framework extraction requires owned parsing and semantic results")
    parsed, result = parsed_source, extraction_result
    if (parsed.path, parsed.language, parsed.root.span) != (result.path, result.language, _entity_span(result.module)):
        raise FrameworkExtractionError("source and semantic result must describe the same file/root revision")
    ExtractionResult(result.path, result.language, result.entities, result.partial)
    if parsed.language is Language.PYTHON:
        text = _PythonSource.from_parsed(parsed).text
    else:
        parsed.source.decode("utf-8")

        def text(node: SyntaxNode) -> str:
            return parsed.bytes_for(node).decode("utf-8")

    unsafe = _recovery_subtrees(parsed.root)
    bindings = _bindings(parsed, result, text, unsafe)
    routes = (
        _python_routes(parsed, result, bindings, text, unsafe)
        if parsed.language is Language.PYTHON
        else _express_routes(parsed, result, bindings, text, unsafe)
    )
    return tuple(sorted(routes, key=_route_order))
