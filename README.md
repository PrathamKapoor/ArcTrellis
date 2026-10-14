# ArcTrellis

**Prove how your codebase works.**

ArcTrellis is intended to become an evidence-first repository intelligence system:
static analysis will identify code entities and relationships, and explanations
will point to verifiable source evidence.

The analysis engine establishes what can be defended by source evidence. The explanation layer
explains that evidence. Structural truth must remain independent of an explanation
provider.

## Current status

Early implementation: Phase 2.2 with the existing quality gate, Python/JavaScript/TypeScript semantic entities and
evidence-backed lexical graph assembly from normalized syntax. Declarations and
import sites become canonical CodeEntity values. Repository indexing and a conservative
internal import-resolution and conservative static call graph subsets are implemented. Static FastAPI, Flask
and Express adapters identify HTTP endpoints with handler evidence. Inheritance resolution,
global middleware execution and runtime test coverage are not implemented. Static test declarations/direct TESTS
and provenance-backed SQLAlchemy/Prisma database observations and graph interactions are available. There is no
GitHub cloning, persistence, BM25/vector retrieval,
LLM integration, HTTP service or frontend. Deterministic structural impact candidates are available.

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
- Repository-wide in-memory indexing with explicit COMPLETE/PARTIAL/FAILED outcomes.
- FILE-to-MODULE structural evidence and a deterministic merged semantic graph.
- Conservative internal module imports with explicit unresolved/ambiguous decisions and LIKELY evidence.
- Static body-owned call-site observations, explicit unresolved/ambiguous decisions and site evidence.
- Conservative lexical, direct same-class and import-assisted CALLS with LIKELY confidence.
- Static FastAPI/Flask/Express route observations with explicit handler uncertainty.
- API_ENDPOINT entities, registration proof and endpoint-to-handler EXPOSES traces.
- Precise Express route middleware, FastAPI decorator dependencies and Flask request hooks.
- Static same-file router prefixes/mounts, distinct local/effective endpoints and multi-site proof.
- Conservative Python/JS/TS TEST declarations and direct call-site TESTS evidence, without runtime coverage.
- Provenance-backed SQLAlchemy/Prisma operations and direct database-capability graph relationships.
- Evidence-preserving endpoint/database, direct test, caller and potential endpoint-impact queries.
- Deterministic structural retrieval with BM25 ranking, exact-symbol ladders and bounded one-hop graph context.
- Typed structured query intents, deterministic plans and conservative canonical entity selection.
- JSON-compatible evidence bundles that preserve stored relationships, confidence and truncation reasons.
- One programmatic `analyze_repository` entry point producing a snapshot aligned with the final graph.
- An installed `arctrellis` CLI with text and JSON output, explicit ambiguity reporting and stable exit codes.
- A loopback-only read-only HTTP API over the same evidence bundle contract, with no new dependency.
- Optional pinned lint/format/type tooling and a native import boundary regression.

Planned capabilities: a future frontend or product demonstration; source evidence inspection;
retrieval and evidence quality evaluation at repository scale.

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
Install the optional development tools and run the local quality gate:

```powershell
.venv\Scripts\python.exe -m pip install -e ".[dev]"
.venv\Scripts\python.exe -m ruff check src tests
.venv\Scripts\python.exe -m ruff format --check src tests
.venv\Scripts\python.exe -m mypy src/arctrellis
.venv\Scripts\python.exe -m compileall -q src
.venv\Scripts\python.exe -m pip check
```

