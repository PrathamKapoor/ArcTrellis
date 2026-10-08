"""Revision-deterministic declaration identity, independent of syntax grammars."""

import json
from uuid import NAMESPACE_URL, uuid5

from arctrellis.core import EntityKind
from arctrellis.ingestion import DiscoveredFile, Language


def make_entity_id(
    *, language: Language, path: str, kind: EntityKind, qualified_name: str, start_byte: int, end_byte: int
) -> str:
    """Return UUID5 over a versioned canonical key; not stable across source edits.

    The key is a compact JSON array of marker, language, path, kind, lexical name
    and half-open byte offsets. Repository identity is not established here.
    """
    if not isinstance(language, Language) or not isinstance(kind, EntityKind):
        raise TypeError("language and kind must be canonical enum members")
    DiscoveredFile(path, 0, language)
    if not isinstance(qualified_name, str):
        raise TypeError("qualified_name must be a string")
    if not qualified_name or qualified_name != qualified_name.strip():
        raise ValueError("qualified_name must be nonempty without surrounding whitespace")
    if type(start_byte) is not int or type(end_byte) is not int:
        raise TypeError("byte offsets must be integers, not booleans")
    if not 0 <= start_byte <= end_byte:
        raise ValueError("byte range must satisfy 0 <= start_byte <= end_byte")
    key = json.dumps(
        ["arctrellis-entity-v1", language.value, path, kind.value, qualified_name, start_byte, end_byte],
        ensure_ascii=True,
        separators=(",", ":"),
    )
    return str(uuid5(NAMESPACE_URL, key))
