# System Flow

## 1. Package installation and imports

Input: a local checkout and Python >=3.13. Packaging reads pyproject.toml.

```text
python -m pip install -e .                 pyproject.toml; install the src package
 └─ setuptools.build_meta                 build backend; discover arctrellis under src
from arctrellis.core import ...            src/arctrellis/core/__init__.py; stable public API
 └─ import .models                        src/arctrellis/core/models.py; load domain types
from arctrellis.graph import ...           src/arctrellis/graph/__init__.py; public graph API
 ├─ import .errors                        src/arctrellis/graph/errors.py; expose intentional failures
 ├─ import .graph                         src/arctrellis/graph/graph.py; load CodeGraph
 │   └─ import .results                   src/arctrellis/graph/results.py; load query records
 └─ import .results                       src/arctrellis/graph/results.py; export immutable results
from arctrellis.ingestion import ...       src/arctrellis/ingestion/__init__.py; public inventory API
 ├─ import .discovery                     src/arctrellis/ingestion/discovery.py; metadata-only scan
 ├─ import .models                        src/arctrellis/ingestion/models.py; immutable inventory
 └─ import .errors                        src/arctrellis/ingestion/errors.py; explicit discovery failures
from arctrellis.parsing import ...         src/arctrellis/parsing/__init__.py; owned syntax API
 ├─ import .models                        src/arctrellis/parsing/models.py; native-independent values
 ├─ import .errors                        src/arctrellis/parsing/errors.py; typed infrastructure failures
 └─ import .parser                        src/arctrellis/parsing/parser.py; single-file entry points
from arctrellis.extraction import ...      src/arctrellis/extraction/__init__.py; canonical entity output
 ├─ import .models                        src/arctrellis/extraction/models.py; immutable local ownership
 ├─ import .ids                           src/arctrellis/extraction/ids.py; reproducible identity
 ├─ import .errors                        src/arctrellis/extraction/errors.py; caller-facing failures
 ├─ import .python                        src/arctrellis/extraction/python.py; normalized Python semantics
 ├─ import .javascript                    src/arctrellis/extraction/javascript.py; shared normalized JS/TS semantics
 └─ import .lexical                       src/arctrellis/extraction/lexical.py; proven single-file graph assembly
```

Output: importable domain, graph, ingestion, parsing, extraction, indexing, resolution, calls and framework APIs. Installation failures propagate from pip.
There is no service process, API or persistence.

## 2. Source locations and entities

Input: caller-supplied IDs, enums, paths, names and optional ownership/language data.

```text
SourceLocation(...)                       src/arctrellis/core/models.py; identify a source range
 └─ SourceLocation.__post_init__()         validate unmodified relative path and integer lines
     └─ _require_text()                   reject missing, padded or mistyped path strings
CodeEntity(...)                           src/arctrellis/core/models.py; represent a named concept
 └─ CodeEntity.__post_init__()             validate required and optional fields
     ├─ _require_text()                   enforce meaningful IDs and names
     ├─ _require_instance()               enforce EntityKind and optional SourceLocation types
     └─ _validate_metadata()              ensure immutable pairs and unique keys
         └─ _require_text()               validate metadata keys
```

Output: frozen, hashable records retained by the caller. Lines are inclusive and
1-based. Paths use forward slashes; no file access or silent normalization occurs.
Wrong types raise TypeError; invalid values raise ValueError during construction.
Phase 1.2 adds optional signature as the last CodeEntity constructor field; validation
uses _require_text and preserves internal newlines and prior positional metadata.

## 3. Evidence and directional relationships

Input: validated locations, an analysis method, source/target IDs, relation kind,
confidence classification, optional score and zero or more evidence records.

```text
Evidence(...)                             src/arctrellis/core/models.py; record source support
 └─ Evidence.__post_init__()               validate location, method identifier and metadata
     ├─ _require_text()                   validate evidence ID and method
     ├─ _require_instance()               require a SourceLocation
     └─ _validate_metadata()              preserve immutable extension data
         └─ _require_text()               validate metadata keys
Relationship(...)                         src/arctrellis/core/models.py; assert source → kind → target
 └─ Relationship.__post_init__()           validate classification, score and evidence tuple
     ├─ _require_text()                   require relationship, source and target IDs
     └─ _require_instance()               require enums and embedded Evidence records
```

Output: an immutable assertion, not a verified analysis result. PROVEN, LIKELY,
POSSIBLE and UNRESOLVED retain the producer's stated uncertainty. Scores must be
finite and in [0, 1]; no score/classification mapping is assumed. Embedded evidence
IDs must be unique within a relationship. Invalid types/values fail explicitly.
Global IDs, target existence and proof adequacy are not checked by domain constructors.

## 4. Unit tests and primitive conversion

Input: installed package and tests under tests/core/, tests/graph/, tests/ingestion/, tests/parsing/ and tests/extraction/.

```text
python -m unittest discover -s tests -v    tests/__init__.py and tests/core/__init__.py; discover tests
 └─ unittest.TestCase test methods         tests/core/test_models.py; exercise public constructors
     ├─ public domain constructors        src/arctrellis/core/models.py; check invariants
     └─ dataclasses.asdict() → json.dumps() primitive conversion; validate JSON compatibility
 └─ graph contract test methods            tests/graph/test_graph.py, test_traversal.py, test_results.py
     ├─ payment_graph()                   tests/graph/fixtures.py; name the synthetic payment entities
     │   └─ build_graph()                 tests/graph/fixtures.py; insert explicitly supplied facts
     ├─ build_graph()                     tests/graph/fixtures.py; build smaller contract examples
     └─ CodeGraph / GraphPath APIs         src/arctrellis/graph/; check storage and query contracts
 └─ ingestion contract test methods        tests/ingestion/test_models.py, test_discovery.py, test_safety.py
     ├─ tempfile.TemporaryDirectory()      isolate local synthetic trees without network
     ├─ scan_repository()                 exercise metadata discovery without target execution
     └─ unittest.mock.patch()             inject access failures and verify exclusion pruning
 └─ parsing test methods                  tests/parsing/test_models.py, test_registry.py, test_parser.py
     ├─ parse_source()                    exercise grammar recovery, isolation and normalized models
     ├─ scan_repository()                 obtain real DiscoveredFile fixtures
     └─ parse_discovered_file()           verify content reads, limits and non-execution
 └─ extraction test methods               tests/extraction/test_ids.py, test_models.py, test_python.py, test_imports.py, test_javascript.py, test_lexical.py
     ├─ parse_source()                    supply normalized syntax fixtures, not native objects
     ├─ extract_python_entities()         verify lexical entities, identity, encoding and conservative recovery
     ├─ extract_entities()               dispatch JS/TS/TSX canonical semantics without execution
     ├─ build_lexical_graph()             verify parent edges, exact proof and existing shortest_path
     └─ scan_repository()/parse_discovered_file() verify the real local pipeline and non-execution
```

Output: test results on stdout/stderr and process exit status. A failing assertion
fails the suite. There is no production serialization or database format yet.

## 5. Graph construction, lookup and snapshots

Input: caller-created CodeEntity and Relationship records. All graph storage is
in memory; immutable domain objects are retained by reference.

```text
CodeGraph.__init__()                      src/arctrellis/graph/graph.py; allocate storage and indexes
CodeGraph.add_entity()                    src/arctrellis/graph/graph.py; protect entity identity
 └─ compare existing record               accept equal values; reject conflicting IDs before mutation
CodeGraph.add_relationship()              src/arctrellis/graph/graph.py; protect edge identity
 ├─ compare existing record               accept equal values without duplicating adjacency
 ├─ CodeGraph.get_entity(source ID)       verify source before inserting anything
 │   └─ _require_id()                     require a string lookup ID
 ├─ CodeGraph.get_entity(target ID)       verify target before inserting anything
 │   └─ _require_id()                     require a string lookup ID
 ├─ store relationship by ID              preserve the canonical edge and its evidence
 ├─ bisect.insort(outgoing IDs)            enable ordered forward adjacency
 └─ bisect.insort(incoming IDs)            enable ordered reverse adjacency
CodeGraph.get_entity()                    src/arctrellis/graph/graph.py; direct canonical entity lookup
 └─ _require_id()                         reject nonstring IDs before dictionary access
CodeGraph.get_relationship()              src/arctrellis/graph/graph.py; direct canonical edge lookup
 └─ _require_id()                         reject nonstring IDs before dictionary access
CodeGraph.has_entity()                    src/arctrellis/graph/graph.py; explicit entity existence check
 └─ _require_id()                         require exact string IDs without normalization
CodeGraph.has_relationship()              src/arctrellis/graph/graph.py; explicit edge existence check
 └─ _require_id()                         require exact string IDs without normalization
CodeGraph.entities()                      src/arctrellis/graph/graph.py; sort entity IDs into a tuple
CodeGraph.relationships()                 src/arctrellis/graph/graph.py; sort edge IDs into a tuple
```

Output: consistent canonical dictionaries and sorted adjacency lists; insertions
return None. Equal value duplicates are idempotent. Conflicting same-ID objects
raise DuplicateEntityError/DuplicateRelationshipError. Missing endpoints raise
UnknownEntityError without adding an edge or changing indexes. Missing lookup IDs
raise UnknownEntityError/UnknownRelationshipError; malformed argument types raise
TypeError. Parallel edges and self-loops are allowed. Parent/evidence global IDs
are not validated. This append-oriented mutable container is not thread-safe.

## 6. Direct adjacency and neighboring entities

Input: a known entity ID and optional RelationshipKind filter.

```text
CodeGraph.successors()                    src/arctrellis/graph/graph.py; unique outgoing neighbors
 └─ CodeGraph.outgoing()                  inspect source-indexed edges, sorted by edge ID
     ├─ CodeGraph.get_entity()            fail unknown IDs explicitly
     │   └─ _require_id()                 require a string ID
     ├─ _single_kind()                    validate and snapshot the optional enum filter
     └─ CodeGraph._adjacent()             read only this entity's outgoing degree
CodeGraph.predecessors()                  src/arctrellis/graph/graph.py; unique incoming neighbors
 └─ CodeGraph.incoming()                  inspect target-indexed edges, sorted by edge ID
     ├─ CodeGraph.get_entity()            fail unknown IDs explicitly
     │   └─ _require_id()                 require a string ID
     ├─ _single_kind()                    validate the optional enum filter
     └─ CodeGraph._adjacent()             read only this entity's incoming degree
```

Output: immutable edge tuples sorted by relationship ID, or unique neighbor tuples
sorted by entity ID. Isolated known nodes return empty tuples. Unknown nodes raise
UnknownEntityError; raw-string kind filters raise TypeError. Canonical records and
evidence remain intact; no relationship inference occurs.

## 7. Bounded traversal and shortest paths

Input: known starting/end IDs, nonnegative integer depth for traversal, and an
optional set/frozenset of RelationshipKind values. None permits all edges; an empty
set permits none.

