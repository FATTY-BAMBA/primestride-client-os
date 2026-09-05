"""PrimeStride Client OS v0.9.2 section-aware multimodal intake.

Adds document-section semantics on top of v0.9.1: missing work-order targets,
planned-vs-actual production timestamps, structured operation rows, and explicit
instruction/constraint/exception classification. The route still returns only
review proposals; persistence remains behind the existing human-review gate.
"""
from __future__ import annotations

import base64
import json
from typing import Any
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
    CATEGORY_VALUES,
    READINESS_KEYS,
    _extract_output_text,
)

VERSION = "0.9.2"

CANONICAL_TARGETS_092 = [
    "Customer.code", "Customer.name", "Contact.name",
    "Product.code", "Product.name", "Specification.value", "Material.name",
    "Quote.quote_number", "Quote.created_at", "Quote.status", "Quote.salesperson",
    "QuoteLine.quantity", "QuoteLine.unit_price", "Quote.total", "Quote.accepted_price",
    "MaterialCost.unit_cost", "Cost.processing", "PricingRule.note", "Quote.exception_note",
    "Order.order_number", "OrderLine.quantity",
    "WorkOrder.work_order_number", "WorkOrder.created_at", "WorkOrder.promised_date",
    "WorkOrder.status", "WorkOrder.salesperson", "WorkOrderLine.quantity",
    "Operation.stage", "Operation.machine", "Operation.assignee",
    "Operation.planned_start", "Operation.planned_end",
    "Operation.actual_start", "Operation.actual_end", "Operation.note",
    "WorkInstruction.text", "WorkConstraint.text", "WorkException.reason",
    "Metric.revenue", "Metric.cost", "Metric.margin", "MetricDefinition.name",
]

OUTPUT_SCHEMA_092: dict[str, Any] = {
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
                    "source_section": {"type": "string"},
                    "source_label": {"type": "string"},
                    "canonical_target": {"type": "string"},
                    "value": {"type": "string"},
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "evidence": {"type": "string"},
                    "semantic_role": {
                        "type": "string",
                        "enum": ["identity", "date", "quantity", "status", "specification", "schedule", "instruction", "constraint", "exception", "note", "other"],
                    },
                },
                "required": ["source_section", "source_label", "canonical_target", "value", "confidence", "evidence", "semantic_role"],
            },
        },
        "operations": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "stage": {"type": "string"},
                    "planned_start": {"type": "string"},
                    "planned_end": {"type": "string"},
                    "actual_start": {"type": "string"},
                    "actual_end": {"type": "string"},
                    "assignee": {"type": "string"},
                    "machine": {"type": "string"},
                    "note": {"type": "string"},
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "evidence": {"type": "string"},
                },
                "required": ["stage", "planned_start", "planned_end", "actual_start", "actual_end", "assignee", "machine", "note", "confidence", "evidence"],
            },
        },
        "instructions": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "properties": {
                    "kind": {"type": "string", "enum": ["instruction", "constraint", "exception", "incident", "note"]},
                    "text": {"type": "string"},
                    "canonical_target": {"type": "string"},
                    "confidence": {"type": "integer", "minimum": 0, "maximum": 100},
                    "evidence": {"type": "string"},
                },
                "required": ["kind", "text", "canonical_target", "confidence", "evidence"],
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
    "required": ["category", "document_type", "summary", "fields", "operations", "instructions", "readiness", "quality_flags", "questions", "do_not_infer"],
}


def _prompt_092(client_context: str) -> str:
    targets = ", ".join(CANONICAL_TARGETS_092)
    readiness = "; ".join(f"Module {module}: {', '.join(keys)}" for module, keys in READINESS_KEYS.items())
    return f"""You are PrimeStride's section-aware evidence extraction assistant for SME operations documents.

Analyze the supplied document/image as evidence. The human reviewer remains authoritative. Extract visible facts and reconstruct document structure without inventing missing facts.

Core rules:
- Preserve visible source wording in source_label/value/evidence.
- Classify the document into exactly one category: {', '.join(CATEGORY_VALUES)}.
- Canonical targets must be one of these values or empty: {targets}.
- If ambiguous, leave canonical_target empty and lower confidence.
- Do not infer a value because it would be useful.
- Distinguish printed labels, handwritten notes, stamps, tables, and schedule rows.

Section-aware mapping rules:
- On a work-order document, 開單日期 / issue date maps to WorkOrder.created_at when clearly the document issue/open date.
- 業務 / sales rep on a work order maps to WorkOrder.salesperson.
- In a production schedule, 預計開始 / planned start maps to Operation.planned_start, NOT Operation.actual_start.
- 預計完成 / planned end maps to Operation.planned_end, NOT Operation.actual_end.
- Only map actual_start/actual_end when the source explicitly says actual/實際/完成紀錄 or clearly records an event that happened.
- A production-row note such as '4C 印刷', '霧膜', '糊盒機 #2', or '客戶自取' is Operation.note unless it clearly belongs to another canonical field. Never map production notes to PricingRule.note.
- PricingRule.note is allowed only inside pricing/quotation logic context.
- A customer request such as '提前一天交貨' is normally a constraint/instruction, not an incident.
- A preventive instruction such as '如有色差先電話確認' is an instruction, not an actual exception event.
- An exception/incident requires evidence that an abnormal event happened (delay, rework, defect, failure, etc.).
- Use WorkException.reason only for actual exception/incident evidence, not generic instructions.

Structured operations:
- If a production schedule/table exists, reconstruct one operation object per visible schedule row.
- Keep planned and actual timestamps separate.
- Empty operation fields must remain empty strings; do not infer them from another row.
- The operation list should preserve visible stage order.

Readiness:
- Readiness criterion must match: {readiness}.
- Only propose evidence directly supported by the document.
- 'available' = directly evidenced; 'partial' = useful but incomplete/ambiguous.
- A single work-order document is NOT a work-order history dataset. For Module 06 work_order_history, use partial at most unless multiple historical records are visibly present.
- Planned timestamps can support time_fields, but do not claim actual_timestamps readiness unless actual event timestamps are visible.

Uncertainty:
- Put unresolved questions in questions.
- Put unsafe assumptions in do_not_infer.
- Mention image/scan quality limitations when relevant.

Known client context may help interpretation but must not override the document:
{client_context or 'No additional context provided.'}
"""


