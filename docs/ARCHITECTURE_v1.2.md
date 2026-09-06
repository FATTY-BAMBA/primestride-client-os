# PrimeStride Client OS Architecture v1.5

## Goal

Preserve the proven Source-First behavior while turning Client OS into a repeatable, testable platform that can support many client implementations without release-by-release architecture drift.

## Foundation completed

### v1.2 — explicit application architecture

- `app/main.py` exposes `create_app()`.
- `app/platform_bootstrap.py` owns explicit runtime wiring.
- `app/db.py` is database/session infrastructure, not application bootstrap.
- The FastAPI constructor monkeypatch was removed.

### v1.3 — stable backend domains

Production wiring moved to stable packages:

- `app/lineage/` — SourceReference identity and provenance
- `app/jobs/` — IngestionJob lifecycle, recovery and retry
- `app/readiness/` — deterministic readiness projection, ranges and gap intelligence
- `app/lifecycle/` — ACTIVE / TEST / ARCHIVED evidence state and stage gates
- `app/intake/` — registration, reclassification, human review and deterministic intake contract
- `app/storage/` — private retained originals and Source-First storage
- `app/workspace/` — lifecycle-safe workspace read paths
- `app/ai/` — section-aware multimodal extraction and background processing

Release-numbered backend modules remain compatibility adapters only.

### v1.4 — stable frontend domains

Data Intake now boots through one stable entrypoint:

`/static/frontend/bootstrap.js`

The browser is organized behind four stable boundaries:

- `frontend/deterministic.js`
- `frontend/ai.js`
- `frontend/source.js`
- `frontend/workspace.js`

The old release-numbered browser modules remain implementation leaves for safe, domain-by-domain retirement; templates no longer know their load order.

## v1.5 — schema ownership and regression safety

### Alembic is authoritative

`alembic upgrade head` is now the normal schema-provisioning path.

The adoption baseline migration creates the full current Client OS schema for a fresh environment while preserving any tables that already exist in production. Runtime `create_all()` is no longer the normal provisioning mechanism for core, lineage, or lifecycle schemas.

`RUNTIME_SCHEMA_BOOTSTRAP=1` remains only as an explicit disposable-development escape hatch.

### Regression suite

The first automated contract covers:

- Alembic creates core + lineage + lifecycle tables
- stable application bootstrap and platform status
- TEST evidence cannot move a client into operational readiness stages
- ACTIVE reviewed evidence can advance through Data Received → Data Readiness
- readiness coverage/ranges keep unknown evidence unknown
- gap intelligence does not re-request already evidenced criteria
- SourceReference source identity, SHA and object location remain immutable on upsert

### CI

`.github/workflows/ci.yml` runs on pushes and pull requests:

1. install production + test dependencies
2. compile application, migration and test modules
3. run `alembic upgrade head` against a fresh SQLite database
4. run the pytest regression suite

This changes the development model: validated architecture rules are now executable contracts rather than only documentation/manual checks.

## Required invariants

1. Source-First Intake retains the original before interpretation.
2. Every retained source resolves to immutable SourceReference provenance.
3. Every processing attempt is an IngestionJob; retry creates another attempt, not another original.
4. TEST and ARCHIVED sources never affect readiness or stage gates.
5. ACTIVE evidence alone can move Data Requested → Data Received → Data Readiness.
6. AI proposes; human review approves evidence.
7. Readiness ranges are deterministic and evidence-based.
8. Client-specific variation should move toward configuration, not hard-coded branches.

## Current platform shape

Backend:

`lineage → jobs → lifecycle → intake/storage/ai → readiness/workspace`

Frontend:

`frontend/bootstrap.js → deterministic + ai + source + workspace`

Database:

`Alembic revisions → provisioned relational schema`

Quality gate:

`GitHub Actions → migration smoke test + regression suite`

## Major next wins

### 1. Frontend leaf retirement

Replace the remaining `v081/v083/v084/v09/v091/v092/v093/v094/v100/v101/v103/v110/v111` implementation leaves inside the four stable browser domains. Do this domain-by-domain behind parity tests rather than as a large rewrite.

### 2. Remove Source Vault manifest dependency

`SourceReference` is now the canonical provenance record. The `PS_SOURCE_VAULT_V1:` copy in `IntakeFile.notes` should become compatibility-only, then be removed after all retained production sources have verified relational equivalents.

### 3. Repeatable tenant/client provisioning

New company onboarding should create tenant configuration, storage namespace, module scope, lifecycle defaults and intake state from configuration instead of named-client assumptions.

### 4. Real-client blueprint generation

When the first real 菘佑 evidence arrives, Client OS should use the proven intake/readiness pipeline to generate the evidence-backed Module 04/05/06 implementation blueprint and smallest next-data request.

### 5. First operational vertical slice

Build a closed loop across the shared operating-data spine:

`Quote → accepted order → work order → production event/status → management metric`

This is the transition from implementation tooling into the actual AI營運大腦 product value.

## Release discipline

Architecture changes must not silently change client truth, readiness scoring, source lineage, storage object identity, lifecycle isolation, or human-review policy. New platform behavior should add a regression test before or with the implementation.
