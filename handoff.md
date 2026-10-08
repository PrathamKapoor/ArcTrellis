# ArcTrellis Handoff

## 1. Current Phase

Phase 1 — Repository Understanding. Subphase 1.8 — Framework semantic adapters and HTTP entry-point extraction.
Objective: recognize static FastAPI/Flask/Express route syntax and produce evidence-backed API_ENDPOINT/EXPOSES.
Status: complete implementation and verification. Phase 1.9 is not started.

## 2. Work Completed

- Added arctrellis.frameworks: frozen FrameworkBinding/HttpRouteObservation, handler decisions/status/result, deterministic IDs, typed errors, observation extraction and endpoint resolution.
- Constructor provenance uses direct canonical imports and unique preceding module-level assignments; receivers with visible writes, wildcard imports, class import shadows or shadowed require are not certified.
- FastAPI FastAPI/APIRouter from-import aliases and seven direct method decorators support ordinary/async functions and represented methods. Exact decorated wrapper matching prevents nested same-name handler collisions.
- Flask Flask aliases and route decorators support GET by default or static list/tuple/set methods; no implicit HEAD/OPTIONS expansion.
- Express default ES/CommonJS imports and simple app/Router bindings support seven direct module-level method registrations. One-argument get is a settings accessor; final argument is the handler. Earlier argument count is retained without middleware classification.
- Unescaped slash-prefixed quoted paths only. Dynamic paths, invalid duplicate/splat arguments and known internal framework-name collisions are unsupported. Router paths are local, never composed with prefixes/mounts.
- Indexing retains lightweight observations/counts while ParsedSource is already live; no full source/trees escape. Typed framework extraction failures are explicit FAILED outcomes with zero calls/routes; safe partial siblings survive.
- Resolution copies the completed call graph and preserves all previous proof. Same-module Express handlers and explicit exported imported functions use unique candidates; type-only/default callable/anonymous handlers stay unresolved.
- One API_ENDPOINT per static HTTP method; duplicate sites remain distinct. MODULE DEFINES endpoint is PROVEN/1.0. Python endpoint EXPOSES decorated handler is PROVEN/1.0; Express local/imported association is LIKELY/0.85 or 0.75.
- Unsupported declarations create no endpoint. A valid static declaration with unknown/ambiguous handler still creates its endpoint but no EXPOSES. No middleware or framework-generated CALLS edges are added.
- Existing shortest_path retains EXPOSES/CALLS proof in FastAPI and Express endpoint-to-callee traces. Full reruns reproduce observations, entities, decisions, relationships and evidence.

## 3. Files Changed

- src/arctrellis/frameworks/__init__.py — deliberate public models/errors/extraction/resolution API.
- src/arctrellis/frameworks/models.py — immutable syntax/provenance and explicit handler outcomes; containment validation.
- src/arctrellis/frameworks/ids.py — versioned canonical JSON/UUID5 observation/proof identity.
- src/arctrellis/frameworks/errors.py — explicit extraction and resolution invariant failures.
- src/arctrellis/frameworks/extraction.py — normalized static constructor/route recognition and conservative visibility guards.
- src/arctrellis/frameworks/resolution.py — snapshot/proof validation, indexed handler matching and endpoint graph assembly.
- src/arctrellis/indexing/models.py — final default route tuple/count fields and owner/import/coordinate/count validation.
- src/arctrellis/indexing/repository.py — extract observations before releasing each parse tree; bounded typed failure handling.
- src/arctrellis/resolution/imports.py — preserve observations when revalidating repository snapshots.
- src/arctrellis/calls/resolution.py — preserve observations during call snapshot validation; call behavior unchanged.
- tests/frameworks/__init__.py — package-aware discovery.
- tests/frameworks/test_endpoints.py — adapter coverage, false positives, uncertainty, recovery and regression cases.
- tests/frameworks/test_contracts.py — model/snapshot/memory/failure/import-order/determinism/trace contracts.
- tests/frameworks/fixtures.py — synthetic four-file mixed HTTP repository.
- tests/frameworks/smoke.py — reproducible static endpoint counts and evidence trace.
- README.md — supported framework patterns, public usage, confidence and security/coverage limitations.
- decisions.md — D-080 through D-089; historical prefix preserved.
- flow.md — extended indexing lifetime, observation/resolution call flow and session table.
- handoff.md — verified continuation state in twelve sections.

