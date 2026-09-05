"""PrimeStride Client OS v1.1.1.2 readiness consistency hotfix.

Composes three behaviors on the Readiness page:
- lifecycle-filtered ACTIVE evidence only
- v0.8.5 honest readiness-range summaries
- lifecycle-aware stage/gap gating when no real source is active

When every current file is TEST/ARCHIVED, the account returns to Data Requested
and the readiness page does not manufacture a specific "ask next" list from zero
reviewed evidence. The correct next action is to wait for the first real sample.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from .db import SessionLocal
from .models import TimelineEvent
from .v111_lifecycle import (
    _CompanyView,
    _reconcile_stage,
    active_intake_files,
    effective_readiness_evidence,
    ensure_lifecycle_rows,
)

VERSION = "1.1.1.2"


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

            # Keep the account stage truthful even when the operator lands on
            # Readiness directly instead of visiting Data Intake first.
            old_stage = c.stage
            if _reconcile_stage(db, c, list(c.intake_files)):
                db.add(TimelineEvent(
                    company_id=c.id,
                    event_type="Stage Reconcile",
                    title=f"Lifecycle-aware readiness stage reconciled to {c.stage}",
                    details=f"v{VERSION} active-source gate" + (f" · {old_stage} → {c.stage}" if old_stage != c.stage else ""),
                ))
            db.commit()

            c = db.scalar(m.company_stmt(company_id))
            active = active_intake_files(db, company_id, list(c.intake_files))
            evidence = effective_readiness_evidence(c, db)
            view = _CompanyView(c, intake_files=active, readiness_evidence=evidence)

            summaries = _honest_summaries(m, view)
            # With zero ACTIVE sources there is no evidence-informed gap ranking
            # yet. Asking for KPI definitions or quote history at this point would
            # recreate the broad-homework behavior Source-First Intake was built
            # to avoid.
            gap_intelligence = _gap_intelligence(summaries) if active else None

            return m.render(request, "readiness_framework.html", {
                "company": c,
                "summaries": summaries,
                "files_received": len(active),
                "status_options": m.READINESS_STATUS_OPTIONS,
                "gap_intelligence": gap_intelligence,
                "readiness_version": VERSION,
            })
        finally:
            db.close()
