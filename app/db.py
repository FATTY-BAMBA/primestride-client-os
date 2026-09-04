import os
from datetime import datetime
from threading import Lock

from sqlalchemy import create_engine, text
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv("DATABASE_URL")
IS_VERCEL = bool(os.getenv("VERCEL"))

# Normalize standard Postgres URLs to the psycopg v3 SQLAlchemy driver. This lets
# us paste Supabase connection strings into Vercel without rewriting credentials.
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
    elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+psycopg://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Local development can use SQLite. Vercel may temporarily use /tmp only as a
# disposable preview fallback; real Preview/Production environments should set
# DATABASE_URL to Supabase Postgres.
if not DATABASE_URL:
    DATABASE_URL = (
        "sqlite:////tmp/primestride_client_os.db"
        if IS_VERCEL
        else "sqlite:///./primestride_client_os.db"
    )

is_sqlite = DATABASE_URL.startswith("sqlite")
engine_kwargs = {"future": True}

if is_sqlite:
    engine_kwargs.update(
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
elif IS_VERCEL:
    # Supabase recommends transaction-mode Supavisor + SQLAlchemy NullPool for
    # serverless/auto-scaling workloads. Transaction mode does not support
    # prepared statements, so psycopg automatic preparation is disabled.
    engine_kwargs.update(
        poolclass=NullPool,
        pool_pre_ping=True,
        connect_args={"prepare_threshold": None},
    )
else:
    engine_kwargs.update(
        pool_pre_ping=True,
        pool_recycle=300,
    )

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
    future=True,
)


class Base(DeclarativeBase):
    pass


_schema_lock = Lock()
_schema_ready = False


def _bootstrap_songyou_client() -> None:
    """Replace the original demo account with our first real implementation client.

    This is intentionally a temporary v0.2 bootstrap for the preview workspace.
    Once Alembic migrations and an explicit onboarding/import command exist, this
    logic should move out of schema initialization.
    """
    now = datetime.utcnow()
    real_name = "菘佑有限公司"
    demo_name = "ABC 印刷有限公司"

    with engine.begin() as conn:
        existing = conn.execute(
            text("SELECT id FROM companies WHERE name = :name LIMIT 1"),
            {"name": real_name},
        ).first()
        if existing:
            return

        demo = conn.execute(
            text("SELECT id FROM companies WHERE name = :name LIMIT 1"),
            {"name": demo_name},
        ).first()

        if demo:
            company_id = demo[0]
            # Remove placeholder/demo context so it is never mistaken for facts
            # learned from the real client.
            for table_name in (
                "pre_meeting_intakes",
                "pain_points",
                "discoveries",
                "meetings",
                "module_fits",
                "tasks",
                "readiness",
                "timeline_events",
            ):
                conn.execute(
                    text(f"DELETE FROM {table_name} WHERE company_id = :company_id"),
                    {"company_id": company_id},
                )

            conn.execute(
                text(
                    """
                    UPDATE companies
                    SET name = :name,
                        industry = :industry,
                        stage = :stage,
                        owner = :owner,
                        next_action = :next_action,
                        due_date = NULL,
                        next_meeting = NULL,
                        fit_status = :fit_status,
                        updated_at = :updated_at
                    WHERE id = :company_id
                    """
                ),
                {
                    "name": real_name,
                    "industry": "Printing",
                    "stage": "Data Requested",
                    "owner": "Abdoulie Fatty",
                    "next_action": "Await initial sample-data upload",
                    "fit_status": "Potential Fit",
                    "updated_at": now,
                    "company_id": company_id,
                },
            )
        else:
            conn.execute(
                text(
                    """
                    INSERT INTO companies
                        (name, industry, stage, owner, next_action, due_date,
                         next_meeting, fit_status, created_at, updated_at)
                    VALUES
                        (:name, :industry, :stage, :owner, :next_action, NULL,
                         NULL, :fit_status, :created_at, :updated_at)
                    """
                ),
                {
                    "name": real_name,
                    "industry": "Printing",
                    "stage": "Data Requested",
                    "owner": "Abdoulie Fatty",
                    "next_action": "Await initial sample-data upload",
                    "fit_status": "Potential Fit",
                    "created_at": now,
                    "updated_at": now,
                },
            )
            company_id = conn.execute(
                text("SELECT id FROM companies WHERE name = :name LIMIT 1"),
                {"name": real_name},
            ).scalar_one()

        conn.execute(
            text(
                """
                INSERT INTO pre_meeting_intakes
                    (company_id, top_improvements, primary_priority,
                     current_tools, company_size, owner_repetitive_task, updated_at)
                VALUES
                    (:company_id, :top_improvements, :primary_priority,
                     NULL, NULL, NULL, :updated_at)
                """
            ),
            {
                "company_id": company_id,
                "top_improvements": "AI Quoting; Work Order & Production Management; AI Analytics",
                "primary_priority": "Phase 0 data intake for modules 04, 05 and 06",
                "updated_at": now,
            },
        )

        module_names = {
            4: "AI 報價",
            5: "工單／生產管理",
            6: "AI 數據分析",
        }
        for module_no, module_name in module_names.items():
            conn.execute(
                text(
                    """
                    INSERT INTO module_fits
                        (company_id, module_no, module_name, fit, reason)
                    VALUES
                        (:company_id, :module_no, :module_name, 'High', :reason)
                    """
                ),
                {
                    "company_id": company_id,
                    "module_no": module_no,
                    "module_name": module_name,
                    "reason": "Client expressed interest during the initial meeting",
                },
            )

        timeline = [
            ("Meeting", "Initial client meeting completed", "Primary contact: Mei"),
            ("Data Request", "Phase 0 data checklist sent", "Initial sample request sent after the meeting"),
            ("Data Request", "Shared upload folder provided", "Awaiting the client's first sample-data upload"),
        ]
        for event_type, title, details in timeline:
            conn.execute(
                text(
                    """
                    INSERT INTO timeline_events
                        (company_id, event_type, title, details, created_at)
                    VALUES
                        (:company_id, :event_type, :title, :details, :created_at)
                    """
                ),
                {
                    "company_id": company_id,
                    "event_type": event_type,
                    "title": title,
                    "details": details,
                    "created_at": now,
                },
            )


def ensure_schema() -> None:
    """Temporary v0.2 bootstrap: create missing tables lazily once per runtime.

    This avoids relying solely on ASGI startup hooks. Before production use we
    will replace schema creation with versioned Alembic migrations.
    """
    global _schema_ready
    if _schema_ready:
        return

    with _schema_lock:
        if _schema_ready:
            return
        Base.metadata.create_all(bind=engine)
        _bootstrap_songyou_client()
        _schema_ready = True


def get_db():
    ensure_schema()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
