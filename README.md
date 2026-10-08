# ArcTrellis

**Prove how your codebase works.**

ArcTrellis is intended to become an evidence-first repository intelligence system:
static analysis will identify code entities and relationships, and explanations
will point to verifiable source evidence.

The analysis engine establishes what can be proven. The explanation layer
explains that evidence. Structural truth must remain independent of an explanation
provider.

## Current status

Early implementation: Phase 1.5, Python/JavaScript/TypeScript semantic entities and
evidence-backed lexical graph assembly from normalized syntax. Declarations and
import sites become canonical CodeEntity values. Import/call/inheritance resolution,
routes, middleware, tests and database semantics are not implemented. There is no
GitHub cloning, persistence, BM25/vector retrieval,
LLM integration, API, frontend or change-impact product mode.

Current capabilities:

- Language-independent entity and directional relationship kinds.
- Immutable, validated source locations, entities, evidence and relationships.
- Explicit static confidence classifications and optional bounded numeric scores.
- A public `arctrellis.core` API with standard-library unit tests.
- Local in-memory graph construction with endpoint integrity and explicit ID conflicts.
- Incoming/outgoing queries, unique neighbors and relationship-kind filtering.
- Bounded forward/reverse traversal and deterministic unweighted shortest paths.
- Immutable path records preserving each original relationship and its evidence.
- Local filesystem inventory with relative POSIX paths, byte sizes and explicit omissions.
- Python, JavaScript and TypeScript extension detection, with deterministic supported subsets.
- Dependency/build/cache pruning and non-following link/reparse-point handling.
- Tree-sitter parsing for Python, JavaScript, TypeScript and TSX.
- Immutable normalized syntax with exact bytes, grammar fields and recovery diagnostics.
- Bounded single-file reads with current-path checks and a default 2 MiB limit.
- Python/JavaScript/TypeScript MODULE/CLASS/FUNCTION/METHOD/IMPORT extraction with lexical ownership.
- Revision-deterministic IDs, exact locations, signatures and retained decorators.
- Explicit partial results that conservatively omit malformed semantic declarations.
- Single-file lexical graphs with proven DEFINES relationships and exact declaration evidence.

Planned capabilities: repository acquisition and indexing; lexical, semantic and structural symbol
search; architecture questions; execution and dependency tracing; source evidence
inspection; reverse dependency impact; retrieval and evidence quality evaluation.

## Development

