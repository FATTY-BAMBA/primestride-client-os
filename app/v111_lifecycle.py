"""PrimeStride Client OS v1.1.1 source lifecycle.

Adds an explicit lifecycle for every intake source so engineering/test material
can coexist with real client evidence without contaminating operational counts,
stage gates, or readiness calculations.

States:
- active   -> real/current client evidence; counts toward readiness
- test     -> synthetic/engineering validation; never counts toward readiness
- archived -> retained for audit/history; excluded from the current assessment

The lifecycle table is additive and leaves immutable SourceReference/R2 objects
untouched. Existing known PrimeStride test fixtures for company 1 are migrated to
TEST on first use; all other sources default to ACTIVE.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from sqlalchemy import Column, DateTime, Index, Integer, MetaData, String, Table, UniqueConstraint, insert, select, update
from sqlalchemy.orm import selectinload

from .db import SessionLocal, engine
from .models import Company, IntakeFile, ReadinessEvidence, TimelineEvent

VERSION = "1.1.1"
VALID_STATES = {"active", "test", "archived"}

lifecycle_metadata = MetaData()
intake_source_lifecycle = Table(
    "intake_source_lifecycle",
    lifecycle_metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, nullable=False),
    Column("intake_file_id", Integer, nullable=False),
    Column("source_id", String(80), nullable=True),
    Column("state", String(24), nullable=False),
    Column("reason", String(500), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("intake_file_id", name="uq_intake_source_lifecycle_file"),
)
Index("ix_intake_source_lifecycle_company", intake_source_lifecycle.c.company_id)
Index("ix_intake_source_lifecycle_company_state", intake_source_lifecycle.c.company_id, intake_source_lifecycle.c.state)
Index("ix_intake_source_lifecycle_source", intake_source_lifecycle.c.source_id)

_schema_lock = threading.Lock()
_schema_ready = False

# Explicit migration of the four engineering fixtures used while building the
# 菘佑 flow. We intentionally do not apply broad filename heuristics to future
# client data.
_COMPANY1_TEST_FIXTURES = {
    "SourceVault_Test.txt",
    "ChatGPT Image Sep 4, 2026, 11_05_41 PM.png",
    "PrimeStride_Test_02_Work_Orders_Messy (1).csv",
    "PrimeStride_Test_01_Quote_History.xlsx",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_lifecycle_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        lifecycle_metadata.create_all(bind=engine, checkfirst=True)
        _schema_ready = True


def _source_id_for_file(db, item: IntakeFile) -> str | None:
    try:
        from .v110_lineage import source_references, ensure_lineage_schema
        ensure_lineage_schema()
        row = db.execute(
            select(source_references.c.source_id).where(source_references.c.intake_file_id == item.id)
        ).first()
        return str(row[0]) if row and row[0] else None
    except Exception:
        return None


def _default_state(item: IntakeFile) -> tuple[str, str | None]:
    if item.company_id == 1 and item.filename in _COMPANY1_TEST_FIXTURES:
        return "test", "PrimeStride engineering fixture created before real client data intake."
    return "active", None


def ensure_lifecycle_rows(db, company_id: int | None = None) -> int:
    ensure_lifecycle_schema()
    stmt = select(IntakeFile)
    if company_id is not None:
        stmt = stmt.where(IntakeFile.company_id == company_id)
    added = 0
    for item in db.scalars(stmt).all():
        exists = db.execute(
            select(intake_source_lifecycle.c.id).where(intake_source_lifecycle.c.intake_file_id == item.id)
        ).first()
        if exists:
            continue
        state, reason = _default_state(item)
        now = _now()
        db.execute(insert(intake_source_lifecycle).values(
            company_id=item.company_id,
            intake_file_id=item.id,
            source_id=_source_id_for_file(db, item),
            state=state,
            reason=reason,
            created_at=now,
            updated_at=now,
        ))
        added += 1
    return added


def lifecycle_rows(db, company_id: int) -> list[dict[str, Any]]:
    ensure_lifecycle_rows(db, company_id)
    rows = db.execute(
        select(intake_source_lifecycle)
        .where(intake_source_lifecycle.c.company_id == company_id)
        .order_by(intake_source_lifecycle.c.intake_file_id.desc())
    ).mappings().all()
    return [dict(r) for r in rows]


def lifecycle_map(db, company_id: int) -> dict[int, dict[str, Any]]:
    return {int(r["intake_file_id"]): r for r in lifecycle_rows(db, company_id)}


def active_intake_files(db, company_id: int, files: list[IntakeFile] | None = None) -> list[IntakeFile]:
    states = lifecycle_map(db, company_id)
    if files is None:
        files = list(db.scalars(select(IntakeFile).where(IntakeFile.company_id == company_id)).all())
    return [f for f in files if states.get(f.id, {}).get("state", "active") == "active"]


def inactive_source_filenames(db, company_id: int) -> set[str]:
    states = lifecycle_map(db, company_id)
    inactive_ids = {fid for fid, row in states.items() if row.get("state") != "active"}
    if not inactive_ids:
        return set()
    return set(db.scalars(
        select(IntakeFile.filename).where(IntakeFile.company_id == company_id, IntakeFile.id.in_(inactive_ids))
    ).all())


def effective_readiness_evidence(c: Company, db) -> list[ReadinessEvidence]:
    inactive = inactive_source_filenames(db, c.id)
    if not inactive:
        return list(c.readiness_evidence)
    return [e for e in c.readiness_evidence if not e.source or e.source not in inactive]


class _CompanyView:
    """Read-only delegate with lifecycle-filtered operational collections."""
    def __init__(self, company: Company, *, intake_files, readiness_evidence):
        self._company = company
        self.intake_files = intake_files
        self.readiness_evidence = readiness_evidence

    def __getattr__(self, name):
        return getattr(self._company, name)


def _reconcile_stage(db, company: Company, all_files: list[IntakeFile]) -> bool:
    if company.stage not in {"Data Requested", "Data Received", "Data Readiness"}:
        return False
    active = active_intake_files(db, company.id, all_files)
    inactive_names = inactive_source_filenames(db, company.id)
    evidence_count = int(sum(
        1 for e in db.scalars(select(ReadinessEvidence).where(ReadinessEvidence.company_id == company.id)).all()
        if e.status != "awaiting" and (not e.source or e.source not in inactive_names)
    ))
    if not active:
        target = "Data Requested"
        next_action = "Await initial sample-data upload"
    elif all(f.status == "Reviewed" for f in active) and evidence_count > 0:
        target = "Data Readiness"
        next_action = "Complete evidence review and identify only blocking data gaps"
    else:
        target = "Data Received"
        next_action = "Review active file classification, detected fields and canonical mappings"
    changed = company.stage != target or company.next_action != next_action
    company.stage = target
    company.next_action = next_action
    return changed


def _jsonable(row: dict[str, Any]) -> dict[str, Any]:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in row.items()}


def install_v111_lifecycle(app: FastAPI) -> None:
    if getattr(app.state, "ps_v111_lifecycle_installed", False):
        return
    app.state.ps_v111_lifecycle_installed = True
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
        print(f"[v1.1.1 lifecycle bootstrap] warning: {exc!r}")

    @app.get("/companies/{company_id}/source-lifecycle", include_in_schema=False)
    def source_lifecycle(company_id: int):
        db = SessionLocal()
        try:
            company = db.get(Company, company_id)
            if not company:
                return JSONResponse({"error": "Company not found."}, status_code=404)
            rows = lifecycle_rows(db, company_id)
            db.commit()
            files = {f.id: f for f in db.scalars(select(IntakeFile).where(IntakeFile.company_id == company_id)).all()}
            items = []
            counts = {"active": 0, "test": 0, "archived": 0}
            for row in rows:
                state = row.get("state") if row.get("state") in VALID_STATES else "active"
                counts[state] += 1
                item = files.get(int(row["intake_file_id"]))
                items.append({
                    **_jsonable(row),
                    "filename": item.filename if item else None,
                    "category": item.category if item else None,
                    "file_status": item.status if item else None,
                })
            return {"ok": True, "version": VERSION, "counts": counts, "items": items}
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
                    source_id=current.get("source_id") or _source_id_for_file(db, item),
                    updated_at=_now(),
                )
            )
            all_files = list(db.scalars(select(IntakeFile).where(IntakeFile.company_id == company_id)).all())
            old_stage = company.stage
            _reconcile_stage(db, company, all_files)
            db.add(TimelineEvent(
                company_id=company_id,
                event_type="Source Lifecycle",
                title=f"Source lifecycle changed: {item.filename}",
                details=f"{previous} → {state}" + (f" · Stage: {old_stage} → {company.stage}" if old_stage != company.stage else ""),
            ))
            db.commit()
            return {"ok": True, "version": VERSION, "file_id": file_id, "state": state, "stage": company.stage}
        finally:
            db.close()

    # Register lifecycle-aware views before the legacy routes in main/v0.8.2.
    @app.get("/companies/{company_id}/data-intake", response_class=HTMLResponse, include_in_schema=False)
    def lifecycle_data_intake(company_id: int, request: Request):
        from .v082_runtime import EXPECTED_DATA_CATEGORIES, TEMPLATES, _memory_groups
        db = SessionLocal()
        try:
            c = db.scalar(
                select(Company).where(Company.id == company_id).options(
                    selectinload(Company.memory_items),
                    selectinload(Company.intake_files),
                )
            )
            if not c:
                return HTMLResponse("Company not found", 404)
            ensure_lifecycle_rows(db, company_id)
            c.intake_files.sort(key=lambda x: x.received_at, reverse=True)
            active = active_intake_files(db, company_id, list(c.intake_files))
            old_stage = c.stage
            if _reconcile_stage(db, c, list(c.intake_files)):
                db.add(TimelineEvent(
                    company_id=c.id,
                    event_type="Stage Reconcile",
                    title=f"Lifecycle-aware intake stage reconciled to {c.stage}",
                    details=f"v{VERSION} active-source gate" + (f" · {old_stage} → {c.stage}" if old_stage != c.stage else ""),
                ))
            db.commit()
            received_categories = {f.category for f in active}
            needs_review = sum(1 for f in active if f.status != "Reviewed")
            return TEMPLATES.TemplateResponse(
                request=request,
                name="data_intake.html",
                context={
                    "company": c,
                    "expected_categories": EXPECTED_DATA_CATEGORIES,
                    "received_categories": received_categories,
                    "files_received": len(active),
                    "needs_review": needs_review,
                    "memory": _memory_groups(c.memory_items),
                    "intake_version": VERSION,
                },
            )
        finally:
            db.close()

    @app.get("/companies/{company_id}/readiness-framework", response_class=HTMLResponse, include_in_schema=False)
    def lifecycle_readiness(company_id: int, request: Request):
        from .main import company_stmt, ensure_v04_memory, render, readiness_summaries, READINESS_STATUS_OPTIONS
        db = SessionLocal()
        try:
            c = db.scalar(company_stmt(company_id))
            if not c:
                return HTMLResponse("Company not found", 404)
            ensure_v04_memory(db, c)
            ensure_lifecycle_rows(db, company_id)
            db.commit()
            c = db.scalar(company_stmt(company_id))
            active = active_intake_files(db, company_id, list(c.intake_files))
            evidence = effective_readiness_evidence(c, db)
            view = _CompanyView(c, intake_files=active, readiness_evidence=evidence)
            return render(request, "readiness_framework.html", {
                "company": c,
                "summaries": readiness_summaries(view),
                "files_received": len(active),
                "status_options": READINESS_STATUS_OPTIONS,
            })
        finally:
            db.close()

    @app.get("/companies/{company_id}", response_class=HTMLResponse, include_in_schema=False)
    def lifecycle_company_detail(company_id: int, request: Request):
        from .main import (
            MODULES, PIPELINE_STAGES, company_stmt, discovery_completion, ensure_v04_memory,
            ensure_v05_decisions, memory_groups, readiness_summaries, render, stage_intelligence,
        )
        db = SessionLocal()
        try:
            c = db.scalar(company_stmt(company_id))
            if not c:
                return HTMLResponse("Company not found", 404)
            ensure_v04_memory(db, c)
            ensure_v05_decisions(db, c)
            ensure_lifecycle_rows(db, company_id)
            db.commit()
            c = db.scalar(company_stmt(company_id))
            c.pains.sort(key=lambda x: x.rank)
            c.module_fits.sort(key=lambda x: x.module_no)
            c.readiness.sort(key=lambda x: x.module_no)
            c.timeline.sort(key=lambda x: x.created_at, reverse=True)
            c.meetings.sort(key=lambda x: x.completed_at, reverse=True)
            c.memory_items.sort(key=lambda x: x.id)
            c.intake_files.sort(key=lambda x: x.received_at, reverse=True)
            c.decisions.sort(key=lambda x: x.decided_at, reverse=True)
            active = active_intake_files(db, company_id, list(c.intake_files))
            evidence = effective_readiness_evidence(c, db)
            view = _CompanyView(c, intake_files=active, readiness_evidence=evidence)
            return render(request, "company.html", {
                "company": c,
                "stages": PIPELINE_STAGES,
                "modules": MODULES,
                "completion": discovery_completion(c.discovery),
                "memory": memory_groups(c),
                "files_received": len(active),
                "stage_info": stage_intelligence(view),
                "readiness_summaries": readiness_summaries(view),
                "decision_count": len(c.decisions),
            })
        finally:
            db.close()
