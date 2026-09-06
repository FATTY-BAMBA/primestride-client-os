# PrimeStride Client OS Architecture v1.3

## Goal

Continue the behavior-preserving consolidation started in v1.2. Move proven runtime behavior out of release-numbered modules and into stable domain packages without changing client truth, source lineage, readiness scoring, lifecycle isolation, or retry semantics.

## Stable domains introduced in v1.3.0

### `app/lineage/`

Owns durable lineage schema, source provenance services, ingestion-job persistence helpers, and lineage HTTP routes.

- `schema.py` — `source_references` and `ingestion_jobs`
- `service.py` — SourceReference upsert/backfill/query and IngestionJob create/update helpers
- `router.py` — lineage status and per-company lineage endpoints

`app/v110_lineage.py` is now a compatibility adapter that re-exports the stable domain API for older modules still importing it.

### `app/jobs/`

Owns ingestion-job recovery/retry behavior.

- `service.py` — retained-original reads, retry creation, provider recovery, attempt sequencing
- `router.py` — retry and provider-state recovery endpoints

`app/v112_jobs.py` is now a compatibility adapter.

### `app/readiness/`

Owns the lifecycle-safe readiness projection and Readiness Framework route.

- `service.py` — ACTIVE-source projection, deterministic honest ranges, next-gap gating
- `router.py` — lifecycle-aware readiness page and stage reconciliation

`app/v1111_readiness_fix.py` is now a compatibility adapter.

## Production wiring

`app/platform_bootstrap.py` now installs these stable domains directly:

1. lineage
2. jobs
3. readiness
4. remaining compatibility modules in validated route order

The platform no longer relies on release-numbered installers for the three migrated domains.

## Compatibility strategy

Versioned modules are retired in two steps rather than deleted immediately:

1. move implementation into a stable domain package;
2. leave a thin adapter exporting the historical names until dependent modules are migrated.

This keeps Source-First Intake, multimodal AI, human review, and existing URLs working while the internal dependency graph is simplified incrementally.

## Required invariants

- Original files are retained before interpretation.
- SourceReference identity and object location remain immutable.
- Retries create new IngestionJob attempts, not new originals.
- TEST and ARCHIVED sources never affect operational readiness or stage gates.
- ACTIVE evidence alone can advance the data-readiness workflow.
- AI proposes; human review confirms evidence.
- Readiness ranges remain deterministic and evidence-based.
- Existing URLs remain backward compatible during migration.

## Next migration order

1. `source_lifecycle` → stable `lifecycle/` domain
2. `review_workflow` + source-first registration → stable `intake/` domain
3. Source Vault storage → stable `storage/` domain
4. multimodal extraction/provider logic → stable `ai/` domain
5. merge frontend version modules behind the stable intake bootstrap

After those migrations, the remaining `v0xx/v1xx` compatibility adapters can be removed in one audited cleanup release.
