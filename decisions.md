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
- Why: Previous decisions must remain unchanged. The editing error affected only uncommitted documentation, not source behavior or Git history.
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
- Date / phase / commit: 2026-10-08, Quality Gate Q1, ec14dca7cf518a167dc42bd853c45d876c64cf26
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
- Date / phase / commit: 2026-10-08, Quality Gate Q1, ec14dca7cf518a167dc42bd853c45d876c64cf26
- Context: Initial strict mypy reported 38 errors in nine files: missing generics/helper annotations, inferred empty-tuple work items, optional fields after independent validation, and an implicit constant re-export. Initial Ruff check fixed 36 issues and reported 98 remaining before formatting; post-format check reported 28 remaining.
- Decision: Add explicit typed traversal work items and private helper/source annotations, concrete generic record tuples, and type-narrowing invariant assertions at already-validated boundaries. Export the parser limit directly from its defining source module. Declare strict zip behavior where equal lengths are already required. Split long fixture strings without changing their bytes and combine equivalent nested test contexts. No global/per-module type suppressions or blanket casts.
- Why: Static tools should check the real contracts; broad ignores would hide defects. Existing tests cover the unchanged parser/extractor invariants and invalid inputs.
- Alternatives considered: ignore_errors, disabling strict checks or inserting mass type ignores contradict the requested quality gate; a large semantic refactor is unnecessary.
- Consequences: Runtime semantics for valid input remain unchanged; assertions document producer invariants, not target-code evaluation. Native library typing currently needs no suppression.
- Files: src/arctrellis/graph/results.py, src/arctrellis/ingestion/models.py, src/arctrellis/parsing/parser.py, src/arctrellis/parsing/__init__.py, src/arctrellis/parsing/models.py, src/arctrellis/extraction/models.py, src/arctrellis/extraction/es_imports.py, src/arctrellis/extraction/javascript.py, src/arctrellis/extraction/python.py, src/arctrellis/extraction/lexical.py, tests/core/test_models.py, tests/extraction/test_ids.py, tests/extraction/test_imports.py, tests/extraction/test_javascript.py, tests/extraction/test_lexical.py, tests/extraction/test_models.py, tests/extraction/test_python.py, tests/graph/fixtures.py, tests/graph/test_graph.py, tests/graph/test_results.py, tests/graph/test_traversal.py, tests/indexing/test_repository.py, tests/ingestion/test_discovery.py, tests/ingestion/test_models.py, tests/ingestion/test_safety.py, tests/parsing/test_models.py, tests/parsing/test_parser.py, tests/parsing/test_registry.py, tests/resolution/test_imports.py, decisions.md, flow.md

### D-064: Audit the native-parser boundary and document local quality commands
- Date / phase / commit: 2026-10-08, Quality Gate Q1, ec14dca7cf518a167dc42bd853c45d876c64cf26
- Context: Static tooling should protect the normalized parsing boundary as new analysis stages are added.
- Decision: Add standard-library import inspection tests over ArcTrellis source, with positive/negative vectors proving native-import detection. Tree-sitter imports must remain inside parsing. Review source searches for execution mechanisms and the fixed grammar loader. Publish verified local development commands in README and flow; no CI.
- Why: Parsing owns native implementation types; extraction, indexing and resolution consume owned records. The audit parses only ArcTrellis test/development source with ast for inspection; it does not replace normalized target parsing or execute inspected source.
- Alternatives considered: Raw text-only import bans depend on formatting; testing target execution via actual target execution violates the boundary; CI and cross-platform claims are outside this session.
- Consequences: The architecture regression is tied to package boundaries rather than formatting. The native grammar loader remains a reviewed internal exception to dynamic module-loading searches.
- Files: tests/test_architecture.py, README.md, decisions.md, flow.md, handoff.md

### D-065: Finalize verified indexing, resolution and quality handoff
- Date / phase / commit: 2026-10-08, Quality Gate Q1, ec14dca7cf518a167dc42bd853c45d876c64cf26
- Context: The bounded session must stop after all three gates and preserve reproducible continuation state.
- Decision: Rewrite the twelve handoff sections, record actual counts/commands/skip reasons, expand current capability/security/development documentation and finalize commit references separately under D-004. Retain conservative deferrals and stop before call-site extraction.
- Why: Baseline 236 tests progressed to 246 after indexing, 259 after resolution and 261 after Q1; all final runs passed with seven existing platform skips. Independent final review compared changed Python syntax against facc23e and found no critical/important issue; test fixtures/assertions remain intact. Package/API/isolation audits and all quality tools passed locally.
- Alternatives considered: Beginning call resolution exceeds authorization; claiming other operating systems or skipped link/FIFO coverage would be false; history rewriting for self-referential hashes is unnecessary.
- Consequences: Phase 1.7 requires a later authorized session. No remote, upload, publication, persistence, CI or target execution is introduced. Frozen summaries still own mutable graph instances and require snapshot discipline.
- Files: README.md, decisions.md, flow.md, handoff.md

### D-066: Preserve actual command contracts during final verification
- Date / phase / commit: 2026-10-08, Quality Gate Q1, ec14dca7cf518a167dc42bd853c45d876c64cf26
- Context: Two auxiliary final audit invocations used incorrect command/input assumptions.
- Decision: Supply bytes to the indexing test fixture helper, and use the repository's normal git diff --check without disabling core.autocrlf. Leave persistent Git configuration unchanged and record the failed attempts.
- Why: A string-based fixture smoke failed with TypeError: memoryview: a bytes-like object is required, not 'str'. The corrected bytes smoke returned supported3, complete3, partial0, failed0, entities9, relationships6. git -c core.autocrlf=false diff --check compared raw CRLF worktree lines to normalized index lines and reported trailing whitespace throughout; normal git diff --check and staged check passed.
- Alternatives considered: Changing test helper input semantics or repository line-ending policy to accommodate mistaken audit commands would be unnecessary; ignoring failed commands would violate verification honesty.
- Consequences: No production/runtime behavior changed. Developer checks must respect actual fixture and Windows Git normalization contracts.
- Files: decisions.md, flow.md, handoff.md

### D-067: Restore historical prose and restrict reference finalization fields
- Date / phase / commit: 2026-10-08, Quality Gate Q1, 0235fbf33103b90004ec470e53623209b2bc68c6
- Context: Final historical-prefix comparison detected an overbroad hash replacement in earlier Stage A documentation finalization.
- Decision: Restore the entire pre-D-055 decisions prefix exactly from 25f333c and its original D-048 flow row. Finalize only current decision commit fields and table Commit cells, leaving literal prose unchanged. Verify historical equality before the final documentation commit.
- Why: Comparison showed D-004's phrase uncommitted markers and D-048's phrase uncommitted documentation replaced by acfd6093f95e0f9dd6b150ad625cb5ab6fee4a79; the old flow row had the same unintended word substitution.
- Alternatives considered: Retaining altered historical prose violates append-only decisions; rewriting earlier commits is prohibited; a local documentation repair preserves actual Git history.
- Consequences: Historical decisions are restored without source/runtime changes. Literal uncommitted in historical explanations is valid; only unresolved commit-reference fields require finalization.
- Files: decisions.md, flow.md, handoff.md
- Symptom: Historical prose contained an implementation hash where a descriptive word belonged.
- Root cause: Global string replacement was used rather than targeting current commit-reference fields.
- Regression test: none; this is a documentation-only repair verified by exact pre-D-055 prefix and D-048 flow-row comparisons against 25f333c.

