# ArcTrellis Handoff

## 1. Current Phase

Phase 2.3A/B/C implementation and verification complete: deterministic structural retrieval over
canonical analysis snapshots. Repository C:/Projects/ArcTrellis, Python 3.13.14, required Git
identity; no remotes. Stop before Phase 2.4.

## 2. Work Completed

Read root documentation and the actual graph/core/index/query contracts, then verified the
reported baseline of 448 tests OK/skipped 7 before changing anything.

Stage A added an immutable build-time lexical snapshot. Stage B added field-weighted BM25, the
exact-match ladder, typed filters, candidate budgets and bounded one-hop graph context. Stage C
added the deterministic evaluation harness, an independent exact/substring baseline, a real
mixed-language retrieval repository, hard-negative and adversarial suites, and an end-to-end
static smoke that passes retrieved endpoint IDs into the existing structural query engine.

Public `arctrellis.retrieval` API: `build_search_index`, `search_symbols`, `search_endpoints`,
`search_tests`, `search_database_operations`, `SearchDocument`, `SearchField`,
`LexicalSearchIndex`, `SearchFilters`, `SearchHit`, `SearchResult`, `ContextSupport`,
`MatchBasis`, `ContextDirection`, `ContextEdge`, `GraphContextIndex`, `ExactMatchTier`,
`RelevanceJudgment`, `ExpectedEntity`, `RetrievalEvaluationResult`, `evaluate_retrieval`,
`exact_substring_baseline`, `format_evaluation`, `explain_hit`, `tokenize`, `normalize_exact`
and the retrieval error hierarchy. The package exports 67 deliberate names. No new runtime
dependency, no analysis/core/graph redesign and no source reread anywhere in retrieval.

Stage A committed 5a329c1, finalized d599b4a. Stage B committed 0f55d1c, finalized 2af8bf1.
Stage C committed d8f5c95, a public-API export correction committed d65d083, and documentation is
finalized separately afterwards.

## 3. Files Changed

- src/arctrellis/retrieval/__init__.py: deliberate public exports only.
- src/arctrellis/retrieval/errors.py: caller input versus invalid snapshot failures.
- src/arctrellis/retrieval/normalization.py: NFKC-preserving-case tokenizer and bounded fields.
- src/arctrellis/retrieval/documents.py: frozen SearchDocument/SearchField and the metadata allowlist.
- src/arctrellis/retrieval/index.py: deterministic inverted index, verified statistics, snapshot id.
- src/arctrellis/retrieval/scoring.py: BM25, field weights, exact-match tiers.
- src/arctrellis/retrieval/context.py: bounded one-hop projection over real stored relationships.
- src/arctrellis/retrieval/search.py: filters, budgets, hits, results, wrappers, explanations.
- src/arctrellis/retrieval/evaluation.py: judgments, metrics, baseline, mode comparison, report.
- tests/retrieval/__init__.py, fixtures.py: small canonical unit graphs.
- tests/retrieval/repository.py, judgments.py: mixed-language repository and independent judgments.
- tests/retrieval/test_documents.py, test_tokenization.py, test_index.py: Stage A contracts.
- tests/retrieval/test_scoring.py, test_search.py, test_context.py, test_limits.py: Stage B.
- tests/retrieval/test_golden.py, test_hardening.py, smoke.py: Stage C evaluation and hardening.
- README.md, decisions.md, flow.md, handoff.md: capabilities, decisions, real call flow, state.

## 4. Current Architecture / State

The analysis lifecycle is unchanged: `index_repository -> resolve_imports -> resolve_calls ->
resolve_http_endpoints -> resolve_framework_flow -> analyze_tests -> materialize_database_graph`.
Retrieval runs afterwards over the completed graph and never reruns it.

```text
build_search_index(graph, analysis_completeness, include_graph_context, max_context_neighbors)
 ├─ _validated_entities          one graph.entities() read; corrupt containers rejected
 ├─ build_document               allowlisted bounded fields; never signatures or arbitrary keys
 ├─ _build_postings              weighted term frequency -> entity-ID-ordered posting lists
 ├─ build_graph_context_index    one graph.relationships() read; allowed kinds only; capped lists
 └─ LexicalSearchIndex           verified statistics, content snapshot id, bounded context
```

Indexed: entity name, qualified name, repository-relative path, kind, language, parent id and
eighteen allowlisted existing metadata keys. Signatures are never indexed. Projected values are
stored truncated to 512 characters and 32 tokens; the canonical entity keeps its full value.
Entities without a SourceLocation report no path and no invented lines. Documents are sorted by
canonical entity ID, so equal graphs built in different insertion orders produce equal indexes.
`snapshot_id` is a UUID5 content digest of the documents and is never a repository revision.

