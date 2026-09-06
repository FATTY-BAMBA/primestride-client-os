from sqlalchemy import update

from app.db import SessionLocal
from app.lifecycle.schema import intake_source_lifecycle
from app.lifecycle.service import active_intake_files, ensure_lifecycle_rows, reconcile_stage
from app.models import Company, IntakeFile, ReadinessEvidence


def test_test_sources_never_advance_operational_stage():
    db = SessionLocal()
    try:
        company = Company(
            name="Regression Lifecycle Co",
            industry="Test",
            stage="Data Requested",
            next_action="Await initial sample-data upload",
        )
        db.add(company)
        db.flush()
        item = IntakeFile(
            company_id=company.id,
            filename="synthetic-regression.csv",
            category="work_orders",
            status="Reviewed",
            source="Regression test",
        )
        db.add(item)
        db.flush()
        ensure_lifecycle_rows(db, company.id)

        db.execute(
            update(intake_source_lifecycle)
            .where(intake_source_lifecycle.c.intake_file_id == item.id)
            .values(state="test", reason="synthetic regression fixture")
        )
        reconcile_stage(db, company, [item])
        assert company.stage == "Data Requested"
        assert active_intake_files(db, company.id, [item]) == []

        db.execute(
            update(intake_source_lifecycle)
            .where(intake_source_lifecycle.c.intake_file_id == item.id)
            .values(state="active")
        )
        reconcile_stage(db, company, [item])
        assert company.stage == "Data Received"

        db.add(ReadinessEvidence(
            company_id=company.id,
            module_no=5,
            criterion_key="work_order_id",
            status="available",
            source=item.filename,
        ))
        db.flush()
        reconcile_stage(db, company, [item])
        assert company.stage == "Data Readiness"
    finally:
        db.rollback()
        db.close()