### D-068: Separate invocation observations from target resolution
- Date / phase / commit: 2026-10-08, Phase 1.7, e074bbb87e6c242536017d1b4186645b69aa12cb
- Context: Named declarations and import dependencies cannot represent individual invocation evidence.
- Decision: Create calls models, errors, IDs, extraction and public API plus contract tests. CallSite is a frozen hashable observation with owner ID, identifier parts, inclusive location and owned SyntaxSpan; it is not a CodeEntity and has no target. UUID5/NAMESPACE_URL over compact versioned canonical JSON includes language, path, owner, callee kind/parts and byte endpoints. Order is path/start/end/ID.
- Why: The requested separation lets syntax observations survive without fabricating callable targets or retaining source trees. Initial contracts failed because arctrellis.calls did not exist.
- Alternatives considered: A CALL entity falsely treats expressions as named declarations; storing native nodes breaks the parsing boundary; random IDs break reproducibility.
- Consequences: Identity is revision-deterministic, not edit-stable or repository-namespaced. The repository validates actual owner existence; SyntaxSpan retains six coordinates without retaining source.
- Files: src/arctrellis/calls/__init__.py, src/arctrellis/calls/models.py, src/arctrellis/calls/ids.py, src/arctrellis/calls/errors.py, src/arctrellis/calls/extraction.py, tests/calls/__init__.py, tests/calls/test_models.py, tests/calls/test_extraction.py, decisions.md, flow.md

### D-069: Extract calls from execution bodies using canonical declaration ownership
- Date / phase / commit: 2026-10-08, Phase 1.7, e074bbb87e6c242536017d1b4186645b69aa12cb
- Context: Span containment would attribute decorators, defaults, annotations and class bases to function execution. Normalized TS method decorators can precede their method node; optional invocation punctuation can be omitted.
- Decision: Iteratively match represented declarations by lexical parent, binding/name and declaration end, verify covering span, then enter only body fields. Omit headers, decorators, class execution, unrepresented anonymous/object callable scopes, constructor/new and optional/computed invocations. Stable identifier/attribute chains survive; dynamic callee subexpressions are omitted but ordinary arguments are visited. Precompute recovery once; omit unsafe invocations/scopes and retain unaffected siblings. Reuse encoding and coordinate helpers without refactoring entity extraction.
- Why: Actual normalized Python/TS samples verified body/name/value fields, decorator spans and optional-call punctuation. Body traversal establishes ownership rather than inferring execution from location alone.
- Alternatives considered: Containment-only ownership creates false caller attribution; reparsing/re-extracting entities duplicates work; evaluating expressions violates static inspection.
- Consequences: Calls hidden in omitted scopes/headers are deliberately absent; JSX elements are not calls, but executable expression children may contain calls. Input must describe the same source revision. Traversal and recovery are iterative and approximately linear before final sorting.
- Files: src/arctrellis/calls/extraction.py, tests/calls/test_extraction.py, decisions.md, flow.md

### D-070: Retain lightweight call observations during the existing indexing read
- Date / phase / commit: 2026-10-08, Phase 1.7, e074bbb87e6c242536017d1b4186645b69aa12cb
- Context: Resolution needs invocation syntax without reopening sources or keeping repository-scale parse trees.
- Decision: Extend FileIndexResult with final default call_site_count and RepositoryIndexResult with final default call_sites tuple and derived count. _analyze_file extracts calls while ParsedSource and ExtractionResult are live, then releases them. Typed call extraction failure is an explicit FAILED outcome with zero observations. Validate unique ordered sites, supported execution owners, matching file/language and per-file counts. Import resolution revalidates the extended snapshot including calls.
- Why: Existing positional fields and entity/relationship counts remain compatible. Contract tests initially failed with missing call_sites/call_site_count attributes; mixed and partial/failed fixtures exercise the extension.
- Alternatives considered: A separate repository reread duplicates I/O and can analyze another revision; retaining full ParsedSource violates the bounded ownership boundary; per-file duplicated site tuples add unnecessary storage.
- Consequences: Only lightweight semantic observations escape per-file analysis. Completeness semantics and existing graph counts remain unchanged. Call counts are not graph relationship counts.
- Files: src/arctrellis/indexing/models.py, src/arctrellis/indexing/repository.py, src/arctrellis/resolution/imports.py, tests/calls/test_indexing.py, decisions.md, flow.md

### D-071: Resolve a static call subset with explicit uncertainty and site evidence
- Date / phase / commit: 2026-10-08, Phase 1.7, e074bbb87e6c242536017d1b4186645b69aa12cb
- Context: Dynamic language behavior prevents runtime-proof CALLS relationships, while canonical declarations and resolved imports support useful conservative candidates.
- Decision: Add CallResolutionStatus/CallResolution/CallResolutionResult and resolve_calls with local indexes by parent/name and import binding. Search nearest semantic scope; represented import bindings block farther same-name functions. NAME targets are FUNCTION only; self/cls/this inside direct METHOD scopes target only direct same-class METHOD. Import-assisted lookup uses resolved import records and direct target-MODULE FUNCTION declarations. Python from aliases, direct module aliases, ES named/namespace and require member forms are supported; type-only, default callable imports, unaliased dotted-member guesses and longer chains are deferred. Multiple witnesses are AMBIGUOUS; unresolved/ambiguous emits no edge. Clone the import graph and add one deterministic site-specific CALLS edge with invocation Evidence per unique target. All CALLS are LIKELY: lexical/same-class 0.85, import-assisted 0.75.
- Why: User mandates these confidence scores, separation, evidence and no guessed targets. Tests exercise each family, negative cases, immutable input snapshots, separate sites and existing graph paths. Initial strict mypy found one missing list annotation; explicit list[CallSite] addresses it without suppression.
- Alternatives considered: PROVEN overstates dynamic semantics; first/last candidate tie-breaking guesses rebinding; inheritance, default exports, constructors, dataflow and full symbol tables exceed scope.
- Consequences: Assignment/parameter shadowing, runtime mutation and complete export semantics are not modeled; results are a conservative static subset, not a complete call graph. Conventional self/cls/this is heuristic. Candidate witness IDs are callable IDs or IMPORT IDs for duplicate-binding ambiguity. IDs remain revision-deterministic and not repository-namespaced. Resolution performs no filesystem I/O, import-resolution rerun or input graph mutation.
- Files: src/arctrellis/calls/models.py, src/arctrellis/calls/resolution.py, src/arctrellis/calls/__init__.py, src/arctrellis/indexing/repository.py, tests/calls/test_resolution.py, decisions.md, flow.md

### D-072: Keep runtime result imports out of the observation dependency path
- Date / phase / commit: 2026-10-08, Phase 1.7, e074bbb87e6c242536017d1b4186645b69aa12cb
- Context: Public indexing imports the calls observation package, whose public resolver initially eagerly imported the import-resolution package and returned to partially initialized indexing.
- Decision: Use postponed/type-only result annotations and local canonical runtime imports when resolve_calls/_imported execute. Add fresh-interpreter tests for indexing-, resolution- and calls-first import orders.
- Why: Fresh indexing import reproduced ImportError: cannot import name 'RepositoryIndexResult' from partially initialized module 'arctrellis.indexing' (most likely due to a circular import). In-process call tests imported calls first and did not expose this boundary failure.
- Alternatives considered: Removing public resolver export weakens deliberate API; moving observation models into indexing reverses semantic ownership; a broad package refactor is unnecessary.
- Consequences: Indexing depends on call observations; runtime resolution depends on completed snapshots only when invoked. Test subprocesses import ArcTrellis itself, never target repository code.
- Files: src/arctrellis/calls/resolution.py, tests/calls/test_indexing.py, decisions.md, flow.md
- Symptom: Fresh indexing import failed with the partially initialized module ImportError above.
- Root cause: Eager import-resolution package initialization imported indexing before its RepositoryIndexResult export was bound.
- Regression test: tests/calls/test_indexing.py, test_public_packages_import_in_fresh_process_in_any_order.