Tokenization NFKC-normalizes while preserving case, splits on ASCII case/digit boundaries and on
every non-alphanumeric character, then case folds each token. `HTTPServer` becomes http+server;
`PaymentService` and `payment_service` share payment+service. Long values are truncated, not
rejected. Queries are pure data.

Ranking is field-weighted BM25 with k1=1.2, b=0.75 and smoothed IDF, summed over distinct query
terms, plus the strongest satisfied exact tier (qualified name 8.0, name 6.0, METHOD+path 5.0,
alphanumeric name 3.0, prefix 0.5 at four or more characters). Field weights run from name 3.0 to
kind/language/path 0.5 and are all exact binary fractions. `relevance_score` is exactly
`bm25_score + exact_match_boost + prefix_boost + graph_context_boost`; every component is
verified finite and exposed separately. Hits sort by relevance, then exact priority, then entity
ID. A BM25 value is a relevance score only, never a probability or confidence.

Graph context is an explicit opt-in. Only EXPOSES, CALLS, TESTS, READS_DATABASE,
WRITES_DATABASE and APPLIES_MIDDLEWARE are projected; DEFINES, IMPORTS, CONTAINS, INHERITS and
USES never act as invocation. At most one hop is examined. A context hit keeps the stored
relationship ID, kind, direction, confidence, confidence_score and original Evidence, and reports
`match_basis=graph_neighbor` without claiming it contains the query terms. The boost is
`min(1.0, seed_coverage * edge_weight)` taking the maximum over supporting relationships, never a
sum, so degree cannot inflate it; middleware is weighted 0.4 below invocation. Relationship
confidence is reported separately and never multiplied into relevance.

Filters mark candidates eligible or ineligible instead of discarding them, so a kind-restricted
wrapper can still discover endpoints that only context connects to the query, while top_k always
applies to eligible results. Limits: query length 512, query tokens 24, top_k default 25 and
maximum 100, posting budget 50000 examined records, graph seed budget 25, neighbor budget 16,
build-time neighbor cap 16 per entity and direction. Blank, token-free and oversized queries are
rejected. Every inspected posting record consumes the budget, including filtered-out records.
`truncated` reports budget-driven incompleteness with a closed reason vocabulary;
`eligible_candidate_count` reports top_k limiting. Counts are exact only when not truncated.

Defaults are unchanged for every prior subsystem. Graph-only mode stays unknown completeness;
callers pass the canonical AnalysisSummary completeness from the same revision.

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
References finalized in a later documentation commit; no history rewriting.

## 6. Requirements and Constraints

Local only: no GitHub API, remote changes, push, upload, publication, packages or releases. All
commits are authored and committed solely by PrathamKapoor <prathamkapoor027@gmail.com>. No
attribution lines, no secrets, no paper/research/tex files. No target execution, imports, test
runs, Node, dependency installation, database connections or SQL. Retrieval never rereads source,
synthesizes entities or relationships, invents Evidence, mutates evidence or confidence, or runs
analysis automatically. No servers, CLI, frontend, LLM, embeddings, vector store, persistence,
cache, workers or incremental updates. Runtime dependencies, Ruff and mypy configuration and all
existing parsing and semantic algorithms are unchanged.

## 7. Testing and Verification

Project interpreter .venv/Scripts/python.exe, Python 3.13.14. Baseline 448; Stage A 503;
Stage B 589; Stage C 640 tests OK/skipped 7. Existing platform skips are the six Windows symlink
privilege cases and the absent FIFO API. No retrieval test is skipped. Every gate ran targeted and
full tests, Ruff lint and format, strict mypy, compileall, pip check and architecture tests.

Commands (prefix `.venv\Scripts\python.exe`):
- `-m unittest tests.retrieval.test_documents -q`: 20 tests OK.
- `-m unittest tests.retrieval.test_tokenization -q`: 17 tests OK.
- `-m unittest tests.retrieval.test_index -q`: 18 tests OK.
- `-m unittest tests.retrieval.test_scoring -q`: 24 tests OK.
- `-m unittest tests.retrieval.test_search -q`: 29 tests OK.
- `-m unittest tests.retrieval.test_context -q`: 19 tests OK.
- `-m unittest tests.retrieval.test_limits -q`: 14 tests OK.
- `-m unittest tests.retrieval.test_golden -q`: 19 tests OK.
- `-m unittest tests.retrieval.test_hardening -q`: 31 tests OK.
- `-m unittest discover -s tests/retrieval -t . -q`: 192 tests OK.
- `-m unittest discover -s tests -q`: 640 tests OK/skipped 7.
- `-m ruff check src tests`: All checks passed.
- `-m ruff format --check src tests`: 158 files already formatted.
- `-m mypy src/arctrellis`: 86 source files, no issues.
- `-m compileall -q src`: exit 0.
- `-m pip check`: No broken requirements found.
- `-m unittest tests.test_architecture -q`: 3 tests OK.
- `-m tests.retrieval.smoke`: 83 entities, 83 documents, 116 terms, 675 posting records,
  34 context edges, 9 queries, 45 lexical hits, 45 graph-context hits, 8 queries using context,
  9 truncated searches, 5 of 7 retrieved endpoints with an existing evidence path, deterministic,
  graph unchanged, snapshot identity stable.

