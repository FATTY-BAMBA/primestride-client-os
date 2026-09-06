"""Stable client-workspace projection routes.

Moves the remaining page-specific read paths out of ``v082_perf.py`` while
preserving lifecycle-safe client truth.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse

from ..db import SessionLocal
from ..lifecycle.service import (
    CompanyView,
    active_intake_files,
    effective_readiness_evidence,
    ensure_lifecycle_rows,
    reconcile_stage,
)
from ..models import TimelineEvent
from ..readiness.scoring import honest_summaries

DOMAIN_VERSION = "1.3.3"


def install_workspace_routes(app: FastAPI) -> None:
    if getattr(app.state, "ps_workspace_routes_installed", False):
        return
    app.state.ps_workspace_routes_installed = True

    @app.get("/companies/{company_id}/stage-intelligence", response_class=HTMLResponse, include_in_schema=False)
    def stage_intelligence(company_id: int, request: Request):
        from .. import main as m

        db = SessionLocal()
        try:
            company = db.scalar(m.company_stmt(company_id))
            if not company:
                return HTMLResponse("Company not found", 404)

            ensure_lifecycle_rows(db, company_id)
            old_stage = company.stage
            if reconcile_stage(db, company, list(company.intake_files)):
                db.add(TimelineEvent(
                    company_id=company.id,
                    event_type="Stage Reconcile",
                    title=f"Lifecycle-aware stage intelligence reconciled to {company.stage}",
                    details=f"v{DOMAIN_VERSION} active-source gate" + (
                        f" · {old_stage} → {company.stage}" if old_stage != company.stage else ""
                    ),
                ))
            db.commit()

            company = db.scalar(m.company_stmt(company_id))
            active = active_intake_files(db, company_id, list(company.intake_files))
            evidence = effective_readiness_evidence(company, db)
            view = CompanyView(company, intake_files=active, readiness_evidence=evidence)

            return m.render(request, "stage_intelligence.html", {
                "company": company,
                "stage_info": m.stage_intelligence(view),
                "stages": m.PIPELINE_STAGES,
            })
        finally:
            db.close()

    @app.get("/companies/{company_id}/solution-blueprint", response_class=HTMLResponse, include_in_schema=False)
    def solution_blueprint(company_id: int, request: Request):
        from .. import main as m

        db = SessionLocal()
        try:
            company = db.scalar(m.company_stmt(company_id))
            if not company:
                return HTMLResponse("Company not found", 404)

            m.ensure_v04_memory(db, company)
            m.ensure_v05_decisions(db, company)
            ensure_lifecycle_rows(db, company_id)
            db.commit()

            company = db.scalar(m.company_stmt(company_id))
            company.decisions.sort(key=lambda item: item.decided_at, reverse=True)
            active = active_intake_files(db, company_id, list(company.intake_files))
            evidence = effective_readiness_evidence(company, db)
            view = CompanyView(company, intake_files=active, readiness_evidence=evidence)

            selected = m.selected_module_nos(view)
            phases = [{"module_no": no, **m.MODULE_DETAILS[no]} for no in selected]
            operating_spine = []
            if 4 in selected:
                operating_spine.append({"en": "Quote", "zh": "報價"})
            if 5 in selected:
                operating_spine.extend([
                    {"en": "Order", "zh": "訂單"},
                    {"en": "Work Order", "zh": "工單"},
                    {"en": "Production Events", "zh": "生產事件"},
                ])
            if 6 in selected:
                operating_spine.append({"en": "Analytics", "zh": "營運分析"})
            if not operating_spine:
                operating_spine = [
                    {"en": "Operational Data", "zh": "營運資料"},
                    {"en": "AI Operations", "zh": "AI 營運"},
                ]

            return m.render(request, "solution_blueprint.html", {
                "company": company,
                "memory": m.memory_groups(company),
                "summaries": honest_summaries(m, view),
                "phases": phases,
                "operating_spine": operating_spine,
                "decisions": company.decisions,
                "files_received": len(active),
                "blueprint_mode": "Evidence-informed" if active else "Hypothesis · evidence pending",
            })
        finally:
            db.close()


__all__ = ["install_workspace_routes"]