### D-073: Omit unsupported escaped identifier spellings before constructing observations
- Date / phase / commit: 2026-10-08, Phase 1.7, e074bbb87e6c242536017d1b4186645b69aa12cb
- Context: Normalized ECMAScript identifier nodes may contain Unicode escape spellings, while CallSite deliberately accepts plain identifier parts only.
- Decision: Validate every accumulated callee part before producing the tuple; unsupported spellings are omitted without evaluating escape semantics or aborting indexing. Cover JS and TS repository inputs with escaped callees.
- Why: Review and a failing regression reproduced valid zero-diagnostic source function f() {} followed by an escaped f call raising ValueError: callee parts must be simple identifier spellings.
- Alternatives considered: Executing/decoding ECMAScript escapes expands the spelling contract unnecessarily; catching every ValueError in indexing would mask invariant defects.
- Consequences: Escaped callee identifiers are deliberately outside the static call subset. Ordinary Unicode identifiers remain supported.
- Files: src/arctrellis/calls/extraction.py, tests/calls/test_indexing.py, decisions.md, flow.md
- Symptom: A valid escaped JS/TS invocation aborted index_repository with the ValueError above.
- Root cause: _parts accepted identifier node kinds without checking whether their source spelling met CallSite validation.
- Regression test: tests/calls/test_indexing.py, test_escaped_script_callees_are_omitted_without_aborting_index.

### D-074: Respect execution namespace and argument boundaries during call analysis
- Date / phase / commit: 2026-10-08, Phase 1.7, e074bbb87e6c242536017d1b4186645b69aa12cb
- Context: Review found Python class namespace leakage and omitted executable JS/TS binding defaults and constructor arguments.
- Decision: Skip CLASS namespaces during Python lexical/import lookup, retaining outer function/module lookup. Traverse executable variable binding patterns and constructor argument fields without treating the constructor itself as a call or entering anonymous bodies. Add independent regression tests for each boundary.
- Why: Class-only imported helper incorrectly emitted a CALLS edge from a method; the expected unresolved test failed (0 unresolved, 1 edge). Destructuring/default/key and new Service(helper()) fixtures returned no observations instead of three ordinary body invocations.
- Alternatives considered: Treating lexical ownership as closure semantics creates false edges; omitting whole new expressions loses independent invocations; constructor resolution remains outside scope.
- Consequences: Canonical parent_id stays unchanged; execution binding visibility can differ from declaration ownership. Constructor invocation is still omitted. Anonymous callable initializer bodies remain excluded unless canonically represented.
- Files: src/arctrellis/calls/extraction.py, src/arctrellis/calls/resolution.py, tests/calls/test_extraction.py, tests/calls/test_resolution.py, decisions.md, flow.md
- Symptom: Class-only imports falsely resolved method calls, while ordinary argument/pattern calls disappeared.
- Root cause: Ancestor lookup searched class namespaces as closures, and extraction pruned variable names/new_expression subtrees wholesale.
- Regression test: tests/calls/test_resolution.py, test_python_class_namespace_is_not_a_method_closure; tests/calls/test_extraction.py, test_destructuring_defaults_and_constructor_arguments_are_body_calls.

### D-075: Revalidate call coordinates and import proof consistency at snapshot boundaries
- Date / phase / commit: 2026-10-08, Phase 1.7, e074bbb87e6c242536017d1b4186645b69aa12cb
- Context: Frozen summaries own mutable graphs; programmatically constructed snapshots can be internally inconsistent even when counts agree.
- Decision: Require each retained call span to fit its canonical owner in bytes and points. Before call resolution, validate every import candidate is an indexed MODULE and resolved records exactly match the existing import-site relationship/evidence; reject missing/extra or modified import edges. Reuse the existing deterministic _import_edge producer without rerunning module/path resolution.
- Why: New failing tests showed an out-of-owner span was accepted, and a modified resolution target with unchanged graph evidence produced an unsupported CALLS edge. Both fixtures must fail explicitly rather than invent proof.
- Alternatives considered: Trusting matching aggregate counts leaves stale snapshots undetected; re-reading sources or rerunning import catalog resolution duplicates stages and violates the boundary.
- Consequences: Corrupted repository summaries fail validation and mismatched resolution snapshots raise CallResolutionInvariantError. No source reads, graph mutation or new identity scheme is introduced.
- Files: src/arctrellis/indexing/models.py, src/arctrellis/calls/resolution.py, tests/calls/test_indexing.py, tests/calls/test_resolution.py, decisions.md, flow.md
- Symptom: Both invalid snapshot regression tests initially failed with AssertionError: expected exception not raised.
- Root cause: Owner/file/count checks omitted coordinate containment, and import snapshot checks omitted decision-to-proof correspondence.
- Regression test: tests/calls/test_indexing.py, test_partial_failed_counts_and_owner_validation; tests/calls/test_resolution.py, test_import_decisions_must_match_preserved_import_evidence.

### D-076: Validate identity inputs and harden integrated call contracts
- Date / phase / commit: 2026-10-08, Phase 1.7, e074bbb87e6c242536017d1b4186645b69aa12cb
- Context: Public identity generation should reject invalid canonical components consistently, and the phase needs independent integration/security/depth evidence.
- Decision: Validate ID inputs using the same CallSite coordinate/spelling contract before UUID generation; use canonical ASCII JSON escaping consistently with existing identity helpers. Add mixed-source fixtures, deterministic full-pipeline, 1100-level owned-syntax traversal, non-execution and import-order contracts; document public usage, confidence, uncertainty and deliberate omissions in README.
- Why: Invalid language input initially raised AttributeError: 'str' object has no attribute 'value' rather than the expected validation error. The corrected API validates inputs before field access. The real six-file smoke measured six observations, four resolved, one unresolved, one ambiguous, four CALLS edges; repeat graph/decisions matched. Initial call tests failed before implementation, review regressions failed before fixes, and strict typing/formatting/compile/dependency checks passed locally after corrections.
- Alternatives considered: Allowing malformed identity components weakens deterministic producer contracts; runtime target execution as a test would violate the security boundary; hard-coded complete parser snapshots would be brittle.
- Consequences: There are no new dependencies or weakened tooling rules. General shadowing/export behavior remains explicitly unsupported. Independent review corrections are recorded in D-073 through D-075 and later entries.
- Files: src/arctrellis/calls/ids.py, tests/calls/fixtures.py, tests/calls/test_models.py, tests/calls/test_extraction.py, tests/calls/test_indexing.py, tests/calls/test_resolution.py, README.md, decisions.md, flow.md
- Symptom: Invalid ID-helper language input raised the AttributeError above.
- Root cause: The helper accessed enum.value before validating canonical inputs.
- Regression test: tests/calls/test_models.py, test_identity_helper_rejects_noncanonical_inputs.