Requires Python 3.13 or newer. This phase is verified on Python 3.13.14; other
versions are not yet tested. From the repository root on Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\python.exe -m unittest discover -s tests -v
.venv\Scripts\python.exe -c "from arctrellis.core import CodeEntity, Relationship, Evidence, SourceLocation"
.venv\Scripts\python.exe -c "from arctrellis.graph import CodeGraph, GraphPath, TraversalResult"
```

Core, graph, discovery and extraction use the standard library. Parsing uses pinned Tree-sitter
and dedicated language grammars; setuptools is only the packaging backend.
No formatter, linter or type checker is configured in this phase.

## Architecture and invariants

`src/arctrellis/core/models.py` defines the domain; `arctrellis.core` is the public
import boundary. Language extraction translates normalized syntax into these
records. All supported languages and future storage share the same vocabulary.

Relationships read **source → kind → target**: a source method `CALLS` a target
method. They embed an immutable tuple of evidence records. Each evidence record
contains a source range and a snake_case analysis method.

IDs are nonempty caller-supplied strings. Producers must assign reproducible IDs
for a repository revision. Constructors do not enforce global uniqueness, target
existence or proof adequacy. `UNRESOLVED` retains uncertainty; producers may supply
an opaque placeholder target ID. Adding that relationship to CodeGraph requires
explicitly inserting its placeholder entity first. No numeric classification
thresholds are assumed.

Paths are unchanged relative strings using `/`, with inclusive 1-based line ranges.
Absolute paths, drive-relative paths, traversal and noncanonical separators are
rejected. Files are not opened and line counts are not checked.

All records are frozen and hashable. Metadata is an ordered tuple of unique
string-key/string-value pairs; nested containers and mutable dictionaries are
rejected. Tuple order participates in equality. Use `dataclasses.asdict()` for a
primitive representation and `json.dumps()` for JSON; enums are string enums and
tuples encode as JSON arrays. This is a conversion boundary, not a versioned wire
format or persistence implementation.

## Local graph queries

`arctrellis.graph.CodeGraph` stores canonical records by ID with separate incoming
and outgoing indexes. Add entities before relationships. Insertions return `None`;
equal value reinsertions are idempotent and preserve the original stored object.
Conflicting IDs raise `DuplicateEntityError` or `DuplicateRelationshipError`.
Distinct edge IDs may describe the same source/kind/target triple.

`get_entity()` and `get_relationship()` raise `UnknownEntityError` and
`UnknownRelationshipError`; `has_entity()` and `has_relationship()` return booleans.
Unknown entity IDs also fail adjacency, traversal and path queries. Missing
relationship endpoints fail before any storage/index change. This applies equally
to UNRESOLVED relationships; any placeholder entity must be supplied explicitly.
The graph does not validate parent IDs or certify proof adequacy.

`entities()` and `relationships()` return immutable snapshots sorted by ID.
`outgoing()`, `incoming()`, `successors()` and `predecessors()` accept an optional
`kind=RelationshipKind.CALLS` filter. Edges sort by relationship ID; unique neighbor
entities sort by entity ID.

`traverse_forward(start_entity_id, max_depth)` and `traverse_reverse(...)` return a
`TraversalResult.entities` tuple in breadth-first discovery order, including the
starting entity once. Depth zero includes only the start. Depth must be a
non-boolean integer >=0. Each expansion follows relationship IDs in lexical order,
independent of insertion order. Cycles and parallel edges never repeat nodes.
Traversal results contain nodes only, not a path or induced subgraph.

`shortest_path(source_entity_id, target_entity_id)` returns a `GraphPath` with
ordered `entities` and original `relationships`, preserving embedded evidence.
Every edge connects its adjacent entities in source-to-target order, with
`len(entities) == len(relationships) + 1`. Same-node queries return one entity and
zero edges. Disconnected known nodes return `None`. Equal-length ties follow BFS
discovery through sorted local relationship IDs.

Traversal and shortest paths accept
`relationship_kinds={RelationshipKind.CALLS, RelationshipKind.EXPOSES}`. `None`
allows all kinds; an empty set follows no edges. Sets and frozensets must contain
enum members. Queries follow explicitly inserted edges regardless of confidence;
they make no inferred relationship or new proof claims.

Dictionary lookups average O(1), adjacency queries cost O(degree), and BFS costs
O(V+E) over the explored subgraph. Sorted adjacency insertion costs O(degree);
full snapshots and neighbor sorting have sorting costs. The append-oriented graph
has no removal, caching, persistence or concurrency guarantees.

## Local repository discovery

```python
from arctrellis.ingestion import scan_repository

inventory = scan_repository("path/to/local/repository")
for source in inventory.supported_files:
    print(source.path, source.size_bytes, source.language)
```

`files` includes every discovered ordinary file, including unsupported files with
`language=None`. `supported_files` includes Python (`.py`, `.pyi`), JavaScript
(`.js`, `.jsx`, `.mjs`, `.cjs`) and TypeScript (`.ts`, `.tsx`, `.mts`, `.cts`).
Extensions match case-insensitively; original path casing is preserved. Files and
`skipped_paths` sort by repository-relative path. `file_count`,
`supported_file_count` and immutable `language_counts` provide summaries.
Records are frozen, hashable and convertible with `dataclasses.asdict()`.
The scan root is runtime context retained by the caller, not stored identity.

Default directory exclusions apply at any depth: `.git`, `node_modules`, `.venv`,
`venv`, `env`, `__pycache__`, `dist`, `build`, `coverage`, `.coverage`, `.next`,
`.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `.cache`, and `vendor`. Names match
case-sensitively. `excluded_directories={"custom"}` replaces defaults; an empty set
disables name exclusions. Link checks always remain active. Hidden directories
such as `.github` are retained unless explicitly excluded. **`.gitignore` is not
interpreted.** Excluded directories are pruned before descent, not filtered later.

Existing readable empty directories are valid; Git is not required. Missing,
file or linked roots (including linked ancestors) raise `InvalidRepositoryPathError`.
Unexpected filesystem errors raise `RepositoryAccessError`, retaining the original
exception; no apparently complete partial inventory is returned. Inputs must use
portable relative filenames: invalid separators/traversal/control characters fail
explicitly rather than being silently normalized. Filename spaces are preserved.

### Security boundary

