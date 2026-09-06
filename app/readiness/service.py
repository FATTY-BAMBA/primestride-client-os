"""Stable readiness projection services.

Composes lifecycle filtering with deterministic readiness ranges and next-gap
intelligence without depending on release-numbered runtime modules.
"""
from __future__ import annotations

from ..lifecycle.service import CompanyView, active_intake_files, effective_readiness_evidence
from .scoring import gap_intelligence, honest_summaries

DOMAIN_VERSION = "1.3.3"


def build_readiness_projection(main_module, company, db) -> dict:
    """Return the lifecycle-safe deterministic readiness view for a company."""
    active = active_intake_files(db, company.id, list(company.intake_files))
    evidence = effective_readiness_evidence(company, db)
    view = CompanyView(company, intake_files=active, readiness_evidence=evidence)
    summaries = honest_summaries(main_module, view)
    next_gaps = gap_intelligence(summaries) if active else None
    return {
        "active_files": active,
        "effective_evidence": evidence,
        "view": view,
        "summaries": summaries,
        "gap_intelligence": next_gaps,
    }