### D-077: Exclude ECMAScript class static-block bindings from method lookup
- Date / phase / commit: 2026-10-08, Phase 1.7, e074bbb87e6c242536017d1b4186645b69aa12cb
- Context: Existing semantic ownership retains static-block declarations under CLASS, but the block's bindings are not visible to ordinary methods.
- Decision: Skip CLASS namespaces during lexical/import ancestor lookup in all languages; direct same-class receiver method resolution remains a separate explicit path. Test class-local static-block functions and fallback to a real module function with the same name.
- Why: Follow-up review and a failing JS/TS regression reproduced method run resolving helper() to a static-block function with LIKELY/0.85 instead of remaining unresolved.
- Alternatives considered: Modeling complete ECMAScript block environments adds out-of-scope symbol infrastructure; retaining false method visibility violates conservative resolution.
- Consequences: Static-block local binding resolution is deferred when represented parentage cannot distinguish execution environments. Direct this.method remains supported; module/function enclosing scopes remain searchable.
- Files: src/arctrellis/calls/resolution.py, tests/calls/test_resolution.py, README.md, decisions.md, flow.md
- Symptom: The method call falsely emitted a CALLS edge to a static-block-only FUNCTION.
- Root cause: Class namespace exclusion was applied only for Python, leaving CLASS-parent ECMAScript bindings visible to methods.
- Regression test: tests/calls/test_resolution.py, test_script_static_block_bindings_are_not_visible_to_methods.

### D-078: Distinguish optional-call punctuation from comments and type arguments
- Date / phase / commit: 2026-10-08, Phase 1.7, e074bbb87e6c242536017d1b4186645b69aa12cb
- Context: The normalized grammar omits anonymous optional-call punctuation, requiring byte inspection without interpreting unrelated text.
- Decision: Add _optional_call to remove direct normalized comment/type_arguments ranges from the callee-to-arguments gap before checking optional punctuation. Cover normal comments containing optional spelling, TS string-literal generic arguments and actual optional generic calls.
- Why: Review reproduced helper followed by a comment containing ?. and ordinary parentheses yielding no call sites despite zero diagnostics. The failing regression and actual TS child inspection verified comment/type_arguments spans; corrected extraction retains ordinary calls and still omits optional invocations.
- Alternatives considered: Raw substring checks confuse source trivia/types with execution punctuation; evaluating JavaScript or using a second target parser is unnecessary and violates the established boundary.
- Consequences: Callee and invocation evidence spans remain exact, including source trivia; no dynamic/optional dispatch resolution is added.
- Files: src/arctrellis/calls/extraction.py, tests/calls/test_extraction.py, decisions.md, flow.md
- Symptom: A well-formed ordinary call was omitted because a comment contained optional-call spelling.
- Root cause: The raw gap substring guard inspected comments and type literals as though they were executable punctuation.
- Regression test: tests/calls/test_extraction.py, test_comment_and_type_literal_optional_spelling_is_not_optional_invocation.

### D-079: Finalize verified Phase 1.7 handoff and stop before framework semantics
- Date / phase / commit: 2026-10-08, Phase 1.7, e074bbb87e6c242536017d1b4186645b69aa12cb
- Context: Completed call analysis must leave reproducible local verification and honest continuation boundaries.
- Decision: Rewrite the twelve handoff sections, record actual commands/results and skip reasons, retain conservative unsupported semantics, and finalize only new commit-reference fields separately under D-004/D-067. Stop before Phase 1.8.
- Why: Final call suite ran 34 tests OK; full suite ran 295 tests OK with seven existing platform skips. Ruff lint/77-file format check, strict mypy/43 source files, compileall and pip check passed. Public imports and native isolation passed. Real six-file smoke measured six call sites, four resolved, one unresolved, one ambiguous and four CALLS edges; proof showed imported validate at service.py:5 with LIKELY/0.75 and lexical helper at line 6 with LIKELY/0.85. Independent review reproduced boundary defects recorded above and verified their corrections with no remaining confirmed critical/important defect.
- Alternatives considered: Proceeding into frameworks exceeds this phase; claiming full dispatch/export semantics or other operating systems would overstate evidence; rewriting history for self-referential hashes is unnecessary.
- Consequences: No runtime dependencies, parser/core/graph redesign, source execution, remote or publication is introduced. Snapshot graphs remain mutable by existing contract; IDs are not edit-stable or repository-namespaced. The next authorized phase may investigate framework entry points.
- Files: README.md, decisions.md, flow.md, handoff.md

### D-080: Separate static route observations from endpoint resolution
- Date / phase / commit: 2026-10-08, Phase 1.8, 023b7922f15f4a31beec3c62d498044f13c980bf
- Context: The authorized initial HTTP adapter layer must retain evidence and avoid fabricated framework semantics.
- Decision: Create frameworks models, IDs, errors and public contract tests. Retain frozen framework constructor provenance and route syntax without source bytes or a selected handler target. Use versioned canonical JSON and UUID5; preserve unsupported static-path/method observations explicitly.
- Why: The initial public test failed with ModuleNotFoundError: arctrellis.frameworks. Observations are not graph facts; runtime framework packages are unnecessary.
- Alternatives considered: Combining syntax recognition with handler selection hides uncertainty; anonymous synthetic handlers and native nodes violate existing boundaries.
- Consequences: IDs remain revision-deterministic and not repository-namespaced; only FastAPI, Flask and Express are supported.
- Files: src/arctrellis/frameworks/models.py, src/arctrellis/frameworks/ids.py, src/arctrellis/frameworks/errors.py, src/arctrellis/frameworks/__init__.py, tests/frameworks/__init__.py, tests/frameworks/test_endpoints.py, decisions.md, flow.md

### D-081: Require simple constructor provenance and literal route declarations
- Date / phase / commit: 2026-10-08, Phase 1.8, 023b7922f15f4a31beec3c62d498044f13c980bf
- Context: The authorized initial HTTP adapter layer must retain evidence and avoid fabricated framework semantics.
- Decision: Use canonical import metadata plus a unique preceding module-level constructor assignment. Reject duplicate/rebound import and instance names. Recognize Python decorators and direct module-level Express registrations; use only unescaped single quoted or double quoted slash-prefixed paths. Flask route defaults to GET and literal method collections create separate methods; router paths remain local.
- Why: Normalized samples verified assignment/call/decorator/keyword_argument fields and Express variable_declarator/member_expression/arguments. Target code is never evaluated.
- Alternatives considered: Name-only .get/.route matching produces false positives; evaluating strings, application factories or mounted prefixes exceeds static scope.
- Consequences: FastAPI api_route, Flask convenience decorators, Blueprint/prefix/mount composition and non-module Express registrations are deferred. Inline Express callbacks remain unresolved; only the final argument is the handler, never an earlier middleware argument.
- Files: src/arctrellis/frameworks/extraction.py, tests/frameworks/test_endpoints.py, decisions.md, flow.md

### D-082: Capture route observations during the existing per-file parse lifetime
- Date / phase / commit: 2026-10-08, Phase 1.8, 023b7922f15f4a31beec3c62d498044f13c980bf
- Context: The authorized initial HTTP adapter layer must retain evidence and avoid fabricated framework semantics.
- Decision: Extend indexing with final default route observation tuple/count fields. Extract observations after calls before releasing ParsedSource; typed framework extraction failure is FAILED with zero semantic observations. Preserve extended fields during import/call snapshot validation.
- Why: One source read supplies entities, calls and framework syntax; persistent results retain no parse trees or source bytes. Existing positional APIs and pre-resolution graph counts remain compatible.
- Alternatives considered: A resolution-time reread can analyze a different revision; retaining ParsedSource grows repository memory; duplicating observations per file adds storage.
- Consequences: Route counts are observations, not endpoint counts. Unsupported patterns do not mark a syntactically complete file partial.
- Files: src/arctrellis/indexing/models.py, src/arctrellis/indexing/repository.py, src/arctrellis/resolution/imports.py, src/arctrellis/calls/resolution.py, tests/frameworks/test_endpoints.py, decisions.md, flow.md

