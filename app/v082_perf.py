"""Page-specific read paths for Client OS v0.8.2.

These routes are registered before the prototype routes in main.py, so the same
URLs use narrower queries and avoid the old commit + full reload pattern.
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .db import get_db
from .models import Company

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def install_v082_perf(app: FastAPI) -> None:
    if getattr(app.state, "ps_v082_perf_installed", False):
        return
    app.state.ps_v082_perf_installed = True

    @app.get("/companies/{company_id}", response_class=HTMLResponse, include_in_schema=False)
    def company_detail_fast(company_id: int, request: Request, db: Session = Depends(get_db)):
        # Company workspace genuinely uses most relationships, but we still avoid
        # the previous ensure -> commit -> query-everything-again cycle.
        c = db.scalar(
            select(Company)
            .where(Company.id == company_id)
            .options(
                selectinload(Company.intake),
                selectinload(Company.pains),
                selectinload(Company.discovery),
                selectinload(Company.meetings),
                selectinload(Company.module_fits),
                selectinload(Company.tasks),
                selectinload(Company.readiness),
                selectinload(Company.timeline),
                selectinload(Company.memory_items),
                selectinload(Company.intake_files),
                selectinload(Company.readiness_evidence),
                selectinload(Company.decisions),
            )
        )
        if not c:
            return HTMLResponse("Company not found", 404)

        # Import only at request time; main.py is fully initialized by then.
        from . import main as m

        # Seed context only for a brand-new account. Existing accounts do zero
        # writes on a normal page read.
        if not c.memory_items or not c.decisions:
            if not c.memory_items:
                m.ensure_v04_memory(db, c)
            if not c.decisions:
                m.ensure_v05_decisions(db, c)
            db.commit()
            c = db.scalar(m.company_stmt(company_id))

        c.pains.sort(key=lambda x: x.rank)
        c.module_fits.sort(key=lambda x: x.module_no)
        c.readiness.sort(key=lambda x: x.module_no)
        c.timeline.sort(key=lambda x: x.created_at, reverse=True)
        c.meetings.sort(key=lambda x: x.completed_at, reverse=True)
        c.memory_items.sort(key=lambda x: x.id)
        c.intake_files.sort(key=lambda x: x.received_at, reverse=True)
        c.decisions.sort(key=lambda x: x.decided_at, reverse=True)
        return TEMPLATES.TemplateResponse(
            request=request,
            name="company.html",
            context={
                "company": c,
                "stages": m.PIPELINE_STAGES,
                "modules": m.MODULES,
                "completion": m.discovery_completion(c.discovery),
                "memory": m.memory_groups(c),
                "files_received": len(c.intake_files),
                "stage_info": m.stage_intelligence(c),
                "readiness_summaries": m.readiness_summaries(c),
                "decision_count": len(c.decisions),
            },
        )

    @app.get("/companies/{company_id}/stage-intelligence", response_class=HTMLResponse, include_in_schema=False)
    def stage_intelligence_fast(company_id: int, request: Request, db: Session = Depends(get_db)):
        c = db.scalar(
            select(Company)
            .where(Company.id == company_id)
            .options(
                selectinload(Company.timeline),
                selectinload(Company.module_fits),
                selectinload(Company.intake_files),
                selectinload(Company.readiness_evidence),
                selectinload(Company.decisions),
            )
        )
        if not c:
            return HTMLResponse("Company not found", 404)
        from . import main as m
        return TEMPLATES.TemplateResponse(
            request=request,
            name="stage_intelligence.html",
            context={"company": c, "stage_info": m.stage_intelligence(c), "stages": m.PIPELINE_STAGES},
        )

    @app.get("/companies/{company_id}/readiness-framework", response_class=HTMLResponse, include_in_schema=False)
    def readiness_fast(company_id: int, request: Request, db: Session = Depends(get_db)):
        c = db.scalar(
            select(Company)
            .where(Company.id == company_id)
            .options(
                selectinload(Company.module_fits),
                selectinload(Company.intake_files),
                selectinload(Company.readiness_evidence),
            )
        )
        if not c:
            return HTMLResponse("Company not found", 404)
        from . import main as m
        return TEMPLATES.TemplateResponse(
            request=request,
            name="readiness_framework.html",
            context={
                "company": c,
                "summaries": m.readiness_summaries(c),
                "files_received": len(c.intake_files),
                "status_options": m.READINESS_STATUS_OPTIONS,
            },
        )

    @app.get("/companies/{company_id}/solution-blueprint", response_class=HTMLResponse, include_in_schema=False)
    def blueprint_fast(company_id: int, request: Request, db: Session = Depends(get_db)):
        c = db.scalar(
            select(Company)
            .where(Company.id == company_id)
            .options(
                selectinload(Company.memory_items),
                selectinload(Company.module_fits),
                selectinload(Company.intake_files),
                selectinload(Company.readiness_evidence),
                selectinload(Company.decisions),
            )
        )
        if not c:
            return HTMLResponse("Company not found", 404)
        from . import main as m
        c.decisions.sort(key=lambda x: x.decided_at, reverse=True)
        selected = m.selected_module_nos(c)
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
            operating_spine = [{"en": "Operational Data", "zh": "營運資料"}, {"en": "AI Operations", "zh": "AI 營運"}]
        return TEMPLATES.TemplateResponse(
            request=request,
            name="solution_blueprint.html",
            context={
                "company": c,
                "memory": m.memory_groups(c),
                "summaries": m.readiness_summaries(c),
                "phases": phases,
                "operating_spine": operating_spine,
                "decisions": c.decisions,
                "files_received": len(c.intake_files),
                "blueprint_mode": "Evidence-informed" if c.intake_files else "Hypothesis · evidence pending",
            },
        )
