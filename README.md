# PrimeStride Client OS v1.6

Internal implementation and client-intelligence operating system for PrimeStride AI.

## What the platform does

Client OS turns messy client evidence into a governed implementation workflow:

`Provision Client → Source-First Intake → private original → SourceReference → IngestionJob → deterministic/AI proposal → human review → lifecycle-safe readiness → client blueprint`

Core rules:
- every Company receives a durable tenant identity
- retain the original before interpretation
- ACTIVE / TEST / ARCHIVED evidence is explicit
- TEST and ARCHIVED sources never affect readiness or stage gates
- AI proposes; humans approve client truth
- readiness is deterministic and evidence-based
- retries create new processing attempts against the same immutable source

## Architecture

Stable backend domains:
- `app/accounts/`
- `app/lineage/`
- `app/jobs/`
- `app/readiness/`
- `app/lifecycle/`
- `app/intake/`
- `app/storage/`
- `app/workspace/`
- `app/ai/`

Stable Data Intake frontend entrypoint:
- `app/static/frontend/bootstrap.js`

Legacy release-numbered modules remain only as compatibility leaves while they are retired safely.

## Multi-client provisioning

v1.6 introduces `tenant_configs` as the durable client provisioning record. A new Company receives a stable tenant key such as:

`c0002-acme-manufacturing`

That key is independent from the mutable company display name and is used as the Source Vault namespace:

`tenants/<tenant_key>/originals/YYYY/MM/...`

Existing SourceReference tenant keys are adopted rather than rewritten, so retained object paths remain immutable.

Provisioning status is available at:

`GET /companies/{company_id}/provisioning/status`

## Database migrations

Alembic is authoritative from v1.5 onward. Runtime `create_all()` is no longer the normal provisioning path.

```bash
alembic upgrade head
```

Migrations are adoption-safe for existing Client OS databases. v1.6 adds durable tenant provisioning without moving or renaming retained Source Vault objects.

`RUNTIME_SCHEMA_BOOTSTRAP=1` exists only as an explicit escape hatch for disposable local experiments.

## Run locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements-dev.txt
alembic upgrade head
uvicorn app.main:app --reload
```

Open http://127.0.0.1:8000

## Tests

```bash
pytest -q
```

GitHub Actions runs:
- Python compilation
- a fresh-database Alembic migration smoke test
- the regression suite

Regression coverage includes schema ownership, platform wiring, tenant-key immutability, historical namespace adoption, lifecycle TEST isolation, deterministic readiness ranges, gap intelligence, and immutable SourceReference identity/object provenance.

## Deployment

GitHub is the source of truth. Production must use PostgreSQL through `DATABASE_URL`; SQLite is local/demo only.

Before a fresh environment serves traffic, run:

```bash
alembic upgrade head
```

## Safety / data hygiene

Never commit API keys, database credentials, real client uploads, or confidential customer data.
