"""Page-specific read paths for Client OS v0.8.5.

These routes are registered before the prototype routes in main.py, so the same
URLs use narrower queries and avoid the old commit + full reload pattern.

v0.8.5 also overlays an honest readiness model: incomplete evidence is shown as
an evidence-coverage percentage plus a readiness range instead of a misleading
"100% provisional" score.
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


GAP_REQUEST_COPY = {
    (4, "pricing_rules"): ("Pricing rules / exception logic", "Closes the remaining quoting logic gap without asking for more quote history."),
    (5, "order_reference"): ("Order / customer reference", "Confirms how accepted quotes, orders and work orders connect."),
    (6, "kpi_definitions"): ("Existing management report or KPI definition", "Shows which management numbers are considered authoritative."),
    (6, "revenue"): ("Trusted revenue field or report", "Needed before revenue analysis can be treated as operational truth."),
    (6, "margin"): ("Margin / gross-profit definition", "Confirms how management defines profitability before AI interprets it."),
    (6, "order_history"): ("Order history / order-level dataset", "Fills the operational link between quote history and work-order history."),
}


def _honest_summary(summary: dict) -> dict:
    """Convert the prototype reviewed-only score into an honest min/max range.

    Awaiting evidence stays in the denominator. It contributes 0 to the minimum
    and its full weight to the maximum. Partial contributes 50%; missing 0%;
    not_required is excluded from the denominator.
    """
    required_total = 0.0
    reviewed_weight = 0.0
    earned_weight = 0.0
    awaiting_weight = 0.0

    available_items = []
    partial_items = []
    missing_items = []
    awaiting_items = []

    for criterion in summary["criteria"]:
        status = criterion["status"]
        weight = float(criterion["weight"])
        if status == "not_required":
            continue
        required_total += weight
        if status == "available":
            reviewed_weight += weight
            earned_weight += weight
            available_items.append(criterion)
        elif status == "partial":
            reviewed_weight += weight
            earned_weight += weight * 0.5
            partial_items.append(criterion)
        elif status == "missing":
            reviewed_weight += weight
            missing_items.append(criterion)
        else:
            awaiting_weight += weight
            awaiting_items.append(criterion)

    coverage = (reviewed_weight / required_total * 100.0) if required_total else 100.0
    minimum = (earned_weight / required_total * 100.0) if required_total else 100.0
    maximum = ((earned_weight + awaiting_weight) / required_total * 100.0) if required_total else 100.0
    final = not awaiting_items

    out = dict(summary)
    out.update(
        {
            "coverage": coverage,
            "range_min": minimum,
            "range_max": maximum,
            "final": final,
            "display_score": minimum if final else None,
            "available_items": available_items,
            "partial_items": partial_items,
            "missing_items": missing_items,
            "awaiting_items": awaiting_items,
            "confirmed_weight": earned_weight,
            "unknown_weight": awaiting_weight,
        }
    )
    return out


def _honest_summaries(m, c: Company) -> list[dict]:
    return [_honest_summary(s) for s in m.readiness_summaries(c)]


def _gap_intelligence(summaries: list[dict]) -> dict:
    """Turn readiness evidence into a compact next-gap / do-not-ask brief."""
    gaps = []
    do_not_ask = []
    known_by_module = []

    for summary in summaries:
        available = summary["available_items"]
        partial = summary["partial_items"]
        missing = summary["missing_items"]
        awaiting = summary["awaiting_items"]

        known_by_module.append(
            {
                "module_no": summary["module_no"],
                "name": summary["name"],
                "coverage": summary["coverage"],
                "available": available[:5],
                "partial": partial,
                "missing": missing,
                "awaiting_count": len(awaiting),
            }
        )

        for criterion in available:
            do_not_ask.append(
                {
                    "module_no": summary["module_no"],
                    "label": criterion["label"],
                    "source": criterion.get("source"),
                }
            )

        for criterion in awaiting:
            module_no = summary["module_no"]
            key = criterion["key"]
            title, reason = GAP_REQUEST_COPY.get(
                (module_no, key),
                (criterion["label"], f"This criterion is still unevidenced for Module {module_no:02d}."),
            )
            # Prioritize nearly-complete modules first. Within a module, heavier
            # criteria come first; KPI definitions receive a small business-value
            # boost when analytics has several equal-weight gaps.
            business_boost = 8 if (module_no, key) == (6, "kpi_definitions") else 0
            priority = summary["coverage"] * 10 + float(criterion["weight"]) + business_boost
            gaps.append(
                {
                    "module_no": module_no,
                    "key": key,
                    "title": title,
                    "reason": reason,
                    "weight": criterion["weight"],
                    "priority": priority,
                }
            )

    gaps.sort(key=lambda x: (-x["priority"], x["module_no"], x["title"]))

    # Deduplicate common criteria such as Product/spec across modules so the
    # "do not ask again" panel reads like a client instruction, not a rubric dump.
    deduped = []
    seen = set()
    for item in do_not_ask:
        key = item["label"].lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(item)

    return {
        "known_by_module": known_by_module,
        "ask_next": gaps[:3],
        "remaining_gaps": gaps[3:],
        "do_not_ask": deduped[:12],
    }


def install_v082_perf(app: FastAPI) -> None:
    if getattr(app.state, "ps_v082_perf_installed", False):
        return
    app.state.ps_v082_perf_installed = True

    @app.get("/companies/{company_id}", response_class=HTMLResponse, include_in_schema=False)
    def company_detail_fast(company_id: int, request: Request, db: Session = Depends(get_db)):
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

        from . import main as m

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
                "readiness_summaries": _honest_summaries(m, c),
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
        summaries = _honest_summaries(m, c)
        return TEMPLATES.TemplateResponse(
            request=request,
            name="readiness_framework.html",
            context={
                "company": c,
                "summaries": summaries,
                "files_received": len(c.intake_files),
                "status_options": m.READINESS_STATUS_OPTIONS,
                "gap_intelligence": _gap_intelligence(summaries),
                "readiness_version": "0.8.5",
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
                "summaries": _honest_summaries(m, c),
                "phases": phases,
                "operating_spine": operating_spine,
                "decisions": c.decisions,
                "files_received": len(c.intake_files),
                "blueprint_mode": "Evidence-informed" if c.intake_files else "Hypothesis · evidence pending",
            },
        )
