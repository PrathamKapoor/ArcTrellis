"""Offline command-line interface over the orchestration API.

This is an adapter, not an engine. Every subcommand builds the same validated
QueryRequest and calls the same run_query, so the CLI cannot answer differently
from the programmatic contract. Nothing here executes, imports or installs target
repository code, evaluates target configuration, connects to a database or makes
an outbound network request (D-146).
"""

from __future__ import annotations

import argparse
import contextlib
import json
import sys
from collections.abc import Sequence
from typing import NoReturn, TextIO

from arctrellis.core import EntityKind
from arctrellis.ingestion import IngestionError
from arctrellis.orchestration import (
    DATABASE_OPERATION_KINDS,
    AnalysisPipelineError,
    AnalysisSnapshot,
    BundleStatus,
    EvidenceBundle,
    InvalidQueryLimitError,
    InvalidQueryRequestError,
    OrchestrationError,
    QueryIntent,
    QueryRequest,
    SelectionStatus,
    UnsupportedIntentError,
    analyze_repository,
    intent_spec,
    run_query,
)
from arctrellis.parsing.source import DEFAULT_MAX_SOURCE_BYTES

from .errors import (
    EXIT_SUCCESS,
    EXIT_UNSUPPORTED,
    CliAmbiguityError,
    CliAnalysisError,
    CliError,
    CliExplanation,
    CliUnsupportedError,
    CliUsageError,
)
from .render import render_bundle, render_snapshot

PROGRAM = "arctrellis"
LANGUAGES = ("python", "javascript", "typescript")
OPERATION_KINDS = ("read", "write", "delete")

#: CLI spelling -> structured intent. Dashes keep the command line readable while
#: the enum keeps its exact uppercase diagnostic name.
INTENT_ALIASES: dict[str, QueryIntent] = {
    "search-entities": QueryIntent.SEARCH_ENTITIES,
    "list-endpoints": QueryIntent.LIST_ENDPOINTS,
    "list-database-callers": QueryIntent.LIST_DATABASE_CALLERS,
    "trace-endpoint-to-database": QueryIntent.TRACE_ENDPOINT_TO_DATABASE,
    "trace-callable-to-database": QueryIntent.TRACE_CALLABLE_TO_DATABASE,
    "direct-database-operations": QueryIntent.DIRECT_DATABASE_OPERATIONS,
    "find-direct-tests": QueryIntent.FIND_DIRECT_TESTS,
    "find-callers": QueryIntent.FIND_CALLERS,
    "find-affected-endpoints": QueryIntent.FIND_AFFECTED_ENDPOINTS,
}

ENTITY_KIND_ALIASES: dict[str, EntityKind] = {kind.value.casefold(): kind for kind in EntityKind}
ENTITY_KIND_ALIASES.update(
    {
        "api-endpoint": EntityKind.API_ENDPOINT,
        "database-operation": EntityKind.DATABASE_OPERATION,
    }
)

EXIT_POLICY = (
    "exit codes: 0 success, 2 invalid arguments or unresolvable request, "
    "3 ambiguous entity selection, 4 analysis failure, 5 unsupported operation"
)

