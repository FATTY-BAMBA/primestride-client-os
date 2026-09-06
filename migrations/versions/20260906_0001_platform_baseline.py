"""PrimeStride Client OS platform baseline.

Revision ID: 20260906_0001
Revises: None

This is the transition from prototype-time create_all() provisioning to Alembic.
It is deliberately adoption-safe: existing production tables are preserved, and
missing tables/indexes are created for fresh environments. Downgrade is
non-destructive because this revision may be stamped onto databases that existed
before Alembic ownership.
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260906_0001"
down_revision = None
branch_labels = None
depends_on = None


def _has_table(name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(name)


def _ensure_index(table: str, name: str, columns: list[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table(table):
        return
    existing = {idx["name"] for idx in inspector.get_indexes(table)}
    if name not in existing:
        op.create_index(name, table, columns, unique=False)


def upgrade() -> None:
    if not _has_table("companies"):
        op.create_table(
            "companies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("industry", sa.String(120), nullable=True),
            sa.Column("stage", sa.String(60), nullable=False),
            sa.Column("owner", sa.String(120), nullable=True),
            sa.Column("next_action", sa.String(300), nullable=True),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("next_meeting", sa.DateTime(), nullable=True),
            sa.Column("fit_status", sa.String(30), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    _ensure_index("companies", "ix_companies_name", ["name"])

    if not _has_table("pre_meeting_intakes"):
        op.create_table(
            "pre_meeting_intakes",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, unique=True),
            sa.Column("top_improvements", sa.Text(), nullable=True),
            sa.Column("primary_priority", sa.Text(), nullable=True),
            sa.Column("current_tools", sa.Text(), nullable=True),
            sa.Column("company_size", sa.String(80), nullable=True),
            sa.Column("owner_repetitive_task", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    if not _has_table("discoveries"):
        op.create_table(
            "discoveries",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False, unique=True),
            sa.Column("current_flow", sa.Text(), nullable=True),
            sa.Column("biggest_bottleneck", sa.Text(), nullable=True),
            sa.Column("key_person_dependency", sa.Text(), nullable=True),
            sa.Column("repeated_questions", sa.Text(), nullable=True),
            sa.Column("quote_process", sa.Text(), nullable=True),
            sa.Column("production_tracking", sa.Text(), nullable=True),
            sa.Column("management_metrics", sa.Text(), nullable=True),
            sa.Column("priority_improvement", sa.Text(), nullable=True),
            sa.Column("existing_systems", sa.Text(), nullable=True),
            sa.Column("success_definition", sa.Text(), nullable=True),
            sa.Column("baseline_notes", sa.Text(), nullable=True),
            sa.Column("customer_words", sa.Text(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )

    if not _has_table("meetings"):
        op.create_table(
            "meetings",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("meeting_type", sa.String(60), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=True),
            sa.Column("completed_at", sa.DateTime(), nullable=False),
            sa.Column("completeness", sa.Float(), nullable=False),
            sa.Column("diagnosis_summary", sa.Text(), nullable=True),
            sa.Column("followup_draft", sa.Text(), nullable=True),
        )

    if not _has_table("pain_points"):
        op.create_table(
            "pain_points",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("rank", sa.Integer(), nullable=False),
            sa.Column("category", sa.String(120), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("severity", sa.String(20), nullable=False),
            sa.Column("customer_quote", sa.Text(), nullable=True),
        )

    if not _has_table("module_fits"):
        op.create_table(
            "module_fits",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("module_no", sa.Integer(), nullable=False),
            sa.Column("module_name", sa.String(100), nullable=False),
            sa.Column("fit", sa.String(20), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
        )

    if not _has_table("tasks"):
        op.create_table(
            "tasks",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("title", sa.String(250), nullable=False),
            sa.Column("owner", sa.String(120), nullable=True),
            sa.Column("due_date", sa.Date(), nullable=True),
            sa.Column("done", sa.Boolean(), nullable=False),
        )

    if not _has_table("readiness"):
        op.create_table(
            "readiness",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("module_no", sa.Integer(), nullable=False),
            sa.Column("module_name", sa.String(100), nullable=False),
            sa.Column("score", sa.Float(), nullable=False),
            sa.Column("status", sa.String(100), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
        )

    if not _has_table("timeline_events"):
        op.create_table(
            "timeline_events",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("event_type", sa.String(80), nullable=False),
            sa.Column("title", sa.String(250), nullable=False),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )

    if not _has_table("client_memory"):
        op.create_table(
            "client_memory",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("kind", sa.String(30), nullable=False),
            sa.Column("title", sa.String(250), nullable=False),
            sa.Column("details", sa.Text(), nullable=True),
            sa.Column("source", sa.String(120), nullable=True),
            sa.Column("confidence", sa.String(20), nullable=False),
            sa.Column("active", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
        )
    _ensure_index("client_memory", "ix_client_memory_company_id", ["company_id"])
    _ensure_index("client_memory", "ix_client_memory_kind", ["kind"])

    if not _has_table("intake_files"):
        op.create_table(
            "intake_files",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("filename", sa.String(300), nullable=False),
            sa.Column("category", sa.String(80), nullable=False),
            sa.Column("status", sa.String(40), nullable=False),
            sa.Column("source", sa.String(80), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("received_at", sa.DateTime(), nullable=False),
        )
    _ensure_index("intake_files", "ix_intake_files_company_id", ["company_id"])

    if not _has_table("readiness_evidence"):
        op.create_table(
            "readiness_evidence",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("module_no", sa.Integer(), nullable=False),
            sa.Column("criterion_key", sa.String(100), nullable=False),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("source", sa.String(200), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
        )
    _ensure_index("readiness_evidence", "ix_readiness_evidence_company_id", ["company_id"])
    _ensure_index("readiness_evidence", "ix_readiness_evidence_module_no", ["module_no"])
    _ensure_index("readiness_evidence", "ix_readiness_evidence_criterion_key", ["criterion_key"])

    if not _has_table("decision_log"):
        op.create_table(
            "decision_log",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), sa.ForeignKey("companies.id"), nullable=False),
            sa.Column("title", sa.String(250), nullable=False),
            sa.Column("decision", sa.Text(), nullable=False),
            sa.Column("rationale", sa.Text(), nullable=True),
            sa.Column("source", sa.String(160), nullable=True),
            sa.Column("status", sa.String(30), nullable=False),
            sa.Column("decided_at", sa.DateTime(), nullable=False),
        )
    _ensure_index("decision_log", "ix_decision_log_company_id", ["company_id"])

    if not _has_table("source_references"):
        op.create_table(
            "source_references",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("source_id", sa.String(80), nullable=False),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("intake_file_id", sa.Integer(), nullable=True),
            sa.Column("tenant_key", sa.String(120), nullable=True),
            sa.Column("original_filename", sa.String(300), nullable=False),
            sa.Column("object_key", sa.Text(), nullable=False),
            sa.Column("bucket", sa.String(250), nullable=True),
            sa.Column("sha256", sa.String(64), nullable=False),
            sa.Column("mime_type", sa.String(180), nullable=True),
            sa.Column("byte_size", sa.BigInteger(), nullable=True),
            sa.Column("storage_provider", sa.String(120), nullable=True),
            sa.Column("immutable", sa.Boolean(), nullable=False),
            sa.Column("parent_source_id", sa.String(80), nullable=True),
            sa.Column("stored_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("source_id", name="uq_source_references_source_id"),
        )
    _ensure_index("source_references", "ix_source_references_company", ["company_id"])
    _ensure_index("source_references", "ix_source_references_company_sha", ["company_id", "sha256"])
    _ensure_index("source_references", "ix_source_references_intake_file", ["intake_file_id"])

    if not _has_table("ingestion_jobs"):
        op.create_table(
            "ingestion_jobs",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("job_key", sa.String(220), nullable=False),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("source_id", sa.String(80), nullable=True),
            sa.Column("intake_file_id", sa.Integer(), nullable=True),
            sa.Column("job_type", sa.String(60), nullable=False),
            sa.Column("status", sa.String(40), nullable=False),
            sa.Column("engine_version", sa.String(80), nullable=True),
            sa.Column("model", sa.String(160), nullable=True),
            sa.Column("provider_job_id", sa.String(220), nullable=True),
            sa.Column("attempt", sa.Integer(), nullable=False),
            sa.Column("error_code", sa.String(120), nullable=True),
            sa.Column("error_detail", sa.Text(), nullable=True),
            sa.Column("result_summary", sa.Text(), nullable=True),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("job_key", name="uq_ingestion_jobs_job_key"),
        )
    _ensure_index("ingestion_jobs", "ix_ingestion_jobs_company", ["company_id"])
    _ensure_index("ingestion_jobs", "ix_ingestion_jobs_source", ["source_id"])
    _ensure_index("ingestion_jobs", "ix_ingestion_jobs_provider", ["provider_job_id"])
    _ensure_index("ingestion_jobs", "ix_ingestion_jobs_company_status", ["company_id", "status"])

    if not _has_table("intake_source_lifecycle"):
        op.create_table(
            "intake_source_lifecycle",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("company_id", sa.Integer(), nullable=False),
            sa.Column("intake_file_id", sa.Integer(), nullable=False),
            sa.Column("source_id", sa.String(80), nullable=True),
            sa.Column("state", sa.String(24), nullable=False),
            sa.Column("reason", sa.String(500), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.UniqueConstraint("intake_file_id", name="uq_intake_source_lifecycle_file"),
        )
    _ensure_index("intake_source_lifecycle", "ix_intake_source_lifecycle_company", ["company_id"])
    _ensure_index("intake_source_lifecycle", "ix_intake_source_lifecycle_company_state", ["company_id", "state"])
    _ensure_index("intake_source_lifecycle", "ix_intake_source_lifecycle_source", ["source_id"])


def downgrade() -> None:
    # Non-destructive adoption baseline. Some databases predate Alembic and this
    # revision must never drop their existing business data during a downgrade.
    pass
