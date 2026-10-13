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
- Date / phase / commit: 2026-10-08, Phase 1.9B, ee5b1d626a142a410ab5f9e01a201bae8faa511c
- Context: Green committed1.9A permits bounded APIRouter prefix/include_router and Express Router use mounting.
- Decision: Add composition_models.py, composition_extraction.py and composition.py with immutable prefix/mount observations, explicit mount outcomes and a deterministic HTTP join helper. Capture these during indexing; extend FrameworkFlowResult with router observations/outcomes and local/effective endpoint access. Retain local entities. Create effective endpoints only for changed static paths; mounting app MODULE owns mounted effective endpoints. Prefix-only effective endpoints remain in router module and describe router configuration, not public deployment. Distinct mount sites retain distinct identities. Reuse handlers/pre-handler proof, retain confidence and multiple Evidence records for route, constructor/prefix and mount.
- Why: Fourteen test-first composition contracts failed with missing result/API fields or absent effective endpoints. Core already supports Evidence tuples; no core redesign or dependencies are needed. Required same-file subset is defensible using existing constructor witnesses.
- Alternatives considered: Mutating local IDs loses immutable source facts; single-location proof cannot support composed paths; cross-file routers lack canonical router variable entities, so optional cross-file binding resolution is deferred; recursive mount chains add unsupported lifecycle/configuration inference.
- Consequences: New effective metadata distinguishes path_completeness=effective plus composition_scope=router or application and links local endpoint/prefix/mount IDs. Nested mounts (including cycles) are unsupported without recursion. Empty/no-change composition retains local fact only. app.use ordinary middleware does not create mount semantics. No full runtime route execution order or public deployment claim.
- Files: src/arctrellis/frameworks/composition_models.py, src/arctrellis/frameworks/composition_extraction.py, src/arctrellis/frameworks/composition.py, src/arctrellis/frameworks/flow.py, src/arctrellis/frameworks/flow_models.py, src/arctrellis/frameworks/__init__.py, src/arctrellis/indexing/models.py, src/arctrellis/indexing/repository.py, src/arctrellis/frameworks/resolution.py, src/arctrellis/calls/resolution.py, src/arctrellis/resolution/imports.py, tests/frameworks/test_composition.py, README.md, decisions.md, flow.md
- Supersedes: D-081 (router composition deferral only), D-090 (composition deferral after its completed gate only)

### D-095: Reject unsafe composition boundaries and use actual graph APIs
- Date / phase / commit: 2026-10-08, Phase 1.9B, ee5b1d626a142a410ab5f9e01a201bae8faa511c
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
- Date / phase / commit: 2026-10-08, Phase 1.9B, ee5b1d626a142a410ab5f9e01a201bae8faa511c
- Context: Composed framework flows require a repeatable mixed fixture, actual proof output and documentation understandable independently of this session.
- Decision: Add tests/frameworks/flow_smoke.py using synthetic source strings and the existing static pipeline. Print measured local/effective/pre-handler/edge counts, deterministic rerun, full FastAPI dependency/handler/callee proof and seven negative cases. Update README and real flow call order for completed pre-handler/composition stages, bounded source order, unchanged-path behavior, same-file ownership, confidence inheritance and multi-site provenance.
- Why: The smoke observed three routes, three local endpoints, two effective endpoints, three resolved pre-handlers, zero unresolved/ambiguous pre-handlers, five APPLIES_MIDDLEWARE and five EXPOSES edges. Repeated snapshots were equal. Fake framework receivers, custom Depends, ordinary app.use function, dynamic prefix and dynamic middleware factory cases were all rejected. Full suite at this step ran371 tests OK/skipped7;76 framework tests and all quality/isolation gates passed before the smoke addition.
- Alternatives considered: Invented traces or runtime framework invocation are prohibited; optional cross-file binding inference and arbitrary nesting lack the canonical semantic representation needed for this phase.
- Consequences: The smoke is static verification, not target runtime execution. Source/header/class injection and arbitrary lifecycle behavior remain outside coverage. Later explanation layers can select effective application endpoints while preserving local facts and prefix-only configuration. No Phase2.0 work begins.
- Files: tests/frameworks/flow_smoke.py, README.md, decisions.md, flow.md, handoff.md

### D-097: Finalize the framework-flow quality gate and bounded continuation state
- Date / phase / commit: 2026-10-09, Phase 1.9B, ee5b1d626a142a410ab5f9e01a201bae8faa511c
- Context: Completed framework-flow semantics need verified quality, local-only audits and a complete handoff before stopping.
- Decision: Record the final gate and rewrite all twelve handoff sections with actual implementation, proof, commands, corrected failures and deliberate omissions. Share the owned-coordinate containment helper in frameworks/models.py between pre-handler/router/index validation without changing its behavior. Confirm no dependency/config/core changes, native isolation, source-free resolution, authorship, forbidden-file and attribution boundaries. Commit locally, finalize only new reference fields separately, then stop.
- Why: Final suite ran371 tests OK/skipped7;76 framework tests passed. Ruff lint and97-file format check passed; strict mypy55 source files, compileall, pip check and2 architecture tests passed.20 pre-handler and24 composition tests passed separately. Mixed smoke measured3 routes/3 local/2 effective/3 resolved pre-handlers/5 middleware/5 EXPOSES with equal reruns and seven rejected negatives. Public pipeline imports passed. Git identity matches required author/committer; remotes and forbidden tracked files are absent. Source audit found only fixed native grammar imports/loading in parsing; pyproject diff empty. Attribution search no-match exit1 is expected.
- Alternatives considered: Continuing Phase2.0 exceeds scope; declaring runtime framework completeness or other-platform verification would exceed observed evidence; global marker replacement/history rewrite conflicts with existing documentation rules.
- Consequences: Seven platform skips remain honest. Graph result shells follow existing mutable CodeGraph ownership. Runtime dynamics, parameter/class dependency environments, Blueprint/global middleware/factories and cross-file/recursive mounts remain deferred. All work stays local.
- Files: src/arctrellis/frameworks/models.py, src/arctrellis/frameworks/flow_models.py, src/arctrellis/frameworks/composition_models.py, src/arctrellis/indexing/models.py, README.md, decisions.md, flow.md, handoff.md

### D-098: Separate static test identities from canonical declarations
- Date / phase / commit: 2026-10-09, Phase 2.0A, 561382be859f04e4605ff8e7db1f2abe038ba834
- Context: Tests are semantic declarations, not execution coverage; anonymous JS callbacks have no canonical FUNCTION identity.
- Decision: Add test_semantics models/extraction/resolution/errors and public API. Retain TestObservation during indexing; derive separate TEST entities with versioned UUID5 IDs, same lexical parent and declaration_entity_id metadata for Python. Parent DEFINES TEST records structural identity. Callback TEST identities own lightweight CallSite values; the private shared call extractor accepts explicit execution roots without inventing FUNCTION entities. Public extract_call_sites behavior remains unchanged. TestAnalysisResult retains independent graph, observations, entities, callback decisions and direct derivation records.
- Why: The canonical TEST kind already exists. Existing RelationshipKind has no correspondence relation; TESTS must never mean wrapper identity. Only immutable coordinates/scalars/tuples escape parsing.
- Alternatives considered: Replacing FUNCTION/METHOD loses existing semantics; fake anonymous FUNCTION identities broaden extraction; a new core relation is unnecessary; source rereads could mix revisions.
- Consequences: Existing positional index APIs gain final default observation/count fields. Snapshot validators preserve them. Test IDs are revision-deterministic, not edit-stable or repository-namespaced. Completed result graphs follow the existing mutable CodeGraph contract.
- Files: src/arctrellis/test_semantics/, src/arctrellis/indexing/, src/arctrellis/calls/extraction.py, src/arctrellis/calls/resolution.py, src/arctrellis/resolution/imports.py, src/arctrellis/frameworks/resolution.py, tests/test_semantics/

### D-099: Recognize only explicit static test syntax and naming containers
- Date / phase / commit: 2026-10-09, Phase 2.0A, 561382be859f04e4605ff8e7db1f2abe038ba834
- Context: Broad name matching would classify nested production helpers and arbitrary object methods as tests.
- Decision: Python module-owned test_ declarations and test_ methods under immediate Test* CLASS parents qualify; preserve existing decorator metadata. Defer unittest inheritance provenance. JS/TS require direct identifier test/it calls in direct module expression statements or recognized describe callback statements, exactly two arguments, a nonempty unpadded unescaped quoted description and an inline arrow/function callback. Describe is grouping only. Omit dynamic/template descriptions, member APIs, optional calls, skip/todo/each, arbitrary production scopes and malformed enclosing syntax. Framework metadata is pytest_naming_convention or unknown_js_test_api; no installed framework identity is claimed.
- Why: These are defensible syntactic conventions without target imports or execution. Exact JS framework provenance and full inheritance require more binding analysis than this subset.
- Alternatives considered: File-name-only classification misses declarations and creates false positives; unrestricted syntax walks enter production functions; unittest aliases/full inheritance and parameterization are intentionally deferred.
- Consequences: Some valid tests are omitted. No test validity, CI execution or assertion quality guarantee is made. Non-Test* unittest classes remain unrecognized in this phase.
- Files: src/arctrellis/test_semantics/extraction.py, src/arctrellis/test_semantics/models.py, src/arctrellis/indexing/models.py, tests/test_semantics/test_analysis.py, README.md

### D-100: Derive direct TESTS exclusively from resolved invocation proof
- Date / phase / commit: 2026-10-09, Phase 2.0A, 561382be859f04e4605ff8e7db1f2abe038ba834
- Context: Test relationships must preserve direct evidence and existing analysis snapshots without inventing endpoint coverage.
- Decision: analyze_tests validates matching index/import/call snapshots, copies the supplied call graph or matching framework-enriched base_graph, adds TEST identities, resolves callback calls using the existing _Symbols/_resolve/_edge machinery, then derives TESTS only from actual direct CALLS. Targets are canonical FUNCTION/METHOD excluding recognized test declarations. TESTS is LIKELY/0.85 with call-site Evidence, python_direct_test_call or ecmascript_direct_test_call, and the original CALLS relationship ID. Never materialize transitive or endpoint TESTS. Typed inconsistent-snapshot errors are exposed as TestAnalysisInvariantError.
- Why: Existing resolved calls provide the permitted evidence contract; anonymous callback ownership is explicit and semantically test-specific. Python declaration CALLS remain unchanged; JS callback CALLS originate at TEST.
- Alternatives considered: Name similarity, handler-to-endpoint inference and transitive TESTS create unsupported facts; universal PROVEN classification overstates static certainty.
- Consequences: Unresolved/ambiguous invocations create no TESTS. Imported calls retain original CALLS confidence while the requested direct-test interpretation is separately LIKELY/0.85. General existing resolver runtime/shadowing limits remain; no execution coverage is computed.
- Files: src/arctrellis/test_semantics/resolution.py, src/arctrellis/test_semantics/models.py, src/arctrellis/test_semantics/errors.py, tests/test_semantics/test_analysis.py, tests/test_semantics/smoke.py