### D-083: Assemble endpoint graphs with registration evidence and explicit handler uncertainty
- Date / phase / commit: 2026-10-08, Phase 1.8, 023b7922f15f4a31beec3c62d498044f13c980bf
- Context: The authorized initial HTTP adapter layer must retain evidence and avoid fabricated framework semantics.
- Decision: Add resolve_http_endpoints(index, imports, calls) returning a new graph. API_ENDPOINT names are METHOD path, qualified names path::http:METHOD:path@start_byte, parent MODULE. Each static method receives a separate deterministic entity and PROVEN/1.0 MODULE DEFINES edge. Python exact decorated-handler EXPOSES is PROVEN/1.0; Express unique local/import-assisted handler EXPOSES is LIKELY/0.85 or 0.75. Unresolved/ambiguous handlers retain endpoints but no EXPOSES.
- Why: The user requires endpoint-to-handler-to-CALLS traces and distinct proof for each registration site. Resolution uses existing import decisions and semantic records without source reads or import reruns.
- Alternatives considered: Guessing ambiguous handlers, creating middleware/CALLS edges, default callable imports or runtime framework introspection is out of scope.
- Consequences: Duplicate registrations remain distinct; graph snapshots stay mutable by existing contract. Handler counts count observations, while multiple-method observations produce multiple endpoints/EXPOSES edges.
- Files: src/arctrellis/frameworks/resolution.py, src/arctrellis/frameworks/__init__.py, tests/frameworks/test_endpoints.py, decisions.md, flow.md

### D-084: Reject uncovered provenance, argument and snapshot false positives
- Date / phase / commit: 2026-10-08, Phase 1.8, 023b7922f15f4a31beec3c62d498044f13c980bf
- Context: Independent review reproduced unsupported framework registration and handler associations in the initial adapter.
- Decision: Reject module-shadowed require, Python with/except/pattern captures, invalid/duplicate framework-specific path arguments and argument splats. Express get with one argument is a settings accessor, not a registration; obvious non-callable argument literals cannot establish a route. Retain handler syntax with a support flag when explicit writes or block-only declarations prevent a direct module binding. Require decorator containment in its handler declaration and binding point containment/order, in addition to byte containment. Preserve supported declarations and direct exports without implementing full alias/dataflow or middleware classification.
- Why: Focused regression run failed ten assertions across require/context writes, decorator arguments, Express settings/numeric arguments and handler reassignment. Block-only function/arrow tests failed both subcases. Normalized probes verified as_pattern alias, named_expression name and case_pattern shapes. After corrections the framework suite ran 27 tests OK.
- Alternatives considered: Ignoring these statically visible contradictions creates false endpoints; complete environment/dataflow or middleware models exceed scope; guessing an unrelated same-name declaration cannot support PROVEN EXPOSES.
- Consequences: Receivers with potential module writes are omitted; unsafe handler bindings keep a static endpoint but no EXPOSES. Malformed/invalid static registration arguments remain unsupported. Conservative omissions may reduce recall. No existing call-resolution shadowing contract is changed.
- Files: src/arctrellis/frameworks/extraction.py, src/arctrellis/frameworks/models.py, src/arctrellis/frameworks/ids.py, src/arctrellis/frameworks/resolution.py, src/arctrellis/indexing/models.py, tests/frameworks/test_endpoints.py, tests/frameworks/test_contracts.py, decisions.md, flow.md
- Symptom: Initial probes produced endpoint_count=1 for fake/invalid registrations, resolved a rebound or block-only handler, and accepted unrelated decorator targets or binding points on line 999.
- Root cause: The initial write pass omitted context/pattern/require shadowing; argument recognition accepted any first literal; handler lookup used structural parentage without direct module visibility; retained coordinates omitted decorator association/binding point constraints.
- Regression test: tests/frameworks/test_endpoints.py test_shadowed_require_and_python_context_bindings_are_rejected, test_invalid_argument_shapes_and_express_settings_getter_are_not_routes, test_explicit_module_handler_rebinding_is_not_selected, test_block_only_handler_is_not_visible_at_module_registration; tests/frameworks/test_contracts.py test_decorator_cannot_be_redirected_to_unrelated_declaration.

### D-085: Harden framework contracts and preserve the strict quality gate
- Date / phase / commit: 2026-10-08, Phase 1.8, 023b7922f15f4a31beec3c62d498044f13c980bf
- Context: New adapters need independent model, lifetime, import-order, proof and mixed-pipeline checks plus existing lint/types.
- Decision: Add a reusable synthetic HTTP fixture and observation/snapshot/security tests. Check all public package import orders in fresh interpreters, bounded failure summaries, no retained bytes/trees, source-free resolution, deterministic reruns and existing endpoint-to-handler-to-CALLS paths. Use explicit SyntaxNode work-item lists, method tuple annotations and distinct typed local variables; format Python with the existing Ruff configuration. Retry a failed atomic patch using inspected formatted contexts.
- Why: Framework contracts ran 27 tests OK. Initial Ruff reported 50 errors (two autofixable); formatting reduced remaining issues to fixture line lengths and an unused import. Initial mypy reported nine annotation/inference errors, then three mixed name/list errors after adding visibility checks. No broad suppressions or dependency/configuration changes are needed. One atomic patch failed with Failed to find expected lines in tests/frameworks/test_contracts.py; inspection confirmed no changes from that attempt.
- Alternatives considered: Weakening strict typing/lint hides defects; full syntax snapshots are brittle; retaining target framework packages or executing target code violates the security boundary.
- Consequences: Source/tests follow the existing gate; test subprocesses import ArcTrellis only. Framework models retain immutable scalar/tuple/span values. Other operating systems and runtime framework behavior are not claimed verified.
- Files: src/arctrellis/frameworks/extraction.py, src/arctrellis/frameworks/resolution.py, tests/frameworks/fixtures.py, tests/frameworks/test_contracts.py, tests/frameworks/test_endpoints.py, decisions.md, flow.md

### D-086: Do not certify repository modules that shadow framework package names
- Date / phase / commit: 2026-10-08, Phase 1.8, 023b7922f15f4a31beec3c62d498044f13c980bf
- Context: A repository can define its own fastapi.py while using the same constructor import spelling as the supported external framework.
- Decision: Use existing import decisions to reject internally resolved or ambiguous constructor dependencies as UNSUPPORTED. Also reject canonical root/src module or package-init framework-name paths present in inventory, including failed files with no module entity. No endpoint is created from that provenance. Ordinary unresolved external framework-name imports remain supported as source-level package identity evidence.
- Why: The failing regression produced endpoint_count=1 and PROVEN association for a local fake fastapi.py defining FastAPI. Source spelling alone cannot defend runtime package identity when an indexed internal collision is visible.
- Alternatives considered: Executing/importing packages violates the boundary; treating a shadow module as the framework produces a false claim; recursively analyzing framework implementation or arbitrary sys.path exceeds scope.
- Consequences: Vendored/custom wrappers named after frameworks are explicitly unsupported. External package installation/runtime identity remains unverified; provenance means static canonical import plus constructor syntax. Inventory and existing resolution records are used without filesystem reads.
- Files: src/arctrellis/frameworks/resolution.py, tests/frameworks/test_endpoints.py, decisions.md, flow.md
- Symptom: A fake internal fastapi.py yielded one supported endpoint instead of zero.
- Root cause: Framework recognition validated canonical import metadata but did not consult internal import resolution or failed-file inventory collisions.
- Regression test: tests/frameworks/test_endpoints.py test_internal_module_named_like_framework_does_not_prove_runtime_framework.

