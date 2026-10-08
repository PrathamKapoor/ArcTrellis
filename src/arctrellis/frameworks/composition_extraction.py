"""Observe direct router configuration and mounts using normalized syntax only."""

from dataclasses import replace

from arctrellis.calls.extraction import _optional_call, _parts
from arctrellis.extraction import ExtractionResult
from arctrellis.extraction.models import _entity_span
from arctrellis.extraction.python import _recovery_subtrees
from arctrellis.extraction.source import _location, _PythonSource
from arctrellis.ingestion import Language
from arctrellis.parsing import ParsedSource, SyntaxNode

from .composition_models import RouterMountObservation, RouterPrefixObservation, _router_id, _router_order
from .errors import FrameworkExtractionError
from .extraction import _arguments, _bindings, _literal, _Text
from .models import Framework


def _prefix_argument(call: SyntaxNode, text: _Text) -> tuple[str | None, SyntaxNode | None]:
    args = _arguments(call)
    keywords: dict[str, list[SyntaxNode]] = {}
    invalid = False
    for arg in args:
        if arg.kind in ("list_splat", "dictionary_splat"):
            invalid = True
        if arg.kind == "keyword_argument":
            name, value = arg.child_by_field("name"), arg.child_by_field("value")
            if name is not None and value is not None:
                keywords.setdefault(text(name), []).append(value)
    if invalid or any(len(values) > 1 for values in keywords.values()):
        return None, None
    values = keywords.get("prefix", [])
    if not values:
        return "", None
    prefix = _literal(values[0], text)
    return prefix if prefix is not None and (
        not prefix or prefix.startswith("/") and not prefix.endswith("/")
    ) else None, values[0]


def extract_router_observations(
    parsed_source: ParsedSource, extraction_result: ExtractionResult
) -> tuple[tuple[RouterPrefixObservation, ...], tuple[RouterMountObservation, ...]]:
    """Same-file constructor prefixes and direct app mounts; no nested inference."""
    if not isinstance(parsed_source, ParsedSource) or not isinstance(extraction_result, ExtractionResult):
        raise TypeError("router extraction requires canonical source/results")
    parsed, result = parsed_source, extraction_result
    if (parsed.path, parsed.language, parsed.root.span) != (result.path, result.language, _entity_span(result.module)):
        raise FrameworkExtractionError("router source/result revision mismatch")
    if parsed.language is Language.PYTHON:
        text = _PythonSource.from_parsed(parsed).text
    else:
        parsed.source.decode("utf-8")

        def text(node: SyntaxNode) -> str:
            return parsed.bytes_for(node).decode("utf-8")

    unsafe = _recovery_subtrees(parsed.root)
    bindings = _bindings(parsed, result, text, unsafe)
    constructors = {
        (n.span.start_byte, n.span.end_byte): n
        for n in parsed.root.walk()
        if n.kind in ("assignment", "variable_declarator")
    }
    prefixes = []
    for framework, binding in bindings.values():
        if binding.constructor not in ("APIRouter", "Router"):
            continue
        node = constructors[(binding.span.start_byte, binding.span.end_byte)]
        call = node.child_by_field("right") or node.child_by_field("value")
        assert call is not None
        prefix, prefix_node = _prefix_argument(call, text) if framework is Framework.FASTAPI else ("", None)
        observation = RouterPrefixObservation(
            "pending",
            parsed.path,
            parsed.language,
            framework,
            result.module.id,
            binding,
            prefix,
            _location(parsed.path, node.span),
            node.span,
            None if prefix_node is None else prefix_node.span,
        )
        prefixes.append(replace(observation, id=_router_id(observation)))
    mounts = []
    for statement in parsed.root.children:
        if statement.kind != "expression_statement":
            continue
        for call in statement.children:
            if call.kind not in ("call", "call_expression") or unsafe[id(call)]:
                continue
            function, arguments = call.child_by_field("function"), call.child_by_field("arguments")
            parts = _parts(function, text)
            item = bindings.get(parts[0]) if len(parts) == 2 else None
            if item is None:
                continue
            framework, binding = item
            if (
                framework is Framework.FASTAPI
                and parts[1] != "include_router"
                or framework is Framework.EXPRESS
                and parts[1] != "use"
                or framework is Framework.FLASK
            ):
                continue
            if (
                function is None
                or arguments is None
                or _optional_call(parsed, call, function, arguments)
                or binding.span.end_byte > call.span.start_byte
            ):
                continue
            args = _arguments(call)
            if framework is Framework.EXPRESS:
                # Ordinary app.use middleware is not a router mount. Two args are
                # observed as a candidate; only an actual Router witness resolves.
                if len(args) != 2:
                    continue
                prefix = _literal(args[0], text)
                reference = _parts(args[1], text)
                if prefix is not None and prefix and not prefix.startswith("/"):
                    prefix = None
            else:
                positional = tuple(a for a in args if a.kind != "keyword_argument")
                prefix, _ = _prefix_argument(call, text)
                reference = _parts(positional[0], text) if len(positional) == 1 else ()
                if len(positional) != 1 or any(a.kind in ("list_splat", "dictionary_splat") for a in args):
                    prefix = None
            mount_observation = RouterMountObservation(
                "pending",
                parsed.path,
                parsed.language,
                framework,
                result.module.id,
                binding,
                reference,
                prefix,
                _location(parsed.path, call.span),
                call.span,
            )
            mounts.append(replace(mount_observation, id=_router_id(mount_observation)))
    return tuple(sorted(prefixes, key=_router_order)), tuple(sorted(mounts, key=_router_order))