### D-101: Correct callback ownership and exclude visible binding contradictions
- Date / phase / commit: 2026-10-09, Phase 2.0A, 561382be859f04e4605ff8e7db1f2abe038ba834
- Context: Initial implementation and additional negative regressions exposed ownership and optional-call/binding mistakes before the phase gate.
- Decision: Construct TEST CodeEntity with explicit keyword parent/language fields; omit optional test calls using the existing punctuation-aware helper. Over-approximate callback/suite parameter, local declaration and assignment names and omit affected callback call observations. Batch explicit execution roots through one shared extraction pass. Retain strict annotations and correct tests to use actual Relationship.confidence and typed snapshot failures.
- Why: Initial six-test run raised dangling lexical parentage because parent/language positional arguments were reversed; another assertion used nonexistent classification. The focused optional-call regression failed by producing an extra TEST. Callback binding guards prevent resolving a parameter/local variable to a module function. Initial mypy reported three missing annotations, then six inferred-empty-tuple/set errors; explicit annotations address them without suppression. Initial Ruff import/line-length/export findings were corrected through normal formatting/exports.
- Alternatives considered: Suppressing errors, weakening parent checks or trusting same-name module bindings would hide false relationships. Complete lexical dataflow is outside scope; conservative omission is preferable.
- Consequences: Over-approximate binding exclusions can omit valid calls. Nested anonymous callbacks remain omitted. Initial API test failed with ModuleNotFoundError before implementation, as expected; one stale-snapshot test initially expected the wrong exception class and was corrected by the explicit public error boundary.
- Files: src/arctrellis/test_semantics/, src/arctrellis/calls/extraction.py, tests/test_semantics/test_analysis.py
- Symptom: Anonymous JS test call resolution raised dangling lexical parentage; optional calls were classified and local bindings could select module targets.
- Root cause: Reversed positional CodeEntity fields, missing optional punctuation guard and no callback-specific local binding exclusion.
- Regression test: tests.test_semantics.test_analysis.TestSemanticsTests.test_script_imported_call_and_nested_callback_omission; test_callback_binding_and_optional_call_boundaries.

### D-102: Close the static test semantic gate before database work
- Date / phase / commit: 2026-10-09, Phase 2.0A, 561382be859f04e4605ff8e7db1f2abe038ba834
- Context: The next subphase is permitted only after complete verified test semantics and local commit finalization.
- Decision: Record the actual targeted/full/quality/isolation/smoke/audit results, commit locally, and finalize only new commit-reference fields in a later documentation commit. Preserve all prior decisions and session tables.
- Why: Targeted test semantics ran 11 tests OK; full suite ran 382 tests OK/skipped7. Ruff lint and105-file format check pass; strict mypy60 source files, compileall, pip check and2 architecture tests pass. Static smoke measured2 observations/2 entities/2 linked/0 unlinked/2 TESTS with deterministic rerun. Public API smoke passes. Source execution search finds only fixed native grammar loading/imports in parsing. Remotes, forbidden tracked files and attribution matches are absent. A first gate lint run found one long smoke literal; splitting it preserved fixture bytes and the rerun passed.
- Alternatives considered: Starting database work before green gates would violate phase ordering. No dependency or quality configuration changes are necessary.
- Consequences: Seven pre-existing platform skips remain: six Windows symlink privilege cases and one absent FIFO API. Static coverage, unittest inheritance, dynamic rebinding and other deferred patterns remain explicit.
- Files: README.md, decisions.md, flow.md, handoff.md, tests/test_semantics/smoke.py

### D-103: Exclude shorthand and named callback bindings from direct test proof
- Date / phase / commit: 2026-10-09, Phase 2.0A correction, f1ad053fefffe7dd9d44d1841b509c78c76a0cd1
- Context: Independent review after the first committed gate reproduced false TESTS to module functions from shorthand local/parameter/suite bindings and named callback self-references. Database work was paused pending correction and a repeated complete gate.
- Decision: Include normalized shorthand_property_identifier_pattern alongside identifier in callback/suite binding exclusion, and retain the callback function-expression name as a local contradiction. Keep TEST identity but omit affected callback CALLS/TESTS. Add ten JS/TS subcases and repeat targeted/full quality gates before resuming database work.
- Why: The new regression failed ten assertions before the correction. Normalized syntax inspection confirmed shorthand bindings use a distinct node kind and function_expression carries a name field. The initial inspection used the wrong parse_source positional order and failed with TypeError before parsing; the corrected inspection used path/language/bytes and succeeded. Corrected targeted suite ran12 tests OK; full suite393 tests OK/skipped7 (including10 uncommitted database-foundation tests). Ruff lint/110-file format check, strict mypy62 files, compileall, pip check and2 architecture tests passed.
- Alternatives considered: Treating this as a generic runtime limitation ignores explicit statically visible bindings; guessing local targets or creating fake functions is unsupported. Conservative omission is the intended policy.
- Consequences: Callback binding exclusions still deliberately over-approximate names. No target source execution, dependency or graph contract change. The previous green gate was insufficient to expose these grammar forms; its historical results remain truthful.
- Files: src/arctrellis/test_semantics/extraction.py, tests/test_semantics/test_analysis.py, README.md, decisions.md, flow.md, handoff.md
- Symptom: Shorthand destructuring and named callbacks falsely linked tests to unrelated module functions.
- Root cause: The binding guard collected only identifier nodes and omitted the callback function-expression name.
- Regression test: tests.test_semantics.test_analysis.TestSemanticsTests.test_callback_destructuring_and_named_function_shadowing (five cases each for JS and TS).

### D-104: Define immutable common database-operation observations
- Date / phase / commit: 2026-10-09, Phase 2.0B, 3d8ec6b71d02181ca80738a451230d669c5ea0e1
- Context: Future database adapters need one language-independent contract before any ORM syntax is recognized.
- Decision: Add arctrellis.database with DatabaseOperationKind READ/WRITE/DELETE/TRANSACTION/UNKNOWN, frozen DatabaseOperationObservation, canonical-owner-validating make_database_operation_observation and ordered DatabaseAnalysisResult. Retain owner ID/kind, path/language, operation/provider/name, optional logical target, SourceLocation, owned SyntaxSpan and immutable string metadata. Compute id as an init=False UUID5 field from version/language/path/owner/provider/kind/name/optional target/byte endpoints. Provider is an extensible lowercase identifier string; unknown is available. Factory validates actual MODULE/FUNCTION/METHOD, matching language and byte/point containment; no canonical owner object escapes it. Result offers sorted construction and nonzero ordered operation/provider counts.
- Why: Operations are expressions, not declarations. Existing immutable core metadata and owned spans avoid dependencies and parser/source retention. No target schema or provider enum is needed before adapters exist.
- Alternatives considered: INSERT/UPDATE categories prematurely specialize the common model; storing owner CodeEntity copies unnecessary declaration contents; random/caller-edited IDs weaken reproducibility; provider enums force changes for every adapter; separate target/table entities are unsupported.
- Consequences: Direct observation construction validates claimed structure, not owner existence/source truth; adapters should use the validated factory. Metadata cannot hold bytes/native objects/handles. Identity is revision-deterministic and not repository-namespaced; confidence remains an adapter responsibility. No dependencies added.
- Files: src/arctrellis/database/models.py, src/arctrellis/database/__init__.py, tests/database/test_foundation.py, README.md

### D-105: Defer database graph materialization pending adapter proof
- Date / phase / commit: 2026-10-09, Phase 2.0B, 3d8ec6b71d02181ca80738a451230d669c5ea0e1
- Context: Inspection confirmed core already contains DATABASE_OPERATION and READS_DATABASE/WRITES_DATABASE, and Relationship requires existing entity endpoints. No database adapter supplies proof or confidence yet.
- Decision: Establish observations/results only in Phase2.0B. Do not add graph conversion, fake database/table/model targets or a production database extraction stage. Future evidence-backed adapters may materialize existing DATABASE_OPERATION entities as expression targets, then owner-to-operation database relationships with adapter-specific proof/confidence. That conversion contract is not implemented or advertised now.
- Why: A valid observation representation alone cannot certify an ORM operation. The canonical operation entity is available for a later honest conversion; its presence does not justify unconditional edges or a universal confidence policy.
- Alternatives considered: Generic owner WRITES_DATABASE DATABASE_OPERATION machinery is coherent but would require a proof-bearing conversion API before an adapter contract exists; fake TABLE/DATABASE entities invent targets; changing core enums is unnecessary; name-only execute recognition is unsafe.
- Consequences: No enabled ORM/database extractor. Generic execute calls in Python/JS/TS remain ordinary calls with no database nodes/edges. SQLAlchemy/Prisma/Mongoose and other adapters are deferred to Phase2.1, not started here.
- Files: src/arctrellis/database/, tests/database/test_foundation.py, tests/database/smoke.py, README.md, flow.md

### D-106: Align capability summary and database contract verification with actual behavior
- Date / phase / commit: 2026-10-09, Phase 2.0B, 3d8ec6b71d02181ca80738a451230d669c5ea0e1
- Context: Database test-first and documentation review exposed incorrect test expectations and a stale README capability summary.
- Decision: Require TypeError when dataclasses.replace attempts to override computed init=False id; retain deterministic computed identity. Correct the synthetic owner fixture to use inclusive line9 for an exclusive line10/column0 span. Update README's current phase and stale no-test-classification sentence; explicitly distinguish the database foundation from extraction. Add repeatable synthetic database smoke and record initial failures honestly.
- Why: Initial database API test failed with ModuleNotFoundError before implementation. Initial ten-test implementation run failed because Python3.13 raises TypeError rather than the expected ValueError for replacing init=False fields. Ruff initially found three long lines, then formatting and lint passed; strict mypy passed62 source files. README review found Phase1.9/no-test-classification still in its initial summary despite the appended2.0A section.
- Alternatives considered: Making id caller-mutable merely to satisfy a mistaken test weakens identity. Retaining stale capability prose contradicts implemented behavior. Synthetic model output must not masquerade as an extractor result.
- Consequences: No production bug or dependency change follows from the incorrect exception expectation/fixture. The README now accurately names static tests and model-only database capability.
- Files: tests/database/test_foundation.py, tests/database/smoke.py, README.md, decisions.md, flow.md
- Symptom: Computed-ID test expected the wrong exception; README initially said test classification was unavailable.
- Root cause: Test assumption about dataclasses.replace and an unchanged historical current-status paragraph.
- Regression test: tests.database.test_foundation.DatabaseFoundationTests.test_forged_identity_rejected; README capability summary reviewed against public APIs.

### D-107: Finalize the verified Phase 2.0 foundation and stop before adapters
- Date / phase / commit: 2026-10-09, Phase 2.0B, 3d8ec6b71d02181ca80738a451230d669c5ea0e1
- Context: Both subphases need a reproducible local handoff after the reviewed test-semantics correction and final database foundation gate.
- Decision: Record all final measured commands/results, independent review, corrected failures, static smokes, security/public API/audit boundaries and complete twelve-section handoff. Commit the database foundation locally, finalize only its new commit-reference fields separately, and stop before Phase2.1.
- Why: Final targeted suites ran12 test-semantics and10 database tests OK; complete suite393 tests OK/skipped7. Ruff check and110-file format check pass, strict mypy62 source files passes, compileall exits0, pip check reports no broken requirements, architecture2 tests pass. Test smoke measures2 observations/entities/linked,0 unlinked,2 TESTS with deterministic rerun and actual line3 call-site proof. Database smoke constructs unknown-provider WRITE/synthetic_write with unknown target at a.py:2 and computed UUID5; conversion is explicitly deferred. Public API smoke passes. Independent review reproduced the D-103 issue, then rechecked the correction with22 targeted tests passing and no remaining important finding. Remotes, forbidden tracked files and attribution matches are absent; source search finds only fixed native grammar imports/loading in parsing. Dependencies/configuration remain unchanged.
- Alternatives considered: Claiming extractor/ORM/database query capability from a representation alone overstates evidence; beginning adapters exceeds authorized scope; history rewriting/global marker replacement breaks traceability.
- Consequences: Seven existing Windows symlink/FIFO skips remain. Other operating systems/runtime frameworks/DB behavior are not verified. No target source/tests/modules/Node/dependencies/DB/SQL were executed/imported/installed/contacted. Existing native parser resource/filesystem race and mutable result-graph limits remain explicit.
- Files: README.md, decisions.md, flow.md, handoff.md, src/arctrellis/database/, tests/database/

