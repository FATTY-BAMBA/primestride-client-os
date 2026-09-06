"""Compatibility adapter for the former v1.1.1 source-lifecycle module.

Production wiring moved to ``app.lifecycle`` in v1.3.1. Older imports continue
to work while remaining intake/storage modules migrate to stable domains.
"""
from .lifecycle.router import install_lifecycle_routes
from .lifecycle.schema import intake_source_lifecycle, lifecycle_metadata
from .lifecycle.service import (
    VALID_STATES,
    _COMPANY1_TEST_FIXTURES,
    _CompanyView,
    _default_state,
    _jsonable,
    _now,
    _reconcile_stage,
    _source_id_for_file,
    active_intake_files,
    effective_readiness_evidence,
    ensure_lifecycle_rows,
    ensure_lifecycle_schema,
    inactive_source_filenames,
    lifecycle_map,
    lifecycle_rows,
)

VERSION = "1.1.1"


def install_v111_lifecycle(app):
    """Backward-compatible installer alias."""
    return install_lifecycle_routes(app)


__all__ = [
    "VERSION",
    "VALID_STATES",
    "lifecycle_metadata",
    "intake_source_lifecycle",
    "ensure_lifecycle_schema",
    "ensure_lifecycle_rows",
    "lifecycle_rows",
    "lifecycle_map",
    "active_intake_files",
    "inactive_source_filenames",
    "effective_readiness_evidence",
    "_CompanyView",
    "_reconcile_stage",
    "_jsonable",
    "_source_id_for_file",
    "_default_state",
    "_now",
    "_COMPANY1_TEST_FIXTURES",
    "install_v111_lifecycle",
]
