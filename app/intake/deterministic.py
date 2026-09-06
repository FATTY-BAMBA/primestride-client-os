"""Stable deterministic-intake helpers.

Owns the non-AI intake rules that previously lived in ``v082_runtime.py``:
category vocabulary, file/hash matching, evidence invalidation and the compact
memory projection used by the Data Intake workspace.

Browser-side table detection/mapping remains unchanged; this module is the stable
server-side contract behind those inspections.
"""
from __future__ import annotations

import re
from pathlib import Path

from fastapi.templating import Jinja2Templates
from sqlalchemy import delete
from sqlalchemy.orm import Session

from ..models import ClientMemory, IntakeFile, Readiness, ReadinessEvidence

DOMAIN_VERSION = "1.3.3"
DETERMINISTIC_ENGINE_VERSION = "0.8.4"

BASE_DIR = Path(__file__).resolve().parents[1]
TEMPLATES = Jinja2Templates(directory=str(BASE_DIR / "templates"))

EXPECTED_DATA_CATEGORIES = [
    ("customers", "Customers & Contacts", "客戶與聯絡人"),
    ("products", "Products / Specs / Materials", "產品／規格／材料"),
    ("quotes", "Quotations / Pricing / Costs", "報價／價格／成本"),
    ("work_orders", "Orders / Work Orders", "訂單／工單"),
    ("reports", "Management Reports", "管理報表"),
    ("other", "Other Process Material", "其他流程資料"),
]
VALID_CATEGORIES = {key for key, _, _ in EXPECTED_DATA_CATEGORIES}
DATA_STAGES = {"Data Requested", "Data Received", "Data Readiness"}
HASH_RE = re.compile(r"sha256=([0-9a-f]{64})", re.I)


def memory_groups(items: list[ClientMemory]) -> dict[str, list[ClientMemory]]:
    groups = {"known": [], "unknown": [], "do_not_ask": [], "next_question": []}
    for item in items:
        if item.active:
            groups.setdefault(item.kind, []).append(item)
    return groups


def clear_file_evidence(db: Session, company_id: int, filename: str) -> None:
    """Invalidate evidence whose current provenance is exactly this file."""
    db.execute(
        delete(ReadinessEvidence).where(
            ReadinessEvidence.company_id == company_id,
            ReadinessEvidence.source == filename,
        )
    )
    # Aggregates are projections; remove them when their evidence changes.
    db.execute(delete(Readiness).where(Readiness.company_id == company_id))


def hash_from_notes(notes: str | None) -> str | None:
    if not notes:
        return None
    match = HASH_RE.search(notes)
    return match.group(1).lower() if match else None


def find_existing_file(
    db: Session,
    company_id: int,
    filename: str,
    notes: str | None,
) -> IntakeFile | None:
    """Resolve a saved browser inspection by filename or deterministic SHA."""
    from sqlalchemy import select

    file_hash = hash_from_notes(notes)
    candidates = list(
        db.scalars(
            select(IntakeFile)
            .where(IntakeFile.company_id == company_id)
            .order_by(IntakeFile.id.desc())
        ).all()
    )
    for item in candidates:
        if item.filename == filename:
            return item
        if file_hash and hash_from_notes(item.notes) == file_hash:
            return item
    return None


# Historical aliases while old imports are retired.
_memory_groups = memory_groups
_clear_file_evidence = clear_file_evidence
_hash_from_notes = hash_from_notes
_find_existing_file = find_existing_file

__all__ = [
    "DOMAIN_VERSION",
    "DETERMINISTIC_ENGINE_VERSION",
    "TEMPLATES",
    "EXPECTED_DATA_CATEGORIES",
    "VALID_CATEGORIES",
    "DATA_STAGES",
    "HASH_RE",
    "memory_groups",
    "clear_file_evidence",
    "hash_from_notes",
    "find_existing_file",
    "_memory_groups",
    "_clear_file_evidence",
    "_hash_from_notes",
    "_find_existing_file",
]
