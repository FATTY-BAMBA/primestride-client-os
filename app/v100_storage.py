"""Compatibility adapter for the former v1.0 Source Vault module.

Production storage routing and helpers moved to ``app.storage`` in v1.3.2.
Older imports remain supported while the remaining AI/intake modules migrate.
"""
from .storage.router import install_storage_routes
from .storage.service import (
    ACCESS_KEY,
    ALLOWED_CATEGORIES,
    BUCKET,
    ENDPOINT,
    MANIFEST_PREFIX,
    MAX_SOURCE_BYTES,
    REGION,
    SECRET_KEY,
    SSE,
    _append_manifest,
    _configured,
    _manifest_from_notes,
    _provider_name,
    _public_manifest,
    _s3_client,
    _safe_name,
)

VERSION = "1.0.0"


def install_v100_storage(app):
    """Backward-compatible installer alias."""
    return install_storage_routes(app)


__all__ = [
    "VERSION",
    "MANIFEST_PREFIX",
    "MAX_SOURCE_BYTES",
    "BUCKET",
    "ENDPOINT",
    "REGION",
    "ACCESS_KEY",
    "SECRET_KEY",
    "SSE",
    "ALLOWED_CATEGORIES",
    "_configured",
    "_provider_name",
    "_s3_client",
    "_safe_name",
    "_manifest_from_notes",
    "_append_manifest",
    "_public_manifest",
    "install_v100_storage",
]
