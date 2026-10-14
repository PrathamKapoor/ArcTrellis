# ArcTrellis Handoff

## 1. Current Phase

Phases 2.4, 2.5 and 2.6 complete and verified: typed structural query orchestration, an installed
offline CLI, and a loopback-only read-only HTTP API, plus authorized scale hardening. Repository
C:/Projects/ArcTrellis, Python 3.13.14, required Git identity, no remotes, nothing pushed. There is
no further authorized phase; the next step is a deliberate product phase that has not begun.

## 2. Work Completed

The session read the three root documents and inspected the real graph, core, indexing, query,
retrieval, CLI-independent public APIs and tests, then verified the reported 640-test baseline
before changing anything.

Phase 2.4 added `arctrellis.orchestration`: a nine-member `QueryIntent` vocabulary, an immutable
`QueryRequest` validated at construction against a per-intent `IntentSpec`, deterministic pure-data
`QueryPlan` values, conservative canonical selection with six explicit statuses, structural
execution that dispatches to the existing `arctrellis.query` functions, an `EvidenceBundle` with
`schema_version=1`, and `analyze_repository(root)` producing an `AnalysisSnapshot` whose retrieval
index is asserted to correspond one-to-one with the final graph.

Phase 2.5 added `arctrellis.cli`: an argparse adapter over the same `QueryRequest` and `run_query`,
an installed `arctrellis` console entry point, analyze/search/query plus the endpoints, database,
trace, impact and tests wrappers, text and JSON output with a strict stdout/stderr split, and a
fixed exit-code policy.

Phase 2.6 added `arctrellis.api` on the standard library with no new dependency: five versioned
read-only routes, loopback-enforced binding, a startup-fixed repository root, bounded request
bodies, rejected unknown fields, and a 409 that carries the full bundle when selection is
ambiguous. `arctrellis serve` makes it reachable from the command line.

Hardening added `tests/scale`: a deterministic generator producing repositories up to 3350
entities that are simultaneously name-ambiguous, cyclic, high-degree and endpoint-ambiguous, with
sixteen contract tests and a benchmark reporter that asserts no wall-clock threshold. The
architecture audit now proves no network, process or dynamic-execution primitive exists anywhere in
the package, and that only `api/app.py` and `api/server.py` bind a socket.

Public `arctrellis.orchestration` API: `analyze_repository`, `AnalysisSnapshot`, `AnalysisCounts`,
`QueryIntent`, `QueryRequest`, `IntentSpec`, `intent_spec`, `SelectorForm`, `PlanStep`, `QueryPlan`,
`build_plan`, `plan_query`, `SelectionStatus`, `SelectionBasis`, `SelectionResult`,
`EntityCandidate`, `select_canonical_entity`, `SearchCandidates`, `search_candidates`,
`ExecutionOutcome`, `execute_plan`, `EvidenceBundle`, `BundleStatus`, `EntitySummary`,
`EvidenceDetail`, `RelationshipEvidence`, `PathEvidence`, `build_bundle`, `entity_candidate`,
`entity_summary`, `path_evidence`, `run_query`, `SCHEMA_VERSION`, `CALLABLE_KINDS`,
`DATABASE_OPERATION_KINDS`, `ENDPOINT_SCOPES` and the error hierarchy.

Public `arctrellis.cli` API: `main`, `entry_point`, `INTENT_ALIASES`, `EXIT_SUCCESS`, `EXIT_USAGE`,
`EXIT_AMBIGUOUS`, `EXIT_ANALYSIS_FAILURE`, `EXIT_UNSUPPORTED` and the CLI error types.

Public `arctrellis.api` API: `ApiApplication`, `ApiResponse`, `AnalysisService`, `create_server`,
`is_loopback`, `server_banner`, `decode_payload`, `encode_payload`, `route_table`, `API_PREFIX`,
`API_VERSION`, `INTENT_NAMES`, `MAX_REQUEST_BYTES`, `ALLOWED_HOSTS`, `DEFAULT_HOST`,
`DEFAULT_PORT`, `UnsafeBindError` and the typed API errors.

## 3. Files Changed

- src/arctrellis/orchestration/{__init__,errors,models,planning,selection,execution,evidence,pipeline,runner}.py: the Phase 2.4 package.
- src/arctrellis/cli/{__init__,errors,main,render}.py: the Phase 2.5 adapter and renderer.
- src/arctrellis/api/{__init__,errors,service,app,server}.py: the Phase 2.6 read-only interface.
- pyproject.toml: the `arctrellis` console entry point; no dependency added.
- tests/orchestration/{__init__,repository,test_requests,test_plans,test_selection,test_execution,test_pipeline,test_end_to_end}.py: 134 tests.
- tests/cli/{__init__,test_cli,test_entry_point,smoke}.py: 66 tests and the full-product smoke.
- tests/api/{__init__,test_api,test_live_server,smoke}.py: 75 tests and the API smoke.
- tests/scale/{__init__,fixtures,test_scale,bench}.py: 16 contract tests and measured reporting.
- tests/test_architecture.py: added the no-network/no-process/no-eval audit and socket localisation.
- README.md, decisions.md, flow.md, handoff.md: capabilities, decisions, real call flow, state.

