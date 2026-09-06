"""HTTP routes for stable multimodal AI intake.

Preserves the proven synchronous compatibility endpoint and the production
background start/poll flow. Every background run is mirrored into first-class
IngestionJob lineage and linked to the retained SourceReference when available.
"""
from __future__ import annotations

import base64
import hashlib
import json
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

from .schema import OUTPUT_SCHEMA_092
from .service import (
    DOMAIN_VERSION,
    MAX_AI_FILE_BYTES,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_RESPONSES_URL,
    RESPONSE_ID_RE,
    SUPPORTED_FILE_TYPES,
    SUPPORTED_IMAGE_TYPES,
    extract_output_text,
    link_source,
    provider_error_payload,
    provider_json,
    record_job_state,
    record_started_job,
    section_prompt,
    validate_section_result,
)


def _file_block(raw: bytes, mime: str, filename: str | None) -> dict:
    encoded = base64.b64encode(raw).decode("ascii")
    if mime in SUPPORTED_IMAGE_TYPES:
        return {
            "type": "input_image",
            "image_url": f"data:{mime};base64,{encoded}",
            "detail": "high",
        }
    return {
        "type": "input_file",
        "file_data": encoded,
        "filename": filename or "client-document.pdf",
    }


def _payload(raw: bytes, mime: str, filename: str | None, client_context: str, *, background: bool) -> dict:
    payload = {
        "model": OPENAI_MODEL,
        "store": False,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 6000 if background else 7500,
        "input": [{
            "role": "user",
            "content": [
                {"type": "input_text", "text": section_prompt(client_context)},
                _file_block(raw, mime, filename),
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
    if background:
        payload["background"] = True
    return payload


def _provider_request(payload: dict) -> UrlRequest:
    return UrlRequest(
        OPENAI_RESPONSES_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )


def _validate_upload(mime: str, raw: bytes):
    if mime not in SUPPORTED_FILE_TYPES:
        return JSONResponse({
            "error": f"Unsupported AI file type: {mime or 'unknown'}",
            "code": "unsupported_type",
        }, status_code=415)
    if len(raw) > MAX_AI_FILE_BYTES:
        return JSONResponse({
            "error": "AI preview limit is 3.5 MB after browser-side compression.",
            "code": "file_too_large",
        }, status_code=413)
    if not raw:
        return JSONResponse({"error": "The selected file is empty.", "code": "empty_file"}, status_code=400)
    return None


def install_ai_routes(app: FastAPI) -> None:
    if getattr(app.state, "ps_ai_routes_installed", False):
        return
    app.state.ps_ai_routes_installed = True

    @app.get("/api/ai-intake/status", include_in_schema=False)
    def ai_intake_status():
        return {
            "configured": bool(OPENAI_API_KEY),
            "model": OPENAI_MODEL if OPENAI_API_KEY else None,
            "max_file_bytes": MAX_AI_FILE_BYTES,
            "supported_types": sorted(SUPPORTED_FILE_TYPES),
            "version": DOMAIN_VERSION,
            "domain": "ai",
            "mode": "section-aware",
        }

    # Compatibility status endpoint retained for the v0.9.3 frontend contract.
    @app.get("/api/ai-intake/status-v093", include_in_schema=False)
    def ai_intake_background_status():
        return {
            "configured": bool(OPENAI_API_KEY),
            "model": OPENAI_MODEL if OPENAI_API_KEY else None,
            "max_file_bytes": MAX_AI_FILE_BYTES,
            "version": DOMAIN_VERSION,
            "mode": "background_polling",
            "job_registry": "first-class ingestion_jobs",
            "domain": "ai",
        }

    # Synchronous route remains for backward compatibility. The browser currently
    # intercepts this call and transparently uses /start + /jobs/{id} instead.
    @app.post("/companies/{company_id}/ai-intake/analyze", include_in_schema=False)
    async def ai_intake_analyze(
        company_id: int,
        file: UploadFile = File(...),
        client_context: str = Form(""),
    ):
        try:
            if not OPENAI_API_KEY:
                return JSONResponse({"error": "AI intake is not configured.", "code": "ai_not_configured"}, status_code=503)
            mime = (file.content_type or "").lower().strip()
            raw = await file.read(MAX_AI_FILE_BYTES + 1)
            invalid = _validate_upload(mime, raw)
            if invalid:
                return invalid

            try:
                data = provider_json(_provider_request(_payload(raw, mime, file.filename, client_context, background=False)), timeout=105)
            except HTTPError as exc:
                return JSONResponse(provider_error_payload(exc), status_code=502)
            except (URLError, TimeoutError) as exc:
                return JSONResponse({
                    "error": "AI provider could not be reached before the analysis timeout.",
                    "code": "provider_timeout",
                    "detail": str(exc),
                }, status_code=504)

            try:
                parsed = json.loads(extract_output_text(data))
                result = validate_section_result(parsed)
            except (ValueError, json.JSONDecodeError) as exc:
                return JSONResponse({
                    "error": "AI response could not be validated.",
                    "code": "invalid_ai_response",
                    "detail": str(exc),
                }, status_code=502)

            return {
                "ok": True,
                "version": DOMAIN_VERSION,
                "model": OPENAI_MODEL,
                "filename": file.filename,
                "mime_type": mime,
                "result": result,
            }
        except Exception as exc:
            return JSONResponse({
                "error": "AI intake failed before a validated result was produced.",
                "code": "ai_intake_internal_error",
                "detail": f"{type(exc).__name__}: {str(exc)[:1200]}",
            }, status_code=500)

    @app.post("/companies/{company_id}/ai-intake/start", include_in_schema=False)
    async def ai_intake_start(
        company_id: int,
        file: UploadFile = File(...),
        client_context: str = Form(""),
        source_id: str = Form(""),
    ):
        try:
            if not OPENAI_API_KEY:
                return JSONResponse({"error": "AI intake is not configured.", "code": "ai_not_configured"}, status_code=503)
            mime = (file.content_type or "").lower().strip()
            raw = await file.read(MAX_AI_FILE_BYTES + 1)
            invalid = _validate_upload(mime, raw)
            if invalid:
                return invalid

            raw_sha256 = hashlib.sha256(raw).hexdigest()
            linked_source_id, linked_intake_file_id = link_source(
                company_id,
                source_id.strip(),
                raw_sha256,
            )

            try:
                data = provider_json(_provider_request(_payload(raw, mime, file.filename, client_context, background=True)), timeout=25)
            except HTTPError as exc:
                return JSONResponse(provider_error_payload(exc), status_code=502)
            except (URLError, TimeoutError) as exc:
                return JSONResponse({
                    "error": "Could not start AI background analysis.",
                    "code": "provider_start_timeout",
                    "detail": str(exc),
                }, status_code=504)

            response_id = str(data.get("id", ""))
            if not RESPONSE_ID_RE.match(response_id):
                return JSONResponse({
                    "error": "AI provider did not return a valid background response id.",
                    "code": "invalid_response_id",
                }, status_code=502)

            record_started_job(
                company_id,
                response_id,
                str(data.get("status", "queued")),
                linked_source_id,
                linked_intake_file_id,
            )
            return {
                "ok": True,
                "version": DOMAIN_VERSION,
                "job_id": response_id,
                "status": data.get("status", "queued"),
                "model": OPENAI_MODEL,
                "filename": file.filename,
                "mime_type": mime,
                "source_id": linked_source_id,
                "lineage_linked": bool(linked_source_id),
            }
        except Exception as exc:
            return JSONResponse({
                "error": "AI background analysis could not be started.",
                "code": "start_internal_error",
                "detail": f"{type(exc).__name__}: {str(exc)[:1200]}",
            }, status_code=500)

    @app.get("/companies/{company_id}/ai-intake/jobs/{job_id}", include_in_schema=False)
    def ai_intake_job(company_id: int, job_id: str):
        if not OPENAI_API_KEY:
            return JSONResponse({"error": "AI intake is not configured.", "code": "ai_not_configured"}, status_code=503)
        if not RESPONSE_ID_RE.match(job_id):
            return JSONResponse({"error": "Invalid AI job id.", "code": "invalid_job_id"}, status_code=400)

        request = UrlRequest(
            f"{OPENAI_RESPONSES_URL.rstrip('/')}/{job_id}",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            method="GET",
        )
        try:
            data = provider_json(request, timeout=20)
        except HTTPError as exc:
            record_job_state(job_id, "failed", error_code="provider_error", error_detail=f"HTTP {exc.code}")
            return JSONResponse(provider_error_payload(exc), status_code=502)
        except (URLError, TimeoutError) as exc:
            return JSONResponse({
                "error": "Could not check AI analysis status.",
                "code": "provider_poll_timeout",
                "detail": str(exc),
            }, status_code=504)
        except Exception as exc:
            return JSONResponse({
                "error": "Could not read AI analysis status.",
                "code": "poll_internal_error",
                "detail": f"{type(exc).__name__}: {str(exc)[:1200]}",
            }, status_code=500)

        status = str(data.get("status", "unknown"))
        if status == "completed":
            try:
                parsed = json.loads(extract_output_text(data))
                result = validate_section_result(parsed)
            except Exception as exc:
                record_job_state(
                    job_id,
                    "failed",
                    error_code="invalid_ai_response",
                    error_detail=f"{type(exc).__name__}: {str(exc)[:1200]}",
                )
                return JSONResponse({
                    "error": "AI response completed but could not be validated.",
                    "code": "invalid_ai_response",
                    "detail": f"{type(exc).__name__}: {str(exc)[:1200]}",
                }, status_code=502)
            record_job_state(job_id, "completed", result_summary=str(result.get("summary") or "")[:4000])
            return {
                "ok": True,
                "version": DOMAIN_VERSION,
                "job_id": job_id,
                "status": "completed",
                "model": OPENAI_MODEL,
                "result": result,
            }

        if status in {"failed", "cancelled", "incomplete"}:
            detail = data.get("error") or data.get("incomplete_details") or {}
            record_job_state(
                job_id,
                status,
                error_code=f"provider_{status}",
                error_detail=json.dumps(detail, ensure_ascii=False)[:4000],
            )
            return JSONResponse({
                "error": f"AI background analysis ended with status: {status}.",
                "code": f"provider_{status}",
                "detail": detail,
                "job_id": job_id,
                "status": status,
            }, status_code=502)

        normalized = status if status in {"queued", "processing"} else "processing"
        record_job_state(job_id, normalized)
        return {
            "ok": True,
            "version": DOMAIN_VERSION,
            "job_id": job_id,
            "status": normalized,
            "model": OPENAI_MODEL,
        }


__all__ = ["install_ai_routes"]
