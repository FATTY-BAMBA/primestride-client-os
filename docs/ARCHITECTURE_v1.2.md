# PrimeStride Client OS Architecture v1.2

## Goal

Stabilize the proven v1.1 behavior before adding more product capability. Preserve Source-First Intake, private original retention, SourceReference lineage, IngestionJob history/retry, source lifecycle isolation, human review, and evidence-based readiness while removing release-by-release bootstrap sprawl.

## What changed in v1.2.0

### Central runtime registry

`app/platform_bootstrap.py` became the single ordered registry for runtime components. Route precedence is documented in one place instead of being encoded as a long list of imports inside `db.py`.

### Stable frontend bootstrap

`app/static/v07.js` became a stable intake bootstrap with one ordered module registry and one sequential loader. Existing versioned modules remain for compatibility, but future consolidation can happen behind this entrypoint without changing the template or creating another promise-chain wrapper.

## What changed in v1.2.1

### Explicit application factory

`app/main.py` now exposes `create_app()` and builds the FastAPI application explicitly. `install_platform_extensions(application)` is called directly before legacy prototype routes are declared, preserving the validated route-shadowing order without modifying the FastAPI constructor.

`db.py` now owns database configuration and session/schema helpers only. The temporary FastAPI monkeypatch / compatibility bridge has been deleted completely.

`/api/platform/status` now reports:

- `bootstrap: explicit-application-factory`
- `compatibility_bridge: none`

The public FastAPI application version and `/health` version are both sourced from `PLATFORM_VERSION`, removing the old `0.5.0` application-version drift.

## Required invariants

1. Source-First Intake retains the original before interpretation.
2. Every retained source can resolve to one immutable SourceReference.
3. Every processing attempt is an IngestionJob; retries create new attempts, not new originals.
4. TEST and ARCHIVED sources never affect readiness or stage gates.
5. ACTIVE evidence alone can move Data Requested → Data Received → Data Readiness.
6. AI proposes; human review approves evidence.
7. Readiness ranges are deterministic and evidence-based.
8. Existing v1.1 URLs and behavior remain backward compatible during consolidation.

## Next cleanup steps

### Phase 3 — domain routers/services

Move routes and business logic into stable modules:

- `intake/` — source-first orchestration, deterministic inspection, review lifecycle
- `storage/` — private object storage and source retention
- `lineage/` — SourceReference and provenance queries
- `jobs/` — IngestionJob lifecycle, recovery and retry
- `readiness/` — evidence projection, scoring ranges, next-gap intelligence
- `ai/` — multimodal extraction and AI gateway interaction

Start with additive stable routers/services while keeping versioned modules as compatibility adapters. Retire each versioned module only after route and end-to-end parity checks pass.

### Phase 4 — frontend consolidation

Merge the stable intake behavior into a small number of domain modules behind the existing bootstrap. Remove DOM monkeypatch layers only after end-to-end parity for structured intake, multimodal intake, lifecycle isolation and job recovery.

### Phase 5 — formal migrations

Move first-class lineage/lifecycle tables from runtime `create_all(checkfirst=True)` provisioning to explicit Alembic migrations. Remove legacy Source Vault manifest dependency only after all active production rows have durable relational equivalents.

## Release discipline

Architecture changes should not change client truth, readiness scores, source lineage, storage object keys, or review policy unless explicitly called out as a product change. Consolidation releases must be behavior-preserving first.