## 4. Current Architecture / State

The analysis lifecycle is unchanged and now has one programmatic entry point.

```text
analyze_repository(root)
  index_repository -> resolve_imports -> resolve_calls -> resolve_http_endpoints
      -> resolve_framework_flow -> analyze_tests -> materialize_database_graph
      -> build_search_index(final graph) -> AnalysisSnapshot
      __post_init__ asserts retrieval documents == graph entities, one to one

run_query(snapshot, request)
  build_plan -> selection -> execution (one existing query function) -> EvidenceBundle
```

Nine intents, each backed by a real query function: `SEARCH_ENTITIES`, `LIST_ENDPOINTS`,
`LIST_DATABASE_CALLERS`, `TRACE_ENDPOINT_TO_DATABASE`, `TRACE_CALLABLE_TO_DATABASE`,
`DIRECT_DATABASE_OPERATIONS`, `FIND_DIRECT_TESTS`, `FIND_CALLERS`, `FIND_AFFECTED_ENDPOINTS`. No
natural-language inference exists; `search_text` is retrieval input only.

Validation is a contract, not a suggestion. Selector forms are mutually exclusive. An option the
chosen intent cannot consume is rejected rather than ignored. `top_k` and `max_examined_postings`
are retrieval budgets; `max_paths`, `max_depth` and `max_expansions` are traversal budgets;
`transitive_callers` belongs to `FIND_CALLERS` alone and `include_graph_context` to `SEARCH_ENTITIES`
alone. `framework` and `endpoint_scope` are list filters for an inventory and constraints on the
selected entity otherwise. All limits are positive non-boolean integers.

Selection never guesses. An exact canonical ID resolves after its kind is checked; an exact
qualified name or `METHOD path` resolves only when exactly one eligible entity matches, otherwise
`AMBIGUOUS` with the full candidate set, bounded at 25 and reporting truncation. A lexical query
returns `CANDIDATES` and names no entity. `entity_kind`, `language`, `path_prefix`, `framework` and
`endpoint_scope` narrow a caller's own selector but never choose.

Bundles preserve stored facts: relationship ID, kind, direction, confidence classification, numeric
score, original Evidence IDs, source locations and analysis methods. Confidence uses the existing
weakest-edge contract and is never multiplied into a probability. Retrieval relevance never
changes a stored CALLS, EXPOSES, database or TESTS confidence. Entity projection omits declaration
signatures and all metadata outside a nine-key allowlist. Serialization is JSON primitives only
with no timestamp, absolute path, source byte or traceback.

The CLI and the API are adapters over the same two functions. `run_query` returns the identical
bundle for an identical request; the CLI renders it as text or JSON, and the API returns the same
JSON document. The API additionally refuses to guess: an ambiguous selection is 409 with the full
bundle attached, so the caller gets the candidates instead of a silent wrong answer.

`AnalysisSnapshot` is a frozen record over the ordinary mutable `CodeGraph`; it does not freeze the
graph, and no mutation path is exposed in the public API.

## 5. Decisions Made

D-128 to D-141 are the Phase 2.3 retrieval decisions and remain unchanged. This session added:

D-142: validate structured query requests against a per-intent option contract.
D-143: resolve canonical entities exactly and never select from a lexical ranking.
D-144: project stored relationships into bundles without adding content or certainty.
D-145: build the retrieval snapshot from the final analysis graph and assert the projection.
D-146: serve the offline CLI as a thin adapter with a documented exit-code policy.
D-147: keep stdout machine-parseable in JSON mode and put every diagnostic on stderr.
D-148: serve the read-only local API from the standard library on an enforced loopback socket.
D-149: bound behaviour with a synthetic repository at scale, and report measurements without asserting them.

Commit references for D-142 to D-149 are finalized in a later documentation commit; no history is
rewritten.

## 6. Requirements and Constraints

Local only: no GitHub API, remote changes, push, upload, publication, packages or releases. All
commits are authored and committed solely by PrathamKapoor <prathamkapoor027@gmail.com>. No
attribution lines, no secrets, no paper/research/tex files. Target repositories are untrusted: no
execution, imports, test runs, Node, dependency installation, database connections or SQL. No
outbound network request. No source symlink is followed intentionally. The HTTP interface is
loopback-only and accepts no filesystem root from a request.

