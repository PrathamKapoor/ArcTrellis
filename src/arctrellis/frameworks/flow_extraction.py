"""Retain pre-handler occurrences while normalized syntax is already owned."""

from bisect import bisect_right
from collections.abc import Callable
from dataclasses import replace

from arctrellis.calls.extraction import _parts
from arctrellis.core import CodeEntity, EntityKind
from arctrellis.extraction import ExtractionResult
from arctrellis.extraction.models import _entity_span
from arctrellis.extraction.python import _recovery_subtrees
from arctrellis.extraction.source import _location, _PythonSource
from arctrellis.ingestion import Language
from arctrellis.parsing import ParsedSource, SyntaxNode

from .errors import FrameworkExtractionError
from .extraction import _arguments, _bindings, _reference_support, _Text, _writes
from .flow_models import PreHandlerKind, PreHandlerObservation, _pre_id, _pre_order
from .models import Framework, FrameworkBinding, HttpRouteObservation


def _python_reference_support(
    parsed: ParsedSource, result: ExtractionResult, text: _Text
) -> Callable[[tuple[str, ...]], bool]:
    writes = _writes(parsed.root, text)
    represented: dict[str, list[CodeEntity]] = {}
    statements = parsed.root.children
    starts = [n.span.start_byte for n in statements]
    for entity in result.entities:
        if entity.parent_id == result.module.id and entity.kind in (EntityKind.FUNCTION, EntityKind.IMPORT):
            name = entity.name if entity.kind is EntityKind.FUNCTION else dict(entity.metadata).get("binding", "")
            represented.setdefault(name, []).append(entity)

    def supported(reference: tuple[str, ...]) -> bool:
        if not reference:
            return False
        candidates = represented.get(reference[0], [])
        spans = [_entity_span(e) for e in candidates]
        for span in spans:
            position = bisect_right(starts, span.start_byte) - 1
            statement = statements[position] if position >= 0 else None
            if (
                statement is None
                or statement.kind
                not in ("function_definition", "decorated_definition", "import_from_statement", "import_statement")
                or span.end_byte > statement.span.end_byte
            ):
                return False
        return all(any(s.start_byte <= a and b == s.end_byte for s in spans) for a, b in writes.get(reference[0], ()))

    return supported


def _depends_imports(parsed: ParsedSource, result: ExtractionResult, text: _Text) -> dict[str, CodeEntity]:
    writes = _writes(parsed.root, text)
    imports: dict[str, list[CodeEntity]] = {}
    for e in result.entities:
        if e.kind is EntityKind.IMPORT and e.parent_id == result.module.id:
            meta = dict(e.metadata)
            if meta.get("is_wildcard") == "true":
                return {}
            imports.setdefault(meta.get("binding", ""), []).append(e)
    good = {}
    for name, sites in imports.items():
        if len(sites) != 1 or writes.get(name):
            continue
        e = sites[0]
        meta, span = dict(e.metadata), _entity_span(e)
        if (meta.get("module"), meta.get("import_form"), meta.get("relative_level"), meta.get("imported_name")) != (
            "fastapi",
            "from",
            "0",
            "Depends",
        ):
            continue
        if any(
            n.kind == "import_from_statement"
            and n.span.start_byte <= span.start_byte
            and span.end_byte <= n.span.end_byte
            for n in parsed.root.children
        ):
            good[name] = e
    return good


def _observation(
    parsed: ParsedSource,
    framework: Framework,
    kind: PreHandlerKind,
    owner: str,
    binding: FrameworkBinding,
    route_id: str | None,
    reference: tuple[str, ...],
    order: int,
    node: SyntaxNode,
    declaration: CodeEntity | None = None,
    provenance: str | None = None,
    supported: bool = True,
) -> PreHandlerObservation:
    value = PreHandlerObservation(
        "pending",
        parsed.path,
        parsed.language,
        framework,
        kind,
        owner,
        binding,
        route_id,
        reference,
        order,
        _location(parsed.path, node.span),
        node.span,
        None if declaration is None else _entity_span(declaration),
        provenance,
        supported,
    )
    return replace(value, id=_pre_id(value))


