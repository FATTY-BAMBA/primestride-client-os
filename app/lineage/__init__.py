"""Stable lineage domain for PrimeStride Client OS.

Versioned v1.1 modules remain as compatibility adapters while production wiring
uses this package directly.
"""

from .schema import ingestion_jobs, source_references
from .service import (
    backfill_source_references,
    create_ingestion_job,
    ensure_lineage_schema,
    find_source_by_id,
    find_source_by_sha,
    manifest_from_notes,
    record_source_reference,
    update_ingestion_job,
)

__all__ = [
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
]
