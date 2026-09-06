# PrimeStride Client OS v1.5

Internal implementation and client-intelligence operating system for PrimeStride AI.

## What the platform does

Client OS turns messy client evidence into a governed implementation workflow:

`Source-First Intake → private original → SourceReference → IngestionJob → deterministic/AI proposal → human review → lifecycle-safe readiness → client blueprint`

Core rules:
- retain the original before interpretation
- ACTIVE / TEST / ARCHIVED evidence is explicit
- TEST and ARCHIVED sources never affect readiness or stage gates
- AI proposes; humans approve client truth
- readiness is deterministic and evidence-based
- retries create new processing attempts against the same immutable source

## Architecture

Stable backend domains:
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

## Database migrations

Alembic is authoritative from v1.5 onward. Runtime `create_all()` is no longer the normal provisioning path.

```bash
alembic upgrade head
```

The first baseline migration is adoption-safe for existing Client OS databases: existing tables are preserved and missing tables/indexes are created.

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

GitHub Actions also runs:
- Python compilation
- a fresh-database Alembic migration smoke test
- the regression suite

The initial regression contract covers schema ownership, stable platform wiring, lifecycle TEST isolation, deterministic readiness ranges, gap intelligence, and immutable SourceReference identity/object provenance.

## Deployment

GitHub is the source of truth. Production must use PostgreSQL through `DATABASE_URL`; SQLite is local/demo only.

Before a fresh environment serves traffic, run:

```bash
alembic upgrade head
```

## Safety / data hygiene

Never commit API keys, database credentials, real client uploads, or confidential customer data.
