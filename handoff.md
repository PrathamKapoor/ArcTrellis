# ArcTrellis Handoff

## 1. Current Phase

Phase 2.4 (A/B/C/D) implementation and verification complete: typed structural query intents,
deterministic plans, conservative canonical entity selection, evidence bundles and full
repository analysis orchestration. Repository C:/Projects/ArcTrellis, Python 3.13.14, required Git
identity, no remotes. Next authorized work is Phase 2.5, the offline CLI.

## 2. Work Completed

Read the three root documents and the actual graph/core/indexing/query/retrieval contracts, then
verified the reported baseline of 640 tests OK/skipped 7 before changing anything.

Phase 2.4A added `arctrellis.orchestration` with a nine-member `QueryIntent` vocabulary, an
immutable `QueryRequest` validated in `__post_init__`, a per-intent `IntentSpec` table and pure
data `QueryPlan` values. Phase 2.4B added conservative canonical selection with explicit
`RESOLVED`/`AMBIGUOUS`/`NOT_FOUND`/`INVALID`/`CANDIDATES`/`NOT_REQUIRED` outcomes. Phase 2.4C
added structural execution that dispatches to the existing `arctrellis.query` functions and an
`EvidenceBundle` with `schema_version=1`. Phase 2.4D added `analyze_repository(root)` and the
`AnalysisSnapshot` that keeps the final graph and the retrieval index built from that same graph.

Public `arctrellis.orchestration` API: `analyze_repository`, `AnalysisSnapshot`, `AnalysisCounts`,
`QueryIntent`, `QueryRequest`, `IntentSpec`, `intent_spec`, `SelectorForm`, `PlanStep`,
`QueryPlan`, `build_plan`, `plan_query`, `SelectionStatus`, `SelectionBasis`, `SelectionResult`,
`EntityCandidate`, `select_canonical_entity`, `SearchCandidates`, `search_candidates`,
`ExecutionOutcome`, `execute_plan`, `EvidenceBundle`, `BundleStatus`, `EntitySummary`,
`EvidenceDetail`, `RelationshipEvidence`, `PathEvidence`, `build_bundle`, `entity_candidate`,
`entity_summary`, `path_evidence`, `run_query`, `SCHEMA_VERSION`, `CALLABLE_KINDS`,
`DATABASE_OPERATION_KINDS`, `ENDPOINT_SCOPES` and the orchestration error hierarchy.

Implementation committed `83f50a6`; documentation committed `f33fd43`. Commit-reference fields are
finalized in a later documentation commit; no history is rewritten.

## 3. Files Changed

- src/arctrellis/orchestration/__init__.py: deliberate public exports only.
- src/arctrellis/orchestration/errors.py: caller input, unavailable analysis, broken invariant.
- src/arctrellis/orchestration/models.py: intents, request validation, plans, selection and bundle models.
- src/arctrellis/orchestration/planning.py: deterministic request-to-plan translation.
- src/arctrellis/orchestration/selection.py: exact-ID, qualified-name, route and lexical selection.
- src/arctrellis/orchestration/execution.py: dispatch to the existing structural query engine.
- src/arctrellis/orchestration/evidence.py: bundle assembly with preserved Evidence and limitations.
- src/arctrellis/orchestration/pipeline.py: analyze_repository and the aligned AnalysisSnapshot.
- src/arctrellis/orchestration/runner.py: the single request execution order.
- tests/orchestration/repository.py: mixed Python/JS/TS fixtures plus every negative case.
- tests/orchestration/test_requests.py, test_plans.py: validation and plan contracts.
- tests/orchestration/test_selection.py: the fifteen canonical-selection cases.
- tests/orchestration/test_execution.py: trace reuse, evidence preservation, bundles, search.
- tests/orchestration/test_pipeline.py: analysis orchestration, partial analysis, reproducibility.
- tests/orchestration/test_end_to_end.py: the complete analyze-to-bundle workflow.
- README.md, decisions.md, flow.md, handoff.md: capabilities, decisions, real call flow, state.

## 4. Current Architecture / State

The analysis lifecycle is unchanged and now has one programmatic entry point.
`analyze_repository(root)` runs the verified dependency order

