# ArcTrellis Handoff

## 1. Current Phase

Phase 1 — Repository Understanding. Subphase 1.7 — Static call-site extraction and conservative call resolution.
Objective: retain body-owned invocation observations during indexing and infer evidence-backed CALLS only for unique static candidates.
Status: complete. Phase 1.8 was not started.

## 2. Work Completed

- Added arctrellis.calls with immutable CallSite, CalleeKind, resolution records/status/result, typed errors and public extraction/resolution APIs.
- Calls are observations, not CodeEntity values. UUID5/versioned canonical JSON includes language, relative path, owner, callee kind/parts and byte endpoints.
- Body-aware iterative extraction matches existing declaration IDs through lexical parent/name/end and covering coordinates, rather than treating span containment as execution ownership.
- Functions, methods, arrow/function-expression bodies and executable module statements retain static NAME/non-computed member calls. Nested scopes switch owners.
- Decorators/defaults/annotations/bases, class execution, anonymous/object callable bodies, optional/computed/dynamic invocations and constructor invocation are omitted. Ordinary constructor arguments, destructuring defaults/keys and JSX expression children may contain independent calls.
- Repository indexing retains only lightweight CallSite tuples and per-file counts, never ParsedSource/source bytes/trees. Failed files contribute none; partial files retain safe surviving scopes.
- Resolution indexes functions/methods/import bindings once, uses existing import decisions, and returns a new graph. Nearest represented bindings block farther names; class namespaces are not enclosing method closures.
- Lexical FUNCTION and direct same-class self/cls/this METHOD matches are LIKELY/0.85. Imported function/module-member matches are LIKELY/0.75. No CALLS is PROVEN.
- Duplicate callable/binding witnesses are ambiguous; unknown targets unresolved; neither creates an edge. Separate sites retain separate relationship/evidence IDs.
- Evidence identifies the actual invocation and all six syntax coordinates. Existing shortest_path preserves CALLS proof along a -> b -> c.
- Corrected verified import initialization, escaped spelling, namespace visibility, omitted executable arguments/patterns, optional punctuation and snapshot-validation defects with failing regressions first.

## 3. Files Changed

- src/arctrellis/calls/__init__.py — deliberate public APIs and errors.
- src/arctrellis/calls/models.py — immutable observations/decisions, derived resolution counts.
- src/arctrellis/calls/ids.py — validated revision-deterministic UUID5 identity and proof keys.
- src/arctrellis/calls/errors.py — extraction/resolution boundary failures.
- src/arctrellis/calls/extraction.py — normalized body-only iterative invocation extraction.
- src/arctrellis/calls/resolution.py — indexed lexical/method/import matching and exact CALLS evidence.
- src/arctrellis/indexing/models.py — final default call tuple/count fields and owner/count/span validation.
- src/arctrellis/indexing/repository.py — extract calls during the existing per-file parse lifetime.
- src/arctrellis/resolution/imports.py — preserve call observations when revalidating the repository snapshot.
- tests/calls/__init__.py — package-aware test discovery.
- tests/calls/fixtures.py — six-file mixed-language integration fixture.
- tests/calls/test_models.py — immutability, coordinates, identity and canonical input contracts.
- tests/calls/test_extraction.py — ownership, omissions, recovery, deep traversal and grammar boundary regressions.
- tests/calls/test_indexing.py — counts, memory, public import order and non-execution contracts.
- tests/calls/test_resolution.py — all resolution families, uncertainty, proof, traversal and deterministic integration.
- README.md — current static call subset, public usage, confidence and limitations.
- decisions.md — D-068 through D-079.
- flow.md — extended indexing lifecycle, call extraction/resolution and current session changes.
- handoff.md — current verified continuation state.

## 4. Current Architecture / State

scan_repository -> parse_discovered_file -> extract_entities -> extract_call_sites -> lexical/file graph assembly -> RepositoryIndexResult.
resolve_imports(index) -> ImportResolutionResult; resolve_calls(index, imports) -> CallResolutionResult.
Graphs retain PROVEN/1.0 DEFINES, LIKELY/0.90 IMPORTS and LIKELY/0.85 or 0.75 CALLS.
Call resolution uses retained semantic values only, verifies matching snapshots/import proof, and never reads source again.
File/module identities and entity/relationship counts remain compatible. Call-site counts are separate from graph edges.
Frozen summary shells own mutable CodeGraph instances; consumers must treat completed results as snapshots.
Repository identity/persistence remains deferred; IDs are not repository-namespaced or edit-stable.

## 5. Decisions Made

- D-068 — observations and versioned call identity separate from targets.
- D-069 — body-only normalized execution ownership and conservative omissions.
- D-070 — lightweight repository observations/counts without syntax retention.
- D-071 — indexed conservative resolution, uncertainty and confidence-specific site evidence.
- D-072 — eliminate eager snapshot-import cycles; verify fresh public import orders.
- D-073 — omit unsupported escaped identifier spellings without aborting indexing.
- D-074 — respect Python class visibility and executable binding/constructor argument boundaries.
- D-075 — revalidate coordinate containment and import decision/proof consistency.
- D-076 — canonical ID validation and integrated depth/security/determinism hardening.
- D-077 — exclude ECMAScript static-block locals from method lookup.
- D-078 — distinguish optional punctuation from comments/type literals.
- D-079 — verified handoff and bounded stop before frameworks.

