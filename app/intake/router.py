"""HTTP routes for lifecycle-safe source-first intake and human review."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import delete, select, update
from sqlalchemy.orm import selectinload

from ..db import SessionLocal
from ..lifecycle.schema import intake_source_lifecycle
from ..lifecycle.service import (
    active_intake_files,
    ensure_lifecycle_rows,
    reconcile_stage,
)
from ..lineage.schema import ingestion_jobs
from ..lineage.service import create_ingestion_job, manifest_from_notes
from ..models import Company, IntakeFile, TimelineEvent
from ..v082_runtime import (
    EXPECTED_DATA_CATEGORIES,
    TEMPLATES,
    VALID_CATEGORIES,
    _clear_file_evidence,
    _find_existing_file,
    _memory_groups,
)
from .service import DOMAIN_VERSION, MANIFEST_PREFIX, inspection_engine, merge_notes_preserving_source


def install_intake_routes(app: FastAPI) -> None:
    if getattr(app.state, "ps_intake_routes_installed", False):
        return
    app.state.ps_intake_routes_installed = True

    @app.get("/companies/{company_id}/data-intake", response_class=HTMLResponse, include_in_schema=False)
    def data_intake(company_id: int, request: Request):
        db = SessionLocal()
        try:
            company = db.scalar(
                select(Company).where(Company.id == company_id).options(
                    selectinload(Company.memory_items),
                    selectinload(Company.intake_files),
                )
            )
            if not company:
                return HTMLResponse("Company not found", 404)

            ensure_lifecycle_rows(db, company_id)
            company.intake_files.sort(key=lambda item: item.received_at, reverse=True)
            active = active_intake_files(db, company_id, list(company.intake_files))
            old_stage = company.stage
            if reconcile_stage(db, company, list(company.intake_files)):
                db.add(TimelineEvent(
                    company_id=company.id,
                    event_type="Stage Reconcile",
                    title=f"Lifecycle-aware intake stage reconciled to {company.stage}",
                    details=f"v{DOMAIN_VERSION} active-source gate" + (
                        f" · {old_stage} → {company.stage}" if old_stage != company.stage else ""
                    ),
                ))
            db.commit()

            received_categories = {item.category for item in active}
            needs_review = sum(1 for item in active if item.status != "Reviewed")
            return TEMPLATES.TemplateResponse(
                request=request,
                name="data_intake.html",
                context={
                    "company": company,
                    "expected_categories": EXPECTED_DATA_CATEGORIES,
                    "received_categories": received_categories,
                    "files_received": len(active),
                    "needs_review": needs_review,
                    "memory": _memory_groups(company.memory_items),
                    "intake_version": DOMAIN_VERSION,
                },
            )
        finally:
            db.close()

    @app.post("/companies/{company_id}/data-intake/register", include_in_schema=False)
    def register_or_refresh_file(
        company_id: int,
        filename: str = Form(...),
        category: str = Form(...),
        source: str = Form("Manual"),
        notes: str = Form(""),
    ):
        db = SessionLocal()
        try:
            company = db.get(Company, company_id)
            if not company:
                return HTMLResponse("Company not found", 404)
            if category not in VALID_CATEGORIES:
                return HTMLResponse("Invalid data category", 400)

            clean_name = filename.strip()
            existing = _find_existing_file(db, company_id, clean_name, notes)
            if existing:
                old_category = existing.category
                old_notes = existing.notes
                _clear_file_evidence(db, company_id, existing.filename)
                existing.filename = clean_name
                existing.category = category
                existing.source = source.strip() or existing.source or "Manual"
                if "Source Vault" in (old_notes or "") or MANIFEST_PREFIX in (old_notes or ""):
                    if "Source Vault" not in existing.source:
                        existing.source = (existing.source + " + Source Vault")[:80]
                existing.notes = merge_notes_preserving_source(old_notes, notes)
                existing.status = "Needs Review"
                existing.received_at = datetime.utcnow()
                title = f"File inspection refreshed: {clean_name}"
                details = (
                    f"Category: {old_category} → {category}"
                    if old_category != category
                    else f"Category confirmed: {category}"
                )
            else:
                existing = IntakeFile(
                    company_id=company_id,
                    filename=clean_name,
                    category=category,
                    status="Needs Review" if notes.strip() else "Received",
                    source=source.strip() or "Manual",
                    notes=notes.strip() or None,
                )
                db.add(existing)
                title = f"Data file registered: {clean_name}"
                details = f"Category: {category}"

            db.flush()

            engine = inspection_engine(existing.notes, existing.source)
            if engine:
                job_type, engine_version = engine
                manifest = manifest_from_notes(existing.notes)
                source_id = str(manifest.get("source_id")) if manifest and manifest.get("source_id") else None
                create_ingestion_job(
                    db,
                    company_id=company_id,
                    job_type=job_type,
                    status="needs_review",
                    source_id=source_id,
                    intake_file_id=existing.id,
                    engine_version=engine_version,
                    result_summary=f"{clean_name} · {category} · saved inspection awaiting human review",
                )

            # Lifecycle state is the authoritative stage gate. Newly registered
            # files default ACTIVE except the explicitly migrated engineering fixtures.
            ensure_lifecycle_rows(db, company_id)
            all_files = list(
                db.scalars(select(IntakeFile).where(IntakeFile.company_id == company_id)).all()
            )
            old_stage = company.stage
            reconcile_stage(db, company, all_files)

            db.add(TimelineEvent(
                company_id=company_id,
                event_type="Data Intake",
                title=title,
                details=(
                    f"{details} · source-first lineage preserved when available"
                    f" · ingestion job recorded"
                    + (f" · Stage: {old_stage} → {company.stage}" if old_stage != company.stage else "")
                ),
            ))
            db.commit()
            return RedirectResponse(f"/companies/{company_id}/data-intake", 303)
        finally:
            db.close()

    @app.post("/companies/{company_id}/intake-files/{file_id}/review", include_in_schema=False)
    def mark_file_reviewed(company_id: int, file_id: int):
        db = SessionLocal()
        try:
            item = db.scalar(
                select(IntakeFile).where(
                    IntakeFile.id == file_id,
                    IntakeFile.company_id == company_id,
                )
            )
            company = db.get(Company, company_id)
            if not item or not company:
                return HTMLResponse("File or company not found", 404)

            duplicates = list(
                db.scalars(
                    select(IntakeFile).where(
                        IntakeFile.company_id == company_id,
                        IntakeFile.filename == item.filename,
                        IntakeFile.id != item.id,
                    )
                ).all()
            )
            for duplicate in duplicates:
                # Lifecycle rows are workflow metadata, so remove an orphan row
                # when collapsing duplicate IntakeFile registrations. SourceReference
                # provenance remains untouched.
                db.execute(
                    delete(intake_source_lifecycle).where(
                        intake_source_lifecycle.c.intake_file_id == duplicate.id
                    )
                )
                db.delete(duplicate)

            item.status = "Reviewed"
            db.flush()

            now = datetime.now(timezone.utc)
            db.execute(
                update(ingestion_jobs)
                .where(
                    ingestion_jobs.c.company_id == company_id,
                    ingestion_jobs.c.intake_file_id == item.id,
                    ingestion_jobs.c.status == "needs_review",
                )
                .values(
                    status="completed",
                    completed_at=now,
                    updated_at=now,
                    result_summary=f"Human review confirmed for {item.filename}",
                )
            )

            ensure_lifecycle_rows(db, company_id)
            files = list(
                db.scalars(
                    select(IntakeFile)
                    .where(IntakeFile.company_id == company_id)
                    .order_by(IntakeFile.id)
                ).all()
            )
            old_stage = company.stage
            reconcile_stage(db, company, files)
            db.add(TimelineEvent(
                company_id=company_id,
                event_type="Data Review",
                title=f"Human review confirmed: {item.filename}",
                details=(
                    f"Ingestion jobs awaiting review marked completed"
                    + (f" · Stage: {old_stage} → {company.stage}" if old_stage != company.stage else "")
                ),
            ))
            db.commit()
            return RedirectResponse(f"/companies/{company_id}/data-intake", 303)
        finally:
            db.close()


__all__ = ["install_intake_routes"]
