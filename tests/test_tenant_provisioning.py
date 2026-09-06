from __future__ import annotations

from app.accounts.service import ensure_tenant_config, tenant_key_for_company
from app.db import SessionLocal
from app.lineage.service import record_source_reference
from app.models import Company


def _company(db, name: str) -> Company:
    company = Company(name=name, stage="New Lead", next_action="Schedule first discovery meeting")
    db.add(company)
    db.flush()
    return company


def test_tenant_key_is_persisted_and_survives_company_rename():
    db = SessionLocal()
    try:
        company = _company(db, "Acme Manufacturing")
        config = ensure_tenant_config(db, company)
        original_key = config["tenant_key"]
        assert config["persisted"] is True
        assert original_key == f"c{company.id:04d}-acme-manufacturing"

        company.name = "Acme Renamed After Provisioning"
        db.flush()
        assert tenant_key_for_company(db, company) == original_key
        db.rollback()
    finally:
        db.close()


def test_explicit_slug_supports_non_ascii_company_names_without_hardcoding():
    db = SessionLocal()
    try:
        company = _company(db, "新園精密有限公司")
        config = ensure_tenant_config(db, company, slug="xin-yuan")
        assert config["tenant_key"] == f"c{company.id:04d}-xin-yuan"
        assert config["slug"] == "xin-yuan"
        db.rollback()
    finally:
        db.close()


def test_existing_source_namespace_is_adopted_before_new_config_is_created():
    db = SessionLocal()
    try:
        company = _company(db, "Historical Client")
        expected_key = f"c{company.id:04d}-historical"
        record_source_reference(
            db,
            company_id=company.id,
            intake_file_id=None,
            manifest={
                "source_id": "src_provisioning_history",
                "tenant_key": expected_key,
                "sha256": "a" * 64,
                "object_key": f"tenants/{expected_key}/originals/2026/09/file.pdf",
                "original_filename": "file.pdf",
                "content_type": "application/pdf",
                "bytes": 123,
                "storage_provider": "test",
                "immutable": True,
            },
        )
        config = ensure_tenant_config(db, company)
        assert config["tenant_key"] == expected_key
        assert config["slug"] == "historical"
        db.rollback()
    finally:
        db.close()
