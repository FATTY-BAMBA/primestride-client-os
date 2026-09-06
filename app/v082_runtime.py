"""Compatibility adapter for the former v0.8.2 intake runtime.

Production deterministic intake routing moved to ``app.intake`` in v1.3.3.
Historical imports remain available while the frontend still reports the proven
0.8.4 browser inspection engine version.
"""
from sqlalchemy import func, select

from .intake.deterministic import (
    DATA_STAGES,
    EXPECTED_DATA_CATEGORIES,
    HASH_RE,
    TEMPLATES,
    VALID_CATEGORIES,
    _clear_file_evidence,
    _find_existing_file,
    _hash_from_notes,
    _memory_groups,
)
from .intake.router import install_intake_routes
from .lifecycle.service import reconcile_stage as _reconcile_stage
from .models import ReadinessEvidence

VERSION = "0.8.2"


def _active_evidence_count(db, company_id: int) -> int:
    return int(
        db.scalar(
            select(func.count(ReadinessEvidence.id)).where(
                ReadinessEvidence.company_id == company_id,
                ReadinessEvidence.status != "awaiting",
            )
        )
        or 0
    )


def install_v082(app):
    """Backward-compatible installer alias."""
    return install_intake_routes(app)


__all__ = [
    "VERSION",
    "EXPECTED_DATA_CATEGORIES",
    "VALID_CATEGORIES",
    "DATA_STAGES",
    "HASH_RE",
    "TEMPLATES",
    "_memory_groups",
    "_active_evidence_count",
    "_reconcile_stage",
    "_clear_file_evidence",
    "_hash_from_notes",
    "_find_existing_file",
    "install_v082",
]
