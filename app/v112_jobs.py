"""PrimeStride Client OS v1.1.2 ingestion job recovery + retry controls.

Adds safe operator actions on first-class ingestion jobs without duplicating the
retained source:
- refresh/recover the provider state for queued/processing multimodal AI jobs
- retry terminal failed/cancelled/incomplete multimodal AI jobs from the same
  immutable SourceReference / R2 original

A retry always creates a new IngestionJob attempt. The original SourceReference
and object key stay unchanged. Archived sources cannot be retried. Large images
that previously relied on browser compression must be re-run through Data Intake
instead of being silently changed server-side.
"""
from __future__ import annotations

import base64
import json
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import func, insert, select, update

from .db import SessionLocal
from .v09_ai import (
    MAX_AI_FILE_BYTES,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_RESPONSES_URL,
    SUPPORTED_FILE_TYPES,
    SUPPORTED_IMAGE_TYPES,
    _extract_output_text,
)
from .v092_ai import OUTPUT_SCHEMA_092, _prompt_092, _validated_result_092
from .v093_ai import _RESPONSE_ID_RE, _provider_json
from .v100_storage import BUCKET, _s3_client
from .v110_lineage import (
    ensure_lineage_schema,
    ingestion_jobs,
    source_references,
    update_ingestion_job,
)
from .v111_lifecycle import ensure_lifecycle_rows, intake_source_lifecycle

VERSION = "1.1.2"
RETRYABLE_STATUSES = {"failed", "cancelled", "incomplete"}
RECOVERABLE_STATUSES = {"queued", "processing"}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _job(db, company_id: int, job_key: str):
    ensure_lineage_schema()
    return db.execute(
        select(ingestion_jobs).where(
            ingestion_jobs.c.company_id == company_id,
            ingestion_jobs.c.job_key == job_key,
        )
    ).mappings().first()


def _source(db, company_id: int, source_id: str | None):
    if not source_id:
        return None
    return db.execute(
        select(source_references).where(
            source_references.c.company_id == company_id,
            source_references.c.source_id == source_id,
        )
    ).mappings().first()


def _source_lifecycle(db, company_id: int, intake_file_id: int | None) -> str:
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


def _read_original(source) -> tuple[bytes, str, str]:
    bucket = str(source.get("bucket") or BUCKET or "").strip()
    object_key = str(source.get("object_key") or "").strip()
    filename = str(source.get("original_filename") or "client-document").strip()
    mime = str(source.get("mime_type") or "application/octet-stream").lower().strip()
    if not bucket or not object_key:
        raise ValueError("SourceReference has no private object location.")
    if mime not in SUPPORTED_FILE_TYPES:
        raise TypeError(f"Unsupported retry source type: {mime or 'unknown'}")
    obj = _s3_client().get_object(Bucket=bucket, Key=object_key)
    raw = obj["Body"].read(MAX_AI_FILE_BYTES + 1)
    if len(raw) > MAX_AI_FILE_BYTES:
        raise OverflowError("Retained original exceeds the direct AI retry limit and requires the browser preprocessing path.")
    if not raw:
        raise ValueError("Retained source object is empty.")
    return raw, mime, filename


def _start_provider_retry(raw: bytes, mime: str, filename: str) -> dict:
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
                {"type": "input_text", "text": _prompt_092("")},
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
    return _provider_json(req, timeout=25)