def extract_pre_handler_observations(
    parsed_source: ParsedSource,
    extraction_result: ExtractionResult,
    route_observations: tuple[HttpRouteObservation, ...],
) -> tuple[PreHandlerObservation, ...]:
    """Direct Express args, decorator Depends lists/tuples and module Flask hooks.

    Unsupported route-local expressions remain explicit observations. Unrelated
    Depends spellings and fake receivers do not establish framework provenance.
    """
    if not isinstance(parsed_source, ParsedSource) or not isinstance(extraction_result, ExtractionResult):
        raise TypeError("pre-handler extraction requires canonical source/results")
    parsed, result = parsed_source, extraction_result
    if (parsed.path, parsed.language, parsed.root.span) != (result.path, result.language, _entity_span(result.module)):
        raise FrameworkExtractionError("pre-handler source/result revision mismatch")
    if not isinstance(route_observations, tuple) or any(
        not isinstance(r, HttpRouteObservation) or r.path != parsed.path or r.owner_module_id != result.module.id
        for r in route_observations
    ):
        raise FrameworkExtractionError("pre-handler routes must describe the same source")
    if parsed.language is Language.PYTHON:
        text = _PythonSource.from_parsed(parsed).text
    else:
        parsed.source.decode("utf-8")

        def text(node: SyntaxNode) -> str:
            return parsed.bytes_for(node).decode("utf-8")

    unsafe = _recovery_subtrees(parsed.root)
    nodes = {
        (n.span.start_byte, n.span.end_byte): n
        for n in parsed.root.walk()
        if n.kind in ("decorator", "call_expression")
    }
    support = (
        _python_reference_support(parsed, result, text)
        if parsed.language is Language.PYTHON
        else _reference_support(parsed, result, text)
    )
    depends = _depends_imports(parsed, result, text) if parsed.language is Language.PYTHON else {}
    module_declarations = {
        (_entity_span(e).start_byte, _entity_span(e).end_byte)
        for e in result.entities
        if e.kind is EntityKind.FUNCTION and e.parent_id == result.module.id
    }
    observations = []
    for route in route_observations:
        node = nodes.get((route.span.start_byte, route.span.end_byte))
        if node is None or unsafe[id(node)]:
            continue
        if route.framework is Framework.EXPRESS:
            for order, argument in enumerate(_arguments(node)[1:-1]):
                reference = _parts(argument, text)
                observations.append(
                    _observation(
                        parsed,
                        route.framework,
                        PreHandlerKind.ROUTE_MIDDLEWARE,
                        route.owner_module_id,
                        route.binding,
                        route.id,
                        reference,
                        order,
                        argument,
                        supported=support(reference),
                    )
                )
        elif route.framework is Framework.FASTAPI and node.children:
            declaration = route.handler_declaration_span
            if declaration is None or (declaration.start_byte, declaration.end_byte) not in module_declarations:
                # Definition-time class namespaces are not module lookup scopes.
                # Class-scoped dependency injection is deliberately deferred.
                continue
            collection = None
            for arg in _arguments(node.children[0]):
                name = arg.child_by_field("name")
                if name is not None and text(name) == "dependencies":
                    collection = arg.child_by_field("value")
            if collection is None or collection.kind not in ("list", "tuple"):
                continue
            for order, dependency in enumerate(n for n in collection.children if n.kind != "comment"):
                parts = _parts(dependency.child_by_field("function"), text)
                witness = depends.get(parts[0]) if len(parts) == 1 and dependency.kind == "call" else None
                if witness is None or _entity_span(witness).end_byte > dependency.span.start_byte:
                    continue
                args = _arguments(dependency)
                reference = _parts(args[0], text) if len(args) == 1 else ()
                observations.append(
                    _observation(
                        parsed,
                        route.framework,
                        PreHandlerKind.DEPENDENCY,
                        route.owner_module_id,
                        route.binding,
                        route.id,
                        reference,
                        order,
                        dependency,
                        provenance=witness.id,
                        supported=support(reference),
                    )
                )
    if parsed.language is Language.PYTHON:
        bindings = _bindings(parsed, result, text, unsafe)
        declarations = {
            (e.name, _entity_span(e).start_byte, _entity_span(e).end_byte): e
            for e in result.entities
            if e.kind is EntityKind.FUNCTION and e.parent_id == result.module.id
        }
        hook_orders: dict[str, int] = {}
        for node in parsed.root.children:
            if node.kind != "decorated_definition" or unsafe[id(node)]:
                continue
            definition = node.child_by_field("definition")
            name = None if definition is None else definition.child_by_field("name")
            handler = None if name is None else declarations.get((text(name), node.span.start_byte, node.span.end_byte))
            if handler is None:
                continue
            for decorator in node.children:
                if decorator.kind != "decorator" or not decorator.children:
                    continue
                parts = _parts(decorator.children[0], text)
                item = bindings.get(parts[0]) if len(parts) == 2 and parts[1] == "before_request" else None
                if item is None or item[0] is not Framework.FLASK or item[1].span.end_byte > decorator.span.start_byte:
                    continue
                binding = item[1]
                order = hook_orders.get(binding.name, 0)
                hook_orders[binding.name] = order + 1
                observations.append(
                    _observation(
                        parsed,
                        Framework.FLASK,
                        PreHandlerKind.REQUEST_HOOK,
                        result.module.id,
                        binding,
                        None,
                        (handler.name,),
                        order,
                        decorator,
                        declaration=handler,
                    )
                )
    return tuple(sorted(observations, key=_pre_order))
