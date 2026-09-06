"""Stable account and tenant provisioning domain."""

from .router import install_account_routes
from .service import ensure_tenant_config, get_tenant_config, tenant_key_for_company

__all__ = [
    "install_account_routes",
    "ensure_tenant_config",
    "get_tenant_config",
    "tenant_key_for_company",
]