## 4. Current Architecture / State

scan_repository -> parse_discovered_file -> extract_entities -> extract_call_sites -> extract_framework_observations -> lexical/file graph assembly -> RepositoryIndexResult.
resolve_imports(index) -> ImportResolutionResult; resolve_calls(index, imports) -> CallResolutionResult;
resolve_http_endpoints(index, imports, calls) -> FrameworkAnalysisResult.
RepositoryIndexResult retains graph, inventory, summaries, immutable calls and immutable route observations.
Framework analysis returns a new graph with API_ENDPOINT entities and DEFINES/EXPOSES; existing DEFINES/IMPORTS/CALLS remain unchanged.
Handler counts count observations; methods may expand one observation into several endpoints/EXPOSES edges.
No source rereads, target runtime execution, framework installation or persistence.
IDs remain revision-deterministic, not edit-stable or repository-namespaced. Owned CodeGraph snapshots remain mutable by existing API.

## 5. Decisions Made

- D-080 — immutable route observations and provenance separate from endpoint/handler resolution.
- D-081 — simple framework constructors and static direct route syntax; explicit conservative omissions.
- D-082 — route observations/counts within the existing per-file parse lifetime.
- D-083 — endpoint naming, module ownership, deterministic registration proof and confidence-specific EXPOSES.
- D-084 — correct receiver writes, invalid arguments, module visibility and decorator/point containment.
- D-085 — model/lifetime/import-order/proof tests, explicit types and unchanged quality tooling.
- D-086 — internal framework-name collisions do not prove the external framework.
- D-087 — direct/wildcard/class/require import guards and exact decorated scope identity.
- D-088 — accurate public subset documentation and repeatable HTTP trace smoke.
- D-089 — actual final gate, audits, negative subcases and bounded handoff.

## 6. Requirements and Constraints

Local only: no remote changes, push, GitHub APIs, uploads or publication.
Every author/committer must be PrathamKapoor <prathamkapoor027@gmail.com>; verify before each commit; never global identity changes.
No attribution trailers, paper/, research/ or .tex commits.
Target repositories are untrusted: never execute/import/require their source, run Node, install dependencies, run scripts/hooks/tests or evaluate constructors/decorators/config/environment.
No new runtime dependencies or changed parser/tool pins. pyproject.toml is unchanged.
No middleware, APPLIES_MIDDLEWARE, mounted/prefix route composition, broader frameworks or future retrieval/storage/infrastructure.
Keep decisions append-only; finalize only new commit fields/table cells, never historical prose.
Keep strict mypy and existing Ruff rules without broad suppressions.

## 7. Testing and Verification

Verified environment: C:/Projects/ArcTrellis; Python 3.13.14; required Git identity; no remotes; clean initial tree.
Ruff 0.16.10 and mypy 2.4.0 were checked directly.
Commands use .venv/Scripts/python.exe:

- -m unittest discover -s tests/frameworks -t . -v — 32 tests OK; subsequent package-aware -q rerun also passed.
- -m unittest discover -s tests -q — 327 tests OK, skipped=7; baseline 295 OK/skipped=7.
- -m unittest discover -s tests -v with skip/result filtering — 327 OK/skipped=7 and actual reasons confirmed.
- -m ruff check src tests — All checks passed.
- -m ruff format --check src tests — 88 files already formatted.
- -m mypy src/arctrellis — Success, no issues in 49 source files.
- -m compileall -q src — exit 0.
- -m pip check — No broken requirements found.
- -m unittest tests.test_architecture -v — 2 tests OK; native imports remain parsing-only.
- -c public framework model/extraction/resolution imports — framework public API OK; fresh import-order tests also passed.
- -m tests.frameworks.smoke — supported4/complete4/partial0/failed0; observations6/endpoints7/resolved-handler4/unresolved1/ambiguous1/unsupported0/EXPOSES5; deterministic=True.
- Selected fake/rebinding/internal-name tests — 3 tests OK, including failed internal-name file and named/pattern capture subcases.

