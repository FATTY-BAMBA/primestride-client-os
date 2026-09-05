"""Durable lineage tables.

This module owns the stable SQLAlchemy table definitions for immutable source
provenance and ingestion execution history.
"""
from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    UniqueConstraint,
)

lineage_metadata = MetaData()

source_references = Table(
    "source_references",
    lineage_metadata,
    Column("id", Integer, primary_key=True),
    Column("source_id", String(80), nullable=False),
    Column("company_id", Integer, nullable=False),
    Column("intake_file_id", Integer, nullable=True),
    Column("tenant_key", String(120), nullable=True),
    Column("original_filename", String(300), nullable=False),
    Column("object_key", Text, nullable=False),
    Column("bucket", String(250), nullable=True),
    Column("sha256", String(64), nullable=False),
    Column("mime_type", String(180), nullable=True),
    Column("byte_size", BigInteger, nullable=True),
    Column("storage_provider", String(120), nullable=True),
    Column("immutable", Boolean, nullable=False, default=True),
    Column("parent_source_id", String(80), nullable=True),
    Column("stored_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("source_id", name="uq_source_references_source_id"),
)
Index("ix_source_references_company", source_references.c.company_id)
Index("ix_source_references_company_sha", source_references.c.company_id, source_references.c.sha256)
Index("ix_source_references_intake_file", source_references.c.intake_file_id)

ingestion_jobs = Table(
    "ingestion_jobs",
    lineage_metadata,
    Column("id", Integer, primary_key=True),
    Column("job_key", String(220), nullable=False),
    Column("company_id", Integer, nullable=False),
    Column("source_id", String(80), nullable=True),
    Column("intake_file_id", Integer, nullable=True),
    Column("job_type", String(60), nullable=False),
    Column("status", String(40), nullable=False),
    Column("engine_version", String(80), nullable=True),
    Column("model", String(160), nullable=True),
    Column("provider_job_id", String(220), nullable=True),
    Column("attempt", Integer, nullable=False, default=1),
    Column("error_code", String(120), nullable=True),
    Column("error_detail", Text, nullable=True),
    Column("result_summary", Text, nullable=True),
    Column("started_at", DateTime(timezone=True), nullable=True),
    Column("completed_at", DateTime(timezone=True), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("job_key", name="uq_ingestion_jobs_job_key"),
)
Index("ix_ingestion_jobs_company", ingestion_jobs.c.company_id)
Index("ix_ingestion_jobs_source", ingestion_jobs.c.source_id)
Index("ix_ingestion_jobs_provider", ingestion_jobs.c.provider_job_id)
Index("ix_ingestion_jobs_company_status", ingestion_jobs.c.company_id, ingestion_jobs.c.status)
