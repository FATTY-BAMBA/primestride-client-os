"""PrimeStride Client OS v0.9 multimodal intake assistant.

The deterministic XLSX/CSV parser remains the primary path. This endpoint is an
optional semantic/vision layer for PDFs and images (and later ambiguous
structured snippets). It never writes client truth directly: it returns
proposals for human review, and the existing intake/readiness routes remain the
only persistence boundary.
"""
from __future__ import annotations

import base64
import json
import os
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request as UrlRequest, urlopen

from fastapi import FastAPI, File, Form, UploadFile
from fastapi.responses import JSONResponse

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-terra").strip() or "gpt-5.6-terra"
OPENAI_RESPONSES_URL = os.getenv("OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses").strip()
MAX_AI_FILE_BYTES = 3_500_000
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
SUPPORTED_FILE_TYPES = SUPPORTED_IMAGE_TYPES | {"application/pdf"}

CATEGORY_VALUES = ["customers", "products", "quotes", "work_orders", "reports", "other"]
CANONICAL_TARGETS = [
    "Customer.code", "Customer.name", "Contact.name",
    "Product.code", "Product.name", "Specification.value", "Material.name",
    "Quote.quote_number", "Quote.created_at", "Quote.status", "Quote.salesperson",
    "QuoteLine.quantity", "QuoteLine.unit_price", "Quote.total", "Quote.accepted_price",
    "MaterialCost.unit_cost", "Cost.processing", "PricingRule.note", "Quote.exception_note",
    "Order.order_number", "OrderLine.quantity",
    "WorkOrder.work_order_number", "WorkOrder.promised_date", "WorkOrder.status",
    "WorkOrderLine.quantity", "Operation.stage", "Operation.machine", "Operation.assignee",
    "Operation.actual_start", "Operation.actual_end", "WorkException.reason",
    "Metric.revenue", "Metric.cost", "Metric.margin", "MetricDefinition.name",
]
READINESS_KEYS = {
    4: ["historical_quotes", "customer_identity", "product_spec", "quantity", "quoted_price", "accepted_price", "material_cost", "processing_cost", "pricing_rules", "exception_examples"],
    5: ["work_order_id", "order_reference", "product_spec", "quantity", "promised_date", "production_stages", "station_machine", "assignee", "current_status", "actual_timestamps", "exceptions"],
    6: ["quote_history", "order_history", "work_order_history", "revenue", "cost", "margin", "customer_product", "time_fields", "production_events", "kpi_definitions"],
}

OUTPUT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "properties": {
        "category": {"type": "string", "enum": CATEGORY_VALUES},
        "document_type": {"type": "string"},
        "summary": {"type": "string"},
        "fields": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "source_label": {"type": "string"},
                    "canonical_target": {"type": "string"},
                    "value": {"type": "string"},
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "evidence": {"type": "string"},
                },
                "required": ["source_label", "canonical_target", "value", "confidence", "evidence"],
            },
        },
        "readiness": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "module_no": {"type": "integer", "enum": [4, 5, 6]},
                    "criterion": {"type": "string"},
                    "status": {"type": "string", "enum": ["available", "partial"]},
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "reason": {"type": "string"},
                },
                "required": ["module_no", "criterion", "status", "confidence", "reason"],
            },
        },
        "quality_flags": {"type": "array", "items": {"type": "string"}},
        "questions": {"type": "array", "items": {"type": "string"}},
        "do_not_infer": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["category", "document_type", "summary", "fields", "readiness", "quality_flags", "questions", "do_not_infer"],
}


def _prompt(client_context: str) -> str:
    targets = ", ".join(CANONICAL_TARGETS)
    readiness = "; ".join(f"Module {module}: {', '.join(keys)}" for module, keys in READINESS_KEYS.items())
    return f"""You are PrimeStride's evidence extraction assistant for SME operations data.

Analyze the supplied client document/image as evidence. The deterministic parser and human reviewer remain authoritative. Your job is to extract visible business facts and propose mappings, never invent missing facts.

Rules:
- Preserve source wording in source_label/value/evidence.
- If a field is ambiguous, use canonical_target as an empty string and lower confidence.
- Do not infer a value merely because it would be useful.
- A photo/scan may contain handwriting, stamps, tables, or multiple regions; extract only what is readable.
- Classify the document into exactly one category: {', '.join(CATEGORY_VALUES)}.
- Canonical targets must be one of these values or empty: {targets}.
- Readiness criterion must match the module's allowed keys: {readiness}.
- Only propose readiness evidence when the document itself supports it.
- 'available' means directly evidenced; 'partial' means incomplete/ambiguous evidence.
- Put unresolved ambiguity in questions. Put unsafe assumptions in do_not_infer.
- This is evidence extraction, not pricing calculation or operational decision-making.

Known client context (may help interpretation but must not override the document):
{client_context or 'No additional context provided.'}
"""


