# PrimeStride Client OS Architecture v1.4

## Goal

Stabilize the proven v1.1 behavior before adding more product capability. Preserve Source-First Intake, private original retention, SourceReference lineage, IngestionJob history/retry, source lifecycle isolation, human review, and evidence-based readiness while removing release-by-release bootstrap sprawl.

## v1.2 foundation

### Central runtime registry

`app/platform_bootstrap.py` became the single ordered registry for runtime components. Route precedence is documented in one place instead of being encoded as a long list of imports inside `db.py`.

### Explicit application factory

`app/main.py` exposes `create_app()` and builds the FastAPI application explicitly. `install_platform_extensions(application)` is called directly before legacy prototype routes are declared, preserving the validated route-shadowing order without modifying the FastAPI constructor.

`db.py` owns database configuration and session/schema helpers only. The temporary FastAPI monkeypatch / compatibility bridge has been deleted completely.

## v1.3 Phase 3 domain migration

### v1.3.0 — lineage, jobs, readiness

Production wiring moved to stable packages:

- `app/lineage/` — SourceReference schema, provenance services, lineage HTTP routes
- `app/jobs/` — IngestionJob recovery/retry services and routes
- `app/readiness/` — lifecycle-safe readiness projection and HTTP routes

Former `v110_lineage.py`, `v112_jobs.py`, and `v1111_readiness_fix.py` modules remain thin compatibility adapters only.

### v1.3.1 — lifecycle and intake workflow

Production wiring now also uses:

- `app/lifecycle/` — ACTIVE / TEST / ARCHIVED schema, evidence filtering, stage reconciliation, source lifecycle routes, lifecycle-safe account projection
- `app/intake/` — Source-First registration, lineage-preserving inspection saves, lifecycle-aware Data Intake view, and the human review gate

Former `v111_lifecycle.py`, `v101_runtime.py`, and `v110_review.py` modules are compatibility adapters. Production routing no longer depends on them.

### v1.3.2 — private storage / Source Vault

Production wiring now uses `app/storage/` for the complete retained-original contract:

- private S3-compatible storage configuration and provider client
- tenant-readable keys such as `tenants/c0001-songyou/originals/YYYY/MM/...`
- SHA-256, immutable source IDs, and compatibility manifests
- Source-First storage status
- Source Vault inventory and 5-minute private open links
- first-class `SourceReference` creation on retention
- lifecycle-aware stage reconciliation after a new retained source is registered

Former `v100_storage.py` and `v101_storage.py` are compatibility adapters only. The jobs domain reads retained originals through `app.storage` directly.

### v1.3.3 — deterministic intake and readiness scoring

Production no longer installs `v082_runtime.py` or `v082_perf.py`.

Stable ownership is now:

- `app/intake/deterministic.py` — intake categories, deterministic hash/file matching, evidence invalidation, and memory projection helpers
- `app/intake/router.py` — register/refresh, reclassify, confirm review, and remove workflow actions with lifecycle-aware stage reconciliation
- `app/readiness/scoring.py` — evidence coverage, honest readiness range, and next-gap intelligence
- `app/workspace/router.py` — lifecycle-safe Stage Intelligence and Solution Blueprint read paths

The historical `v082_runtime.py` and `v082_perf.py` files are thin compatibility adapters only. Browser-side table detection and canonical mapping remain on the validated v0.8.4 engine; this release changes ownership and wiring, not extraction behavior.

### v1.3.4 — multimodal AI domain

Production no longer installs the `v09_ai.py`, `v091_ai.py`, `v092_ai.py`, or `v093_ai.py` route implementations.

Stable ownership is now:

- `app/ai/schema.py` — controlled categories, readiness keys, canonical targets, and strict section-aware structured-output schema
- `app/ai/service.py` — provider configuration, evidence prompts, defensive result validation, retained-source linking, provider helpers, and first-class IngestionJob state recording
- `app/ai/router.py` — synchronous compatibility analyze route plus the production background start/poll flow

The background contract is preserved: Source-First supplies the retained `source_id`, AI processing creates a linked IngestionJob, the browser polls without blocking the page, and only reviewed evidence can become client truth.

`app/jobs/` imports the stable AI service directly for retry/recovery, eliminating the last production backend dependency on release-numbered AI modules.

## v1.4 Phase 4 frontend consolidation

### v1.4.0 — stable browser domains

Data Intake now boots through one stable browser entrypoint:

`/static/frontend/bootstrap.js`

That bootstrap exposes four ordered browser domains:

- `frontend/deterministic.js` — validated structured-browser inspection stack
- `frontend/ai.js` — multimodal review, section-aware rendering, background polling, and evidence governance stack
- `frontend/source.js` — Source Vault + Source-First orchestration stack
- `frontend/workspace.js` — progressive disclosure, lineage/job controls, and source lifecycle UI stack

The legacy `v07.js` file is now only a compatibility entrypoint that forwards to the stable frontend bootstrap. The Data Intake template no longer contains or needs knowledge of the 13-file release-numbered load order.

The release-numbered browser files remain behavior-compatibility leaves behind the stable domain boundaries for this pass. They are intentionally not deleted yet because the Source-First → AI → review → TEST-isolation flow has already been proven and preserving that behavior is more important than a large risky rewrite. Future frontend work can replace one stable domain at a time without changing templates or the application shell.

## Required invariants

1. Source-First Intake retains the original before interpretation.
2. Every retained source can resolve to one immutable SourceReference.
3. Every processing attempt is an IngestionJob; retries create new attempts, not new originals.
4. TEST and ARCHIVED sources never affect readiness or stage gates.
5. ACTIVE evidence alone can move Data Requested → Data Received → Data Readiness.
6. AI proposes; human review approves evidence.
7. Readiness ranges are deterministic and evidence-based.
8. Existing v1.1 URLs and behavior remain backward compatible during consolidation.

## Platform status after v1.4.0

Backend production bootstrap is entirely stable-domain based:

- lineage
- jobs
- readiness
- lifecycle
- intake
- storage
- workspace
- ai

Frontend production wiring is now domain-oriented behind a single stable bootstrap:

- deterministic
- ai
- source
- workspace

## Remaining cleanup

### Frontend leaf retirement

Replace the release-numbered browser implementation leaves inside each stable frontend domain only after parity tests. This is now an internal domain-by-domain cleanup rather than a template/bootstrap problem.

### Formal migrations

Move first-class lineage/lifecycle tables from runtime `create_all(checkfirst=True)` provisioning to explicit Alembic migrations. Remove legacy Source Vault manifest dependency only after all active production rows have durable relational equivalents.

## Release discipline

Architecture changes should not change client truth, readiness scores, source lineage, storage object keys, or review policy unless explicitly called out as a product change. Consolidation releases must be behavior-preserving first.
