# Supabase setup for PrimeStride Client OS

## Purpose
Use Supabase as managed PostgreSQL infrastructure while keeping PrimeStride application logic and data access based on standard PostgreSQL/SQLAlchemy.

## Runtime architecture

Vercel FastAPI -> Supabase Transaction Pooler (Supavisor, port 6543) -> PostgreSQL

For Vercel serverless traffic, use the Supabase **Transaction Pooler** connection string as `DATABASE_URL`.

For future migrations/admin work, keep a separate direct/session connection as `DIRECT_DATABASE_URL`.

## Vercel environment variables

Set these in the **Client OS Vercel project**, never in GitHub:

- `DATABASE_URL` — Supabase Transaction Pooler URL; enable for Preview + Production.
- `DIRECT_DATABASE_URL` — direct/session database URL reserved for migrations/admin; do not expose to frontend/browser code.

The application automatically normalizes `postgres://` or `postgresql://` URLs to SQLAlchemy's psycopg v3 driver.

## Validation sequence

1. Configure `DATABASE_URL` for Preview.
2. Redeploy the feature branch.
3. Open `/health`; expected database mode is PostgreSQL.
4. Open `/` and confirm pipeline renders.
5. Create a temporary company and refresh the page; record must persist.
6. Run the guided Discovery Meeting and verify the saved record persists after another deployment.
7. Only after Preview passes, configure Production and merge the PR.

## Security rules

- Never commit connection strings, database passwords, Supabase service-role keys, or client data.
- Browser/client code must never receive `DATABASE_URL` or `DIRECT_DATABASE_URL`.
- Real client uploads will later use private storage buckets and explicit authorization policies.
- Tenant isolation and Row Level Security are planned before any client-facing portal.

## Migration policy

`Base.metadata.create_all()` is temporary v0.2 bootstrap behavior only. Before Client OS becomes a production system of record, replace it with versioned Alembic migrations and use `DIRECT_DATABASE_URL` for migration execution.

## Next infrastructure milestones

- Alembic initial schema migration
- Supabase Storage for v0.3 secure client uploads
- PrimeStride staff authentication
- Tenant-aware permissions / RLS before client-facing access
- Database backup and recovery policy
