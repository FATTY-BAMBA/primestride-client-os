import os
from threading import Lock

from sqlalchemy import create_engine
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
    # serverless/auto-scaling workloads. Supavisor owns the connection pooling.
    engine_kwargs.update(
        poolclass=NullPool,
        pool_pre_ping=True,
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
        _schema_ready = True


def get_db():
    ensure_schema()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
