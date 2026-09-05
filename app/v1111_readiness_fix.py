"""Compatibility adapter for the former v1.1.1.3 readiness route.

Production wiring moved to ``app.readiness`` in v1.3. The old installer name is
kept so any external or historical imports remain valid during consolidation.
"""
from .readiness.router import install_readiness_routes
from .readiness.service import build_readiness_projection

VERSION = "1.1.1.3"


def install_v1111_readiness_fix(app):
    """Backward-compatible installer alias."""
    return install_readiness_routes(app)


__all__ = ["VERSION", "build_readiness_projection", "install_v1111_readiness_fix"]