Real trace: POST /payments EXPOSES create_payment at fastapi_app.py:5-5,
fastapi_decorated_handler, PROVEN/1.0, bytes81..103/columns0..22;
create_payment CALLS validate_payment at line7-7,
python_lexical_call_resolution, LIKELY/0.85, bytes138..156/columns4..22.

Initial expected failure: ModuleNotFoundError for the absent framework package.
Reproduced/fixed defects: shadowed require, context/wildcard/class/conditional imports,
invalid/duplicate decorator arguments, Express settings getter/numeric arguments,
explicit handler rebinding/block-only targets, unrelated decorator association/point containment,
and valid nested same-name handler ValueError. All are covered by persistent regressions.
Initial strict typing errors were explicit list/tuple/local inference issues, fixed without suppression.
Initial lint errors were formatting/import/line issues, fixed using Ruff and exact fixture-string splits.
Two atomic patch attempts failed on already-formatted contexts and changed no files; inspected contexts were used to retry.

Source search found execution/native mechanisms only in parsing's fixed installed-grammar loader;
no target execution mechanism was introduced. git diff -- pyproject.toml is empty; normal diff check passed.
Six symlink tests skipped for Windows WinError1314; one FIFO test for absent os.mkfifo. Junction tests passed.
Other operating systems, real hostile filesystem races, installed framework runtime validity and exhaustive dynamic semantics were not tested.

## 8. Known Issues / Risks

Confirmed unresolved implementation defects: none found in the bounded reviews/gates.
Confirmed limitations: no final mounted router/Blueprint paths; no dynamic paths, middleware, runtime mutation or complete framework coverage.
Constructor provenance is source-level canonical import/assignment evidence, not verification of installed runtime package identity.
Express static handler inference remains LIKELY; general export/re-export, arbitrary assignment/dataflow and callback identity are not modeled.
Possible risks: unfamiliar runtime/configured repositories may behave differently; existing native resource and filesystem race limits remain.
Frozen summaries own mutable graphs; caller mutation can invalidate snapshot summaries, checked at supported resolver boundaries.

## 9. Unfinished Work

No required Phase 1.8 implementation remains. Local implementation/reference finalization follows the verified gate.
Intentional omissions are not unresolved defects. Phase 1.9 was not started.

## 10. Next Subphase

Phase 1.9 — Middleware semantics and framework flow enrichment, only in a later authorized session.
Potential work includes statically defensible dependencies/hooks/Express middleware, APPLIES_MIDDLEWARE and router mount/prefix composition.

## 11. Critical Context

EXPOSES direction is endpoint -> handler; CALLS remains actual caller -> callable.
DEFINES endpoint proof is registration-site PROVEN/1.0.
FastAPI/Flask decorator association is PROVEN/1.0; Express local/imported association LIKELY/0.85 or0.75.
Evidence points to the decorator/registration and retains six syntax coordinates.
Unsupported paths/methods/provenance produce no endpoint. Unknown/ambiguous handlers retain static endpoints but no EXPOSES.
No framework CALLS or APPLIES_MIDDLEWARE. Existing call confidence is never elevated.
Class imports and exact complete decorated spans matter for receiver/handler association.
Preserve parser pins and all previous ingestion/parsing/extraction/graph/call/import contracts.

## 12. Agent Instructions

Read decisions.md, flow.md and this handoff completely before changing code; verify actual environment/Git state.
Preserve append-only decision history and conservative provenance/confidence/security boundaries.
Reproduce bugs and add regressions; never guess handler, framework, mounted path or middleware semantics.
Run framework/full tests, Ruff lint/format, strict mypy, compileall, pip check, public import/isolation/security audits and smoke.
Keep sources/trees out of repository results and perform no source rereads in resolution.
Verify identities, forbidden paths and attribution before local commits; finalize current references only.
Do not publish, add remotes, push, execute targets or continue beyond the authorized phase.
