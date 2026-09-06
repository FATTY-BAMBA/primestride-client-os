"""Add durable tenant provisioning identity.

Revision ID: 20260906_0002
Revises: 20260906_0001

Each Client OS company receives one immutable tenant key used by Source Vault and
future tenant-scoped configuration. Existing source_references are consulted
first so already-retained object paths remain unchanged.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa

revision = "20260906_0002"
down_revision = "20260906_0001"
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")[:64]


def upgrade() -> None:
    if not _has_table("tenant_configs"):
        op.create_table(
            "tenant_configs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("tenant_key", sa.String(120), nullable=False),
            sa.Column("slug", sa.String(80), nullable=False),
            sa.Column("locale", sa.String(32), nullable=False),
            sa.Column("timezone", sa.String(64), nullable=False),
            sa.Column("lifecycle_default", sa.String(24), nullable=False),
            sa.Column("onboarding_status", sa.String(40), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("company_id", name="uq_tenant_configs_company"),
            sa.UniqueConstraint("tenant_key", name="uq_tenant_configs_tenant_key"),
        )

    bind = op.get_bind()
    existing_company_ids = {
        int(row[0]) for row in bind.execute(sa.text("SELECT company_id FROM tenant_configs")).all()
    }
    source_refs_available = _has_table("source_references")
    now = datetime.now(timezone.utc)

    companies = bind.execute(sa.text("SELECT id, name FROM companies ORDER BY id")).mappings().all()
    for company in companies:
        company_id = int(company["id"])
        if company_id in existing_company_ids:
            continue

        historical_key = None
        if source_refs_available:
            row = bind.execute(
                sa.text(
                    "SELECT tenant_key FROM source_references "
                    "WHERE company_id = :company_id AND tenant_key IS NOT NULL "
                    "ORDER BY id DESC LIMIT 1"
                ),
                {"company_id": company_id},
            ).first()
            historical_key = str(row[0]).strip() if row and row[0] else None

        prefix = f"c{company_id:04d}-"
        historical_slug = None
        if historical_key and historical_key.startswith(prefix):
            historical_slug = _slug(historical_key[len(prefix):]) or None

        # Preserve the already-published first-client namespace on fresh installs
        # where no SourceReference exists yet. This is a compatibility seed, not
        # a general filename/name heuristic for future tenants.
        if not historical_slug and company_id == 1 and str(company["name"]) == "菘佑有限公司":
            historical_slug = "songyou"

        slug = historical_slug or _slug(str(company["name"])) or "client"
        tenant_key = historical_key if historical_slug and historical_key else f"c{company_id:04d}-{slug}"

        bind.execute(
            sa.text(
                "INSERT INTO tenant_configs "
                "(company_id, tenant_key, slug, locale, timezone, lifecycle_default, onboarding_status, created_at, updated_at) "
                "VALUES (:company_id, :tenant_key, :slug, :locale, :timezone, :lifecycle_default, :onboarding_status, :created_at, :updated_at)"
            ),
            {
                "company_id": company_id,
                "tenant_key": tenant_key,
                "slug": slug,
                "locale": "zh-Hant",
                "timezone": "Asia/Taipei",
                "lifecycle_default": "active",
                "onboarding_status": "provisioned",
                "created_at": now,
                "updated_at": now,
            },
        )


def downgrade() -> None:
    # Tenant identity is referenced by immutable Source Vault object paths. Never
    # drop it automatically once adopted; rollback should be a forward migration.
    pass