```text
CodeGraph.traverse_forward()              src/arctrellis/graph/graph.py; follow outgoing edges
 └─ CodeGraph._traverse()                 delegate to the shared bounded flow below
CodeGraph.traverse_reverse()              src/arctrellis/graph/graph.py; follow incoming edges
 └─ CodeGraph._traverse()                 delegate to the shared bounded flow below
CodeGraph._traverse()                     src/arctrellis/graph/graph.py; validate start and depth
 ├─ CodeGraph.get_entity()                reject unknown starting nodes
 │   └─ _require_id()                     require string IDs
 ├─ _selected_kinds()                     validate and freeze filters
 ├─ CodeGraph._breadth_first()            discover each reachable node once up to max_depth
 │   └─ CodeGraph._adjacent()             expand sorted indexed edges; enqueue unseen neighbors
 └─ TraversalResult(...)                  src/arctrellis/graph/results.py; immutable discovery-order nodes
     └─ TraversalResult.__post_init__()    validate nonempty distinct entity records
         └─ _require_records()           enforce tuple ownership and CodeEntity types
CodeGraph.shortest_path()                 src/arctrellis/graph/graph.py; find an unweighted directed route
 ├─ CodeGraph.get_entity(source ID)       validate source even for a same-node query
 │   └─ _require_id()                     require a string ID
 ├─ CodeGraph.get_entity(target ID)       distinguish unknown target from disconnection
 │   └─ _require_id()                     require a string ID
 ├─ _selected_kinds()                     validate optional edge kinds
 ├─ CodeGraph._breadth_first()            track first discovery edge for each node
 │   └─ CodeGraph._adjacent()             use relationship-ID order to resolve equal-length ties
 └─ CodeGraph._build_path()               walk parent edges backward and reverse the route
     └─ GraphPath(...)                    src/arctrellis/graph/results.py; retain original proof edges
         └─ GraphPath.__post_init__()      validate cardinality and directed continuity
             └─ _require_records()       require immutable tuples of domain records
```

Output: TraversalResult contains only distinct nodes, including the start first,
in BFS discovery order. A GraphPath contains one more entity than relationship;
same-node queries produce a one-entity zero-edge path. Known disconnected pairs
return None. Unknown nodes raise graph errors; invalid depth/filter types raise
TypeError and negative depth raises ValueError. Visitation is recorded at discovery
to stop cycles and parallel-edge repetition. Queries follow inserted records
without filtering confidence or asserting new proof. BFS is O(V+E) over explored
nodes/edges because sorted adjacency is maintained at insertion.

## 8. Local repository discovery

Input: an existing local directory and optional replacement set/frozenset of excluded
directory names. No Git repository is required. The tree must remain stable.

```text
scan_repository()                         src/arctrellis/ingestion/discovery.py; inventory metadata only
 ├─ _excluded_names()                     validate and snapshot explicit name exclusions
 ├─ _normalize_root()                     establish a lexical absolute runtime boundary
 │   ├─ os.fspath()                       accept a string or local path object
 │   ├─ os.path.abspath()                 normalize lexical root without resolving links
 │   ├─ os.lstat()                        inspect root and ancestors without following final links
 │   └─ _link_reason()                    reject indirect root components
 └─ _walk_directory()                     visit ordinary directories with an iterative stack
     ├─ _check_directory()                detect changed directory identity before descent
     │   ├─ os.lstat()                    refresh non-following metadata
     │   └─ _link_reason()                reject new indirection
     ├─ os.scandir()                      enumerate metadata, never open file contents
     │   ├─ entry.stat(follow_symlinks=False) distinguish ordinary files, directories and links
     │   ├─ _link_reason()                classify links, junctions and other reparse omissions
     │   ├─ SkippedPath()                 record links, exclusions and nonregular objects
     │   │   └─ SkippedPath.__post_init__() validate relative path and reason
     │   │       └─ _require_path()        enforce portable path syntax in ingestion/models.py
     │   ├─ os.lstat()                    obtain directory identity after exclusions and link checks
     │   ├─ pending.append()              queue only ordinary directories for later inspection
     │   └─ DiscoveredFile()              retain byte size and extension-derived language
     │       └─ DiscoveredFile.__post_init__() validate path, size and language
     │           └─ _require_path()       preserve valid raw relative filenames
     ├─ _check_directory()                detect directory changes after enumeration
     ├─ sorted(files)                     make file order independent of enumeration
     ├─ sorted(skipped)                   make omission order independent of enumeration
     └─ RepositoryInventory()             retain ordered immutable metadata tuples
         └─ RepositoryInventory.__post_init__() validate disjoint ordered records
             └─ _require_ordered_records() enforce tuple types and sorted unique paths
RepositoryInventory.supported_files       src/arctrellis/ingestion/models.py; filter recognized sources
RepositoryInventory.file_count            src/arctrellis/ingestion/models.py; count all regular files
RepositoryInventory.supported_file_count  src/arctrellis/ingestion/models.py; count recognized sources
RepositoryInventory.language_counts       src/arctrellis/ingestion/models.py; immutable language summary
 ├─ collections.Counter()                 aggregate only nonempty supported language values
 ├─ sorted()                             order counts by canonical language value
 └─ tuple()                              freeze the language summary
```

Output: RepositoryInventory with files, supported_files, file_count,
supported_file_count, language_counts and skipped_paths. Language counts sort by
canonical language value; paths sort by original case-sensitive Python string order.
Unsupported ordinary files remain visible. Excluded directories are never entered;
hidden directories are retained unless named in the explicit exclusion policy.
.gitignore is not parsed. Files are never read, imported, executed or hashed.

Missing/file/linked roots raise InvalidRepositoryPathError. Unexpected filesystem
errors (including vanished entries) raise RepositoryAccessError with their original
cause; there is no partial inventory. Invalid argument types/configuration fail
with TypeError/ValueError. Linked paths inside the tree are intentional skips.
Directory identity checks detect ordinary changes but are not atomic containment:
concurrent hostile replacement remains a documented limitation on Windows.
Expected work is O(visited entries) plus sorting the file and skip records.

## 9. Single-file parsing and normalization

Input: source bytes with a compatible relative path/language, or one DiscoveredFile
and its local repository root. No entire-inventory automatic parse is performed.

```text
parse_discovered_file()                   src/arctrellis/parsing/parser.py; connect inventory to syntax
 ├─ _validate_limit()                     parsing/source.py; require a positive integer resource limit
 ├─ _grammar_for()                        parsing/registry.py; reject unsupported or contradictory metadata
 │   └─ DiscoveredFile()                  ingestion/models.py; reuse public portable-path validation
 ├─ _read_source()                        parsing/source.py; read current bounded bytes
 │   ├─ os.fspath()                       accept local runtime root context
 │   ├─ os.path.abspath()                 normalize lexical root without resolving links
 │   ├─ PureWindowsPath()                 reject nested drive-bearing source components
 │   ├─ Path.relative_to()                verify constructed target containment before filesystem access
 │   ├─ os.lstat()                        inspect all ancestors and current target
 │   ├─ _ordinary()                       reject observed links, reparse points and wrong kinds
 │   ├─ _check_size()                     reject current size above the inclusive maximum
 │   ├─ os.open()                         open read-only with available non-following/nonblocking flags
 │   ├─ os.fstat()                        inspect the actual descriptor identity and kind
 │   ├─ _identity()                       compare descriptor with checked target
 │   ├─ os.read()                         read chunks totaling at most limit+1 bytes
 │   ├─ _check_size()                     reject oversized bytes instead of parsing truncation
 │   ├─ os.fstat()                        detect observed size/mtime change during read
 │   ├─ os.close()                        release descriptor even on failure
 │   ├─ os.lstat()                        recheck target and ancestor identities
 │   └─ _ordinary()                       reject observed post-read indirection
 └─ parse_source()                        delegate to the bytes-only boundary below
parse_source()                           src/arctrellis/parsing/parser.py; parse one immutable byte value
 ├─ _validate_limit()                     validate direct-call resource configuration
 ├─ _grammar_for()                        select Python, JavaScript, TypeScript or TSX
 ├─ _check_size()                         enforce resource bound before native parsing
 ├─ _new_parser()                         parsing/registry.py; construct fresh private native parser
 │   ├─ import_module()                   load only the selected installed official grammar
 │   └─ tree_sitter.Parser()              initialize a compatible grammar wrapper
 ├─ Parser.parse()                       treat bytes as syntax data, never execute them
 ├─ _normalize_tree()                     parsing/normalization.py; iterative native child-object conversion
 │   ├─ _span()                          convert rows to 1-based lines, retain byte offsets/columns
 │   ├─ children()                       preserve native child order and actual grammar field names
 │   ├─ _capture()                       copy native metadata immediately into owned values
 │   ├─ SyntaxNode()                     retain named/recovery nodes, fields and source order
 │   ├─ SyntaxNode.walk()                inspect normalized nodes in iterative preorder
 │   └─ ParseDiagnostic()                retain real ERROR/MISSING categories without invented messages
 └─ ParsedSource()                       parsing/models.py; own bytes, syntax and diagnostics
```

Output: immutable ArcTrellis values with no native objects. Syntax spans have
inclusive start/exclusive end bytes and points, 1-based lines and 0-based byte
columns. Ordinary anonymous punctuation is omitted; error/missing constructs are
retained even when anonymous. Rare anonymous wrappers promote their retained
descendants in source order. Field names describe the original immediate native
parent. child_by_field returns the first direct match, or None; walk is preorder;
bytes_for slices a bounded supplied node without claiming membership in this tree.

Malformed syntax returns diagnostics, not a hard failure. UnsupportedLanguageError
means no compatible extension/language; ParserConfigurationError and
ParserExecutionError identify infrastructure failures. SourceReadError chains OS
errors, with UnsafeSourceError for observed indirect/nonregular targets.
SourceTooLargeError reports actual observed size and configured limit. The default
2 MiB maximum permits equality and never sends a truncated source to the parser.
The input tree must remain stable: checks are not atomic hostile-race containment.
No source is imported/executed and no target dependencies/hooks/tests run.
Extra memory retains both source bytes and normalized syntax. Parsing itself has no
cache/workers and creates no semantic entities, relationships or graph mutations.

```text
SyntaxNode.__eq__()                       parsing/models.py; compare corresponding trees without recursion
 └─ SyntaxNode._signature()               compare kind, span, flags, field and child count
SyntaxNode.__hash__()                     parsing/models.py; hash iterative preorder signatures
 ├─ SyntaxNode.walk()                     visit grammar order without recursion
 └─ SyntaxNode._signature()               include child counts to preserve tree structure
SyntaxNode.child_by_field()               parsing/models.py; return first direct field or None
ParsedSource.bytes_for()                  parsing/models.py; validate bounds and slice exact bytes
ParsedSource.size_bytes                   parsing/models.py; derive retained source length
ParsedSource.has_errors                   parsing/models.py; derive diagnostic presence
ParsedSource.diagnostic_count             parsing/models.py; derive diagnostic count
```

## 10. Python semantic entities

Input: one Python ParsedSource; extraction does not open files or call a parser.

