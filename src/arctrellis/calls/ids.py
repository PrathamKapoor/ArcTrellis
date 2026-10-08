"""Versioned UUID5 identities; revision-deterministic, not repository-namespaced."""

import json
from uuid import NAMESPACE_URL, uuid5

from arctrellis.extraction.source import _location
from arctrellis.ingestion import Language
from arctrellis.parsing import SyntaxSpan

from .models import CalleeKind, CallSite


def _identity(marker: str, *components: object) -> str:
    return str(uuid5(NAMESPACE_URL, json.dumps((marker, *components), ensure_ascii=True, separators=(",", ":"))))


def make_call_site_id(
    language: Language,
    path: str,
    owner_entity_id: str,
    callee_kind: CalleeKind,
    callee_parts: tuple[str, ...],
    span: SyntaxSpan,
) -> str:
    """Reproduce an invocation identity from its syntax, owner and byte range."""
    if not isinstance(span, SyntaxSpan):
        raise TypeError("span must be SyntaxSpan")
    CallSite(
        "identity_validation", path, language, owner_entity_id, callee_kind, callee_parts, _location(path, span), span
    )
    return _identity(
        "arctrellis-call-site-v1",
        language.value,
        path,
        owner_entity_id,
        callee_kind.value,
        callee_parts,
        span.start_byte,
        span.end_byte,
    )
