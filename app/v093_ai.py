"""Compatibility adapter for the former v0.9.3 background AI module.

Production background start/poll routing and first-class job recording moved to
``app.ai`` in v1.3.4.
"""
from .ai.router import install_ai_routes
from .ai.service import (
    _RESPONSE_ID_RE,
    _link_source,
    _provider_json,
    _record_job_state,
    _record_started_job,
)

VERSION = "0.9.3"


def install_v093_ai(app):
    return install_ai_routes(app)


__all__ = [
    "VERSION",
    "_RESPONSE_ID_RE",
    "_provider_json",
    "_link_source",
    "_record_started_job",
    "_record_job_state",
    "install_v093_ai",
]