Discovery performs filesystem inspection only. It does not read source contents,
import repository modules, execute scripts, install target dependencies, execute
package hooks, hash files or follow symbolic links. Linked files/directories,
Windows junctions and other reparse points are recorded as skipped. Nonregular
objects are skipped without opening them.

The target tree must remain stable during scanning. Directory identity checks
detect ordinary replacements, but Windows pathname operations do not provide an
atomic sandbox against concurrent hostile replacement. This is metadata discovery,
not a guarantee of atomic safe reads; parsing performs its own revalidation below.
Work is linear in visited entries plus sorting file and omission records; there is
no concurrent or incremental scanner.

## Single-file syntax parsing

```python
from arctrellis.ingestion import scan_repository
from arctrellis.parsing import parse_discovered_file, parse_source

root = "path/to/local/repository"
inventory = scan_repository(root)
if inventory.supported_files:
    parsed = parse_discovered_file(root, inventory.supported_files[0])
    print(parsed.root.kind, parsed.diagnostic_count)
```

`parse_source(path, language, source_bytes)` provides the same normalized result
without filesystem access. Language is the ingestion `Language` enum. All ten
supported extensions match case-insensitively; extension/language contradictions
raise `UnsupportedLanguageError`. `.tsx` uses the dedicated TSX grammar, retaining
canonical `typescript`. JavaScript's grammar also accepts JSX.

`ParsedSource` owns the original immutable bytes, a `SyntaxNode` root and a tuple
of `ParseDiagnostic` records. No native Tree/Node/Parser/Language/Point object leaves
the adapter. Tree-sitter kinds and field names are grammar vocabulary, not resolved
symbols or architecture facts. Syntax alone is not a semantic graph; extraction produces canonical entities.

Nodes retain named syntax plus ERROR/MISSING constructs, including anonymous missing
punctuation. Ordinary punctuation is omitted. Children retain grammar/source order;
`walk()` yields iterative preorder and `child_by_field(name)` returns the first
direct match or `None`. `parsed.bytes_for(node)` returns exact bounded bytes without
decoding or claiming that a caller-supplied node belongs to this tree.

`SyntaxSpan` uses inclusive start/exclusive end byte offsets, 1-based lines and
0-based **byte** columns. End points are exclusive, including the next line's
column zero. These differ from core `SourceLocation` inclusive line ranges.
Malformed source returns syntax and ERROR/MISSING diagnostics without invented
compiler messages. Hard initialization/execution failures use typed parsing errors.
Bytes remain exact, including undecodable inputs; no decoded copy is stored.

Both entry points accept `max_source_bytes=` with a positive integer override.
The default is `DEFAULT_MAX_SOURCE_BYTES = 2 * 1024 * 1024`; equality is permitted.
Oversized sources raise `SourceTooLargeError`; truncated bytes are never parsed.
Current file size, rather than discovery metadata, is checked. Reads are bounded
to limit+1 bytes, and observed path/descriptor identity, size and mtime changes
raise `SourceReadError`. Observed linked or nonregular paths raise its subtype
`UnsafeSourceError`. Root ancestors and final target containment are revalidated.

### Parsing security and resource boundary

Discovery reads metadata only. Parsing deliberately reads supported source bytes
for syntax analysis. Neither executes/imports target code, installs target
dependencies, runs package hooks/scripts/tests or loads repository plugins. File
parsing rejects observed symlinks, junctions and reparse points, with available
non-following open flags. Pathname checks still require a stable tree and are not
an atomic sandbox against hostile concurrent replacement.

Fresh parser instances avoid shared mutable parser state; there is no pooling,
parallel parsing, repository-wide parse job or incremental cache. Normalized syntax
and retained source consume extra memory. The byte limit bounds input size, not
native execution time or total tree memory. Iterative conversion, walking, equality
and hashing support deep syntax. Native parser errors are not all Python exceptions;
syntax parsing is not a process sandbox.

Verified pins: tree-sitter 0.25.2, tree-sitter-python 0.25.0,
tree-sitter-javascript 0.25.0 and tree-sitter-typescript 0.23.2. Runtime 0.26.0 was
tested and rejected after reproducible native point-access crashes on this Windows
environment; see D-027. Upgrades require grammar and deep-input regression checks.

## Python semantic entity extraction

