# System Flow

## 1. Package installation and imports

Input: a local checkout and Python >=3.13. Packaging reads pyproject.toml.

```text
python -m pip install -e .                 pyproject.toml; install the src package
 └─ setuptools.build_meta                 build backend; discover arctrellis under src
from arctrellis.core import ...            src/arctrellis/core/__init__.py; stable public API
 └─ import .models                        src/arctrellis/core/models.py; load domain types
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
Global IDs, target existence and proof adequacy are not checked in this phase.

## 4. Unit tests and primitive conversion

Input: installed package and test cases under tests/core/test_models.py.

```text
python -m unittest discover -s tests -v    tests/__init__.py and tests/core/__init__.py; discover tests
 └─ unittest.TestCase test methods         tests/core/test_models.py; exercise public constructors
     ├─ public domain constructors        src/arctrellis/core/models.py; check invariants
     └─ dataclasses.asdict() → json.dumps() primitive conversion; validate JSON compatibility
```

Output: test results on stdout/stderr and process exit status. A failing assertion
fails the suite. There is no production serialization or database format yet.

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
