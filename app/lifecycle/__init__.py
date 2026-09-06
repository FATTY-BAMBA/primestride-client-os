"""Stable source-lifecycle domain for PrimeStride Client OS."""

from .router import install_lifecycle_routes
from .service import (
    CompanyView,
    active_intake_files,
    effective_readiness_evidence,
    ensure_lifecycle_rows,
    ensure_lifecycle_schema,
    inactive_source_filenames,
    lifecycle_map,
    lifecycle_rows,
    reconcile_stage,
)

__all__ = [
    "install_lifecycle_routes",
    "CompanyView",
    "active_intake_files",
    "effective_readiness_evidence",
    "ensure_lifecycle_rows",
    "ensure_lifecycle_schema",
    "inactive_source_filenames",
    "lifecycle_map",
    "lifecycle_rows",
    "reconcile_stage",
]
