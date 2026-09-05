"""PrimeStride Client OS source-first runtime glue.

Overrides intake registration so deterministic/AI review saves do not overwrite
Source Vault lineage. v1.1 also records deterministic browser inspections as
first-class ingestion_jobs awaiting human review.
"""
from __future__ import annotations

import re
from datetime import datetime

from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, RedirectResponse

from .db import SessionLocal
from .models import IntakeFile, TimelineEvent
from .v082_runtime import DATA_STAGES, VALID_CATEGORIES, _clear_file_evidence, _find_existing_file
from .v110_lineage import create_ingestion_job, manifest_from_notes

VERSION = "1.1.0"
MANIFEST_PREFIX = "PS_SOURCE_VAULT_V1:"


def _merge_notes_preserving_source(old_notes: str | None, new_notes: str | None) -> str | None:
    new_lines = [line for line in (new_notes or "").splitlines() if line and not line.startswith(MANIFEST_PREFIX)]
    manifests = [line for line in (old_notes or "").splitlines() if line.startswith(MANIFEST_PREFIX)]
    merged = new_lines + manifests
    text = "\n".join(merged).strip()
    return text or None


def _inspection_engine(notes: str | None, source: str | None) -> tuple[str, str] | None:
    text = f"{source or ''} {notes or ''}"
    if re.search(r"messy-data inspection|Local browser inspection|sheet=|mapped=", text, re.I):
        match = re.search(r"v(0\.8(?:\.\d+)?)", text, re.I)
        return "deterministic_inspection", (match.group(1) if match else "0.8.4")
    if re.search(r"AI multimodal|multimodal analysis|model=", text, re.I):
        match = re.search(r"v(0\.9(?:\.\d+)*)", text, re.I)
        return "multimodal_ai_review", (match.group(1) if match else "0.9.4.1")
    return None


def install_v101_runtime(app: FastAPI) -> None:
    if getattr(app.state, "ps_v101_runtime_installed", False):
        return
    app.state.ps_v101_runtime_installed = True

    @app.post("/companies/{company_id}/data-intake/register", include_in_schema=False)
    def register_or_refresh_file_source_first(
        company_id: int,
        filename: str = Form(...),
        category: str = Form(...),
        source: str = Form("Manual"),
        notes: str = Form(""),
    ):
        db = SessionLocal()
        try:
            from .models import Company
            c = db.get(Company, company_id)
            if not c:
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
                existing.notes = _merge_notes_preserving_source(old_notes, notes)
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

            db.flush()

            # v1.1: a saved inspection is a processing attempt, not just text in
            # IntakeFile.notes. Keep it in needs_review until Confirm Review.
            engine = _inspection_engine(existing.notes, existing.source)
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

            if c.stage in DATA_STAGES:
                c.stage = "Data Received"
                c.next_action = "Review file classification, detected fields and canonical mappings"
            db.add(TimelineEvent(
                company_id=company_id,
                event_type="Data Intake",
                title=title,
                details=f"{details} · source-first lineage preserved when available · ingestion job recorded",
            ))
            db.commit()
            return RedirectResponse(f"/companies/{company_id}/data-intake", 303)
        finally:
            db.close()