Measured evaluation at K=5 over 19 evaluated queries of 20 judgments: baseline Recall 0.8246,
Precision 0.3158, MRR 0.7298, HitRate 0.8947; BM25 0.8860/0.3474/0.8070/0.9474; BM25 with graph
0.8860/0.3211/0.8553/0.9474. Graph context improves listPayments, createPayment, persistPayment,
payment creation and payment database write and regresses test payment. BM25 regresses test
payment against the baseline. payment refund endpoint is missed by all three modes.

Smoke trace: `GET /payments -> listPayments -> listAllPayments -> listPayments ->
sqlalchemy:Payment.execute@221` with the original four relationships, unchanged. POST /payments
[app.py] and DELETE /payments/{paymentId] return NO_KNOWN_PATH because their handlers call
service methods that call resolution does not resolve.

Corrected failures during this phase: `tokenize(max_tokens=0)` returned one token because the
limit was checked after appending; `bm25_score` returned zero for a zero average length instead
of dropping the length-normalization term; `GraphContextIndex` cross-direction validation failed
on legitimately asymmetric capping; context supports named the returned hit as its own neighbor
and described the seed's direction; graph candidates that share no query token were dropped,
which deleted the documented discovery case; `graph_context_used` was computed from the full
ranking instead of the returned top_k; stored field values were unbounded even though tokenization
was bounded; `evaluate_retrieval` was not re-exported from the package entry point. Fixture-name
and metadata expectations in the new tests were corrected against actual canonical output rather
than by changing production behavior. No existing test was disabled and no timing threshold was
introduced. One repository grep for network or execution primitives matched only the identifier
`evaluate_retrieval` because of the `eval(` substring; no such primitive exists in retrieval.

## 8. Known Issues / Risks

No confirmed unresolved functional defect in the supported retrieval subset. Public graph
snapshots still allocate and sort eagerly before any examination budget, so index construction and
entity/relationship enumeration remain bounded only by corpus size; retrieval pays that cost once
per build instead of once per candidate. Index memory grows with tokens, the deliberate
memory-for-latency trade, and no memory cap is claimed. The default 25-seed budget truncates
graph-context expansion on the measured mixed repository, which every smoke query reports.
Conceptual multiword queries are matched by tokens only: `payment refund endpoint` is missed
entirely, and `PaymentService` ranks the identically named IMPORT above the CLASS. Adding a
judgement or changing a weight legitimately changes measured metrics. Static resolution
omissions, runtime binding limitations, revision-only non-repository-namespaced IDs and native
parser platform limits are unchanged.

## 9. Unfinished Work

No mandatory Phase 2.3 work remains. Local implementation and documentation reference finalization
are complete; Stage C implementation is d8f5c95. No Phase 2.4 work has started. There is no
optional full-source search, embedding, reranking, natural-language planner or incremental index.

## 10. Next Subphase

Phase 2.4 — Evidence Retrieval Orchestration and Deterministic Query Planning, in a later
authorized session only. Do not begin it during Phase 2.3 finalization.

## 11. Critical Context

The analysis engine establishes what repository evidence supports; the explanation layer explains
that evidence. Retrieval relevance is not a probability, a confidence or a runtime claim. A
graph-context hit is a structural association over one stored relationship, never proof of
execution, order, success or deployment. TESTS context means direct static test-call proof, never
runtime coverage. A staged SQLAlchemy mutation and a transaction control are retrievable as
canonical DATABASE_OPERATION facts but carry no read/write capability edge, and retrieval never
describes them as proven writes. IMPORTS and DEFINES are never context. A truncated result is a
bounded discovered ranking, never an exhaustive one, and a result never proves repository
completeness. Retrieval IDs are canonical entity IDs; retrieving an entity does not trace it.

## 12. Agent Instructions

Read root documents completely and inspect the actual public APIs and tests before changing
anything. Preserve decisions and history and continue D-numbering from D-140. Finalize only new
commit-reference fields in a later documentation commit; never globally replace historical prose.
Use the project interpreter and run the complete gates; never weaken strict tooling and never
invent measured output. Judge the retrieval implementation against the independent judgments in
tests/retrieval/judgments.py and report regressions as findings. Validate file outcome counts
before interpreting empty semantics. Check author, committer and remotes at every boundary and
keep target input strictly as untrusted static data. Stop after this phase: no push, no remote,
no publication, no target execution, no database or SQL, and no automatic analysis from retrieval.