No runtime dependency was added in this session: the CLI is argparse and the API is http.server.
Ruff and mypy configuration and every existing parsing, semantic, query and retrieval algorithm are
unchanged. The architecture audit now proves that no module imports a socket, an HTTP client, a
process-spawning module or a deserializer, and that no module calls `eval`, `exec`, `compile` or
`__import__`.

## 7. Testing and Verification

Project interpreter .venv/Scripts/python.exe, Python 3.13.14. Baseline 640; Phase 2.4 adds 134,
Phase 2.5 adds 66, Phase 2.6 adds 75, scale hardening adds 16, for 933 tests OK/skipped 7. The
seven skips are the pre-existing six Windows symlink-privilege cases and the absent FIFO API; no
orchestration, CLI, API or scale test is skipped.

Commands (prefix `.venv\Scripts\python.exe`):
- `-m unittest tests.orchestration.test_requests -q`: 29 tests OK.
- `-m unittest tests.orchestration.test_plans -q`: 9 tests OK.
- `-m unittest tests.orchestration.test_selection -q`: 29 tests OK.
- `-m unittest tests.orchestration.test_execution -q`: 39 tests OK.
- `-m unittest tests.orchestration.test_pipeline -q`: 20 tests OK.
- `-m unittest tests.orchestration.test_end_to_end -q`: 8 tests OK.
- `-m unittest discover -s tests/orchestration -t . -q`: 134 tests OK.
- `-m unittest discover -s tests/cli -t . -q`: 66 tests OK.
- `-m unittest discover -s tests/api -t . -q`: 75 tests OK.
- `-m unittest discover -s tests/scale -t . -q`: 16 tests OK.
- `-m unittest discover -s tests -q`: 933 tests OK/skipped 7.
- `-m ruff check src tests`: All checks passed.
- `-m ruff format --check src tests`: 196 files already formatted.
- `-m mypy src/arctrellis`: 104 source files, no issues.
- `-m compileall -q src`: exit 0.
- `-m pip check`: No broken requirements found.
- `-m unittest tests.test_architecture -q`: 5 tests OK.
- `-m unittest discover -s tests/retrieval -t . -q`: 192 tests OK.
- `-m tests.retrieval.smoke`: Deterministic True, Graph unchanged True, Snapshot identity stable True.
- `-m tests.cli.smoke`: 13 requests, 7 evidence bundles, 1 inventory, 2 search, 1 no-known-path, 1 truncated, 13 JSON-serializable, CLI/API status, selected entity and relationship IDs all agree, deterministic rerun True, ambiguous exit status 3, graph unchanged.
- `-m tests.api.smoke`: health 200, summary 200, endpoints 200, search 200, exact query 200, ambiguous 409 with the full bundle, unknown entity 404, unsupported intent 501, oversized body 413, unknown route 404, API payload byte-equal to the orchestration bundle, repeated request identical.
- `-m tests.scale.bench`: measured, not asserted.

Measured mixed-fixture facts: 8 supported files, all complete, 76 entities, 98 relationships, 11
endpoints, 3 tests, 8 database operations, 76 retrieval documents, 116 terms, completeness
complete, snapshot `f277737a-7b4a-5e6e-af7e-a23490822c93`.

Verified evidence example: `POST /payments [app.py:5]` EXPOSES `createPaymentRoute [app.py:6]`
(PROVEN 1.0, `fastapi_decorated_handler app.py:5`) CALLS `createPayment [payments.py:4]`
(LIKELY 0.75, `python_imported_symbol_call_resolution app.py:7`) WRITES_DATABASE
`sqlalchemy:Payment.execute@134 [payments.py:5]` (LIKELY 0.85, `sqlalchemy_execute_insert
payments.py:5`). Ambiguous `POST /payments` returns exit 3 / HTTP 409 with two candidates;
`GET /reports` and `POST /ghost` and `POST /fake` return `NO_KNOWN_PATH`.

CLI exit codes measured from the installed script: analyze 0, search 0, exact-ID trace 0, ambiguous
3, unknown entity ID 2, unsupported intent 5, missing repository 4, invalid limit 2.

Measured scale profiles: small 13 files/7296 bytes/170 entities/275 relationships/90 terms/0.5522 s
analyze/0.0021 s search; medium 63/53689/1140/1965/264/2.3700 s/0.0267 s; large
153/164678/3350/5935/523/10.9255 s/0.1126 s. Observations on one machine, not guarantees.

