# Structural Query Implementation Plan

Goal: Implement the user-specified Phase 2.2A/B/C without target execution or remote operations.

Architecture: query depends only on core/graph and standard library. Frozen paths retain original records;
one constrained breadth-first simple-path search serves forward and reverse queries. No graph internals change.
The detailed design and authorization are Coding Prompt 12 in the session; no additional approval is required.

## Stage A

- [x] Add tests/query/test_paths.py first; run it and observe missing query API.
- [x] Add query/errors.py, models.py, traversal.py, database.py and deliberate __init__.py exports.
- [x] Validate graph membership/continuity, positive non-boolean budgets, edge-specific patterns and metadata.
- [x] Test parallel evidence, cycles, deterministic order, JSON primitives, missing IDs and truncation.
- [x] Run targeted/full unittest, Ruff lint/format, strict mypy, compileall, pip check and architecture audit.
- [x] Append D-118 onward and flow; audit/stage/commit locally with required identity, finalize references.

## Stage B

- [x] Add tests/query/test_architecture_queries.py first and observe missing API failure.
- [x] Add direct database/test queries, reverse callers/impact and metadata endpoint inventory filters.
- [x] Use a validated lightweight completeness enum argument; never retain RepositoryIndexResult or source.
- [x] Test direct/transitive distinction, duplicate registrations, local/effective scope and missing-path semantics.
- [x] Repeat complete Stage A gates, documentation, audits and local commit/reference finalization.

## Stage C

- [x] Add independently specified Python, JS, TS and mixed golden temporary repository fixtures.
- [x] Exercise the actual index/import/call/HTTP/flow/test/database pipeline before source-free queries.
- [x] Add bounded synthetic stress, insertion-order determinism, security and immutable result checks.
- [x] Add reproducible tests.query.smoke with real counts, paths and reverse impact proof.
- [x] Repeat complete gates; update README, decisions, flow and twelve-section handoff; commit/finalize locally.
- [x] Re-run all gates after final commit, inspect identity/remotes/status; stop before Phase 2.3.

Limits default to depth12, paths25, examined edges10000. Depth includes terminal edges.
Search returns bounded discovered paths sorted by hop count/relationship IDs/entity IDs, not globally shortest claims.
Queue memory is bounded by edge budget. Path cap requires finding an extra result before marking truncation;
depth/expansion cuts mark unexplored eligible continuations. Missing scores produce unknown weakest score.
No runtime dependencies, source reads, synthetic edges, middleware impact or probabilistic confidence.
