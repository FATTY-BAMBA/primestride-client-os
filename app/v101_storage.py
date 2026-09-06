"""Compatibility adapter for the former v1.0.1 tenant-readable Source Vault.

Production storage routing moved to ``app.storage`` in v1.3.2. Tenant-key and
storage helper imports remain available for older modules during consolidation.
"""
from .storage.router import install_storage_routes
from .storage.service import (
    DEFAULT_NAME_ALIASES as _DEFAULT_NAME_ALIASES,
    _ascii_slug,
    _slug_overrides,
    tenant_key,
)

VERSION = "1.0.1"


def install_v101_storage(app):
    """Backward-compatible installer alias."""
    return install_storage_routes(app)


__all__ = [
    "VERSION",
    "_DEFAULT_NAME_ALIASES",
    "_ascii_slug",
    "_slug_overrides",
    "tenant_key",
    "install_v101_storage",
]
