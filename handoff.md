# ArcTrellis Handoff

## 1. Current Phase

Phase 2.1A/B/C complete: bounded SQLAlchemy extraction, Prisma extraction and evidence-backed database
operation graphs. Final local commit/reference finalization pending. Phase 2.2 has not started.
Repository C:/Projects/ArcTrellis, Python3.13.14, required Git identity, no remotes.

## 2. Work Completed

SQLAlchemy: direct/aliased sqlalchemy.orm Session import and unique preceding direct constructor assignment;
get READ/read_capable; execute of imported select/insert/update/delete as READ/WRITE/WRITE/DELETE and
statement_execution. add/add_all/delete are staged intent; flush/commit/rollback transaction_control;
other execute UNKNOWN. Targets are source identifiers, never mapped models/tables. Statement provenance
retains exact nested canonical call ID/span plus import witness. No runtime SQLAlchemy imported.

Prisma: named/aliased PrismaClient import @prisma/client, unique preceding new assignment; JS/TS eight read
methods, five write methods, two delete methods and direct $transaction. Targets retain accessor spelling.
Requests do not establish await/completion/success/commit or changed rows. Raw queries are omitted.

Canonical call ownership is reused. Whole-scope writes/parameters/imports/self-bindings exclude provenance;
file-wide explicit mutation root names and enum/namespace names conservatively invalidate it. Catch/with/
comprehension bodies are omitted. Inventory blocks conventional root/src package-name collisions.

Repository indexing retains lightweight observations/counts during the existing parse lifetime. Snapshot
validators preserve/check the new fields. Source-free materialization produces deterministic operation
site entities and only eligible READS_DATABASE/WRITES_DATABASE relationships with LIKELY/0.85 invocation
Evidence. Staged/transaction/UNKNOWN nodes have no database edge. Python and TS endpoint traces verified.

## 3. Files Changed

- src/arctrellis/database/__init__.py: deliberate adapter/dispatcher/graph/result exports.
- src/arctrellis/database/models.py: accurate common-model module description; existing contract retained.
- src/arctrellis/database/syntax.py: temporary normalized binding indexes, scope/mutation exclusions.
- src/arctrellis/database/sqlalchemy.py: provenance-backed Session intent/statement observations.
- src/arctrellis/database/prisma.py: provenance-backed JS/TS client requests.
- src/arctrellis/database/extraction.py: language dispatcher and inventory collision guard.
- src/arctrellis/database/validation.py: source-free canonical owner/call/import/effect proof checks.
- src/arctrellis/database/graph.py: independent operation graph and DatabaseGraphResult/counts.
- src/arctrellis/indexing/models.py, repository.py: parse-lifetime observations/counts and validation.
- src/arctrellis/calls/resolution.py, src/arctrellis/resolution/imports.py,
  src/arctrellis/frameworks/resolution.py: preserve database fields in snapshot checks.
- tests/database/test_sqlalchemy.py, test_prisma.py: method/provenance/scope/recovery/identity subcases.
- tests/database/test_graph.py: mixed integration, evidence, snapshots, corruption, effects, lifecycle/negatives.
- tests/database/smoke.py: measured temporary Python/TS database traces and deterministic rerun.
- tests/test_architecture.py: absolute ORM import isolation audit.
- README.md, decisions.md, flow.md, handoff.md: accurate capabilities, records and continuation.

## 4. Current Architecture / State

index_repository -> scan_repository -> _blocked_providers -> _analyze_file -> parse_discovered_file
-> extract_entities -> extract_call_sites -> framework/pre-handler/router -> extract_test_observations
-> extract_database_operations -> lexical/file assembly -> FileIndexResult -> release ParsedSource.
RepositoryIndexResult retains immutable lightweight tuples only, with explicit COMPLETE/PARTIAL/FAILED.
resolve_imports -> resolve_calls -> resolve_http_endpoints -> resolve_framework_flow -> analyze_tests
-> materialize_database_graph(index, base_graph=tests.graph). All prior facts are preserved in new storage.
Omit base_graph for index-only enrichment. No second parse/read during database materialization.