```text
extract_python_entities()                 src/arctrellis/extraction/python.py; validate input language/root/path
 ├─ _PythonSource.from_parsed()           extraction/source.py; establish Python encoding without execution
 │   ├─ tokenize.detect_encoding()       inspect BOM/cookie in already-owned bytes
 │   └─ bytes.decode()                   reject unsafe/unknown decoding with a chained error
 ├─ _recovery_subtrees()                  iterative postorder; mark recovery once per syntax node
 ├─ _entity()                            create the unique MODULE lexical root
 │   ├─ make_entity_id()                  extraction/ids.py; UUID5 over versioned canonical JSON
 │   │   ├─ json.dumps()                 encode delimiter-safe identity components
 │   │   └─ uuid5()                      reproduce identity within a source revision
 │   ├─ _location()                      extraction/source.py; convert exclusive syntax end to inclusive lines
 │   ├─ _span_metadata()                 preserve all six exact coordinates as strings
 │   └─ CodeEntity()                     core/models.py; enforce canonical immutable records
 └─ iterative pending stack              preserve nearest semantic scope through control syntax
     ├─ decorated_definition             unwrap definition once, retaining decorator order/wrapper span
     ├─ _declaration()                   create CLASS or FUNCTION/METHOD according to immediate scope
     │   ├─ _PythonSource.signature()     select final depth-zero header colon, including lambda annotations
     │   ├─ _PythonSource.text()          decode exact name/decorator byte slices
     │   ├─ _lexical_name()               build path::scope.names without guessing package roots
     │   └─ _entity()                     create declaration, then queue its body under the new scope
     ├─ _import_bindings()               extraction/imports.py; retain ordinary/from/future binding clauses
     │   └─ _module_text()               preserve identifier components and leading relative dots
     ├─ _entity()                        caller creates each IMPORT using binding span and current parent
     └─ remaining syntax                 queue children under the unchanged semantic parent
sorted(..., key=_entity_order)            extraction/models.py; stable span/kind/ID order after MODULE
ExtractionResult()                       extraction/models.py; validate per-file ownership and unique IDs
 └─ ExtractionResult.__post_init__()      reject invalid module/path/language/parent/order/span states
     └─ _entity_span()                   validate exact canonical span metadata
```

Output: frozen ExtractionResult with MODULE first and source-ordered CodeEntity
records. Methods are functions whose nearest semantic parent is CLASS; nested
functions under methods remain FUNCTION. Imports retain bindings, not resolved
dependencies. Signature is an optional canonical field; decorators use numbered
metadata keys. Result.module and entities_of_kind return immutable values.

Any recovery within a declaration/import/wrapper suppresses that whole semantic
scope; unaffected siblings survive and partial is true. Structurally incomplete
candidates are skipped and also mark partial. Wrong language raises
UnsupportedExtractionLanguageError; decode errors chain SourceDecodingError;
invalid normalized boundaries raise SemanticExtractionError. Constructors retain
TypeError/ValueError for programmer-supplied invalid result data. No native parser
objects, filesystem reads, relationships, variables or reference entities emerge.
Traversal/recovery work is linear in syntax size; final entity sorting costs O(E log E).

## 11. JavaScript and TypeScript semantic entities

Input: one JS/JSX or TS/TSX ParsedSource. No file reads or target execution occur.

```text
extract_entities()                       src/arctrellis/extraction/__init__.py; select canonical language
 ├─ extract_python_entities()            extraction/python.py; retain the existing Python contract
 ├─ extract_javascript_entities()        extraction/javascript.py; enforce JavaScript input
 └─ extract_typescript_entities()        extraction/javascript.py; enforce TypeScript/TSX input
     └─ _extract()                       validate program root/path and strict UTF-8 bytes
         ├─ _recovery()                  precompute unsafe subtrees once, without recursion
         ├─ SyntaxNode.walk()            index direct class-body method membership; exclude object methods
         ├─ _make()                      create MODULE and revision-deterministic canonical entities
         │   ├─ make_entity_id()         extraction/ids.py; reuse the versioned identity contract
         │   ├─ _location()              extraction/source.py; inclusive source lines
         │   └─ _span_metadata()         retain all six exact coordinates
         └─ iterative stack              carry nearest represented semantic parent
             ├─ export_statement         forward declarations and inexpensive export flags
             ├─ _es_imports()            extraction/es_imports.py; one entity per static ES binding/site
             │   ├─ _literal()           retain exact module spelling without evaluation
             │   └─ _binding()           preserve immutable import metadata
             ├─ _require_import()        extraction/es_imports.py; simple static syntactic require site
             ├─ _declaration()           interpret fields, headers and modifiers; enter body scope
             ├─ _cover()                 include preceding TS class-body decorators in member spans
             └─ other syntax             retain scope; omit unrepresented anonymous/object/type scopes
ExtractionResult()                       extraction/models.py; validate module, spans, parents and ordering
```

Output: the existing immutable ExtractionResult and CodeEntity vocabulary. All
JS/TS callable declarations use FUNCTION except class member syntax/callable fields,
which use METHOD. A function nested inside a method remains FUNCTION. Binding names
are lexical abstractions, not claims about runtime identity. Interfaces/type aliases/
enums, anonymous unbound scopes and object methods are deliberately omitted.

UTF-8 decoding is strict and chained as SourceDecodingError. Wrong language raises
UnsupportedExtractionLanguageError and an invalid root/path raises SemanticExtractionError.
Recovery anywhere in a candidate suppresses its whole represented scope and marks
partial; unaffected siblings survive. Signatures end at the body's start; callable
bindings begin at the identifier, excluding the variable keyword. Module strings
retain source spelling and quoted literals; no escapes, imports or require calls
are evaluated/resolved. No relationships or automatic repository-wide pass exists.

## 12. Evidence-backed single-file lexical graph assembly

Input: one ExtractionResult, including optional partial status; no source reads occur.

```text
build_lexical_graph()                     src/arctrellis/extraction/lexical.py; create a fresh single-file graph
 ├─ ExtractionResult()                   extraction/models.py; reject corrupted ownership/spans before assembly
 ├─ CodeGraph()                          graph/graph.py; allocate independent graph storage
 ├─ CodeGraph.add_entity()               graph/graph.py; insert all endpoints before relationships
 └─ for each non-module child           source order; parent_id proves represented lexical ownership
     ├─ CodeGraph.get_entity()           graph/graph.py; require the child's actual canonical parent
     ├─ _lexical_relationship()          extraction/lexical.py; construct exactly one DEFINES record
     │   ├─ _entity_span()               extraction/models.py; retrieve exact child coordinates
     │   ├─ _span_metadata()             extraction/source.py; retain proof coordinates as strings
     │   ├─ _proof_id()                  compact JSON/UUID5; deterministic evidence and relationship identity
     │   ├─ Evidence()                   core/models.py; child declaration lines, method lexical_parentage
     │   └─ Relationship()               core/models.py; parent -> DEFINES -> child, PROVEN, score 1.0
     └─ CodeGraph.add_relationship()     graph/graph.py; preserve proof and enforce endpoint integrity
```

Output: a new CodeGraph containing every canonical entity and one lexical edge per
non-module entity. The MODULE has no fabricated repository parent. Imports are
declaration sites and receive DEFINES, never resolved IMPORTS. No CONTAINS duplication,
CALLS or INHERITS edges exist. Partial extraction produces proven edges only for its
surviving entities; callers keep result.partial separately. GraphPath/adjacency retain
the original immutable Relationship/Evidence records. No repository merge occurs.

Wrong input type raises TypeError; corrupted result invariants raise chained
SemanticExtractionError before graph construction. Existing graph errors propagate
if an insertion invariant fails. Identity is versioned, revision-deterministic and
not repository-namespaced. Assembly uses existing graph insertion/sorting costs;
it introduces no concurrency, persistence or alternate traversal behavior.

## 13. Repository semantic indexing

Input: an existing local root and positive source-byte limit.

```text
index_repository()                       src/arctrellis/indexing/repository.py; validate limit and orchestrate
 ├─ scan_repository()                    ingestion/discovery.py; trustworthy ordered inventory or abort
 └─ for each supported file             sequential inventory order; unsupported files remain inventory-only
     ├─ _analyze_file()                  own one source/tree only for this helper's lifetime
     │   ├─ parse_discovered_file()      parsing/parser.py; bounded safe current bytes and normalized syntax
     │   ├─ extract_entities()          extraction/__init__.py; canonical language dispatch
     │   ├─ extract_call_sites()        calls/extraction.py; retain body-owned observations before releasing syntax
     │   ├─ extract_framework_observations() frameworks/extraction.py; retain route/provenance syntax before release
     │   ├─ extract_pre_handler_observations() frameworks/flow_extraction.py; preserve precise pre-handler occurrences
     │   ├─ extract_router_observations()  frameworks/composition_extraction.py; preserve constructor/prefix/mount proof
     │   ├─ extract_test_observations() test_semantics/extraction.py; retain semantic tests before release
     │   ├─ extract_database_operations() database/extraction.py; retain provenance-backed DB observations
     │   ├─ build_lexical_graph()        extraction/lexical.py; retain existing parent proof
     │   ├─ _file_entity()               create path-based FILE with analyzed byte size
     │   │   └─ _file_id()               indexing/ids.py; content-independent structural identity
     │   ├─ _membership()               PROVEN FILE DEFINES MODULE with root evidence
     │   │   └─ _stable_id()             versioned canonical JSON/UUID5 proof identities
     │   └─ FileIndexResult()            indexing/models.py; summarize before source/tree release
     ├─ CodeGraph.add_entity()           graph/graph.py; merge canonical endpoints first
     ├─ CodeGraph.add_relationship()     graph/graph.py; retain immutable evidence
     └─ outcomes.append()               retain explicit COMPLETE/PARTIAL/FAILED summary
 └─ RepositoryIndexResult()              indexing/models.py; validate ordered outcomes and graph counts
```

Output: inventory, merged in-memory graph, frozen per-file summaries, source-ordered CallSite, HttpRouteObservation and PreHandlerObservation tuples. FILE identity
uses path/language, not declaration positions; no repository entity is invented.
Counts include FILE and membership edges. ParsedSource, bytes, trees, exceptions and
tracebacks are not retained. Typed source/parsing/extraction failures return bounded
stage/type summaries and continue; discovery failures abort without inventory, and
assembly/collision violations raise chained RepositoryIndexInvariantError. Partial
semantic survivors enter the graph and make is_complete false. Owned CodeGraph remains
mutable by its existing contract; consumers should treat completed results as snapshots.

## 14. Conservative internal import resolution

Input: RepositoryIndexResult; no source or configuration reads.

```text
resolve_imports(index)                          src/arctrellis/resolution/imports.py
 ├─ RepositoryIndexResult(...)                 reject stale summary invariants
 ├─ CodeGraph.add_entity()                     copy endpoints before edges
 ├─ CodeGraph.add_relationship()               copy proof without mutating base graph
 ├─ _catalog(modules)                          resolution/catalog.py: derive path-based module candidates
 └─ for each IMPORT in deterministic ID order
     ├─ _python_candidates(...)               calculate absolute/relative Python aliases
     ├─ _script_candidates(...)               match safe relative JS/TS paths against catalog
     ├─ ImportResolution(...)                 record unique, ambiguous or unresolved result
     └─ _import_edge(site, target)             only unique candidates become LIKELY/0.90 edges
         └─ CodeGraph.add_relationship()       retain import-site evidence
```

