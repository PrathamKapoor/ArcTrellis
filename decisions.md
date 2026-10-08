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
- Decision: Commit verified implementation and documentation together, then replace their acfd6093f95e0f9dd6b150ad625cb5ab6fee4a79 markers with that implementation hash in a separate documentation finalization commit. The finalization commit does not need to embed its own hash.
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

### D-011: Define immutable portable inventory records
- Date / phase / commit: 2026-10-08, Phase 1.0, d02524700240e8a37b15f01e7138b7dbb3a70e8a
- Context: Future parsers need filesystem inputs without owning discovery or receiving contents.
- Decision: Add ingestion DiscoveredFile, SkippedPath, RepositoryInventory, Language and SkipReason. Validate raw relative forward-slash paths, nonnegative sizes and enum types; preserve actual filename spaces. Require sorted unique immutable tuples, disjoint file/skip paths and derived supported subsets and ordered counts. Store no root or contents.
- Why: Immutable values support reproducibility, hashing and primitive serialization without changing SourceLocation semantics.
- Alternatives considered: Mutable collections weaken value semantics; path normalization hides malformed inputs; absolute roots tie values to hosts; contents exceed scope.
- Consequences: Consumers retain the root separately. Unrepresentable portable filenames fail explicitly. Counts include only supported languages with nonzero counts.
- Files: src/arctrellis/ingestion/models.py, src/arctrellis/ingestion/__init__.py, tests/ingestion/__init__.py, tests/ingestion/test_models.py, README.md, decisions.md, flow.md, handoff.md

### D-012: Inspect metadata with explicit exclusions and no link traversal
- Date / phase / commit: 2026-10-08, Phase 1.0, d02524700240e8a37b15f01e7138b7dbb3a70e8a
- Context: Untrusted directories may contain dependencies, links, unusual objects and code that must never execute.
- Decision: Add synchronous standard-library scan_repository with non-following stat, scandir and an iterative directory stack. Prune case-sensitive directory names at every level; optional set/frozenset exclusions replace defaults. Skip links, junctions, other reparse points and nonregular objects with records. Detect ten Python/JavaScript/TypeScript extensions case-insensitively and sort files/skips lexically by original relative path. Defer .gitignore and hashing.
- Why: Pruning before descent avoids dependency trees; explicit metadata inspection separates filesystem safety from parsing. No additional package is needed.
- Alternatives considered: Blanket hidden exclusion loses .github; following internal links complicates cycles; third-party crawlers add no required capability; Git ignore semantics need separate design.
- Consequences: Matching directory names may contain legitimate source; callers can replace exclusions. Link guards remain active with empty exclusions. Unsupported ordinary files remain visible.
- Files: src/arctrellis/ingestion/discovery.py, src/arctrellis/ingestion/__init__.py, tests/ingestion/test_discovery.py, tests/ingestion/test_safety.py, README.md, decisions.md, flow.md, handoff.md

### D-013: Fail incomplete scans and state concurrent filesystem limits
- Date / phase / commit: 2026-10-08, Phase 1.0, d02524700240e8a37b15f01e7138b7dbb3a70e8a
- Context: Unexpected filesystem errors must not masquerade as complete inventories. Observed Windows Python lacks O_NOFOLLOW and descriptor-based scandir.
- Decision: Add IngestionError, InvalidRepositoryPathError and RepositoryAccessError. Normalize the root lexically once, reject linked root ancestors, require an ordinary directory and recheck directory identity before descent. Chain unexpected filesystem errors and return no partial result. Require a stable target tree and document that pathname metadata checks are not an atomic sandbox against concurrent substitution.
- Why: Explicit failure preserves completeness; available checks avoid static links but cannot make Windows pathname operations atomic.
- Alternatives considered: Silent skipping hides missing data; resolving linked roots accepts indirection; claiming race-proof containment exceeds verified APIs; native dependencies exceed scope.
- Consequences: Linked root ancestors are rejected. Callers must prevent concurrent hostile changes; future readers must revalidate paths. Injected access tests do not claim real OS permission-denial coverage.
- Files: src/arctrellis/ingestion/errors.py, src/arctrellis/ingestion/discovery.py, src/arctrellis/ingestion/__init__.py, tests/ingestion/test_discovery.py, tests/ingestion/test_safety.py, README.md, decisions.md, flow.md, handoff.md

### D-014: Verify discovery with local synthetic fixtures
- Date / phase / commit: 2026-10-08, Phase 1.0, d02524700240e8a37b15f01e7138b7dbb3a70e8a
- Context: Discovery needs reproducible safety tests without network access or target execution.
- Decision: Add unittest inventory, discovery and safety suites using temporary directories, explicit skips for unavailable link creation and injected filesystem errors. Preserve Phase 0 implementation and prior documentation history. Finalize references under D-004.
- Why: The user requires local verification, honest limitations and unchanged domain/graph semantics. The baseline ran 89 tests with OK.
- Alternatives considered: External fixtures require network; target execution violates the inspection boundary; graph changes are unnecessary.
- Consequences: Platform skips and simulated error coverage must be reported honestly. No dependency, remote or publishing operations are included.
- Files: tests/ingestion/__init__.py, tests/ingestion/test_models.py, tests/ingestion/test_discovery.py, tests/ingestion/test_safety.py, README.md, decisions.md, flow.md, handoff.md

### D-015: Retry an atomic documentation patch with verified context
- Date / phase / commit: 2026-10-08, Phase 1.0, d02524700240e8a37b15f01e7138b7dbb3a70e8a
- Context: A combined initial test/documentation patch failed with `Failed to find expected lines in C:\Projects\ArcTrellis\flow.md: #`; git status --short remained empty.
- Decision: Read the actual flow document and retry with existing section context rather than a guessed standalone heading.
- Why: The failed patch changed no repository files; documenting the failed edit avoids repeating it.
- Alternatives considered: none.
- Consequences: Patch contexts must match inspected source. This is an editing failure, not a repository defect.
- Files: decisions.md, flow.md

### D-016: Compare directory identity using the same metadata API
- Date / phase / commit: 2026-10-08, Phase 1.0, d02524700240e8a37b15f01e7138b7dbb3a70e8a
- Context: The first implementation run failed five nested discovery tests on unchanged Windows directories.
- Decision: Obtain queued ordinary-directory identities using os.lstat, matching the fresh checks, while retaining non-following DirEntry metadata for classification and file size.
- Why: A minimal local reproduction printed DirEntry identity 0 0 and nonzero os.lstat device/inode fields for the same directory; comparing these APIs incorrectly reported a replacement.
- Alternatives considered: Removing identity checks loses useful change detection; treating zero identities as matches weakens checks; using lstat consistently for queued identities fixes the mismatch directly.
- Consequences: Each entered child directory requires an additional metadata lookup. Excluded directories still require no traversal. This does not make pathname checks atomic.
- Files: src/arctrellis/ingestion/discovery.py, tests/ingestion/test_discovery.py, decisions.md, flow.md, handoff.md
- Symptom: RepositoryAccessError: directory changed during discovery on unchanged nested directories; the run reported FAILED (errors=5).
- Root cause: Windows DirEntry.stat(follow_symlinks=False) yielded zero st_dev/st_ino fields, while os.lstat returned actual identity values; _check_directory compared incompatible values.
- Regression test: tests/ingestion/test_discovery.py::DiscoveryTests.test_nested_files_have_relative_posix_paths_and_sizes and test_creation_order_and_repeated_scans_are_equal.

### D-017: Pin the Tree-sitter runtime explicitly
- Date / phase / commit: 2026-10-08, Phase 1.1, 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168
- Context: Syntax parsing now requires a runtime dependency; pip index versions reported 0.26.0 and official documentation describes ABI compatibility.
- Decision: Add tree-sitter==0.26.0 and verify actual installation and grammar compatibility before completion.
- Why: Exact pins make syntax behavior reproducible; this is the current version observed through package tooling.
- Alternatives considered: Python ast handles only Python; handwritten parsers are inappropriate; tree-sitter-languages convenience bundle hides language ownership and pip index returned ERROR: No matching distribution found for tree-sitter-languages in this environment.
- Consequences: Dependency upgrades require grammar and normalized-output regression verification. Compatibility is established by real parsing tests, not matching version numbers.
- Files: pyproject.toml, decisions.md, flow.md, README.md, handoff.md
- Package: tree-sitter ==0.26.0
- Why this package: Parses source bytes as syntax without target execution.
- Packages compared: tree-sitter-languages convenience bundle versus explicit runtime plus grammars; the explicit approach ships only required grammars and exposes their versions.

### D-018: Pin the Python grammar separately
- Date / phase / commit: 2026-10-08, Phase 1.1, 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168
- Context: Python and stub syntax need a grammar; package tooling reported 0.25.0.
- Decision: Add tree-sitter-python==0.25.0 for .py and .pyi.
- Why: Dedicated grammar ownership and exact syntax-version reproducibility match the requested architecture.
- Alternatives considered: Python ast lacks the shared Tree-sitter adapter and recovery model; bundled grammars obscure independent provenance.
- Consequences: Grammar updates may change node kinds or recovery; test them deliberately.
- Files: pyproject.toml, decisions.md, flow.md, README.md, handoff.md
- Package: tree-sitter-python ==0.25.0
- Why this package: Supplies the Python grammar capsule consumed by the parser adapter.
- Packages compared: tree-sitter-languages bundling and standard-library ast; neither satisfies the chosen explicit shared syntax boundary as directly.