#: Ergonomic subcommands fix their own intent so a wrapper cannot drift from the
#: structured request it is meant to express.
COMMAND_INTENTS: dict[str, QueryIntent] = {
    "endpoints": QueryIntent.LIST_ENDPOINTS,
    "database": QueryIntent.LIST_DATABASE_CALLERS,
    "trace": QueryIntent.TRACE_ENDPOINT_TO_DATABASE,
    "impact": QueryIntent.FIND_AFFECTED_ENDPOINTS,
    "tests": QueryIntent.FIND_DIRECT_TESTS,
}


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog=PROGRAM,
        description="Prove how a local repository works from static structural evidence.",
        epilog=EXIT_POLICY,
    )
    parser.add_argument("--version", action="version", version=f"{PROGRAM} 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze = subparsers.add_parser(
        "analyze",
        help="analyze one repository and print its structural inventory",
        description="Analyze a local repository and print measured counts and completeness.",
    )
    _add_root(analyze)
    analyze.add_argument(
        "--max-source-bytes",
        type=int,
        default=DEFAULT_MAX_SOURCE_BYTES,
        metavar="N",
        help="per-file read bound in bytes (default: %(default)s)",
    )
    _add_json(analyze)

    search = subparsers.add_parser(
        "search",
        help="rank canonical entities lexically without selecting one",
        description=(
            "Rank canonical entities for a query. Results are candidates only: "
            "a lexical score is never entity identity."
        ),
    )
    _add_root(search)
    search.add_argument("text", metavar="QUERY", help="retrieval text, not a natural-language intent")
    search.add_argument("--limit", type=int, default=25, metavar="N", help="maximum candidates (default: %(default)s)")
    search.add_argument("--kind", metavar="KIND", help="restrict to one entity kind, e.g. class or api-endpoint")
    search.add_argument("--language", metavar="LANG", help="restrict to python, javascript or typescript")
    search.add_argument("--path-prefix", metavar="PREFIX", help="restrict to a repository-relative path prefix")
    search.add_argument("--framework", metavar="NAME", help="restrict to one detected framework, e.g. fastapi")
    search.add_argument(
        "--context",
        action="store_true",
        help="enable the bounded one-hop graph-context boost (off by default)",
    )
    _add_json(search)

    query = subparsers.add_parser(
        "query",
        help="run one structured intent and print its evidence bundle",
        description=(
            "Execute one structured intent. Exactly one selector form may be supplied: "
            "--entity-id, --qualified-name, --method with --path, or TEXT for search-entities."
        ),
        epilog="example: arctrellis query . --intent trace-endpoint-to-database --method POST --path /payments",
    )
    _add_root(query)
    query.add_argument("text", nargs="?", metavar="TEXT", help="retrieval text for --intent search-entities")
    query.add_argument("--intent", required=True, metavar="INTENT", help=_intent_help())
    query.add_argument("--entity-id", metavar="ID", help="exact canonical entity ID")
    query.add_argument("--qualified-name", metavar="NAME", help="exact canonical qualified name")
    query.add_argument("--method", metavar="METHOD", help="uppercase HTTP method, with --path")
    query.add_argument("--path", metavar="ROUTE", help="exact route path, with --method")
    query.add_argument("--kind", metavar="KIND", help="constrain the selected entity kind")
    query.add_argument("--language", metavar="LANG", help="constrain the selected entity language")
    query.add_argument("--path-prefix", metavar="PREFIX", help="constrain the selected entity path prefix")
    query.add_argument("--framework", metavar="NAME", help="constrain or filter by framework")
    query.add_argument(
        "--scope",
        choices=("local", "declared", "effective", "application"),
        metavar="SCOPE",
        help="endpoint scope filter or constraint",
    )
    query.add_argument(
        "--operations",
        metavar="KINDS",
        help="comma-separated database operation kinds: read, write, delete",
    )
    query.add_argument("--transitive", action="store_true", help="transitive callers for find-callers")
    query.add_argument(
        "--include-graph-context",
        action="store_true",
        help="bounded one-hop context for search-entities",
    )
    _add_limit(query)
    query.add_argument("--max-depth", type=int, default=12, metavar="N", help="traversal depth (default: %(default)s)")
    query.add_argument(
        "--max-expansions", type=int, default=10000, metavar="N", help="traversal budget (default: %(default)s)"
    )
    _add_json(query)

    endpoints = subparsers.add_parser(
        "endpoints",
        help="list canonical endpoint registrations",
        description="List endpoint registrations from canonical metadata.",
    )
    _add_root(endpoints)
    endpoints.add_argument("--method", metavar="METHOD", help="filter by uppercase HTTP method")
    endpoints.add_argument("--path", metavar="ROUTE", help="filter by exact route path")
    endpoints.add_argument("--framework", metavar="NAME", help="filter by detected framework")
    endpoints.add_argument(
        "--scope",
        choices=("local", "declared", "effective", "application"),
        metavar="SCOPE",
        help="filter by endpoint scope",
    )
    _add_limit(endpoints)
    _add_json(endpoints)

    database = subparsers.add_parser(
        "database",
        help="list direct database-operation callers",
        description="List functions and methods that directly own a database operation.",
    )
    _add_root(database)
    database.add_argument("--operations", metavar="KINDS", help="comma-separated: read, write, delete")
    _add_limit(database)
    _add_json(database)

    trace = subparsers.add_parser(
        "trace",
        help="trace one endpoint to its database operations",
        description="Trace one canonical endpoint registration to its database operations.",
    )
    _add_root(trace)
    trace.add_argument("--entity-id", metavar="ID", help="exact canonical endpoint ID")
    trace.add_argument("--method", metavar="METHOD", help="uppercase HTTP method, with --path")
    trace.add_argument("--path", metavar="ROUTE", help="exact route path, with --method")
    trace.add_argument("--scope", choices=("local", "declared", "effective", "application"), metavar="SCOPE")
    _add_limit(trace)
    trace.add_argument("--max-depth", type=int, default=12, metavar="N", help="traversal depth (default: %(default)s)")
    trace.add_argument(
        "--max-expansions", type=int, default=10000, metavar="N", help="traversal budget (default: %(default)s)"
    )
    _add_json(trace)

    for name, intent, help_text in (
        ("impact", QueryIntent.FIND_AFFECTED_ENDPOINTS, "candidate endpoints affected by a callable"),
        ("tests", QueryIntent.FIND_DIRECT_TESTS, "direct static tests for a callable"),
    ):
        wrapper = subparsers.add_parser(name, help=help_text, description=help_text)
        _add_root(wrapper)
        wrapper.add_argument("--entity-id", metavar="ID", help="exact canonical callable ID")
        wrapper.add_argument("--qualified-name", metavar="NAME", help="exact canonical qualified name")
        _add_limit(wrapper)
        wrapper.add_argument(
            "--max-depth", type=int, default=12, metavar="N", help="traversal depth (default: %(default)s)"
        )
        wrapper.add_argument(
            "--max-expansions", type=int, default=10000, metavar="N", help="traversal budget (default: %(default)s)"
        )
        _add_json(wrapper)
        del intent

    return parser