Python supports identifier-component path aliases and an explicit leading-src heuristic; no environment/configuration or imported-symbol resolution. JS/TS probes exact supported extensions, or all supported extension/index paths for extensionless names; explicit directory-intent specifiers probe only indexes; no priority guesses. Unknown extensions, bare imports, escaped/percent literals and outside-root paths are unresolved. Ambiguous imports record sorted candidate IDs without an edge. Output is ImportResolutionResult with a new graph and decisions. Invalid graph/summary invariants abort explicitly; original index remains unchanged. Evidence points to the IMPORT location with language-specific analysis method, not a guessed target declaration.

## 15. Local development quality gate

Developer input is ArcTrellis source/tests and pyproject.toml, never a target repository.

```text
developer gate (manual local sequence)        commands below run independently
 ├─ python -m pip install -e ".[dev]"          pyproject.toml: opt in to pinned development tools
 ├─ python -m unittest discover -s tests -v    verify runtime contracts and import-boundary audit
 ├─ python -m ruff check src tests             lint without target execution
 ├─ python -m ruff format --check src tests    require deterministic Python formatting
 ├─ python -m mypy src/arctrellis              check strict types without blanket suppression
 ├─ python -m compileall -q src                compile ArcTrellis source without executing it
 └─ python -m pip check                        verify installed dependency consistency
```

`ruff format src tests` applies formatting before checks. Tools are optional dev dependencies; runtime parser pins remain unchanged. The standard-library tests/test_architecture.py import audit inspects ArcTrellis source only and rejects native imports outside parsing. Any failed command requires correction and rerun; no CI, publication or target package hooks are introduced.

## 16. Static call observations

Input: ParsedSource and its already-produced ExtractionResult; no file access or semantic re-extraction.

```text
extract_call_sites()                       src/arctrellis/calls/extraction.py
 ├─ ExtractionResult()                    validate canonical per-file ownership
 ├─ _PythonSource.from_parsed() / decode() establish strict existing decoding policy
 ├─ _recovery_subtrees()                  mark unsafe syntax once without recursion
 └─ iterative pending stack              preserve semantic ownership through executable control flow
     ├─ declaration match                parent/name/end identify canonical scopes, never span-only ownership
     │   └─ body field                   enter function/method bodies; omit headers and class execution
     ├─ _parts()                         retain only static identifier/member spellings
     ├─ _optional_call()                 distinguish real punctuation from comments and TS type arguments
     ├─ make_call_site_id()               calls/ids.py: reproducible invocation identity
     └─ CallSite()                       calls/models.py: immutable owned coordinates without a target
sorted(..., key=_site_order)               retain deterministic source order
```

Output: immutable CallSite tuple. Incompatible source/semantic scopes raise CallExtractionError;
wrong API types raise TypeError. Recovery produces only surviving safe observations. No source
execution, graph edges or target selection occurs. Anonymous scopes and dynamic invocation
callees are omitted; ordinary argument expressions may still be visited.

## 17. Conservative call resolution

Input: RepositoryIndexResult plus its ImportResolutionResult; no source/config reads or import rerun.

```text
resolve_calls()                            src/arctrellis/calls/resolution.py
 ├─ RepositoryIndexResult()                validate call owners/counts and base snapshot
 ├─ ImportResolutionResult()               validate import decisions and matching entities/base edges
 ├─ _import_edge()                         require exact preserved import proof, without path re-resolution
 ├─ _Symbols()                            index functions/methods/bindings once, by parent and name
 ├─ CodeGraph.add_entity()/add_relationship() copy immutable records into independent graph storage
 └─ for each source-ordered CallSite
     ├─ _resolve()                        select a conservative resolution family
     │   ├─ _ancestors()                  search nearest scope; class/static-block namespaces are not method closures
     │   ├─ _choose()                     one candidate resolves; duplicates remain ambiguous
     │   └─ _imported()                   use existing resolved module plus direct function lookup
     ├─ CallResolution()                  retain resolved/unresolved/ambiguous outcome
     └─ _edge()                           only unique targets receive a CALLS relationship
         ├─ _identity()                   calls/ids.py: versioned site-specific proof identity
         ├─ Evidence()                    invocation lines and all six exact coordinates
         └─ CodeGraph.add_relationship()  preserve LIKELY/0.85 or import-assisted LIKELY/0.75 evidence
```

Output: CallResolutionResult with a new graph and one decision per observation. No edge
is emitted for unresolved/ambiguous calls. Invalid or mismatched snapshots raise
CallResolutionInvariantError. Duplicate import bindings are ambiguity witnesses, not
selected callable targets. Local runtime imports avoid initialization cycles; they
load only ArcTrellis result types, never target modules. Assignment/parameter shadowing
and runtime dispatch are not modeled, so no CALLS edge is PROVEN.

## 18. Static framework route observations and endpoint resolution

Input: ParsedSource with its existing ExtractionResult during indexing; retained observations plus matching import/call snapshots during resolution.

```text
extract_framework_observations()           src/arctrellis/frameworks/extraction.py
 ├─ _bindings()                           require unique canonical framework imports and preceding constructors
 │   └─ _writes()                         reject module rebinding/context captures and shadowed require
 ├─ _python_routes() / _express_routes()   inspect direct decorators/registrations without execution
 └─ _observe()                            retain static path/methods, handler syntax and exact spans
resolve_http_endpoints()                   src/arctrellis/frameworks/resolution.py
 ├─ _validate_snapshots()                 reject stale inputs before adding graph facts
 ├─ framework import decision/inventory   reject known internal framework-name collisions, even failed files
 ├─ _handler_index()                      index direct functions/import bindings/declaration spans once
 ├─ _handler()                            match canonical decorated declarations or indexed Express references
 ├─ _endpoint()                           one API_ENDPOINT per static HTTP method
 └─ _relationship()                       preserve registration-site Evidence for DEFINES and EXPOSES
     └─ CodeGraph.add_relationship()       retain immutable proof in the independent graph
```

Observations separate syntax from target selection. Constructor/import provenance rejects unrelated .get/.route receivers and visible contradictory writes. Decorator arguments use framework-specific path/rule keywords; splats and invalid duplicates remain unsupported. Express one-argument get is a settings accessor. Direct module handler visibility is retained separately from handler syntax; explicit rebinding or block-only targets stay unresolved. Unsupported paths/methods create a decision but no endpoint. A valid static registration with an unknown/ambiguous handler retains its endpoint and DEFINES proof, with no EXPOSES edge. Wildcard/conditional imports and class import shadows cannot establish receiver provenance. Exact decorated declaration spans prevent same-name nested handler collisions. Python decorator association is PROVEN/1.0; Express local/import-assisted references remain LIKELY/0.85 or 0.75. This endpoint-resolution stage adds no middleware, route composition or framework CALLS; the separate framework-flow stage enriches pre-handlers and static paths. Typed extraction errors become explicit FAILED file outcomes; inconsistent snapshots raise FrameworkResolutionInvariantError. Resolution reads retained semantic records only; inputs remain unchanged.

## Changes in this session (Phase 0.1)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Foundation | Initialize Git, src packaging, local authorship and ignore rules. | .gitignore, pyproject.toml, src/arctrellis/__init__.py | e7a2f98d078583b392170d323682870745311e45 | D-001 |
| Domain | Add canonical enums, frozen records and public exports. | src/arctrellis/core/models.py, src/arctrellis/core/__init__.py | e7a2f98d078583b392170d323682870745311e45 | D-002 |
| Validation | Enforce path, line, metadata, type and score invariants. | src/arctrellis/core/models.py | e7a2f98d078583b392170d323682870745311e45 | D-003 |
| Tests | Add standard-library public API and domain invariant coverage. | tests/__init__.py, tests/core/__init__.py, tests/core/test_models.py | e7a2f98d078583b392170d323682870745311e45 | D-001, D-002, D-003 |
| Documentation | Document current capabilities, flows, decisions and handoff. | README.md, decisions.md, flow.md, handoff.md | e7a2f98d078583b392170d323682870745311e45 | D-001, D-002, D-003, D-004 |
| Commit traceability | Finalize implementation commit references in a separate documentation commit. | decisions.md, flow.md, handoff.md | e7a2f98d078583b392170d323682870745311e45 | D-004 |
| Commit configuration | Record the initial commit's per-command signing override; no runtime or persistent configuration changed. | decisions.md, flow.md, handoff.md | e7a2f98d078583b392170d323682870745311e45 | D-005 |

## Changes in this session (Phase 0.2)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Tests | Define graph storage, adjacency, traversal, path and immutable result contracts using existing domain records. | tests/graph/__init__.py, tests/graph/fixtures.py, tests/graph/test_graph.py, tests/graph/test_traversal.py, tests/graph/test_results.py | 7c9b42800c1e5b7c8d22791109480cc2cb42b94f | D-006, D-007, D-008 |
| Graph storage | Add endpoint-safe canonical storage, idempotence, explicit lookup errors, counts and immutable snapshots. | src/arctrellis/graph/graph.py, src/arctrellis/graph/errors.py | 7c9b42800c1e5b7c8d22791109480cc2cb42b94f | D-006, D-008 |
| Queries | Add sorted adjacency, unique neighbors, filters and shared cycle-safe BFS for traversal and shortest paths. | src/arctrellis/graph/graph.py | 7c9b42800c1e5b7c8d22791109480cc2cb42b94f | D-007, D-008 |
| Results and public API | Add validated immutable node results and evidence-preserving directed paths, with intentional package exports. | src/arctrellis/graph/results.py, src/arctrellis/graph/__init__.py | 7c9b42800c1e5b7c8d22791109480cc2cb42b94f | D-008 |
| Documentation | Describe actual graph semantics and call order while preserving the Phase 0.1 history. | README.md, decisions.md, flow.md, handoff.md | 7c9b42800c1e5b7c8d22791109480cc2cb42b94f | D-006, D-007, D-008 |
| Fixture and session traceability | Use named synthetic payment entities, record actual verification, and finalize new commit references without rewriting old history. | tests/graph/fixtures.py, decisions.md, flow.md, handoff.md | 7c9b42800c1e5b7c8d22791109480cc2cb42b94f | D-009 |
| Documentation review | Correct the constructor/graph validation distinction, explicit placeholder policy and continuous session table; rewrite handoff in place. | README.md, decisions.md, flow.md, handoff.md | 7c9b42800c1e5b7c8d22791109480cc2cb42b94f | D-010 |

