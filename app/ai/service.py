"""Stable multimodal AI intake services.

Owns provider configuration, section-aware prompt/schema validation, source
linkage, and first-class ingestion-job state recording. AI remains proposal-only;
persistence of reviewed evidence stays behind the intake human-review boundary.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request as UrlRequest, urlopen

from ..db import SessionLocal
from ..lineage.service import (
    create_ingestion_job,
    find_source_by_id,
    find_source_by_sha,
    update_ingestion_job,
)
from .schema import (
    CANONICAL_TARGETS,
    CANONICAL_TARGETS_092,
    CATEGORY_VALUES,
    READINESS_KEYS,
)

DOMAIN_VERSION = "1.3.4"
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-terra").strip() or "gpt-5.6-terra"
OPENAI_RESPONSES_URL = os.getenv("OPENAI_RESPONSES_URL", "https://api.openai.com/v1/responses").strip()
MAX_AI_FILE_BYTES = 3_500_000
SUPPORTED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/webp"}
SUPPORTED_FILE_TYPES = SUPPORTED_IMAGE_TYPES | {"application/pdf"}
RESPONSE_ID_RE = re.compile(r"^resp_[A-Za-z0-9_-]{8,200}$")
_RESPONSE_ID_RE = RESPONSE_ID_RE


def prompt(client_context: str) -> str:
    """Historical v0.9 prompt retained for compatibility imports."""
    targets = ", ".join(CANONICAL_TARGETS)
    readiness = "; ".join(
        f"Module {module}: {', '.join(keys)}" for module, keys in READINESS_KEYS.items()
    )
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


def section_prompt(client_context: str) -> str:
    targets = ", ".join(CANONICAL_TARGETS_092)
    readiness = "; ".join(
        f"Module {module}: {', '.join(keys)}" for module, keys in READINESS_KEYS.items()
    )
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


def extract_output_text(response: dict[str, Any]) -> str:
    for item in response.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            if content.get("type") == "output_text" and content.get("text"):
                return content["text"]
    raise ValueError("Model response did not contain structured output text")


def _clean_list(data: dict[str, Any], key: str, limit: int = 20) -> list[str]:
    return [str(value)[:700] for value in data.get(key, [])[:limit] if str(value).strip()]


def validated_result(data: dict[str, Any]) -> dict[str, Any]:
    """Historical v0.9 validator retained for compatibility imports."""
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
    readiness = _validated_readiness(data)
    return {
        "category": category,
        "document_type": str(data.get("document_type", "Unknown document"))[:200],
        "summary": str(data.get("summary", ""))[:2000],
        "fields": fields,
        "readiness": readiness,
        "quality_flags": _clean_list(data, "quality_flags"),
        "questions": _clean_list(data, "questions"),
        "do_not_infer": _clean_list(data, "do_not_infer"),
    }


def _validated_readiness(data: dict[str, Any]) -> list[dict[str, Any]]:
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
    return readiness


def validate_section_result(data: dict[str, Any]) -> dict[str, Any]:
    category = data.get("category") if data.get("category") in CATEGORY_VALUES else "other"
    fields = []
    roles = {"identity", "date", "quantity", "status", "specification", "schedule", "instruction", "constraint", "exception", "note", "other"}
    for field in data.get("fields", [])[:100]:
        target = str(field.get("canonical_target", "")).strip()
        if target not in CANONICAL_TARGETS_092:
            target = ""
        role = str(field.get("semantic_role", "other"))
        if role not in roles:
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
    valid_kinds = {"instruction", "constraint", "exception", "incident", "note"}
    for item in data.get("instructions", [])[:40]:
        kind = str(item.get("kind", "note"))
        if kind not in valid_kinds:
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

    return {
        "category": category,
        "document_type": str(data.get("document_type", "Unknown document"))[:200],
        "summary": str(data.get("summary", ""))[:2000],
        "fields": fields,
        "operations": operations,
        "instructions": instructions,
        "readiness": _validated_readiness(data),
        "quality_flags": _clean_list(data, "quality_flags"),
        "questions": _clean_list(data, "questions"),
        "do_not_infer": _clean_list(data, "do_not_infer"),
    }


def provider_json(req: UrlRequest, timeout: int = 25) -> dict:
    with urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def provider_error_payload(exc: HTTPError) -> dict[str, Any]:
    body = exc.read().decode("utf-8", errors="replace")[:2500]
    return {
        "error": "AI provider request failed.",
        "code": "provider_error",
        "provider_status": exc.code,
        "detail": body,
    }


def link_source(company_id: int, requested_source_id: str, raw_sha256: str) -> tuple[str | None, int | None]:
    db = SessionLocal()
    try:
        source = None
        if requested_source_id:
            source = find_source_by_id(db, company_id, requested_source_id)
        if not source:
            source = find_source_by_sha(db, company_id, raw_sha256)
        if not source:
            return None, None
        return source.get("source_id"), source.get("intake_file_id")
    finally:
        db.close()


def record_started_job(
    company_id: int,
    response_id: str,
    status: str,
    source_id: str | None,
    intake_file_id: int | None,
) -> None:
    try:
        db = SessionLocal()
        try:
            create_ingestion_job(
                db,
                company_id=company_id,
                job_type="multimodal_ai",
                status=status if status in {"queued", "processing"} else "queued",
                source_id=source_id,
                intake_file_id=intake_file_id,
                engine_version=DOMAIN_VERSION,
                model=OPENAI_MODEL,
                provider_job_id=response_id,
                job_key=response_id,
            )
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        print(f"[AI ingestion job start] warning: {exc!r}")


def record_job_state(
    response_id: str,
    status: str,
    *,
    error_code: str | None = None,
    error_detail: str | None = None,
    result_summary: str | None = None,
) -> None:
    try:
        db = SessionLocal()
        try:
            update_ingestion_job(
                db,
                provider_job_id=response_id,
                status=status,
                error_code=error_code,
                error_detail=error_detail,
                result_summary=result_summary,
            )
            db.commit()
        finally:
            db.close()
    except Exception as exc:
        print(f"[AI ingestion job update] warning: {exc!r}")


# Historical aliases for compatibility adapters.
_prompt = prompt
_prompt_092 = section_prompt
_extract_output_text = extract_output_text
_validated_result = validated_result
_validated_result_092 = validate_section_result
_provider_json = provider_json
_link_source = link_source
_record_started_job = record_started_job
_record_job_state = record_job_state
