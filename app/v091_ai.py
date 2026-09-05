"""v0.9.1 resilience layer for multimodal AI intake.

Keeps the v0.9 extraction contract but makes the analyze route safer for hosted
functions: low reasoning effort for extraction latency, bounded output, longer
provider timeout, and a final JSON catch-all so the browser never sees a Python
error page as if it were JSON.
"""
from __future__ import annotations

import base64
import json
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
    OUTPUT_SCHEMA,
    _prompt,
    _extract_output_text,
    _validated_result,
)

VERSION = "0.9.1"


def install_v091_ai(app: FastAPI) -> None:
    if getattr(app.state, "ps_v091_ai_installed", False):
        return
    app.state.ps_v091_ai_installed = True

    # Register before v0.9's route; Starlette resolves the first matching route.
    @app.post("/companies/{company_id}/ai-intake/analyze", include_in_schema=False)
    async def ai_intake_analyze_v091(
        company_id: int,
        file: UploadFile = File(...),
        client_context: str = Form(""),
    ):
        try:
            if not OPENAI_API_KEY:
                return JSONResponse({
                    "error": "AI intake is not configured yet. Add OPENAI_API_KEY in the server environment.",
                    "code": "ai_not_configured",
                }, status_code=503)

            mime = (file.content_type or "").lower().strip()
            if mime not in SUPPORTED_FILE_TYPES:
                return JSONResponse({
                    "error": f"Unsupported AI file type: {mime or 'unknown'}",
                    "code": "unsupported_type",
                }, status_code=415)

            raw = await file.read(MAX_AI_FILE_BYTES + 1)
            if len(raw) > MAX_AI_FILE_BYTES:
                return JSONResponse({
                    "error": "AI preview limit is 3.5 MB after browser-side compression.",
                    "code": "file_too_large",
                }, status_code=413)
            if not raw:
                return JSONResponse({"error": "The selected file is empty.", "code": "empty_file"}, status_code=400)

            b64 = base64.b64encode(raw).decode("ascii")
            if mime in SUPPORTED_IMAGE_TYPES:
                file_block = {
                    "type": "input_image",
                    "image_url": f"data:{mime};base64,{b64}",
                    "detail": "high",
                }
            else:
                file_block = {
                    "type": "input_file",
                    "file_data": b64,
                    "filename": file.filename or "client-document.pdf",
                }

            payload = {
                "model": OPENAI_MODEL,
                "store": False,
                "reasoning": {"effort": "low"},
                "max_output_tokens": 6000,
                "input": [{
                    "role": "user",
                    "content": [
                        {"type": "input_text", "text": _prompt(client_context)},
                        file_block,
                    ],
                }],
                "text": {
                    "format": {
                        "type": "json_schema",
                        "name": "primestride_intake_evidence",
                        "description": "Evidence extraction and canonical mapping proposals for PrimeStride Client OS.",
                        "strict": True,
                        "schema": OUTPUT_SCHEMA,
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
                with urlopen(req, timeout=105) as resp:
                    api_data = json.loads(resp.read().decode("utf-8"))
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")[:2500]
                return JSONResponse({
                    "error": "AI provider request failed.",
                    "code": "provider_error",
                    "provider_status": exc.code,
                    "detail": body,
                }, status_code=502)
            except (URLError, TimeoutError) as exc:
                return JSONResponse({
                    "error": "AI provider could not be reached before the analysis timeout.",
                    "code": "provider_timeout",
                    "detail": str(exc),
                }, status_code=504)

            try:
                parsed = json.loads(_extract_output_text(api_data))
                result = _validated_result(parsed)
            except (ValueError, json.JSONDecodeError) as exc:
                return JSONResponse({
                    "error": "AI response could not be validated.",
                    "code": "invalid_ai_response",
                    "detail": str(exc),
                }, status_code=502)

            return {
                "ok": True,
                "version": VERSION,
                "model": OPENAI_MODEL,
                "filename": file.filename,
                "mime_type": mime,
                "result": result,
            }
        except Exception as exc:
            # Last-resort safety boundary. Do not leak a framework HTML/plain
            # error page into a frontend that expects JSON.
            return JSONResponse({
                "error": "AI intake failed before a validated result was produced.",
                "code": "ai_intake_internal_error",
                "detail": f"{type(exc).__name__}: {str(exc)[:1200]}",
            }, status_code=500)