def _intent_help() -> str:
    return "one of: " + ", ".join(sorted(INTENT_ALIASES))


def _add_root(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "root",
        metavar="ROOT",
        help="local repository directory; never executed, imported or installed",
    )


def _add_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--json",
        action="store_true",
        help="write one JSON document to stdout; all diagnostics go to stderr",
    )


def _add_limit(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--limit",
        type=int,
        default=25,
        metavar="N",
        help=("candidate limit for a retrieval intent, path limit for a traversal intent (default: %(default)s)"),
    )


def _fail(message: str) -> NoReturn:
    raise CliUsageError(message)


def _entity_kind(value: str | None) -> EntityKind | None:
    if value is None:
        return None
    kind = ENTITY_KIND_ALIASES.get(value.casefold().replace("_", "-"))
    if kind is None:
        _fail(f"unknown entity kind {value!r}; expected one of {', '.join(sorted(ENTITY_KIND_ALIASES))}")
    return kind


def _language(value: str | None) -> str | None:
    if value is None:
        return None
    if value.casefold() not in LANGUAGES:
        _fail(f"unknown language {value!r}; expected one of {', '.join(LANGUAGES)}")
    return value.casefold()


def _operations(value: str | None) -> frozenset[str]:
    if value is None:
        return DATABASE_OPERATION_KINDS
    requested = frozenset(item.strip().casefold() for item in value.split(",") if item.strip())
    if not requested or not requested <= set(OPERATION_KINDS):
        _fail(f"unknown operation kinds {value!r}; expected a nonempty subset of {', '.join(OPERATION_KINDS)}")
    return requested