### D-087: Close direct-import and decorated-scope provenance gaps
- Date / phase / commit: 2026-10-08, Phase 1.8, 023b7922f15f4a31beec3c62d498044f13c980bf
- Context: Follow-up review found additional simple import/write contradictions and an indexing abort for a valid nested same-name declaration.
- Decision: Require constructor imports in direct module statements, decline module wildcard provenance, and include canonical class import bindings in receiver shadow checks. Detect shadowed require for imported Express handler references too. Reject all duplicate Python keyword arguments. Match decorated handlers by name plus exact start/end declaration span rather than name/end alone. Pre-index direct statement ranges and class import bindings; avoid per-route repository scans.
- Why: Three focused tests failed six assertions for wildcard/conditional/class imports, duplicate options and imported require handlers. A valid decorated h ending in nested h raised ValueError: decorated handler declaration must contain the route decorator in both function and method fixtures. The nested declaration shares its enclosing declaration end but not start; containment validation correctly exposed the wrong dictionary selection.
- Alternatives considered: Resolving wildcard exports or full control-flow environments adds unrequested infrastructure; accepting invalid duplicate arguments fabricates runtime registrations; catching the ValueError as a normal file failure hides the verified valid-source association defect.
- Consequences: Provenance is restricted to direct imports/constructors; no complete runtime symbol model is claimed. Exact decorated wrapper identity prevents nested same-name overwrites. Existing extraction/call/import semantics remain unchanged.
- Files: src/arctrellis/frameworks/extraction.py, tests/frameworks/test_endpoints.py, decisions.md, flow.md
- Symptom: Contradictory import/keyword inputs emitted endpoints or EXPOSES; valid nested same-name decorated scopes aborted repository indexing with the ValueError above.
- Root cause: Initial constructor lookup used semantic MODULE ownership for conditional imports, class imports and wildcard/require shadowing were not included, and decorated handler lookup keyed only name/end, allowing a nested declaration to overwrite its enclosing handler.
- Regression test: tests/frameworks/test_endpoints.py test_wildcard_conditional_import_and_class_import_shadows_are_not_framework_provenance, test_duplicate_option_keywords_do_not_prove_route_registration, test_shadowed_require_does_not_resolve_express_imported_handler, test_final_nested_same_name_does_not_replace_decorated_handler.

### D-088: Document the verified static HTTP subset and reproducible trace smoke
- Date / phase / commit: 2026-10-08, Phase 1.8, 023b7922f15f4a31beec3c62d498044f13c980bf
- Context: The adapter layer needs accurate public usage, source lifetime, confidence and uncertainty documentation for engineers continuing the project.
- Decision: Update README current capabilities, supported patterns, naming/parentage, static literal restrictions, handler uncertainty and security limitations. Update the existing indexing flow and framework flow with actual call names/order. Add a local tests.frameworks.smoke command using the shared synthetic repository and original CodeGraph shortest_path; print counts, deterministic rerun and exact proof. Do not begin middleware semantics.
- Why: The smoke ran four complete supported files, six observations, seven endpoints, four resolved-handler observations, one unresolved, one ambiguous and five EXPOSES edges, with deterministic=True. Verified trace: POST /payments EXPOSES create_payment at fastapi_app.py:5, fastapi_decorated_handler/PROVEN/1.0; create_payment CALLS validate_payment at line 7, python_lexical_call_resolution/LIKELY/0.85. The final independent review reran original reproductions and 32 framework tests, finding no remaining confirmed critical/important defect in the agreed scope.
- Alternatives considered: Broad framework claims or runtime guarantees exceed evidence; retaining anonymous handlers or middleware edges invents semantics; an unrepeatable inline-only smoke makes future checks harder.
- Consequences: The README distinguishes observation counts from expanded endpoints. Constructors/decorators/framework packages are never executed/imported, and endpoint resolution reads only retained records. IDs preserve existing revision/repository limits; mounted paths, runtime mutation and omitted framework patterns remain explicit.
- Files: README.md, tests/frameworks/smoke.py, decisions.md, flow.md

### D-089: Finalize the verified HTTP adapter gate and bounded handoff
- Date / phase / commit: 2026-10-08, Phase 1.8, 023b7922f15f4a31beec3c62d498044f13c980bf
- Context: Completed framework semantics must leave reproducible evidence, honest limitations and local continuation state before stopping.
- Decision: Rewrite all twelve handoff sections with actual command results, corrected regressions, supported semantics and deliberate omissions. Extend negative subcases for failed internal framework-name files and Python named/pattern captures. Verify unchanged dependencies, public imports, source isolation/security searches, identities, forbidden/attribution audits and clean local commit finalization. Finalize only current commit-reference fields under D-004/D-067; stop before Phase 1.9.
- Why: Full suite ran 327 tests OK with seven existing platform skips; framework suite ran 32 tests OK. Ruff lint and 88-file formatting passed, strict mypy checked 49 source files with no issues, compileall exited zero and pip check found no broken requirements. Public API and two architecture tests passed. Mixed smoke measured six observations, seven endpoints, four resolved/one unresolved/one ambiguous handler records and five EXPOSES edges, with equal reruns. Source searches found native imports and fixed grammar loading only in parsing. pyproject.toml has no diff.
- Alternatives considered: Claiming runtime framework validity/full coverage or other operating systems exceeds verification; continuing into middleware violates scope; historical prose/global marker replacement and history rewriting are prohibited.
- Consequences: Six symlink tests remain skipped for Windows privilege and one FIFO test for absent os.mkfifo; junction tests pass. Dynamic/mounted framework paths, middleware and runtime binding behavior remain deferred. Frozen result shells own mutable graphs; completed snapshots must not be mutated. No dependency, remote or publication is introduced.
- Files: tests/frameworks/test_endpoints.py, README.md, decisions.md, flow.md, handoff.md

### D-090: Normalize precise pre-handler roles with immutable source observations
- Date / phase / commit: 2026-10-08, Phase 1.9A, 94cdfd6dc4e789f2bc315f2fb82a05ac98f37ec9
- Context: Existing endpoint adapters retain argument counts but no pre-handler semantics; core Relationship has embedded Evidence but no metadata field.
- Decision: Add flow_models.py, flow_extraction.py and flow.py under frameworks and test_flow.py. Represent route_middleware, dependency and request_hook distinctly; retain binding, route identity or exact hook declaration, declared order and six coordinates. Normalize endpoint-to-callable edges as APPLIES_MIDDLEWARE with precise role/order in Evidence metadata; never add callable wrapper entities or synthetic CALLS. Reuse versioned canonical JSON/UUID5 and existing handler/import indexes. Extend indexing with final default lightweight tuples/counts and preserve them in all snapshot validators.
- Why: Phase 1.9 explicitly requires this separation and source lifetime. Baseline was 327 tests OK/skipped=7. Initial 13 pre-handler tests failed because resolve_framework_flow was absent. Syntax inspection verified direct decorator attributes and list/call/keyword fields. A first inspection used the wrong parse_source argument order and failed with TypeError: parse_source() got multiple values for argument path; corrected inspection succeeded.
- Alternatives considered: Generic middleware observations lose framework meaning; copying parse trees violates memory ownership; a second resolver duplicates existing import/function matching; changing core solely to add role metadata is unnecessary.
- Consequences: Dependencies are not ASGI middleware and hooks are not WSGI middleware. Only direct module hooks and decorator-level dependency lists/tuples are supported. No parameter injection, factories, global Express use, cross-file hook ordering or composition before the 1.9A gate. Local resolution is LIKELY/0.85, imported LIKELY/0.75; exact same-app Flask hook association is PROVEN/1.0. Existing IDs remain revision-deterministic and not repository-namespaced.
- Files: src/arctrellis/frameworks/flow_models.py, src/arctrellis/frameworks/flow_extraction.py, src/arctrellis/frameworks/flow.py, src/arctrellis/frameworks/__init__.py, src/arctrellis/frameworks/extraction.py, src/arctrellis/frameworks/resolution.py, src/arctrellis/indexing/models.py, src/arctrellis/indexing/repository.py, src/arctrellis/calls/resolution.py, src/arctrellis/resolution/imports.py, tests/frameworks/test_flow.py, README.md, decisions.md, flow.md