DATABASE_OPERATION qualified name is path::database:provider:target.method@start_byte; unknown target is
omitted. parent_id is execution owner, with no fabricated DEFINES for an expression. READS/WRITES point
owner -> operation. GraphResult observations/entities/relationships follow deterministic source order;
operation/provider counts and staged/unlinked/unmaterialized counts are derived. Frozen shells own mutable
CodeGraph instances; treat completed results as snapshots. Source/metadata authenticity is not guaranteed
for arbitrary caller-fabricated records; source-free validation is structural, while adapters establish syntax.

## 5. Decisions Made

D-109: bounded SQLAlchemy Session/statement provenance and effect stages; optional forms deferred.
D-110: omit comprehension environments, remove supplied-site override, disambiguate nested scope names.
D-111: direct PrismaClient construction and full bounded JS/TS method mapping.
D-112: catch/with omissions and named function self-binding guards.
D-113: file-wide explicit mutation/computed/delete and TS enum/namespace contradictions.
D-114: existing parse-lifetime integration, collision guard, lightweight validation and field preservation.
D-115: deterministic operation nodes and eligible capabilities/evidence in independent graph; supersedes D-105.
D-116: exact contained statement invocation proof prevents borrowing unrelated insert imports/calls.
D-117: complete local gate, reproducible mixed traces, documentation and stop before Phase2.2.

## 6. Requirements and Constraints

Local only: no remote/GitHub API/push/upload/package/release/publishing. Every author/committer solely
PrathamKapoor <prathamkapoor027@gmail.com>; no coauthors/tool attribution or paper/research/tex files.
No target source/tests/modules/packages executed/imported; no Node, dependency install, ORM/runtime
constructor/decorator evaluation, DB connection, credentials or SQL execution. Source is untrusted data.
No runtime dependencies, core vocabularies, parser pins, quality settings or graph algorithms changed.
Stop after Phase2.1C; Phase2.2 query engine is future work, not implemented this session.

## 7. Testing and Verification

Verified .venv/Scripts/python.exe Python3.13.14. Baseline393 tests OK/skipped7; StageA400 OK/skipped7;
StageB404 OK/skipped7; final pre-commit417 OK/skipped7. Seven existing skips: six Windows symlink privilege
(WinError1314) cases and one absent os.mkfifo API. No skipped database test.

Final verified commands with .venv\Scripts\python.exe:
- -m unittest tests.database.test_sqlalchemy -q:8 tests (many operation/negative subcases), OK.
- -m unittest tests.database.test_prisma -q:4 tests (all CRUD methods in JS/TS and negatives), OK.
- -m unittest tests.database.test_graph -q:11 tests, OK.
- -m unittest tests.database.test_foundation -q:10 tests, OK.
- -m unittest discover -s tests -q:417 tests, OK/skipped7.
- -m ruff check src tests:All checks passed.
- -m ruff format --check src tests:119 files already formatted.
- -m mypy src/arctrellis:68 source files, no issues.
- -m compileall -q src:exit0.
- -m pip check:No broken requirements found.
- -m unittest tests.test_architecture -q:3 tests, OK.
- -m tests.database.smoke:SQLAlchemy6, Prisma3, operation9, reads2, writes3, staged1,
  unmaterialized0, without-DB-edge4, unknown1; deterministic=True.
  Python POST/payment path: app.py:12 fastapi_decorated_handler PROVEN/1.0,
  app.py:14 python_lexical_call_resolution LIKELY/0.85,
  app.py:7 sqlalchemy_execute_insert LIKELY/0.85.
  TS POST/payment path: app.ts:10 express_local_handler_resolution LIKELY/0.85,
  app.ts:8 ecmascript_lexical_call_resolution LIKELY/0.85,
  app.ts:6 prisma_model_create LIKELY/0.85.
