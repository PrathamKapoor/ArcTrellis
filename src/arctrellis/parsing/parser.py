"""Single-file syntax parsing; no semantic extraction or repository execution."""

import os

from arctrellis.ingestion import DiscoveredFile, Language
from .errors import ParserExecutionError
from .models import ParsedSource
from .normalization import _normalize_tree
from .registry import _grammar_for, _new_parser
from .source import DEFAULT_MAX_SOURCE_BYTES, _check_size, _read_source, _validate_limit


def parse_source(path: str, language: Language | None, source: bytes, *,
                 max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES) -> ParsedSource:
    """Parse exact bytes using an extension-compatible grammar and fresh parser.

    Syntax recovery returns diagnostics; hard infrastructure failures raise typed
    errors. The inclusive byte limit applies before native parsing. No decoding
    or target execution occurs; current usage is synchronous and single-file.
    """
    _validate_limit(max_source_bytes)
    if not isinstance(source, bytes):
        raise TypeError("source must be immutable bytes")
    grammar = _grammar_for(path, language)
    _check_size(len(source), max_source_bytes)
    parser = _new_parser(grammar)
    try:
        tree = parser.parse(source)
    except (ValueError, RuntimeError) as error:
        raise ParserExecutionError(f"parser failed for {path}") from error
    if tree is None:
        raise ParserExecutionError(f"parser returned no tree for {path}")
    root, diagnostics = _normalize_tree(tree.root_node)
    return ParsedSource(path, language, source, root, diagnostics)


def parse_discovered_file(repository_root: str | os.PathLike[str], discovered_file: DiscoveredFile, *,
                          max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES) -> ParsedSource:
    """Revalidate and read one discovered source file, then normalize its syntax.

    Inventory size is not trusted. Reject observed links and nonregular targets;
    the filesystem must remain stable because path checks are not atomic.
    """
    if not isinstance(discovered_file, DiscoveredFile):
        raise TypeError("discovered_file must be DiscoveredFile")
    _validate_limit(max_source_bytes)
    _grammar_for(discovered_file.path, discovered_file.language)
    source = _read_source(repository_root, discovered_file, max_source_bytes)
    return parse_source(discovered_file.path, discovered_file.language, source,
                        max_source_bytes=max_source_bytes)
