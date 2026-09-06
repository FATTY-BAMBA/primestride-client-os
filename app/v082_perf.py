"""Compatibility adapter for the former v0.8.5 page/readiness overlay.

Production readiness scoring moved to ``app.readiness.scoring`` and the remaining
page-specific workspace routes moved to ``app.workspace`` in v1.3.3.
"""
from .lifecycle.router import install_lifecycle_routes
from .readiness.router import install_readiness_routes
from .readiness.scoring import (
    GAP_REQUEST_COPY,
    _gap_intelligence,
    _honest_summaries,
    _honest_summary,
)
from .workspace.router import install_workspace_routes

VERSION = "0.8.5"


def install_v082_perf(app):
    """Backward-compatible installer alias for the stable route owners."""
    install_lifecycle_routes(app)
    install_readiness_routes(app)
    install_workspace_routes(app)


__all__ = [
    "VERSION",
    "GAP_REQUEST_COPY",
    "_honest_summary",
    "_honest_summaries",
    "_gap_intelligence",
    "install_v082_perf",
]
