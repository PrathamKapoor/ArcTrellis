# ArcTrellis

**Prove how your codebase works.**

ArcTrellis is intended to become an evidence-first repository intelligence system:
static analysis will identify code entities and relationships, and explanations
will point to verifiable source evidence.

The analysis engine establishes what can be proven. The explanation layer
explains that evidence. Structural truth must remain independent of an explanation
provider.

## Current status

Early implementation: Phase 1.0, safe local repository discovery and language
detection. There is no source parser, symbol extraction, inferred call relationship,
GitHub cloning, persistence, embedding retrieval, LLM integration,
API or frontend.

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

Planned capabilities: source parsing and repository acquisition; lexical, semantic and structural symbol
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

The domain has no runtime dependencies. Setuptools is only the packaging backend.
No formatter, linter or type checker is configured in this phase.

## Architecture and invariants

`src/arctrellis/core/models.py` defines the domain; `arctrellis.core` is the public
import boundary. Future parsers translate language-specific syntax into these
records. Future storage and query layers consume the same records.

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
not a guarantee of safe later file reads; future parsers must revalidate their inputs.
Work is linear in visited entries plus sorting file and omission records; there is
no concurrent or incremental scanner.

See [decisions.md](decisions.md), [flow.md](flow.md) and [handoff.md](handoff.md)
for rationale, call order and continuation state.
