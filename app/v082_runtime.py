"""PrimeStride Client OS v0.8.2 runtime extension.

This module keeps the prototype moving without a schema migration: it adds a
correction/review lifecycle for intake files, enforces stage gates, and serves a
lightweight Data Intake query. The temporary FastAPI bootstrap hook lives in
`db.py`; once the app is reorganized around explicit routers this module should
be included normally with `app.include_router(...)`.
"""
from __future__ import annotations

import re
import time
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session, selectinload

from .db import DATABASE_URL, get_db
from .models import (
    ClientMemory,
    Company,
    IntakeFile,
    Readiness,
    ReadinessEvidence,
    TimelineEvent,
)

BASE_DIR = Path(__file__).resolve().parent
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))
VERSION = "0.8.2"

EXPECTED_DATA_CATEGORIES = [
    ("customers", "Customers & Contacts", "客戶與聯絡人"),
    ("products", "Products / Specs / Materials", "產品／規格／材料"),
    ("quotes", "Quotations / Pricing / Costs", "報價／價格／成本"),
    ("work_orders", "Orders / Work Orders", "訂單／工單"),
    ("reports", "Management Reports", "管理報表"),
    ("other", "Other Process Material", "其他流程資料"),
]
VALID_CATEGORIES = {key for key, _, _ in EXPECTED_DATA_CATEGORIES}
DATA_STAGES = {"Data Requested", "Data Received", "Data Readiness"}
HASH_RE = re.compile(r"sha256=([0-9a-f]{64})", re.I)


def _memory_groups(items: list[ClientMemory]) -> dict[str, list[ClientMemory]]:
    groups = {"known": [], "unknown": [], "do_not_ask": [], "next_question": []}
    for item in items:
        if item.active:
            groups.setdefault(item.kind, []).append(item)
    return groups


def _active_evidence_count(db: Session, company_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(ReadinessEvidence.id)).where(
                ReadinessEvidence.company_id == company_id,
                ReadinessEvidence.status != "awaiting",
            )
        )
        or 0
    )


def _reconcile_stage(db: Session, company: Company, files: list[IntakeFile] | None = None) -> bool:
    """Keep stage truth aligned with the intake definition of done.

    Data Requested -> no file yet.
    Data Received  -> files exist, but every file is not yet human-reviewed or
                      there is no approved readiness evidence yet.
    Data Readiness -> every registered file is Reviewed AND at least one
                      readiness evidence item has been approved.
    """
    if company.stage not in DATA_STAGES:
        return False

    files = files if files is not None else list(
        db.scalars(
            select(IntakeFile).where(IntakeFile.company_id == company.id).order_by(IntakeFile.id)
        ).all()
    )
    evidence_count = _active_evidence_count(db, company.id)

    if not files:
        target = "Data Requested"
        next_action = "Await initial sample-data upload"
    elif all(f.status == "Reviewed" for f in files) and evidence_count > 0:
        target = "Data Readiness"
        next_action = "Complete evidence review and identify only blocking data gaps"
    else:
        target = "Data Received"
        next_action = "Review file classification, detected fields and canonical mappings"

    changed = company.stage != target or company.next_action != next_action
    company.stage = target
    company.next_action = next_action
    return changed


def _clear_file_evidence(db: Session, company_id: int, filename: str) -> None:
    """Remove evidence whose current provenance is this file.

    v0.8 stores one current evidence row per module/criterion, so source equality
    is the safest reversible boundary available before full SourceReference
    lineage lands in v1.0.
    """
    db.execute(
        delete(ReadinessEvidence).where(
            ReadinessEvidence.company_id == company_id,
            ReadinessEvidence.source == filename,
        )
    )
    # Avoid displaying a stale aggregate after evidence is corrected/removed.
    db.execute(delete(Readiness).where(Readiness.company_id == company_id))


def _hash_from_notes(notes: str | None) -> str | None:
    if not notes:
        return None
    match = HASH_RE.search(notes)
    return match.group(1).lower() if match else None