def _insert_retry_job(db, old_job, response_id: str, provider_status: str) -> dict:
    same_source = ingestion_jobs.c.source_id == old_job.get("source_id") if old_job.get("source_id") else ingestion_jobs.c.intake_file_id == old_job.get("intake_file_id")
    max_attempt = db.scalar(
        select(func.max(ingestion_jobs.c.attempt)).where(
            ingestion_jobs.c.company_id == old_job["company_id"],
            ingestion_jobs.c.job_type == old_job["job_type"],
            same_source,
        )
    ) or int(old_job.get("attempt") or 1)
    now = _now()
    status = provider_status if provider_status in {"queued", "processing"} else "queued"
    db.execute(insert(ingestion_jobs).values(
        job_key=response_id,
        company_id=old_job["company_id"],
        source_id=old_job.get("source_id"),
        intake_file_id=old_job.get("intake_file_id"),
        job_type=old_job["job_type"],
        status=status,
        engine_version=VERSION,
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


def _jsonable(row: dict) -> dict:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in row.items()}


def install_v112_jobs(app: FastAPI) -> None:
    if getattr(app.state, "ps_v112_jobs_installed", False):
        return
    app.state.ps_v112_jobs_installed = True

    @app.post("/companies/{company_id}/ingestion-jobs/{job_key}/retry", include_in_schema=False)
    def retry_job(company_id: int, job_key: str):
        if not OPENAI_API_KEY:
            return JSONResponse({"error": "AI intake is not configured.", "code": "ai_not_configured"}, status_code=503)
        db = SessionLocal()
        try:
            job = _job(db, company_id, job_key)
            if not job:
                return JSONResponse({"error": "Ingestion job not found."}, status_code=404)
            if str(job.get("status")) not in RETRYABLE_STATUSES:
                return JSONResponse({"error": "Only failed, cancelled, or incomplete jobs can be retried.", "code": "job_not_retryable"}, status_code=409)
            if str(job.get("job_type")) != "multimodal_ai":
                return JSONResponse({"error": "Automatic retry is currently available for multimodal AI jobs only.", "code": "retry_not_supported_for_job_type"}, status_code=409)
            source = _source(db, company_id, job.get("source_id"))
            if not source:
                return JSONResponse({"error": "This job is not linked to a retained SourceReference, so Client OS cannot safely retry it without another upload.", "code": "retry_source_missing"}, status_code=409)
            lifecycle = _source_lifecycle(db, company_id, source.get("intake_file_id"))
            if lifecycle == "archived":
                return JSONResponse({"error": "Archived sources cannot be retried until they are reactivated.", "code": "source_archived"}, status_code=409)

            try:
                raw, mime, filename = _read_original(source)
            except OverflowError as exc:
                return JSONResponse({"error": str(exc), "code": "retry_requires_browser_preprocess"}, status_code=413)
            except TypeError as exc:
                return JSONResponse({"error": str(exc), "code": "unsupported_type"}, status_code=415)
            except Exception as exc:
                return JSONResponse({"error": "Could not read the retained original for retry.", "code": "source_read_failed", "detail": f"{type(exc).__name__}: {str(exc)[:900]}"}, status_code=502)

            try:
                data = _start_provider_retry(raw, mime, filename)
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")[:1800]
                return JSONResponse({"error": "AI provider rejected the retry request.", "code": "provider_error", "provider_status": exc.code, "detail": body}, status_code=502)
            except (URLError, TimeoutError) as exc:
                return JSONResponse({"error": "Could not start the retry with the AI provider.", "code": "provider_start_timeout", "detail": str(exc)}, status_code=504)
            except Exception as exc:
                return JSONResponse({"error": "Could not start the retry.", "code": "retry_start_failed", "detail": f"{type(exc).__name__}: {str(exc)[:900]}"}, status_code=502)

            response_id = str(data.get("id") or "")
            if not _RESPONSE_ID_RE.match(response_id):
                return JSONResponse({"error": "AI provider did not return a valid retry response id.", "code": "invalid_response_id"}, status_code=502)
            new_job = _insert_retry_job(db, job, response_id, str(data.get("status") or "queued"))
            db.commit()
            return {
                "ok": True,
                "version": VERSION,
                "message": "Retry started from the same retained original.",
                "source_id": job.get("source_id"),
                "previous_job": job_key,
                "job": _jsonable(new_job),
            }
        finally:
            db.close()

    @app.post("/companies/{company_id}/ingestion-jobs/{job_key}/recover", include_in_schema=False)
    def recover_job(company_id: int, job_key: str):
        if not OPENAI_API_KEY:
            return JSONResponse({"error": "AI intake is not configured.", "code": "ai_not_configured"}, status_code=503)
        db = SessionLocal()
        try:
            job = _job(db, company_id, job_key)
            if not job:
                return JSONResponse({"error": "Ingestion job not found."}, status_code=404)
            if str(job.get("status")) not in RECOVERABLE_STATUSES:
                return JSONResponse({"error": "Only queued or processing jobs need provider-state recovery.", "code": "job_not_recoverable"}, status_code=409)
            if str(job.get("job_type")) != "multimodal_ai" or not job.get("provider_job_id"):
                return JSONResponse({"error": "This job has no recoverable AI provider state.", "code": "recovery_not_supported"}, status_code=409)

            provider_id = str(job["provider_job_id"])
            req = UrlRequest(
                f"{OPENAI_RESPONSES_URL.rstrip('/')}/{provider_id}",
                headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
                method="GET",
            )
            try:
                data = _provider_json(req, timeout=20)
            except HTTPError as exc:
                return JSONResponse({"error": "Could not recover provider state.", "code": "provider_error", "provider_status": exc.code}, status_code=502)
            except (URLError, TimeoutError) as exc:
                return JSONResponse({"error": "Provider state check timed out.", "code": "provider_poll_timeout", "detail": str(exc)}, status_code=504)

            status = str(data.get("status") or "processing")
            result = None
            if status == "completed":
                try:
                    parsed = json.loads(_extract_output_text(data))
                    result = _validated_result_092(parsed)
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
            db.commit()
            return {
                "ok": True,
                "version": VERSION,
                "job_key": job_key,
                "status": status,
                "result_available": bool(result),
                "message": "Provider state recovered." if status not in RECOVERABLE_STATUSES else "Job is still running.",
            }
        finally:
            db.close()