## Changes in this session (Phase 1.0)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Test contracts | Add synthetic discovery and immutable inventory tests before implementation. | tests/ingestion/__init__.py, tests/ingestion/test_models.py, tests/ingestion/test_discovery.py | d02524700240e8a37b15f01e7138b7dbb3a70e8a | D-011, D-012, D-013, D-014 |
| Editing recovery | Retry an atomic patch after checking the real Markdown context; rejected attempt changed nothing. | decisions.md, flow.md | d02524700240e8a37b15f01e7138b7dbb3a70e8a | D-015 |
| Inventory | Add validated immutable portable file/skip records, supported subsets and deterministic counts. | src/arctrellis/ingestion/models.py | d02524700240e8a37b15f01e7138b7dbb3a70e8a | D-011 |
| Discovery and errors | Add metadata-only traversal, pruning, language detection, link guards, root checks and explicit incomplete-scan errors. | src/arctrellis/ingestion/discovery.py, src/arctrellis/ingestion/errors.py | d02524700240e8a37b15f01e7138b7dbb3a70e8a | D-012, D-013 |
| Public API | Export intentional ingestion models, scanner, defaults and errors. | src/arctrellis/ingestion/__init__.py | d02524700240e8a37b15f01e7138b7dbb3a70e8a | D-011, D-012, D-013 |
| Windows identity | Use os.lstat for both queued and refreshed directory identities instead of comparing zero DirEntry fields. | src/arctrellis/ingestion/discovery.py, tests/ingestion/test_discovery.py | d02524700240e8a37b15f01e7138b7dbb3a70e8a | D-016 |
| Safety verification | Add real link/junction fixtures, explicit platform skips and simulated link/nonregular classification, metadata, enumeration and replacement failures. | tests/ingestion/test_safety.py | d02524700240e8a37b15f01e7138b7dbb3a70e8a | D-012, D-013, D-014 |
| Documentation | Describe current discovery semantics, security boundary, call order and session continuity. | README.md, decisions.md, flow.md, handoff.md | d02524700240e8a37b15f01e7138b7dbb3a70e8a | D-011, D-012, D-013, D-014 |
| Commit traceability | Finalize the implementation references and verified handoff in a separate documentation commit. | decisions.md, flow.md, handoff.md | d02524700240e8a37b15f01e7138b7dbb3a70e8a | D-004, D-014 |

## Changes in this session (Phase 1.1)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Parser dependencies | Pin Tree-sitter and three explicit grammar packages; editable installation loads only declared parser dependencies. | pyproject.toml, decisions.md, flow.md | 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168 | D-017, D-018, D-019, D-020 |
| Test contracts | Add normalized model, grammar and scan-to-parse safety contracts before implementation. | tests/parsing/__init__.py, tests/parsing/test_models.py, tests/parsing/test_registry.py, tests/parsing/test_parser.py | 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168 | D-021, D-022, D-023 |
| Normalized syntax | Add immutable syntax/spans/diagnostics and iterative native-to-owned conversion. | src/arctrellis/parsing/models.py, src/arctrellis/parsing/normalization.py | 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168 | D-021 |
| Parsing API | Add fresh explicit grammar selection, bytes/file entry points and typed failures. | src/arctrellis/parsing/registry.py, src/arctrellis/parsing/parser.py, src/arctrellis/parsing/errors.py, src/arctrellis/parsing/__init__.py | 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168 | D-022 |
| Source safety | Add bounded current-file reads and path/descriptor checks; preserve the stable-tree assumption. | src/arctrellis/parsing/source.py | 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168 | D-023 |
| Annotation correction | Postpone recursive and type-only annotations to make imports work on Python 3.13. | src/arctrellis/parsing/models.py, src/arctrellis/parsing/registry.py | 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168 | D-024 |
| Recovery and safety tests | Verify anonymous missing tokens, deep normalization, exact-limit reads, dependency isolation, typed failures and real junction replacement. | tests/parsing/test_parser.py | 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168 | D-021, D-022, D-023 |
| Native traversal correction | Replace cursor access with native child objects after reproducing invalid coordinates and a Windows access violation. | src/arctrellis/parsing/normalization.py, tests/parsing/test_parser.py | 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168 | D-025, D-026 |
| Runtime compatibility | Compare runtime 0.25.2 after reproducing point-access crashes independently of traversal strategy under 0.26.0. | pyproject.toml, decisions.md, flow.md | 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168 | D-027 |
| Review regressions | Add deep equality, Windows nested-drive containment and missing-runtime contract regressions. | tests/parsing/test_parser.py | 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168 | D-028, D-029, D-030 |
| Review corrections | Add iterative value comparison/hash, final target containment and lazy annotation-only native imports after reproducing all three failures. | src/arctrellis/parsing/models.py, src/arctrellis/parsing/source.py, src/arctrellis/parsing/normalization.py | 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168 | D-028, D-029, D-030 |
| Read-change tests | Verify growth past the limit, descriptor identity change, cleanup and mtime change fail without parsing. | tests/parsing/test_parser.py | 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168 | D-023 |
| Documentation | Describe actual syntax capabilities, installed pins, resource limits, isolation and discovery-versus-parsing security. | README.md, decisions.md, flow.md, handoff.md | 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168 | D-021, D-022, D-023, D-027 |
| Verification and handoff | Record final compatibility evidence, correct containment call placement, and retain failed-approach history in the session handoff. | decisions.md, flow.md, handoff.md | 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168 | D-031 |
| Commit traceability | Finalize implementation references in a separate documentation commit without rewriting history. | decisions.md, flow.md, handoff.md | 594ae41b7d78e9a5f7d43492eb7d9ddbfb134168 | D-004, D-031 |

## Changes in this session (Phase 1.2)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Contracts | Add test-first canonical signature, identity, result, Python and import contracts. | tests/core/test_models.py, tests/extraction/__init__.py, tests/extraction/test_ids.py, tests/extraction/test_models.py, tests/extraction/test_python.py, tests/extraction/test_imports.py | 4981f258ea312e254e9c4de4b34f3f3068e71a03 | D-032, D-033, D-034, D-035, D-036 |
| Inspection | Use a literal stdin script after an inline quoting failure; verify normalized Python grammar shapes. | decisions.md, flow.md | 4981f258ea312e254e9c4de4b34f3f3068e71a03 | D-036 |
| Canonical signature | Add a final optional signature field without moving existing positional arguments. | src/arctrellis/core/models.py, tests/core/test_models.py | 4981f258ea312e254e9c4de4b34f3f3068e71a03 | D-032 |
| Identity and results | Add versioned UUID5 identity, validated immutable per-file ownership and public extraction errors/API. | src/arctrellis/extraction/__init__.py, src/arctrellis/extraction/ids.py, src/arctrellis/extraction/models.py, src/arctrellis/extraction/errors.py | 4981f258ea312e254e9c4de4b34f3f3068e71a03 | D-033 |
| Python semantics | Add iterative scoped declarations, decorators and unresolved per-binding imports. | src/arctrellis/extraction/python.py, src/arctrellis/extraction/imports.py | 4981f258ea312e254e9c4de4b34f3f3068e71a03 | D-034 |
| Encoding and recovery | Decode owned Python bytes, slice declaration headers, retain exact spans and suppress ambiguous semantic scopes. | src/arctrellis/extraction/source.py, src/arctrellis/extraction/python.py | 4981f258ea312e254e9c4de4b34f3f3068e71a03 | D-035 |
| Annotation correction | Postpone a self-referential classmethod annotation after a verified import failure. | src/arctrellis/extraction/source.py | 4981f258ea312e254e9c4de4b34f3f3068e71a03 | D-037 |
| Recovery verification | Test diagnostic-free empty suites, missing identities, canonical output and the non-UTF-8 identifier limitation. | tests/extraction/test_python.py, README.md | 4981f258ea312e254e9c4de4b34f3f3068e71a03 | D-038 |
| Patch recovery | Retry an atomic edit after checking actual README context; the rejected attempt changed nothing. | decisions.md, flow.md, README.md | 4981f258ea312e254e9c4de4b34f3f3068e71a03 | D-039 |
| Review regressions | Reproduce future-import omission and lambda signature truncation with literal syntax samples. | tests/extraction/test_imports.py, tests/extraction/test_python.py | 4981f258ea312e254e9c4de4b34f3f3068e71a03 | D-040, D-041 |
| Review fixes | Retain complete lambda headers and grammar-defined future-import module/bindings without native imports. | src/arctrellis/extraction/source.py, src/arctrellis/extraction/imports.py, src/arctrellis/extraction/python.py | 4981f258ea312e254e9c4de4b34f3f3068e71a03 | D-040, D-041 |
| Coordinate correction | Align signature character offsets with tokenizer newline-only rows. | src/arctrellis/extraction/source.py, tests/extraction/test_python.py | 4981f258ea312e254e9c4de4b34f3f3068e71a03 | D-042 |
| Documentation and verification | Document implemented semantics, identity/security limits, reviewed corrections and real regression results in the twelve-section handoff. | README.md, decisions.md, flow.md, handoff.md | 4981f258ea312e254e9c4de4b34f3f3068e71a03 | D-032, D-033, D-034, D-035, D-038, D-040, D-041, D-042, D-043 |
| Commit traceability | Finalize feature commit references separately without embedding a self-referential hash or rewriting history. | decisions.md, flow.md, handoff.md | 4981f258ea312e254e9c4de4b34f3f3068e71a03 | D-004, D-043 |

## Changes in this session (Phase 1.3)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Contracts | Add normalized JS/TS declaration, binding, import, recovery and pipeline tests before implementation. | tests/extraction/test_javascript.py | 66d881e02bcb52e467720b39293319ff7595f085 | D-044 |
| JS/TS semantics | Add common normalized declaration traversal, strict decoding, signatures, decorators and exports without changing Python. | src/arctrellis/extraction/javascript.py, src/arctrellis/extraction/__init__.py | 66d881e02bcb52e467720b39293319ff7595f085 | D-044, D-045 |
| Import sites | Record ES bindings/type-only/side-effect imports and conservative static require sites, retaining literal spelling. | src/arctrellis/extraction/es_imports.py | 66d881e02bcb52e467720b39293319ff7595f085 | D-045 |
| Flow and capability documentation | Describe actual JS/TS transformation, omissions and unresolved import spelling. | README.md, decisions.md, flow.md | 66d881e02bcb52e467720b39293319ff7595f085 | D-044, D-045 |
| Modifier correction | Scan actual field containers and exclude decorator arguments after failing regressions. | src/arctrellis/extraction/javascript.py, tests/extraction/test_javascript.py | 66d881e02bcb52e467720b39293319ff7595f085 | D-046 |
| Empty import correction | Preserve an unbound module site for an empty named clause instead of reporting false partial state. | src/arctrellis/extraction/es_imports.py, tests/extraction/test_javascript.py, README.md | 66d881e02bcb52e467720b39293319ff7595f085 | D-047 |
| Decision-history correction | Restore historical entry boundaries from HEAD after an uncommitted insertion error. | decisions.md, flow.md | 66d881e02bcb52e467720b39293319ff7595f085 | D-048 |
| Scope correction | Require direct class-body membership before class method extraction, excluding embedded object methods. | src/arctrellis/extraction/javascript.py, tests/extraction/test_javascript.py | 66d881e02bcb52e467720b39293319ff7595f085 | D-049 |
| Phase gate and handoff | Record passing regressions, reviewed corrections and local-only continuation; finalize references separately. | README.md, decisions.md, flow.md, handoff.md | 66d881e02bcb52e467720b39293319ff7595f085 | D-050, D-004 |

## Changes in this session (Phase 1.4)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Lexical graph contracts | Add entity/edge cardinality, proof, identity, traversal, partial and multilingual pipeline tests before implementation. | tests/extraction/test_lexical.py | ec887ee7426340589582ae618aa4e7751a89c0f5 | D-051 |
| Graph assembly | Insert all entities, then proven lexical DEFINES edges with exact child evidence and deterministic identities. | src/arctrellis/extraction/lexical.py, src/arctrellis/extraction/__init__.py | ec887ee7426340589582ae618aa4e7751a89c0f5 | D-051, D-052 |
| Boundary documentation | Describe graph proof ownership, partial-result status, native isolation and the shared decoding exception policy. | README.md, decisions.md, flow.md, src/arctrellis/extraction/errors.py | ec887ee7426340589582ae618aa4e7751a89c0f5 | D-051, D-052 |
| Verification invocation | Use graph test package context after the standalone relative-import invocation failed. | decisions.md, flow.md, handoff.md | ec887ee7426340589582ae618aa4e7751a89c0f5 | D-053 |
| Security proof and handoff | Strengthen top-level non-execution fixture and record final regression, graph evidence and bounded continuation. | tests/extraction/test_javascript.py, README.md, decisions.md, flow.md, handoff.md | ec887ee7426340589582ae618aa4e7751a89c0f5 | D-054 |
| Commit traceability | Finalize local feature references separately without rewriting history or embedding a self-referential hash. | decisions.md, flow.md, handoff.md | ec887ee7426340589582ae618aa4e7751a89c0f5 | D-004, D-054 |