Apply formatting with `.venv\Scripts\python.exe -m ruff format src tests`.
Ruff 0.16.10 uses E/F/I/UP/B/SIM rules and 120 columns; mypy 2.4.0 checks
`src/arctrellis` in strict mode without broad suppressions. Tests remain standard-library
unittest. These commands were verified locally on Python 3.13.14; no CI or
cross-platform validation is claimed. Configuration follows the
[Ruff configuration documentation](https://docs.astral.sh/ruff/configuration/) and
[mypy configuration documentation](https://mypy.readthedocs.io/en/stable/config_file.html).

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
parallel parsing or incremental cache. Repository indexing orchestrates this single-file
operation sequentially and releases each parse after extraction. Normalized syntax
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
with `test_` remain ordinary functions; entity extraction alone does not create endpoints.

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
semantics are unchanged. Repository indexing and conservative import resolution below
compose this single-file builder without changing its lexical contract.

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

Only semantic graph records, inventory, diagnostic counts, lightweight CallSite values and HTTP route observations survive per-file analysis.
ParsedSource, full source bytes and syntax trees are released after each helper returns.
Summary records are immutable; CodeGraph retains its existing mutable API, so completed
results should be treated as snapshots. This is not persistent indexing.

### Conservative internal imports

```python
from arctrellis.indexing import index_repository
from arctrellis.resolution import resolve_imports

index = index_repository("path/to/local/repository")
resolved = resolve_imports(index)
print(resolved.resolved_count, resolved.unresolved_count, resolved.ambiguous_count)
```

`resolve_imports(index)` returns a new graph and explicit per-import decisions. Python uses path-based modules (including __init__ and an extra alias without a leading src directory) and relative imports. JS/TS resolves simple quoted relative imports, exact source extensions and unique extension/index candidates; static CommonJS uses the same policy. A unique static match adds a LIKELY/0.90 IMPORTS edge from the lexical importing scope to the target MODULE with import-site evidence. Lexical DEFINES stays PROVEN. Multiple candidates are AMBIGUOUS with no edge; unresolved imports stay visible.

Unsupported: Node packages/node_modules, package.json exports, tsconfig/webpack aliases, complete Python environment/sys.path or namespace behavior, general symbol/export resolution or dynamic import evaluation. The call stage below supports a limited imported-function lookup. Escaped and percent-encoded JS strings are not evaluated or resolved. Resolution does not re-read files or mutate the original index. IDs are still not repository-namespaced.


### Indexing and resolution safety

Indexing scans metadata and reads supported source bytes through the existing bounded,
revalidated parser. Extraction operates on owned bytes/syntax; graph assembly operates
on semantic values. Resolution operates only on the index catalog and import metadata,
with no source re-reads or external filesystem probes. No stage executes/imports target
source, invokes Node, installs target dependencies, runs scripts/hooks or target tests.
The existing concurrent-replacement/native-resource limitations still apply. A partial
index remains partial after resolution; resolving imports does not certify complete
repository understanding. Frozen summaries own mutable CodeGraph instances; callers
must treat completed graphs as snapshots or counts may become stale.

## Conservative static calls

```python
from arctrellis.calls import resolve_calls
from arctrellis.indexing import index_repository
from arctrellis.resolution import resolve_imports

index = index_repository("path/to/local/repository")
imports = resolve_imports(index)
calls = resolve_calls(index, imports)
print(index.call_site_count, calls.resolved_count, calls.unresolved_count, calls.ambiguous_count)
```

`extract_call_sites(parsed_source, extraction_result)` separately records invocation
observations without choosing targets or repeating entity extraction. Indexing calls it
while syntax is already live. `index.call_sites` is an immutable tuple ordered by path,
start byte, end byte and ID; file summaries expose `call_site_count`. Failed files have
no observations, partial files retain only safe surviving scopes. No source bytes or
syntax trees are retained repository-wide.

Observations represent plain NAME calls and simple non-computed member chains in
Python/JavaScript/TypeScript. A MODULE owns executable top-level calls; represented
FUNCTION/METHOD entities own only their bodies, including arrow expression bodies.
Nested declarations switch owners. Decorators, declaration defaults/annotations/bases,
class-body execution and unrepresented anonymous/object callable bodies are omitted.
JSX elements are not calls; ordinary executable JSX expression children may contain
calls. Constructor invocation is omitted while ordinary argument calls survive;
executable destructuring defaults/keys are inspected. Dynamic callees and optional
invocations are omitted without evaluation. Escaped ECMAScript callee spellings are
omitted; ordinary Unicode identifiers remain intact. Recovery subtrees are excluded.

`resolve_calls(index, imports)` copies the import graph and returns explicit decisions
in call-site order. NAME calls match uniquely visible FUNCTION declarations (including
represented callable variable bindings); recursion and nested lexical functions work.
Nearest represented import bindings block farther functions. Class namespaces
are skipped because they are not method closures; ECMAScript static-block locals
are not treated as bindings visible to ordinary methods. Duplicate functions, methods or
visible import bindings are AMBIGUOUS, with no tie-breaking and no CALLS edge.

Inside a direct METHOD, conventional Python `self`/`cls` and JS/TS `this` member calls
may target a uniquely named METHOD directly owned by that same CLASS. This includes
represented callable class fields. These names are syntactic heuristics, not runtime
receiver proof. Inherited methods and `super` are not resolved.

Import-assisted calls reuse resolved module records: Python from-import aliases and
direct module bindings, ES named/aliased functions and namespace members, and static
CommonJS namespace members. Only directly module-owned FUNCTION targets are eligible.
Type-only imports never produce runtime call edges. Default-import calls, callable
CommonJS exports and unaliased dotted-module binding guesses remain unresolved.
Longer member chains remain observable but unresolved. General export/re-export and
symbol visibility semantics are not modeled; matching declarations is a static heuristic.

Every emitted relationship is caller -> CALLS -> callable and retains invocation-site
Evidence with all six exact coordinates. Analysis methods distinguish lexical,
same-class, imported-symbol and imported-module-member resolution by language family.
Confidence is always LIKELY: **0.85 lexical/same-class**, **0.75 import-assisted**.
No Phase 1.7 CALLS edge is PROVEN. Separate invocation sites remain separate edges.
Unknown and ambiguous targets produce records without speculative graph edges.

**This is a conservative static call graph subset, not a complete call graph.**
Assignment/parameter shadowing and runtime rebinding are not tracked; the current
confidence labels do not make those cases runtime guarantees. Arbitrary dynamic
dispatch, inheritance, constructor targets, callbacks, higher-order targets, function
values beyond represented bindings, object methods, dependency injection,
framework-generated calls, monkey patching, reflection and full alias/dataflow
analysis are intentionally unsupported. IDs use versioned canonical JSON and UUID5;
they reproduce a revision and are neither edit-stable nor repository-namespaced.

Call resolution revalidates snapshot identity/proof consistency and never reopens
sources, reruns imports, executes target code or mutates input graphs. Indexing's
existing source/resource/stable-tree limitations remain. Existing graph paths retain
CALLS Evidence; traversal does not elevate static confidence to runtime proof.

## Static HTTP framework endpoints

```python
from arctrellis.calls import resolve_calls
from arctrellis.frameworks import resolve_http_endpoints
from arctrellis.indexing import index_repository
from arctrellis.resolution import resolve_imports

index = index_repository("path/to/local/repository")
imports = resolve_imports(index)
calls = resolve_calls(index, imports)
http = resolve_http_endpoints(index, imports, calls)
print(http.observation_count, http.endpoint_count, http.resolved_handler_count)
```

`extract_framework_observations(parsed_source, extraction_result)` records syntax
while indexing already owns the parse tree. `index.route_observations` is a frozen,
hashable observation tuple ordered by relative path/start byte/end byte/ID; file
summaries expose `route_observation_count`. These values retain constructor/import
provenance, handler references and owned coordinates, without source bytes or trees.
No entity extraction is repeated. Typed extraction failures discard that file's
semantic observations and remain explicit FAILED outcomes; partial files retain
only unaffected declarations. Unsupported route syntax does not change file
completeness, which describes parsing/extraction rather than framework coverage.

Supported initial adapters:

- **FastAPI:** direct module `from fastapi import FastAPI/APIRouter` bindings,
  including constructor aliases, followed by simple instance assignments. Direct
  get/post/put/patch/delete/options/head decorators associate represented functions
  or class methods, including async handlers. APIRouter paths are explicitly local;
  static constructor prefixes and simple same-file include_router mounting are composed by the framework-flow stage.
- **Flask:** direct module Flask constructor imports/aliases and app assignments,
  with `@app.route` using a static literal path and optional literal list/tuple/set
  of methods. The adapter default is GET. Explicit methods are normalized/deduplicated;
  implicit HEAD/OPTIONS are never expanded. Convenience verb decorators and Blueprint
  composition are outside this adapter.
- **Express:** direct default ES import or simple CommonJS require of "express",
  followed by a simple module-level app or express.Router initialization. Direct
  module registrations support get/post/put/patch/delete/options/head. One-argument
  app.get is a settings accessor, not a registration. Only the final argument is
  the handler reference; earlier arguments are counted during endpoint extraction and classified separately by the pre-handler stage.

Supported paths are slash-prefixed, unescaped single/double quoted strings.
Interpolation, escaped strings, concatenation, templates and variables are not
interpreted. Invalid duplicate/path arguments and Python argument splats remain
unsupported. Constructors, imports and receivers must have direct static provenance;
visible reassignment, context/pattern captures, wildcard imports, shadowed require
and known internal framework-name modules cannot prove an endpoint. This establishes
source-level canonical package/constructor provenance, not installed package identity
or a guarantee of actual runtime registration. Arbitrary runtime mutation remains
outside the analysis model.

Resolution records distinguish RESOLVED, UNRESOLVED, AMBIGUOUS and UNSUPPORTED.
Each static HTTP method creates an API_ENDPOINT named `POST /payments`, with qualified
name `path::http:POST:/payments@start_byte` and parent MODULE. Duplicate registration
sites remain distinct. Dynamic/unsupported path or methods create no endpoint;
a proven static registration with an unresolved/ambiguous handler retains its endpoint
and DEFINES evidence, with **no EXPOSES edge**. Handler counts refer to observations;
a multi-method observation expands into several endpoints and edges.

MODULE -> DEFINES -> API_ENDPOINT is PROVEN/1.0 with registration evidence.
API_ENDPOINT -> EXPOSES -> handler points in the direction needed for tracing:
Python decorator association is PROVEN/1.0; unique Express module handlers are
LIKELY/0.85 and import-assisted handlers LIKELY/0.75. Express imported references
reuse existing module decisions and require a directly exported FUNCTION for named,
aliased, namespace or require-member lookup. Type-only, default-callable and general
CommonJS export assignment/re-export semantics are not resolved. Explicit handler
rebinding and block-only local declarations stay unresolved. Anonymous inline callbacks
have no canonical handler entity and are never fabricated.

Every new edge retains the registration/decorator SourceLocation and all six exact
coordinates. Evidence methods distinguish route declarations and handler associations.
Endpoint/proof/observation IDs use versioned canonical JSON and UUID5; they reproduce
identical input but are not edit-stable or repository-namespaced. Existing graph paths
can follow endpoint -> EXPOSES -> handler -> CALLS -> callee with both proofs intact.

Resolution copies the completed call graph, preserves all prior evidence and validates
matching snapshots. It performs no source reads, framework imports, constructor or
decorator execution, Node invocation, dependency installation or environment evaluation.
Endpoint resolution adds no framework CALLS or APPLIES_MIDDLEWARE relationships; the separate framework-flow stage adds pre-handler edges.

Deferred: api_route, module-namespace constructor imports, application factories,
nested/conditional Express registration, cross-file/recursive router composition,
Flask Blueprints, global Express app.use middleware and route chains, dynamic
routes, runtime introspection and frameworks beyond these three adapters.

Local reproducible verification:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests/frameworks -t . -v
.venv\Scripts\python.exe -m tests.frameworks.smoke
```

## Static framework pre-handler semantics

`resolve_framework_flow(index, imports, calls, endpoints)` returns an independent graph
and explicit resolved/unresolved/ambiguous/unsupported pre-handler decisions.
Indexing retains lightweight observations, never source bytes or trees.

- Express: direct route arguments before the final handler; simple module functions,
  named/aliased imports and namespace members. Declared argument order is retained.
- FastAPI: decorator `dependencies=[Depends(auth)]` or a tuple, requiring direct
  `fastapi.Depends` from-import provenance (aliases supported). Class-scoped decorators, parameter injection,
  factories and arbitrary dependency trees are deferred.
- Flask: direct module `@app.before_request` functions apply only to the exact same
  recognized app binding. Declaration order is per file/app, not global runtime order.

`API_ENDPOINT APPLIES_MIDDLEWARE FUNCTION` reuses canonical declarations. Evidence
retains `semantic_kind=route_middleware|dependency|request_hook`, `order_index` and
exact reference coordinates. Dependencies are not ASGI middleware; request hooks
are not WSGI middleware. Express/FastAPI associations are LIKELY/0.85 locally or
LIKELY/0.75 import-assisted. Exact Flask same-app hook association is PROVEN/1.0.
Unknown/ambiguous/unsupported targets receive no edge. No synthetic middleware-to-handler
CALLS are created. Global Express use and Flask other hooks/Blueprints remain deferred.

## Static router path composition

The final `resolve_framework_flow(index, imports, calls, endpoints)` stage captures
same-file constructor and mount provenance from observations retained during indexing:

- FastAPI: a static `APIRouter(prefix="/users")`, plus direct
  `app.include_router(router, prefix="/api")` or an absent include prefix.
  Constructor imports may be aliased. Only route declarations preceding the include
  site participate in this conservative subset; framework-version lifecycle behavior
  is not emulated. Nonempty FastAPI prefixes ending in `/` are unsupported, matching
  the [APIRouter prefix contract](https://fastapi.tiangolo.com/reference/apirouter/).
- Express: proven `express.Router()` and direct two-argument
  `app.use("/api", router)`. Normal functions, middleware factories, dynamic mount
  paths and additional mount arguments do not produce effective endpoints.
- Cross-file router variables and nested mount chains are deferred. Nested/cyclic
  FastAPI includes receive unsupported decisions; the implementation never recurses.

Local endpoints remain unchanged. Changed composed paths create separate entities
with `path_completeness=effective`, `local_endpoint_id`, constructor/prefix/mount
observation IDs and `composition_scope=application|router`. Mounted effective endpoints
belong to the mounting app's MODULE. Prefix-only endpoints describe router configuration,
not proof of a publicly deployed path. Unchanged paths retain the local fact without
creating a duplicate effective entity. Separate mount sites remain distinct even if
paths match. Unsupported mounts preserve local endpoints and explicit decisions.

`join_http_paths(prefix, route)` removes boundary slashes only:
`"/api/" + "/users" -> "/api/users"`, `"/api" + "/" -> "/api/"`,
`"" + "/users" -> "/users"`. The route must begin with `/`; the prefix may be
empty. Trailing route slashes, internal spelling and path parameters are preserved;
there is no URL decoding or filesystem normalization. Adapter composition declines
local paths beginning `//` rather than normalizing them into effective claims.

Effective DEFINES, EXPOSES and APPLIES_MIDDLEWARE edges retain original route/reference
Evidence and add constructor, prefix and mount proof records. Original handler and
pre-handler confidence is inherited unchanged. No middleware-to-handler CALLS or
full runtime middleware-order guarantee is introduced. Resolution uses retained
observations and existing imports/entities; it does not reread or execute sources.
Result tuples are immutable; their independently owned CodeGraph follows the existing
mutable graph API and should be treated as a completed snapshot.

Verified local commands:

```powershell
.venv\Scripts\python.exe -m unittest tests.frameworks.test_flow -q
.venv\Scripts\python.exe -m unittest tests.frameworks.test_composition -q
.venv\Scripts\python.exe -m tests.frameworks.flow_smoke
```

## Static test semantics

`arctrellis.test_semantics.analyze_tests(index, imports, calls, base_graph=flow.graph)` adds TEST identities
and direct TESTS evidence to a fresh graph. Omit base_graph to use the call graph. Indexing retains lightweight
TestObservation values while syntax is available. Python module test_ functions and methods under Test* classes
qualify; arbitrary nested helpers and production-class test_ methods do not. Decorators are retained, not evaluated.
Unittest inheritance recognition is deferred. JS/TS supports direct test/it with nonempty unpadded unescaped quoted
names and inline arrow/function callbacks, at module scope or direct describe suite scope. Framework identity remains
unknown_js_test_api. Dynamic/template names, member/optional APIs, skip/each/todo and arbitrary scopes are omitted.

TEST entities preserve Python declaration IDs in metadata without replacing FUNCTION/METHOD. Anonymous callbacks
use TEST execution ownership, never fabricated FUNCTION identities. Callback/suite local binding contradictions
conservatively omit affected calls. Direct resolved CALLS yield TESTS to non-test FUNCTION/METHOD targets,
LIKELY/0.85, with actual invocation Evidence and the underlying CALLS ID. Unresolved/ambiguous calls yield no edge.
There are no transitive TESTS or endpoint coverage claims. Static test relationships are **not runtime coverage**,
proof of passing tests, CI execution, or assertion quality. Existing call-resolution runtime binding limitations remain.

Run `.venv\Scripts\python.exe -m unittest tests.test_semantics.test_analysis -q` and
`.venv\Scripts\python.exe -m tests.test_semantics.smoke` for contracts and measured Python/JS evidence.

## Database-operation foundation

`arctrellis.database` exports `DatabaseOperationKind`, `DatabaseOperationObservation`,
`make_database_operation_observation`, and `DatabaseAnalysisResult`. Categories are READ, WRITE, DELETE,
TRANSACTION and UNKNOWN; insert/update/upsert distinctions belong in future adapter metadata.
The owner-validating factory accepts a canonical MODULE/FUNCTION/METHOD and an operation SyntaxSpan,
checks language/path/byte/point containment, then retains only owner ID/kind and owned coordinates.
Observations include operation name, extensible lowercase provider identifier (`unknown` is available),
optional logical target name, immutable string metadata and a computed versioned UUID5 ID.
Direct record construction validates structure, not source truth or owner existence; adapters should use the factory.
Result constructors require deterministic ordering/unique IDs; `from_observations` sorts an immutable tuple.
Counts by operation kind/provider include only nonzero observed categories.

A standalone SQLAlchemy static extractor is available (Phase 2.1A). This model does not classify arbitrary `execute()` calls.
No TABLE/MODEL/DATABASE entities, connections, credentials, SQL parsing or query execution are introduced.
Indexing captures supported SQLAlchemy/Prisma observations during its existing parse lifetime.
`materialize_database_graph(index, base_graph=tests.graph)` produces a new database-enriched graph;
omit base_graph to preserve only the index graph. No source is reread during materialization.

Run `.venv\Scripts\python.exe -m unittest tests.database.test_foundation -q` and
`.venv\Scripts\python.exe -m tests.database.smoke`. The latter analyzes temporary mixed Python/TS source and prints measured evidence paths without executing it.

Callback binding exclusions include shorthand destructuring in local declarations/parameters/suites and
named callback function self-bindings; affected calls do not resolve to unrelated module functions.

## SQLAlchemy static operations

`extract_sqlalchemy_operations(parsed_source, extraction_result)` consumes existing normalized syntax.
Direct `from sqlalchemy.orm import Session` (including import aliases) plus a unique preceding direct
assignment `db = Session(engine)` establishes source-level provenance. Calls use canonical execution
owners and conservative whole-scope write/parameter/import exclusions. Repository callers can block
known internal package collisions through `blocked_providers`. No installed SQLAlchemy identity is proven.

Supported: get (READ/read_capable); execute of directly imported sqlalchemy select/insert/update/delete
(READ/WRITE/WRITE/DELETE, statement_execution); add/add_all and delete (staged_mutation intent);
flush/commit/rollback (TRANSACTION/transaction_control); other execute arguments (UNKNOWN).
Targets are source identifiers, never verified mapped models or tables. get can use an identity map;
staged mutations and transaction controls do not prove database writes. Graph eligibility is restricted by effect stage as described below.
Context managers, AsyncSession, sessionmaker, typed parameters, aliases, comprehensions and complete
control/dataflow are deferred. Visible rebinding anywhere in a scope excludes provenance, even before the rebind.
Run `.venv\Scripts\python.exe -m unittest tests.database.test_sqlalchemy -q`.

## Prisma static operations

`extract_prisma_operations(parsed_source, extraction_result)` supports direct named/aliased PrismaClient
imports from `@prisma/client` followed by a unique direct `new` binding in JS/TS. Supported reads:
findUnique/findUniqueOrThrow/findFirst/findFirstOrThrow/findMany/count/aggregate/groupBy; writes:
create/createMany/update/updateMany/upsert; deletes: delete/deleteMany; transaction: $transaction.
Accessor names are Prisma source accessors, not physical table names. Requests are not runtime execution,
await/commit/success or row-change proof. Raw queries, dynamic/computed/optional access, aliases, CommonJS,
client extensions/custom paths, schema and anonymous transaction callback reasoning are omitted.
Catch/with bodies are deferred; named function self-bindings and visible local/rebound clients reject provenance.
Run `.venv\Scripts\python.exe -m unittest tests.database.test_prisma -q`.

Explicit root-name mutations anywhere in the file (including another function) and TS enum/namespace
bindings invalidate ORM provenance conservatively. Unrelated same-spelled locals can therefore reduce recall;
this is not complete interprocedural mutation or alias analysis.

## Evidence-backed database graphs

`arctrellis.database` exports `extract_database_operations`, provider-specific extractors,
`materialize_database_graph` and `DatabaseGraphResult`. Operations become deterministic
DATABASE_OPERATION site entities named provider:target.method@byte (target omitted if unknown),
qualified as path::database:name. parent_id records MODULE/FUNCTION/METHOD execution ownership;
no lexical DEFINES edge is fabricated for an expression.

Owner READS_DATABASE operation means a recognized read-capable source operation. Owner WRITES_DATABASE
operation means a recognized direct write/delete-capable source request or statement. Both are LIKELY/0.85,
with actual invocation Evidence, exact coordinates, provider/method/effect metadata and UUID5 identities.
Recognition confidence and category confidence do not establish runtime execution certainty.
SQLAlchemy staged add/add_all/delete, transactions and UNKNOWN retain nodes without read/write edges;
commit/flush never imply pending rows changed. get can avoid SQL through the identity map. Prisma calls
need not be awaited to be observed, and neither promise completion nor transaction outcome is inferred.

DatabaseGraphResult retains ordered observations/entities/relationships and operation/provider counts,
unmaterialized/staged/unlinked counts. The frozen result owns a separate mutable CodeGraph; treat it as
a completed snapshot. Existing graph traversal preserves original EXPOSES/CALLS/database Evidence along
endpoint-to-database paths. It does not materialize new transitive edges or imply runtime reachability.

Known conventional root/src package collisions block provider recognition, including failed source files.
Source-free snapshot validation checks canonical owner/call/import witnesses, effect/method consistency and
nested statement invocation proof. It is structural validation of extractor output, not authentication of
arbitrary fabricated metadata or runtime package identity. No second parse or source read occurs.

Limits: static subset only; no schema/table resolution, SQL parsing, connections, implicit flush effects,
complete session/dataflow/aliases, arbitrary client alias resolution, query results or transaction outcomes.
Catch/with/comprehension bodies and unrepresented anonymous callbacks are deliberately omitted.
No Mongoose or other new ORM adapters are included. Phase 2.2 queries are not implemented.


## Structural Query API

ArcTrellis provides a deterministic static structural query engine over existing analysis graphs.
Queries do not parse or reopen source, rerun analysis, execute targets or mutate the graph.
Run analysis explicitly first; `graph` below is the completed database-enriched `CodeGraph`.

```python
from arctrellis.query import (
    AnalysisSummary,
    find_callers,
    find_direct_tests_for_symbol,
    find_potentially_affected_endpoints,
    get_direct_database_operations,
    list_direct_database_callers,
    list_endpoints,
    trace_callable_to_database,
    trace_endpoint_to_database,
)

# Use actual counts from the RepositoryIndexResult belonging to this revision.
context = AnalysisSummary(index.complete_file_count, index.partial_file_count, index.failed_file_count)
endpoints = list_endpoints(graph, http_method="POST")
for endpoint in endpoints.entities:  # registration IDs remain distinct
    trace = trace_endpoint_to_database(
        graph, endpoint.id, operation_kinds=frozenset(("write", "delete")),
        max_depth=12, max_paths=25, max_expansions=10000,
        analysis_completeness=context.completeness,
    )
    print(trace.status.value, trace.truncated, trace.analysis_completeness.value)
    payload = trace.to_dict()  # directly JSON-serializable primitive values
    for path in trace.paths:
        print(path.entity_ids, path.relationship_ids, path.weakest_edge_score)

# Symbol IDs below must refer to existing FUNCTION/METHOD records.
direct = get_direct_database_operations(graph, callable_id)
reachable = trace_callable_to_database(graph, callable_id)
database_owners = list_direct_database_callers(graph)
tests = find_direct_tests_for_symbol(graph, callable_id)
direct_callers = find_callers(graph, callable_id)
all_callers = find_callers(graph, callable_id, transitive=True)
impact = find_potentially_affected_endpoints(graph, callable_id)
```

Endpoint traces enforce `EXPOSES -> CALLS* -> (READS_DATABASE | WRITES_DATABASE)`;
callable traces enforce `CALLS* -> database edge`. Zero CALLS is valid. DELETE is selected
from operation metadata although its relationship is WRITES_DATABASE. Staged SQLAlchemy
mutations and transaction-only observations have no capability edge and cannot become write paths.
These are statically supported potential paths to read/write/delete-capable operations;
they never establish execution, successful SQL, changed rows or committed transactions.
IMPORTS, DEFINES, TESTS and APPLIES_MIDDLEWARE cannot substitute for invocation edges.

Each frozen EvidencePath contains original entities and relationships, with exact Evidence IDs,
locations, methods and metadata (including retained byte coordinates). Continuity and graph membership
are checked. Parallel evidence sites retain separate paths and path IDs. Results contain no graph,
source bytes or parser objects. Concurrent external graph mutation is unsupported.

Path order is hop count, ordered relationship IDs, then entity IDs. Search enumerates bounded simple
paths, stopping cycles without discarding independent parallel proofs; results are bounded discovered
paths, not a claim of globally shortest or exhaustive runtime paths. The confidence class is the lowest
supporting edge class and the numeric summary is the minimum edge score. If any score is absent the
summary stays unknown. Scores are not calibrated probabilities and are never multiplied.

Traversal defaults are depth12, paths25 and10000 inspected adjacency records, all positive non-boolean
integers. Depth counts all edges including terminal EXPOSES/database edges. Every inspected adjacency
record consumes the budget, even a rejected kind or cycle. Depth cuts, an extra path beyond the cap,
or exhausted examination budget report explicit truncation reasons. Truncation is conservative:
unexplored branches may never reach a terminal. Public graph APIs eagerly allocate adjacency/sorted
snapshot tuples; these allocations and sorting are outside the examination budget. No global cache exists.

`NO_KNOWN_PATH` means no supported static path was found within these constraints. It does not prove
runtime absence, including when analysis completeness is complete. Graph-only queries report unknown
completeness; pass the actual lightweight summary state to preserve complete/partial/failed context.
The caller associates this summary with the same graph revision; file completeness is not semantic exhaustiveness.
Unknown IDs, unsupported source kinds, invalid limits and relevant graph corruption raise distinct QueryError
subclasses. Missing evidence remains empty rather than being invented.

Direct database queries do not follow CALLS. `list_direct_database_callers` returns one-hop paths for
FUNCTION/METHOD owners (source_entity_id=None); group the first entity ID to obtain unique owners.
Direct operation lookup also permits MODULE owners, matching materialization. Global inventories default
to1000 matches/paths and10000 examined records. Direct TESTS lookup means direct static test evidence,
never runtime coverage or HTTP-client testing; no match does not mean a function is untested.

Caller queries use incoming CALLS only and include FUNCTION/METHOD callers, omitting MODULE/TEST owners.
Impact uses reverse CALLS* then reverse EXPOSES. Returned paths preserve original forward edge order
(endpoint/caller -> changed/target symbol) and explicitly mark traversal direction reverse. Candidates
are potential structural dependencies, never guaranteed breakage. Middleware impact is deferred.

Endpoint inventory filters exact `http_method`, `framework` and `route_path` metadata. `scope="local"`
selects router-local facts, `"declared"` selects application-declared routes, `"effective"` selects all
composed paths, and `"application"` selects effective application mounts only. Effective router prefixes
alone do not prove application exposure. None includes all facts; duplicate paths/registrations stay separate.
No query establishes public deployment or runtime availability.

This is not yet natural-language search, a runtime trace, complete test coverage, a vulnerability analyzer,
a full semantic program slicer, a complete call graph, a persistence/query service or an LLM explanation layer.

Reproduce the static golden evaluation and measured mixed-language smoke locally:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests/query -t . -q
.venv\Scripts\python.exe -m tests.query.smoke
```

## Structural Retrieval (Phase 2.3)

`arctrellis.retrieval` ranks canonical entities that the existing analysis pipeline already
produced. Retrieval never scans, parses, opens or executes repository source: it consumes a
completed `CodeGraph` and nothing else.

```python
from arctrellis.query import AnalysisSummary, trace_endpoint_to_database
from arctrellis.retrieval import (
    SearchFilters,
    build_search_index,
    search_endpoints,
    search_tests,
)

context = AnalysisSummary(index.complete_file_count, index.partial_file_count, index.failed_file_count)
snapshot = build_search_index(graph, analysis_completeness=context.completeness)

results = search_symbols(snapshot, "payment creation", top_k=10, include_graph_context=True)
for hit in results.hits:
    print(hit.entity_id, hit.relevance_score, hit.match_basis.value, hit.matched_fields)

# Retrieved IDs are canonical IDs and can feed the existing structural query engine.
trace = trace_endpoint_to_database(graph, results.hits[0].entity_id, analysis_completeness=context.completeness)

endpoints = search_endpoints(snapshot, "payments", filters=SearchFilters(frameworks=frozenset({"fastapi"})))
tests = search_tests(snapshot, "payment")
```

`build_search_index(graph)` reads `graph.entities()` exactly once and `graph.relationships()`
at most once, so the eager snapshot allocation that public graph APIs perform is paid once per
build rather than once per candidate or hit. The index is a build-time snapshot: later graph
mutation is not observed, and `snapshot_id` is a content digest of the documents, not a
repository revision or commit.

### What is indexed

Structural metadata only, never source text. Each canonical `CodeEntity` becomes exactly one
immutable `SearchDocument` identified by its canonical entity ID. Indexable fields are entity
name, qualified name, repository-relative path, entity kind, language, parent ID, and an
explicit allowlist of eighteen existing metadata keys (`framework`, `http_method`, `route_path`,
`path_completeness`, `registration_kind`, `composition_scope`, `provider`, `operation_kind`,
`operation_name`, `target_name`, `target_basis`, `effect_stage`, `import_form`, `module`,
`imported_name`, `alias`, `binding`, `is_type_only`). Every other metadata key is excluded by
omission. Signatures are never indexed, so string literals inside them cannot become retrieval
content. Projected values are stored truncated to 512 characters and 32 tokens; the canonical
entity keeps its full value. Entities without a `SourceLocation` report no path and no line
numbers.

### Normalization and tokenization

Text is NFKC-normalized while preserving case, split on ASCII case and digit boundaries and on
every non-alphanumeric character, then case folded per token. `PaymentService`,
`payment_service`, `payment-service`, `payment.service`, `payment/service` and `paymentService`
all produce `payment`, `service`. Acronyms keep their capitals: `HTTPServer` produces `http`,
`server`. Non-ASCII letter runs stay whole. Everything is data; no query text is decoded,
resolved, executed or treated as an instruction.

### Ranking

BM25 with `k1=1.2`, `b=0.75` and smoothed IDF, computed over field-weighted term frequencies
(`name` 3.0 down to `entity_kind`/`language`/`repository_relative_path` 0.5, all exact binary
fractions). A fixed exact-match ladder applies only the strongest satisfied rule: qualified
name 8.0, entity name 6.0, canonical `METHOD path` 5.0, alphanumeric-equivalent name 3.0,
name prefix 0.5. Every hit exposes `bm25_score`, `exact_match_boost`, `prefix_boost`,
`graph_context_boost` and `relevance_score`, which is exactly their sum. Results sort by
relevance, then exact priority, then canonical entity ID. A BM25 score is a lexical relevance
score: it is never a probability, a confidence, a semantic-similarity measure or a statement
about runtime behavior.

### Typed filters

`SearchFilters` supports entity kinds, languages, repository-relative path prefixes, HTTP
method, framework, database provider, database operation kind and endpoint path completeness.
Filters match canonical attributes and allowlisted field values only; an absent value never
satisfies a filter. Filters constrain output, so `top_k` always applies to eligible results.
`search_endpoints`, `search_tests` and `search_database_operations` delegate to the single
ranking engine with a merged kind restriction.

### Graph-aware one-hop context

`include_graph_context=True` is an explicit opt-in. Only relationships that the indexed snapshot
actually stores are used: `EXPOSES`, `CALLS`, `TESTS`, `READS_DATABASE`, `WRITES_DATABASE` and
`APPLIES_MIDDLEWARE`. `DEFINES`, `IMPORTS`, `CONTAINS`, `INHERITS` and `USES` are never context
and never stand in for a call. At most one hop is examined; a neighbor of a neighbor is never
visited. A context hit carries the stored relationship ID, kind, direction, confidence,
confidence score and original Evidence, and is reported as `match_basis=graph_neighbor` without
claiming it contains the query terms. The boost is `min(1.0, seed_coverage * edge_weight)` using
the maximum over supporting relationships, never a sum, so degree cannot inflate it; middleware
is a pre-handler association weighted below invocation. Relationship confidence is reported
separately and is never multiplied into relevance.

### Limits, truncation and empty input

Maximum query length 512 characters, maximum 24 query tokens, `top_k` default 25 and maximum
100, default posting budget 50000 examined records, default graph seed budget 25, default
neighbor budget 16 per seed, build-time neighbor cap 16 per entity and direction. Blank,
whitespace-only, token-free, over-long and over-tokenized queries are rejected with
`InvalidSearchQueryError`. Every inspected posting record consumes the budget, including
records later rejected by a filter. `truncated` reports budget-driven incompleteness with a
stable reason from `posting_budget`, `graph_seed_budget`, `graph_neighbor_budget`; `top_k`
limiting is reported separately through `eligible_candidate_count`. Candidate counts are exact
only when `truncated` is False. Index construction is bounded only by the canonical entity count;
no memory cap is claimed.

### Evaluation

`evaluate_retrieval(index, judgments, k=5)` measures three modes against independently written
relevance judgments: an exact/substring baseline, BM25, and BM25 with graph context. Metrics are
Recall@K, Precision@K, MRR@K and HitRate@K, macro-averaged over evaluated queries. Queries whose
judgments resolve to nothing are skipped and reported, never averaged as zero. Measured at K=5
over 19 evaluated queries: baseline 0.8246/0.3158/0.7298, BM25 0.8860/0.3474/0.8070,
BM25+graph 0.8860/0.3211/0.8553. Graph context improves MRR and lowers precision; `test payment`
regresses against the baseline in both BM25 modes; `payment refund endpoint` is missed by all
three modes because no document contains all of its tokens. These are lexical measurements on a
small synthetic corpus, not semantic retrieval quality.

### What Phase 2.3 does not provide

- Full source-code text search. Only structural metadata is indexed.
- Semantic embeddings, vector search or any similarity model.
- Natural-language question understanding or query planning.
- LLM-generated explanations. `match_reasons` and `explain_hit` are structured and deterministic.
- Runtime execution traces, runtime coverage or behavioral claims.
- Complete graph coverage; a result never proves repository completeness.
- Exhaustive search under a truncated budget.
- Persistent or incremental indexes; a snapshot never refreshes itself.
- Any web API, CLI, storage engine, worker or background process.

Verified local commands:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests/retrieval -t . -q
.venv\Scripts\python.exe -m tests.retrieval.smoke
```

## Structured Query Orchestration (Phase 2.4)

`arctrellis.orchestration` connects the retrieval engine to the structural query engine through
an explicit, validated intent contract. The governing rule is that **a lexical score is not entity
identity**: retrieval finds candidate entities, selection decides which canonical entity the caller
meant, the existing query engine executes, and the bundle reports exactly what repository evidence
supports.

```python
from arctrellis.orchestration import QueryIntent, QueryRequest, analyze_repository, run_query

snapshot = analyze_repository(r"C:\Projects\SampleRepo")

# 1. Search. Ranked candidates only; nothing is selected for you.
found = run_query(snapshot, QueryRequest(intent=QueryIntent.SEARCH_ENTITIES, search_text="list payments"))
for candidate in found.candidate_entities:
    print(candidate.entity_id, candidate.entity_kind.value, candidate.name, candidate.relevance_score)

# 2. Choose one canonical ID explicitly, then trace that exact entity.
bundle = run_query(
    snapshot,
    QueryRequest(intent=QueryIntent.TRACE_ENDPOINT_TO_DATABASE, entity_id=found.candidate_entities[0].entity_id),
)
for path in bundle.paths:
    for relationship in path.relationships:
        print(relationship.relationship_kind, relationship.source_entity_id, "->", relationship.target_entity_id)
```

`analyze_repository(root)` runs the real analysis stages in their verified dependency order
(`index_repository`, `resolve_imports`, `resolve_calls`, `resolve_http_endpoints`,
`resolve_framework_flow`, `analyze_tests`, `materialize_database_graph`) and then builds the
retrieval index from that final graph, so lexical search and structural queries can never be
served from two different repository states. Snapshot construction asserts that the retrieval
documents correspond one-to-one with the final graph entities. No `ParsedSource`, syntax tree or
source byte is retained, and no stage executes, imports or installs target code.

### Structured intents

Nine intents exist, each backed by an existing query function. No intent has a placeholder
backend.

| Intent | Source entity | Backend |
|---|---|---|
| `SEARCH_ENTITIES` | none | `search_symbols` |
| `LIST_ENDPOINTS` | none | `list_endpoints` |
| `LIST_DATABASE_CALLERS` | none | `list_direct_database_callers` |
| `TRACE_ENDPOINT_TO_DATABASE` | `API_ENDPOINT` | `trace_endpoint_to_database` |
| `TRACE_CALLABLE_TO_DATABASE` | `FUNCTION`/`METHOD` | `trace_callable_to_database` |
| `DIRECT_DATABASE_OPERATIONS` | `FUNCTION`/`METHOD`/`MODULE` | `get_direct_database_operations` |
| `FIND_DIRECT_TESTS` | `FUNCTION`/`METHOD` | `find_direct_tests_for_symbol` |
| `FIND_CALLERS` | `FUNCTION`/`METHOD` | `find_callers` |
| `FIND_AFFECTED_ENDPOINTS` | `FUNCTION`/`METHOD` | `find_potentially_affected_endpoints` |

There is no natural-language inference. `search_text` is retrieval input only: it can never imply
an architectural intent. Selector forms are mutually exclusive: exactly one of `entity_id`,
`qualified_name`, `http_method` + `route_path`, or `search_text` may be present. An option the
chosen intent cannot consume is rejected with `UnsupportedIntentError` rather than silently
ignored, so `top_k` on a trace or `include_graph_context` on a query fails loudly. `top_k` and
`max_examined_postings` are retrieval budgets; `max_paths`, `max_depth` and `max_expansions` are
traversal budgets. All limits must be positive non-boolean integers.

### Plans

`build_plan(request)` returns an immutable `QueryPlan` holding only data: the step vocabulary
(`SEARCH_CANDIDATES`, `SELECT_CANONICAL_ENTITY`, `EXECUTE_STRUCTURAL_QUERY`, `ASSEMBLE_EVIDENCE`),
the required source entity kinds, the name of the structural query to run, the limits and the
planned output type. A plan holds no callable, no graph, no timestamp and no random value, so
equal requests always produce equal plans.

### Conservative entity selection

| Selector | Outcome |
|---|---|
| Exact canonical entity ID | `RESOLVED` if the entity exists and its kind satisfies the intent, `NOT_FOUND` if absent, `INVALID` if the kind is wrong |
| Exact qualified name | `RESOLVED` when exactly one eligible entity matches, `AMBIGUOUS` with the full candidate set otherwise |
| Exact HTTP method and route | `RESOLVED` when exactly one registration matches, `AMBIGUOUS` otherwise |
| `search_text` | `CANDIDATES`: ranked candidates and **no** selected entity, so no structural query can run |

`entity_kind`, `language`, `path_prefix`, `framework` and `endpoint_scope` are constraints that
narrow your own selector; they never choose for you. Duplicate endpoint registrations and a
`PaymentService` CLASS versus `PaymentService` IMPORT are first-class expected outcomes reported
as ambiguity, never resolved by rank. An exact-ID selection scans the snapshot's exact-name and
route lookups, which is exhaustive, so a resolved selection never claims truncation.

### Evidence bundles

`run_query(snapshot, request)` returns an `EvidenceBundle` with `schema_version=1` and a status of
`SEARCH_RESULTS`, `EVIDENCE_PATHS`, `INVENTORY`, `NO_KNOWN_PATH`, `AMBIGUOUS_SOURCE`,
`NOT_FOUND_SOURCE` or `INVALID_SOURCE`. Every relationship in a bundle is the original stored
record with its original ID, kind, confidence classification, numeric score and original
`Evidence` IDs, source locations and analysis methods. Confidence is summarized with the existing
weakest-edge contract and is never multiplied into a probability. Truncation reasons and analysis
completeness propagate unchanged, and `limitations` states the boundaries explicitly, including
that `no_known_path_is_not_proof_of_absence`.

`bundle.to_dict()` produces JSON primitives only, with no timestamp, absolute path, source byte,
declaration signature or traceback, so equal requests over equal snapshots serialize identically.
Entity projection deliberately omits declaration signatures and all metadata outside a nine-key
allowlist, because a signature is source text.

### What Phase 2.4 does not provide

- Natural-language intent inference from a sentence.
- Automatic selection of the top-ranked lexical hit for a structural query.
- Reranking of stored graph confidence by retrieval relevance.
- Conversion of `IMPORTS`, `DEFINES`, `TESTS` or `APPLIES_MIDDLEWARE` into execution.
- Probabilities of runtime behavior.
- Caching or persistence of an analysis snapshot across processes.

Verified local commands:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests/orchestration -t . -q
```

## Offline CLI (Phase 2.5)

The CLI is a thin adapter over the orchestration API. It implements no analysis and no query
logic: every subcommand builds the same validated `QueryRequest` and calls the same `run_query`,
so the command line cannot answer differently from the Python API.

```powershell
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\arctrellis.exe analyze C:\Projects\SampleRepo
.venv\Scripts\arctrellis.exe search C:\Projects\SampleRepo "list payments"
.venv\Scripts\arctrellis.exe query C:\Projects\SampleRepo --intent trace-endpoint-to-database --method POST --path /payments
```

If `arctrellis.exe` is not on PATH, the equivalent form is:

```powershell
.venv\Scripts\python.exe -c "import sys; from arctrellis.cli.main import main; sys.exit(main(sys.argv[1:]))" analyze C:\Projects\SampleRepo
```

### Commands

| Command | Intent | Purpose |
|---|---|---|
| `analyze ROOT` | none | measured counts, completeness and snapshot identity |
| `search ROOT TEXT` | `search-entities` | ranked candidates; selects nothing |
| `query ROOT --intent I [selector]` | any | one structured intent and its evidence bundle |
| `endpoints ROOT` | `list-endpoints` | endpoint registration inventory |
| `database ROOT` | `list-database-callers` | direct database-operation owners |
| `trace ROOT` | `trace-endpoint-to-database` | endpoint to database trace |
| `impact ROOT` | `find-affected-endpoints` | candidate endpoints for a callable |
| `tests ROOT` | `find-direct-tests` | direct static tests for a callable |

Exactly one selector form may be supplied: `--entity-id`, `--qualified-name`, `--method` with
`--path`, or `TEXT` for `search-entities`. `--limit` becomes `top_k` for a retrieval intent and
`max_paths` for a traversal intent, matching the library's own option contract, so an impossible
combination is rejected by the same rule the API applies.

### Ambiguity

An ambiguous selector prints every candidate and exits 3. It never selects rank 1:

```text
$ arctrellis query . --intent trace-endpoint-to-database --method POST --path /payments
status: AMBIGUOUS_SOURCE (ambiguous source selection; no entity selected)
selection: ambiguous (2 endpoint registrations share this method and path; supply an exact entity ID)
  1. d7315561-...  API_ENDPOINT POST /payments [js/app.js] basis=EXACT_ENDPOINT_METHOD_PATH
  2. ed8c6277-...  API_ENDPOINT POST /payments [app.py] basis=EXACT_ENDPOINT_METHOD_PATH
$ echo $LASTEXITCODE
3
```

### Output modes

`--json` writes exactly one JSON document to stdout and nothing else. The payload is the bundle's
own `to_dict()` unchanged, so it matches the public contract, and diagnostics go to stderr. Text
mode prints a stable report:

```text
status: EVIDENCE_PATHS (structural evidence paths found)
selection: resolved (resolved by unique endpoint method and path)
selected entity: API_ENDPOINT POST /payments [app.py:5]
evidence paths: 1
path 1 of 3 hop(s), direction=forward, weakest-edge confidence=LIKELY (0.75)
  API_ENDPOINT POST /payments [app.py:5]
  EXPOSES #1: confidence=PROVEN score=1.0
    evidence fastapi_decorated_handler app.py:5
  FUNCTION createPaymentRoute [app.py:6]
  CALLS #2: confidence=LIKELY score=0.75
    evidence python_imported_symbol_call_resolution app.py:7
  FUNCTION createPayment [payments.py:4]
  WRITES_DATABASE #3: confidence=LIKELY score=0.85
    evidence sqlalchemy_execute_insert payments.py:5
  DATABASE_OPERATION sqlalchemy:Payment.execute@134 [payments.py:5]
```

### Exit codes

| Code | Meaning |
|---|---|
| 0 | success |
| 2 | invalid CLI arguments, or a well-formed request that could not be resolved |
| 3 | ambiguous entity selection |
| 4 | analysis failure |
| 5 | unsupported operation or internal error |

### Safety and limitations

The target root is validated by the existing safe discovery logic. The CLI never executes,
imports or installs target code, never evaluates target configuration, never connects to a
database, never makes an outbound network request and never requires or inspects a Git
repository. No traceback is ever printed. Analysis is rebuilt in memory per invocation: there is
no cache, index file or daemon, and no timing benchmark is claimed.

Verified local commands:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests/cli -t . -q
.venv\Scripts\python.exe -m tests.cli.smoke
```

## Local Read-Only HTTP API (Phase 2.6)

`arctrellis.api` exposes the existing analysis over five read-only routes. It adds no runtime
dependency and implements no analysis or query logic: it parses a bounded JSON payload into the
same validated `QueryRequest` the CLI builds, calls the same `run_query`, and returns the bundle's
own serialization.

```powershell
.venv\Scripts\arctrellis.exe serve C:\Projects\SampleRepo --port 8756
```

```text
GET  /api/v1/health      readiness, snapshot identity, analysis completeness
GET  /api/v1/summary     measured counts and completeness
GET  /api/v1/endpoints   endpoint registration inventory (method, path, framework, scope filters)
POST /api/v1/search      bounded lexical search returning ranked candidates
POST /api/v1/query       one structured intent returning the EvidenceBundle contract
```

```powershell
$body = @{ intent = 'trace-endpoint-to-database'; method = 'POST'; path = '/payments' } |
    ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8756/api/v1/query `
    -ContentType 'application/json' -Body $body
```

### Ambiguity over HTTP

A selector that matches more than one canonical entity returns **409** with the full bundle in the
response, so the client receives the candidates and the preserved evidence instead of a guessed
answer:

```json
{
  "error": "ambiguous_selection",
  "message": "2 endpoint registrations share this method and path; supply an exact entity ID",
  "bundle": { "selected_entity": null, "candidate_entities": [ ... ] }
}
```

### Status codes

| Code | Meaning |
|---|---|
| 200 | success, including an empty search result and a `NO_KNOWN_PATH` bundle |
| 400 | body is not a valid bounded JSON object, or a bad query-string filter |
| 404 | unknown route, or the selected entity does not exist |
| 405 | the path exists but not for this method |
| 409 | ambiguous or incompatible source selection |
| 413 | request body exceeds 65536 bytes |
| 415 | content type is not `application/json` |
| 422 | payload violates the request contract (unknown field, conflicting selectors, bad limit) |
| 501 | unsupported intent |

### Security controls

- The bind address is validated in code: only `127.0.0.1`, `::1` and the literal `localhost` are
  accepted. Any other address or hostname raises `UnsafeBindError` without a DNS lookup, and there
  is no configuration path that widens it.
- The repository root is supplied once at startup and is unreachable from any request. No route
  accepts a filesystem path, so no request can redirect the analysis.
- Request bodies are bounded at 64 KiB and an oversized `Content-Length` is refused before the
  body is read. Response sizes are bounded by the retrieval and traversal budgets.
- Unknown request fields and unknown query-string keys are rejected rather than ignored.
- No response contains a traceback, an absolute path, an environment value, a credential or target
  source text. `health` and `summary` never disclose the analyzed root.
- The listener suppresses client-disconnect noise instead of printing a traceback.
- **There is no authentication.** This service must never be exposed beyond loopback. No
  multi-tenancy, no uploads, no outbound requests, no deployment.

Verified local commands:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests/api -t . -q
.venv\Scripts\python.exe -m tests.api.smoke
```