### D-108: Record independent review interpreter failures without treating empty output as proof
- Date / phase / commit: 2026-10-09, Phase 2.0B verification, 3d8ec6b71d02181ca80738a451230d669c5ea0e1
- Context: Independent review reported two failed reproduction attempts before using the project interpreter.
- Decision: Preserve the failed environment probes and inspect file_results before interpreting empty semantic output. Use .venv/Scripts/python for actual review verification; change no target source or dependencies.
- Why: System python -c importing tests.test_semantics.test_analysis failed with ModuleNotFoundError: No module named arctrellis. With PYTHONPATH=src, the system interpreter instead produced a FAILED file outcome with ParserConfigurationError/parsing failed (ParserConfigurationError), initially obscuring the defect. The same reproduction under the project interpreter exposed the false edges. Final project-interpreter review ran22 targeted tests OK after correction.
- Alternatives considered: Treating empty results from a failed index as a negative semantic proof is incorrect; installing grammars into the system interpreter is unnecessary.
- Consequences: These are review environment failures, not further production defects. Root verification independently reproduced and corrected the D-103 issue and passed the final complete gate.
- Files: decisions.md, flow.md, handoff.md

### D-109: Extract bounded SQLAlchemy intent using canonical call ownership
- Date / phase / commit: 2026-10-09, Phase 2.1A, 0f3e24585f927dc293e6ae8ae9143e9df0751ef9
- Context: Database foundation exists but no adapter supplies defensible source patterns.
- Decision: Add database/sqlalchemy.py and temporary syntax.py indexes; reuse common observations and canonical extract_call_sites ownership. Require direct imported sqlalchemy.orm Session (aliases allowed), one preceding direct constructor assignment and no competing scope writes. Require imported sqlalchemy statement constructors for classified execute. Retain constructor/binding/statement witness IDs, effect_stage and stable analysis_method. Model get as read_capable, add/add_all/delete as staged_mutation, flush/commit/rollback as transaction_control and unknown execute as UNKNOWN. Targets are source_identifier only. Defer context managers, AsyncSession, factories, typed parameters, alias propagation and complete flow. Standalone blocked_providers supports inventory collisions for later integration.
- Why: Normalized grammar inspections verified assignment/call/attribute/argument and with/async-with shapes; optional context-manager scope support is deliberately omitted. Existing canonical owners avoid another execution-scope engine. No runtime dependency or ORM import is needed.
- Alternatives considered: Name-only session/execute matching fabricates provider identity; full SSA/unit-of-work simulation exceeds scope; staged writes cannot support WRITES_DATABASE. A second database model is unnecessary.
- Consequences: Conservative whole-scope exclusions lose valid operations. Adapter output is static intent/capability, never proof of SQL, mapped schema or runtime execution. No graph conversion yet.
- Files: src/arctrellis/database/__init__.py, src/arctrellis/database/sqlalchemy.py, src/arctrellis/database/syntax.py, tests/database/test_sqlalchemy.py, README.md, flow.md, handoff.md

### D-110: Exclude comprehension bindings and disambiguate nested same-name scopes
- Date / phase / commit: 2026-10-09, Phase 2.1A, 0f3e24585f927dc293e6ae8ae9143e9df0751ef9
- Context: Independent review found comprehension shadowing and an unsafe optional supplied-call-site boundary; a local regression also reproduced nested same-name scope collision.
- Decision: Omit calls inside Python comprehensions/generators; derive call sites internally without caller override. Select the closest covering canonical declaration start among same-name/end candidates. Keep strict typing and format gates; fix local variable type narrowing without suppressions.
- Why: New tests failed three assertions before correction (two comprehension false positives and one missing nested operation); corrected targeted suite passes. Supplied sites could change owner/callee at an actual span, bypassing parameter shadows. Removing the new optional argument eliminates that unsupported input contract.
- Alternatives considered: Complete comprehension environments and trusted caller ownership add unnecessary scope; containment alone does not establish execution ownership.
- Consequences: Comprehension operations remain absent. No changes to existing call semantics or core types.
- Files: src/arctrellis/database/syntax.py, src/arctrellis/database/sqlalchemy.py, tests/database/test_sqlalchemy.py, decisions.md, flow.md, handoff.md
- Symptom: Comprehension-local db/select names acquired outer ORM provenance; nested final same-name declaration lost a valid operation.
- Root cause: Existing write helper omits for_in_clause, and a name/end dictionary overwrote enclosing canonical declarations.
- Regression test: SQLAlchemyTests.test_comprehension_scopes_are_deferred; test_nested_final_same_name_keeps_correct_owner.

### D-111: Recognize direct Prisma Client requests in JavaScript and TypeScript
- Date / phase / commit: 2026-10-09, Phase 2.1B, b0ecb51aea242e78fc25b25f3eccbc348f937195
- Context: The common database model and SQLAlchemy adapter are verified; JS/TS needs equivalent provenance-backed source requests.
- Decision: Add prisma.py and extract_prisma_operations; require direct named/aliased PrismaClient import from @prisma/client and a unique preceding direct new constructor assignment. Classify eight reads, five writes, two deletes and direct $transaction. Retain accessor spelling as target_name/target_basis=prisma_model_accessor, effect_stage=client_request or transaction_control and exact invocation. Omit raw queries, computed/optional access, factories, client aliases, CommonJS, custom generated paths and anonymous transaction bodies.
- Why: JS/TS normalized inspections showed matching import/new/member/arguments fields with zero diagnostics. Every supported CRUD method is tested in both languages, with canonical FUNCTION/METHOD ownership and deterministic IDs. No Node/Prisma dependency is needed.
- Alternatives considered: Variable-name recognition invents provenance; schema/table inference and raw SQL classification exceed source evidence; full dependency injection/dataflow is outside scope.
- Consequences: Observations mean source requests, not successful promises, committed transactions or changed rows. No graph conversion yet. Whole-scope binding exclusions intentionally sacrifice recall.
- Files: src/arctrellis/database/prisma.py, src/arctrellis/database/__init__.py, src/arctrellis/database/syntax.py, tests/database/test_prisma.py, README.md, flow.md, handoff.md

### D-112: Defer catch/with environments and record named function self-bindings
- Date / phase / commit: 2026-10-09, Phase 2.1B, b0ecb51aea242e78fc25b25f3eccbc348f937195
- Context: New negative tests reproduced catch parameters inheriting outer Prisma provenance; named function expressions also introduce local self-bindings.
- Decision: Record named function-expression self names as local contradictions; omit calls inside catch_clause and with_statement rather than pretending these environments are fully modeled. Keep existing comprehension omissions and canonical ownership.
- Why: Two catch negative assertions failed before the fix, then passed. Existing general write helper does not collect catch parameters. Named expression test confirms the canonical binding name differs from its internal function name.
- Alternatives considered: Rewriting stable framework binding logic would expand scope; source containment without environment handling fabricates a client. Complete block/with environments remain deferred.
- Consequences: Legitimate operations in catch/with bodies can be omitted, explicitly documented. No changes to existing framework or call resolution semantics.
- Files: src/arctrellis/database/syntax.py, tests/database/test_prisma.py, decisions.md, flow.md, handoff.md
- Symptom: catch(db) calls emitted Prisma WRITE from an unrelated outer db binding.
- Root cause: Shared write collector omitted catch_clause parameter while canonical calls retained surrounding execution ownership.
- Regression test: PrismaTests.test_negatives (module and function catch shadow cases).

### D-113: Invalidate visibly mutated client names across execution scopes
- Date / phase / commit: 2026-10-09, Phase 2.1B, b0ecb51aea242e78fc25b25f3eccbc348f937195
- Context: Independent Prisma review identified outer-client writes inside another callable and omitted TypeScript runtime enum bindings.
- Decision: Conservatively invalidate root names appearing anywhere in explicit JS assignment/update/delete patterns, Python member assignments, computed mutation receivers, JS unary delete, or TS enum/internal_module declarations. Do not simulate whether a mutating function runs; name-level contradictions exclude source provenance across scopes.
- Why: Nine new negative subcases failed before their corrections (nested member replacement, outer let reassignment, enum shadow, two computed mutations and unary delete including tab/comment/parenthesized spellings), then passed. Normalized probes verified enum_declaration/internal_module name fields.
- Alternatives considered: Interprocedural mutation execution and full block binding models exceed scope; ignoring visible contradictions fabricates provider operations.
- Consequences: Same-spelled unrelated local mutation can suppress valid operations elsewhere; this intentional false-negative bias is documented. No general alias analysis or monkey-patch certainty is claimed.
- Files: src/arctrellis/database/syntax.py, tests/database/test_prisma.py, decisions.md, flow.md, README.md, handoff.md
- Symptom: Replaced client/method and local enum produced Prisma operations through outer client provenance.
- Root cause: Per-scope write collection excludes nested callable writes and does not represent TS enum/namespace bindings; operation callee filtering also omitted computed mutation roots and JS unary delete.
- Regression test: PrismaTests.test_negatives (replace member, replace let binding, enum shadow).

### D-114: Retain database observations within the existing indexing lifetime
- Date / phase / commit: 2026-10-09, Phase 2.1C, b2a5e1a9c8b684cd053d065a0289c83d6d19d2a6
- Context: Verified standalone adapters need repository orchestration without rereads or retained syntax.
- Decision: Add database/extraction.py dispatcher and validation.py; extend index models with final default database_observations/database_operation_count fields. Extract after tests while ParsedSource exists; use inventory to block conventional root/src provider collisions, including failed sources. Preserve fields in import/call/framework snapshot validators. Validate canonical owner/site/import witnesses, receiver binding_name, effect/method/category, ordering and file counts. Existing typed failures remain bounded FAILED; internal invariants propagate.
- Why: Shared source lifetime avoids second parsing/I/O and immutable scalar observations bound repository retention. Canonical existing calls establish execution ownership. No dependency/core type changes.
- Alternatives considered: Reopening files risks revision mismatch; retaining ParsedSource violates memory boundary; silent catch-all extraction failure hides defects; arbitrary runtime search paths are not defensible.
- Consequences: No general package identity certification or complete lexical/dataflow proof. Structural snapshot validation does not authenticate fabricated caller records. Conventional collisions sacrifice recall. Public signatures preserve prior positional fields.
- Files: src/arctrellis/database/extraction.py, validation.py, syntax.py, __init__.py, src/arctrellis/indexing/models.py, repository.py, src/arctrellis/calls/resolution.py, src/arctrellis/resolution/imports.py, src/arctrellis/frameworks/resolution.py, tests/database/test_graph.py, README.md, flow.md, handoff.md