## Changes in this session (Phase 1.5)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Repository contracts | Add mixed-language, outcome, memory, collision and structural proof tests before implementation. | tests/indexing/__init__.py, tests/indexing/test_repository.py | acfd6093f95e0f9dd6b150ad625cb5ab6fee4a79 | D-055, D-056 |
| Repository pipeline | Add ordered per-file analysis, structural membership, fatal collision handling and explicit summaries without syntax retention. | src/arctrellis/indexing/__init__.py, src/arctrellis/indexing/models.py, src/arctrellis/indexing/repository.py, src/arctrellis/indexing/errors.py, src/arctrellis/indexing/ids.py | acfd6093f95e0f9dd6b150ad625cb5ab6fee4a79 | D-055, D-056 |
| Documentation | Describe repository outcomes, ownership lifecycle and structural identity. | README.md, decisions.md, flow.md | acfd6093f95e0f9dd6b150ad625cb5ab6fee4a79 | D-055, D-056 |

## Changes in this session (Phase 1.6)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Resolution | Add immutable decisions, path catalog and pure static resolver with contract tests. | src/arctrellis/resolution/, tests/resolution/, README.md, decisions.md, flow.md | 300652d914eb811f8a0c13f6bb2333afd914c1ee | D-057 |
| Evidence | Add site-specific LIKELY IMPORTS edges preserving lexical graph proof. | src/arctrellis/resolution/imports.py, tests/resolution/test_imports.py | 300652d914eb811f8a0c13f6bb2333afd914c1ee | D-058 |
| Candidate boundaries | Correct root index probes and reject literal-dot Python filename aliases. | src/arctrellis/resolution/catalog.py, src/arctrellis/resolution/imports.py, tests/resolution/test_imports.py, decisions.md, flow.md | 300652d914eb811f8a0c13f6bb2333afd914c1ee | D-059 |
| Directory candidates | Preserve trailing slash/dot directory intent and restrict probes to indexes. | src/arctrellis/resolution/catalog.py, tests/resolution/test_imports.py, decisions.md, flow.md | 300652d914eb811f8a0c13f6bb2333afd914c1ee | D-060 |
| Conservative literals | Defer percent-encoded specifiers and cover alias/relative-level negatives. | src/arctrellis/resolution/catalog.py, tests/resolution/test_imports.py, README.md, decisions.md, flow.md | 300652d914eb811f8a0c13f6bb2333afd914c1ee | D-061 |

## Changes in this session (Quality Gate Q1)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Development | Add optional pinned quality tools, Ruff configuration and strict mypy. | pyproject.toml, README.md, decisions.md, flow.md | ec14dca7cf518a167dc42bd853c45d876c64cf26 | D-062 |
| Python quality | Format and lint source/tests; make static type contracts explicit. | src/arctrellis/**/*.py, tests/**/*.py | ec14dca7cf518a167dc42bd853c45d876c64cf26 | D-062 |
| Static contracts | Annotate iterative work items and helper boundaries; preserve fixture bytes and validated invariants. | src/arctrellis/, tests/, decisions.md, flow.md | ec14dca7cf518a167dc42bd853c45d876c64cf26 | D-063 |
| Architecture | Add native import audit and verified local developer quality flow. | tests/test_architecture.py, README.md, decisions.md, flow.md, handoff.md | ec14dca7cf518a167dc42bd853c45d876c64cf26 | D-064 |
| Handoff | Record verified gates, limits and twelve-section continuation state; stop after Q1. | README.md, decisions.md, flow.md, handoff.md | ec14dca7cf518a167dc42bd853c45d876c64cf26 | D-065 |
| Verification commands | Correct auxiliary smoke byte input and retain existing Git line normalization for whitespace audit. | decisions.md, flow.md, handoff.md | ec14dca7cf518a167dc42bd853c45d876c64cf26 | D-066 |
| Historical prose | Restore old decision/flow prose and restrict finalization to current commit fields. | decisions.md, flow.md, handoff.md | 0235fbf33103b90004ec470e53623209b2bc68c6 | D-067 |

## Changes in this session (Phase 1.7)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Call observations | Add immutable invocation values, identity, typed errors and public contract tests. | src/arctrellis/calls/, tests/calls/test_models.py, tests/calls/__init__.py | e074bbb87e6c242536017d1b4186645b69aa12cb | D-068 |
| Body extraction | Interpret normalized invocation syntax using canonical body ownership and conservative omissions. | src/arctrellis/calls/extraction.py, tests/calls/test_extraction.py | e074bbb87e6c242536017d1b4186645b69aa12cb | D-069 |
| Index observations | Extend semantic indexing and import snapshot validation with lightweight call tuples/counts. | src/arctrellis/indexing/models.py, src/arctrellis/indexing/repository.py, src/arctrellis/resolution/imports.py, tests/calls/test_indexing.py | e074bbb87e6c242536017d1b4186645b69aa12cb | D-070 |
| Call resolution | Add indexed lexical/method/import matching and site-specific LIKELY CALLS evidence. | src/arctrellis/calls/models.py, src/arctrellis/calls/resolution.py, src/arctrellis/calls/__init__.py, tests/calls/test_resolution.py | e074bbb87e6c242536017d1b4186645b69aa12cb | D-071 |
| Import order | Defer runtime snapshot imports and verify public APIs in fresh interpreters. | src/arctrellis/calls/resolution.py, tests/calls/test_indexing.py | e074bbb87e6c242536017d1b4186645b69aa12cb | D-072 |
| Callee spelling | Omit escaped callee identifiers safely without decoding them. | src/arctrellis/calls/extraction.py, tests/calls/test_indexing.py | e074bbb87e6c242536017d1b4186645b69aa12cb | D-073 |
| Execution boundaries | Skip Python class closure lookup and preserve executable binding defaults/constructor arguments. | src/arctrellis/calls/extraction.py, src/arctrellis/calls/resolution.py, tests/calls/test_extraction.py, tests/calls/test_resolution.py | e074bbb87e6c242536017d1b4186645b69aa12cb | D-074 |
| Snapshot validation | Reject out-of-owner observations and import records that disagree with preserved proof. | src/arctrellis/indexing/models.py, src/arctrellis/calls/resolution.py, tests/calls/test_indexing.py, tests/calls/test_resolution.py | e074bbb87e6c242536017d1b4186645b69aa12cb | D-075 |
| Contract hardening | Validate ID components and cover depth, non-execution and mixed deterministic call analysis. | src/arctrellis/calls/ids.py, tests/calls/fixtures.py, tests/calls/, README.md | e074bbb87e6c242536017d1b4186645b69aa12cb | D-076 |
| Static block scope | Exclude class-owned static-block bindings from ordinary method lookup. | src/arctrellis/calls/resolution.py, tests/calls/test_resolution.py, README.md | e074bbb87e6c242536017d1b4186645b69aa12cb | D-077 |
| Optional punctuation | Exclude normalized comment/type spans from optional invocation detection. | src/arctrellis/calls/extraction.py, tests/calls/test_extraction.py | e074bbb87e6c242536017d1b4186645b69aa12cb | D-078 |
| Verification and handoff | Record final gates, smoke evidence, intentional limits and twelve-section continuation state. | README.md, decisions.md, flow.md, handoff.md | e074bbb87e6c242536017d1b4186645b69aa12cb | D-079 |

## Changes in this session (Phase 1.8)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Route contracts | Add immutable observations, provenance, IDs, errors and test-first public contracts. | src/arctrellis/frameworks/, tests/frameworks/ | 023b7922f15f4a31beec3c62d498044f13c980bf | D-080 |
| Framework syntax | Require constructor/import provenance and preserve conservative static registration syntax. | src/arctrellis/frameworks/extraction.py, tests/frameworks/test_endpoints.py | 023b7922f15f4a31beec3c62d498044f13c980bf | D-081 |
| Index integration | Retain lightweight route observations/counts during the existing parse lifetime. | src/arctrellis/indexing/, src/arctrellis/resolution/imports.py, src/arctrellis/calls/resolution.py | 023b7922f15f4a31beec3c62d498044f13c980bf | D-082 |
| Endpoint graphs | Resolve handlers and add deterministic registration-backed DEFINES/EXPOSES in an independent graph. | src/arctrellis/frameworks/resolution.py, tests/frameworks/test_endpoints.py | 023b7922f15f4a31beec3c62d498044f13c980bf | D-083 |
| Provenance corrections | Reject shadowed constructors, invalid argument shapes, out-of-scope handlers and stale decorator coordinates. | src/arctrellis/frameworks/, src/arctrellis/indexing/models.py, tests/frameworks/ | 023b7922f15f4a31beec3c62d498044f13c980bf | D-084 |
| Engineering contracts | Add mixed fixtures, memory/failure/import-order/proof tests and retain strict annotations/formatting. | tests/frameworks/fixtures.py, tests/frameworks/test_contracts.py, src/arctrellis/frameworks/ | 023b7922f15f4a31beec3c62d498044f13c980bf | D-085 |
| Framework identity | Defer known internal modules that shadow framework package names. | src/arctrellis/frameworks/resolution.py, tests/frameworks/test_endpoints.py | 023b7922f15f4a31beec3c62d498044f13c980bf | D-086 |
| Scope/provenance review | Restrict direct imports, reject wildcard/class/require shadows, and match complete decorated wrapper spans. | src/arctrellis/frameworks/extraction.py, tests/frameworks/test_endpoints.py | 023b7922f15f4a31beec3c62d498044f13c980bf | D-087 |
| Public documentation and smoke | Explain supported HTTP patterns/limits and provide a repeatable evidence-backed mixed trace command. | README.md, tests/frameworks/smoke.py, decisions.md, flow.md | 023b7922f15f4a31beec3c62d498044f13c980bf | D-088 |
| Final verification and handoff | Record real gates, negative subcases, skips, local audits and twelve-section continuation state. | tests/frameworks/test_endpoints.py, README.md, decisions.md, flow.md, handoff.md | 023b7922f15f4a31beec3c62d498044f13c980bf | D-089 |

## 19. Static framework pre-handler flow

Input: owned ParsedSource and existing entities/routes during indexing, then matching repository/import/call/endpoint snapshots.

