"""Deterministic structural retrieval over existing canonical analysis snapshots.

Phase 2.3A exposes the build-time lexical snapshot only. It indexes structural
metadata, not source text, and it never executes, imports, installs or networks
with target repository code.
"""

from .documents import (
    FIELD_ENTITY_KIND,
    FIELD_LANGUAGE,
    FIELD_NAME,
    FIELD_PATH,
    FIELD_QUALIFIED_NAME,
    SEARCHABLE_METADATA_KEYS,
    SearchDocument,
    SearchField,
    build_document,
)
from .errors import InvalidSearchIndexError, RetrievalError, RetrievalInvariantError
from .index import LexicalSearchIndex, build_search_index

__all__ = [
    "FIELD_ENTITY_KIND",
    "FIELD_LANGUAGE",
    "FIELD_NAME",
    "FIELD_PATH",
    "FIELD_QUALIFIED_NAME",
    "InvalidSearchIndexError",
    "LexicalSearchIndex",
    "RetrievalError",
    "RetrievalInvariantError",
    "SEARCHABLE_METADATA_KEYS",
    "SearchDocument",
    "SearchField",
    "build_document",
    "build_search_index",
]
