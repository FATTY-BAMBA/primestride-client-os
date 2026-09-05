"""Stable readiness projection services.

This layer composes lifecycle filtering with deterministic readiness ranges and
gap intelligence. It intentionally depends on the still-versioned lifecycle and
v0.8.5 range helpers until those domains are migrated in later consolidation
passes.
"""
from __future__ import annotations

from ..v082_perf import _gap_intelligence, _honest_summaries
from ..v111_lifecycle import _CompanyView, active_intake_files, effective_readiness_evidence

DOMAIN_VERSION = "1.3.0"


def build_readiness_projection(main_module, company, db) -> dict:
    """Return the lifecycle-safe deterministic readiness view for a company."""
    active = active_intake_files(db, company.id, list(company.intake_files))
    evidence = effective_readiness_evidence(company, db)
    view = _CompanyView(company, intake_files=active, readiness_evidence=evidence)
    summaries = _honest_summaries(main_module, view)
    gap_intelligence = _gap_intelligence(summaries) if active else None
    return {
        "active_files": active,
        "effective_evidence": evidence,
        "view": view,
        "summaries": summaries,
        "gap_intelligence": gap_intelligence,
    }
