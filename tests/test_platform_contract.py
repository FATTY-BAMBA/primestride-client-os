from sqlalchemy import inspect
from fastapi.testclient import TestClient

from app.db import engine, ensure_schema
from app.main import app


def test_alembic_baseline_owns_required_tables():
    ensure_schema()
    tables = set(inspect(engine).get_table_names())
    assert {
        "companies",
        "intake_files",
        "readiness_evidence",
        "source_references",
        "ingestion_jobs",
        "intake_source_lifecycle",
        "tenant_configs",
        "alembic_version",
    }.issubset(tables)


def test_platform_status_exposes_stable_architecture():
    with TestClient(app) as client:
        response = client.get("/api/platform/status")
    assert response.status_code == 200
    payload = response.json()
    assert payload["version"] == "1.6.0"
    assert payload["compatibility_bridge"] == "none"
    assert payload["tenant_provisioning"] == "persistent-tenant-config"
    assert set(payload["stable_domains"]) >= {
        "accounts", "lineage", "jobs", "readiness", "lifecycle", "intake", "storage", "workspace", "ai"
    }