def _extract_output_text(response: dict[str, Any]) -> str:
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return content["text"]
    raise ValueError("Model response did not contain structured output text")


def _validated_result(data: dict[str, Any]) -> dict[str, Any]:
    # Defensive filtering: never trust model strings as persistence identifiers.
    category = data.get("category") if data.get("category") in CATEGORY_VALUES else "other"
    fields = []
    for field in data.get("fields", [])[:80]:
        target = str(field.get("canonical_target", "")).strip()
        if target not in CANONICAL_TARGETS:
            target = ""
        fields.append({
            "source_label": str(field.get("source_label", ""))[:200],
            "canonical_target": target,
            "value": str(field.get("value", ""))[:1000],
            "confidence": max(0, min(100, int(field.get("confidence", 0)))),
            "evidence": str(field.get("evidence", ""))[:1000],
        })

    readiness = []
    for item in data.get("readiness", [])[:40]:
        try:
            module_no = int(item.get("module_no"))
        except Exception:
            continue
        criterion = str(item.get("criterion", ""))
        if module_no not in READINESS_KEYS or criterion not in READINESS_KEYS[module_no]:
            continue
        status = item.get("status") if item.get("status") in {"available", "partial"} else "partial"
        readiness.append({
            "module_no": module_no,
            "criterion": criterion,
            "status": status,
            "confidence": max(0, min(100, int(item.get("confidence", 0)))),
            "reason": str(item.get("reason", ""))[:1000],
        })

    def clean_list(key: str, limit: int = 20) -> list[str]:
        return [str(x)[:700] for x in data.get(key, [])[:limit] if str(x).strip()]

    return {
        "category": category,
        "document_type": str(data.get("document_type", "Unknown document"))[:200],
        "summary": str(data.get("summary", ""))[:2000],
        "fields": fields,
        "readiness": readiness,
        "quality_flags": clean_list("quality_flags"),
        "questions": clean_list("questions"),
        "do_not_infer": clean_list("do_not_infer"),
    }


def install_v09_ai(app: FastAPI) -> None:
    if getattr(app.state, "ps_v09_ai_installed", False):
        return
    app.state.ps_v09_ai_installed = True

    @app.get("/api/ai-intake/status", include_in_schema=False)
    def ai_intake_status():
        return {
            "configured": bool(OPENAI_API_KEY),
            "model": OPENAI_MODEL if OPENAI_API_KEY else None,
            "max_file_bytes": MAX_AI_FILE_BYTES,
            "supported_types": sorted(SUPPORTED_FILE_TYPES),
            "version": "0.9.0",
        }

    @app.post("/companies/{company_id}/ai-intake/analyze", include_in_schema=False)
    async def ai_intake_analyze(
        company_id: int,
        file: UploadFile = File(...),
        client_context: str = Form(""),
    ):
        if not OPENAI_API_KEY:
            return JSONResponse({
                "error": "AI intake is not configured yet. Add OPENAI_API_KEY in the server environment; deterministic ingestion remains available.",
                "code": "ai_not_configured",
            }, status_code=503)

        mime = (file.content_type or "").lower().strip()
        if mime not in SUPPORTED_FILE_TYPES:
            return JSONResponse({"error": f"Unsupported AI file type: {mime or 'unknown'}"}, status_code=415)

        raw = await file.read(MAX_AI_FILE_BYTES + 1)
        if len(raw) > MAX_AI_FILE_BYTES:
            return JSONResponse({"error": "AI preview limit is 3.5 MB after browser-side image compression. Larger files will use object storage/background ingestion later."}, status_code=413)
        if not raw:
            return JSONResponse({"error": "The selected file is empty."}, status_code=400)

        b64 = base64.b64encode(raw).decode("ascii")
        if mime in SUPPORTED_IMAGE_TYPES:
            file_block = {"type": "input_image", "image_url": f"data:{mime};base64,{b64}", "detail": "high"}
        else:
            file_block = {"type": "input_file", "file_data": b64, "filename": file.filename or "client-document.pdf"}

        payload = {
            "model": OPENAI_MODEL,
            "store": False,
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
            with urlopen(req, timeout=90) as resp:
                api_data = json.loads(resp.read().decode("utf-8"))
            parsed = json.loads(_extract_output_text(api_data))
            result = _validated_result(parsed)
            return {
                "ok": True,
                "version": "0.9.0",
                "model": OPENAI_MODEL,
                "filename": file.filename,
                "mime_type": mime,
                "result": result,
            }
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")[:2000]
            return JSONResponse({"error": "AI provider request failed.", "provider_status": exc.code, "detail": body}, status_code=502)
        except (URLError, TimeoutError) as exc:
            return JSONResponse({"error": "AI provider could not be reached.", "detail": str(exc)}, status_code=502)
        except (ValueError, json.JSONDecodeError) as exc:
            return JSONResponse({"error": "AI response could not be validated.", "detail": str(exc)}, status_code=502)