```python
from arctrellis.extraction import extract_python_entities
from arctrellis.ingestion import Language, scan_repository
from arctrellis.parsing import parse_discovered_file

root = "path/to/local/repository"
inventory = scan_repository(root)
python_file = next((file for file in inventory.supported_files
                    if file.language is Language.PYTHON), None)
if python_file is not None:
    result = extract_python_entities(parse_discovered_file(root, python_file))
    for entity in result.entities:
        print(entity.kind, entity.qualified_name, entity.signature)
```

Extraction is a pure transformation of one Python `ParsedSource`; it performs no
filesystem access. `ExtractionResult` is frozen and hashable, with a module-first
entity tuple, `partial`, `module` and `entities_of_kind()`. It validates unique IDs,
consistent file/language/span metadata and parents already present in the result.
Remaining entities sort by start byte, end byte, kind and ID.

MODULE uses the file stem as its name and the repository-relative path as its
qualified name, without guessing a Python package root. Classes/functions use
`path::Outer.inner` lexical names. A function whose nearest semantic parent is CLASS
is METHOD, including definitions inside class control flow and decorated descriptors.
A nested function inside a method is FUNCTION. Async definitions retain `is_async`.
Variables, lambdas and referenced external names are not extracted. Names beginning
with `test_` remain ordinary functions; route decorators do not create endpoints.

`CodeEntity.signature` is an optional final field preserving existing positional
constructor arguments. Classes, functions and methods retain exact multiline
headers without the final colon, body or decorators, including lambda annotations.
Decorated entities include the wrapper in their source range and store ordered
exact snippets under `decorator.0`, `decorator.1`, etc. Metadata preserves all six
syntax coordinates as decimal strings; SourceLocation keeps inclusive lines.

Imports produce one IMPORT per local binding, including future imports. Direct
dotted imports bind their first component unless aliased. From-imports retain
their module, imported name, alias, binding, relative level and wildcard flag.
Relative dots are preserved and wildcards remain a single `*`; no names are resolved
or expanded. Import qualified names use `scope::import:binding@start_byte`.
Imports inside functions/classes/methods retain the nearest semantic parent.

### Identity and partial-result contracts

UUID5 with NAMESPACE_URL hashes compact canonical JSON of the versioned marker,
language, repository-relative path, kind, lexical qualified name, start byte and
end byte. Identical input reproduces IDs. Duplicate declarations retain separate
IDs through their positions, even when human-readable names match. These IDs are
**revision-deterministic, not edit-stable**: moving/editing declarations can change
them. Repository identity is not yet part of the key; independent repositories
with identical components can produce the same IDs.

Recovery anywhere in a declaration/import/decorated wrapper suppresses that whole
semantic scope and its descendants. Unaffected sibling declarations survive.
`partial=True` records parser problems or structural omissions, including empty
suites that the grammar can return without diagnostics. This policy favors reliable
identity over recall and does not certify full Python compiler validity.

Encoding detection uses `tokenize.detect_encoding`; exact slices use that encoding
without executing code. UTF-8 identifiers, UTF-8 BOM and Latin-1 string literals
are tested. Non-UTF-8 identifiers can still produce native-parser recovery and a
partial result: the parser's original bytes are not rewritten. Unknown encodings
or undecodable source raise chained `SourceDecodingError`; wrong-language inputs
raise `UnsupportedExtractionLanguageError`.

### Extraction security boundary

Discovery reads metadata; parsing reads bytes; extraction interprets normalized
syntax and those already-owned bytes. Extraction never imports target modules,
executes source, installs target dependencies, runs target tests or performs file
reads. It imports no native parser types and outputs only canonical entities.
Entity extraction does not create relationships, resolve dependencies or process
an entire repository. A separate builder creates lexical edges from validated parent
IDs. Both operations perform no target execution or filesystem reads. Traversal is
iterative; final entity ordering adds sorting cost.

## JavaScript and TypeScript semantic entity extraction

```python
from arctrellis.extraction import extract_entities
result = extract_entities(parsed)  # One ParsedSource; dispatch by canonical language.
```

The language-specific extract_javascript_entities and extract_typescript_entities
entry points are also public. TSX uses TypeScript extraction. Each file has one
path-qualified MODULE. Named classes, function declarations, simple identifier-bound
arrow/function expressions and class methods become canonical entities. Bound class
expressions use the binding's name. Callable class fields become METHOD, with
declaration_form distinguishing them from method syntax. Nearest represented
lexical parents govern nested declarations; no runtime module identity is inferred.

