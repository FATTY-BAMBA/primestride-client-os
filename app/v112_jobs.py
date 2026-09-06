"""Compatibility adapter for the former v1.1.2 job-recovery module.

Production wiring moved to ``app.jobs`` in v1.3. Older imports continue to work
while the remaining intake/AI modules migrate to stable domain packages.
"""
from .jobs.router import install_job_routes
from .jobs.service import (
    RECOVERABLE_STATUSES,
    RETRYABLE_STATUSES,
    get_job as _job,
    get_source as _source,
    get_source_lifecycle as _source_lifecycle,
    insert_retry_job as _insert_retry_job,
    jsonable as _jsonable,
    now_utc as _now,
    read_original as _read_original,
    recover_provider_state,
    start_provider_retry as _start_provider_retry,
)

VERSION = "1.1.2"


def install_v112_jobs(app):
    """Backward-compatible installer alias."""
    return install_job_routes(app)


__all__ = [
    "VERSION",
    "RETRYABLE_STATUSES",
    "RECOVERABLE_STATUSES",
    "_now",
    "_job",
    "_source",
    "_source_lifecycle",
    "_read_original",
    "_start_provider_retry",
    "_insert_retry_job",
    "recover_provider_state",
    "_jsonable",
    "install_v112_jobs",
]