## 6. Requirements and Constraints

Local only: no remotes, push, uploads, GitHub APIs or publication.
Every commit must use PrathamKapoor <prathamkapoor027@gmail.com> as author and committer; verify identity before each commit.
No attribution trailers, paper/, research/ or .tex commits.
No target code execution/import/require/Node/dependencies/scripts/hooks/tests/config evaluation.
No new runtime dependencies or parser pin changes; pyproject.toml is unchanged.
No inheritance, constructor targets, callbacks, higher-order dispatch, full dataflow or framework semantics.
Keep decisions append-only; finalize only new commit fields/table cells, never descriptive occurrences of uncommitted.
Keep strict mypy and Ruff rules unchanged.

## 7. Testing and Verification

Verified environment: C:/Projects/ArcTrellis, Python 3.13.14, required Git identity, no remotes.
Commands run with .venv/Scripts/python.exe:

- -m unittest discover -s tests/calls -t . -v — 34 tests OK.
- -m unittest discover -s tests -q — 295 tests OK, skipped=7; baseline was 261 OK/skipped=7.
- -m ruff check src tests — All checks passed.
- -m ruff format --check src tests — 77 files already formatted.
- -m mypy src/arctrellis — Success, no issues in 43 source files.
- -m compileall -q src — exit 0.
- -m pip check — No broken requirements found.
- -m unittest tests.test_architecture -v — 2 tests OK; native imports remain parsing-only.
- -c public calls/indexing/resolution imports — public APIs OK; fresh import-order regression also passed.
- stdin temporary mixed_sources pipeline — supported6/complete6/partial0/failed0; call_sites6/resolved4/unresolved1/ambiguous1/CALLS4; deterministic rerun true.

Real smoke proof: service.py::create CALLS util.py::validate, service.py:5-5,
python_imported_symbol_call_resolution, LIKELY, 0.75.
Also service.py::create CALLS service.py::helper at line 6 with python_lexical_call_resolution/0.85,
service.ts::submit CALLS util.ts::audit, and app.js::run CALLS helper.js::sanitize.

Source searches found native imports only in parsing; execution-mechanism search found only the existing fixed installed-grammar loader.
git diff -- pyproject.toml returned no changes. Normal git diff --check passed (Git warned about expected LF-to-CRLF normalization).

Initial expected test failures: missing calls package/API/counts. Verified regression failures: circular public import,
escaped callee ValueError, class namespace/static-block false edges, omitted arguments/patterns, optional comment omission,
out-of-owner coordinates, stale import proof and noncanonical helper AttributeError; all corrected and regression-tested.
Initial lint reported formatting/import/line issues; formatter/autofix and exact fixture-string splits corrected them.
Initial strict typing reported one missing list annotation; corrected explicitly without suppression.

Seven existing platform skips: six symlink tests require Windows link privilege (WinError 1314), FIFO test requires unavailable os.mkfifo.
Junction tests passed. Other operating systems, real hostile filesystem races, runtime call behavior, and exhaustive language semantics were not tested.

## 8. Known Issues / Risks

Confirmed unresolved implementation defects: none found in the bounded reviews/gates.
Confirmed limitations: assignment/parameter shadowing and runtime rebinding/export semantics are not modeled;
self/cls/this conventions and static candidates remain heuristics. No complete call graph is claimed.
Class/static-block environments without represented execution scopes may remain unresolved.
Possible risks: unfamiliar dynamic/configured repositories can differ from static candidates; existing filesystem race/native resource limitations remain.
Graphs are mutable snapshot objects; unauthorized caller mutation can stale summaries, detected at supported validation boundaries.

## 9. Unfinished Work

No required Phase 1.7 implementation remains. Intentional omissions are not unresolved defects.
Local commit references are finalized separately after the feature commit exists; no history rewrite.

## 10. Next Subphase

Phase 1.8 — Framework semantic adapters and HTTP entry-point extraction.
Do not begin it without the next authorized session. Likely initial candidates: FastAPI, Flask and Express.

## 11. Critical Context

CALLS source is actual MODULE/FUNCTION/METHOD owner; target is a unique eligible FUNCTION/METHOD.
Evidence points to invocation, not target declaration. No PROVEN CALLS; lexical/method 0.85, imported 0.75.
Imports must already be resolved and match preserved proof. Type-only/default callable imports do not resolve calls.
Python unaliased dotted module bindings and longer member chains remain unresolved.
Nearest import/function binding collisions remain ambiguous; candidate witness IDs may identify IMPORT bindings.
Class parentage is structural ownership, not a promise that class namespaces are closures.
Preserve parser pins: tree-sitter 0.25.2 and the existing compatible grammar versions.
The existing normalized parser, core graph traversal and ingestion safety behavior were not redesigned.

## 12. Agent Instructions

Read decisions.md, flow.md and this file completely before changing code. Verify current Git/Python state; do not trust historical summaries.
Preserve append-only decisions and current confidence/ownership/security boundaries. Write regression tests before verified bug fixes.
Run call tests, full suite, Ruff lint/format, strict mypy, compileall, pip check and architecture audit.
Never execute untrusted targets, reread sources during resolution, publish or add a remote.
Verify identity and forbidden/attribution audits before local commits. Finalize only new commit-reference fields.
Stop at the authorized phase boundary; the next work is framework entry-point semantics, not speculative dynamic dispatch.
