"""Synchronous best-effort source indexing with fatal graph invariants."""

import os
from pathlib import PurePosixPath

from arctrellis.calls import CallExtractionError, CallSite, extract_call_sites
from arctrellis.core import CodeEntity, Confidence, EntityKind, Evidence, Relationship, RelationshipKind
from arctrellis.extraction import ExtractionError, build_lexical_graph, extract_entities
from arctrellis.frameworks import (
    FrameworkExtractionError,
    HttpRouteObservation,
    PreHandlerObservation,
    RouterMountObservation,
    RouterPrefixObservation,
    extract_framework_observations,
    extract_pre_handler_observations,
    extract_router_observations,
)
from arctrellis.graph import CodeGraph, GraphError
from arctrellis.ingestion import DiscoveredFile, scan_repository
from arctrellis.parsing import DEFAULT_MAX_SOURCE_BYTES, ParsingError, parse_discovered_file
from arctrellis.test_semantics.extraction import extract_test_observations
from arctrellis.test_semantics.models import TestObservation

from .errors import RepositoryIndexInvariantError
from .ids import _file_id, _stable_id
from .models import FileIndexResult, FileIndexStatus, RepositoryIndexResult


def _file_entity(file: DiscoveredFile, analyzed_size: int) -> CodeEntity:
    if file.language is None:
        raise RepositoryIndexInvariantError("unsupported file reached semantic assembly")
    return CodeEntity(
        _file_id(file.path, file.language),
        EntityKind.FILE,
        PurePosixPath(file.path).name,
        file.path,
        language=file.language.value,
        metadata=(("size_bytes", str(analyzed_size)),),
    )


def _membership(file: CodeEntity, module: CodeEntity) -> Relationship:
    if module.location is None:
        raise RepositoryIndexInvariantError("extracted module has no source evidence")
    coordinates = tuple(
        (k, v)
        for k, v in module.metadata
        if k in ("start_byte", "end_byte", "start_line", "start_column", "end_line", "end_column")
    )
    evidence = Evidence(
        _stable_id("arctrellis-membership-evidence-v1", file.id, module.id, coordinates),
        module.location,
        "file_module_membership",
        coordinates,
    )
    return Relationship(
        _stable_id("arctrellis-membership-edge-v1", file.id, module.id, evidence.id),
        file.id,
        RelationshipKind.DEFINES,
        module.id,
        Confidence.PROVEN,
        1.0,
        (evidence,),
    )


def _analyze_file(
    root: str | os.PathLike[str], file: DiscoveredFile, limit: int
) -> tuple[
    FileIndexResult,
    CodeGraph | None,
    tuple[CallSite, ...],
    tuple[HttpRouteObservation, ...],
    tuple[PreHandlerObservation, ...],
    tuple[RouterPrefixObservation, ...],
    tuple[RouterMountObservation, ...],
    tuple[TestObservation, ...],
]:
    if file.language is None:
        raise RepositoryIndexInvariantError("unsupported file reached analysis")
    diagnostics = 0
    stage = "parsing"
    try:
        parsed = parse_discovered_file(root, file, max_source_bytes=limit)
        diagnostics = parsed.diagnostic_count
        stage = "extraction"
        result = extract_entities(parsed)
        stage = "call_extraction"
        call_sites = extract_call_sites(parsed, result)
        stage = "framework_extraction"
        routes = extract_framework_observations(parsed, result)
        stage = "pre_handler_extraction"
        pre_handlers = extract_pre_handler_observations(parsed, result, routes)
        stage = "router_extraction"
        prefixes, mounts = extract_router_observations(parsed, result)
        stage = "test_extraction"
        tests = extract_test_observations(parsed, result)
    except (ParsingError, ExtractionError, CallExtractionError, FrameworkExtractionError) as error:
        error_type = type(error).__name__[:128]
        return (
            FileIndexResult(
                file.path,
                file.language,
                FileIndexStatus.FAILED,
                0,
                0,
                diagnostics,
                error_type,
                f"{stage} failed ({error_type})",
            ),
            None,
            (),
            (),
            (),
            (),
            (),
            (),
        )
    try:
        local = build_lexical_graph(result)
        structural = _file_entity(file, parsed.size_bytes)
        local.add_entity(structural)
        local.add_relationship(_membership(structural, result.module))
    except (GraphError, ExtractionError, TypeError, ValueError) as error:
        raise RepositoryIndexInvariantError(f"invalid semantic assembly for {file.path}") from error
    # Only semantic values escape this helper; parsed/source/tree references die here.
    status = FileIndexStatus.PARTIAL if result.partial else FileIndexStatus.COMPLETE
    return (
        FileIndexResult(
            file.path,
            file.language,
            status,
            local.entity_count,
            local.relationship_count,
            diagnostics,
            call_site_count=len(call_sites),
            route_observation_count=len(routes),
            pre_handler_observation_count=len(pre_handlers),
            router_observation_count=len(prefixes) + len(mounts),
            test_observation_count=len(tests),
        ),
        local,
        call_sites,
        routes,
        pre_handlers,
        prefixes,
        mounts,
        tests,
    )


def index_repository(
    root: str | os.PathLike[str], *, max_source_bytes: int = DEFAULT_MAX_SOURCE_BYTES
) -> RepositoryIndexResult:
    """Index supported sources; discovery/invariant failures abort, typed file failures continue."""
    if type(max_source_bytes) is not int or max_source_bytes <= 0:
        raise ValueError("max_source_bytes must be a positive non-boolean integer")
    inventory = scan_repository(root)
    graph = CodeGraph()
    outcomes = []
    sites: list[CallSite] = []
    routes: list[HttpRouteObservation] = []
    pre_handlers: list[PreHandlerObservation] = []
    prefixes: list[RouterPrefixObservation] = []
    mounts: list[RouterMountObservation] = []
    tests: list[TestObservation] = []
    for file in inventory.supported_files:
        (
            summary,
            local,
            calls,
            observations,
            pre_observations,
            prefix_observations,
            mount_observations,
            test_observations,
        ) = _analyze_file(root, file, max_source_bytes)
        if local is not None:
            try:
                for entity in local.entities():
                    graph.add_entity(entity)
                for relationship in local.relationships():
                    graph.add_relationship(relationship)
            except GraphError as error:
                raise RepositoryIndexInvariantError(f"graph collision while merging {file.path}") from error
        outcomes.append(summary)
        sites.extend(calls)
        routes.extend(observations)
        pre_handlers.extend(pre_observations)
        prefixes.extend(prefix_observations)
        mounts.extend(mount_observations)
        tests.extend(test_observations)
    try:
        return RepositoryIndexResult(
            inventory,
            graph,
            tuple(outcomes),
            tuple(sites),
            tuple(routes),
            tuple(pre_handlers),
            tuple(prefixes),
            tuple(mounts),
            tuple(tests),
        )
    except (TypeError, ValueError) as error:
        raise RepositoryIndexInvariantError("repository summary does not match merged graph") from error
