"""v1.1 human-review gate integration.

Keeps the existing intake review behavior but also closes first-class
IngestionJob records when a reviewer explicitly confirms the file.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import select, update

from .db import SessionLocal
from .models import Company, IntakeFile, TimelineEvent
from .v082_runtime import _reconcile_stage
from .v110_lineage import ingestion_jobs

VERSION = "1.1.0"


def install_v110_review(app: FastAPI) -> None:
    if getattr(app.state, "ps_v110_review_installed", False):
        return
    app.state.ps_v110_review_installed = True

    # Register before the legacy v0.8.2 review route.
    @app.post("/companies/{company_id}/intake-files/{file_id}/review", include_in_schema=False)
    def mark_file_reviewed_v110(company_id: int, file_id: int):
        db = SessionLocal()
        try:
            item = db.scalar(
                select(IntakeFile).where(IntakeFile.id == file_id, IntakeFile.company_id == company_id)
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
            for dup in duplicates:
                db.delete(dup)

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

            files = list(
                db.scalars(
                    select(IntakeFile)
                    .where(IntakeFile.company_id == company_id)
                    .order_by(IntakeFile.id)
                ).all()
            )
            old_stage = company.stage
            _reconcile_stage(db, company, files)
            db.add(TimelineEvent(
                company_id=company_id,
                event_type="Data Review",
                title=f"File review confirmed: {item.filename}",
                details=(
                    f"Classification: {item.category} · v1.1 ingestion job closed"
                    + (f" · Stage: {old_stage} → {company.stage}" if old_stage != company.stage else "")
                ),
            ))
            db.commit()
            return RedirectResponse(f"/companies/{company_id}/data-intake#file-{file_id}", 303)
        finally:
            db.close()
