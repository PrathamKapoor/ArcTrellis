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
```

Output: importable in-memory domain types. Installation failures propagate from pip.
There is no service process, API, persistence or repository analyzer.

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

Input: installed package and test cases under tests/core/ and tests/graph/.

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
