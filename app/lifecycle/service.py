"""Stable source-lifecycle services.

Owns ACTIVE / TEST / ARCHIVED source state, lifecycle-safe evidence projection,
and the intake-stage reconciliation gate.
"""
from __future__ import annotations

import threading
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import insert, inspect, select

from ..db import RUNTIME_SCHEMA_BOOTSTRAP, engine
from ..lineage.schema import source_references
from ..lineage.service import ensure_lineage_schema
from ..models import Company, IntakeFile, ReadinessEvidence
from .schema import intake_source_lifecycle, lifecycle_metadata

DOMAIN_VERSION = "1.5.0"
VALID_STATES = {"active", "test", "archived"}

_schema_lock = threading.Lock()
_schema_ready = False

# Explicit one-time migration of the engineering fixtures used while the 菘佑
# workflow was being built. Future files are never classified by filename pattern.
COMPANY1_TEST_FIXTURES = {
    "SourceVault_Test.txt",
    "ChatGPT Image Sep 4, 2026, 11_05_41 PM.png",
    "PrimeStride_Test_02_Work_Orders_Messy (1).csv",
    "PrimeStride_Test_01_Quote_History.xlsx",
}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ensure_lifecycle_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        if RUNTIME_SCHEMA_BOOTSTRAP:
            lifecycle_metadata.create_all(bind=engine, checkfirst=True)
        else:
            if not inspect(engine).has_table("intake_source_lifecycle"):
                raise RuntimeError(
                    "Lifecycle schema is not migrated. Missing: intake_source_lifecycle. "
                    "Run `alembic upgrade head`."
                )
        _schema_ready = True


def source_id_for_file(db, item: IntakeFile) -> str | None:
    try:
        ensure_lineage_schema()
        row = db.execute(
            select(source_references.c.source_id).where(source_references.c.intake_file_id == item.id)
        ).first()
        return str(row[0]) if row and row[0] else None
    except Exception:
        return None


def default_state(item: IntakeFile) -> tuple[str, str | None]:
    if item.company_id == 1 and item.filename in COMPANY1_TEST_FIXTURES:
        return "test", "PrimeStride engineering fixture created before real client data intake."
    return "active", None


def ensure_lifecycle_rows(db, company_id: int | None = None) -> int:
    ensure_lifecycle_schema()
    stmt = select(IntakeFile)
    if company_id is not None:
        stmt = stmt.where(IntakeFile.company_id == company_id)
    added = 0
    for item in db.scalars(stmt).all():
        exists = db.execute(
            select(intake_source_lifecycle.c.id).where(intake_source_lifecycle.c.intake_file_id == item.id)
        ).first()
        if exists:
            continue
        state, reason = default_state(item)
        now = now_utc()
        db.execute(insert(intake_source_lifecycle).values(
            company_id=item.company_id,
            intake_file_id=item.id,
            source_id=source_id_for_file(db, item),
            state=state,
            reason=reason,
            created_at=now,
            updated_at=now,
        ))
        added += 1
    return added


def lifecycle_rows(db, company_id: int) -> list[dict[str, Any]]:
    ensure_lifecycle_rows(db, company_id)
    rows = db.execute(
        select(intake_source_lifecycle)
        .where(intake_source_lifecycle.c.company_id == company_id)
        .order_by(intake_source_lifecycle.c.intake_file_id.desc())
    ).mappings().all()
    return [dict(row) for row in rows]


def lifecycle_map(db, company_id: int) -> dict[int, dict[str, Any]]:
    return {int(row["intake_file_id"]): row for row in lifecycle_rows(db, company_id)}


def active_intake_files(db, company_id: int, files: list[IntakeFile] | None = None) -> list[IntakeFile]:
    states = lifecycle_map(db, company_id)
    if files is None:
        files = list(db.scalars(select(IntakeFile).where(IntakeFile.company_id == company_id)).all())
    return [item for item in files if states.get(item.id, {}).get("state", "active") == "active"]


def inactive_source_filenames(db, company_id: int) -> set[str]:
    states = lifecycle_map(db, company_id)
    inactive_ids = {file_id for file_id, row in states.items() if row.get("state") != "active"}
    if not inactive_ids:
        return set()
    return set(db.scalars(
        select(IntakeFile.filename).where(
            IntakeFile.company_id == company_id,
            IntakeFile.id.in_(inactive_ids),
        )
    ).all())


def effective_readiness_evidence(company: Company, db) -> list[ReadinessEvidence]:
    inactive = inactive_source_filenames(db, company.id)
    if not inactive:
        return list(company.readiness_evidence)
    return [
        evidence for evidence in company.readiness_evidence
        if not evidence.source or evidence.source not in inactive
    ]


class CompanyView:
    """Read-only delegate with lifecycle-filtered operational collections."""

    def __init__(self, company: Company, *, intake_files, readiness_evidence):
        self._company = company
        self.intake_files = intake_files
        self.readiness_evidence = readiness_evidence

    def __getattr__(self, name):
        return getattr(self._company, name)


def reconcile_stage(db, company: Company, all_files: list[IntakeFile]) -> bool:
    """Keep Data Requested / Received / Readiness aligned to ACTIVE evidence."""
    if company.stage not in {"Data Requested", "Data Received", "Data Readiness"}:
        return False

    active = active_intake_files(db, company.id, all_files)
    inactive_names = inactive_source_filenames(db, company.id)
    evidence_count = sum(
        1
        for evidence in db.scalars(
            select(ReadinessEvidence).where(ReadinessEvidence.company_id == company.id)
        ).all()
        if evidence.status != "awaiting" and (not evidence.source or evidence.source not in inactive_names)
    )

    if not active:
        target = "Data Requested"
        next_action = "Await initial sample-data upload"
    elif all(item.status == "Reviewed" for item in active) and evidence_count > 0:
        target = "Data Readiness"
        next_action = "Complete evidence review and identify only blocking data gaps"
    else:
        target = "Data Received"
        next_action = "Review active file classification, detected fields and canonical mappings"

    changed = company.stage != target or company.next_action != next_action
    company.stage = target
    company.next_action = next_action
    return changed


def jsonable(row: dict[str, Any]) -> dict[str, Any]:
    return {key: (value.isoformat() if isinstance(value, datetime) else value) for key, value in row.items()}


# Compatibility aliases used while the old release-numbered modules are retired.
_CompanyView = CompanyView
_reconcile_stage = reconcile_stage
_jsonable = jsonable
_source_id_for_file = source_id_for_file
_default_state = default_state
_now = now_utc
_COMPANY1_TEST_FIXTURES = COMPANY1_TEST_FIXTURES

__all__ = [
    "DOMAIN_VERSION",
    "VALID_STATES",
    "COMPANY1_TEST_FIXTURES",
    "CompanyView",
    "active_intake_files",
    "default_state",
    "effective_readiness_evidence",
    "ensure_lifecycle_rows",
    "ensure_lifecycle_schema",
    "inactive_source_filenames",
    "jsonable",
    "lifecycle_map",
    "lifecycle_rows",
    "now_utc",
    "reconcile_stage",
    "source_id_for_file",
    "_CompanyView",
    "_reconcile_stage",
    "_jsonable",
    "_source_id_for_file",
    "_default_state",
    "_now",
    "_COMPANY1_TEST_FIXTURES",
]
