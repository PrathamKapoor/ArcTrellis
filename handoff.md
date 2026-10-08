# ArcTrellis Handoff

## 1. Current Phase

Phase 1.9: middleware/pre-handler semantics (1.9A) and static router composition (1.9B).
Status: complete. Implementation and required verification are complete.
Phase 2.0 has not started.

## 2. Work Completed

Express route arguments before the final handler become ordered route_middleware observations.
FastAPI module-function decorator lists/tuples of direct imported Depends calls become dependency
observations. Flask direct before_request decorators become request_hook observations scoped to
an exact proven app binding. These roles share APPLIES_MIDDLEWARE edges while retaining precise
semantic_kind/order/occurrence Evidence. Existing canonical FUNCTION entities are reused;
no synthetic middleware-to-handler CALLS or wrapper entities are created.

Static same-file APIRouter prefixes/include_router and Express Router/app.use mounts derive
changed effective paths while retaining local endpoints. Each effective edge retains the local
proof and separate constructor/prefix/mount Evidence. Handlers and pre-handler confidence are
preserved. Duplicate mounts remain distinct. Unsupported/ambiguous/unresolved decisions stay
explicit. Prefix-only paths describe router configuration rather than public deployment.

## 3. Files Changed

- src/arctrellis/frameworks/flow_models.py: precise immutable observations/result and counts.
- src/arctrellis/frameworks/flow_extraction.py: pre-handler syntax and provenance extraction.
- src/arctrellis/frameworks/flow.py: snapshot validation and independent pre-handler graph.
- src/arctrellis/frameworks/composition_models.py: router configuration/mount observations/outcomes.
- src/arctrellis/frameworks/composition_extraction.py: direct static prefix/mount extraction.
- src/arctrellis/frameworks/composition.py: path helper/effective identity/multi-source proof.
- src/arctrellis/frameworks/__init__.py: public framework-flow APIs.
- src/arctrellis/frameworks/models.py: shared owned-coordinate containment helper.
- src/arctrellis/frameworks/extraction.py: reusable complete reference visibility helper.
- src/arctrellis/frameworks/resolution.py: reusable handler indexes/reference lookup and snapshot fields.
- src/arctrellis/indexing/models.py: immutable observation/count validation and provenance boundaries.
- src/arctrellis/indexing/repository.py: observations extracted before parse lifetime ends.
- src/arctrellis/calls/resolution.py and src/arctrellis/resolution/imports.py: preserve/validate new tuples.
- tests/frameworks/test_flow.py: twenty pre-handler contract/regression tests.
- tests/frameworks/test_composition.py: twenty-four composition contract/regression tests.
- tests/frameworks/flow_smoke.py: mixed static flow/proof and seven negative cases.
- README.md, decisions.md, flow.md, handoff.md: actual semantics, decisions, flow and continuation state.

## 4. Current Architecture / State

index_repository -> per source parse_discovered_file -> extract_entities -> extract_call_sites
-> extract_framework_observations -> extract_pre_handler_observations -> extract_router_observations
-> release ParsedSource. RepositoryIndexResult retains lightweight tuples, graph and bounded summaries;
no ParsedSource, source bytes or SyntaxNode trees are retained. FAILED files contribute none;
PARTIAL files retain unaffected observations.

resolve_imports -> resolve_calls -> resolve_http_endpoints -> resolve_framework_flow.
The final stage validates matching snapshots, resolves pre-handlers using existing indexes,
adds evidence-backed APPLIES_MIDDLEWARE, then compose_router_paths adds effective endpoints.
Each stage owns a separate CodeGraph. Frozen result shells contain an ordinary mutable graph;
callers should treat completed graphs as snapshots.

## 5. Decisions Made

D-090: precise categories, normalization, observation lifetime and confidence.
D-091: complete visibility helper and actual graph/test boundary correction.
D-092: class dependency deferral and exact constructor/Depends provenance.
D-093: green committed pre-handler gate.
D-094: same-file composition, local/effective identity/ownership and multi-site proof.
D-095: graph API corrections and rejection of unsafe composition path boundaries.
D-096: repeatable static flow smoke and explicit supported subset.
D-097: final quality/audit verification and twelve-section handoff.

## 6. Requirements and Constraints

Local only. No remotes, pushes, uploads, publication or GitHub APIs. All commits author/committer
PrathamKapoor <prathamkapoor027@gmail.com>. No forbidden paper/research/tex files, secrets or attribution.
No target execution/import/Node/framework installation or environment/config evaluation.
No dependencies, parser pins, quality configuration or core graph/domain contracts changed.
No Phase 2.0 implementation is authorized within this session.

## 7. Testing and Verification

Verified project interpreter: .venv\Scripts\python.exe, Python 3.13.14.
Stage A gate ran20 pre-handler tests,52 framework tests and347 total tests OK/skipped7 before commits
94cdfd6dc4e789f2bc315f2fb82a05ac98f37ec9 and f9f9336.
Final checks:

