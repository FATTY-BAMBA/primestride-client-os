# PrimeStride Client OS Architecture v1.3

## Goal

Stabilize the proven v1.1 behavior before adding more product capability. Preserve Source-First Intake, private original retention, SourceReference lineage, IngestionJob history/retry, source lifecycle isolation, human review, and evidence-based readiness while removing release-by-release bootstrap sprawl.

## v1.2 foundation

### Central runtime registry

`app/platform_bootstrap.py` became the single ordered registry for runtime components. Route precedence is documented in one place instead of being encoded as a long list of imports inside `db.py`.

### Stable frontend bootstrap

`app/static/v07.js` became a stable intake bootstrap with one ordered module registry and one sequential loader. Existing versioned modules remain for compatibility, but future consolidation can happen behind this entrypoint without changing the template or creating another promise-chain wrapper.

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

The jobs and readiness domains now import lifecycle behavior from `app.lifecycle`, eliminating another release-numbered dependency edge.

### v1.3.2 — private storage / Source Vault

Production wiring now uses `app/storage/` for the complete retained-original contract:

- private S3-compatible storage configuration and provider client
- tenant-readable keys such as `tenants/c0001-songyou/originals/YYYY/MM/...`
- SHA-256, immutable source IDs, and compatibility manifests
- Source-First storage status
- Source Vault inventory and 5-minute private open links
- first-class `SourceReference` creation on retention
- lifecycle-aware stage reconciliation after a new retained source is registered

Former `v100_storage.py` and `v101_storage.py` are now compatibility adapters only. The jobs domain reads retained originals through `app.storage` directly, so retry/recovery no longer depends on a release-numbered storage module.

## Required invariants

1. Source-First Intake retains the original before interpretation.
2. Every retained source can resolve to one immutable SourceReference.
3. Every processing attempt is an IngestionJob; retries create new attempts, not new originals.
4. TEST and ARCHIVED sources never affect readiness or stage gates.
5. ACTIVE evidence alone can move Data Requested → Data Received → Data Readiness.
6. AI proposes; human review approves evidence.
7. Readiness ranges are deterministic and evidence-based.
8. Existing v1.1 URLs and behavior remain backward compatible during consolidation.

## Remaining cleanup

### Deterministic intake domain

Move table-region detection, canonical mapping, correction lifecycle helpers, and readiness-range helpers out of `v082_runtime.py` / `v082_perf.py` into stable intake/readiness services.

### AI domain

Move multimodal provider interaction, section-aware mapping, background polling, and result validation into a stable `ai/` package. Versioned AI modules become compatibility adapters after parity tests.

### Frontend consolidation

Merge stable intake behavior into a small number of domain modules behind the existing bootstrap. Remove DOM monkeypatch layers only after end-to-end parity for structured intake, multimodal intake, lifecycle isolation and job recovery.

### Formal migrations

Move first-class lineage/lifecycle tables from runtime `create_all(checkfirst=True)` provisioning to explicit Alembic migrations. Remove legacy Source Vault manifest dependency only after all active production rows have durable relational equivalents.

## Release discipline

Architecture changes should not change client truth, readiness scores, source lineage, storage object keys, or review policy unless explicitly called out as a product change. Consolidation releases must be behavior-preserving first.