def _intent(value: str) -> QueryIntent:
    intent = INTENT_ALIASES.get(value.casefold().replace("_", "-"))
    if intent is None:
        raise CliUnsupportedError(f"unsupported intent {value!r}; expected one of {', '.join(sorted(INTENT_ALIASES))}")
    return intent


def _request(args: argparse.Namespace) -> QueryRequest:
    """Build one validated request from parsed arguments, or fail with exit code 2.

    ``--limit`` means whichever budget the chosen intent actually consumes. This
    mirrors the per-intent option contract instead of inventing CLI-only meaning,
    so an impossible combination is rejected by the same rule the library applies.
    An ergonomic wrapper fixes its own intent, so it cannot drift from the
    structured request it expresses.
    """
    command = args.command
    declared = getattr(args, "intent", None)
    if declared is None:
        intent = COMMAND_INTENTS.get(command)
        if intent is None:
            raise CliUnsupportedError(f"no intent is associated with the {command!r} command")
    else:
        intent = _intent(declared)
    spec = intent_spec(intent)
    method: str | None = getattr(args, "method", None)
    route: str | None = getattr(args, "path", None)
    # A half-specified HTTP pair is only wrong when the pair is a selector. For an
    # inventory the pair is a filter, and QueryRequest already knows which one the
    # intent means, so the CLI defers to that single rule instead of duplicating it.
    limit = getattr(args, "limit", 25)
    search_text = getattr(args, "text", None) if intent is QueryIntent.SEARCH_ENTITIES else None
    if intent is not QueryIntent.SEARCH_ENTITIES and getattr(args, "text", None) is not None:
        _fail("TEXT is only valid with --intent search-entities")
    try:
        return QueryRequest(
            intent=intent,
            entity_id=getattr(args, "entity_id", None),
            qualified_name=getattr(args, "qualified_name", None),
            http_method=method.upper() if method is not None else None,
            route_path=route,
            search_text=search_text,
            entity_kind=_entity_kind(getattr(args, "kind", None)),
            language=_language(getattr(args, "language", None)),
            path_prefix=getattr(args, "path_prefix", None),
            framework=getattr(args, "framework", None),
            endpoint_scope=getattr(args, "scope", None),
            operation_kinds=_operations(getattr(args, "operations", None)),
            include_graph_context=bool(getattr(args, "include_graph_context", False)),
            transitive_callers=bool(getattr(args, "transitive", False)),
            top_k=limit if spec.uses_search_limits else 25,
            max_depth=getattr(args, "max_depth", 12),
            max_paths=limit if spec.uses_path_limits else 25,
            max_expansions=getattr(args, "max_expansions", 10000),
        )
    except (InvalidQueryRequestError, InvalidQueryLimitError, UnsupportedIntentError) as error:
        raise CliUsageError(str(error)) from error


def _analyze(args: argparse.Namespace) -> AnalysisSnapshot:
    """Analyze the target root through the existing safe pipeline.

    Discovery and permission failures keep their own typed errors and are reported
    as analysis failures with exit code 4; nothing is executed in the target.
    """
    try:
        return analyze_repository(
            args.root,
            max_source_bytes=getattr(args, "max_source_bytes", DEFAULT_MAX_SOURCE_BYTES),
        )
    except IngestionError as error:
        raise CliAnalysisError(f"{type(error).__name__}: {error}") from error
    except AnalysisPipelineError as error:
        raise CliAnalysisError(f"{type(error).__name__}: {error}") from error
    except OrchestrationError as error:
        raise CliAnalysisError(f"{type(error).__name__}: {error}") from error
    except (OSError, ValueError, TypeError) as error:
        raise CliAnalysisError(f"{type(error).__name__}: {error}") from error


