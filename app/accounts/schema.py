"""Database contract for repeatable client/tenant provisioning."""
from __future__ import annotations

from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, UniqueConstraint

accounts_metadata = MetaData()

tenant_configs = Table(
    "tenant_configs",
    accounts_metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, nullable=False),
    Column("tenant_key", String(120), nullable=False),
    Column("slug", String(80), nullable=False),
    Column("locale", String(32), nullable=False),
    Column("timezone", String(64), nullable=False),
    Column("lifecycle_default", String(24), nullable=False),
    Column("onboarding_status", String(40), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("company_id", name="uq_tenant_configs_company"),
    UniqueConstraint("tenant_key", name="uq_tenant_configs_tenant_key"),
)

__all__ = ["accounts_metadata", "tenant_configs"]
