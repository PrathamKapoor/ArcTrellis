# Decisions

Append-only record of engineering decisions.

### D-001: Establish a src-layout package and standard-library test workflow
- Date / phase / commit: 2026-10-08, Phase 0.1, e7a2f98d078583b392170d323682870745311e45
- Context: The inspected project directory was empty; git status and git rev-parse initially failed because no repository existed. Python 3.13.14 was observed.
- Decision: Initialize Git in the inspected directory, configure the required local identity, add the src-layout arctrellis package, use Python >=3.13 and unittest discovery, and exclude Python/editor artifacts, paper/, research/ and *.tex. Add the three required root documents and README without a license claim.
- Why: The requested foundation needs installable packaging and reproducible tests; unittest provides assertions, discovery and subtests without a testing dependency. The Python minimum matches the observed minor version and permits explicit type aliases.
- Alternatives considered: Flat package layout weakens separation of installed code; pytest adds an unnecessary dependency for these tests; older Python support is unverified; empty future component directories contain no implementation.
- Consequences: Python before 3.13 is unsupported. No formatter, linter or type checker is configured. A license must be chosen before contributors can rely on reuse permissions.
- Files: .gitignore, pyproject.toml, README.md, src/arctrellis/__init__.py, src/arctrellis/core/__init__.py, decisions.md, flow.md, handoff.md, tests/__init__.py, tests/core/__init__.py, tests/core/test_models.py
- Package: setuptools ==84.0.0 (build only)
- Why this package: Standard packaging backend for editable installation and src-layout discovery; version 84.0.0 was observed locally.
- Packages compared: Hatchling and Flit are reasonable backends but add unfamiliar tooling with no benefit for this small pure-Python package; omitting a backend would leave installation implicit.

### D-002: Define immutable canonical vocabulary and explicit caller-owned identities
- Date / phase / commit: 2026-10-08, Phase 0.1, e7a2f98d078583b392170d323682870745311e45
- Context: Future parsing and querying components require a common vocabulary without infrastructure dependencies.
- Decision: Create EntityKind, RelationshipKind and Confidence string enums and frozen, slotted SourceLocation, CodeEntity, Evidence and Relationship dataclasses. Export the seven types from arctrellis.core. IDs are validated caller-supplied strings. Relationships point from source to target and embed a tuple of Evidence records. Classification is mandatory; an optional finite confidence_score ranges from zero to one. Duplicate embedded evidence IDs are rejected.
- Why: The requested scope is representation and invariants, not discovery, graph integrity or proof verification. Embedded immutable records keep ownership simple. Caller-owned IDs avoid speculative cross-repository identity design.
- Alternatives considered: Random identifiers would not reproduce identity; deterministic identity generation needs repository context not yet defined; evidence references require a separate store; score-derived classifications impose unsupported calibration thresholds; runtime OBSERVED is outside scope.
- Consequences: Producers must provide reproducible IDs and adequate proof. Global uniqueness, endpoint existence and unresolved-target policy remain future graph concerns. UNRESOLVED can use an opaque caller-supplied target placeholder. Zero evidence is valid even for PROVEN; constructors do not certify truth.
- Files: src/arctrellis/core/models.py, src/arctrellis/core/__init__.py, tests/core/test_models.py, README.md, decisions.md, flow.md

### D-003: Validate raw portable paths and restrict metadata to immutable string pairs
- Date / phase / commit: 2026-10-08, Phase 0.1, e7a2f98d078583b392170d323682870745311e45
- Context: Repository paths must work across operating systems without hiding invalid input; metadata must not undermine immutable records or future serialization.
- Decision: Store unmodified forward-slash relative strings, rejecting Windows anchors, backslashes, control characters, empty/dot/traversal segments and surrounding whitespace. Require integer, non-boolean inclusive line bounds. Store metadata as ordered tuples of unique string pairs. Validate nested record types, enum types, required strings, optional strings and snake_case evidence methods at construction; use TypeError for wrong types and ValueError for invalid values.
- Why: PurePosixPath normalizes dot and repeated separator segments before validation, losing the original invalid spelling. Strings and immutable tuples convert through dataclasses.asdict and JSON without a serializer framework.
- Alternatives considered: PurePosixPath storage silently normalizes input; mutable dictionaries undermine freezing; read-only dictionary proxies complicate hashing and asdict; recursive metadata freezing adds unnecessary complexity; arbitrary method strings allow unclear method identifiers.
- Consequences: Adapters must provide canonical paths and flatten metadata to strings. Metadata order participates in equality. Paths are syntax-validated only; filesystem existence, symlinks and source line counts are not checked.
- Files: src/arctrellis/core/models.py, tests/core/test_models.py, README.md, decisions.md, flow.md