```text
extract_pre_handler_observations()         frameworks/flow_extraction.py; retain occurrence syntax before parse release
 ├─ _bindings() / _writes()               frameworks/extraction.py; require constructor provenance and visible binding safety
 ├─ Express arguments before final handler preserve route-local order; omit final handler
 ├─ FastAPI decorator dependency list     require direct FastAPI Depends import; never evaluate dependency calls
 └─ Flask before_request decorator        retain exact same-app binding and decorated function
resolve_framework_flow()                  frameworks/flow.py; copy prior graph, never reread sources
 ├─ validate existing endpoint snapshot   reject stale facts rather than silently replacing them
 ├─ _handler_index() / _reference_handler() frameworks/resolution.py; reuse function/import selection
 ├─ resolve each pre-handler              duplicates ambiguous; unsupported/unknown produces no edge
 ├─ _pre_edge()                           endpoint APPLIES_MIDDLEWARE callable with occurrence Evidence
 └─ compose_router_paths()                frameworks/composition.py; enrich static paths after pre-handler resolution
```

Evidence metadata retains semantic_kind and order_index. Express/FastAPI edges are LIKELY/0.85 locally or0.75 import-assisted. Flask exact same-app hooks are PROVEN/1.0; source order is per-file/app registration order, not a claim of cross-file runtime ordering. No middleware-to-handler CALLS are fabricated. Typed extraction failure remains a bounded FAILED file outcome.

## Changes in this session (Phase 1.9A)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Pre-handler contracts and pipeline | Add precise observations, lifetime/count extension and evidence-backed independent flow graphs. | src/arctrellis/frameworks/, src/arctrellis/indexing/, src/arctrellis/calls/resolution.py, src/arctrellis/resolution/imports.py, tests/frameworks/test_flow.py, README.md | 94cdfd6dc4e789f2bc315f2fb82a05ac98f37ec9 | D-090 |
| Reference safety | Preserve the complete direct-module visibility index and test actual snapshot boundaries. | src/arctrellis/frameworks/extraction.py, src/arctrellis/indexing/models.py, tests/frameworks/test_flow.py | 94cdfd6dc4e789f2bc315f2fb82a05ac98f37ec9 | D-091 |
| Scope and provenance | Defer class dependencies and validate exact constructor/Depends witnesses and app identity. | src/arctrellis/frameworks/flow_extraction.py, src/arctrellis/frameworks/flow_models.py, src/arctrellis/frameworks/flow.py, src/arctrellis/indexing/models.py, tests/frameworks/test_flow.py, README.md | 94cdfd6dc4e789f2bc315f2fb82a05ac98f37ec9 | D-092 |
| Verification gate | Record52 framework/347 total tests, quality/isolation checks, smoke and reviewed corrections. | README.md, decisions.md, flow.md, handoff.md | 94cdfd6dc4e789f2bc315f2fb82a05ac98f37ec9 | D-093 |

## 20. Static router path composition

Input: prefix/mount observations captured within the existing parse lifetime and an independently resolved pre-handler graph.

```text
extract_router_observations()             frameworks/composition_extraction.py; no reparse
 ├─ _bindings()                           shared unique canonical constructor provenance
 ├─ router prefix syntax                  retain static literal or explicit unsupported value
 └─ direct include_router/use             retain module-level mount site; never execute
compose_router_paths()                    frameworks/composition.py; retained records only
 ├─ validate router constructor witnesses against existing entities/import decisions
 ├─ resolve same-file router reference    no imported-variable or recursive mount inference
 ├─ reject unsupported boundaries        FastAPI trailing prefixes/dynamic values, doubled route-leading slash
 ├─ preceding FastAPI declaration subset do not emulate lifecycle differences or recursively follow mounts
 ├─ join_http_paths()                     trim only boundary slashes; preserve trailing route slash
 ├─ create effective endpoints            retain local fact and distinct mount identities
 └─ copy DEFINES/EXPOSES/pre-handler proof add route/prefix/constructor/mount Evidence without raising confidence
```

Mount ownership is the application module. Prefix-only paths are router configuration, not proof of public mounting. Unsupported/ambiguous mounts create no effective path. Middleware edges remain separate from EXPOSES, never synthetic execution CALLS. No source files are reopened.

## Changes in this session (Phase 1.9B)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Static composition | Capture configuration/mount observations and preserve local/effective endpoint facts with multi-site proof. | src/arctrellis/frameworks/, src/arctrellis/indexing/, src/arctrellis/calls/resolution.py, src/arctrellis/resolution/imports.py, tests/frameworks/test_composition.py, README.md | ee5b1d626a142a410ab5f9e01a201bae8faa511c | D-094 |
| Composition hardening | Reject invalid FastAPI prefix boundaries and unusual route slash normalization; use keyword-only graph filters and typed router validation. | src/arctrellis/frameworks/composition.py, src/arctrellis/frameworks/composition_extraction.py, src/arctrellis/frameworks/flow_models.py, src/arctrellis/indexing/models.py, tests/frameworks/test_composition.py | ee5b1d626a142a410ab5f9e01a201bae8faa511c | D-095 |
| Verification and documentation | Add repeatable mixed flow/proof and seven negative smoke cases; document local/effective ownership and bounded composition. | tests/frameworks/flow_smoke.py, README.md, decisions.md, flow.md, handoff.md | ee5b1d626a142a410ab5f9e01a201bae8faa511c | D-096 |
| Final quality and handoff | Share coordinate containment validation and record all passing gates, audits, skips and twelve-section continuation state. | src/arctrellis/frameworks/models.py, src/arctrellis/frameworks/flow_models.py, src/arctrellis/frameworks/composition_models.py, src/arctrellis/indexing/models.py, README.md, decisions.md, flow.md, handoff.md | ee5b1d626a142a410ab5f9e01a201bae8faa511c | D-097 |

## 21. Static test semantics

index_repository -> _analyze_file -> extract_test_observations (after router extraction, before parse release).
RepositoryIndexResult retains TestObservation tuples and per-file counts; callback calls retain owned spans only.
Python tests reference existing FUNCTION/METHOD declarations. JS callback tests have explicit semantic TEST ownership,
without general anonymous FUNCTION entities. Failed files contribute no observations.

resolve_imports -> resolve_calls -> optional resolve_http_endpoints/resolve_framework_flow -> analyze_tests.
analyze_tests uses _validate_snapshots, copies call or matching enriched base_graph, adds TEST and DEFINES,
resolves callback CallSite values through shared _Symbols/_resolve/_edge, then derives direct TESTS from CALLS.
TestDerivation retains original CALLS and derived TESTS IDs. Evidence points to invocation coordinates,
with python_direct_test_call/ecmascript_direct_test_call and LIKELY/0.85. TestAnalysisResult returns a new graph.
No transitive TESTS, endpoint test classification, target execution, source reread or runtime coverage occurs.

## Changes in this session (Phase 2.0A)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Test contracts and identity | Add immutable observations, TEST identity, callback ownership, result and snapshot validation. | src/arctrellis/test_semantics/, src/arctrellis/indexing/, src/arctrellis/calls/, src/arctrellis/resolution/imports.py, src/arctrellis/frameworks/resolution.py | 561382be859f04e4605ff8e7db1f2abe038ba834 | D-098 |
| Recognition policy | Restrict Python containers and JS/TS direct static callbacks/suites. | src/arctrellis/test_semantics/extraction.py, tests/test_semantics/test_analysis.py, README.md | 561382be859f04e4605ff8e7db1f2abe038ba834 | D-099 |
| Direct proof | Derive evidence-backed direct TESTS, preserve enriched graphs and provide realistic static smoke. | src/arctrellis/test_semantics/resolution.py, tests/test_semantics/ | 561382be859f04e4605ff8e7db1f2abe038ba834 | D-100 |
| Boundary corrections | Fix callback parentage, optional calls and local binding contradictions. | src/arctrellis/test_semantics/, tests/test_semantics/test_analysis.py | 561382be859f04e4605ff8e7db1f2abe038ba834 | D-101 |
| Verification gate | Record targeted/full quality gates, static smoke and local audits. | README.md, decisions.md, flow.md, handoff.md, tests/test_semantics/smoke.py | 561382be859f04e4605ff8e7db1f2abe038ba834 | D-102 |

## Changes in this session (Phase 2.0A correction)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Callback binding safety | Exclude shorthand destructuring and named callback self-bindings; repeat the full gate before resuming2.0B. | src/arctrellis/test_semantics/extraction.py, tests/test_semantics/test_analysis.py, README.md, decisions.md, flow.md, handoff.md | f1ad053fefffe7dd9d44d1841b509c78c76a0cd1 | D-103 |

_callback_shadows now recognizes identifier and shorthand_property_identifier_pattern in binding positions,
and the callback function-expression name. Affected direct callback calls are omitted before resolution;
TEST identity remains. This applies to test callbacks and inherited describe suite bindings.

## 22. Database-operation foundation

Common construction boundary:
make_database_operation_observation -> validate canonical execution owner and operation coordinates
-> DatabaseOperationObservation (computed UUID5, owner ID/kind, provider/kind/name/target, immutable metadata)
-> DatabaseAnalysisResult.from_observations -> deterministic ordering and operation/provider counts.

Phase2.1 adds database extraction during index_repository and optional source-free materialization after
existing semantic enrichments (section25). SQLAlchemy/Prisma -> DatabaseOperationObservation -> validated
DATABASE_OPERATION / eligible READS_DATABASE / WRITES_DATABASE facts. No source bytes/native parser objects,
owner objects, credentials, connection handles, SQL execution or universal DB confidence are retained/introduced.

## Changes in this session (Phase 2.0B)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Database contract | Add immutable operation model, canonical-owner factory, deterministic identity and ordered results/counts. | src/arctrellis/database/, tests/database/test_foundation.py | 3d8ec6b71d02181ca80738a451230d669c5ea0e1 | D-104 |
| Graph boundary | Defer conversion/adapters and verify generic execute negatives in Python/JS/TS. | tests/database/test_foundation.py, README.md, flow.md | 3d8ec6b71d02181ca80738a451230d669c5ea0e1 | D-105 |
| Documentation and synthetic smoke | Correct stale capability prose/test expectation and distinguish model construction from extraction. | tests/database/smoke.py, tests/database/test_foundation.py, README.md, decisions.md, flow.md | 3d8ec6b71d02181ca80738a451230d669c5ea0e1 | D-106 |
| Final verification and handoff | Record393-test quality gate, reviewed correction, synthetic smokes and twelve-section continuation state. | README.md, decisions.md, flow.md, handoff.md | 3d8ec6b71d02181ca80738a451230d669c5ea0e1 | D-107 |
| Review environment audit | Record system-interpreter import/parser failures and corrected project-interpreter verification. | decisions.md, flow.md, handoff.md | 3d8ec6b71d02181ca80738a451230d669c5ea0e1 | D-108 |

## 23. Standalone SQLAlchemy extraction (Phase 2.1A)

```text
extract_sqlalchemy_operations(parsed_source, extraction_result)
 ├─ SyntaxContext                       validate revision; temporary normalized syntax only
 │   ├─ extract_call_sites               reuse canonical execution owners
 │   ├─ _writes + parameters/imports     conservatively exclude competing bindings
 │   └─ direct statement indexes         prove import/constructor assignment positions
 ├─ SyntaxContext.client/imported        require Session and statement import witnesses
 └─ make_database_operation_observation retain intent/capability, exact invocation and witness IDs
```

