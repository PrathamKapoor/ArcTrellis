"""Versioned canonical JSON identities, consistent with semantic proof producers."""

import json
from uuid import NAMESPACE_URL, uuid5

from .models import HttpRouteObservation


def _identity(marker: str, *components: object) -> str:
    return str(uuid5(NAMESPACE_URL, json.dumps([marker, *components], separators=(",", ":"), ensure_ascii=True)))


def _observation_id(route: HttpRouteObservation) -> str:
    return _identity(
        "arctrellis-http-observation-v1",
        route.framework.value,
        route.language.value,
        route.path,
        route.owner_module_id,
        route.binding.name,
        route.binding.import_entity_id,
        route.binding.constructor,
        route.binding.span.start_byte,
        route.binding.span.end_byte,
        route.binding.path_completeness,
        route.span.start_byte,
        route.span.end_byte,
        route.route_path,
        route.http_methods,
        route.handler_reference,
        None
        if route.handler_declaration_span is None
        else (route.handler_declaration_span.start_byte, route.handler_declaration_span.end_byte),
        route.registration_kind,
        route.pre_handler_argument_count,
        route.handler_binding_supported,
    )