### D-115: Materialize operation sites and only eligible database capabilities
- Date / phase / commit: 2026-10-09, Phase 2.1C, b2a5e1a9c8b684cd053d065a0289c83d6d19d2a6
- Context: Core DATABASE_OPERATION and database relationship kinds exist; adapters now supply bounded proof.
- Decision: Add graph.py with DatabaseGraphResult/materialize_database_graph. Copy a validated index or matching enriched base graph; never mutate prior graph. Versioned UUID5 operation IDs include observation ID and metadata; qualified names path::database:provider:target.method@byte. Parent is canonical execution owner, without DEFINES. Emit owner-to-operation READS_DATABASE for read_capable/statement_execution/client_request READ; WRITES_DATABASE for statement_execution/client_request WRITE/DELETE. Every edge is LIKELY/0.85 with exact invocation Evidence and deterministic proof/edge IDs. Staged/transaction/UNKNOWN retain nodes without DB edges. Return ordered observations/entities/relationships, operation/provider counts and staged/unlinked/unmaterialized counts.
- Why: Expression nodes avoid fake tables or declarations. Static recognized capability never establishes SQL execution, changed rows or transaction outcome. Existing traversal preserves original multi-stage Evidence.
- Alternatives considered: Staged mutation writes or transaction-implies-write fabricates effects; fake TABLE targets invent schema; new transaction vocabulary and query APIs exceed scope; deep immutability claims would contradict mutable CodeGraph.
- Consequences: All supported observations currently materialize nodes (unmaterialized zero); unlinked includes staged/transaction/unknown. Repeated database enrichment is explicitly rejected. No transitive database edges or new graph algorithm.
- Files: src/arctrellis/database/graph.py, __init__.py, tests/database/test_graph.py, README.md, flow.md, handoff.md
- Supersedes: D-105 (graph conversion deferral, now supplied with adapter proof)

### D-116: Bind classified SQLAlchemy execute proof to its nested invocation
- Date / phase / commit: 2026-10-09, Phase 2.1C, b2a5e1a9c8b684cd053d065a0289c83d6d19d2a6
- Context: Independent review found a coherent UNKNOWN-to-WRITE snapshot relabeling could borrow an unrelated insert import.
- Decision: Retain statement_call_id/start/end from canonical calls during extraction; require exact same-owner nested statement invocation, matching imported binding and containment in its execute span before accepting classified statement effects.
- Why: test_unknown_execute_cannot_borrow_other_statement_proof failed with expected ValueError not raised, then passed after correction. Import existence alone does not associate a statement with an execute argument.
- Alternatives considered: Source reread violates lifetime; trusting unrelated imports fabricates WRITE; source authenticity of arbitrary caller-created metadata remains outside structural validation.
- Consequences: Source-free materialization has stronger retained statement witnesses. No ORM/SQL execution or parser object retention.
- Files: src/arctrellis/database/sqlalchemy.py, validation.py, tests/database/test_graph.py, decisions.md, flow.md, handoff.md
- Symptom: UNKNOWN execute(command) accepted borrowed insert metadata and could emit WRITES_DATABASE.
- Root cause: Snapshot checks validated statement import identity but omitted exact nested statement invocation association.
- Regression test: DatabaseGraphTests.test_unknown_execute_cannot_borrow_other_statement_proof.

### D-117: Verify mixed database traces and finalize the local Phase 2.1 boundary
- Date / phase / commit: 2026-10-09, Phase 2.1C, b2a5e1a9c8b684cd053d065a0289c83d6d19d2a6
- Context: All three stages need reproducible verification, accurate capability documentation and bounded continuation.
- Decision: Replace synthetic database smoke with real temporary Python/TS static indexing, enrichment and evidence paths; extend graph, negative, lifetime, import-order and isolation tests. Update current README/flow and rewrite all twelve handoff sections; finalize new reference fields separately after local commits. Stop before Phase2.2. No dependency/core/quality configuration changes.
- Why: Final pre-commit full417 tests OK/skipped7; database33 and architecture3 tests pass. Ruff119-file format and lint, strict mypy68 files, compileall and pip check pass. Mixed smoke measures SQLAlchemy6/Prisma3, nodes9, reads2/writes3, staged1/unmaterialized0/unlinked4/unknown1; rerun identical. Python and TS EXPOSES/CALLS/WRITES paths preserve actual call-site Evidence and .85 database confidence. Security search finds only fixed parsing grammar loading; attribution/forbidden-path/credential searches empty. Remotes remain empty.
- Alternatives considered: Runtime ORM execution, future query API and broader dataflow exceed scope; source-free validation cannot authenticate arbitrary coherently fabricated metadata, so its structural boundary remains explicit. Normal transform(insert(...)) execution remains UNKNOWN and is regression tested.
- Consequences: Seven existing Windows symlink/FIFO skips remain. Independent reviews found and verified corrections D-110/D-112/D-113/D-116. StageA API absence/lint/type narrowing, StageB API absence/lint and catch/mutation regressions, StageC API absence/lint/one union annotation and proof regression were corrected. The new ORM import audit initially mistook six relative adapter imports for runtime package imports; checking ImportFrom.level==0 corrected the test, not production behavior. No other platform/runtime execution claim.
- Files: README.md, decisions.md, flow.md, handoff.md, tests/database/smoke.py, test_graph.py, test_sqlalchemy.py, tests/test_architecture.py, src/arctrellis/database/, src/arctrellis/indexing/, src/arctrellis/calls/resolution.py, src/arctrellis/frameworks/resolution.py, src/arctrellis/resolution/imports.py


### D-118: Isolate immutable evidence-path queries from analysis lifecycle
- Date / phase / commit: 2026-10-11, Phase 2.2A, cc52333412c69b31486ca486101297e84fec6e0a
- Context: Existing shortest_path visits nodes once and cannot enumerate parallel constrained proof paths.
- Decision: Add query/errors.py, models.py, traversal.py, database.py and deliberate public exports. Reuse GraphPath continuity validation and public CodeGraph access only; EvidencePath.from_graph validates exact record membership. Frozen results retain original immutable entities/relationships/evidence, never graph/source/parser objects. Concurrent external graph mutation is unsupported. No dependencies change.
- Why: Querying must be observational and source-free while preserving every original proof and registration identity.
- Alternatives considered: Generic shortest_path loses alternative proof sites; modifying graph internals expands stable scope; a graph library adds no required capability.
- Consequences: Direct path construction validates continuity, not membership/source authenticity; queries always use from_graph. Empty Evidence remains empty. Typed unknown-ID, source-kind, limit and invariant errors distinguish programmer failures from NO_KNOWN_PATH.
- Files: src/arctrellis/query/, tests/query/test_paths.py, docs/superpowers/plans/2026-10-11-structural-query.md

### D-119: Bound constrained simple-path enumeration and preserve weakest support
- Date / phase / commit: 2026-10-11, Phase 2.2A, cc52333412c69b31486ca486101297e84fec6e0a
- Context: Branches, cycles and independent call sites require deterministic bounded enumeration without invented probability.
- Decision: Breadth-first simple paths with defaults depth12, paths25 and examined-adjacency-record budget10000. All limits are positive integers excluding bool. Every inspected adjacency record consumes budget, including rejected kinds/cycles. Depth includes terminal edges. Eligible non-cycle depth continuations mark max_depth; budget exhaustion marks max_expansions conservatively; an extra terminal path marks max_paths, avoiding false exact-cap truncation. Results sort by hop count, ordered relationship IDs, entity IDs. Path UUID5 includes ordered edge and entity IDs. Minimum confidence class and minimum score summarize weakest support; any missing score makes score unknown. No multiplication.
- Why: Independent site evidence survives, cycles terminate, queue growth is bounded by expansion budget, and partial search cannot claim exhaustiveness.
- Alternatives considered: Global visited sets collapse proof paths; DFS biases length discovery; probability products falsely imply calibration; timing-based limits undermine determinism.
- Consequences: Returned paths are bounded discovered paths, not globally shortest claims. Truncation may conservatively include branches that never reach a terminal. NO_KNOWN_PATH never proves no runtime behavior. Graph-only completeness is unknown; caller may supply canonical AnalysisCompleteness, without retaining indexing results. General find_paths requires explicit relationship kinds and supports forward/reverse search with stored forward path direction.
- Files: src/arctrellis/query/models.py, traversal.py, tests/query/test_paths.py

### D-120: Require exact endpoint/callable database patterns
- Date / phase / commit: 2026-10-11, Phase 2.2A, cc52333412c69b31486ca486101297e84fec6e0a
- Context: IMPORTS/DEFINES/TESTS/pre-handler associations do not establish invocation chains.
- Decision: trace_endpoint_to_database accepts API_ENDPOINT and EXPOSES -> CALLS* -> READS_DATABASE/WRITES_DATABASE only; trace_callable_to_database starts FUNCTION/METHOD with CALLS* -> database edge. Zero CALLS is valid. Filter read/write/delete from operation metadata, with DELETE using WRITES_DATABASE. Invalid database terminal kind/category or staged/transaction/unknown effect with a DB edge raises QueryGraphInvariantError. Preserve selected local/effective endpoint ID. Explicit JSON primitive dictionaries retain every evidence field and metadata coordinate.
- Why: Real existing adapter integration verifies Python/TS read/write and delete, including direct handler operations and omitted staged/transaction observations.
- Alternatives considered: Arbitrary-kind traversal fabricates execution; relationship-kind-only filtering conflates WRITE/DELETE; merging routes destroys registration evidence.
- Consequences: Results describe potential static capability paths, never execution/success/commit/changed rows. No pipeline rerun or filesystem access occurs. Missing metadata is not inferred from names. Initial missing package test failed before implementation; initial lint/format and one deque annotation error were corrected without suppressions.
- Files: src/arctrellis/query/database.py, __init__.py, tests/query/test_paths.py


### D-121: Expose direct database and direct static test proof without transitive claims
- Date / phase / commit: 2026-10-11, Phase 2.2B, fda96a0b2f340b7be4a8fc14269d1ba79d7791ad
- Context: Direct ownership and transitive reachability answer different questions.
- Decision: get_direct_database_operations returns only one-hop DB paths for supported MODULE/FUNCTION/METHOD owners. list_direct_database_callers returns one-hop paths for FUNCTION/METHOD owners, with source_entity_id=None for the global inventory; group first path entity IDs for owners. find_direct_tests_for_symbol accepts FUNCTION/METHOD and returns original incoming TESTS only, one path per proof site. All retain operation/provider metadata and evidence; direct queries have path/expansion limits. Inventories default to1000 paths and10000 examined records.
- Why: Real Python and JS pipeline tests verify direct associations, absent transitive tests, direct handler test evidence and database owner details. Parallel TESTS sites remain distinct.
- Alternatives considered: A uses-database boolean loses operation categories; synthetic transitive edges misstate direct evidence; labeling absent TESTS untested or handler tests HTTP coverage is unsupported.
- Consequences: Missing paths mean no known direct static evidence. Direct-test results run TEST -> symbol with direction=reverse. No test detection/call resolution reruns, runtime coverage or HTTP-client claim.
- Files: src/arctrellis/query/database.py, tests.py, models.py, __init__.py, tests/query/test_architecture_queries.py