### D-019: Pin the JavaScript grammar separately
- Date / phase / commit: 2026-10-08, Phase 1.1, 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168
- Context: JavaScript and JSX need a grammar; package tooling reported 0.25.0.
- Decision: Add tree-sitter-javascript==0.25.0 for .js/.jsx/.mjs/.cjs.
- Why: Explicit grammar ownership avoids unrelated language bundles.
- Alternatives considered: Bundled grammars hide independently selected versions; executing Node.js violates the source-as-data boundary.
- Consequences: JavaScript syntax tests must cover JSX and modern constructs when upgrading.
- Files: pyproject.toml, decisions.md, flow.md, README.md, handoff.md
- Package: tree-sitter-javascript ==0.25.0
- Why this package: Supplies JavaScript/JSX syntax without target execution.
- Packages compared: tree-sitter-languages bundle; separate grammar offers clearer provenance and narrower installation.

### D-020: Pin TypeScript and TSX grammar ownership together
- Date / phase / commit: 2026-10-08, Phase 1.1, 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168
- Context: TypeScript requires separate TS and TSX dialect selection; tooling reported 0.23.2.
- Decision: Add tree-sitter-typescript==0.23.2; .tsx selects its TSX grammar while canonical language remains typescript.
- Why: The dedicated package provides both required dialects without creating a new ingestion language.
- Alternatives considered: Plain TypeScript for TSX misrepresents JSX syntax; convenience bundles obscure dialect/version ownership.
- Consequences: Extension/language consistency is checked before parsing; every ingestion-supported extension needs a grammar test.
- Files: pyproject.toml, decisions.md, flow.md, README.md, handoff.md
- Package: tree-sitter-typescript ==0.23.2
- Why this package: Supplies dedicated TypeScript and TSX grammars.
- Packages compared: tree-sitter-languages convenience bundle and JavaScript grammar; JavaScript does not cover TypeScript type syntax.

### D-021: Own normalized immutable syntax instead of parser objects
- Date / phase / commit: 2026-10-08, Phase 1.1, 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168
- Context: Future semantic extractors need syntax without infrastructure-specific objects.
- Decision: Add parsing models SyntaxSpan, SyntaxNode, ParseDiagnostic, DiagnosticKind and ParsedSource. Retain named nodes plus any error/missing nodes, preserve child/field order and flags, discard parser identity. Spans use half-open byte ranges, 1-based lines and 0-based byte columns. Retain source bytes exactly and immutable diagnostic tuples. Add iterative preorder walk, first-match child_by_field and bounded bytes_for helpers.
- Why: Own values isolate Tree-sitter and permit deterministic equality. Missing anonymous punctuation must remain visible. Raw bytes avoid duplicate decoded strings and preserve exact slicing.
- Alternatives considered: Raw trees couple all consumers to the dependency; full punctuation trees add unnecessary memory; source decoding adds an unrelated encoding policy; recursive traversal fails on deeply nested inputs.
- Consequences: Grammar kinds/fields remain grammar-specific vocabulary, not semantic entities. Normalization and retained bytes cost extra memory; bytes are not directly JSON-serializable. Lines/end positions are exclusive syntax coordinates, unlike inclusive SourceLocation lines.
- Files: src/arctrellis/parsing/models.py, src/arctrellis/parsing/normalization.py, src/arctrellis/parsing/__init__.py, tests/parsing/__init__.py, tests/parsing/test_models.py, tests/parsing/test_parser.py, README.md, decisions.md, flow.md, handoff.md

### D-022: Select explicit grammars and fresh synchronous parsers
- Date / phase / commit: 2026-10-08, Phase 1.1, 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168
- Context: Every ingestion extension must parse consistently, including TSX, without shared mutable parser state.
- Decision: Add private grammar selection and parser construction in registry.py; reject contradictory language/extension metadata. Construct a fresh Parser and grammar wrapper for every parse. parse_source returns normalized syntax and ERROR/MISSING diagnostics even for malformed source; internal parser failures use typed exceptions.
- Why: Fresh instances avoid reuse/thread-safety assumptions. Invalid syntax is a recoverable result, distinct from configuration or hard parser failure.
- Alternatives considered: Caching mutable parsers introduces synchronization and order concerns; rejecting all error trees loses unaffected syntax; treating TSX as a new language changes ingestion unnecessarily.
- Consequences: No pooling, incremental parsing or performance/thread-safety claim exists. Grammar loading overhead is accepted for single-file correctness.
- Files: src/arctrellis/parsing/registry.py, src/arctrellis/parsing/parser.py, src/arctrellis/parsing/errors.py, src/arctrellis/parsing/__init__.py, tests/parsing/test_registry.py, tests/parsing/test_parser.py, README.md, decisions.md, flow.md, handoff.md

### D-023: Bound and revalidate source reads separately from discovery
- Date / phase / commit: 2026-10-08, Phase 1.1, 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168
- Context: Parsing now needs source contents from potentially stale inventory metadata and untrusted paths.
- Decision: Add parse_discovered_file and a dedicated source reader. Validate root/ancestors and current ordinary file status, reject observed links/reparse points, check descriptor metadata, read at most limit+1 bytes and recheck identity/size/mtime after reading. Apply DEFAULT_MAX_SOURCE_BYTES=2*1024*1024 to both entry points; equality is allowed, positive integer overrides supported, oversized sources fail without parsing truncations. Distinguish SourceReadError, UnsafeSourceError, SourceTooLargeError, UnsupportedLanguageError, ParserConfigurationError and ParserExecutionError under ParsingError.
- Why: Bounded reads contain input allocation and ignore stale discovery size. Exception chaining preserves filesystem failures. Parsing still never imports, evaluates, executes or installs target code.
- Alternatives considered: Trusting inventory size misses changed files; unbounded reads defeat the limit; native atomic containment exceeds scope; sharing private ingestion helpers couples independent boundaries.
- Consequences: Stable filesystem assumption remains necessary; pathname checks are not a universal atomic sandbox. SourceReadError includes changed/unsafe targets through a subtype. Source bytes and normalized trees increase memory; file size does not bound execution time or normalized-node count.
- Files: src/arctrellis/parsing/source.py, src/arctrellis/parsing/parser.py, src/arctrellis/parsing/errors.py, tests/parsing/test_parser.py, README.md, decisions.md, flow.md, handoff.md

### D-024: Postpone recursive and type-only parser annotations
- Date / phase / commit: 2026-10-08, Phase 1.1, 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168
- Context: The first implementation test run failed during public package import.
- Decision: Use postponed annotations in models.py and registry.py for recursive SyntaxNode types and the private type-checking-only Parser annotation.
- Why: Python 3.13 otherwise evaluates type names during definition; SyntaxNode does not exist inside its own unfinished class body. Registry imports Parser only under TYPE_CHECKING.
- Alternatives considered: Quoting each forward annotation works but is easier to miss; runtime native imports solely for annotations add unnecessary coupling.
- Consequences: Runtime annotation introspection must resolve type names deliberately; public normalized objects remain independent of native types.
- Files: src/arctrellis/parsing/models.py, src/arctrellis/parsing/registry.py, tests/parsing/test_models.py, tests/parsing/test_registry.py, decisions.md, flow.md, handoff.md
- Symptom: NameError: name 'SyntaxNode' is not defined; parser-specific run FAILED (errors=3).
- Root cause: The recursive children: tuple[SyntaxNode, ...] annotation was eagerly evaluated before class creation on Python 3.13.
- Regression test: tests/parsing/test_models.py::SyntaxModelTests.test_walk_and_field_lookup_preserve_order_and_choose_first_match; public import and grammar selection tests also require successful module definition.

### D-025: Capture syntax coordinates at cursor entry
- Date / phase / commit: 2026-10-08, Phase 1.1, 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168
- Context: Deep array nesting exposed a normalized child containment failure after standard samples passed.
- Decision: Capture primitive node metadata into immutable SyntaxNode templates when entering each native cursor position; reconstruct children from these values rather than delayed native-node access.
- Why: The failing conversion printed an array at bytes 1207..1210 with start column 1210, while direct native-tree inspection showed consistent spans and cursor-entry inspection showed start column 1207. The delayed frame metadata differed from the entry metadata.
- Alternatives considered: Relaxing containment hides wrong coordinates; recursive traversal reintroduces depth limits; capturing values immediately respects the isolation boundary.
- Consequences: Temporary leaf templates add allocation during conversion. Native cursor references are not retained in frames. Native implementation details causing delayed coordinate changes are unknown.
- Files: src/arctrellis/parsing/normalization.py, tests/parsing/test_parser.py, decisions.md, flow.md, handoff.md
- Symptom: ValueError: children must be contained in the parent and in source order for 1200 nested JavaScript arrays.
- Root cause: Conversion deferred reading native node point metadata until after cursor traversal; the delayed start column differed from the correctly observed cursor-entry coordinate.
- Regression test: tests/parsing/test_parser.py::ParserTests.test_deep_native_tree_normalization_does_not_use_python_recursion.