### D-004: Finalize commit references without rewriting history
- Date / phase / commit: 2026-10-08, Phase 0.1, e7a2f98d078583b392170d323682870745311e45
- Context: The required documentation must reference real commits, but a commit cannot contain its own final hash.
- Decision: Commit verified implementation and documentation together, then replace their uncommitted markers with that implementation hash in a separate documentation finalization commit. The finalization commit does not need to embed its own hash.
- Why: This follows the explicit safe procedure and preserves truthful history. No implementation occurred in the earlier process-launch failure.
- Alternatives considered: Amending commits changes the hash again; inventing a hash or deleting decision history breaks traceability.
- Consequences: Implementation records reference the implementation commit; the later commit records reference finalization and the verified handoff.
- Files: decisions.md, flow.md, handoff.md

### D-005: Record the initial commit's signing override
- Date / phase / commit: 2026-10-08, Phase 0.1, e7a2f98d078583b392170d323682870745311e45
- Context: The initial commit command explicitly supplied commit.gpgsign=false; this operational choice needs to remain visible even though no persistent configuration file changed.
- Decision: Use an unsigned initial foundation commit with the required author and committer identity, and record the per-command override. Do not change repository or global signing configuration.
- Why: The session requires exact author identity and attribution-free commits, and specifies no signing requirement. git log reported signature:N and the required author and committer for the foundation commit.
- Alternatives considered: Default signing behavior was not used for the initial commit; inherited signing configuration was not inspected. Signature enforcement was outside this phase's requirements.
- Consequences: The initial commit's identity is recorded in Git metadata without cryptographic signature verification. Future contributors may choose a signing policy explicitly.
- Files: decisions.md, flow.md, handoff.md

### D-006: Store an append-oriented graph with strict endpoint integrity
- Date / phase / commit: 2026-10-08, Phase 0.2, 7c9b42800c1e5b7c8d22791109480cc2cb42b94f
- Context: Phase 0.1 left graph-wide uniqueness and relationship endpoint existence to a graph layer. Phase 0.2 requires a dependency-free in-memory container.
- Decision: Add arctrellis.graph.CodeGraph using dictionaries for canonical entities and relationships and incoming/outgoing adjacency lists. add_entity and add_relationship return None, preserve original immutable records, and treat equal value reinsertions as idempotent. Conflicting same-ID records raise DuplicateEntityError or DuplicateRelationshipError. Distinct relationship IDs may share a structural triple. Check both relationship endpoints before changing storage or indexes. Add no removal API or dependency.
- Why: Explicit checks prevent dangling edges and silent overwrites, while parallel records preserve independent evidence. The requested phase is append-oriented and requires no graph library.
- Alternatives considered: Strict duplicate failure complicates repeated loading; overwriting loses facts; collapsing triples loses evidence; implicit placeholder creation invents entities; third-party graph storage adds unnecessary weight.
- Consequences: Entities must be loaded before relationships. An UNRESOLVED edge still needs an explicitly inserted placeholder entity; CodeGraph does not create placeholders. Parent IDs and evidence ID uniqueness across relationships remain unchecked. This mutable container is not thread-safe.
- Files: src/arctrellis/graph/graph.py, src/arctrellis/graph/__init__.py, src/arctrellis/graph/errors.py, tests/graph/__init__.py, tests/graph/fixtures.py, tests/graph/test_graph.py, README.md, decisions.md, flow.md, handoff.md

### D-007: Use sorted adjacency indexes and shared deterministic breadth-first search
- Date / phase / commit: 2026-10-08, Phase 0.2, 7c9b42800c1e5b7c8d22791109480cc2cb42b94f
- Context: Structural queries and paths must reproduce results regardless of insertion order and terminate on cycles.
- Decision: Keep adjacency relationship IDs lexically sorted at insertion using bisect.insort. Return tuples; full snapshots and unique neighbors sort by entity/relationship ID. Traverse in breadth-first discovery order, expanding each node's edges by relationship ID. Mark nodes visited on discovery. Share the BFS implementation between bounded forward/reverse traversal and unweighted shortest paths. None means all kinds; an empty set means no edges. Multi-kind filters accept sets/frozensets of RelationshipKind only; depth must be a non-boolean integer >=0.
- Why: Ordered adjacency avoids sorting during BFS and scans only the queried degree. A deque plus discovery-time visitation prevents cycles and duplicate nodes while finding shortest unweighted paths.
- Alternatives considered: Sorting adjacency on each query adds repeated degree sorting; insertion-order traversal is nondeterministic across equivalent inputs; DFS does not guarantee shortest paths; weighted algorithms have no cost model in this phase; caching is unnecessary.
- Consequences: Equal-length path ties follow BFS discovery through sorted local edge IDs, not a global path ranking. Insertion costs O(degree) per sorted adjacency list; lookup averages O(1), adjacency O(degree), BFS O(V+E) within the explored subgraph. Snapshots and neighbor ordering incur sorting costs. IDs use Python string lexical order.
- Files: src/arctrellis/graph/graph.py, tests/graph/test_graph.py, tests/graph/test_traversal.py, tests/graph/fixtures.py, README.md, decisions.md, flow.md, handoff.md