Signatures retain exact declaration/binding headers before the body, including
TypeScript generics, annotations and class heritage. Callable binding headers begin
at the binding identifier, excluding const/let/var; callable fields retain member
modifiers. Async/generator/static/getter/
setter/constructor state and export/default-export state are metadata. Decorators
retain ordered snippets and are included in declaration locations when exposed by
the grammar. JSX/TSX elements produce no separate entities.

ES imports produce one IMPORT per default/named/namespace binding. Side-effect
imports (including empty named clauses) produce one site with an empty binding, named by the module spelling (or
its quoted literal for empty/padded names). Type-only imports retain is_type_only.
Metadata preserves module as the exact source interior and module_literal as the
quoted syntax, with module_format=source_spelling; escape sequences are not evaluated.
Simple identifier-bound require calls with one unescaped static string also become
IMPORT sites. They are syntactic sites, without proof that require is unshadowed or
resolution to a runtime dependency. Dynamic/destructured/escaped require forms are
omitted. Import sites retain their nearest semantic parent.

Unbound anonymous expressions, arbitrary object methods, computed member names,
TypeScript interfaces/type aliases/enums and ambient/type-only declarations do not
become canonical declarations. Omitted callable scopes are not traversed into a
false outer parent. No VARIABLES, EXPORTS, JSX entities or framework classifications
are invented. Strict UTF-8 decoding raises SourceDecodingError on invalid bytes.
Recovery suppresses affected declarations/scopes and marks partial; unaffected
siblings survive. Existing revision-deterministic ID/coordinate contracts apply.

## Evidence-backed lexical graph assembly

```python
from arctrellis.extraction import extract_entities, build_lexical_graph
result = extract_entities(parsed)
graph = build_lexical_graph(result)
# Existing graph.shortest_path() returns relationships with their Evidence intact.
```

The builder accepts one ExtractionResult and creates a fresh CodeGraph. All entities
are inserted first. Every non-module entity receives exactly one parent -> child
DEFINES relationship, Confidence.PROVEN and confidence_score=1.0. Evidence points
to the child's inclusive declaration SourceLocation and preserves all six exact
syntax coordinates with analysis_method=lexical_parentage.

The module has no fabricated repository parent. Imports receive lexical DEFINES,
not IMPORTS: they are unresolved declaration sites, not resolved dependencies.
No duplicate CONTAINS, CALLS or INHERITS relationships are emitted. A partial
extraction can still prove the surviving entities' lexical ownership; the caller
retains result.partial separately, as the graph makes no file-completeness claim.

Evidence and relationship IDs use distinct versioned compact JSON keys and UUID5/
NAMESPACE_URL, including parent/child identity and exact child proof coordinates.
They reproduce equal input but are not edit-stable or repository-namespaced.
The builder revalidates result invariants, failing explicitly with chained
SemanticExtractionError for corrupted producer output. Graph storage/query
semantics are unchanged. Repository-wide assembly and semantic resolution remain
future work.

See [decisions.md](decisions.md), [flow.md](flow.md) and [handoff.md](handoff.md)
for rationale, call order and continuation state.

## Repository semantic indexing

```python
from arctrellis.indexing import index_repository
index = index_repository("path/to/local/repository")
print(index.is_complete, index.complete_file_count, index.partial_file_count, index.failed_file_count)
```

The synchronous in-memory index processes supported files in inventory order.
COMPLETE/PARTIAL/FAILED outcomes are explicit; unsupported files remain inventory-only.
Typed source failures do not discard other files. Discovery failures and conflicting
graph identities abort. Failure summaries retain bounded stage/type text rather than
exception objects, traceback or source-derived error text.

Every successfully or partially analyzed file contributes a parentless FILE, its
MODULE, existing lexical entities/edges and one PROVEN FILE DEFINES MODULE relationship
with file_module_membership evidence. FILE UUID5 identity uses language/relative path,
remaining stable across content edits; declaration/proof identity remains revision-based.
Repository identity is deliberately deferred; no REPOSITORY node is invented.

Only semantic graph records, inventory and diagnostic counts survive per-file analysis.
ParsedSource, full source bytes and syntax trees are released after each helper returns.
Summary records are immutable; CodeGraph retains its existing mutable API, so completed
results should be treated as snapshots. This is not persistent indexing.