```text
index_repository -> resolve_imports -> resolve_calls -> resolve_http_endpoints
    -> resolve_framework_flow -> analyze_tests -> materialize_database_graph
    -> build_search_index(final graph) -> AnalysisSnapshot
```

and asserts that the retrieval documents correspond one-to-one with the final graph entities.
Lexical search and structural queries therefore always describe the same repository state.
Intermediate stage results are dropped when the call returns, so no `ParsedSource`, syntax tree or
source byte survives. `AnalysisSnapshot` is a frozen record over the ordinary mutable `CodeGraph`;
it does not freeze the graph, and no mutation path is exposed in the public API.

```text
run_query(snapshot, request)
 ├─ build_plan(request)        pure data: steps, source kinds, query name, limits, output type
 ├─ selection                  SEARCH_ENTITIES -> ranked CANDIDATES that name no entity
 │                             ENTITY_ID / QUALIFIED_NAME / ENDPOINT_METHOD_PATH -> exact
 │                             NONE -> NOT_REQUIRED (graph-wide inventory)
 ├─ execution                  exactly one existing query function, read only
 └─ build_bundle(...)          EvidenceBundle, JSON primitives, deterministic
```

Nine intents, each backed by a real query function: `SEARCH_ENTITIES` (`search_symbols`),
`LIST_ENDPOINTS` (`list_endpoints`), `LIST_DATABASE_CALLERS` (`list_direct_database_callers`),
`TRACE_ENDPOINT_TO_DATABASE`, `TRACE_CALLABLE_TO_DATABASE`, `DIRECT_DATABASE_OPERATIONS`,
`FIND_DIRECT_TESTS`, `FIND_CALLERS`, `FIND_AFFECTED_ENDPOINTS`. There is no natural-language
inference: `search_text` is retrieval input only and can never imply an architectural intent.

Validation is a contract, not a suggestion. Selector forms are mutually exclusive. An option the
chosen intent cannot consume is rejected with `UnsupportedIntentError` rather than silently
ignored: `top_k` and `max_examined_postings` are retrieval budgets, `max_paths`, `max_depth` and
`max_expansions` are traversal budgets, `transitive_callers` belongs to `FIND_CALLERS` alone and
`include_graph_context` belongs to `SEARCH_ENTITIES` alone. All limits are positive non-boolean
integers and `top_k` is capped at the retrieval cap.

Selection never guesses. An exact canonical entity ID resolves directly after its kind is checked;
an exact qualified name or `METHOD path` resolves only when exactly one eligible entity matches,
otherwise `AMBIGUOUS` with the full candidate set. `entity_kind`, `language`, `path_prefix`,
`framework` and `endpoint_scope` narrow a caller's own selector but never choose. A lexical query
returns `CANDIDATES` and names no entity, so a high BM25 score can never become a structural query
target. Snapshot construction indexes qualified names and routes exactly, so exact-match ambiguity
claims are exhaustive and never drawn from a truncated subset.

Bundles preserve stored facts. Every relationship keeps its original ID, kind, direction,
confidence classification, numeric score, original Evidence IDs, source locations and analysis
methods; confidence is summarized with the existing weakest-edge contract and never multiplied
into a probability. Retrieval relevance never changes a CALLS, EXPOSES, database or TESTS
confidence. Entity projection omits declaration signatures and all metadata outside a nine-key
allowlist, because a signature is source text. Serialization is JSON primitives only with no
timestamp, absolute path, source byte or traceback, so equal requests over equal snapshots
serialize identically.

## 5. Decisions Made