Defects found and fixed during this session, each with a regression test: `ExecutionOutcome`
asserted that a nonempty path list implies a path result, so any query legitimately returning zero
paths raised an invariant error; a draft reported a lexical search as `RESOLVED` while naming no
entity, which the `SelectionResult` contract rejects, so `CANDIDATES` and `NOT_REQUIRED` were added
as honest statuses; `QueryRequest` compared a supplied option against the wrong limit family, so
`top_k` was rejected for `SEARCH_ENTITIES`; the endpoint option pair was forced together even for an
inventory filter and was rejected as a selector on `LIST_ENDPOINTS`, because the filter form had no
representation, which `ENDPOINT_FILTER` fixed; graph-wide intents never executed their structural
query because execution required a selected entity; an inventory with entities but no evidence
paths violated the bundle contract, which `INVENTORY` fixed; `build_plan` reported `evidence_paths`
for endpoint inventories because the output ternary was ordered wrongly; the CLI read
`max_source_bytes` on subcommands that do not define it; the CLI treated a half-specified HTTP pair
as an error even for a filter; `InvalidRepositoryPathError` was not caught and surfaced as an
internal error instead of exit 4; argparse help bypassed the injected streams until a redirect was
added; `_endpoint_filters` raised a bare `ApiError` and returned 500 for a bad query key; an empty
lexical search returned 404 because `NOT_FOUND` was mapped unconditionally; the scale fixture
generator joined multi-line blocks character by character. No existing test was disabled, no
tooling was weakened and no timing threshold was introduced.

## 8. Known Issues / Risks

A Python handler that calls a method through a bound instance variable (`service.createRefund()`)
produces no CALLS edge, because instance-attribute resolution is outside the current call-resolution
subset; the fixtures therefore route traced endpoints through imported module functions. This is an
existing Phase 1 limitation, not an orchestration defect, and it is why `POST /refunds` reports
`NO_KNOWN_PATH`.

Selection scans the snapshot's exact qualified-name and route lookups, which is exhaustive for exact
selectors, so a resolved selection never claims truncation; only the lexical path is bounded, at 25
candidates for an ambiguity report and by the posting budget for search. Public graph snapshots still
allocate and sort eagerly before any examination budget, so index construction remains bounded only
by corpus size. `analyze_repository` holds the final graph and the retrieval index in memory
together; no memory cap is claimed and analysis time grows faster than entity count because every
stage re-reads the graph. The default 25-seed budget still truncates graph-context expansion on the
retrieval fixture. Conceptual multiword queries are still matched by tokens only. The API has no
authentication and no refresh: it serves one startup snapshot and must never leave loopback. Static
resolution omissions, runtime binding limitations, revision-only non-repository-namespaced IDs and
native parser platform limits are unchanged.

## 9. Unfinished Work

No authorized phase is unfinished. Deliberately absent, and not started: a frontend or product
demonstration, authentication, multi-tenancy, persistence or an incremental index, natural-language
intent inference, embeddings or vector search, LLM-generated explanation, deployment, and any
remote or published surface.

## 10. Next Subphase

No next phase is authorized. The recommended next step is a deliberate product demonstration phase
— for example a local read-only viewer over the existing API, which needs no new backend capability
— but it must not begin without a new prompt. If that is declined, the highest-value engineering
work is an analysis cache with an explicit staleness contract, because analysis cost grows faster
than entity count and every CLI invocation currently rebuilds it.

## 11. Critical Context

The analysis engine establishes what source evidence supports; the explanation layer explains that
evidence. A lexical relevance score is not entity identity, not a probability, not a confidence and
not a runtime claim. A high BM25 score must never select a structural query target, over the CLI
(exit 3) or the API (409 with the bundle). A graph-context hit is a structural association over one
stored relationship, never proof of execution, order, success or deployment. TESTS context means
direct static test-call proof, never runtime coverage. A staged SQLAlchemy mutation and a
transaction control are canonical DATABASE_OPERATION facts but carry no read/write capability edge.
IMPORTS and DEFINES are never context and never execution. `NO_KNOWN_PATH` is never proof of
absence. A truncated result is a bounded discovered ranking, never an exhaustive one, and no result
proves repository completeness. Bundle IDs are canonical entity IDs; retrieving or naming an entity
does not trace it. The API and the CLI return the identical bundle for an identical request; a
difference between them would be a defect, not a transport difference.

## 12. Agent Instructions

Read root documents completely and inspect the actual public APIs and tests before changing
anything. Preserve decisions and history and continue D-numbering from D-150. Finalize only new
commit-reference fields in a later documentation commit; never globally replace historical prose.
Use the project interpreter and run the complete gates; never weaken strict tooling and never
invent measured output. Report measured numbers as observations with their environment, never as
guarantees, and never add a wall-clock assertion to a test. Validate file outcome counts before
interpreting empty semantics. Keep target input strictly as untrusted static data: no execution,
imports, test runs, Node, dependency installation, database connections, SQL or outbound network
access. Check author, committer and remotes at every boundary. Stop here: no push, no remote, no
publication, no deployment, no public binding.