### D-122: Separate reverse callable callers and endpoint impact candidates
- Date / phase / commit: 2026-10-11, Phase 2.2B, fda96a0b2f340b7be4a8fc14269d1ba79d7791ad
- Context: Existing CALLS evidence supports reverse structural dependencies but not guaranteed breakage.
- Decision: find_callers defaults to direct incoming CALLS; transitive=True collects each nonempty simple reverse CALLS prefix and continues through FUNCTION/METHOD only. TEST/MODULE execution owners are omitted deliberately. find_potentially_affected_endpoints follows reverse CALLS* then reverse EXPOSES, including directly exposed handlers. Shared search gains stop_at_terminal=False for caller prefixes. Return original forward ordered paths and direction=reverse; confidence/evidence unchanged. Middleware impact is deferred.
- Why: Cyclic/parallel caller fixtures and real pipeline impact preserve original direction and prevent IMPORTS/DEFINES/TESTS/APPLIES_MIDDLEWARE false dependencies.
- Alternatives considered: Reversing stored edges changes source truth; mixing pre-handler association with invocation paths confuses semantics; runtime prediction needs unavailable control-flow/runtime evidence.
- Consequences: All traversal bounds include terminal EXPOSES. No candidate means no known endpoint dependency path, not a guarantee of safe change. Results are language independent and retain duplicate registration IDs.
- Files: src/arctrellis/query/dependencies.py, impact.py, traversal.py, tests/query/test_architecture_queries.py

### D-123: Filter canonical endpoint metadata and preserve lightweight analysis context
- Date / phase / commit: 2026-10-11, Phase 2.2B, fda96a0b2f340b7be4a8fc14269d1ba79d7791ad
- Context: Existing metadata uses local router paths, declared application routes and effective composed paths; router-effective does not establish application mounting.
- Decision: list_endpoints uses exact http_method/framework/route_path metadata and scope local/declared/effective/application; application selects effective composition_scope=application only. None retains all registration sites; no parsing names or filename inference. Frozen EntityQueryResult records bounds/truncation/context; defaults1000 matches/10000 examined entities. AnalysisSummary validates file counts, maps all-failed to failed, mixed failures/recovery to partial and no failures/recovery to complete; caller passes summary.completeness to any query. Graph-only mode stays unknown.
- Why: Inspected framework models allow local/declared and composition adds effective/router/application. Existing is_complete accepts empty complete analysis. A lightweight count summary retains no repository graph/source and avoids analysis imports.
- Alternatives considered: Treating all effective paths as publicly mounted misstates router configuration; merging equal paths loses proof; guessing completeness from graph size is false.
- Consequences: Caller must associate completeness with the same graph revision. COMPLETE describes file outcomes only, never runtime exhaustiveness. Inventory scanning is bounded but public entities()/relationships() snapshots allocate/sort existing records before scanning. No global cache or dependency added. Initial missing AnalysisSummary API test and initial line-format findings corrected; strict mypy passes without suppressions.
- Files: src/arctrellis/query/endpoints.py, models.py, __init__.py, tests/query/test_architecture_queries.py


### D-124: Evaluate independently specified cross-file static golden repositories
- Date / phase / commit: 2026-10-11, Phase 2.2C, fdab31ba76a9713bf7b513a2761bfa31b6b555f2
- Context: Query unit graphs alone do not verify integration with actual analysis output.
- Decision: Add tests/query/fixtures.py with Python FastAPI/imported SQLAlchemy helpers, JS Express/middleware/router/imported Prisma helpers, typed TS duplicate registrations and mixed-language fixtures. Golden tests independently assert named chains, relationship kinds, operation categories, proof lines/methods, confidence and direct TESTS. Real canonical IDs come from analysis; none are manually fabricated. Include unresolved/ambiguous calls, fake receivers/clients, staged/commit-only operations, local/effective routes and same-name cross-language symbols. Add tests.query.smoke using the complete existing pipeline.
- Why: Nine complete files produce13 endpoint registrations,8 operations,3 TESTS,8 endpoint-to-DB paths,6 direct DB callers and1 endpoint impact candidate for persist_payment. Five endpoint traces have no known path; one intentional depth1 query is truncated. Rerun dictionaries and graph snapshots match. Golden expectations initially used an incorrect shortened imported-call method name; inspected resolver uses imported_symbol_call_resolution, and assertions were corrected without changing production behavior.
- Alternatives considered: Deriving expectations with the query implementation is circular; whole UUID snapshots are brittle; real target execution violates the boundary; timing benchmarks are unnecessary for correctness.
- Consequences: Synthetic static evaluation establishes supported examples, not production/runtime completeness. Smoke metrics include a deliberate truncated query. Source strings remain test data and never execute/import/install.
- Files: tests/query/fixtures.py, test_golden.py, smoke.py, README.md

### D-125: Report relevant corrupt graph proof as invariant failures
- Date / phase / commit: 2026-10-11, Phase 2.2C, fdab31ba76a9713bf7b513a2761bfa31b6b555f2
- Context: New corruption tests found DB inventory treating an internal missing target as a bad caller ID and reverse impact ignoring malformed EXPOSES sources.
- Decision: DB inventory uses canonical public graph lookups and exact relationship equality, chaining graph lookup failures as QueryGraphInvariantError. Reverse impact raises that error when an incoming EXPOSES source is not API_ENDPOINT. Retain original semantics for absent explicit query IDs and valid disconnected entities.
- Why: Both tests failed before correction (one unexpected UnknownQueryEntityError, one missing exception) and pass after minimal fixes. Normal CodeGraph insertion prevents dangling edges, but a corrupted/custom public snapshot must not misreport caller input or silently hide malformed relevant proof.
- Alternatives considered: Broad exception swallowing hides corruption; changing CodeGraph internals is unnecessary; treating normal no-known-path outcomes as failures is incorrect.
- Consequences: Relevant structural corruption fails loudly; queries do not authenticate arbitrary coherent fabricated source evidence. No source reread, dependency or original analysis change.
- Files: src/arctrellis/query/database.py, impact.py, tests/query/test_hardening.py
- Symptom: Missing internal DB target raised UnknownQueryEntityError; malformed reverse EXPOSES returned no candidate.
- Root cause: Inventory reused caller-input require_entity and impact combined kind/source checks into an omission branch.
- Regression test: HardeningTests.test_corrupt_inventory_is_invariant_failure_not_unknown_input; test_corrupt_impact_exposes_and_direct_test_source_rejected.

### D-126: Harden bounded enumeration and retain honest public-API resource limits
- Date / phase / commit: 2026-10-11, Phase 2.2C, fdab31ba76a9713bf7b513a2761bfa31b6b555f2
- Context: Quality evaluation must prove budgets/determinism/security without brittle timings or broader graph redesign.
- Decision: Add functional stress graphs with20/200/2000 services (42/402/4002 entities), parallel sites/cycles/database leaves; exercise depth/path/100-examination caps and exhaustive uncapped-within-budget results. Add fresh-process public import isolation, filesystem/mutation guards, JSON primitive checks, missing-proof/score preservation, malformed results and multi-hop forward/reverse cases. Document that public adjacency/inventory APIs eagerly allocate/sort snapshots outside examination budgets. Keep no cache/worker/thread/dependency. Rewrite twelve handoff sections and stop before2.3.
- Why:31 targeted query tests pass, including independently reviewed30 before the final multihop case. Read-only review found no critical/important functional defect and identified the eager snapshot allocation limitation, now explicit. Bound counters, truncation, exact-cap behavior, insertion-order equivalence and repeated real pipelines are checked without timing thresholds.
- Alternatives considered: Lazy graph iteration requires a new graph contract outside this phase; claiming total CPU/memory caps exceeds public-API guarantees; persistent/global caching and timed tests are unnecessary.
- Consequences: Path enumeration/queue growth is bounded; snapshot allocation/sorting is not capped by max_expansions. Existing static resolution/identity/platform/native limitations remain. No runtime probability, complete coverage, safe-change guarantee or public deployment claim is introduced.
- Files: tests/query/test_hardening.py, src/arctrellis/query/, README.md, decisions.md, flow.md, handoff.md, docs/superpowers/plans/2026-10-11-structural-query.md


### D-127: Scope final session audits to the verified starting commit
- Date / phase / commit: 2026-10-11, Phase 2.2C verification, 5ffe450391a8bbbe37ef356e12f8bae6a4e90b86
- Context: An auxiliary final audit expected six session commits but used older0f781de as its comparison base.
- Decision: Use333f8561ef1b4daff0c03141af093ab3f6681578, verified as cc52333's parent, for changed-file and session identity audits. Preserve the failed invocation in handoff and rerun the actual gates after documentation finalization.
- Why: The first six-commit assertion failed because0f781de predates previous database integration commits. Corrected333f856..HEAD audit passed with six solely required-identity session commits, clean tree, no remotes/forbidden/attribution/key patterns, preserved historical decisions and finalized references. No production code changed for this correction.
- Alternatives considered: Changing expected counts to absorb earlier unrelated commits obscures session scope; rewriting history is unnecessary.
- Consequences: Future session audits must derive their baseline from the actual starting HEAD rather than a prompt's older recent-commit list. Additional documentation correction/finalization commits also require the same identity and post-commit gates.
- Files: decisions.md, flow.md, handoff.md

### D-128: Project canonical entities into bounded immutable search documents
- Date / phase / commit: 2026-10-13, Phase 2.3A, 5a329c1
- Context: Phase 2.3 needs deterministic retrieval before any explanation layer, over existing canonical CodeEntity records and nothing else.
- Decision: Add src/arctrellis/retrieval with errors.py, normalization.py, documents.py and index.py. SearchDocument is a frozen projection of exactly one CodeEntity keyed by its canonical CodeEntity.id, carrying entity_kind, language, repository_relative_path (from the entity location only), source_location, name, qualified_name and allowlisted searchable fields. SEARCHABLE_METADATA_KEYS holds eighteen verified existing keys (framework, http_method, route_path, path_completeness, registration_kind, composition_scope, provider, operation_kind, operation_name, target_name, target_basis, effect_stage, import_form, module, imported_name, alias, binding, is_type_only); every other metadata key is excluded by omission. Signatures are never indexed, so signature literals cannot become retrieval content. No entity kind is filtered and no synthetic entity is created. Missing location stays None; line numbers are never invented.
- Why: Names, qualified names, paths, kinds, languages, routes, frameworks, import and database identifiers are the grounded structural facts a developer searches, and they already exist canonically. Reusing the canonical identity avoids inventing search IDs or duplicating one entity per relationship. Excluding signatures keeps arbitrary source expressions out of the corpus and makes the Phase 2.3 "structural metadata, not source text" boundary enforceable rather than aspirational.
- Alternatives considered: Indexing full signatures and arbitrary metadata would smuggle source literals and unbounded values into the corpus. Re-scanning source with new identifiers would duplicate the parser and weaken traceability. Filtering to a subset of entity kinds would need a justification that no evidence supports. Random search UUIDs would sever provenance from canonical IDs.
- Consequences: Searching a string literal inside source code cannot work and is explicitly deferred. Documents retain only bounded scalar strings; no source bytes, trees, parser objects, credentials or tracebacks are reachable. Field lookup uses a read-only proxy over a dictionary that is never exposed, so no mutable container is reachable from a document.
- Files: src/arctrellis/retrieval/errors.py, normalization.py, documents.py, index.py, __init__.py, tests/retrieval/