- Fresh interpreter public package import orders pass; no retained bytes/trees, original graphs unchanged,
  materialization read guards and source execution/ORM import guards pass.
- Git whitespace passes; remotes/forbidden files/attribution/credential matches absent.
  Execution search finds only existing fixed parsing grammar imports/loading; pyproject diff empty.

Initial missing APIs failed before implementations. StageA initial lint/format and seven typing errors,
then three name-inference errors were fixed without suppressions. Comprehension2/nested scope1 regressions
failed before correction. StageB catch2 and mutation/enum/computed/delete9 negative subcases failed before
fixes. StageC initial lint and one union annotation were corrected. Coherent UNKNOWN-to-WRITE borrowing
regression failed before statement-call proof fix. New architecture audit initially flagged six relative
adapter imports; restricting absolute import analysis corrected its test assumption. All gates repeated.
Independent read-only reviews verified corrections; no important normal-extraction defect remains confirmed.

## 8. Known Issues / Risks

No confirmed unresolved important defect in supported extraction/graph semantics. Static relationships are
not runtime effects; get may avoid SQL and Prisma requests may never execute. Conservative global name
exclusions can omit unrelated valid operations. Generic call resolution still has its historical limited
runtime/shadowing model; endpoint traces inherit existing confidence, not stronger certainty.

Source-free structural validation cannot authenticate arbitrary coherent fabrication of observation/call
metadata, including replacing UNKNOWN transform(insert(...)) with metadata borrowing its nested insert;
normal extraction correctly keeps that source UNKNOWN and emits no write edge. External package installation
identity, arbitrary search paths, monkey patches, dynamic alias effects and other platforms are unverified.
Existing native parser resource/filesystem race limits and revision-only/non-namespaced IDs remain.

## 9. Unfinished Work

No required Phase2.1 implementation remains. Final local commit and reference finalization pending.
No ORM runtime/schema/query execution or Phase2.2 implementation was started. References use real
implementation hashes in later docs commits without history rewrite under D-004/D-067.

## 10. Next Subphase

Phase 2.2 — Deterministic structural query engine and evidence-path API, only in a later authorized session.
Use existing graph traversal and original Evidence; never invent semantic edges. Do not begin it now.

## 11. Critical Context

Common DatabaseOperationObservation identity remains UUID5/version1; owner must be MODULE/FUNCTION/METHOD.
Provider is extensible string, not inferred from method names. Adapters use verified direct import + unique
constructor patterns and retain effect_stage. Result sorting is path/start/end/ID; source locations inclusive,
syntax spans half-open exact bytes/points. Statement first-argument recognition belongs to SQLAlchemy syntax
extraction; retained canonical invocation witnesses strengthen structural validation without reparsing.

No TABLE/MODEL/DATABASE entities. Staged SQLAlchemy mutations/commit/flush/rollback/UNKNOWN never emit
WRITES_DATABASE; DELETE direct statements/client requests are write-capable. No runtime PROVEN DB claim.
Context-manager Session, AsyncSession, sessionmaker, typed params, full aliases/dataflow, Python comprehensions,
catch/with/anonymous bodies, CommonJS/custom clients, Prisma schema/extensions/raw queries, SQL parsing,
physical table resolution, transaction outcomes, implicit flush and other ORM adapters are deferred.
Existing static TESTS, framework/middleware/router behavior remains preserved, with historical limitations.

## 12. Agent Instructions

Read root records completely and inspect actual code before editing. Preserve historical decisions/session
tables, continue D-numbering, document bugs with symptoms/root cause/regression and finalize only new commit
reference fields separately. Verify exact local Git identity before every commit and empty remotes at gates.
Use .venv interpreter, complete quality gates and inspect explicit file outcomes before interpreting empty
semantics. All target input remains static/local. No target execution/import/install/DB/SQL/remote/publishing.
Treat graphs as independent mutable snapshots and preserve confidence/evidence limits. Stop after handoff.