### D-091: Preserve complete reference indexes and record test-boundary corrections
- Date / phase / commit: 2026-10-08, Phase 1.9A, 94cdfd6dc4e789f2bc315f2fb82a05ac98f37ec9
- Context: Initial helper extraction and additional snapshot tests revealed development failures before the phase gate.
- Decision: Move the complete direct-declaration/represented-import setup into _reference_support; retain the same endpoint behavior and reuse it for middleware. Use explicit optional local names for index validation. Correct new tests to use actual source_entity_id/target_entity_id, relationship_kinds and embedded Evidence metadata; inject a stale edge between existing entities rather than a dangling endpoint.
- Why: Initial pre-handler run failed seven cases with NameError: name direct is not defined; the visibility setup had been moved only up to its first loop. Mypy found eight errors including optional route variable reuse. The corrected run passed thirteen tests and strict mypy. An additional stale-snapshot fixture failed before reaching the resolver with UnknownEntityError because it inserted an edge to an absent endpoint; corrected injection exercises the intended boundary.
- Alternatives considered: Broad error catching or disabling visibility checks would hide defects; weakening graph endpoint integrity for a fixture is invalid.
- Consequences: Existing endpoint and call contracts remain unchanged. Initial lint formatting/import issues are corrected without suppression; no package or core model changes.
- Files: src/arctrellis/frameworks/extraction.py, src/arctrellis/indexing/models.py, tests/frameworks/test_flow.py, decisions.md, flow.md
- Symptom: Seven Express subcases aborted with NameError; a test fixture raised UnknownEntityError before snapshot validation.
- Root cause: The refactor selected the first loop rather than the full index setup; the stale fixture referenced an endpoint absent from the call graph.
- Regression test: tests/frameworks/test_flow.py test_express_preserves_argument_order_and_excludes_handler and test_pre_handler_identity_and_route_containment_are_checked; existing tests/frameworks/test_endpoints.py guard preserved handler behavior.

### D-092: Omit class dependency environments and validate exact pre-handler provenance
- Date / phase / commit: 2026-10-08, Phase 1.9A, 94cdfd6dc4e789f2bc315f2fb82a05ac98f37ec9
- Context: Review reproduced module dependency selection despite class-local shadows, and caller-created snapshots could substitute incompatible framework/Depends witnesses.
- Decision: Extract decorator dependencies only for represented module FUNCTION declarations; preserve class route endpoints but defer class-scoped dependencies. Require canonical Depends import metadata and preceding coordinates, nonempty dependency provenance, constructor witness/framework/kind agreement, and framework-qualified app association. Use statement-position lookup for direct Python callable visibility.
- Why: Class-scope regression failed three assertions (assignment/function/import shadows emitted LIKELY/0.85 module dependency edges). Two provenance tests failed with ValueError not raised: a Flask hook could adopt a FastAPI binding, and a dependency could adopt the FastAPI constructor import. The initial minimal edit script stopped at an unmatched formatting assertion after changing extraction/model; actual formatted validation context was then inspected and corrected.
- Alternatives considered: Complete class-scope symbol tables expand injection scope; ignoring visible shadows fabricates claims; generic import ownership cannot establish framework provenance; broad exception catching hides inconsistent snapshots.
- Consequences: Method endpoints remain supported, but class-scoped dependency injection is deferred. Hook app keys include framework. No core, graph or dependency changes; binary position lookup avoids repeated whole-module visibility scans.
- Files: src/arctrellis/frameworks/flow_extraction.py, src/arctrellis/frameworks/flow_models.py, src/arctrellis/frameworks/flow.py, src/arctrellis/indexing/models.py, tests/frameworks/test_flow.py, README.md, decisions.md, flow.md
- Symptom: Class-shadowed dependencies produced wrong module targets; corrupted snapshots could emit PROVEN Flask hook edges on FastAPI endpoints.
- Root cause: Definition-time class namespaces were omitted, and pre-handler validation checked generic import ownership without exact constructor/Depends metadata; app keys omitted framework.
- Regression test: tests/frameworks/test_flow.py test_class_scoped_depends_and_callable_shadows_are_deferred, test_pre_handler_provenance_cannot_be_replaced_by_other_framework_import, test_depends_requires_actual_fastapi_depends_import.

### D-093: Close the pre-handler gate before static route composition
- Date / phase / commit: 2026-10-08, Phase 1.9A, 94cdfd6dc4e789f2bc315f2fb82a05ac98f37ec9
- Context: Phase 1.9B is authorized only after a verified, committed green pre-handler stage.
- Decision: Commit the precise pre-handler implementation, tests and documentation locally; finalize current reference fields separately before composition. Record independent review corrections, real quality gates, memory/failure/source-free contracts and deliberate omissions.
- Why: Pre-handler suite ran 20 tests OK, framework suite52 OK, full suite347 OK/skipped7. Ruff check and92-file format check passed; strict mypy52 source files, compileall, pip check and2 architecture tests passed. Mixed smoke produced3 observations/3 resolved/3 APPLIES_MIDDLEWARE edges with exact .85/.85/1.0 confidence contracts. Public flow imports passed; dependencies unchanged and remotes empty. Review reran class and snapshot regressions and found no remaining important blocker.
- Alternatives considered: Proceeding with known false-positive defects would violate the gate; global middleware semantics and class injection remain intentionally deferred.
- Consequences: Phase1.9B may now add bounded same-file composition only after local commit finalization. Existing platform/native/filesystem limitations remain. All changes remain local under the required identity.
- Files: README.md, decisions.md, flow.md, handoff.md, tests/frameworks/test_flow.py, src/arctrellis/frameworks/, src/arctrellis/indexing/, src/arctrellis/calls/resolution.py, src/arctrellis/resolution/imports.py

