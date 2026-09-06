"""Stable lineage services for source provenance and ingestion attempts."""
from __future__ import annotations

import json
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert, inspect, select, update
from sqlalchemy.orm import Session

from ..db import RUNTIME_SCHEMA_BOOTSTRAP, engine
from ..models import IntakeFile
from .schema import ingestion_jobs, lineage_metadata, source_references

MANIFEST_PREFIX = "PS_SOURCE_VAULT_V1:"

_schema_lock = threading.Lock()
_schema_ready = False


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ensure_lineage_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        if RUNTIME_SCHEMA_BOOTSTRAP:
            lineage_metadata.create_all(bind=engine, checkfirst=True)
        else:
            db_inspector = inspect(engine)
            missing = [
                name for name in ("source_references", "ingestion_jobs")
                if not db_inspector.has_table(name)
            ]
            if missing:
                raise RuntimeError(
                    "Lineage schema is not migrated. Missing: "
                    + ", ".join(missing)
                    + ". Run `alembic upgrade head`."
                )
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
    """Upsert workflow linkage without mutating immutable source identity."""
    ensure_lineage_schema()
    source_id = str(manifest.get("source_id") or "").strip()
    sha256 = str(manifest.get("sha256") or "").strip().lower()
    object_key = str(manifest.get("object_key") or "").strip()
    filename = str(manifest.get("original_filename") or "client-file").strip()
    if not source_id or len(sha256) != 64 or not object_key:
        raise ValueError("Source manifest is missing source_id, sha256, or object_key.")

    now = now_utc()
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
    now = now_utc()
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
    now = now_utc()
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


def jsonable(row: dict[str, Any]) -> dict[str, Any]:
    return {key: (value.isoformat() if isinstance(value, datetime) else value) for key, value in row.items()}