### D-026: Replace native cursor traversal after a verified Windows crash
- Date / phase / commit: 2026-10-08, Phase 1.1, 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168
- Context: Capturing at cursor entry did not fix deep traversal: focused runs exited one without a traceback; a faulthandler reproduction printed Windows fatal exception: access violation in _span from native cursor-node access.
- Decision: Use iterative native Node.children traversal and field_name_for_child, keeping immediate primitive snapshots and avoiding TreeCursor. Preserve strict span validation rather than hiding corruption.
- Why: Independent direct native-child inspection of the same 1200-level source reported native spans consistent. Cursor-backed metadata access was the verified crash surface; the native implementation mechanism is unknown.
- Alternatives considered: Immediate snapshots alone failed and are recorded in D-025; reducing the test depth hides the safety issue; claiming a Python exception can catch a native access violation is false; dependency downgrade has not been shown necessary.
- Consequences: Native children lists add allocation. Deep-node conversion requires regression coverage; byte size remains a bound on input only, not native execution time or memory.
- Files: src/arctrellis/parsing/normalization.py, tests/parsing/test_parser.py, decisions.md, flow.md, handoff.md
- Symptom: Windows fatal exception: access violation in _span during deep cursor conversion; earlier incorrect columns caused ValueError containment failures.
- Root cause: Normalization accessed point metadata from native cursor-produced nodes on the installed Windows binding; this surface produced inconsistent coordinates and a fatal access violation, while direct native-child traversal reported consistent spans. Native internals are unknown.
- Regression test: tests/parsing/test_parser.py::ParserTests.test_deep_native_tree_normalization_does_not_use_python_recursion.
- Supersedes: D-025

### D-027: Compare an earlier runtime after native point-read crashes
- Date / phase / commit: 2026-10-08, Phase 1.1, 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168
- Context: Child-object traversal also crashed. A minimal native loop calling _span, and another retaining Point objects explicitly, reproduced Windows fatal exception: access violation without normalized nodes. The cursor-only diagnosis in D-026 was insufficient.
- Decision: Replace the runtime pin with tree-sitter==0.25.2, an available version reported by pip index, and verify the same three grammars and deep regression before completion. Keep direct child traversal and strict coordinate validation.
- Why: Failure occurs in native point access independently of conversion strategy. Runtime comparison tests compatibility instead of guessing a Python workaround. Exact native internals remain unknown.
- Alternatives considered: TreeCursor and immediate snapshots both failed under 0.26.0; relaxing coordinates or reducing regression depth hides the defect; native exception handling cannot catch access violations safely.
- Consequences: The current/latest runtime is not automatically the compatible choice. Future upgrades must repeat deep/native point tests on Windows. The grammar pins remain unchanged.
- Files: pyproject.toml, src/arctrellis/parsing/normalization.py, tests/parsing/test_parser.py, README.md, decisions.md, flow.md, handoff.md
- Package: tree-sitter ==0.25.2
- Why this package: Retains the required parser API while allowing an observed native compatibility comparison.
- Packages compared: tree-sitter 0.26.0 (native point access crashed) and 0.25.2 (compatibility must be verified); bundled grammars remain unnecessary.
- Symptom: Windows fatal exception: access violation in direct native point-reading loops and parser normalization.
- Root cause: The installed 0.26.0 native binding's point-access surface crashes on this Windows/Python environment for deep source; internal cause unknown. It is not limited to TreeCursor.
- Regression test: tests/parsing/test_parser.py::ParserTests.test_deep_native_tree_normalization_does_not_use_python_recursion.
- Supersedes: D-017, D-026

### D-028: Compare and hash normalized trees iteratively
- Date / phase / commit: 2026-10-08, Phase 1.1, 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168
- Context: Independent review identified recursive dataclass equality/hash despite iterative normalization and traversal.
- Decision: Use iterative SyntaxNode equality over corresponding ordered children and iterative preorder hashing with child counts. Preserve immutable value semantics without a depth cap.
- Why: Repeated parse values must compare equal even for deep inputs; generation must not rely on Python recursion depth.
- Alternatives considered: Restricting comparison depth weakens determinism; canonical serialization adds an unnecessary framework; identity equality loses value semantics.
- Consequences: Comparison/hash costs O(nodes); hashes are ordinary Python runtime hashes, not canonical source identities.
- Files: src/arctrellis/parsing/models.py, tests/parsing/test_parser.py, decisions.md, flow.md, handoff.md
- Symptom: Deep trees can trigger RecursionError under generated equality/hash.
- Root cause: Generated dataclass methods recursively compare/hash child tuples.
- Regression test: tests/parsing/test_parser.py::ParserTests.test_deep_repeated_parse_equality_and_hashing_do_not_recurse.

### D-029: Enforce final Windows path containment before filesystem access
- Date / phase / commit: 2026-10-08, Phase 1.1, 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168
- Context: Review identified nested drive-bearing components in caller-created DiscoveredFile paths. A reproduction accepted src/D:/outside/a.py and joined it to D:outside\a.py from C:/repo.
- Decision: Reject drive-bearing individual components at the parser read boundary and require the constructed target to be relative to the normalized root before any metadata/open calls. Preserve ingestion semantics; parsing adds its own read safety checks.
- Why: Static root escape is a preventable input-validation defect, separate from the documented concurrent filesystem limitation.
- Alternatives considered: Modifying ingestion is unnecessary for safe reads in this phase; ancestor checks without final containment could inspect another drive; relying on eventual access failure is unsafe.
- Consequences: Parser file reads impose stricter component safety than inventory records where Windows path construction is relevant.
- Files: src/arctrellis/parsing/source.py, tests/parsing/test_parser.py, decisions.md, flow.md, handoff.md
- Symptom: A nested D: component resets Windows path construction outside C:/repo.
- Root cause: The inventory validator checks the full string anchor, while joinpath interprets later components as drive instructions; the reader lacked a final containment check.
- Regression test: tests/parsing/test_parser.py::ParserTests.test_nested_drive_component_cannot_escape_root_or_trigger_io.

### D-030: Keep annotation-only native types out of runtime imports
- Date / phase / commit: 2026-10-08, Phase 1.1, 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168
- Context: Review found normalization importing native Node solely for annotations before parser initialization error handling.
- Decision: Postpone normalization annotations and import Node only under TYPE_CHECKING; load runtime/grammars inside _new_parser where failures are chained as ParserConfigurationError.
- Why: Public normalized models remain importable without native initialization; missing dependencies must use the intended caller-facing error.
- Alternatives considered: Eager annotation imports bypass typed errors; broad import-error swallowing hides real failures.
- Consequences: Private normalization annotations resolve native types only in type-checking contexts. No native object is exposed publicly.
- Files: src/arctrellis/parsing/normalization.py, tests/parsing/test_parser.py, decisions.md, flow.md, handoff.md
- Symptom: Missing runtime fails public parsing import before a parse call can report ParserConfigurationError.
- Root cause: An annotation-only from tree_sitter import Node ran at module import time outside the registry's exception boundary.
- Regression test: tests/parsing/test_parser.py::ParserTests.test_missing_native_runtime_becomes_typed_configuration_error.

### D-031: Finalize verified parser compatibility and accurate call ownership
- Date / phase / commit: 2026-10-08, Phase 1.1, 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168
- Context: Runtime comparison and review corrections require final evidence; flow review found parser containment checks placed in the discovery call tree.
- Decision: Retain the D-027 runtime/grammar pins after successful parser and full-suite verification. Record the failed 0.26.0 approaches and final results in handoff.md; place PureWindowsPath and Path.relative_to only under parsing _read_source in flow.md. Finalize implementation hashes separately under D-004.
- Why: The parser suite ran 37 tests, OK (skipped=1); the full suite ran 164 tests, OK (skipped=7). pip show verified runtime 0.25.2 and grammars 0.25.0/0.25.0/0.23.2; pip check reported no broken requirements. Public imports succeeded and the real scan-to-parse smoke printed app.py module 0. Source inspection confirms containment calls belong to parsing/source.py, not ingestion/discovery.py.
- Alternatives considered: Recording intended compatibility without tests would violate the evidence requirement; changing ingestion to match misplaced documentation would change stable semantics unnecessarily.
- Consequences: Windows symlink privilege skips and concurrent replacement/native resource limitations remain explicit. Runtime upgrades must repeat the deep regression. Earlier entries describe attempts when made; D-027 and this entry establish the final verified outcome.
- Files: decisions.md, flow.md, handoff.md
- Symptom: flow.md attributed PureWindowsPath and Path.relative_to to ingestion _normalize_root although those calls exist only in parsing _read_source.
- Root cause: The documentation patch matched the first repeated os.path.abspath call line rather than the parser section.
- Regression test: none; documentation-only correction verified against src/arctrellis/parsing/source.py and src/arctrellis/ingestion/discovery.py.

### D-032: Add the missing optional declaration signature compatibly
- Date / phase / commit: 2026-10-08, Phase 1.2, 4981f258ea312e254e9c4de4b34f3f3068e71a03
- Context: Inspection verified CodeEntity has no signature field although Phase 1.2 explicitly requires CodeEntity.signature. Existing callers use positional metadata as the eighth argument.
- Decision: Add optional signature as the final field, default None; validate nonempty unpadded strings while permitting internal newlines. Add a regression covering existing positional construction and signature validation.
- Why: A final optional field preserves existing constructor positions and satisfies the requested canonical signature API.
- Alternatives considered: Metadata-only signatures do not provide the requested field; inserting before metadata breaks existing callers; a separate Python entity model breaks the canonical boundary.
- Consequences: Primitive entity conversion includes signature; older instances have None. Existing graph and parsing semantics need no change.
- Files: src/arctrellis/core/models.py, tests/core/test_models.py, README.md, decisions.md, flow.md, handoff.md