def _explain_selection(bundle: EvidenceBundle, stderr: TextIO) -> None:
    """Report ambiguity and non-resolution on stderr, never on stdout."""
    selection = bundle.selection
    if selection.status is SelectionStatus.AMBIGUOUS:
        print(f"ambiguous selection: {selection.reason}", file=stderr)
        for index, candidate in enumerate(selection.candidates, start=1):
            print(
                f"  {index}. {candidate.entity_id}  {candidate.entity_kind.value} "
                f"{candidate.name} [{candidate.repository_relative_path or '<no path>'}]",
                file=stderr,
            )
        print("supply --entity-id with one of the IDs above to continue", file=stderr)
    elif selection.status is SelectionStatus.NOT_FOUND:
        print(f"not found: {selection.reason}", file=stderr)
    elif selection.status is SelectionStatus.INVALID:
        print(f"invalid selection: {selection.reason}", file=stderr)
    if bundle.status is BundleStatus.NO_KNOWN_PATH:
        print(
            "no known structural path: this reports absent evidence, not proof that none exists",
            file=stderr,
        )


def _emit(payload: dict[str, object], lines: list[str], as_json: bool, stdout: TextIO) -> None:
    if as_json:
        json.dump(payload, stdout, indent=2, sort_keys=True)
        stdout.write("\n")
    else:
        for line in lines:
            print(line, file=stdout)


def _search_request(args: argparse.Namespace) -> QueryRequest:
    try:
        return QueryRequest(
            intent=QueryIntent.SEARCH_ENTITIES,
            search_text=args.text,
            entity_kind=_entity_kind(args.kind),
            language=_language(args.language),
            path_prefix=args.path_prefix,
            framework=args.framework,
            include_graph_context=args.context,
            top_k=args.limit,
        )
    except (InvalidQueryRequestError, InvalidQueryLimitError, UnsupportedIntentError) as error:
        raise CliUsageError(str(error)) from error


def _run(args: argparse.Namespace, stdout: TextIO, stderr: TextIO) -> int:
    if args.command == "analyze":
        snapshot = _analyze(args)
        _emit(snapshot.to_dict(), render_snapshot(snapshot), args.json, stdout)
        return EXIT_SUCCESS

    snapshot = _analyze(args)
    request = _search_request(args) if args.command == "search" else _request(args)
    bundle = run_query(snapshot, request)
    _emit(bundle.to_dict(), render_bundle(bundle), args.json, stdout)
    _explain_selection(bundle, stderr)
    if bundle.selection.status is SelectionStatus.AMBIGUOUS:
        return CliAmbiguityError.exit_code
    if bundle.status in (BundleStatus.NOT_FOUND_SOURCE, BundleStatus.INVALID_SOURCE):
        return CliExplanation.exit_code
    return EXIT_SUCCESS


def main(argv: Sequence[str] | None = None, stdout: TextIO | None = None, stderr: TextIO | None = None) -> int:
    """Run the CLI and return the documented exit status.

    ``argv``, ``stdout`` and ``stderr`` exist so tests can drive the exact same
    code path the console entry point uses without touching the real streams.
    """
    out = sys.stdout if stdout is None else stdout
    err = sys.stderr if stderr is None else stderr
    parser = _parser()
    try:
        # argparse writes help to sys.stdout and argument errors to sys.stderr by
        # convention. Redirecting only around parsing keeps that convention while
        # still honoring the streams a caller injected.
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            args = parser.parse_args(list(argv) if argv is not None else None)
        return _run(args, out, err)
    except CliError as error:
        print(f"{PROGRAM}: error: {error.message}", file=err)
        return error.exit_code
    except KeyboardInterrupt:
        print(f"{PROGRAM}: interrupted", file=err)
        return EXIT_UNSUPPORTED
    except SystemExit:
        raise
    except Exception as error:  # noqa: BLE001 - the CLI boundary must never leak a traceback
        # A command-line tool must not print an internal traceback or pretend to
        # succeed. The type name is diagnostic; the message is bounded and never
        # includes target source, credentials or an environment dump.
        print(
            f"{PROGRAM}: internal error: {type(error).__name__}: {error}",
            file=err,
        )
        return EXIT_UNSUPPORTED


def entry_point() -> None:
    """Console-script target: exit with the CLI status."""
    raise SystemExit(main())
