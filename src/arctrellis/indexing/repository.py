"""Synchronous best-effort source indexing with fatal graph invariants."""

import os
from pathlib import PurePosixPath

from arctrellis.core import CodeEntity, Confidence, EntityKind, Evidence, Relationship, RelationshipKind
from arctrellis.extraction import ExtractionError, extract_entities, build_lexical_graph
from arctrellis.graph import CodeGraph, GraphError
from arctrellis.ingestion import DiscoveredFile, scan_repository
from arctrellis.parsing import DEFAULT_MAX_SOURCE_BYTES, ParsingError, parse_discovered_file
from .errors import RepositoryIndexInvariantError
from .ids import _file_id, _stable_id
from .models import FileIndexResult, FileIndexStatus, RepositoryIndexResult


def _file_entity(file: DiscoveredFile, analyzed_size: int) -> CodeEntity:
    if file.language is None:
        raise RepositoryIndexInvariantError('unsupported file reached semantic assembly')
    return CodeEntity(_file_id(file.path, file.language), EntityKind.FILE, PurePosixPath(file.path).name,
                      file.path, language=file.language.value, metadata=(('size_bytes', str(analyzed_size)),))


def _membership(file: CodeEntity, module: CodeEntity) -> Relationship:
    if module.location is None:
        raise RepositoryIndexInvariantError('extracted module has no source evidence')
    coordinates = tuple((k, v) for k, v in module.metadata if k in (
        'start_byte', 'end_byte', 'start_line', 'start_column', 'end_line', 'end_column'))
    evidence = Evidence(_stable_id('arctrellis-membership-evidence-v1', file.id, module.id, coordinates),
                        module.location, 'file_module_membership', coordinates)
    return Relationship(_stable_id('arctrellis-membership-edge-v1', file.id, module.id, evidence.id),
                        file.id, RelationshipKind.DEFINES, module.id, Confidence.PROVEN, 1.0, (evidence,))


def _analyze_file(root: str | os.PathLike[str], file: DiscoveredFile, limit: int) -> tuple[FileIndexResult, CodeGraph | None]:
    if file.language is None:
        raise RepositoryIndexInvariantError('unsupported file reached analysis')
    diagnostics = 0
    stage = 'parsing'
    try:
        parsed = parse_discovered_file(root, file, max_source_bytes=limit)
        diagnostics = parsed.diagnostic_count
        stage = 'extraction'
        result = extract_entities(parsed)
    except (ParsingError, ExtractionError) as error:
        error_type = type(error).__name__[:128]
        return FileIndexResult(file.path, file.language, FileIndexStatus.FAILED, 0, 0, diagnostics,
                               error_type, f'{stage} failed ({error_type})'), None
    try:
        local = build_lexical_graph(result)
        structural = _file_entity(file, parsed.size_bytes)
        local.add_entity(structural)
        local.add_relationship(_membership(structural, result.module))
    except (GraphError, ExtractionError, TypeError, ValueError) as error:
        raise RepositoryIndexInvariantError(f'invalid semantic assembly for {file.path}') from error
    # Only semantic values escape this helper; parsed/source/tree references die here.
    status = FileIndexStatus.PARTIAL if result.partial else FileIndexStatus.COMPLETE
    return FileIndexResult(file.path, file.language, status, local.entity_count,
                           local.relationship_count, diagnostics), local


def index_repository(root: str | os.PathLike[str], *, max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES) -> RepositoryIndexResult:
    """Index supported sources; discovery/invariant failures abort, typed file failures continue."""
    if type(max_source_bytes) is not int or max_source_bytes <= 0:
        raise ValueError('max_source_bytes must be a positive non-boolean integer')
    inventory = scan_repository(root)
    graph = CodeGraph()
    outcomes = []
    for file in inventory.supported_files:
        summary, local = _analyze_file(root, file, max_source_bytes)
        if local is not None:
            try:
                for entity in local.entities():
                    graph.add_entity(entity)
                for relationship in local.relationships():
                    graph.add_relationship(relationship)
            except GraphError as error:
                raise RepositoryIndexInvariantError(f'graph collision while merging {file.path}') from error
        outcomes.append(summary)
    try:
        return RepositoryIndexResult(inventory, graph, tuple(outcomes))
    except (TypeError, ValueError) as error:
        raise RepositoryIndexInvariantError('repository summary does not match merged graph') from error
