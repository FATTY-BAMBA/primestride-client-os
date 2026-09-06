from app.db import SessionLocal
from app.lineage.service import record_source_reference
from app.models import Company, IntakeFile


def test_source_reference_identity_and_object_location_are_immutable():
    db = SessionLocal()
    try:
        company = Company(name="Regression Lineage Co", industry="Test", stage="Data Requested")
        db.add(company)
        db.flush()
        intake = IntakeFile(
            company_id=company.id,
            filename="original.csv",
            category="quotes",
            status="Received",
            source="Source Vault",
        )
        db.add(intake)
        db.flush()

        base = {
            "source_id": "src_regression_immutable",
            "tenant_key": f"c{company.id:04d}-regression",
            "sha256": "a" * 64,
            "bytes": 123,
            "content_type": "text/csv",
            "original_filename": "original.csv",
            "object_key": "tenants/regression/originals/immutable.csv",
            "bucket": "private-bucket",
            "storage_provider": "test",
            "immutable": True,
        }
        first = record_source_reference(
            db,
            company_id=company.id,
            intake_file_id=intake.id,
            manifest=base,
        )
        changed = dict(base)
        changed["object_key"] = "tenants/regression/originals/SHOULD-NOT-REPLACE.csv"
        changed["sha256"] = "b" * 64
        second = record_source_reference(
            db,
            company_id=company.id,
            intake_file_id=intake.id,
            manifest=changed,
        )

        assert second["source_id"] == first["source_id"]
        assert second["object_key"] == first["object_key"]
        assert second["sha256"] == first["sha256"]
    finally:
        db.rollback()
        db.close()