D-128: immutable canonical SearchDocument projections over allowlisted structural metadata.
D-129: NFKC-preserving-case tokenizer, acronym and digit boundaries, per-field bounds.
D-130: one deterministic build-time lexical snapshot with verified statistics and content id.
D-131: reuse the canonical AnalysisCompleteness vocabulary instead of a second enum.
D-132: standard BM25 plus a fixed exact-match ladder with exposed score components.
D-133: bounded one-hop graph context from real stored relationships only.
D-134: explicit field weighting for field-aware BM25; supersedes the D-130 raw-count lengths.
D-135: filter eligibility separated from candidate budgets, with honest truncation reporting.
D-136: one ranking entry point with kind-restricted delegating wrappers.
D-137: deterministic evaluation harness with independent judgments and standard metrics.
D-138: independent exact/substring baseline with regressions reported rather than hidden.
D-139: mixed-language retrieval repository, hard negatives and the end-to-end smoke.
D-140: stored projected field values truncated to the documented limit; supersedes part of D-128.
D-141: export the evaluation surface from the package entry point alongside search types.
D-142: validate structured query requests against a per-intent option contract.
D-143: resolve canonical entities exactly and never select from a lexical ranking.
D-144: project stored relationships into bundles without adding content or certainty.
D-145: build the retrieval snapshot from the final analysis graph and assert the projection.
References finalized in a later documentation commit; no history rewriting.

## 6. Requirements and Constraints

Local only: no GitHub API, remote changes, push, upload, publication, packages or releases. All
commits are authored and committed solely by PrathamKapoor <prathamkapoor027@gmail.com>. No
attribution lines, no secrets, no paper/research/tex files. No target execution, imports, test
runs, Node, dependency installation, database connections or SQL. Orchestration never rereads
source, synthesizes entities or relationships, invents Evidence, mutates evidence or confidence,
or runs analysis automatically. Retrieval relevance is never a confidence. Phase 2.5 may add an
argparse CLI and a console entry point in pyproject.toml, but no server, frontend, LLM,
embeddings, vector store, persistence, cache, worker or incremental update. No new runtime
dependency for the CLI; standard library only. Ruff and mypy configuration and every existing
parsing, semantic, query and retrieval algorithm stay unchanged.

## 7. Testing and Verification

Project interpreter .venv/Scripts/python.exe, Python 3.13.14. Baseline 640; Phase 2.4 adds 134
orchestration tests for 774 tests OK/skipped 7. Existing platform skips are the six Windows
symlink privilege cases and the absent FIFO API; no orchestration test is skipped. Every gate ran
targeted and full tests, Ruff lint and format, strict mypy, compileall, pip check and architecture
tests.

Commands (prefix `.venv\Scripts\python.exe`):
- `-m unittest tests.orchestration.test_requests -q`: 29 tests OK.
- `-m unittest tests.orchestration.test_plans -q`: 9 tests OK.
- `-m unittest tests.orchestration.test_selection -q`: 29 tests OK.
- `-m unittest tests.orchestration.test_execution -q`: 39 tests OK.
- `-m unittest tests.orchestration.test_pipeline -q`: 20 tests OK.
- `-m unittest tests.orchestration.test_end_to_end -q`: 8 tests OK.
- `-m unittest discover -s tests/orchestration -t . -q`: 134 tests OK.
- `-m unittest discover -s tests -q`: 774 tests OK/skipped 7.
- `-m ruff check src tests`: All checks passed.
- `-m ruff format --check src tests`: 175 files already formatted.
- `-m mypy src/arctrellis`: 95 source files, no issues.
- `-m compileall -q src`: exit 0.
- `-m pip check`: No broken requirements found.
- `-m unittest tests.test_architecture -q`: 3 tests OK.
- `-m unittest discover -s tests/retrieval -t . -q`: 192 tests OK.
- `-m tests.retrieval.smoke`: unchanged measured retrieval smoke output.

Measured orchestration facts on the mixed fixture: 74 entities, 94 relationships, 10 endpoints,
3 tests, 8 database operations, 74 retrieval documents, 114 terms, analysis completeness complete.
`POST /payments` in app.py resolves to one candidate and traces
`EXPOSES -> CALLS -> WRITES_DATABASE`; `GET /reports` and `POST /ghost` and `POST /fake` all return
`NO_KNOWN_PATH`; `POST /payments` as a method-plus-route selector returns `AMBIGUOUS_SOURCE` with
four registrations; `PaymentService` returns both the CLASS and the IMPORT as candidates and
selects neither; duplicate `js/dup.js::handler` qualified names return `AMBIGUOUS` with two
candidates.