### D-008: Expose explicit graph errors and immutable traversal/path results
- Date / phase / commit: 2026-10-08, Phase 0.2, 7c9b42800c1e5b7c8d22791109480cc2cb42b94f
- Context: Queries need a clear distinction between unknown IDs, disconnected known nodes, and evidence-preserving paths.
- Decision: Add GraphError, DuplicateEntityError, DuplicateRelationshipError, UnknownEntityError and UnknownRelationshipError in errors.py. ID lookups and queries require string IDs and raise explicit unknown-ID errors; existence methods return booleans. Return TraversalResult with distinct entities in BFS discovery order, including the start. Return GraphPath with entity and original relationship tuples; validate nonempty entities, cardinality and directed edge continuity. Known disconnected pairs return None; same-node queries return a one-entity zero-edge path. Export only intentional public types through arctrellis.graph; put result records in results.py.
- Why: Traversal needs a named result without guessing tuple semantics; paths must retain original evidence. Small modules keep container, errors and record invariants cohesive. Phase 0.1 records need no changes.
- Alternatives considered: Optional lookup results hide unknown-ID mistakes; errors for no path treat normal disconnection as exceptional; entity-ID-only paths lose edge proof; embedding a full BFS tree adds unnecessary result state.
- Consequences: TraversalResult contains nodes only; inspect adjacency for edges or use GraphPath for a specific proof path. Result constructors reject wrong types and malformed structure. GraphPath may represent a walk with repeated entities, although shortest_path emits simple paths. Existence checks do not normalize IDs. Reachability follows inserted edges regardless of confidence and makes no new proof claims.
- Files: src/arctrellis/graph/results.py, src/arctrellis/graph/errors.py, src/arctrellis/graph/__init__.py, src/arctrellis/graph/graph.py, tests/graph/test_results.py, tests/graph/test_traversal.py, tests/graph/test_graph.py, README.md, decisions.md, flow.md, handoff.md

### D-009: Keep graph verification fixtures explicit and preserve session traceability
- Date / phase / commit: 2026-10-08, Phase 0.2, 7c9b42800c1e5b7c8d22791109480cc2cb42b94f
- Context: The graph must be reviewed and tested without a parser, and future sessions need the exact current state rather than an overwritten historical claim.
- Decision: Keep synthetic payment-flow constructors only in tests/graph/fixtures.py, with meaningful entity names and manually supplied evidence. Separate storage/adjacency, traversal/path and result-contract tests into cohesive modules. Verify all existing tests and public imports locally; rewrite handoff with actual results. Preserve prior decision entries and session tables and finalize new commit references in a separate documentation commit under D-004. No remote, publishing or dependency operations are part of this phase.
- Why: The user requires realistic examples, honest capabilities, regression coverage, twelve handoff sections and local-only commits. The initial test-first run failed with ModuleNotFoundError: No module named 'arctrellis.graph', as expected before implementation; after implementation the observed full suite ran 89 tests with OK.
- Alternatives considered: Production demo facts would mix fixtures into real graph storage; a single larger test module obscures separate contracts; rewriting existing history loses truthful context; publishing is explicitly prohibited.
- Consequences: Test evidence is synthetic, not output from source analysis. All implementation and documentation claims must remain limited to explicitly inserted in-memory records. Prior phase details remain in Git history and the preserved decision/flow records.
- Files: tests/graph/fixtures.py, tests/graph/test_graph.py, tests/graph/test_traversal.py, tests/graph/test_results.py, README.md, decisions.md, flow.md, handoff.md

### D-010: Correct documentation boundaries and rewrite handoff in place
- Date / phase / commit: 2026-10-08, Phase 0.2, 7c9b42800c1e5b7c8d22791109480cc2cb42b94f
- Context: Independent code review found no important graph correctness issues, but identified a split Markdown session table and stale wording about endpoint validation and unresolved references. An attempted combined delete/add handoff patch was rejected with `apply_patch verification failed: invalid patch: multiple operations target C:\Projects\ArcTrellis\handoff.md`; it changed no files.
- Decision: Keep the session table continuous, distinguish domain constructor validation from CodeGraph endpoint checks, and state the implemented explicit-placeholder policy. Rewrite handoff with one in-place file write instead of combined delete/add operations.
- Why: These corrections align documentation with actual code. The rejected patch was a documentation-edit mechanism failure, not an ArcTrellis defect; recording it prevents repeating that unsupported approach.
- Alternatives considered: Separate delete/add operations would temporarily remove the required handoff file; leaving stale wording would obscure the graph's integrity policy.
- Consequences: Future handoff rewrites should use one supported update per target path. The graph's correctness and Phase 0.1 domain semantics are unchanged.
- Files: README.md, decisions.md, flow.md, handoff.md
- Symptom: The Phase 0.2 table was interrupted after its first row, and documentation said target existence was not checked in this phase or awaited a future graph policy.
- Root cause: A blank line separated Markdown table rows; wording retained the domain-only validation boundary after CodeGraph had implemented endpoint integrity and explicit placeholder insertion.
- Regression test: none; documentation-only corrections were checked against CodeGraph.add_relationship and reviewed in the final Markdown source.