def _validated_result_092(data: dict[str, Any]) -> dict[str, Any]:
    category = data.get("category") if data.get("category") in CATEGORY_VALUES else "other"
    fields = []
    for field in data.get("fields", [])[:100]:
        target = str(field.get("canonical_target", "")).strip()
        if target not in CANONICAL_TARGETS_092:
            target = ""
        role = str(field.get("semantic_role", "other"))
        if role not in {"identity", "date", "quantity", "status", "specification", "schedule", "instruction", "constraint", "exception", "note", "other"}:
            role = "other"
        fields.append({
            "source_section": str(field.get("source_section", ""))[:200],
            "source_label": str(field.get("source_label", ""))[:200],
            "canonical_target": target,
            "value": str(field.get("value", ""))[:1000],
            "confidence": max(0, min(100, int(field.get("confidence", 0)))),
            "evidence": str(field.get("evidence", ""))[:1000],
            "semantic_role": role,
        })

    operations = []
    for op in data.get("operations", [])[:60]:
        operations.append({
            "stage": str(op.get("stage", ""))[:250],
            "planned_start": str(op.get("planned_start", ""))[:100],
            "planned_end": str(op.get("planned_end", ""))[:100],
            "actual_start": str(op.get("actual_start", ""))[:100],
            "actual_end": str(op.get("actual_end", ""))[:100],
            "assignee": str(op.get("assignee", ""))[:200],
            "machine": str(op.get("machine", ""))[:200],
            "note": str(op.get("note", ""))[:700],
            "confidence": max(0, min(100, int(op.get("confidence", 0)))),
            "evidence": str(op.get("evidence", ""))[:1000],
        })

    instructions = []
    for item in data.get("instructions", [])[:40]:
        kind = str(item.get("kind", "note"))
        if kind not in {"instruction", "constraint", "exception", "incident", "note"}:
            kind = "note"
        target = str(item.get("canonical_target", "")).strip()
        if target not in CANONICAL_TARGETS_092:
            target = ""
        instructions.append({
            "kind": kind,
            "text": str(item.get("text", ""))[:1000],
            "canonical_target": target,
            "confidence": max(0, min(100, int(item.get("confidence", 0)))),
            "evidence": str(item.get("evidence", ""))[:1000],
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
        "operations": operations,
        "instructions": instructions,
        "readiness": readiness,
        "quality_flags": clean_list("quality_flags"),
        "questions": clean_list("questions"),
        "do_not_infer": clean_list("do_not_infer"),
    }


def install_v092_ai(app: FastAPI) -> None:
    if getattr(app.state, "ps_v092_ai_installed", False):
        return
    app.state.ps_v092_ai_installed = True

    @app.get("/api/ai-intake/status", include_in_schema=False)
    def ai_intake_status_v092():
        return {
            "configured": bool(OPENAI_API_KEY),
            "model": OPENAI_MODEL if OPENAI_API_KEY else None,
            "max_file_bytes": MAX_AI_FILE_BYTES,
            "supported_types": sorted(SUPPORTED_FILE_TYPES),
            "version": VERSION,
        }

    @app.post("/companies/{company_id}/ai-intake/analyze", include_in_schema=False)
    async def ai_intake_analyze_v092(
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
                "store": False,
                "reasoning": {"effort": "low"},
                "max_output_tokens": 7500,
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
                        "description": "Section-aware evidence extraction with structured operations and explicit instruction semantics.",
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
            try:
                with urlopen(req, timeout=105) as resp:
                    api_data = json.loads(resp.read().decode("utf-8"))
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")[:2500]
                return JSONResponse({"error": "AI provider request failed.", "code": "provider_error", "provider_status": exc.code, "detail": body}, status_code=502)
            except (URLError, TimeoutError) as exc:
                return JSONResponse({"error": "AI provider could not be reached before the analysis timeout.", "code": "provider_timeout", "detail": str(exc)}, status_code=504)

            try:
                parsed = json.loads(_extract_output_text(api_data))
                result = _validated_result_092(parsed)
            except (ValueError, json.JSONDecodeError) as exc:
                return JSONResponse({"error": "AI response could not be validated.", "code": "invalid_ai_response", "detail": str(exc)}, status_code=502)

            return {"ok": True, "version": VERSION, "model": OPENAI_MODEL, "filename": file.filename, "mime_type": mime, "result": result}
        except Exception as exc:
            return JSONResponse({"error": "AI intake failed before a validated result was produced.", "code": "ai_intake_internal_error", "detail": f"{type(exc).__name__}: {str(exc)[:1200]}"}, status_code=500)
