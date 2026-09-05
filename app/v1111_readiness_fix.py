"""PrimeStride Client OS v1.1.1.1 readiness hotfix.

The v1.1.1 lifecycle route correctly filtered TEST/ARCHIVED evidence, but it
passed the older prototype readiness summary shape to the v0.8.5 readiness
template. That template expects honest-range fields such as coverage, range_min,
range_max, confirmed_weight and unknown_weight.

This route registers before v1.1.1 and composes both behaviors:
- lifecycle-filtered active evidence only
- v0.8.5 honest readiness-range summary + gap intelligence
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from .db import SessionLocal
from .v111_lifecycle import (
    _CompanyView,
    active_intake_files,
    effective_readiness_evidence,
    ensure_lifecycle_rows,
)

VERSION = "1.1.1.1"


def install_v1111_readiness_fix(app: FastAPI) -> None:
    if getattr(app.state, "ps_v1111_readiness_fix_installed", False):
        return
    app.state.ps_v1111_readiness_fix_installed = True

    @app.get("/companies/{company_id}/readiness-framework", response_class=HTMLResponse, include_in_schema=False)
    def readiness_lifecycle_honest_range(company_id: int, request: Request):
        from . import main as m
        from .v082_perf import _gap_intelligence, _honest_summaries

        db = SessionLocal()
        try:
            c = db.scalar(m.company_stmt(company_id))
            if not c:
                return HTMLResponse("Company not found", 404)

            m.ensure_v04_memory(db, c)
            ensure_lifecycle_rows(db, company_id)
            db.commit()

            c = db.scalar(m.company_stmt(company_id))
            active = active_intake_files(db, company_id, list(c.intake_files))
            evidence = effective_readiness_evidence(c, db)
            view = _CompanyView(c, intake_files=active, readiness_evidence=evidence)

            summaries = _honest_summaries(m, view)
            return m.render(request, "readiness_framework.html", {
                "company": c,
                "summaries": summaries,
                "files_received": len(active),
                "status_options": m.READINESS_STATUS_OPTIONS,
                "gap_intelligence": _gap_intelligence(summaries),
                "readiness_version": VERSION,
            })
        finally:
            db.close()