### D-033: Centralize revision-deterministic identity and validated extraction results
- Date / phase / commit: 2026-10-08, Phase 1.2, 4981f258ea312e254e9c4de4b34f3f3068e71a03
- Context: Extraction is the first producer of canonical entity IDs and must retain scoped declarations without ambiguous ownership.
- Decision: Add extraction models, IDs, errors and public API. Use UUID5/NAMESPACE_URL over compact canonical JSON containing a versioned marker, language, path, kind, lexical qualified name and half-open byte span. ExtractionResult owns a module-first immutable entity tuple sorted by byte span/kind/ID, rejects duplicate IDs and invalid local parents, and retains partial status. Language uses the existing Language enum; the result vocabulary supports future supported-language extractors while this extractor accepts Python only.
- Why: Caller-independent deterministic identity and an explicit validated result can be reused without filesystem or native-parser dependencies.
- Alternatives considered: Random IDs and Python hash do not reproduce identities; delimiter concatenation is ambiguous; guessed Python package roots are unsupported; mutable results weaken ownership.
- Consequences: IDs are revision-deterministic, not edit-stable or namespaced across independent repositories. Module qualified name is the file path; declarations use path::lexical.names; imports use scope::import:binding@start_byte. Equal names at different spans remain separate.
- Files: src/arctrellis/extraction/__init__.py, src/arctrellis/extraction/models.py, src/arctrellis/extraction/ids.py, src/arctrellis/extraction/errors.py, tests/extraction/__init__.py, tests/extraction/test_models.py, tests/extraction/test_ids.py, README.md, decisions.md, flow.md, handoff.md

### D-034: Interpret verified normalized Python grammar with semantic scope
- Date / phase / commit: 2026-10-08, Phase 1.2, 4981f258ea312e254e9c4de4b34f3f3068e71a03
- Context: Normalized samples verified async uses function_definition, decorators wrap a definition field, and imports expose repeated name fields plus module_name and wildcard_import.
- Decision: Add an iterative Python extractor that carries nearest semantic parent through control syntax. Emit only MODULE, CLASS, FUNCTION, METHOD and one IMPORT per binding. Classes determine immediate method scope; decorated wrappers supply locations/numbered decorator metadata without duplicate extraction. Keep six exact span coordinates as string metadata and async state. Import metadata retains form/module/imported name/alias/binding/relative level/wildcard state without resolution.
- Why: Syntax-parent-only classification fails class control flow and nested functions; field-based grammar interpretation was observed directly through ArcTrellis SyntaxNode samples.
- Alternatives considered: Raw native imports break isolation; ast as primary parser contradicts the shared boundary; whole-statement imports lose binding units; runtime reflection executes target code.
- Consequences: No variables, lambdas, graph edges, reference entities, test/endpoint classification or resolution is produced. Extraction reads only already-owned normalized syntax and bytes.
- Files: src/arctrellis/extraction/python.py, src/arctrellis/extraction/imports.py, tests/extraction/test_python.py, tests/extraction/test_imports.py, README.md, decisions.md, flow.md, handoff.md

### D-035: Decode owned Python bytes and conservatively exclude recovery declarations
- Date / phase / commit: 2026-10-08, Phase 1.2, 4981f258ea312e254e9c4de4b34f3f3068e71a03
- Context: Signatures/names need encoding-aware decoding, and malformed source must not yield speculative semantic identity.
- Decision: Detect source encoding with tokenize.detect_encoding, validate full decoding, and decode exact byte slices with that encoding. Preserve declaration headers through a token-based top-level colon boundary, including multiline annotations but excluding decorators/body/comments after the header colon. Precompute subtree recovery state iteratively; skip any candidate declaration/import or decorated wrapper containing ERROR/MISSING descendants and do not traverse that rejected semantic scope. Mark partial from parser diagnostics or observed recovery/skips. Use explicit decoding, wrong-language and semantic-boundary exceptions.
- Why: Encoding detection is standard-library data inspection; tokenize is only a header delimiter helper, not a second semantic parser. One recovery prepass avoids repeated subtree scans.
- Alternatives considered: UTF-8-only decoding ignores Python cookies; guessing incomplete names invents facts; retaining descendants of skipped semantic parents misstates lexical ownership; recursive traversal fails deep input.
- Consequences: A malformed body can exclude an otherwise valid enclosing declaration and its descendants. Unaffected siblings survive. Non-UTF-8 syntax remains limited by the existing byte parser; no all-encodings guarantee is made. SourceLocation excludes exclusive end-line column zero while empty modules retain line 1.
- Files: src/arctrellis/extraction/source.py, src/arctrellis/extraction/python.py, src/arctrellis/extraction/errors.py, tests/extraction/test_python.py, README.md, decisions.md, flow.md, handoff.md

### D-036: Use local contract tests and literal scripts for grammar inspection
- Date / phase / commit: 2026-10-08, Phase 1.2, 4981f258ea312e254e9c4de4b34f3f3068e71a03
- Context: The baseline ran 164 tests, OK (skipped=7). The first inline grammar inspection failed with SyntaxError: unterminated string literal due to PowerShell quote handling.
- Decision: Retry temporary grammar inspection through a literal here-string piped to Python stdin; add local extraction, identity, import and result tests before implementation. Keep existing dependencies and the environment unchanged. Preserve failed inspection history and finalize local commit references under D-004.
- Why: The retry printed actual normalized kinds/fields for all required samples, with zero diagnostics; no permanent debug file or target execution is needed.
- Alternatives considered: Escaping nested shell quotes is fragile; committing debug fixtures adds no public capability; external repositories are unnecessary.
- Consequences: Platform skips remain explicit. The failed command was a temporary inspection quoting error, not an ArcTrellis defect.
- Files: tests/extraction/__init__.py, tests/extraction/test_ids.py, tests/extraction/test_models.py, tests/extraction/test_python.py, tests/extraction/test_imports.py, decisions.md, flow.md, handoff.md

### D-037: Postpone the source helper's self-referential annotation
- Date / phase / commit: 2026-10-08, Phase 1.2, 4981f258ea312e254e9c4de4b34f3f3068e71a03
- Context: The first extraction implementation run failed all four test imports before running semantic assertions.
- Decision: Postpone annotations in extraction/source.py, matching the established Python 3.13 forward-reference approach.
- Why: _PythonSource.from_parsed names its own not-yet-created class in a return annotation.
- Alternatives considered: Quoting that single name also works; removing the annotation loses useful typing.
- Consequences: No extraction behavior changes; public imports now reach the actual semantic tests.
- Files: src/arctrellis/extraction/source.py, tests/extraction/test_python.py, decisions.md, flow.md, handoff.md
- Symptom: NameError: name '_PythonSource' is not defined; extraction suite FAILED (errors=4).
- Root cause: Python 3.13 eagerly evaluated the classmethod return annotation during class definition.
- Regression test: tests/extraction/test_python.py::PythonExtractionTests.test_empty_module_has_path_identity_and_inclusive_location and all extraction public-import tests.

### D-038: Verify empty-suite recovery and encoding limits explicitly
- Date / phase / commit: 2026-10-08, Phase 1.2, 4981f258ea312e254e9c4de4b34f3f3068e71a03
- Context: Additional probes showed def f(): followed by a newline has an empty body with no parser diagnostics. A Latin-1 identifier produced two parser diagnostics although decoding succeeds.
- Decision: Retain conservative empty-body skipping and partial status; add tests for diagnostic-free empty suites, missing names/recovery flags, canonical serialization and the native non-UTF-8 identifier limitation.
- Why: Absence of parser diagnostics is not proof of a structurally complete declaration. Parsing remains the syntax boundary; extraction does not re-encode or reparse.
- Alternatives considered: Changing parser encoding semantics expands scope; decoding names cannot repair native recovery; unnamed declarations would invent identity.
- Consequences: partial can indicate a structural skip without parser diagnostics. UTF-8/BOM and Latin-1 literals are tested separately from native identifier limitations; no compiler-validity or all-encodings claim exists.
- Files: tests/extraction/test_python.py, README.md, decisions.md, flow.md, handoff.md

### D-039: Retry a rejected documentation patch with actual context
- Date / phase / commit: 2026-10-08, Phase 1.2, 4981f258ea312e254e9c4de4b34f3f3068e71a03
- Context: A combined test/documentation patch failed with apply_patch verification failed: Failed to find expected lines in C:\Projects\ArcTrellis\README.md: No numeric classification. Search confirmed its added tests and D-038 were absent.
- Decision: Retry using the inspected README paragraphs and separate supported contexts.
- Why: The rejected atomic patch changed no files; the expected line was part of a longer existing line.
- Alternatives considered: none.
- Consequences: Keep edit failures distinct from repository behavior and verify documentation context before patching.
- Files: README.md, decisions.md, flow.md

### D-040: Preserve lambda return annotation colons in declaration signatures
- Date / phase / commit: 2026-10-08, Phase 1.2, 4981f258ea312e254e9c4de4b34f3f3068e71a03
- Context: Independent review and a local literal-byte probe reproduced a truncated signature with zero syntax diagnostics.
- Decision: Select the final depth-zero operator colon in the already-bounded declaration header, ignoring colons inside brackets, strings and comments.
- Why: The first depth-zero colon can belong to an unparenthesized lambda return annotation; the declaration delimiter is the final one before its body.
- Alternatives considered: A full signature parser is unnecessary; accepting truncated text loses exact source evidence; raw rfind would misread comment/string colons.
- Consequences: tokenize remains only a header-boundary helper. The entire header token stream is inspected before returning the exact slice.
- Files: src/arctrellis/extraction/source.py, tests/extraction/test_python.py, README.md, decisions.md, flow.md, handoff.md
- Symptom: def f() -> lambda: int produced signature def f() -> lambda and partial=False.
- Root cause: signature() returned immediately at the first depth-zero colon, including lambda annotation delimiters.
- Regression test: tests/extraction/test_python.py::PythonExtractionTests.test_lambda_return_annotation_keeps_internal_top_level_colons.

