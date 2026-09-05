"""Compatibility adapter for the former v1.0.1 source-first runtime module.

Production registration and review routing moved to ``app.intake`` in v1.3.1.
"""
from .intake.router import install_intake_routes
from .intake.service import (
    MANIFEST_PREFIX,
    _inspection_engine,
    _merge_notes_preserving_source,
)

VERSION = "1.1.0"


def install_v101_runtime(app):
    """Backward-compatible installer alias."""
    return install_intake_routes(app)


__all__ = [
    "VERSION",
    "MANIFEST_PREFIX",
    "_merge_notes_preserving_source",
    "_inspection_engine",
    "install_v101_runtime",
]
