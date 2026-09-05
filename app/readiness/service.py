"""Stable readiness projection services.

Composes lifecycle filtering with deterministic readiness ranges and gap
intelligence. Lifecycle is now a stable domain; only the v0.8.5 deterministic
range helpers remain as compatibility dependencies for a later migration pass.
"""
from __future__ import annotations

from ..lifecycle.service import CompanyView, active_intake_files, effective_readiness_evidence
from ..v082_perf import _gap_intelligence, _honest_summaries

DOMAIN_VERSION = "1.3.1"


def build_readiness_projection(main_module, company, db) -> dict:
    """Return the lifecycle-safe deterministic readiness view for a company."""
    active = active_intake_files(db, company.id, list(company.intake_files))
    evidence = effective_readiness_evidence(company, db)
    view = CompanyView(company, intake_files=active, readiness_evidence=evidence)
    summaries = _honest_summaries(main_module, view)
    gap_intelligence = _gap_intelligence(summaries) if active else None
    return {
        "active_files": active,
        "effective_evidence": evidence,
        "view": view,
        "summaries": summaries,
        "gap_intelligence": gap_intelligence,
    }