### D-129: Fix the identifier tokenizer and Unicode normalization policy
- Date / phase / commit: 2026-10-13, Phase 2.3A, 5a329c1
- Context: PaymentService, payment_service, payment-service, payment.service, payment/service and paymentService must share tokens, and HTTPServer must not split per capital.
- Decision: canonical_text applies NFKC while preserving case; tokenize splits that cased text on ASCII case/digit boundaries and on every non-alphanumeric character, then case folds each token. Acronym runs keep capitals (HTTPServer -> http, server); Capitalized words, lowercase runs and digit runs are separate tokens; non-ASCII letter runs stay whole. normalize_exact collapses whitespace for exact field comparison. MAX_FIELD_VALUE_LENGTH is 512 characters and MAX_FIELD_TOKENS is 32 tokens per approved field value. Long values are truncated at the prefix rather than rejected. Original identifiers are never mutated.
- Why: Folding before splitting would erase exactly the camel/Pascal boundaries that carry retrieval signal. A bounded prefix prevents an adversarially long identifier or metadata value from causing unbounded per-field work while keeping normal identifiers whole. Queries are pure data: punctuation, control characters, traversal-like text and instruction-like text are only separators and tokens.
- Alternatives considered: A stemmer or language model would imply semantic understanding this phase does not have. Rejecting over-long values would make an otherwise searchable entity unreachable for an incidental reason. Splitting every capital would make HTTPServer unusable.
- Consequences: Non-ASCII letters adjacent to ASCII runs form their own token (café -> caf, é), which is deterministic and documented. A single enormous identifier contributes at most 32 tokens to a document. Tokenization is a pure function with no corpus state.
- Files: src/arctrellis/retrieval/normalization.py, tests/retrieval/test_tokenization.py
- Symptom: tokenize(value, max_tokens=0) returned one token instead of none because the limit was checked after appending.
- Root cause: The loop appended the first match before comparing the collected length with the limit.
- Regression test: tests.retrieval.test_tokenization.TokenizationTests.test_explicit_token_limit_is_honored

### D-130: Build one deterministic build-time lexical snapshot
- Date / phase / commit: 2026-10-13, Phase 2.3A, 5a329c1
- Context: Retrieval must not repeat the eager adjacency/sorted snapshot allocation that the public graph APIs perform before any examination budget applies (D-126).
- Decision: build_search_index(graph, *, analysis_completeness) calls graph.entities() exactly once and graph.relationships() never; documents are sorted by canonical entity ID so insertion order is irrelevant. The index holds MappingProxyType-backed postings, document_lengths, document_frequency and documents_by_id plus document_count, term_count, posting_record_count and average_document_length (0.0 for an empty corpus). __post_init__ verifies lengths, posting ordering, uniqueness and term frequencies against the documents, so a corrupt or overridden container fails with RetrievalInvariantError rather than silently mis-ranking. Non-CodeGraph input raises InvalidSearchIndexError. snapshot_id is a UUID5 content digest of the documents and is explicitly not a repository revision, commit or provenance claim. The snapshot never observes later graph mutation; index construction is bounded only by the canonical entity count and no memory cap is claimed. build_search_index consumes already-produced analysis data and never calls scan_repository, parse_discovered_file or index_repository.
- Why: Equal graphs built in different insertion orders must produce equal indexes, so ordering cannot come from the mutable graph. Verifying statistics against the documents makes the posting lists trustworthy as a retrieval contract instead of an unchecked cache. A content digest gives callers a stable identity for result provenance without inventing repository revision data.
- Alternatives considered: Lazy graph iteration would need a new graph contract outside this phase. A cache or incremental update would introduce invalidation semantics this phase does not need. Claiming a memory cap without enforcing one would be dishonest, so only measured counts are reported.
- Consequences: Relationship changes after a build are invisible to the lexical snapshot; graph-aware context in Phase 2.3B is therefore built into the same snapshot rather than read from a possibly newer graph. Index size grows with tokens, which is the deliberate memory-for-latency trade.
- Files: src/arctrellis/retrieval/index.py, tests/retrieval/test_index.py

### D-131: Reuse the canonical analysis completeness vocabulary in retrieval
- Date / phase / commit: 2026-10-13, Phase 2.3A, 5a329c1
- Context: Search results need caller-supplied analysis context so a complete file scan is never mistaken for exhaustive repository semantics.
- Decision: retrieval imports AnalysisCompleteness from arctrellis.query instead of defining a parallel enum, and build_search_index accepts it with the existing UNKNOWN default. Retrieval never runs analysis, retains no RepositoryIndexResult and cannot infer completeness from graph size.
- Why: Phase 2.2 already established the canonical complete/partial/failed vocabulary and the rule that callers associate the summary with the same graph revision. A second vocabulary would let two subsystems disagree about the same fact.
- Alternatives considered: A retrieval-specific enum duplicates meaning and invites drift. Inferring completeness from the corpus invents a claim the analysis stages never made.
- Consequences: retrieval depends on query, graph and core but never on parsing, indexing or ingestion; the fresh-import and import-boundary tests enforce that direction. COMPLETE still describes file outcomes only, never runtime or semantic exhaustiveness.
- Files: src/arctrellis/retrieval/index.py, tests/retrieval/test_index.py

### D-132: Implement standard BM25 with a fixed exact-match boost ladder
- Date / phase / commit: 2026-10-13, Phase 2.3B, 0f55d1c
- Context: Pure BM25 can rank a long path above an exact symbol name, and no third-party ranking package is permitted.
- Decision: Implement BM25 in the standard library with k1=1.2, b=0.75, smoothed IDF ln(1 + (N - df + 0.5)/(df + 0.5)) and the standard tf saturation denominator. Exact-match tiers apply only the strongest satisfied rule: qualified name 8.0, entity name 6.0, canonical METHOD path 5.0, alphanumeric-equivalent name 3.0, name prefix 0.5 at four or more query characters. Every satisfied tier is still reported through match_reasons and matched_fields. relevance_score is exactly bm25_score + exact_match_boost + prefix_boost + graph_context_boost, verified finite on every hit and every score component exposed separately. document_length is the field-weighted length. An empty corpus is a defined zero; a zero average length drops the length-normalization term instead of dividing by zero. Weights are module constants that no query text, fixture name or entity name can change.
- Why: The ladder is a small, explicit, auditable ordering rather than an opaque weighting. Applying only the strongest tier prevents one document accumulating several bonuses for the same fact. BM25 sums over distinct query terms, so a repeated query token cannot inflate a score.
- Alternatives considered: rank-bm25 and Lucene add a dependency for arithmetic the standard library already expresses. Field-length tunings tuned against one benchmark would be overfitting. Multiplying boosts into the BM25 score or labelling any of it a probability would fabricate calibration.
- Consequences: A BM25 value is a lexical relevance score only: not a probability, not a confidence, not semantic correctness, not runtime likelihood and not graph confidence. It is never rendered as a percentage. Name-prefix matching only fires for prefixes of four or more characters, so short prefixes do not match everything.
- Files: src/arctrellis/retrieval/scoring.py, src/arctrellis/retrieval/search.py, tests/retrieval/test_scoring.py

### D-133: Project one bounded one-hop graph context from real relationships
- Date / phase / commit: 2026-10-13, Phase 2.3B, 0f55d1c
- Context: A developer searching payment creation should also see the endpoint that exposes createPayment, but retrieval must never invent an edge.
- Decision: context.py projects EXPOSES, CALLS, TESTS, WRITES_DATABASE, READS_DATABASE and APPLIES_MIDDLEWARE only, from one graph.relationships() read taken while building the snapshot. DEFINES, CONTAINS, INHERITS, USES and IMPORTS are never context and never stand in for CALLS. APPLIES_MIDDLEWARE is a pre-handler association weighted below invocation. Per-edge weights are EXPOSES 1.0, CALLS 0.8, WRITES_DATABASE 0.6, READS_DATABASE 0.5, TESTS 0.5, APPLIES_MIDDLEWARE 0.4; GRAPH_CONTEXT_BOOST_CAP is 1.0, equal to the largest edge weight, so the cap is a structural invariant rather than a tuned number. A candidate keeps the maximum contribution over its supporting relationships, never their sum, so degree cannot inflate a boost. A seed contributes in proportion to the share of distinct query terms it matched relative to the best seed, so a corpus where nothing matches every term still surfaces connected context. A neighbor need not contain the query terms: it is reported as match_basis=graph_neighbor with the stored relationship ID, kind, direction, confidence, confidence_score and original Evidence. Direction is expressed relative to the returned hit. Neighbor lists are capped per entity and direction at build time (default 16) and capped again per seed at query time (default 16); capped build-time lists are counted in context_capped_list_count. Expansion never visits a neighbor of a neighbor. Retrieval never calls an adjacency API per candidate.
- Why: One snapshot read means the lexical corpus and the relationship context can never come from two graph revisions, and it pays the eager public snapshot allocation once per build rather than once per hit. Grounding every contribution in a stored relationship keeps the boost auditable.
- Alternatives considered: Summing neighbor contributions would reward hubs. Requiring token overlap in the neighbor would delete exactly the case graph-aware retrieval exists for. An eager adjacency call per candidate would repeat the documented D-126 allocation problem. An LLM-written explanation is out of scope.
- Consequences: An entity with more than the cap neighbors is not fully represented, and the index reports how many lists were capped rather than implying complete coverage. A graph-context hit is a structural association, never a runtime or execution claim, and relationship confidence is reported separately instead of being multiplied into relevance.
- Files: src/arctrellis/retrieval/context.py, src/arctrellis/retrieval/search.py, tests/retrieval/test_context.py
- Symptom: An endpoint exposing a strongly matched handler was never returned, because a graph candidate had to share a query token lexically.
- Root cause: The first context policy required token overlap between the neighbor and the query, which excluded the documented discovery case by construction.
- Regression test: tests.retrieval.test_context.GraphContextTests.test_endpoint_discovers_its_linked_handler; test_handler_discovers_its_linked_endpoint
- Symptom: A graph-context support named the returned hit as its own neighbor, and the direction described the seed instead of the hit.
- Root cause: Supports were constructed while walking outward from the seed and then stored unchanged on the neighbor.
- Regression test: tests.retrieval.test_context.GraphContextTests.test_endpoint_discovers_its_linked_handler asserts the direction and the neighbor recorded from the hit's point of view.

### D-134: Rank fields by explicit weight rather than raw token repetition
- Date / phase / commit: 2026-10-13, Phase 2.3B, 0f55d1c
- Context: Phase 2.3B requires field-aware ranking, and the D-128 token counts let a repeated generic token in a long path outweigh a real symbol name.
- Decision: scoring.FIELD_WEIGHTS gives name 3.0, qualified_name/http_method/route_path 2.0, framework/provider/operation_kind/operation_name/target_name/imported_name/binding 1.5, module/alias/import_form/is_type_only/target_basis/effect_stage/registration_kind/composition_scope/path_completeness 1.0 and entity_kind/language/repository_relative_path 0.5. Every projected field name has a weight and unlisted fields keep the default 1.0. BM25 term frequency is the sum of per-field weighted counts and document length is the sum of weighted field lengths. All weights are exact binary fractions, so weighted counts compare exactly and results stay reproducible. This supersedes the raw token-count interpretation of document_lengths recorded in D-130.
- Why: Developers state intent in entity names far more often than in paths; a BM25F-style weighting expresses that without a second scoring pass or a dependency, and every weight is justifiable from the field's meaning rather than from a benchmark result.
- Alternatives considered: Unweighted counts let test_payments.py repeat payment three times and outrank a symbol named createPayment. A learned or benchmark-tuned weighting would overfit the golden set. Discarding path and kind fields would remove useful recall.
- Consequences: document_length is a float weighted length rather than a raw token count; SearchDocument.token_count still reports the raw count. Every field weight is asserted by a test so a new projected field cannot silently fall back to the default.
- Files: src/arctrellis/retrieval/scoring.py, src/arctrellis/retrieval/index.py, tests/retrieval/test_scoring.py
- Supersedes: D-130 (raw token-count document lengths and posting frequencies are replaced by weighted values)

