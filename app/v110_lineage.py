"""PrimeStride Client OS v1.1 first-class lineage registry.

Moves source provenance and ingestion execution history out of free-form
IntakeFile.notes into durable relational records while keeping the v1.0 manifest
format backward compatible during migration.

This module intentionally owns only two platform tables:
- source_references: immutable original-source identity and storage provenance
- ingestion_jobs: every parse/AI processing attempt and its lifecycle

The tables are additive and created with checkfirst=True so existing Client OS
data is untouched. Existing PS_SOURCE_VAULT_V1 manifests are backfilled into
source_references on install/read.
"""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
    insert,
    select,
    update,
)
from sqlalchemy.orm import Session

from .db import SessionLocal, engine
from .models import Company, IntakeFile

VERSION = "1.1.0"
MANIFEST_PREFIX = "PS_SOURCE_VAULT_V1:"

lineage_metadata = MetaData()

source_references = Table(
    "source_references",
    lineage_metadata,
    Column("id", Integer, primary_key=True),
    Column("source_id", String(80), nullable=False),
    Column("company_id", Integer, nullable=False),
    Column("intake_file_id", Integer, nullable=True),
    Column("tenant_key", String(120), nullable=True),
    Column("original_filename", String(300), nullable=False),
    Column("object_key", Text, nullable=False),
    Column("bucket", String(250), nullable=True),
    Column("sha256", String(64), nullable=False),
    Column("mime_type", String(180), nullable=True),
    Column("byte_size", BigInteger, nullable=True),
    Column("storage_provider", String(120), nullable=True),
    Column("immutable", Boolean, nullable=False, default=True),
    Column("parent_source_id", String(80), nullable=True),
    Column("stored_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("source_id", name="uq_source_references_source_id"),
)
Index("ix_source_references_company", source_references.c.company_id)
Index("ix_source_references_company_sha", source_references.c.company_id, source_references.c.sha256)
Index("ix_source_references_intake_file", source_references.c.intake_file_id)

ingestion_jobs = Table(
    "ingestion_jobs",
    lineage_metadata,
    Column("id", Integer, primary_key=True),
    Column("job_key", String(220), nullable=False),
    Column("company_id", Integer, nullable=False),
    Column("source_id", String(80), nullable=True),
    Column("intake_file_id", Integer, nullable=True),
    Column("job_type", String(60), nullable=False),
    Column("status", String(40), nullable=False),
    Column("engine_version", String(80), nullable=True),
    Column("model", String(160), nullable=True),
    Column("provider_job_id", String(220), nullable=True),
    Column("attempt", Integer, nullable=False, default=1),
    Column("error_code", String(120), nullable=True),
    Column("error_detail", Text, nullable=True),
    Column("result_summary", Text, nullable=True),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("job_key", name="uq_ingestion_jobs_job_key"),
)
Index("ix_ingestion_jobs_company", ingestion_jobs.c.company_id)
Index("ix_ingestion_jobs_source", ingestion_jobs.c.source_id)
Index("ix_ingestion_jobs_provider", ingestion_jobs.c.provider_job_id)
Index("ix_ingestion_jobs_company_status", ingestion_jobs.c.company_id, ingestion_jobs.c.status)

_schema_lock = threading.Lock()
_schema_ready = False


def _now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_lineage_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        lineage_metadata.create_all(bind=engine, checkfirst=True)
        _schema_ready = True


def manifest_from_notes(notes: str | None) -> dict[str, Any] | None:
    if not notes or MANIFEST_PREFIX not in notes:
        return None
    for line in notes.splitlines():
        if line.startswith(MANIFEST_PREFIX):
            try:
                value = json.loads(line[len(MANIFEST_PREFIX):])
                return value if isinstance(value, dict) else None
            except Exception:
                return None
    return None


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def record_source_reference(
    db: Session,
    *,
    company_id: int,
    intake_file_id: int | None,
    manifest: dict[str, Any],
) -> dict[str, Any]:
    """Upsert an immutable source reference from a Source Vault manifest."""
    ensure_lineage_schema()
    source_id = str(manifest.get("source_id") or "").strip()
    sha256 = str(manifest.get("sha256") or "").strip().lower()
    object_key = str(manifest.get("object_key") or "").strip()
    filename = str(manifest.get("original_filename") or "client-file").strip()
    if not source_id or len(sha256) != 64 or not object_key:
        raise ValueError("Source manifest is missing source_id, sha256, or object_key.")

    now = _now()
    values = {
        "source_id": source_id,
        "company_id": company_id,
        "intake_file_id": intake_file_id,
        "tenant_key": (str(manifest.get("tenant_key") or "").strip() or None),
        "original_filename": filename[:300],
        "object_key": object_key,
        "bucket": (str(manifest.get("bucket") or "").strip() or None),
        "sha256": sha256,
        "mime_type": (str(manifest.get("content_type") or "").strip() or None),
        "byte_size": int(manifest.get("bytes") or 0) or None,
        "storage_provider": (str(manifest.get("storage_provider") or "").strip() or None),
        "immutable": bool(manifest.get("immutable", True)),
        "parent_source_id": (str(manifest.get("parent_source_id") or "").strip() or None),
        "stored_at": _coerce_datetime(manifest.get("stored_at")),
        "updated_at": now,
    }
    existing = db.execute(
        select(source_references).where(source_references.c.source_id == source_id)
    ).mappings().first()
    if existing:
        # Identity/object provenance are immutable; only attach workflow linkage
        # or fill fields that were absent during an earlier backfill.
        safe_update = {
            "intake_file_id": intake_file_id or existing.get("intake_file_id"),
            "tenant_key": values["tenant_key"] or existing.get("tenant_key"),
            "mime_type": values["mime_type"] or existing.get("mime_type"),
            "byte_size": values["byte_size"] or existing.get("byte_size"),
            "storage_provider": values["storage_provider"] or existing.get("storage_provider"),
            "updated_at": now,
        }
        db.execute(
            update(source_references)
            .where(source_references.c.source_id == source_id)
            .values(**safe_update)
        )
    else:
        db.execute(insert(source_references).values(created_at=now, **values))

    row = db.execute(
        select(source_references).where(source_references.c.source_id == source_id)
    ).mappings().one()
    return dict(row)


def backfill_source_references(db: Session, company_id: int | None = None) -> int:
    ensure_lineage_schema()
    stmt = select(IntakeFile)
    if company_id is not None:
        stmt = stmt.where(IntakeFile.company_id == company_id)
    count = 0
    for item in db.scalars(stmt).all():
        manifest = manifest_from_notes(item.notes)
        if not manifest:
            continue
        try:
            before = db.execute(
                select(source_references.c.id).where(
                    source_references.c.source_id == str(manifest.get("source_id") or "")
                )
            ).first()
            record_source_reference(
                db,
                company_id=item.company_id,
                intake_file_id=item.id,
                manifest=manifest,
            )
            if not before:
                count += 1
        except Exception as exc:
            print(f"[lineage backfill] IntakeFile {item.id}: {exc!r}")
    return count


def find_source_by_id(db: Session, company_id: int, source_id: str) -> dict[str, Any] | None:
    ensure_lineage_schema()
    row = db.execute(
        select(source_references).where(
            source_references.c.company_id == company_id,
            source_references.c.source_id == source_id,
        )
    ).mappings().first()
    return dict(row) if row else None


def find_source_by_sha(db: Session, company_id: int, sha256: str) -> dict[str, Any] | None:
    ensure_lineage_schema()
    row = db.execute(
        select(source_references)
        .where(
            source_references.c.company_id == company_id,
            source_references.c.sha256 == sha256.lower(),
        )
        .order_by(source_references.c.id.desc())
    ).mappings().first()
    return dict(row) if row else None


def create_ingestion_job(
    db: Session,
    *,
    company_id: int,
    job_type: str,
    status: str,
    source_id: str | None = None,
    intake_file_id: int | None = None,
    engine_version: str | None = None,
    model: str | None = None,
    provider_job_id: str | None = None,
    job_key: str | None = None,
    result_summary: str | None = None,
) -> dict[str, Any]:
    ensure_lineage_schema()
    now = _now()
    key = job_key or provider_job_id or f"job_{uuid.uuid4().hex}"
    existing = db.execute(
        select(ingestion_jobs).where(ingestion_jobs.c.job_key == key)
    ).mappings().first()
    if existing:
        return dict(existing)
    db.execute(insert(ingestion_jobs).values(
        job_key=key,
        company_id=company_id,
        source_id=source_id,
        intake_file_id=intake_file_id,
        job_type=job_type,
        status=status,
        engine_version=engine_version,
        model=model,
        provider_job_id=provider_job_id,
        attempt=1,
        result_summary=result_summary,
        started_at=now if status in {"processing", "queued"} else None,
        completed_at=now if status in {"completed", "failed", "cancelled"} else None,
        created_at=now,
        updated_at=now,
    ))
    row = db.execute(
        select(ingestion_jobs).where(ingestion_jobs.c.job_key == key)
    ).mappings().one()
    return dict(row)


def update_ingestion_job(
    db: Session,
    *,
    job_key: str | None = None,
    provider_job_id: str | None = None,
    status: str | None = None,
    source_id: str | None = None,
    intake_file_id: int | None = None,
    error_code: str | None = None,
    error_detail: str | None = None,
    result_summary: str | None = None,
) -> dict[str, Any] | None:
    ensure_lineage_schema()
    if not job_key and not provider_job_id:
        return None
    where = ingestion_jobs.c.job_key == job_key if job_key else ingestion_jobs.c.provider_job_id == provider_job_id
    existing = db.execute(select(ingestion_jobs).where(where)).mappings().first()
    if not existing:
        return None
    now = _now()
    values: dict[str, Any] = {"updated_at": now}
    if status is not None:
        values["status"] = status
        if status in {"completed", "failed", "cancelled", "incomplete"}:
            values["completed_at"] = now
    if source_id is not None:
        values["source_id"] = source_id
    if intake_file_id is not None:
        values["intake_file_id"] = intake_file_id
    if error_code is not None:
        values["error_code"] = error_code[:120]
    if error_detail is not None:
        values["error_detail"] = error_detail[:5000]
    if result_summary is not None:
        values["result_summary"] = result_summary[:5000]
    db.execute(update(ingestion_jobs).where(where).values(**values))
    row = db.execute(select(ingestion_jobs).where(where)).mappings().first()
    return dict(row) if row else None


def _jsonable(row: dict[str, Any]) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for key, value in row.items():
        out[key] = value.isoformat() if isinstance(value, datetime) else value
    return out


def install_v110_lineage(app: FastAPI) -> None:
    if getattr(app.state, "ps_v110_lineage_installed", False):
        return
    app.state.ps_v110_lineage_installed = True
    try:
        ensure_lineage_schema()
        db = SessionLocal()
        try:
            added = backfill_source_references(db)
            if added:
                db.commit()
            else:
                db.rollback()
        finally:
            db.close()
    except Exception as exc:
        print(f"[v1.1 lineage bootstrap] warning: {exc!r}")

    @app.get("/api/lineage/status", include_in_schema=False)
    def lineage_status():
        try:
            ensure_lineage_schema()
            return {
                "ok": True,
                "version": VERSION,
                "source_references": "ready",
                "ingestion_jobs": "ready",
                "migration": "manifest-backfill-compatible",
            }
        except Exception as exc:
            return JSONResponse({
                "ok": False,
                "version": VERSION,
                "error": "Lineage registry schema is unavailable.",
                "detail": f"{type(exc).__name__}: {str(exc)[:1000]}",
            }, status_code=503)

    @app.get("/companies/{company_id}/lineage", include_in_schema=False)
    def company_lineage(company_id: int):
        db = SessionLocal()
        try:
            if not db.get(Company, company_id):
                return JSONResponse({"error": "Company not found."}, status_code=404)
            backfill_source_references(db, company_id)
            db.commit()
            sources = [dict(r) for r in db.execute(
                select(source_references)
                .where(source_references.c.company_id == company_id)
                .order_by(source_references.c.id.desc())
                .limit(100)
            ).mappings().all()]
            jobs = [dict(r) for r in db.execute(
                select(ingestion_jobs)
                .where(ingestion_jobs.c.company_id == company_id)
                .order_by(ingestion_jobs.c.id.desc())
                .limit(100)
            ).mappings().all()]
            return {
                "ok": True,
                "version": VERSION,
                "source_count": len(sources),
                "job_count": len(jobs),
                "sources": [_jsonable(x) for x in sources],
                "jobs": [_jsonable(x) for x in jobs],
            }
        finally:
            db.close()
