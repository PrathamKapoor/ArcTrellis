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

Output: importable domain, graph, ingestion, parsing and extraction APIs. Installation failures propagate from pip.
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
     │   ├─ build_lexical_graph()        extraction/lexical.py; retain existing parent proof
     │   ├─ _file_entity()               create path-based FILE with analyzed byte size
     │   │   └─ _file_id()               indexing/ids.py; content-independent structural identity
     │   └─ _membership()               PROVEN FILE DEFINES MODULE with root evidence
     │       └─ _stable_id()             versioned canonical JSON/UUID5 proof identities
     ├─ CodeGraph.add_entity()           graph/graph.py; merge canonical endpoints first
     ├─ CodeGraph.add_relationship()     graph/graph.py; retain immutable evidence
     └─ FileIndexResult()                indexing/models.py; explicit COMPLETE/PARTIAL/FAILED summary
RepositoryIndexResult()                  indexing/models.py; validate ordered outcomes and graph counts
```

Output: inventory, merged in-memory graph and frozen per-file summaries. FILE identity
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
 ├─ CodeGraph.add_entity()/add_relationship()  clone base graph without mutation
 ├─ _catalog(modules)                          resolution/catalog.py: derive path-based module candidates
 └─ for each IMPORT in deterministic ID order
     ├─ _python_candidates(...)               calculate absolute/relative Python aliases
     ├─ _script_candidates(...)               match safe relative JS/TS paths against catalog
     ├─ ImportResolution(...)                 record unique, ambiguous or unresolved result
     └─ _import_edge(site, target)             only unique candidates become LIKELY/0.90 edges
         └─ CodeGraph.add_relationship()       retain import-site evidence
```

Python supports identifier-component path aliases and an explicit leading-src heuristic; no environment/configuration or imported-symbol resolution. JS/TS probes exact supported extensions, or all supported extension/index paths for extensionless names; explicit directory-intent specifiers probe only indexes; no priority guesses. Unknown extensions, bare imports, escaped literals and outside-root paths are unresolved. Ambiguous imports record sorted candidate IDs without an edge. Output is ImportResolutionResult with a new graph and decisions. Invalid graph/summary invariants abort explicitly; original index remains unchanged. Evidence points to the IMPORT location with language-specific analysis method, not a guessed target declaration.

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
| Decision-history correction | Restore historical entry boundaries from HEAD after an acfd6093f95e0f9dd6b150ad625cb5ab6fee4a79 insertion error. | decisions.md, flow.md | 66d881e02bcb52e467720b39293319ff7595f085 | D-048 |
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
