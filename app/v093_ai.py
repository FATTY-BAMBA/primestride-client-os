"""PrimeStride Client OS v0.9.3 background multimodal intake.

Turns long multimodal extraction into a short submit + poll flow. The OpenAI
Responses API runs the analysis in background mode; Vercel only handles brief
start/status requests, avoiding one long serverless invocation and a fragile
blank-page/timeout experience.
"""
from __future__ import annotations

import base64
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

from .v09_ai import (
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_RESPONSES_URL,
    MAX_AI_FILE_BYTES,
    SUPPORTED_FILE_TYPES,
    SUPPORTED_IMAGE_TYPES,
    _extract_output_text,
)
from .v092_ai import OUTPUT_SCHEMA_092, _prompt_092, _validated_result_092

VERSION = "0.9.3"
_RESPONSE_ID_RE = re.compile(r"^resp_[A-Za-z0-9_-]{8,200}$")


def _provider_json(req: UrlRequest, timeout: int = 25) -> dict:
    with urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _provider_error(exc: HTTPError) -> JSONResponse:
    body = exc.read().decode("utf-8", errors="replace")[:2500]
    return JSONResponse({
        "error": "AI provider request failed.",
        "code": "provider_error",
        "provider_status": exc.code,
        "detail": body,
    }, status_code=502)


def install_v093_ai(app: FastAPI) -> None:
    if getattr(app.state, "ps_v093_ai_installed", False):
        return
    app.state.ps_v093_ai_installed = True

    @app.get("/api/ai-intake/status-v093", include_in_schema=False)
    def ai_intake_status_v093():
        return {
            "configured": bool(OPENAI_API_KEY),
            "model": OPENAI_MODEL if OPENAI_API_KEY else None,
            "max_file_bytes": MAX_AI_FILE_BYTES,
            "version": VERSION,
            "mode": "background_polling",
        }

    @app.post("/companies/{company_id}/ai-intake/start", include_in_schema=False)
    async def ai_intake_start_v093(
        company_id: int,
        file: UploadFile = File(...),
        client_context: str = Form(""),
    ):
        try:
            if not OPENAI_API_KEY:
                return JSONResponse({"error": "AI intake is not configured.", "code": "ai_not_configured"}, status_code=503)

            mime = (file.content_type or "").lower().strip()
            if mime not in SUPPORTED_FILE_TYPES:
                return JSONResponse({"error": f"Unsupported AI file type: {mime or 'unknown'}", "code": "unsupported_type"}, status_code=415)

            raw = await file.read(MAX_AI_FILE_BYTES + 1)
            if len(raw) > MAX_AI_FILE_BYTES:
                return JSONResponse({"error": "AI preview limit is 3.5 MB after browser-side compression.", "code": "file_too_large"}, status_code=413)
            if not raw:
                return JSONResponse({"error": "The selected file is empty.", "code": "empty_file"}, status_code=400)

            b64 = base64.b64encode(raw).decode("ascii")
            if mime in SUPPORTED_IMAGE_TYPES:
                file_block = {"type": "input_image", "image_url": f"data:{mime};base64,{b64}", "detail": "high"}
            else:
                file_block = {"type": "input_file", "file_data": b64, "filename": file.filename or "client-document.pdf"}

            payload = {
                "model": OPENAI_MODEL,
                "background": True,
                "store": False,
                "reasoning": {"effort": "low"},
                "max_output_tokens": 6000,
                "input": [{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": _prompt_092(client_context)},
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
                headers={
                    "Authorization": f"Bearer {OPENAI_API_KEY}",
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            try:
                data = _provider_json(req, timeout=25)
            except HTTPError as exc:
                return _provider_error(exc)
            except (URLError, TimeoutError) as exc:
                return JSONResponse({"error": "Could not start AI background analysis.", "code": "provider_start_timeout", "detail": str(exc)}, status_code=504)

            response_id = str(data.get("id", ""))
            if not _RESPONSE_ID_RE.match(response_id):
                return JSONResponse({"error": "AI provider did not return a valid background response id.", "code": "invalid_response_id"}, status_code=502)

            return {
                "ok": True,
                "version": VERSION,
                "job_id": response_id,
                "status": data.get("status", "queued"),
                "model": OPENAI_MODEL,
                "filename": file.filename,
                "mime_type": mime,
            }
        except Exception as exc:
            return JSONResponse({"error": "AI background analysis could not be started.", "code": "start_internal_error", "detail": f"{type(exc).__name__}: {str(exc)[:1200]}"}, status_code=500)

    @app.get("/companies/{company_id}/ai-intake/jobs/{job_id}", include_in_schema=False)
    def ai_intake_job_v093(company_id: int, job_id: str):
        if not OPENAI_API_KEY:
            return JSONResponse({"error": "AI intake is not configured.", "code": "ai_not_configured"}, status_code=503)
        if not _RESPONSE_ID_RE.match(job_id):
            return JSONResponse({"error": "Invalid AI job id.", "code": "invalid_job_id"}, status_code=400)

        req = UrlRequest(
            f"{OPENAI_RESPONSES_URL.rstrip('/')}/{job_id}",
            headers={"Authorization": f"Bearer {OPENAI_API_KEY}"},
            method="GET",
        )
        try:
            data = _provider_json(req, timeout=20)
        except HTTPError as exc:
            return _provider_error(exc)
        except (URLError, TimeoutError) as exc:
            return JSONResponse({"error": "Could not check AI analysis status.", "code": "provider_poll_timeout", "detail": str(exc)}, status_code=504)
        except Exception as exc:
            return JSONResponse({"error": "Could not read AI analysis status.", "code": "poll_internal_error", "detail": f"{type(exc).__name__}: {str(exc)[:1200]}"}, status_code=500)

        status = str(data.get("status", "unknown"))
        if status == "completed":
            try:
                parsed = json.loads(_extract_output_text(data))
                result = _validated_result_092(parsed)
            except Exception as exc:
                return JSONResponse({"error": "AI response completed but could not be validated.", "code": "invalid_ai_response", "detail": f"{type(exc).__name__}: {str(exc)[:1200]}"}, status_code=502)
            return {
                "ok": True,
                "version": VERSION,
                "job_id": job_id,
                "status": "completed",
                "model": OPENAI_MODEL,
                "result": result,
            }

        if status in {"failed", "cancelled", "incomplete"}:
            detail = data.get("error") or data.get("incomplete_details") or {}
            return JSONResponse({
                "error": f"AI background analysis ended with status: {status}.",
                "code": f"provider_{status}",
                "detail": detail,
                "job_id": job_id,
                "status": status,
            }, status_code=502)

        return {
            "ok": True,
            "version": VERSION,
            "job_id": job_id,
            "status": status,
            "model": OPENAI_MODEL,
        }
