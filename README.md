# ArcTrellis

**Prove how your codebase works.**

ArcTrellis is intended to become an evidence-first repository intelligence system:
static analysis will identify code entities and relationships, and explanations
will point to verifiable source evidence.

The analysis engine establishes what can be proven. The explanation layer
explains that evidence. Structural truth must remain independent of an explanation
provider.

## Current status

Early implementation: Phase 0.1, repository foundation and canonical domain model.
There is no source analyzer, repository ingestion, graph container, API or UI yet.

Current capabilities:

- Language-independent entity and directional relationship kinds.
- Immutable, validated source locations, entities, evidence and relationships.
- Explicit static confidence classifications and optional bounded numeric scores.
- A public `arctrellis.core` API with standard-library unit tests.

Planned capabilities: repository ingestion; lexical, semantic and structural symbol
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
an opaque placeholder target ID until a later graph policy defines unresolved
references. No numeric classification thresholds are assumed.

Paths are unchanged relative strings using `/`, with inclusive 1-based line ranges.
Absolute paths, drive-relative paths, traversal and noncanonical separators are
rejected. Files are not opened and line counts are not checked.

All records are frozen and hashable. Metadata is an ordered tuple of unique
string-key/string-value pairs; nested containers and mutable dictionaries are
rejected. Tuple order participates in equality. Use `dataclasses.asdict()` for a
primitive representation and `json.dumps()` for JSON; enums are string enums and
tuples encode as JSON arrays. This is a conversion boundary, not a versioned wire
format or persistence implementation.

See [decisions.md](decisions.md), [flow.md](flow.md) and [handoff.md](handoff.md)
for rationale, call order and continuation state.