### D-041: Include normalized future-import binding declarations
- Date / phase / commit: 2026-10-08, Phase 1.2, 4981f258ea312e254e9c4de4b34f3f3068e71a03
- Context: Review reproduced from __future__ import annotations yielding only MODULE with partial=False. Inspection verified future_import_statement and repeated name fields, with no module_name field.
- Decision: Include future_import_statement in recovery checks/import dispatch and assign its grammar-defined __future__ module explicitly, reusing per-binding alias metadata.
- Why: These are actual source import declarations. The grammar's anonymous module token would otherwise silently disappear.
- Alternatives considered: Ignoring future imports violates the import inventory; runtime feature evaluation is out of scope; modifying normalized punctuation retention is unnecessary.
- Consequences: Future feature validity/placement is not compiler-validated; declarations are recorded without runtime activation or resolution.
- Files: src/arctrellis/extraction/python.py, src/arctrellis/extraction/imports.py, tests/extraction/test_imports.py, README.md, decisions.md, flow.md, handoff.md
- Symptom: Future imports were omitted with a complete result despite valid normalized syntax.
- Root cause: The extractor only dispatched import_statement/import_from_statement, and the binding helper required module_name for every from form.
- Regression test: tests/extraction/test_imports.py::ImportTests.test_future_imports_use_their_anonymous_module_token_without_resolution.