Corrected failures during this phase: `ExecutionOutcome` asserted that a nonempty path list implies
a path result, so any query legitimately returning zero paths raised `OrchestrationInvariantError`;
a draft reported a lexical search as `RESOLVED` while naming no entity, which the `SelectionResult`
contract rejects, so `CANDIDATES` and `NOT_REQUIRED` were added as honest explicit statuses;
`QueryRequest` compared a supplied option against the wrong limit family, so `top_k` was rejected
for `SEARCH_ENTITIES` even though the intent declares it; the endpoint option pair was forced to be
supplied together even for an inventory filter, and the same pair was rejected as a selector on
`LIST_ENDPOINTS` because the filter form had no representation; `graph-wide` intents never executed
their structural query because execution required a selected entity; an inventory with entities but
no evidence paths violated the bundle contract, so `INVENTORY` was added; `build_plan` reported
`evidence_paths` for endpoint inventories because the output ternary was ordered wrongly. Fixture
expectations were corrected against actual canonical output rather than by changing production
behaviour. No existing test was disabled, no tooling was weakened and no timing threshold was
introduced.

## 8. Known Issues / Risks

A Python handler that calls a method through a bound instance variable
(`service.createRefund()`) produces no CALLS edge, because instance-attribute resolution is outside
the current call-resolution subset; the orchestration fixture therefore routes its traced endpoint
through an imported module function. This is an existing Phase 1 limitation, not an orchestration
defect, and it is the reason `POST /refunds` reports `NO_KNOWN_PATH`.

Selection scans the snapshot's exact qualified-name and route lookups, which is exhaustive for
exact selectors; only the lexical path is bounded by a posting budget. Public graph snapshots still
allocate and sort eagerly before any examination budget, so index construction remains bounded only
by corpus size, and `analyze_repository` holds the final graph and the retrieval index in memory
together. No memory cap is claimed and no timing benchmark was run. The default 25-seed budget
still truncates graph-context expansion on the earlier retrieval fixture. Conceptual multiword
queries are still matched by tokens only. Static resolution omissions, runtime binding
limitations, revision-only non-repository-namespaced IDs and native parser platform limits are
unchanged.

## 9. Unfinished Work

No mandatory Phase 2.4 work remains. Phase 2.5 (offline CLI) and Phase 2.6 (loopback-only read-only
HTTP API) are authorized but not started. There is no caching or persistence of an analysis
snapshot across processes, which the CLI must document as a real limitation rather than hide.

## 10. Next Subphase

Phase 2.5 — offline CLI. It must be a thin adapter over `analyze_repository`, `QueryRequest`,
`build_plan` and `run_query`; it must not implement a second analysis engine, must print measured
values only, must return distinct non-zero exit codes for ambiguity and failure, must support a
`--json` mode whose stdout is valid JSON with diagnostics on stderr, and must validate the target
path through the existing safe discovery logic without executing anything in it.

## 11. Critical Context

The analysis engine establishes what repository evidence supports; the explanation layer explains
that evidence. A lexical relevance score is not entity identity, not a probability, not a
confidence and not a runtime claim. A high BM25 score must never select a structural query target.
A graph-context hit is a structural association over one stored relationship, never proof of
execution, order, success or deployment. TESTS context means direct static test-call proof, never
runtime coverage. A staged SQLAlchemy mutation and a transaction control are canonical
DATABASE_OPERATION facts but carry no read/write capability edge. IMPORTS and DEFINES are never
context and never execution. `NO_KNOWN_PATH` is never proof of absence: static-analysis
incompleteness and query limits both produce it. A truncated result is a bounded discovered
ranking, never an exhaustive one, and no result proves repository completeness. Bundle IDs are
canonical entity IDs; retrieving or naming an entity does not trace it.

## 12. Agent Instructions

Read root documents completely and inspect the actual public APIs and tests before changing
anything. Preserve decisions and history and continue D-numbering from D-146. Finalize only new
commit-reference fields in a later documentation commit; never globally replace historical prose.
Use the project interpreter and run the complete gates; never weaken strict tooling and never
invent measured output. Validate file outcome counts before interpreting empty semantics. Keep
target input strictly as untrusted static data: no execution, imports, test runs, Node, dependency
installation, database connections, SQL or outbound network access. Check author, committer and
remotes at every boundary. Stop after the authorized phases: no push, no remote, no publication.
