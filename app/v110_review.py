"""Compatibility adapter for the former v1.1 human-review gate module.

Production review routing moved to ``app.intake`` in v1.3.1.
"""
from .intake.router import install_intake_routes

VERSION = "1.1.0"


def install_v110_review(app):
    """Backward-compatible installer alias."""
    return install_intake_routes(app)


__all__ = ["VERSION", "install_v110_review"]
