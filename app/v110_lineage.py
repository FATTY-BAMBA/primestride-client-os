"""Compatibility adapter for the former v1.1 lineage implementation.

Production wiring moved to ``app.lineage`` in v1.3. Existing imports from older
intake/AI modules remain valid while those modules are migrated domain by domain.
"""
from .lineage.router import install_lineage_routes
from .lineage.schema import ingestion_jobs, lineage_metadata, source_references
from .lineage.service import (
    MANIFEST_PREFIX,
    backfill_source_references,
    create_ingestion_job,
    ensure_lineage_schema,
    find_source_by_id,
    find_source_by_sha,
    jsonable as _jsonable,
    manifest_from_notes,
    record_source_reference,
    update_ingestion_job,
)

VERSION = "1.1.0"


def install_v110_lineage(app):
    """Backward-compatible installer alias."""
    return install_lineage_routes(app)


__all__ = [
    "VERSION",
    "MANIFEST_PREFIX",
    "lineage_metadata",
    "source_references",
    "ingestion_jobs",
    "ensure_lineage_schema",
    "manifest_from_notes",
    "record_source_reference",
    "backfill_source_references",
    "find_source_by_id",
    "find_source_by_sha",
    "create_ingestion_job",
    "update_ingestion_job",
    "_jsonable",
    "install_v110_lineage",
]
