"""Compatibility adapter for the former v0.9.2 section-aware AI module.

Production schemas, prompt validation, and HTTP routing moved to ``app.ai`` in
v1.3.4. Historical exports remain available for older imports.
"""
from .ai.router import install_ai_routes
from .ai.schema import CANONICAL_TARGETS_092, OUTPUT_SCHEMA_092
from .ai.service import _prompt_092, _validated_result_092

VERSION = "0.9.2"


def install_v092_ai(app):
    return install_ai_routes(app)


__all__ = [
    "VERSION",
    "CANONICAL_TARGETS_092",
    "OUTPUT_SCHEMA_092",
    "_prompt_092",
    "_validated_result_092",
    "install_v092_ai",
]