This adapter also runs through extract_database_operations during indexing (section25). Context managers/factories/typed parameters
and comprehension binding environments are omitted. Staged mutation is not database write evidence.
Recovery suppresses affected constructs while unaffected canonical calls survive; internal invalid
revision/owner invariants raise rather than silently disappearing. No filesystem reads or target imports.

## Changes in this session (Phase 2.1A)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| SQLAlchemy adapter | Require import/constructor provenance and retain operation effect stages. | src/arctrellis/database/, tests/database/test_sqlalchemy.py, README.md | 0f3e24585f927dc293e6ae8ae9143e9df0751ef9 | D-109 |
| Scope review | Omit comprehensions, remove supplied call override and disambiguate nested scopes. | src/arctrellis/database/syntax.py, tests/database/test_sqlalchemy.py, decisions.md, flow.md, handoff.md | 0f3e24585f927dc293e6ae8ae9143e9df0751ef9 | D-110 |

## 24. Standalone Prisma extraction (Phase 2.1B)

```text
extract_prisma_operations(parsed_source, extraction_result)
 ├─ SyntaxContext                         canonical calls and conservative lexical binding indexes
 ├─ SyntaxContext.client                  named @prisma/client import + preceding unique new assignment
 └─ make_database_operation_observation   retain client_request/transaction_control and accessor, not table
```

The repository database pass now dispatches this adapter (section25). Catch/with, comprehensions, raw queries, computed access,
anonymous bodies, factories and arbitrary aliases are omitted; no target code/package/SQL execution.

## Changes in this session (Phase 2.1B)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Prisma adapter | Recognize direct JS/TS client requests with method/accessor metadata. | src/arctrellis/database/, tests/database/test_prisma.py, README.md | b0ecb51aea242e78fc25b25f3eccbc348f937195 | D-111 |
| Scope guard | Defer catch/with environments and record named function self-bindings. | src/arctrellis/database/syntax.py, tests/database/test_prisma.py, decisions.md, flow.md, handoff.md | b0ecb51aea242e78fc25b25f3eccbc348f937195 | D-112 |

| Cross-scope contradictions | Invalidate explicitly mutated root names and TS enum/namespace names conservatively. | src/arctrellis/database/syntax.py, tests/database/test_prisma.py, decisions.md, flow.md, README.md, handoff.md | b0ecb51aea242e78fc25b25f3eccbc348f937195 | D-113 |

## 25. Repository database interactions (Phase 2.1C)

```text
index_repository(root)
 ├─ scan_repository / _blocked_providers    inventory detects conventional root/src package collisions
 └─ _analyze_file
     ├─ parse_discovered_file              existing safe single source read/normalized parse
     ├─ extract_entities / extract_call_sites canonical declarations and body ownership
     ├─ framework/router/test extraction   existing independent observations
     ├─ extract_database_operations        same ParsedSource/ExtractionResult, never reopen source
     │   ├─ extract_sqlalchemy_operations  Session/statement import + unique constructor binding
     │   └─ extract_prisma_operations      named import + unique new binding
     ├─ lexical/file graph assembly        unchanged declaration graph counts
     └─ FileIndexResult                   DB count; release ParsedSource when helper returns
RepositoryIndexResult                     lightweight database_observations only
 └─ validate_database_observation         canonical owners/calls/imports, effect contract, statement call proof
resolve_imports -> resolve_calls -> resolve_http_endpoints -> resolve_framework_flow -> analyze_tests
materialize_database_graph(index, base_graph=tests.graph)
 ├─ replace(index)                        revalidate counts/proof without rereading syntax
 ├─ check preserved index/no prior DB facts reject mismatched snapshot before changes
 ├─ copy CodeGraph records                independent mutable graph; preserve all supplied enrichment
 ├─ _operation_entity                     deterministic DATABASE_OPERATION; parent owner, no DEFINES
 ├─ _database_edge                        eligible read/write/delete capability only; LIKELY/0.85
 │   └─ Evidence                          exact invocation, coordinates, provider/method/effect metadata
 └─ DatabaseGraphResult                   ordered nodes/proof, counts, explicit unlinked/staged values
CodeGraph.shortest_path                   existing filtered traversal retains each original proof edge
```

Database observations share COMPLETE/PARTIAL/FAILED file contracts. Recovery excludes affected syntax;
unaffected observations survive PARTIAL. Existing typed extraction/parsing errors return bounded FAILED
stage/type summaries and zero records; internal ValueError/TypeError invariants propagate loudly.
Standalone and result constructors validate structure, not source authenticity. Unknown/staged/transaction
sites have nodes but no fabricated database edge. No source/tree/native types escape, no materialization
parse/read, no SQL/target/runtime dependency execution and no new dependencies or core kinds.

## Changes in this session (Phase 2.1C)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Index lifecycle | Capture and validate lightweight operations/counts; preserve all snapshot fields. | src/arctrellis/database/extraction.py, validation.py, syntax.py, src/arctrellis/indexing/, src/arctrellis/calls/resolution.py, src/arctrellis/frameworks/resolution.py, src/arctrellis/resolution/imports.py | b2a5e1a9c8b684cd053d065a0289c83d6d19d2a6 | D-114 |
| Database graphs | Materialize site entities and eligible evidence-backed capabilities in independent graph. | src/arctrellis/database/graph.py, __init__.py, tests/database/test_graph.py | b2a5e1a9c8b684cd053d065a0289c83d6d19d2a6 | D-115 |
| Statement proof | Require actual nested statement invocation coordinates/ID, not unrelated import existence. | src/arctrellis/database/sqlalchemy.py, validation.py, tests/database/test_graph.py | b2a5e1a9c8b684cd053d065a0289c83d6d19d2a6 | D-116 |
| Verification | Mixed static smoke, traces, isolation, negatives, public imports and final documentation. | tests/database/smoke.py, tests/database/test_graph.py, tests/test_architecture.py, README.md, decisions.md, flow.md, handoff.md | b2a5e1a9c8b684cd053d065a0289c83d6d19d2a6 | D-117 |


## 26. Evidence-preserving structural paths (Phase 2.2A)

Input: an existing CodeGraph plus exact source ID, operation filters, positive depth/path/expansion budgets
and optional caller-supplied AnalysisCompleteness. No analysis lifecycle operation runs here.

```text
trace_endpoint_to_database / trace_callable_to_database
 ├─ require_entity                       distinguish unknown ID from unsupported source kind
 ├─ validate_operations                  read/write/delete metadata filter, never infer from names
 └─ search                               shared query-layer bounded BFS, public graph access only
     ├─ validate_limits                  reject bool, zero, negative and noninteger values
     ├─ outgoing / incoming              deterministic original records; each inspected edge consumes budget
     ├─ transition                       enforce EXPOSES -> CALLS* -> DB, or CALLS* -> DB
     │   └─ database_operation           validate terminal kind/category/effect; zero CALLS allowed
     ├─ simple-path check                prevent repeated entity/cycle enumeration
     ├─ depth / extra result / budget    mark explicit truncation reasons when exploration is cut
     ├─ EvidencePath.from_graph          GraphPath continuity + exact entity/relationship membership
     ├─ path_order                       length, relationship IDs, entity IDs
     └─ PathQueryResult                  preserve context, limits, inspected count and original proof
         └─ to_dict                      explicit JSON primitives; retain original proof metadata
find_paths                               explicit-kind general forward/reverse nonempty paths
 └─ search                               same bounded engine, not generic shortest_path
```

Reverse search normalizes returned paths into original forward edge order and marks direction=reverse.
Minimum confidence class/score reports weakest support, not probability; absent score stays unknown.
No known path is an absence of available static proof, even with complete indexed files. Results contain
immutable domain values, not a mutable graph; concurrent graph mutation is unsupported. Querying never
reads source, invokes parsing/resolution/materialization or adds graph records. Typed query errors separate
unknown source IDs, unsupported kinds, invalid budgets and corrupted relevant graph structure.

## Changes in this session (Phase 2.2A)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Query boundary | Immutable proof paths, typed errors and explicit primitive output. | src/arctrellis/query/, tests/query/ | cc52333412c69b31486ca486101297e84fec6e0a | D-118 |
| Traversal | Constrained BFS, simple paths, budgets, truncation and weakest support. | src/arctrellis/query/models.py, traversal.py | cc52333412c69b31486ca486101297e84fec6e0a | D-119 |
| Database traces | Exact endpoint/callable patterns, operation filters and real adapter tests. | src/arctrellis/query/database.py, tests/query/test_paths.py | cc52333412c69b31486ca486101297e84fec6e0a | D-120 |

Gate: paths7 tests and full424 tests OK/skipped7; Ruff lint/126-file format, strict mypy73, compileall, pip check and architecture3 pass. No remote.


## 27. Practical architecture queries (Phase 2.2B)

```text
get_direct_database_operations(graph, owner)
 ├─ require_entity / validate_operations  explicit supported owners and category filters
 └─ search                               one-hop DB edges only; retain provider/effect/operation proof
list_direct_database_callers(graph)
 ├─ relationships                       existing sorted snapshot, scan under budget
 ├─ database_operation                  eligible direct capability and FUNCTION/METHOD owner
 └─ EvidencePath.from_graph              one-hop proof paths; source=None marks graph-wide inventory
find_direct_tests_for_symbol(graph, symbol)
 ├─ require_entity                      FUNCTION/METHOD only, no handler-to-endpoint inference
 └─ search(reverse)                     direct TESTS from TEST only; no transitive coverage
find_callers(graph, target, transitive=False)
 ├─ require_entity                      callable target
 └─ search(reverse CALLS)                direct edges, or every simple callable prefix in transitive mode
find_potentially_affected_endpoints(graph, changed)
 ├─ require_entity                      changed callable
 └─ search(reverse)
     ├─ reverse CALLS*                  callable dependency candidates, cycle/depth/path/budget bounds
     ├─ reverse EXPOSES                 endpoint registration evidence, zero CALLS valid
     └─ EvidencePath.from_graph         normalize forward endpoint -> changed order; mark reverse search
list_endpoints(graph, filters)
 ├─ entities                            sorted existing snapshot
 ├─ exact metadata filters             method/framework/path/local/declared/effective/application
 └─ EntityQueryResult                   original registrations; limits/truncation/context retained
AnalysisSummary(complete, partial, failed).completeness
 └─ caller supplies query context       no source/index retained; graph-only default unknown
```

Every query is source-free/read-only; direct facts are never synthesized from transitive paths.
Caller queries omit TEST/MODULE callers; test lookup is direct static evidence, never HTTP coverage.
Middleware impact is deferred. Unknown paths do not prove absence of runtime impact or test execution.
Original relationship direction and weakest support remain intact even when discovery is reverse.
Inventory filtering never silently merges local/effective or duplicate route registrations.

## Changes in this session (Phase 2.2B)

| Area | Change | Files | Commit | Decision |
|---|---|---|---|---|
| Direct queries | DB owner/operation inventory and direct TESTS lookup with original proof. | src/arctrellis/query/database.py, tests.py | uncommitted | D-121 |
| Reverse queries | Direct/transitive callable callers and endpoint impact candidates. | src/arctrellis/query/dependencies.py, impact.py, traversal.py | uncommitted | D-122 |
| Metadata/context | Endpoint inventory, application scope and lightweight completeness counts. | src/arctrellis/query/endpoints.py, models.py, tests/query/test_architecture_queries.py | uncommitted | D-123 |
