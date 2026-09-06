"""Repeatable multi-client provisioning services.

Every Company gets a durable tenant identity before client files arrive. The
identity is intentionally separate from the mutable company name so renaming an
account never changes its object-storage namespace or source lineage.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import inspect, insert, select, update

from ..lineage.schema import source_references
from ..models import Company, ModuleFit
from .schema import tenant_configs

DOMAIN_VERSION = "1.6.0"
DEFAULT_LOCALE = "zh-Hant"
DEFAULT_TIMEZONE = "Asia/Taipei"
DEFAULT_LIFECYCLE = "active"
DEFAULT_ONBOARDING_STATUS = "provisioned"
# Compatibility seed only: preserves the already-published first-client namespace
# on fresh installs before any SourceReference exists. Future tenants do not use
# a broad name heuristic.
COMPATIBILITY_NAME_ALIASES = {"菘佑有限公司": "songyou"}


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def ascii_slug(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
    return slug[:64]


def tenant_config_table_available(db) -> bool:
    try:
        return inspect(db.get_bind()).has_table("tenant_configs")
    except Exception:
        return False


def _existing_source_tenant_key(db, company_id: int) -> str | None:
    """Reuse a historical tenant namespace if Source Vault already created one."""
    try:
        if not inspect(db.get_bind()).has_table("source_references"):
            return None
        row = db.execute(
            select(source_references.c.tenant_key)
            .where(
                source_references.c.company_id == company_id,
                source_references.c.tenant_key.is_not(None),
            )
            .order_by(source_references.c.id.desc())
            .limit(1)
        ).first()
        return str(row[0]).strip() if row and row[0] else None
    except Exception:
        return None


def _slug_from_tenant_key(company_id: int, tenant_key: str | None) -> str | None:
    if not tenant_key:
        return None
    prefix = f"c{company_id:04d}-"
    if tenant_key.startswith(prefix):
        slug = ascii_slug(tenant_key[len(prefix):])
        return slug or None
    return None


def derive_tenant_identity(db, company: Company, requested_slug: str | None = None) -> dict[str, str]:
    requested = ascii_slug(requested_slug or "")
    historical_key = _existing_source_tenant_key(db, company.id)
    historical_slug = _slug_from_tenant_key(company.id, historical_key)
    compatibility_slug = COMPATIBILITY_NAME_ALIASES.get(company.name)
    slug = requested or historical_slug or compatibility_slug or ascii_slug(company.name) or "client"
    tenant_key = historical_key if historical_slug and not requested else f"c{company.id:04d}-{slug}"
    return {"slug": slug, "tenant_key": tenant_key}


def get_tenant_config(db, company_id: int) -> dict[str, Any] | None:
    if not tenant_config_table_available(db):
        return None
    row = db.execute(
        select(tenant_configs).where(tenant_configs.c.company_id == company_id)
    ).mappings().first()
    return dict(row) if row else None


def ensure_tenant_config(
    db,
    company: Company,
    *,
    slug: str | None = None,
    locale: str | None = None,
    timezone_name: str | None = None,
) -> dict[str, Any]:
    """Return the company's stable tenant config, creating it when possible.

    Deployments whose production database has not yet adopted the latest Alembic
    revision degrade safely to a derived non-persisted identity. Once migrations
    are applied, the next call persists the same namespace.
    """
    existing = get_tenant_config(db, company.id)
    now = now_utc()
    if existing:
        changes: dict[str, Any] = {}
        if locale and locale.strip() and locale.strip() != existing.get("locale"):
            changes["locale"] = locale.strip()[:32]
        if timezone_name and timezone_name.strip() and timezone_name.strip() != existing.get("timezone"):
            changes["timezone"] = timezone_name.strip()[:64]
        if changes:
            changes["updated_at"] = now
            db.execute(
                update(tenant_configs)
                .where(tenant_configs.c.company_id == company.id)
                .values(**changes)
            )
            existing = get_tenant_config(db, company.id) or existing
        existing["persisted"] = True
        return existing

    identity = derive_tenant_identity(db, company, requested_slug=slug)
    fallback = {
        "id": None,
        "company_id": company.id,
        "tenant_key": identity["tenant_key"],
        "slug": identity["slug"],
        "locale": (locale or DEFAULT_LOCALE).strip()[:32] or DEFAULT_LOCALE,
        "timezone": (timezone_name or DEFAULT_TIMEZONE).strip()[:64] or DEFAULT_TIMEZONE,
        "lifecycle_default": DEFAULT_LIFECYCLE,
        "onboarding_status": DEFAULT_ONBOARDING_STATUS,
        "created_at": now,
        "updated_at": now,
        "persisted": False,
    }
    if not tenant_config_table_available(db):
        return fallback

    db.execute(insert(tenant_configs).values(
        company_id=company.id,
        tenant_key=fallback["tenant_key"],
        slug=fallback["slug"],
        locale=fallback["locale"],
        timezone=fallback["timezone"],
        lifecycle_default=fallback["lifecycle_default"],
        onboarding_status=fallback["onboarding_status"],
        created_at=now,
        updated_at=now,
    ))
    created = get_tenant_config(db, company.id) or fallback
    created["persisted"] = True
    return created


def tenant_key_for_company(db, company: Company) -> str:
    return str(ensure_tenant_config(db, company)["tenant_key"])


def provisioning_snapshot(db, company: Company) -> dict[str, Any]:
    config = ensure_tenant_config(db, company)
    modules = [
        int(row.module_no)
        for row in db.scalars(
            select(ModuleFit)
            .where(ModuleFit.company_id == company.id, ModuleFit.fit == "High")
            .order_by(ModuleFit.module_no)
        ).all()
    ]
    return {
        "version": DOMAIN_VERSION,
        "company_id": company.id,
        "company_name": company.name,
        "tenant_key": config["tenant_key"],
        "slug": config["slug"],
        "locale": config["locale"],
        "timezone": config["timezone"],
        "lifecycle_default": config["lifecycle_default"],
        "onboarding_status": config["onboarding_status"],
        "persisted": bool(config.get("persisted")),
        "storage_prefix": f"tenants/{config['tenant_key']}/originals/",
        "priority_modules": modules,
    }


__all__ = [
    "DOMAIN_VERSION",
    "DEFAULT_LOCALE",
    "DEFAULT_TIMEZONE",
    "DEFAULT_LIFECYCLE",
    "COMPATIBILITY_NAME_ALIASES",
    "ascii_slug",
    "derive_tenant_identity",
    "tenant_config_table_available",
    "get_tenant_config",
    "ensure_tenant_config",
    "tenant_key_for_company",
    "provisioning_snapshot",
]
