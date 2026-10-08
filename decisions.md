# Decisions

Append-only record of engineering decisions.

### D-001: Establish a src-layout package and standard-library test workflow
- Date / phase / commit: 2026-10-08, Phase 0.1, uncommitted
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
- Date / phase / commit: 2026-10-08, Phase 0.1, uncommitted
- Context: Future parsing and querying components require a common vocabulary without infrastructure dependencies.
- Decision: Create EntityKind, RelationshipKind and Confidence string enums and frozen, slotted SourceLocation, CodeEntity, Evidence and Relationship dataclasses. Export the seven types from arctrellis.core. IDs are validated caller-supplied strings. Relationships point from source to target and embed a tuple of Evidence records. Classification is mandatory; an optional finite confidence_score ranges from zero to one. Duplicate embedded evidence IDs are rejected.
- Why: The requested scope is representation and invariants, not discovery, graph integrity or proof verification. Embedded immutable records keep ownership simple. Caller-owned IDs avoid speculative cross-repository identity design.
- Alternatives considered: Random identifiers would not reproduce identity; deterministic identity generation needs repository context not yet defined; evidence references require a separate store; score-derived classifications impose unsupported calibration thresholds; runtime OBSERVED is outside scope.
- Consequences: Producers must provide reproducible IDs and adequate proof. Global uniqueness, endpoint existence and unresolved-target policy remain future graph concerns. UNRESOLVED can use an opaque caller-supplied target placeholder. Zero evidence is valid even for PROVEN; constructors do not certify truth.
- Files: src/arctrellis/core/models.py, src/arctrellis/core/__init__.py, tests/core/test_models.py, README.md, decisions.md, flow.md

### D-003: Validate raw portable paths and restrict metadata to immutable string pairs
- Date / phase / commit: 2026-10-08, Phase 0.1, uncommitted
- Context: Repository paths must work across operating systems without hiding invalid input; metadata must not undermine immutable records or future serialization.
- Decision: Store unmodified forward-slash relative strings, rejecting Windows anchors, backslashes, control characters, empty/dot/traversal segments and surrounding whitespace. Require integer, non-boolean inclusive line bounds. Store metadata as ordered tuples of unique string pairs. Validate nested record types, enum types, required strings, optional strings and snake_case evidence methods at construction; use TypeError for wrong types and ValueError for invalid values.
- Why: PurePosixPath normalizes dot and repeated separator segments before validation, losing the original invalid spelling. Strings and immutable tuples convert through dataclasses.asdict and JSON without a serializer framework.
- Alternatives considered: PurePosixPath storage silently normalizes input; mutable dictionaries undermine freezing; read-only dictionary proxies complicate hashing and asdict; recursive metadata freezing adds unnecessary complexity; arbitrary method strings allow unclear method identifiers.
- Consequences: Adapters must provide canonical paths and flatten metadata to strings. Metadata order participates in equality. Paths are syntax-validated only; filesystem existence, symlinks and source line counts are not checked.
- Files: src/arctrellis/core/models.py, tests/core/test_models.py, README.md, decisions.md, flow.md

### D-004: Finalize commit references without rewriting history
- Date / phase / commit: 2026-10-08, Phase 0.1, uncommitted
- Context: The required documentation must reference real commits, but a commit cannot contain its own final hash.
- Decision: Commit verified implementation and documentation together, then replace their uncommitted markers with that implementation hash in a separate documentation finalization commit. The finalization commit does not need to embed its own hash.
- Why: This follows the explicit safe procedure and preserves truthful history. No implementation occurred in the earlier process-launch failure.
- Alternatives considered: Amending commits changes the hash again; inventing a hash or deleting decision history breaks traceability.
- Consequences: Implementation records reference the implementation commit; the later commit records reference finalization and the verified handoff.
- Files: decisions.md, flow.md, handoff.md