def _find_existing_file(db: Session, company_id: int, filename: str, notes: str | None) -> IntakeFile | None:
    file_hash = _hash_from_notes(notes)
    candidates = list(
        db.scalars(
            select(IntakeFile)
            .where(IntakeFile.company_id == company_id)
            .order_by(IntakeFile.id.desc())
        ).all()
    )
    for item in candidates:
        if item.filename == filename:
            return item
        if file_hash and _hash_from_notes(item.notes) == file_hash:
            return item
    return None


def install_v082(app: FastAPI) -> None:
    if getattr(app.state, "ps_v082_installed", False):
        return
    app.state.ps_v082_installed = True

    @app.middleware("http")
    async def ps_v082_timing(request: Request, call_next):
        started = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - started) * 1000
        response.headers["Server-Timing"] = f"primestride;dur={elapsed_ms:.1f}"
        response.headers["X-PrimeStride-Version"] = VERSION
        return response

    # Registered before main.py adds its prototype route, so Starlette resolves
    # this lightweight version first for Data Intake.
    @app.get("/companies/{company_id}/data-intake", response_class=HTMLResponse, include_in_schema=False)
    def data_intake_fast(company_id: int, request: Request, db: Session = Depends(get_db)):
        c = db.scalar(
            select(Company)
            .where(Company.id == company_id)
            .options(
                selectinload(Company.memory_items),
                selectinload(Company.intake_files),
            )
        )
        if not c:
            return HTMLResponse("Company not found", 404)

        c.intake_files.sort(key=lambda x: x.received_at, reverse=True)
        if _reconcile_stage(db, c, c.intake_files):
            db.add(
                TimelineEvent(
                    company_id=c.id,
                    event_type="Stage Reconcile",
                    title=f"Intake stage reconciled to {c.stage}",
                    details="v0.8.2 definition-of-done gate",
                )
            )
            db.commit()

        received_categories = {f.category for f in c.intake_files}
        needs_review = sum(1 for f in c.intake_files if f.status != "Reviewed")
        return TEMPLATES.TemplateResponse(
            request=request,
            name="data_intake.html",
            context={
                "company": c,
                "expected_categories": EXPECTED_DATA_CATEGORIES,
                "received_categories": received_categories,
                "files_received": len(c.intake_files),
                "needs_review": needs_review,
                "memory": _memory_groups(c.memory_items),
                "intake_version": VERSION,
            },
        )

    # Override prototype registration with idempotent register/update behavior.
    @app.post("/companies/{company_id}/data-intake/register", include_in_schema=False)
    def register_or_refresh_file(
        company_id: int,
        filename: str = Form(...),
        category: str = Form(...),
        source: str = Form("Manual"),
        notes: str = Form(""),
        db: Session = Depends(get_db),
    ):
        c = db.get(Company, company_id)
        if not c:
            return HTMLResponse("Company not found", 404)
        if category not in VALID_CATEGORIES:
            return HTMLResponse("Invalid data category", 400)

        clean_name = filename.strip()
        existing = _find_existing_file(db, company_id, clean_name, notes)
        if existing:
            old_category = existing.category
            _clear_file_evidence(db, company_id, existing.filename)
            existing.filename = clean_name
            existing.category = category
            existing.source = source.strip() or "Manual"
            existing.notes = notes.strip() or None
            existing.status = "Needs Review"
            existing.received_at = datetime.utcnow()
            title = f"File inspection refreshed: {clean_name}"
            details = f"Category: {old_category} → {category}" if old_category != category else f"Category confirmed: {category}"
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

        if c.stage in DATA_STAGES:
            c.stage = "Data Received"
            c.next_action = "Review file classification, detected fields and canonical mappings"
        db.add(TimelineEvent(company_id=company_id, event_type="Data Intake", title=title, details=details))
        db.commit()
        return RedirectResponse(f"/companies/{company_id}/data-intake", 303)

    @app.post("/companies/{company_id}/intake-files/{file_id}/reclassify", include_in_schema=False)
    def reclassify_file(
        company_id: int,
        file_id: int,
        category: str = Form(...),
        db: Session = Depends(get_db),
    ):
        if category not in VALID_CATEGORIES:
            return HTMLResponse("Invalid data category", 400)
        item = db.scalar(
            select(IntakeFile).where(IntakeFile.id == file_id, IntakeFile.company_id == company_id)
        )
        c = db.get(Company, company_id)
        if not item or not c:
            return HTMLResponse("File or company not found", 404)

        old = item.category
        if old != category:
            _clear_file_evidence(db, company_id, item.filename)
            item.category = category
        item.status = "Needs Review"
        if c.stage in DATA_STAGES:
            c.stage = "Data Received"
            c.next_action = "Review corrected classification and mappings"
        db.add(
            TimelineEvent(
                company_id=company_id,
                event_type="Data Correction",
                title=f"File reclassified: {item.filename}",
                details=f"{old} → {category}; prior evidence from this file superseded",
            )
        )
        db.commit()
        return RedirectResponse(f"/companies/{company_id}/data-intake#file-{file_id}", 303)

    @app.post("/companies/{company_id}/intake-files/{file_id}/review", include_in_schema=False)
    def mark_file_reviewed(company_id: int, file_id: int, db: Session = Depends(get_db)):
        item = db.scalar(
            select(IntakeFile).where(IntakeFile.id == file_id, IntakeFile.company_id == company_id)
        )
        c = db.get(Company, company_id)
        if not item or not c:
            return HTMLResponse("File or company not found", 404)

        # Collapse accidental duplicate registrations of the same filename,
        # keeping the explicitly reviewed row.
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
        files = list(
            db.scalars(
                select(IntakeFile).where(IntakeFile.company_id == company_id).order_by(IntakeFile.id)
            ).all()
        )
        old_stage = c.stage
        _reconcile_stage(db, c, files)
        db.add(
            TimelineEvent(
                company_id=company_id,
                event_type="Data Review",
                title=f"File review confirmed: {item.filename}",
                details=f"Classification: {item.category}" + (f" · Stage: {old_stage} → {c.stage}" if old_stage != c.stage else ""),
            )
        )
        db.commit()
        return RedirectResponse(f"/companies/{company_id}/data-intake#file-{file_id}", 303)

    @app.post("/companies/{company_id}/intake-files/{file_id}/remove", include_in_schema=False)
    def remove_file(company_id: int, file_id: int, db: Session = Depends(get_db)):
        item = db.scalar(
            select(IntakeFile).where(IntakeFile.id == file_id, IntakeFile.company_id == company_id)
        )
        c = db.get(Company, company_id)
        if not item or not c:
            return HTMLResponse("File or company not found", 404)

        filename = item.filename
        _clear_file_evidence(db, company_id, filename)
        db.delete(item)
        db.flush()
        remaining = list(
            db.scalars(
                select(IntakeFile).where(IntakeFile.company_id == company_id).order_by(IntakeFile.id)
            ).all()
        )
        old_stage = c.stage
        _reconcile_stage(db, c, remaining)
        db.add(
            TimelineEvent(
                company_id=company_id,
                event_type="Data Correction",
                title=f"File removed from intake: {filename}",
                details=f"Evidence sourced only from this file was removed" + (f" · Stage: {old_stage} → {c.stage}" if old_stage != c.stage else ""),
            )
        )
        db.commit()
        return RedirectResponse(f"/companies/{company_id}/data-intake", 303)

    @app.get("/health", include_in_schema=False)
    def health_v082():
        db_kind = "postgresql" if DATABASE_URL.startswith("postgres") else "sqlite-demo"
        return {"status": "ok", "service": "PrimeStride Client OS", "version": VERSION, "database": db_kind}
