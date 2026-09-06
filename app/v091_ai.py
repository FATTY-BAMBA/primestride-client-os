"""Compatibility adapter for the former v0.9.1 AI resilience layer.

Production AI routing moved to ``app.ai`` in v1.3.4.
"""
from .ai.router import install_ai_routes

VERSION = "0.9.1"


def install_v091_ai(app):
    return install_ai_routes(app)


__all__ = ["VERSION", "install_v091_ai"]