- .venv\Scripts\python.exe -m unittest tests.frameworks.test_flow -q:20 tests OK.
- .venv\Scripts\python.exe -m unittest tests.frameworks.test_composition -q:24 tests OK.
- .venv\Scripts\python.exe -m unittest discover -s tests/frameworks -t . -q:76 tests OK.
- .venv\Scripts\python.exe -m unittest discover -s tests -q:371 tests OK, skipped7.
- .venv\Scripts\python.exe -m ruff check src tests:All checks passed.
- .venv\Scripts\python.exe -m ruff format --check src tests:97 files already formatted.
- .venv\Scripts\python.exe -m mypy src/arctrellis:55 source files, no issues.
- .venv\Scripts\python.exe -m compileall -q src:exit0.
- .venv\Scripts\python.exe -m pip check:No broken requirements found.
- .venv\Scripts\python.exe -m unittest tests.test_architecture -q:2 tests OK.
- .venv\Scripts\python.exe -m tests.frameworks.flow_smoke:3 route observations,3 local endpoints,
  2 effective endpoints,3 pre-handler observations/resolved,0 unresolved/ambiguous,5 APPLIES_MIDDLEWARE,
  5 EXPOSES; deterministic=True. All seven negative cases rejected.
- Public API import commands for core/graph/ingestion/parsing/extraction/indexing/imports/calls/frameworks
  passed in a fresh project interpreter.
- Source search for tree_sitter/eval/exec/subprocess/os.system/importlib found only native imports and
  fixed grammar loading in parsing. No execution APIs in framework-flow code.
- git diff --check passed; pyproject.toml diff empty; git remote -v empty.
- git config user.name/email and git var author/committer identities matched required identity.
- git ls-files paper/* research/* *.tex returned empty. Attribution pattern search returned no matches
  (rg exit1 is expected for no matches).

Seven existing skips: six Windows symlink privilege cases (WinError1314), one absent os.mkfifo case.
Other operating systems, installed framework runtime behavior and public deployment were not tested.
Initial missing APIs, helper NameError, stale fixture injection, graph keyword mistakes, strict type errors
and lint/format findings were corrected. Class/provenance and path-boundary regressions failed before
fixes, then passed. See D-091/D-092/D-095 for verified causes and exact regression methods.

## 8. Known Issues / Risks

No remaining confirmed important defect found in the permitted subset. Dynamic rebinding, monkey
patching, framework installation/version/configuration and public execution behavior are unverified.
IDs remain revision-deterministic, not edit-stable or repository-namespaced. Result graphs are mutable.
Order metadata describes declared route-list order or per-file/app hook order, never a global runtime
execution sequence. FastAPI composition includes only declarations preceding a mount; later declarations
are deliberately omitted without emulating framework-version lifecycle differences.

## 9. Unfinished Work

No required implementation remains in Phase 1.9A/B. Optional cross-file router variables
and recursive composition remain intentionally deferred. Implementation commits:
94cdfd6dc4e789f2bc315f2fb82a05ac98f37ec9 (pre-handlers),
ee5b1d626a142a410ab5f9e01a201bae8faa511c (composition). Current decision/table references
are finalized in the separate documentation commit.

## 10. Next Subphase

Phase 2.0 — Test semantics and database-operation foundation, in a future authorized session.
Stop after finalizing Phase 1.9; do not begin this future phase now.

## 11. Critical Context

Express/FastAPI pre-handlers: LIKELY0.85 local,0.75 imported. Flask exact same-app before_request:
PROVEN1.0. Role/order reside in Evidence metadata because core Relationship has no metadata field.
Effective DEFINES is PROVEN1.0 with multiple source facts; copied EXPOSES/APPLIES_MIDDLEWARE keep
original confidence. Local and effective endpoints remain distinguishable via path_completeness;
composition_scope distinguishes application exposure from unmounted router configuration.

join_http_paths trims prefix trailing and route leading boundary slashes, preserves route trailing
slash/parameters and never URL-decodes or uses OS paths. FastAPI nonempty trailing-slash prefixes and
local double-leading-slash paths are excluded by the adapter; ordinary helper trailing joins remain valid.
FastAPI parameter/class dependencies, Flask Blueprints/other hooks, Express global middleware/factories,
route chains, app factories, cross-file/nested mounts and complete runtime ordering remain deferred.

## 12. Agent Instructions

Read all root docs before work. Preserve append-only decisions and finalize only new commit-reference
fields/table cells. Inspect actual code and immutable snapshot contracts. Add regression tests for
verified defects; retain strict typing/lint and evidence confidence. Keep target repositories static,
local and unexecuted. Never alter remotes, push, publish or add forbidden files/attribution.
