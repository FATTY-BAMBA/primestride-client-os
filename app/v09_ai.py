"""Compatibility adapter for the former v0.9 multimodal intake module.

Production AI routing moved to ``app.ai`` in v1.3.4.
"""
from .ai.router import install_ai_routes
from .ai.schema import (
    CANONICAL_TARGETS,
    CATEGORY_VALUES,
    OUTPUT_SCHEMA,
    READINESS_KEYS,
)
from .ai.service import (
    MAX_AI_FILE_BYTES,
    OPENAI_API_KEY,
    OPENAI_MODEL,
    OPENAI_RESPONSES_URL,
    SUPPORTED_FILE_TYPES,
    SUPPORTED_IMAGE_TYPES,
    _extract_output_text,
    _prompt,
    _validated_result,
)

VERSION = "0.9.0"


def install_v09_ai(app):
    return install_ai_routes(app)


__all__ = [
    "VERSION",
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_RESPONSES_URL",
    "MAX_AI_FILE_BYTES",
    "SUPPORTED_IMAGE_TYPES",
    "SUPPORTED_FILE_TYPES",
    "CATEGORY_VALUES",
    "CANONICAL_TARGETS",
    "READINESS_KEYS",
    "OUTPUT_SCHEMA",
    "_prompt",
    "_extract_output_text",
    "_validated_result",
    "install_v09_ai",
]
