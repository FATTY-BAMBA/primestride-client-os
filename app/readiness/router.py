"""HTTP routes for lifecycle-safe evidence readiness."""
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from ..db import SessionLocal
from ..lifecycle.service import ensure_lifecycle_rows, reconcile_stage
from ..models import TimelineEvent
from .service import DOMAIN_VERSION, build_readiness_projection


def install_readiness_routes(app: FastAPI) -> None:
    if getattr(app.state, "ps_readiness_routes_installed", False):
        return
    app.state.ps_readiness_routes_installed = True

    @app.get("/companies/{company_id}/readiness-framework", response_class=HTMLResponse, include_in_schema=False)
    def readiness_framework(company_id: int, request: Request):
        # Lazy import avoids a circular dependency while main.py is constructing
        # the application and installing domain routers.
        from .. import main as m

        db = SessionLocal()
        try:
            company = db.scalar(m.company_stmt(company_id))
            if not company:
                return HTMLResponse("Company not found", 404)

            m.ensure_v04_memory(db, company)
            ensure_lifecycle_rows(db, company_id)

            old_stage = company.stage
            if reconcile_stage(db, company, list(company.intake_files)):
                db.add(TimelineEvent(
                    company_id=company.id,
                    event_type="Stage Reconcile",
                    title=f"Lifecycle-aware readiness stage reconciled to {company.stage}",
                    details=f"v{DOMAIN_VERSION} active-source gate" + (
                        f" · {old_stage} → {company.stage}" if old_stage != company.stage else ""
                    ),
                ))
            db.commit()

            company = db.scalar(m.company_stmt(company_id))
            projection = build_readiness_projection(m, company, db)

            return m.render(request, "readiness_framework.html", {
                "company": company,
                "summaries": projection["summaries"],
                "files_received": len(projection["active_files"]),
                "status_options": m.READINESS_STATUS_OPTIONS,
                "gap_intelligence": projection["gap_intelligence"],
                "readiness_version": DOMAIN_VERSION,
            })
        finally:
            db.close()
