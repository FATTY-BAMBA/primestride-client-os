"""Relational schema for intake source lifecycle state."""
from sqlalchemy import Column, DateTime, Index, Integer, MetaData, String, Table, UniqueConstraint

lifecycle_metadata = MetaData()

intake_source_lifecycle = Table(
    "intake_source_lifecycle",
    lifecycle_metadata,
    Column("id", Integer, primary_key=True),
    Column("company_id", Integer, nullable=False),
    Column("intake_file_id", Integer, nullable=False),
    Column("source_id", String(80), nullable=True),
    Column("state", String(24), nullable=False),
    Column("reason", String(500), nullable=True),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    UniqueConstraint("intake_file_id", name="uq_intake_source_lifecycle_file"),
)
Index("ix_intake_source_lifecycle_company", intake_source_lifecycle.c.company_id)
Index("ix_intake_source_lifecycle_company_state", intake_source_lifecycle.c.company_id, intake_source_lifecycle.c.state)
Index("ix_intake_source_lifecycle_source", intake_source_lifecycle.c.source_id)

__all__ = ["lifecycle_metadata", "intake_source_lifecycle"]