### D-135: Separate filter eligibility, candidate budgets and truncation reporting
- Date / phase / commit: 2026-10-13, Phase 2.3B, 0f55d1c
- Context: top_k must apply to eligible filtered results, while graph-aware discovery must still work through a kind filter, and budgets must only claim what they actually bound.
- Decision: Filters mark a candidate eligible or ineligible; ineligible candidates are removed before ranking, so a filter always constrains output and top_k always applies to eligible results. Seeds for graph context are the strongest lexical matches in the whole corpus, so search_endpoints(index, "createPayment", include_graph_context=True) can return the exposing endpoint; graph-discovered candidates are filtered on creation. Blank, whitespace-only, token-free, over-512-character and over-24-token queries are rejected with InvalidSearchQueryError rather than answered. Limits are positive non-boolean integers, top_k is capped at 100, default posting budget is 50000 examined records, default graph seed budget 25 and default neighbor budget 16. Every posting record actually inspected consumes the budget, including records later rejected by a filter. Truncation reasons are the closed set posting_budget, graph_seed_budget and graph_neighbor_budget; truncated reports budget-driven incompleteness only, while top_k limiting is reported through eligible_candidate_count. Candidate counts are exact only when truncated is False. Field values are stored truncated to 512 characters with at most 32 tokens each; the canonical CodeEntity keeps the full value.
- Why: Filtering during the posting scan would make an endpoint unreachable when no endpoint matches lexically, defeating the documented discovery flow. Claiming a bound the counter does not govern would be dishonest, so only inspected posting records are counted and the pre-budget snapshot allocation stays explicitly outside it.
- Alternatives considered: Filtering before scanning loses context discovery. Counting only filter-passing records would understate real work. Silently capping rather than reporting would hide incompleteness.
- Consequences: A query whose budget is exhausted may omit eligible documents and must be read as incomplete. Candidate sets are bounded by matched candidates plus seeds times neighbors. No memory cap is claimed for index construction, which remains bounded only by the canonical entity count.
- Files: src/arctrellis/retrieval/search.py, src/arctrellis/retrieval/documents.py, tests/retrieval/test_limits.py, tests/retrieval/test_search.py

### D-136: Expose one ranking entry point with kind-restricted delegating wrappers
- Date / phase / commit: 2026-10-13, Phase 2.3B, 0f55d1c
- Context: The public API needs endpoint, test and database-operation searches without a second scoring implementation or near-duplicate aliases.
- Decision: search_symbols is the single scoring entry point and searches every indexed canonical entity kind; search_endpoints, search_tests and search_database_operations delegate to it with a merged entity-kind filter and never reimplement ranking. A wrapper merges its restriction with a caller-supplied SearchFilters instead of replacing it, and unknown option names still fail inside search_symbols. Typed filters cover entity kinds, languages, path prefixes, HTTP method, framework, database provider, database operation kind and endpoint path completeness, matching only canonical attributes and allowlisted projected values; an absent value never satisfies a filter. SearchHit, SearchResult, SearchFilters, MatchBasis and ContextSupport are frozen and to_dict returns JSON primitives only. No web API, CLI or persistence is introduced.
- Why: One engine keeps score semantics, budgets, ordering and serialization identical across entry points, and filters read only grounded canonical values so retrieval never infers meaning from a name or filename.
- Alternatives considered: Separate ranking implementations would drift. Aliases such as search_entities would duplicate behavior with a different name. Inferring filters from names or file paths would fabricate facts.
- Consequences: Despite its name search_symbols is not restricted to declarations; the wrappers are the restricted forms. Empty filter sets are rejected rather than treated as match-nothing. Scores are relevance only, and a result never claims completeness, runtime behavior or repository coverage.
- Files: src/arctrellis/retrieval/search.py, src/arctrellis/retrieval/__init__.py, tests/retrieval/test_search.py

### D-137: Add a deterministic evaluation harness with independent relevance judgments
- Date / phase / commit: 2026-10-13, Phase 2.3C, d8f5c95
- Context: Retrieval quality must be measured rather than asserted, and the judgments must not be derived from the ranking they judge.
- Decision: Add src/arctrellis/retrieval/evaluation.py with ExpectedEntity (kind/name/optional path selectors, never canonical UUIDs), RelevanceJudgment (query, expected selectors, category exact/multi_entity/conceptual, note), QueryOutcome, RetrievalMetrics, ModeEvaluation, RetrievalEvaluationResult, evaluate_retrieval and format_evaluation. Metrics at a documented cut-off k: recall@k = |top-k retrieved and relevant| / |relevant|; precision@k = |top-k retrieved and relevant| / k; mrr@k = 1/rank of the first relevant result inside the top k else 0; hit_rate@k = 1 when any relevant result is inside the top k. All are macro-averaged over evaluated queries. A judgment whose selectors resolve to nothing in the corpus is skipped and reported in skipped_queries, never averaged as zero. Unresolved selectors are reported in unresolved_judgment_labels. Duplicate retrieved identifiers are de-duplicated by first occurrence and counted. Invalid k, non-sequence judgments, non-judgment items, duplicate queries and unknown modes raise RetrievalEvaluationError. Judgments live in tests/retrieval/judgments.py, outside the ranking package.
- Why: Explicit judgments written from repository reasoning are the only way to check ranking without circularity. Reporting skipped and unresolved queries honestly avoids manufacturing numbers from empty targets.
- Alternatives considered: Deriving expectations from the ranking is circular. Graded nDCG needs relevance grades this corpus cannot justify. A third-party evaluation package adds a dependency for arithmetic the standard library expresses.
- Consequences: These are lexical retrieval measurements on a small synthetic corpus. They are not a semantic benchmark and do not generalize to real repositories. A skipped query and a zero-recall query are visibly different.
- Files: src/arctrellis/retrieval/evaluation.py, tests/retrieval/judgments.py, tests/retrieval/test_golden.py

### D-138: Compare an independent exact/substring baseline and report regressions honestly
- Date / phase / commit: 2026-10-13, Phase 2.3C, d8f5c95
- Context: A single self-evaluation proves nothing; the improvement claim must be measured against a weaker system and against its own failures.
- Decision: Provide exact_substring_baseline, a non-statistical ranking by exactness tier (exact normalized value, normalized substring, all query tokens contained, any shared token), then by matching-field count and canonical entity ID. It shares no code with BM25, field weights, boosts or graph context. evaluate_retrieval always runs all three modes and records which queries each mode improved and regressed against the baseline. Measured at K=5 over 19 evaluated queries of 20 judgments: baseline Recall 0.8246, Precision 0.3158, MRR 0.7298, HitRate 0.8947; BM25 Recall 0.8860, Precision 0.3474, MRR 0.8070, HitRate 0.9474; BM25+graph Recall 0.8860, Precision 0.3211, MRR 0.8553, HitRate 0.9474. Graph context improves MRR but lowers precision, improves listPayments, createPayment, persistPayment, payment creation and payment database write, and regresses test payment. BM25 regresses test payment against the baseline (rank 1 to rank 2). payment refund endpoint is missed by every mode because no document contains all of payment, refund and endpoint. The repository change that added listAllPayments moved graph Recall from 0.9035 to 0.8860, so the pinned values were re-measured rather than preserved.
- Why: Reporting only wins would misrepresent the feature. The numbers are pinned in tests as a regression guard, and the failure modes are named so a future change is evaluated against real evidence.
- Alternatives considered: Tuning weights until every query succeeds would overfit 19 judgments. Dropping the conceptual queries would hide exactly the cases a developer cares about.
- Consequences: No universal retrieval-quality claim is made. Adding or changing a judgment legitimately changes the measured values and requires re-measuring, which the pinned test forces explicitly.
- Files: src/arctrellis/retrieval/evaluation.py, tests/retrieval/test_golden.py, tests/retrieval/smoke.py

### D-139: Add a mixed-language retrieval repository and hard-negative contracts
- Date / phase / commit: 2026-10-13, Phase 2.3C, d8f5c95
- Context: Retrieval must be verified against real analysis output and must refuse to invent repository facts under adversarial input.
- Decision: Add tests/retrieval/repository.py with a Python FastAPI/SQLAlchemy service, a JavaScript Express/Prisma service and a TypeScript Prisma service, containing a PaymentService class, reused symbol names across files and languages, duplicated TypeScript and cross-language POST /payments registrations, an unresolved call, a fake client function and a staged mutation. Run it through the complete existing pipeline; never seed graph facts manually. Add tests/retrieval/test_hardening.py covering wrong-kind filters, distinguishable similar names, duplicate names and routes, unknown metadata, unresolved calls, staged operations, direct-test semantics, fake framework shapes, instruction-like and path-like query text, missing locations, incomplete analysis, snapshot isolation, adversarial Unicode, control characters, oversized values, fresh-process import isolation, package import boundaries and the absence of fixture names as ranking literals. Also verify that a retrieved endpoint ID is accepted unchanged by trace_endpoint_to_database and that its existing evidence path is preserved.
- Why: Hard negatives are where a retrieval layer invents facts. Testing them against real analysis output proves the projection, not a hand-built graph.
- Alternatives considered: Unit-only synthetic graphs cannot show integration defects. Relaxing the injection and traversal cases would weaken the security boundary.
- Consequences: In the measured run 83 entities produce 83 documents, 116 terms and 675 posting records; five of seven retrieved endpoints retain an existing evidence path, and POST /payments [app.py] and DELETE /payments/{paymentId} return NO_KNOWN_PATH because their handlers call service methods that call resolution cannot resolve. All nine smoke queries report truncated=True with the single reason graph_seed_budget, because 35 lexical candidates exceed the default 25-seed budget while the 50000 posting budget is never reached; this is reported rather than hidden.
- Files: tests/retrieval/repository.py, test_hardening.py, smoke.py, README.md
- Symptom: A search whose only graph-supported hits fell outside top_k raised ValueError from SearchResult construction.
- Root cause: graph_context_used was computed from the full ranked tuple instead of the returned top_k slice, so it claimed context that the caller could not see.
- Regression test: tests.retrieval.test_golden.GoldenRetrievalTests.test_exact_symbol_queries_return_the_symbol_first and the end-to-end smoke run.
- Symptom: An oversized allowlisted metadata value was stored in full on the search document.
- Root cause: build_document bounded only the tokenization input and stored the untruncated value, so the document could retain an arbitrarily long string.
- Regression test: tests.retrieval.test_limits.ResourceLimitTests.test_oversized_metadata_value_is_bounded_at_index_build

### D-140: Bound stored field values to the documented projection limit
- Date / phase / commit: 2026-10-13, Phase 2.3C correction, d8f5c95
- Context: D-128 promised bounded searchable values, but only tokenization was bounded.
- Decision: build_document truncates every projected field value to MAX_FIELD_VALUE_LENGTH (512 characters) before storing and tokenizing it. The canonical CodeEntity keeps its full metadata, so no repository fact is lost; only the search projection is bounded. Supersedes the D-128 statement that only the tokenization input is truncated.
- Why: A document that can retain an unbounded string is a memory risk that the documented limit does not cover, and the projection exists only to make names searchable.
- Alternatives considered: Skipping over-long values entirely would make an otherwise retrievable entity unreachable. Raising the limit would weaken the bound.
- Consequences: A hit can display a truncated metadata value; the canonical entity remains the authority and its full value is available through the analysis result.
- Files: src/arctrellis/retrieval/documents.py, tests/retrieval/test_limits.py
- Supersedes: D-128 (projected field values are now stored truncated, not only tokenized truncated)