### D-042: Align header offsets with tokenizer newline coordinates
- Date / phase / commit: 2026-10-08, Phase 1.2, 4981f258ea312e254e9c4de4b34f3f3068e71a03
- Context: Review recheck found cleanly parsed headers containing U+2028 or form-feed produce truncated signatures.
- Decision: Compute decoded header row offsets only from actual newline characters, matching StringIO.readline/tokenize, rather than str.splitlines.
- Why: splitlines treats additional Unicode separators and form-feed as line breaks while tokenizer rows do not.
- Alternatives considered: Replacing separator characters loses exact source; ignoring column mapping cannot locate a multiline declaration colon.
- Consequences: Signature text retains the original separators. Header scanning remains linear and uses decoded character columns, separate from syntax byte columns.
- Files: src/arctrellis/extraction/source.py, tests/extraction/test_python.py, decisions.md, flow.md, handoff.md
- Symptom: A header with x: "a\u2028b" truncated inside the annotation; a form-feed header returned only def f(.
- Root cause: splitlines-derived row offsets disagree with newline-only tokenizer rows.
- Regression test: tests/extraction/test_python.py::PythonExtractionTests.test_signature_rows_use_only_newlines_not_unicode_separators_or_formfeeds.

### D-043: Record verified Python extraction and preserve local session continuity
- Date / phase / commit: 2026-10-08, Phase 1.2, 4981f258ea312e254e9c4de4b34f3f3068e71a03
- Context: Implementation and independent review corrections are complete; the next session needs verified boundaries and actual results.
- Decision: Rewrite all twelve handoff sections with extraction contracts, actual test outcomes, initial failures and encoding/recovery limitations. Keep dependency configuration, parsing, ingestion and graph unchanged; finalize implementation hashes separately under D-004 after local commits.
- Why: Extraction tests ran 31 tests with OK; the complete suite ran 196 tests, OK (skipped=7), including the original 164 tests and signature compatibility coverage. Public imports and scan/parse/extract smoke succeeded; pip check found no broken requirements; native-import source search found no matches. Review recheck found no remaining actionable issue.
- Alternatives considered: Reporting only successes loses debugging context; claiming arbitrary encoding support exceeds the tested parser; moving to Phase 1.3 now exceeds scope.
- Consequences: Six symlink and one FIFO tests remain platform skips from previous phases. Conservative recovery can omit enclosing scopes; identities are not edit-stable or repository-global. All work remains local.
- Files: README.md, decisions.md, flow.md, handoff.md

### D-044: Extend canonical extraction through one normalized JS/TS engine
- Date / phase / commit: 2026-10-08, Phase 1.3, 66d881e02bcb52e467720b39293319ff7595f085
- Context: All v1 languages need common entities before lexical graph assembly; inspected normalized samples expose common declaration, binding and method fields.
- Decision: Add JS/TS entry points and a small canonical-language dispatcher, reusing ExtractionResult, UUID5 identity and six-coordinate metadata. Use iterative nearest-scope traversal and strict UTF-8 decoding. Keep Python behavior and dependency pins unchanged.
- Why: Actual samples verified declarations, async/generators, callable bindings, class fields, export wrappers and TS decorator siblings without target execution. Baseline: 196 tests, OK (skipped=7).
- Alternatives considered: Separate duplicated TS traversal adds maintenance cost; raw parser types violate isolation; a large Python refactor is unnecessary.
- Consequences: Single-file transformation only; no variables, object methods, anonymous unbound scopes, framework semantics or resolution. Interfaces/type aliases/enums remain syntax-only. IDs remain revision-deterministic and not repository-namespaced.
- Files: src/arctrellis/extraction/javascript.py, src/arctrellis/extraction/__init__.py, tests/extraction/test_javascript.py, README.md, decisions.md, flow.md

### D-045: Preserve callable declarations, modifiers and static import sites
- Date / phase / commit: 2026-10-08, Phase 1.3, 66d881e02bcb52e467720b39293319ff7595f085
- Context: JS/TS use callable variable/class-field bindings, anonymous expressions, export wrappers and ES import clauses that differ from Python.
- Decision: Add a shared iterative JS/TS engine with simple identifier-bound functions/classes and class callable fields. Preserve signatures as exact binding/declaration headers before body, numbered decorators and export/modifier metadata. Anonymous unbound scopes and object methods are omitted without traversing their bodies. Type declarations remain syntax-only. Import bindings preserve default/named/namespace/side-effect/type-only forms. Statically obvious simple require calls are recorded as unresolved syntactic import sites.
- Why: Normalized inspections verified fields and TS class-body decorator siblings. The test-first public API assertion failed because extract_entities was absent; the initial implemented JS/TS suite ran 24 tests, OK.
- Alternatives considered: Inventing anonymous names or classes for object literals creates unsupported semantic claims; collapsing import statements loses bindings; duplicate JS/TS traversals add maintenance; dynamic require needs resolution outside scope.
- Consequences: ES module metadata retains exact string interior plus quoted module_literal with module_format=source_spelling, not evaluated escape sequences. Require accepts one unescaped static quoted string and a simple identifier callee/binding only; no assertion is made that require is unshadowed at runtime. Callable binding headers omit const/let/var; bodies and decorators are excluded. Shared coordinate helpers are reused without changing Python semantics.
- Files: src/arctrellis/extraction/javascript.py, src/arctrellis/extraction/es_imports.py, src/arctrellis/extraction/__init__.py, tests/extraction/test_javascript.py, README.md, decisions.md, flow.md

### D-046: Limit modifier scans to their actual declaration prefixes
- Date / phase / commit: 2026-10-08, Phase 1.3, 66d881e02bcb52e467720b39293319ff7595f085
- Context: Independent review reproduced static callable-field and decorated export metadata errors in cleanly parsed source.
- Decision: Scan static field modifiers on the field container and retain its header prefix; exclude decorator nodes from export/member modifier prefixes.
- Why: Both focused regressions initially failed; after correction the JS/TS suite ran 26 tests, OK.
- Alternatives considered: Searching entire source snippets can confuse decorator arguments and bodies with declaration modifiers; removing metadata loses useful source facts.
- Consequences: Callable-field signatures preserve static/access modifiers; async/generator still come from the callable initializer. No runtime decorator evaluation occurs.
- Files: src/arctrellis/extraction/javascript.py, tests/extraction/test_javascript.py, README.md, decisions.md, flow.md
- Symptom: static run = () => {} reported is_static=false; @dec(default) export class C reported is_default_export=true.
- Root cause: Static metadata inspected only the initializer, while export scanning included the decorator argument prefix.
- Regression test: tests/extraction/test_javascript.py::JavaScriptExtractionTests.test_static_callable_field_preserves_member_modifiers and test_export_modifier_scan_excludes_decorator_arguments.

### D-047: Retain empty named import sites without false partial status
- Date / phase / commit: 2026-10-08, Phase 1.3, 66d881e02bcb52e467720b39293319ff7595f085
- Context: Review reproduced import {} from "m" returning partial=True despite clean syntax.
- Decision: Represent an empty named clause as one unbound side_effect import site, retaining type-only state if present, and no fabricated binding. Add literal-spelling coverage.
- Why: The focused empty-import regression failed before this correction. A static module import site remains present even when there are no named bindings.
- Alternatives considered: Omitting the site with a complete result loses the module declaration; treating valid empty syntax as malformed is inaccurate; inventing a local binding is false.
- Consequences: side_effect describes an unbound source import site, not a guarantee of runtime execution, especially for type-only TS clauses.
- Files: src/arctrellis/extraction/es_imports.py, tests/extraction/test_javascript.py, README.md, decisions.md, flow.md
- Symptom: Clean empty named import returned partial=True and no IMPORT entity.
- Root cause: _es_imports used tuple(bindings) or None, conflating a valid zero-binding clause with invalid structure.
- Regression test: tests/extraction/test_javascript.py::JavaScriptImportTests.test_empty_named_import_is_a_complete_unbound_site.

### D-048: Restore historical decision boundaries after an insertion-context error
- Date / phase / commit: 2026-10-08, Phase 1.3, 66d881e02bcb52e467720b39293319ff7595f085
- Context: Documentation review found D-044 insertion had split D-010, and moving the entry also moved D-010's three bug-detail lines.
- Decision: Restore the complete historical prefix from HEAD and append only the new entries; inspect the resulting diff before commit.
- Why: Previous decisions must remain unchanged. The editing error affected only acfd6093f95e0f9dd6b150ad625cb5ab6fee4a79 documentation, not source behavior or Git history.
- Alternatives considered: Manually rewriting historical entries risks further changes; retaining misplaced bug context is inaccurate.
- Consequences: Append-only history remains intact; patch contexts must use the actual end of the decisions file.
- Files: decisions.md, flow.md
- Symptom: D-044 incorrectly contained the Phase 0.2 table bug's symptom/root cause/regression lines.
- Root cause: An ambiguous Files context inserted D-044 before D-010's trailing lines; moving through the next heading included those lines.
- Regression test: none; documentation-only correction checked by git diff against HEAD.

### D-049: Require actual class-body membership before extracting methods
- Date / phase / commit: 2026-10-08, Phase 1.3, 66d881e02bcb52e467720b39293319ff7595f085
- Context: Review found clean JS/TS object methods inside class static blocks incorrectly emitted as class methods.
- Decision: Index direct normalized class-body method members iteratively and require membership as well as CLASS semantic parent before emitting METHOD. Continue omitting object methods and their bodies.
- Why: The focused regression failed with extra METHOD/FUNCTION entities before correction; the updated JS/TS suite ran 29 tests, OK.
- Alternatives considered: Nearest semantic scope alone is insufficient to distinguish class syntax from object syntax; representing object/value ownership needs a future model.
- Consequences: Static blocks may retain represented declarations, but embedded object methods never fabricate class membership. The membership pass is linear and stores only temporary identities.
- Files: src/arctrellis/extraction/javascript.py, tests/extraction/test_javascript.py, decisions.md, flow.md
- Symptom: class C { static { use({ run() { function hidden() {} } }); } } produced METHOD C.run and FUNCTION C.run.hidden, partial=False.
- Root cause: Method recognition checked parent.kind=CLASS without checking the actual normalized method's class-body membership.
- Regression test: tests/extraction/test_javascript.py::JavaScriptExtractionTests.test_object_methods_inside_class_static_blocks_are_not_class_methods.

### D-050: Close the verified JS/TS gate before lexical graph work
- Date / phase / commit: 2026-10-08, Phase 1.3, 66d881e02bcb52e467720b39293319ff7595f085
- Context: Phase 1.4 is authorized only after Phase 1.3 passes its full regression gate and local commit finalization.
- Decision: Preserve unchanged dependencies/stable layers, record review regressions and actual verification, and finalize local feature references separately under D-004 before starting the graph builder.
- Why: JS/TS tests ran 29 tests, OK; full suite ran 225 tests, OK (skipped=7). Public imports and JS/TSX scan/parse/extract smoke succeeded, pip check reported no broken requirements, and extraction native-import search had no matches. Focused review recheck found no unresolved important issue.
- Alternatives considered: Continuing with an unverified feature risks propagating semantic mistakes; publishing is explicitly prohibited.
- Consequences: Existing platform skips, native parser resource limits and revision/repository identity limitations remain. Only single-file lexical assembly may follow.
- Files: README.md, decisions.md, flow.md, handoff.md

### D-051: Assemble single-file lexical graphs with proven DEFINES evidence
- Date / phase / commit: 2026-10-08, Phase 1.4, ec887ee7426340589582ae618aa4e7751a89c0f5
- Context: All v1 language extractors passed the Phase 1.3 gate and local commit/reference finalization; canonical parent IDs can now prove lexical ownership.
- Decision: Add build_lexical_graph under extraction, consuming one validated ExtractionResult and returning a fresh CodeGraph. Insert every entity first; generate exactly one parent-to-child DEFINES edge per non-module entity, Confidence.PROVEN and score 1.0. Embed child declaration SourceLocation and six exact coordinates under lexical_parentage.
- Why: This boundary transforms extraction output without introducing repository indexing policy or changing graph storage/traversal semantics. Parent IDs explicitly establish lexical ownership; endpoint insertion first respects existing graph integrity.
- Alternatives considered: Emitting CONTAINS too duplicates the fact; IMPORTS would confuse import sites with resolved dependencies; mutating a caller graph introduces merge policy; a new vague analysis package is unnecessary.
- Consequences: Imports receive DEFINES only. The module has no fabricated repository parent. Partial extraction can supply proven surviving edges; callers retain ExtractionResult.partial because CodeGraph does not carry file-level status. No resolution, calls or framework inference exists.
- Files: src/arctrellis/extraction/lexical.py, src/arctrellis/extraction/__init__.py, tests/extraction/test_lexical.py, README.md, decisions.md, flow.md, handoff.md

### D-052: Give lexical relationships and proof records versioned deterministic IDs
- Date / phase / commit: 2026-10-08, Phase 1.4, ec887ee7426340589582ae618aa4e7751a89c0f5
- Context: Source-derived graph edges and evidence must reproduce without random IDs, while producer invariant violations must fail before returning a graph.
- Decision: Use UUID5/NAMESPACE_URL over compact JSON. Evidence key includes its version marker, lexical_parentage, parent/child IDs, child file/inclusive lines and ordered six-coordinate metadata. Relationship key includes its own marker, DEFINES, parent/child IDs and evidence ID. Revalidate ExtractionResult before assembly; chain invalid result data as SemanticExtractionError.
- Why: This matches the existing entity identity strategy without changing it. The test-first public builder assertion failed before implementation; proof tests verify UUID5, repeatable snapshots and changed source identity.
- Alternatives considered: Random IDs/hash break reproducibility; entity-only evidence keys discard exact span context; silent parent skipping creates false partial graphs; external graph storage exceeds scope.
- Consequences: IDs inherit revision/repository namespace limits from entity IDs. Child snippets/source contents are not copied into Evidence; locations and exact spans point to evidence already owned by callers. CodeGraph remains mutable with its existing insertion costs. Decoding exception documentation now describes both language policies.
- Files: src/arctrellis/extraction/lexical.py, src/arctrellis/extraction/__init__.py, src/arctrellis/extraction/errors.py, tests/extraction/test_lexical.py, README.md, decisions.md, flow.md, handoff.md

### D-053: Supply package context for standalone graph regression discovery
- Date / phase / commit: 2026-10-08, Phase 1.4, ec887ee7426340589582ae618aa4e7751a89c0f5
- Context: The standalone graph invocation failed imports even though the complete suite was green.
- Decision: Run graph discovery with -s tests/graph -t . so relative fixture imports retain their package context; change no graph/test semantics.
- Why: The first command failed three imports with ImportError: attempted relative import with no known parent package. The corrected command ran 56 tests, OK.
- Alternatives considered: Rewriting existing relative imports is unnecessary; hiding the failed command loses honest verification history.
- Consequences: Use the explicit top-level directory for standalone graph discovery. This was an invocation error, not a production defect.
- Files: decisions.md, flow.md, handoff.md

### D-054: Finalize multilingual proof verification and bounded session handoff
- Date / phase / commit: 2026-10-08, Phase 1.4, ec887ee7426340589582ae618aa4e7751a89c0f5
- Context: Both authorized phases need checked final state, regression evidence and a clear stop before repository-wide indexing.
- Decision: Record actual multilingual graph/proof smoke, independent review, full regression/skip reasons and local identity audits. Strengthen the existing JS/TS pipeline fixture with a top-level marker-writing source statement whose marker must remain absent. Rewrite all twelve handoff sections and finalize local hashes under D-004.
- Why: JS/TS suite ran 29 tests, lexical suite 11, all extraction 71, graph 56 and complete suite 236, OK (skipped=7). The marker fixture passes without execution. The graph smoke verified service.ts::Service DEFINES service.ts::Service.create with service.ts lines 1..1, lexical_parentage, PROVEN/1.0. Independent lexical review found no critical or important findings.
- Alternatives considered: Repository-wide merging begins Phase 1.5 and is explicitly unauthorized here; claiming real symlink coverage despite privilege skips would be false.
- Consequences: Stop after Phase 1.4; preserve native/race, encoding, conservative omission and identity limitations. No dependencies, remotes, publication or stable-layer changes are needed.
- Files: tests/extraction/test_javascript.py, README.md, decisions.md, flow.md, handoff.md

### D-055: Index supported source files with explicit outcomes and bounded ownership
- Date / phase / commit: 2026-10-08, Phase 1.5, acfd6093f95e0f9dd6b150ad625cb5ab6fee4a79
- Context: Single-file semantics are verified; repository analysis needs explicit completeness without retaining all syntax/source bytes.
- Decision: Add indexing FileIndexStatus, FileIndexResult, RepositoryIndexResult and index_repository. Process inventory order synchronously; per-file helper releases ParsedSource after returning summary/semantic graph. Record typed source/extraction failures as FAILED with bounded stage/type text, never exception objects or source-derived exception messages. Discovery failures and graph collisions abort.
- Why: Baseline ran 236 tests, OK (skipped=7). The user requires best-effort file analysis and explicit fatal invariants. Indexing tests ran 10 tests OK; full suite ran 246 tests OK (skipped=7). Mixed smoke: five complete supported files, zero partial/failed, 17 entities, 12 relationships; excluded node_modules and unsupported README stay outside the graph.
- Alternatives considered: Fail-fast per source loses unaffected files; silent skips misstate completeness; retaining syntax trees increases repository memory; concurrency/index persistence exceeds scope.
- Consequences: Summary records are frozen but the owned CodeGraph retains its existing mutable API. COMPLETE has no recovery, PARTIAL follows extraction.partial (including structural omissions), FAILED adds no graph records. Unsupported files stay inventory-only.
- Files: src/arctrellis/indexing/__init__.py, src/arctrellis/indexing/models.py, src/arctrellis/indexing/repository.py, src/arctrellis/indexing/errors.py, tests/indexing/__init__.py, tests/indexing/test_repository.py, README.md, decisions.md, flow.md

### D-056: Add path-based FILE identities and proven file-to-module membership
- Date / phase / commit: 2026-10-08, Phase 1.5, acfd6093f95e0f9dd6b150ad625cb5ab6fee4a79
- Context: A merged graph needs source-file structural roots without inventing repository identity.
- Decision: Use UUID5/NAMESPACE_URL with compact versioned JSON for FILE language/path identity, independent of byte positions. FILE nodes are parentless, location-free and retain analyzed size_bytes. Add one PROVEN/1.0 FILE DEFINES MODULE edge with file_module_membership evidence from module root coordinates; merge existing lexical records through CodeGraph APIs.
- Why: FILE identity remains path-stable across source edits while existing declaration identity is revision-deterministic. Module evidence already exists; a repository root identity remains undefined.
- Alternatives considered: Absolute-root IDs depend on clone location; a constant repository ID collides; random IDs break reproducibility; modifying module.parent_id would break ExtractionResult semantics.
- Consequences: Graph membership connects FILE to the existing parentless MODULE without changing semantic records. IDs remain non-namespaced across repositories. File summary counts include FILE and its membership edge.
- Files: src/arctrellis/indexing/ids.py, src/arctrellis/indexing/repository.py, src/arctrellis/indexing/models.py, tests/indexing/test_repository.py, README.md, decisions.md, flow.md

### D-057: Resolve internal modules conservatively without runtime configuration
- Date / phase / commit: 2026-10-08, Phase 1.6, 300652d914eb811f8a0c13f6bb2333afd914c1ee
- Context: The repository index provides import sites and module paths but no runtime environment or package configuration.
- Decision: Add resolution package and resolve_imports returning a new graph plus immutable RESOLVED/UNRESOLVED/AMBIGUOUS decisions sorted by import ID. Python aliases derive from paths, __init__ files and an additional leading-src alias. Relative Python imports use each path-based package interpretation. JS/TS use safe matching quoted literals, only relative paths, exact supported extensions or the full extension/index candidate set. Multiple matches emit no edge. Unknown extensions, escapes, bare names and outside-root paths remain unresolved.
- Why: The user requires conservative static module dependencies without source re-reads or configuration evaluation. Test-first import failed with ModuleNotFoundError for the not-yet-created resolution package; implementation consumes graph metadata only. Final resolution suite ran 13 tests OK; full suite 259 tests OK (skipped=7). Mixed smoke returned resolved=2, unresolved=1, ambiguous=1 with identical rerun decisions/edges. Public imports and pip check passed. Independent review findings were reproduced and corrected in D-059 through D-061.
- Alternatives considered: Runtime imports execute untrusted code; choosing extension priority guesses compiler configuration; class/symbol resolution and arbitrary source roots exceed scope; labeling bare JS aliases external is not defensible.
- Consequences: No package exports, aliases, full Python sys.path/namespace behavior, transpiler extension rewriting or imported-symbol resolution. Literal spelling remains unchanged by extraction. Frozen summaries own an ordinary mutable graph; callers treat it as a snapshot.
- Files: src/arctrellis/resolution/__init__.py, src/arctrellis/resolution/models.py, src/arctrellis/resolution/catalog.py, src/arctrellis/resolution/imports.py, tests/resolution/__init__.py, tests/resolution/test_imports.py, README.md, decisions.md, flow.md

### D-058: Back module import edges with import-site evidence and likely confidence
- Date / phase / commit: 2026-10-08, Phase 1.6, 300652d914eb811f8a0c13f6bb2333afd914c1ee
- Context: A unique path match is static evidence rather than proof of runtime import behavior.
- Decision: Emit IMPORTS from the import entity lexical parent to the target MODULE, LIKELY/0.90. Preserve each site separately with versioned compact-JSON UUID5 identities using import ID, owner and target. Evidence uses import location and six existing syntax coordinates; methods are python_static_import_resolution and ecmascript_relative_import_resolution. Reuse indexing's small private _stable_id helper.
- Why: Separate sites preserve evidence integrity; local function/method imports must originate at their actual scope. Existing DEFINES records remain PROVEN and unchanged.
- Alternatives considered: PROVEN overstates environmental certainty; using IMPORT entity as source confuses dependency scope with evidence site; collapsing repeated imports loses proof sites.
- Consequences: Original index graph is copied via public APIs; unresolved and ambiguous imports add no target or edge. Identities remain revision-deterministic and not repository-namespaced. Invalid index invariants raise RepositoryIndexInvariantError.
- Files: src/arctrellis/resolution/imports.py, src/arctrellis/resolution/models.py, src/arctrellis/resolution/catalog.py, tests/resolution/test_imports.py, README.md, decisions.md, flow.md

### D-059: Keep candidate aliases faithful to path components and repository root
- Date / phase / commit: 2026-10-08, Phase 1.6, 300652d914eb811f8a0c13f6bb2333afd914c1ee
- Context: Review found edge cases in the new path catalog before its completion gate.
- Decision: Accept Python module alias components only when each is an identifier; build root directory index probes without a leading slash. Remove the unused modules argument from _python_candidates.
- Why: Root-index regression failed with AssertionError: 0 != 1. Separate dotted-filename smoke returned resolved=1, unresolved=0 for import pkg.util against pkg.util.py, an incorrect module-path interpretation.
- Alternatives considered: Treating dots inside one filename as directory boundaries is false; filesystem normalization would add unwanted I/O and OS dependence.
- Consequences: Root index candidates stay repository-relative; invalid Python path-component aliases remain unresolved rather than guessed.
- Files: src/arctrellis/resolution/catalog.py, src/arctrellis/resolution/imports.py, tests/resolution/test_imports.py, decisions.md, flow.md
- Symptom: Root ./ import missed index.js; pkg.util.py falsely matched dotted import pkg.util.
- Root cause: Empty normalized base was concatenated with /index; joining unvalidated path components with dots erased component boundaries.
- Regression test: tests/resolution/test_imports.py::ImportResolutionTests.test_root_index_and_python_literal_dot_filename

### D-060: Preserve directory intent in relative script specifiers
- Date / phase / commit: 2026-10-08, Phase 1.6, 300652d914eb811f8a0c13f6bb2333afd914c1ee
- Context: Independent review found a conservative-resolution false positive in trailing-slash imports.
- Decision: Relative specifiers ending in slash, dot or dot-dot probe only directory index candidates; ordinary extensionless names keep file and index probes.
- Why: The regression test failed twice with AssertionError: 0 != 1 for unresolved_count when ./service/ and ./service.js/ incorrectly matched service.js; an index plus sibling-file case also failed by becoming ambiguous.
- Alternatives considered: Marking all directory imports unresolved is safe but loses reliable unique index matches; discarding trailing directory intent incorrectly asserts a source-file dependency.
- Consequences: Normalization retains semantic path intent without filesystem access. Unique index dependencies remain LIKELY, not runtime proof.
- Files: src/arctrellis/resolution/catalog.py, tests/resolution/test_imports.py, decisions.md, flow.md
- Symptom: Directory-only import strings resolved a source file or became ambiguous with a sibling file.
- Root cause: Empty terminal path components were discarded before candidate probing, erasing directory intent.
- Regression test: tests/resolution/test_imports.py::ImportResolutionTests.test_directory_specifiers_do_not_match_files

### D-061: Defer URL-encoded specifiers and verify remaining catalog negatives
- Date / phase / commit: 2026-10-08, Phase 1.6, 300652d914eb811f8a0c13f6bb2333afd914c1ee
- Context: A quoted JS specifier may still carry loader-specific URL interpretation rather than a literal filesystem path.
- Decision: Reject percent-bearing relative literals as unsupported_specifier; add negative coverage for root/src alias ambiguity, excessive Python relative levels and terminal dot/dot-dot directory intent.
- Why: test_conservative_catalog_boundaries failed with AssertionError: 0 != 1 for import ./serv%69ce.js matching the percent-bearing filename. Direct spelling resolution would claim a dependency without loader semantics.
- Alternatives considered: URL decoding adds another resolution policy not requested; treating percent spelling as literal can yield a wrong target; defer these optional imports explicitly instead.
- Consequences: Percent-bearing specifiers remain unresolved, like query/fragment/escape/config-dependent cases. No runtime loader evaluation is introduced.
- Files: src/arctrellis/resolution/catalog.py, tests/resolution/test_imports.py, README.md, decisions.md, flow.md
- Symptom: URL-encoded module specifier matched a literal-percent filename.
- Root cause: Candidate filtering excluded query and fragment markers but allowed percent encoding without a loader policy.
- Regression test: tests/resolution/test_imports.py::ImportResolutionTests.test_conservative_catalog_boundaries

### D-062: Pin development-only Ruff and mypy for a reproducible quality gate
- Date / phase / commit: 2026-10-08, Quality Gate Q1, uncommitted
- Context: Multi-language indexing and resolution need lint, formatting and static typing in addition to runtime tests.
- Decision: Add optional dev extra with Ruff 0.16.10 and mypy 2.4.0; retain every existing runtime parser pin. Configure Python 3.13, Ruff E/F/I/UP/B/SIM with 120-column formatting, and mypy strict for src/arctrellis. Apply Ruff only to Python source/tests, not Markdown.
- Why: pip index versions reported ruff (0.16.10) and mypy (2.4.0) as currently available. Official Ruff configuration and mypy configuration documentation describe the selected pyproject interfaces. Editable base/dev installations succeeded. Installed versions were rechecked by pip show and version commands. Final Ruff lint/format, strict mypy (37 source files), compileall, pip check and full unittest suite (261 tests, skipped=7) all passed.
- Alternatives considered: Black plus Flake8/isort needs multiple competing formatter/lint packages; Ruff supplies both. Pyright is a valid alternative but mypy fits Python dataclass/annotation development and needs no Node tooling. Runtime tooling dependencies burden ordinary users. No CI is authorized.
- Consequences: Development tools are opt-in; no target dependencies are installed. Strict errors must be fixed without blanket suppressions. Tests and formatting share the documented 120-column convention.
- Files: pyproject.toml, src/arctrellis/extraction/__init__.py, src/arctrellis/extraction/es_imports.py, src/arctrellis/extraction/ids.py, src/arctrellis/extraction/imports.py, src/arctrellis/extraction/javascript.py, src/arctrellis/extraction/lexical.py, src/arctrellis/extraction/models.py, src/arctrellis/extraction/python.py, src/arctrellis/extraction/source.py, src/arctrellis/graph/graph.py, src/arctrellis/graph/results.py, src/arctrellis/indexing/__init__.py, src/arctrellis/indexing/ids.py, src/arctrellis/indexing/models.py, src/arctrellis/indexing/repository.py, src/arctrellis/ingestion/__init__.py, src/arctrellis/ingestion/discovery.py, src/arctrellis/ingestion/models.py, src/arctrellis/parsing/__init__.py, src/arctrellis/parsing/models.py, src/arctrellis/parsing/normalization.py, src/arctrellis/parsing/parser.py, src/arctrellis/parsing/registry.py, src/arctrellis/parsing/source.py, src/arctrellis/resolution/__init__.py, src/arctrellis/resolution/catalog.py, src/arctrellis/resolution/imports.py, src/arctrellis/resolution/models.py, tests/core/test_models.py, tests/extraction/test_ids.py, tests/extraction/test_imports.py, tests/extraction/test_javascript.py, tests/extraction/test_lexical.py, tests/extraction/test_models.py, tests/extraction/test_python.py, tests/graph/fixtures.py, tests/graph/test_graph.py, tests/graph/test_results.py, tests/graph/test_traversal.py, tests/indexing/test_repository.py, tests/ingestion/test_discovery.py, tests/ingestion/test_models.py, tests/ingestion/test_safety.py, tests/parsing/test_models.py, tests/parsing/test_parser.py, tests/parsing/test_registry.py, tests/resolution/test_imports.py, README.md, decisions.md, flow.md
- Package: ruff ==0.16.10; mypy ==2.4.0 (optional dev dependencies)
- Why this package: Ruff provides lint and formatting; mypy verifies annotations and type boundaries.
- Packages compared: Black, Flake8 and isort require separate components; Pyright was not chosen to keep the development tooling Python-oriented.

### D-063: Express validated type invariants without broad suppressions
- Date / phase / commit: 2026-10-08, Quality Gate Q1, uncommitted
- Context: Initial strict mypy reported 38 errors in nine files: missing generics/helper annotations, inferred empty-tuple work items, optional fields after independent validation, and an implicit constant re-export. Initial Ruff check fixed 36 issues and reported 98 remaining before formatting; post-format check reported 28 remaining.
- Decision: Add explicit typed traversal work items and private helper/source annotations, concrete generic record tuples, and type-narrowing invariant assertions at already-validated boundaries. Export the parser limit directly from its defining source module. Declare strict zip behavior where equal lengths are already required. Split long fixture strings without changing their bytes and combine equivalent nested test contexts. No global/per-module type suppressions or blanket casts.
- Why: Static tools should check the real contracts; broad ignores would hide defects. Existing tests cover the unchanged parser/extractor invariants and invalid inputs.
- Alternatives considered: ignore_errors, disabling strict checks or inserting mass type ignores contradict the requested quality gate; a large semantic refactor is unnecessary.
- Consequences: Runtime semantics for valid input remain unchanged; assertions document producer invariants, not target-code evaluation. Native library typing currently needs no suppression.
- Files: src/arctrellis/graph/results.py, src/arctrellis/ingestion/models.py, src/arctrellis/parsing/parser.py, src/arctrellis/parsing/__init__.py, src/arctrellis/parsing/models.py, src/arctrellis/extraction/models.py, src/arctrellis/extraction/es_imports.py, src/arctrellis/extraction/javascript.py, src/arctrellis/extraction/python.py, src/arctrellis/extraction/lexical.py, tests/core/test_models.py, tests/extraction/test_ids.py, tests/extraction/test_imports.py, tests/extraction/test_javascript.py, tests/extraction/test_lexical.py, tests/extraction/test_models.py, tests/extraction/test_python.py, tests/graph/fixtures.py, tests/graph/test_graph.py, tests/graph/test_results.py, tests/graph/test_traversal.py, tests/indexing/test_repository.py, tests/ingestion/test_discovery.py, tests/ingestion/test_models.py, tests/ingestion/test_safety.py, tests/parsing/test_models.py, tests/parsing/test_parser.py, tests/parsing/test_registry.py, tests/resolution/test_imports.py, decisions.md, flow.md

### D-064: Audit the native-parser boundary and document local quality commands
- Date / phase / commit: 2026-10-08, Quality Gate Q1, uncommitted
- Context: Static tooling should protect the normalized parsing boundary as new analysis stages are added.
- Decision: Add standard-library import inspection tests over ArcTrellis source, with positive/negative vectors proving native-import detection. Tree-sitter imports must remain inside parsing. Review source searches for execution mechanisms and the fixed grammar loader. Publish verified local development commands in README and flow; no CI.
- Why: Parsing owns native implementation types; extraction, indexing and resolution consume owned records. The audit parses only ArcTrellis test/development source with ast for inspection; it does not replace normalized target parsing or execute inspected source.
- Alternatives considered: Raw text-only import bans depend on formatting; testing target execution via actual target execution violates the boundary; CI and cross-platform claims are outside this session.
- Consequences: The architecture regression is tied to package boundaries rather than formatting. The native grammar loader remains a reviewed internal exception to dynamic module-loading searches.
- Files: tests/test_architecture.py, README.md, decisions.md, flow.md, handoff.md

### D-065: Finalize verified indexing, resolution and quality handoff
- Date / phase / commit: 2026-10-08, Quality Gate Q1, uncommitted
- Context: The bounded session must stop after all three gates and preserve reproducible continuation state.
- Decision: Rewrite the twelve handoff sections, record actual counts/commands/skip reasons, expand current capability/security/development documentation and finalize commit references separately under D-004. Retain conservative deferrals and stop before call-site extraction.
- Why: Baseline 236 tests progressed to 246 after indexing, 259 after resolution and 261 after Q1; all final runs passed with seven existing platform skips. Independent final review compared changed Python syntax against facc23e and found no critical/important issue; test fixtures/assertions remain intact. Package/API/isolation audits and all quality tools passed locally.
- Alternatives considered: Beginning call resolution exceeds authorization; claiming other operating systems or skipped link/FIFO coverage would be false; history rewriting for self-referential hashes is unnecessary.
- Consequences: Phase 1.7 requires a later authorized session. No remote, upload, publication, persistence, CI or target execution is introduced. Frozen summaries still own mutable graph instances and require snapshot discipline.
- Files: README.md, decisions.md, flow.md, handoff.md

### D-066: Preserve actual command contracts during final verification
- Date / phase / commit: 2026-10-08, Quality Gate Q1, uncommitted
- Context: Two auxiliary final audit invocations used incorrect command/input assumptions.
- Decision: Supply bytes to the indexing test fixture helper, and use the repository's normal git diff --check without disabling core.autocrlf. Leave persistent Git configuration unchanged and record the failed attempts.
- Why: A string-based fixture smoke failed with TypeError: memoryview: a bytes-like object is required, not 'str'. The corrected bytes smoke returned supported3, complete3, partial0, failed0, entities9, relationships6. git -c core.autocrlf=false diff --check compared raw CRLF worktree lines to normalized index lines and reported trailing whitespace throughout; normal git diff --check and staged check passed.
- Alternatives considered: Changing test helper input semantics or repository line-ending policy to accommodate mistaken audit commands would be unnecessary; ignoring failed commands would violate verification honesty.
- Consequences: No production/runtime behavior changed. Developer checks must respect actual fixture and Windows Git normalization contracts.
- Files: decisions.md, flow.md, handoff.md
