# PrimeStride Client OS Architecture v1.2

## Goal

Stabilize the proven v1.1 behavior before adding more product capability. Preserve Source-First Intake, private original retention, SourceReference lineage, IngestionJob history/retry, source lifecycle isolation, human review, and evidence-based readiness while removing release-by-release bootstrap sprawl.

## What changed in v1.2.0

### Central runtime registry

`app/platform_bootstrap.py` is now the single ordered registry for runtime components. Route precedence is documented in one place instead of being encoded as a long list of imports inside `db.py`.

`db.py` now owns database configuration only plus a small temporary compatibility bridge. The bridge exists solely because `app/main.py` still constructs the FastAPI application during module import; it delegates immediately to `install_platform_extensions()`.

### Stable frontend bootstrap

`app/static/v07.js` is now a stable intake bootstrap with one ordered module registry and one sequential loader. Existing versioned modules remain for compatibility, but future consolidation can happen behind this entrypoint without changing the template or creating another promise-chain wrapper.

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

### Phase 2 — application factory

Create `create_app()` and move FastAPI construction out of `main.py`. Call `install_platform_extensions(app)` explicitly, then delete the compatibility bridge from `db.py`.

### Phase 3 — domain routers/services

Move routes and business logic into stable modules:

- `intake/` — source-first orchestration, deterministic inspection, review lifecycle
- `storage/` — private object storage and source retention
- `lineage/` — SourceReference and provenance queries
- `jobs/` — IngestionJob lifecycle, recovery and retry
- `readiness/` — evidence projection, scoring ranges, next-gap intelligence
- `ai/` — multimodal extraction and AI gateway interaction

Versioned modules become compatibility adapters and are retired only after behavior parity tests pass.

### Phase 4 — frontend consolidation

Merge the stable intake behavior into a small number of domain modules behind the existing bootstrap. Remove DOM monkeypatch layers only after end-to-end parity for structured intake, multimodal intake, lifecycle isolation and job recovery.

## Release discipline

Architecture changes should not change client truth, readiness scores, source lineage, storage object keys, or review policy unless explicitly called out as a product change. Consolidation releases must be behavior-preserving first.
