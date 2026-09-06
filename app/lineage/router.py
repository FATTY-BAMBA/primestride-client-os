"""HTTP routes for the stable lineage domain."""
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import select

from ..db import SessionLocal
from ..models import Company
from .schema import ingestion_jobs, source_references
from .service import (
    backfill_source_references,
    ensure_lineage_schema,
    jsonable,
)

DOMAIN_VERSION = "1.3.0"


def install_lineage_routes(app: FastAPI) -> None:
    if getattr(app.state, "ps_lineage_routes_installed", False):
        return
    app.state.ps_lineage_routes_installed = True

    try:
        ensure_lineage_schema()
        db = SessionLocal()
        try:
            added = backfill_source_references(db)
            if added:
                db.commit()
            else:
                db.rollback()
        finally:
            db.close()
    except Exception as exc:
        print(f"[lineage bootstrap] warning: {exc!r}")

    @app.get("/api/lineage/status", include_in_schema=False)
    def lineage_status():
        try:
            ensure_lineage_schema()
            return {
                "ok": True,
                "version": DOMAIN_VERSION,
                "source_references": "ready",
                "ingestion_jobs": "ready",
                "migration": "manifest-backfill-compatible",
                "domain": "lineage",
            }
        except Exception as exc:
            return JSONResponse({
                "ok": False,
                "version": DOMAIN_VERSION,
                "error": "Lineage registry schema is unavailable.",
                "detail": f"{type(exc).__name__}: {str(exc)[:1000]}",
            }, status_code=503)

    @app.get("/companies/{company_id}/lineage", include_in_schema=False)
    def company_lineage(company_id: int):
        db = SessionLocal()
        try:
            if not db.get(Company, company_id):
                return JSONResponse({"error": "Company not found."}, status_code=404)
            backfill_source_references(db, company_id)
            db.commit()
            sources = [dict(r) for r in db.execute(
                select(source_references)
                .where(source_references.c.company_id == company_id)
                .order_by(source_references.c.id.desc())
                .limit(100)
            ).mappings().all()]
            jobs = [dict(r) for r in db.execute(
                select(ingestion_jobs)
                .where(ingestion_jobs.c.company_id == company_id)
                .order_by(ingestion_jobs.c.id.desc())
                .limit(100)
            ).mappings().all()]
            return {
                "ok": True,
                "version": DOMAIN_VERSION,
                "source_count": len(sources),
                "job_count": len(jobs),
                "sources": [jsonable(x) for x in sources],
                "jobs": [jsonable(x) for x in jobs],
            }
        finally:
            db.close()