### D-141: Export the evaluation surface from the retrieval package
- Date / phase / commit: 2026-10-13, Phase 2.3C correction, d65d083
- Context: A final public-API import check found evaluate_retrieval and its models were importable only from arctrellis.retrieval.evaluation, not from the documented package entry point.
- Decision: Re-export BASELINE, BM25, GRAPH, EVALUATION_MODES, ExpectedEntity, ModeEvaluation, QueryOutcome, RelevanceJudgment, RetrievalEvaluationError, RetrievalEvaluationResult, RetrievalMetrics, evaluate_retrieval, exact_substring_baseline and format_evaluation from arctrellis.retrieval, and assert the documented entry-point imports in a fresh interpreter. The package exports 67 deliberate names; private helpers stay private.
- Why: The documented public API promises evaluation types alongside search types; a half-exported surface forces callers to know internal module paths and weakens the boundary the export list exists to create.
- Alternatives considered: Leaving evaluation submodule-only would work technically but contradicts the documented API and the isolation test that checks it.
- Consequences: Importing arctrellis.retrieval pulls in the evaluation module, which depends only on the retrieval modules already loaded and adds no analysis, parser or network dependency. The fresh-process import test now fails if any analysis or runtime module is pulled in.
- Files: src/arctrellis/retrieval/__init__.py, tests/retrieval/test_index.py, tests/retrieval/test_hardening.py
- Symptom: from arctrellis.retrieval import evaluate_retrieval raised ImportError.
- Root cause: The package __init__ was written before evaluation.py existed and was never extended.
- Regression test: tests.retrieval.test_index.IndexContractTests.test_retrieval_import_boundary_and_fresh_public_import and tests.retrieval.test_hardening.BoundaryAndIsolationTests.test_fresh_public_import_does_not_load_analysis_or_runtime_dependencies

### D-142: Validate structured query requests against a per-intent option contract
- Date / phase / commit: 2026-10-13, Phase 2.4A, uncommitted
- Context: The structural query engine traces stored relationships and the retrieval engine ranks canonical entities, but nothing described what a caller was asking for. Without an explicit contract a free-form string could silently acquire an architectural meaning, and an option the chosen backend ignores would look like it worked.
- Decision: Add arctrellis.orchestration with QueryIntent, a fixed nine-member intent vocabulary, and an immutable QueryRequest validated in __post_init__. Every intent declares an IntentSpec: required source entity kinds, allowed selector forms, the named structural query it executes, and which option families it consumes. A supplied non-default option that the intent does not declare is rejected with UnsupportedIntentError; a selector the intent does not declare is rejected rather than reinterpreted. Budget fields belong to exactly one family: top_k and max_examined_postings are retrieval budgets, max_paths, max_depth and max_expansions are traversal budgets. Limits must be positive non-boolean integers and top_k is capped at the existing retrieval cap. No natural-language intent inference exists: search_text is retrieval input only.
- Why: Rejecting an unused option is the only way a caller learns that graph-context ranking, transitive callers or an operation-kind filter had no effect. Mutually exclusive selector forms stop one request from silently meaning two different things, and the SPECS table keeps that policy inspectable instead of buried in branches.
- Alternatives considered: Ignoring unknown options is friendlier but hides caller mistakes. A free-form intent string with keyword matching would have been shorter and would have made "show me what happens when payment is created" imply a trace, which this phase explicitly must not do. A generalized workflow language would have grown beyond the nine existing query backends.
- Consequences: Adding an intent requires an IntentSpec row, a planning branch and an execution branch; an intent cannot exist without a real query backend. Selector semantics depend on the intent, so the same HTTP method and route pair is a selector for TRACE_ENDPOINT_TO_DATABASE and a list filter for LIST_ENDPOINTS, reported as distinct SelectorForm values. An option rejected here never reaches a query engine.
- Files: src/arctrellis/orchestration/models.py, src/arctrellis/orchestration/planning.py, tests/orchestration/test_requests.py, tests/orchestration/test_plans.py

### D-143: Resolve canonical entities exactly, and never select from a lexical ranking
- Date / phase / commit: 2026-10-13, Phase 2.4B, uncommitted
- Context: Retrieval evaluation showed a canonical CLASS can rank below an identically named IMPORT, and that similar symbol names create ambiguous results. Choosing a structural-query target from a BM25 rank would make a relevance measurement stand in for entity identity, which is the failure mode this product exists to avoid.
- Decision: Selection returns an explicit status and never guesses. An exact canonical entity ID resolves directly after its kind is verified against the intent's required source kinds. An exact qualified name or an exact METHOD plus route resolves only when exactly one eligible canonical entity matches; more than one is AMBIGUOUS with the full candidate set. A lexical query returns SelectionStatus.CANDIDATES and names no entity, so no structural query can run against a merely well-ranked candidate. Search results are never promoted to a selection. entity_kind, language, path_prefix, framework and endpoint_scope are constraints that narrow a caller's own selector; they never choose. Snapshot construction indexes qualified names and routes exactly, so exact-match ambiguity claims are exhaustive rather than drawn from a truncated candidate subset.
- Why: A high lexical score is a measurement of token overlap and field weights, not proof of which canonical entity the caller meant. Reporting ambiguity with the exact candidate set keeps the decision with the person who knows the repository.
- Alternatives considered: Accepting the top hit when it is unique would have removed an entire failure mode and would have silently executed a trace against the wrong entity. Resolving an exact qualified name to the first match would have been deterministic but wrong. Restricting selection to entity IDs alone would have been safest but unusable, because a caller normally knows the method and path rather than a UUID5 identifier.
- Consequences: Callers that want a structural query must supply an exact entity ID, an unambiguous qualified name or an unambiguous METHOD plus route. Duplicate registrations are a first-class expected outcome and are surfaced in the bundle rather than resolved. Candidate lists are bounded at MAX_SELECTION_CANDIDATES (25) and report whether the list was truncated; a resolved selection never reports truncation because exact lookup is exhaustive.
- Files: src/arctrellis/orchestration/selection.py, src/arctrellis/orchestration/pipeline.py, tests/orchestration/test_selection.py, tests/orchestration/test_end_to_end.py
- Symptom: An early draft reported the lexical search outcome as RESOLVED while naming no entity, which the SelectionResult contract then had to reject; the same conflation would have let a bundle claim a resolved source it did not have.
- Root cause: The first draft reused RESOLVED for "the search ran" as well as "one entity was identified".
- Regression test: tests.orchestration.test_selection.LexicalCandidateSelectionTests.test_top_ranked_candidate_is_not_promoted_to_a_selection and tests.orchestration.test_selection.LexicalCandidateSelectionTests.test_fuzzy_retrieval_returns_candidates_and_selects_nothing

### D-144: Project stored relationships into bundles without adding content or certainty
- Date / phase / commit: 2026-10-13, Phase 2.4C, uncommitted
- Context: A bundle is the product a future CLI, HTTP API or explanation layer will consume. It must carry the evidence that supports a claim and nothing that would let a reader overstate that evidence.
- Decision: ExecutionOutcome dispatches to the existing arctrellis.query functions and returns their PathQueryResult or EntityQueryResult unchanged; no relationship, confidence value, Evidence record or relationship identity is created, altered or removed. Retrieval relevance is never allowed to change a stored CALLS, EXPOSES, READS_DATABASE, WRITES_DATABASE or TESTS confidence. EvidenceBundle keeps schema_version 1, the request, the plan, the selection outcome, the selected entity, candidates, ranked search hits, evidence paths, analysis completeness, retrieval and graph truncation reasons and explicit limitations. Each relationship keeps its ID, kind, direction, confidence classification, numeric score, original Evidence IDs, source locations and analysis methods. Confidence is summarized with the existing weakest-edge contract and is never multiplied into a probability. Entity projection deliberately omits the declaration signature and all entity metadata outside a nine-key allowlist, because a signature is source text. IMPORTS, DEFINES, TESTS and APPLIES_MIDDLEWARE are never converted into execution edges, and a query that finds nothing returns NO_KNOWN_PATH with the limitation that no known path is not proof of absence.
- Why: The analysis engine establishes what source evidence supports and the explanation layer explains that evidence. A bundle that paraphrased, re-ranked or enriched a stored record would break that separation at exactly the point a reader trusts it.
- Alternatives considered: Reusing the query package's entity_dict serializer was shorter but includes the declaration signature, which is source content; a bundle must not carry source snippets. Emitting a single overall path confidence would have been more readable and would have hidden which edge is weakest.
- Consequences: Bundles are larger than the internal query results but stable and self-describing. Entity metadata outside the allowlist is not reachable through a bundle; the canonical analysis result remains the authority for it. Serialization is JSON primitives only and contains no timestamp, absolute path, source byte or traceback, so equal requests over equal snapshots serialize identically.
- Files: src/arctrellis/orchestration/execution.py, src/arctrellis/orchestration/evidence.py, src/arctrellis/orchestration/models.py, tests/orchestration/test_execution.py
- Symptom: ExecutionOutcome originally asserted that a nonempty path list implied a path result, so any query that legitimately returned zero paths raised OrchestrationInvariantError.
- Root cause: The invariant used truthiness instead of identity with the originating result; an empty PathQueryResult is a valid, meaningful outcome.
- Regression test: tests.orchestration.test_execution.RouteWithoutDatabaseTests.test_route_with_no_database_path_reports_no_known_path and tests.orchestration.test_execution.EndpointTraceTests.test_route_with_no_database_path_reports_no_known_path

### D-145: Build the retrieval snapshot from the final analysis graph and assert the projection
- Date / phase / commit: 2026-10-13, Phase 2.4D, uncommitted
- Context: Developers had to know the real stage order of seven analysis packages and then manually build a retrieval index, with nothing guaranteeing that the index and the structural graph described the same repository state.
- Decision: analyze_repository(root) is the single programmatic entry point. It runs the verified dependency order index_repository, resolve_imports, resolve_calls, resolve_http_endpoints, resolve_framework_flow, analyze_tests, materialize_database_graph, then builds the retrieval index from that final database-and-test-enriched graph. AnalysisSnapshot keeps the final CodeGraph, the LexicalSearchIndex built from it, measured counts, analysis completeness and exact qualified-name and route lookups. Construction verifies that the retrieval documents correspond one-to-one with the final graph entities and raises OrchestrationInvariantError otherwise. No ParsedSource, syntax tree or source byte is retained by any stage, and no mutation path is exposed in the public API. Discovery failures and graph-collision invariants keep propagating as their existing typed ingestion and indexing errors rather than being swallowed; per-file failures remain bounded FAILED or PARTIAL outcomes and are visible through the counts and completeness.
- Why: Serving structural queries and lexical search from two different graph states would produce internally inconsistent answers with no way for a caller to detect it. Asserting the one-to-one projection turns that silent mismatch into an explicit failure at snapshot construction.
- Alternatives considered: Caching analysis results between invocations would help repeated queries but introduces a persistence format and a staleness question that belong to a later phase. Freezing or copying the graph would claim immutability the existing mutable CodeGraph contract does not provide.
- Consequences: AnalysisSnapshot is a frozen record over a mutable CodeGraph and does not freeze it; callers must treat a snapshot as a completed, unmutated revision exactly as the existing phase results require. One analyze_repository call holds the final graph and the retrieval index in memory and drops the intermediate stage results. Snapshot identity is the retrieval content digest, not a revision claim.
- Files: src/arctrellis/orchestration/pipeline.py, tests/orchestration/test_pipeline.py
