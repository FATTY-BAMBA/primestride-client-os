"""HTTP routes for ingestion-job recovery and retry."""
from urllib.error import HTTPError, URLError

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from ..db import SessionLocal
from .service import (
    DOMAIN_VERSION,
    OPENAI_API_KEY,
    RECOVERABLE_STATUSES,
    RETRYABLE_STATUSES,
    _RESPONSE_ID_RE,
    get_job,
    get_source,
    get_source_lifecycle,
    insert_retry_job,
    jsonable,
    read_original,
    recover_provider_state,
    start_provider_retry,
)


def install_job_routes(app: FastAPI) -> None:
    if getattr(app.state, "ps_job_routes_installed", False):
        return
    app.state.ps_job_routes_installed = True

    @app.post("/companies/{company_id}/ingestion-jobs/{job_key}/retry", include_in_schema=False)
    def retry_job(company_id: int, job_key: str):
        if not OPENAI_API_KEY:
            return JSONResponse({"error": "AI intake is not configured.", "code": "ai_not_configured"}, status_code=503)
        db = SessionLocal()
        try:
            job = get_job(db, company_id, job_key)
            if not job:
                return JSONResponse({"error": "Ingestion job not found."}, status_code=404)
            if str(job.get("status")) not in RETRYABLE_STATUSES:
                return JSONResponse({"error": "Only failed, cancelled, or incomplete jobs can be retried.", "code": "job_not_retryable"}, status_code=409)
            if str(job.get("job_type")) != "multimodal_ai":
                return JSONResponse({"error": "Automatic retry is currently available for multimodal AI jobs only.", "code": "retry_not_supported_for_job_type"}, status_code=409)
            source = get_source(db, company_id, job.get("source_id"))
            if not source:
                return JSONResponse({"error": "This job is not linked to a retained SourceReference, so Client OS cannot safely retry it without another upload.", "code": "retry_source_missing"}, status_code=409)
            lifecycle = get_source_lifecycle(db, company_id, source.get("intake_file_id"))
            if lifecycle == "archived":
                return JSONResponse({"error": "Archived sources cannot be retried until they are reactivated.", "code": "source_archived"}, status_code=409)

            try:
                raw, mime, filename = read_original(source)
            except OverflowError as exc:
                return JSONResponse({"error": str(exc), "code": "retry_requires_browser_preprocess"}, status_code=413)
            except TypeError as exc:
                return JSONResponse({"error": str(exc), "code": "unsupported_type"}, status_code=415)
            except Exception as exc:
                return JSONResponse({"error": "Could not read the retained original for retry.", "code": "source_read_failed", "detail": f"{type(exc).__name__}: {str(exc)[:900]}"}, status_code=502)

            try:
                data = start_provider_retry(raw, mime, filename)
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
            new_job = insert_retry_job(db, job, response_id, str(data.get("status") or "queued"))
            db.commit()
            return {
                "ok": True,
                "version": DOMAIN_VERSION,
                "message": "Retry started from the same retained original.",
                "source_id": job.get("source_id"),
                "previous_job": job_key,
                "job": jsonable(new_job),
            }
        finally:
            db.close()

    @app.post("/companies/{company_id}/ingestion-jobs/{job_key}/recover", include_in_schema=False)
    def recover_job(company_id: int, job_key: str):
        if not OPENAI_API_KEY:
            return JSONResponse({"error": "AI intake is not configured.", "code": "ai_not_configured"}, status_code=503)
        db = SessionLocal()
        try:
            job = get_job(db, company_id, job_key)
            if not job:
                return JSONResponse({"error": "Ingestion job not found."}, status_code=404)
            if str(job.get("status")) not in RECOVERABLE_STATUSES:
                return JSONResponse({"error": "Only queued or processing jobs need provider-state recovery.", "code": "job_not_recoverable"}, status_code=409)
            if str(job.get("job_type")) != "multimodal_ai" or not job.get("provider_job_id"):
                return JSONResponse({"error": "This job has no recoverable AI provider state.", "code": "recovery_not_supported"}, status_code=409)

            try:
                status, result = recover_provider_state(db, str(job["provider_job_id"]))
            except HTTPError as exc:
                return JSONResponse({"error": "Could not recover provider state.", "code": "provider_error", "provider_status": exc.code}, status_code=502)
            except (URLError, TimeoutError) as exc:
                return JSONResponse({"error": "Provider state check timed out.", "code": "provider_poll_timeout", "detail": str(exc)}, status_code=504)

            db.commit()
            return {
                "ok": True,
                "version": DOMAIN_VERSION,
                "job_key": job_key,
                "status": status,
                "result_available": bool(result),
                "message": "Provider state recovered." if status not in RECOVERABLE_STATUSES else "Job is still running.",
            }
        finally:
            db.close()