### D-094: Compose same-file static router paths without replacing local facts
- Date / phase / commit: 2026-10-08, Phase 1.9B, uncommitted
- Context: Green committed1.9A permits bounded APIRouter prefix/include_router and Express Router use mounting.
- Decision: Add composition_models.py, composition_extraction.py and composition.py with immutable prefix/mount observations, explicit mount outcomes and a deterministic HTTP join helper. Capture these during indexing; extend FrameworkFlowResult with router observations/outcomes and local/effective endpoint access. Retain local entities. Create effective endpoints only for changed static paths; mounting app MODULE owns mounted effective endpoints. Prefix-only effective endpoints remain in router module and describe router configuration, not public deployment. Distinct mount sites retain distinct identities. Reuse handlers/pre-handler proof, retain confidence and multiple Evidence records for route, constructor/prefix and mount.
- Why: Fourteen test-first composition contracts failed with missing result/API fields or absent effective endpoints. Core already supports Evidence tuples; no core redesign or dependencies are needed. Required same-file subset is defensible using existing constructor witnesses.
- Alternatives considered: Mutating local IDs loses immutable source facts; single-location proof cannot support composed paths; cross-file routers lack canonical router variable entities, so optional cross-file binding resolution is deferred; recursive mount chains add unsupported lifecycle/configuration inference.
- Consequences: New effective metadata distinguishes path_completeness=effective plus composition_scope=router or application and links local endpoint/prefix/mount IDs. Nested mounts (including cycles) are unsupported without recursion. Empty/no-change composition retains local fact only. app.use ordinary middleware does not create mount semantics. No full runtime route execution order or public deployment claim.
- Files: src/arctrellis/frameworks/composition_models.py, src/arctrellis/frameworks/composition_extraction.py, src/arctrellis/frameworks/composition.py, src/arctrellis/frameworks/flow.py, src/arctrellis/frameworks/flow_models.py, src/arctrellis/frameworks/__init__.py, src/arctrellis/indexing/models.py, src/arctrellis/indexing/repository.py, src/arctrellis/frameworks/resolution.py, src/arctrellis/calls/resolution.py, src/arctrellis/resolution/imports.py, tests/frameworks/test_composition.py, README.md, decisions.md, flow.md
- Supersedes: D-081 (router composition deferral only), D-090 (composition deferral after its completed gate only)

### D-095: Reject unsafe composition boundaries and use actual graph APIs
- Date / phase / commit: 2026-10-08, Phase 1.9B, uncommitted
- Context: Initial integration exposed graph API/type defects, and review found that normalizing every adapter input could fabricate a plausible effective path.
- Decision: Use keyword-only CodeGraph incoming/outgoing kind filters, explicit union annotations for heterogeneous router validation and distinct prefix/mount local variables. Add missing derived mount counts. Keep the mandated HTTP join helper boundary normalization, but reject FastAPI nonempty trailing-slash prefixes and decline effective composition for double-leading-slash local routes. Preserve local endpoints. Restrict FastAPI mounts to preceding declarations as a conservative static subset, without claiming framework-version lifecycle emulation.
- Why: Initial 14-test implementation run had eight errors; incoming passed a positional kind, then the incorrect kinds keyword, and three new tests also passed positional outgoing filters. Strict mypy first found five errors, then one; corrected APIs and annotations now pass. Two new regression methods failed three assertions because invalid /users/ or /api/ prefixes and //x local routes generated effective GET /api/users/x. Official https://fastapi.tiangolo.com/reference/apirouter/ documents prefix trailing-slash rejection; published current include internals also show that assuming one universal route-copy lifecycle would be incorrect. The generic helper contract remains independently tested.
- Alternatives considered: Altering core graph API would break stable contracts; treating normalization as framework runtime truth violates evidence-first design; evaluating framework code is prohibited; preserving arbitrary slash semantics across frameworks requires a separate adapter policy outside the bounded subset.
- Consequences: Trailing route slash and parameter spelling remain intact. Ordinary Express trailing mount slashes remain supported by the join policy. Unsupported FastAPI prefix observations remain explicit; unusual double-leading local paths remain local-only. No source or framework runtime execution occurs.
- Files: src/arctrellis/frameworks/composition.py, src/arctrellis/frameworks/composition_extraction.py, src/arctrellis/frameworks/flow_models.py, src/arctrellis/indexing/models.py, tests/frameworks/test_composition.py, decisions.md, flow.md
- Symptom: TypeError: CodeGraph.incoming() takes 2 positional arguments but 3 were given; invalid FastAPI prefixes and //x routes emitted normalized effective endpoints.
- Root cause: New code/tests assumed a different public graph signature; tuple validation inferred object instead of the router union. Adapter composition accepted every generic join-helper input, hiding known configuration/path contradictions.
- Regression test: tests/frameworks/test_composition.py test_fastapi_include_composes_both_prefixes, test_fastapi_invalid_trailing_prefix_does_not_fabricate_effective_path, test_multiple_leading_route_slashes_are_not_normalized_into_effective_facts, test_fastapi_mount_only_includes_routes_registered_before_include.

### D-096: Publish a reproducible local flow smoke and explicit composition limits
- Date / phase / commit: 2026-10-08, Phase 1.9B, uncommitted
- Context: Composed framework flows require a repeatable mixed fixture, actual proof output and documentation understandable independently of this session.
- Decision: Add tests/frameworks/flow_smoke.py using synthetic source strings and the existing static pipeline. Print measured local/effective/pre-handler/edge counts, deterministic rerun, full FastAPI dependency/handler/callee proof and seven negative cases. Update README and real flow call order for completed pre-handler/composition stages, bounded source order, unchanged-path behavior, same-file ownership, confidence inheritance and multi-site provenance.
- Why: The smoke observed three routes, three local endpoints, two effective endpoints, three resolved pre-handlers, zero unresolved/ambiguous pre-handlers, five APPLIES_MIDDLEWARE and five EXPOSES edges. Repeated snapshots were equal. Fake framework receivers, custom Depends, ordinary app.use function, dynamic prefix and dynamic middleware factory cases were all rejected. Full suite at this step ran371 tests OK/skipped7;76 framework tests and all quality/isolation gates passed before the smoke addition.
- Alternatives considered: Invented traces or runtime framework invocation are prohibited; optional cross-file binding inference and arbitrary nesting lack the canonical semantic representation needed for this phase.
- Consequences: The smoke is static verification, not target runtime execution. Source/header/class injection and arbitrary lifecycle behavior remain outside coverage. Later explanation layers can select effective application endpoints while preserving local facts and prefix-only configuration. No Phase2.0 work begins.
- Files: tests/frameworks/flow_smoke.py, README.md, decisions.md, flow.md, handoff.md

### D-097: Finalize the framework-flow quality gate and bounded continuation state
- Date / phase / commit: 2026-10-09, Phase 1.9B, uncommitted
- Context: Completed framework-flow semantics need verified quality, local-only audits and a complete handoff before stopping.
- Decision: Record the final gate and rewrite all twelve handoff sections with actual implementation, proof, commands, corrected failures and deliberate omissions. Share the owned-coordinate containment helper in frameworks/models.py between pre-handler/router/index validation without changing its behavior. Confirm no dependency/config/core changes, native isolation, source-free resolution, authorship, forbidden-file and attribution boundaries. Commit locally, finalize only new reference fields separately, then stop.
- Why: Final suite ran371 tests OK/skipped7;76 framework tests passed. Ruff lint and97-file format check passed; strict mypy55 source files, compileall, pip check and2 architecture tests passed.20 pre-handler and24 composition tests passed separately. Mixed smoke measured3 routes/3 local/2 effective/3 resolved pre-handlers/5 middleware/5 EXPOSES with equal reruns and seven rejected negatives. Public pipeline imports passed. Git identity matches required author/committer; remotes and forbidden tracked files are absent. Source audit found only fixed native grammar imports/loading in parsing; pyproject diff empty. Attribution search no-match exit1 is expected.
- Alternatives considered: Continuing Phase2.0 exceeds scope; declaring runtime framework completeness or other-platform verification would exceed observed evidence; global marker replacement/history rewrite conflicts with existing documentation rules.
- Consequences: Seven platform skips remain honest. Graph result shells follow existing mutable CodeGraph ownership. Runtime dynamics, parameter/class dependency environments, Blueprint/global middleware/factories and cross-file/recursive mounts remain deferred. All work stays local.
- Files: src/arctrellis/frameworks/models.py, src/arctrellis/frameworks/flow_models.py, src/arctrellis/frameworks/composition_models.py, src/arctrellis/indexing/models.py, README.md, decisions.md, flow.md, handoff.md
