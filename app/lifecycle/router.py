"""HTTP routes for stable source lifecycle state."""
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import select, update

from ..db import SessionLocal
from ..models import Company, IntakeFile, TimelineEvent, PIPELINE_STAGES
from .schema import intake_source_lifecycle
from .service import (
    DOMAIN_VERSION,
    VALID_STATES,
    CompanyView,
    active_intake_files,
    effective_readiness_evidence,
    ensure_lifecycle_rows,
    ensure_lifecycle_schema,
    jsonable,
    lifecycle_rows,
    now_utc,
    reconcile_stage,
    source_id_for_file,
)


def install_lifecycle_routes(app: FastAPI) -> None:
    if getattr(app.state, "ps_lifecycle_routes_installed", False):
        return
    app.state.ps_lifecycle_routes_installed = True

    try:
        ensure_lifecycle_schema()
        db = SessionLocal()
        try:
            if ensure_lifecycle_rows(db):
                db.commit()
            else:
                db.rollback()
        finally:
            db.close()
    except Exception as exc:
        print(f"[lifecycle bootstrap] warning: {exc!r}")

    @app.get("/companies/{company_id}/source-lifecycle", include_in_schema=False)
    def source_lifecycle(company_id: int):
        db = SessionLocal()
        try:
            company = db.get(Company, company_id)
            if not company:
                return JSONResponse({"error": "Company not found."}, status_code=404)
            rows = lifecycle_rows(db, company_id)
            db.commit()
            files = {
                item.id: item
                for item in db.scalars(
                    select(IntakeFile).where(IntakeFile.company_id == company_id)
                ).all()
            }
            items = []
            counts = {"active": 0, "test": 0, "archived": 0}
            for row in rows:
                state = row.get("state") if row.get("state") in VALID_STATES else "active"
                counts[state] += 1
                item = files.get(int(row["intake_file_id"]))
                items.append({
                    **jsonable(row),
                    "filename": item.filename if item else None,
                    "category": item.category if item else None,
                    "file_status": item.status if item else None,
                })
            return {
                "ok": True,
                "version": DOMAIN_VERSION,
                "domain": "lifecycle",
                "counts": counts,
                "items": items,
            }
        finally:
            db.close()

    @app.post("/companies/{company_id}/intake-files/{file_id}/lifecycle", include_in_schema=False)
    def set_source_lifecycle(
        company_id: int,
        file_id: int,
        state: str = Form(...),
        reason: str = Form(""),
    ):
        state = state.strip().lower()
        if state not in VALID_STATES:
            return JSONResponse({"error": "Invalid source lifecycle state."}, status_code=400)
        db = SessionLocal()
        try:
            company = db.get(Company, company_id)
            item = db.get(IntakeFile, file_id)
            if not company or not item or item.company_id != company_id:
                return JSONResponse({"error": "Source file not found."}, status_code=404)

            ensure_lifecycle_rows(db, company_id)
            current = db.execute(
                select(intake_source_lifecycle).where(intake_source_lifecycle.c.intake_file_id == file_id)
            ).mappings().one()
            previous = str(current.get("state") or "active")
            db.execute(
                update(intake_source_lifecycle)
                .where(intake_source_lifecycle.c.intake_file_id == file_id)
                .values(
                    state=state,
                    reason=(reason.strip()[:500] or current.get("reason")),
                    source_id=current.get("source_id") or source_id_for_file(db, item),
                    updated_at=now_utc(),
                )
            )

            all_files = list(
                db.scalars(select(IntakeFile).where(IntakeFile.company_id == company_id)).all()
            )
            old_stage = company.stage
            reconcile_stage(db, company, all_files)
            db.add(TimelineEvent(
                company_id=company_id,
                event_type="Source Lifecycle",
                title=f"Source lifecycle changed: {item.filename}",
                details=f"{previous} → {state}" + (
                    f" · Stage: {old_stage} → {company.stage}" if old_stage != company.stage else ""
                ),
            ))
            db.commit()
            return {
                "ok": True,
                "version": DOMAIN_VERSION,
                "file_id": file_id,
                "state": state,
                "stage": company.stage,
            }
        finally:
            db.close()

    # Lifecycle-safe account overview. Data Intake itself is owned by app.intake.
    @app.get("/companies/{company_id}", response_class=HTMLResponse, include_in_schema=False)
    def lifecycle_company_detail(company_id: int, request: Request):
        from .. import main as m

        db = SessionLocal()
        try:
            company = db.scalar(m.company_stmt(company_id))
            if not company:
                return HTMLResponse("Company not found", 404)

            m.ensure_v04_memory(db, company)
            m.ensure_v05_decisions(db, company)
            ensure_lifecycle_rows(db, company_id)
            old_stage = company.stage
            if reconcile_stage(db, company, list(company.intake_files)):
                db.add(TimelineEvent(
                    company_id=company.id,
                    event_type="Stage Reconcile",
                    title=f"Lifecycle-aware account stage reconciled to {company.stage}",
                    details=f"v{DOMAIN_VERSION} active-source gate" + (
                        f" · {old_stage} → {company.stage}" if old_stage != company.stage else ""
                    ),
                ))
            db.commit()

            company = db.scalar(m.company_stmt(company_id))
            company.pains.sort(key=lambda x: x.rank)
            company.module_fits.sort(key=lambda x: x.module_no)
            company.readiness.sort(key=lambda x: x.module_no)
            company.timeline.sort(key=lambda x: x.created_at, reverse=True)
            company.meetings.sort(key=lambda x: x.completed_at, reverse=True)
            company.memory_items.sort(key=lambda x: x.id)
            company.intake_files.sort(key=lambda x: x.received_at, reverse=True)
            company.decisions.sort(key=lambda x: x.decided_at, reverse=True)

            active = active_intake_files(db, company_id, list(company.intake_files))
            evidence = effective_readiness_evidence(company, db)
            view = CompanyView(company, intake_files=active, readiness_evidence=evidence)

            return m.render(request, "company.html", {
                "company": company,
                "stages": PIPELINE_STAGES,
                "modules": m.MODULES,
                "completion": m.discovery_completion(company.discovery),
                "memory": m.memory_groups(company),
                "files_received": len(active),
                "stage_info": m.stage_intelligence(view),
                "readiness_summaries": m.readiness_summaries(view),
                "decision_count": len(company.decisions),
            })
        finally:
            db.close()


__all__ = ["install_lifecycle_routes"]
