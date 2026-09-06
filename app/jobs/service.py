"""Stable ingestion-job services for recovery and retry."""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from urllib.request import Request as UrlRequest

from sqlalchemy import func, insert, select, update

from ..ai.schema import OUTPUT_SCHEMA_092
from ..ai.service import (
    MAX_AI_FILE_BYTES,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_RESPONSES_URL,
    RESPONSE_ID_RE,
    SUPPORTED_FILE_TYPES,
    SUPPORTED_IMAGE_TYPES,
    extract_output_text,
    provider_json,
    section_prompt,
    validate_section_result,
)
from ..lifecycle.schema import intake_source_lifecycle
from ..lifecycle.service import ensure_lifecycle_rows
from ..lineage.schema import ingestion_jobs, source_references
from ..lineage.service import ensure_lineage_schema, update_ingestion_job
from ..storage.service import BUCKET, s3_client

DOMAIN_VERSION = "1.3.4"
RETRYABLE_STATUSES = {"failed", "cancelled", "incomplete"}
RECOVERABLE_STATUSES = {"queued", "processing"}
_RESPONSE_ID_RE = RESPONSE_ID_RE


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def get_job(db, company_id: int, job_key: str):
    ensure_lineage_schema()
    return db.execute(
        select(ingestion_jobs).where(
            ingestion_jobs.c.company_id == company_id,
            ingestion_jobs.c.job_key == job_key,
        )
    ).mappings().first()


def get_source(db, company_id: int, source_id: str | None):
    if not source_id:
        return None
    return db.execute(
        select(source_references).where(
            source_references.c.company_id == company_id,
            source_references.c.source_id == source_id,
        )
    ).mappings().first()


def get_source_lifecycle(db, company_id: int, intake_file_id: int | None) -> str:
    if not intake_file_id:
        return "active"
    ensure_lifecycle_rows(db, company_id)
    row = db.execute(
        select(intake_source_lifecycle.c.state).where(
            intake_source_lifecycle.c.company_id == company_id,
            intake_source_lifecycle.c.intake_file_id == intake_file_id,
        )
    ).first()
    return str(row[0]) if row and row[0] else "active"


def read_original(source) -> tuple[bytes, str, str]:
    bucket = str(source.get("bucket") or BUCKET or "").strip()
    object_key = str(source.get("object_key") or "").strip()
    filename = str(source.get("original_filename") or "client-document").strip()
    mime = str(source.get("mime_type") or "application/octet-stream").lower().strip()
    if not bucket or not object_key:
        raise ValueError("SourceReference has no private object location.")
    if mime not in SUPPORTED_FILE_TYPES:
        raise TypeError(f"Unsupported retry source type: {mime or 'unknown'}")
    obj = s3_client().get_object(Bucket=bucket, Key=object_key)
    raw = obj["Body"].read(MAX_AI_FILE_BYTES + 1)
    if len(raw) > MAX_AI_FILE_BYTES:
        raise OverflowError("Retained original exceeds the direct AI retry limit and requires the browser preprocessing path.")
    if not raw:
        raise ValueError("Retained source object is empty.")
    return raw, mime, filename


def start_provider_retry(raw: bytes, mime: str, filename: str) -> dict:
    b64 = base64.b64encode(raw).decode("ascii")
    if mime in SUPPORTED_IMAGE_TYPES:
        file_block = {"type": "input_image", "image_url": f"data:{mime};base64,{b64}", "detail": "high"}
    else:
        file_block = {"type": "input_file", "file_data": b64, "filename": filename}

    payload = {
        "model": OPENAI_MODEL,
        "background": True,
        "store": False,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 6000,
        "input": [{
            "role": "user",
            "content": [
                {"type": "input_text", "text": section_prompt("")},
                file_block,
            ],
        }],
        "text": {
            "format": {
                "type": "json_schema",
                "name": "primestride_section_aware_intake",
                "description": "Section-aware multimodal evidence extraction for PrimeStride Client OS.",
                "strict": True,
                "schema": OUTPUT_SCHEMA_092,
            }
        },
    }
    req = UrlRequest(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"},
        method="POST",
    )
    return provider_json(req, timeout=25)


def insert_retry_job(db, old_job, response_id: str, provider_status: str) -> dict:
    same_source = ingestion_jobs.c.source_id == old_job.get("source_id") if old_job.get("source_id") else ingestion_jobs.c.intake_file_id == old_job.get("intake_file_id")
    max_attempt = db.scalar(
        select(func.max(ingestion_jobs.c.attempt)).where(
            ingestion_jobs.c.company_id == old_job["company_id"],
            ingestion_jobs.c.job_type == old_job["job_type"],
            same_source,
        )
    ) or int(old_job.get("attempt") or 1)
    now = now_utc()
    status = provider_status if provider_status in {"queued", "processing"} else "queued"
    db.execute(insert(ingestion_jobs).values(
        job_key=response_id,
        company_id=old_job["company_id"],
        source_id=old_job.get("source_id"),
        intake_file_id=old_job.get("intake_file_id"),
        job_type=old_job["job_type"],
        status=status,
        engine_version=DOMAIN_VERSION,
        model=OPENAI_MODEL,
        provider_job_id=response_id,
        attempt=int(max_attempt) + 1,
        result_summary=f"Retry of {old_job['job_key']}",
        started_at=now,
        completed_at=None,
        created_at=now,
        updated_at=now,
    ))
    previous_summary = str(old_job.get("result_summary") or "").strip()
    retry_note = f"Retried as {response_id}"
    db.execute(
        update(ingestion_jobs)
        .where(ingestion_jobs.c.id == old_job["id"])
        .values(result_summary=(f"{previous_summary} · {retry_note}" if previous_summary else retry_note)[:5000], updated_at=now)
    )
    return dict(db.execute(select(ingestion_jobs).where(ingestion_jobs.c.job_key == response_id)).mappings().one())


def recover_provider_state(db, provider_id: str) -> tuple[str, dict | None]:
    req = UrlRequest(
        f"{OPENAI_RESPONSES_URL.rstrip('/')}/{provider_id}",
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
        method="GET",
    )
    data = provider_json(req, timeout=20)
    status = str(data.get("status") or "processing")
    result = None
    if status == "completed":
        try:
            parsed = json.loads(extract_output_text(data))
            result = validate_section_result(parsed)
            update_ingestion_job(db, provider_job_id=provider_id, status="completed", result_summary=str(result.get("summary") or "")[:4000])
        except Exception as exc:
            status = "failed"
            update_ingestion_job(db, provider_job_id=provider_id, status="failed", error_code="invalid_ai_response", error_detail=f"{type(exc).__name__}: {str(exc)[:1200]}")
    elif status in {"failed", "cancelled", "incomplete"}:
        detail = data.get("error") or data.get("incomplete_details") or {}
        update_ingestion_job(db, provider_job_id=provider_id, status=status, error_code=f"provider_{status}", error_detail=json.dumps(detail, ensure_ascii=False)[:4000])
    else:
        normalized = status if status in {"queued", "processing"} else "processing"
        update_ingestion_job(db, provider_job_id=provider_id, status=normalized)
        status = normalized
    return status, result


def jsonable(row: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in row.items()}


__all__ = [
    "DOMAIN_VERSION",
    "RETRYABLE_STATUSES",
    "RECOVERABLE_STATUSES",
    "OPENAI_API_KEY",
    "OPENAI_RESPONSES_URL",
    "_RESPONSE_ID_RE",
    "get_job",
    "get_source",
    "get_source_lifecycle",
    "read_original",
    "start_provider_retry",
    "insert_retry_job",
    "recover_provider_state",
    "jsonable",
]
