import os
from threading import Lock

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv("DATABASE_URL")
IS_VERCEL = bool(os.getenv("VERCEL"))

# Normalize common Postgres URLs to psycopg v3.
if DATABASE_URL:
    if DATABASE_URL.startswith("postgres://"):
        DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg://", 1)
    elif DATABASE_URL.startswith("postgresql://") and not DATABASE_URL.startswith("postgresql+psycopg://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg://", 1)

# Local development can use SQLite. Vercel's /tmp fallback is disposable and is
# only a preview safety net; real Preview/Production should set DATABASE_URL.
if not DATABASE_URL:
    DATABASE_URL = "sqlite:////tmp/primestride_client_os.db" if IS_VERCEL else "sqlite:///./primestride_client_os.db"

is_sqlite = DATABASE_URL.startswith("sqlite")
engine_kwargs = {"future": True}

if is_sqlite:
    engine_kwargs.update(
        connect_args={"check_same_thread": False},
        poolclass=NullPool,
    )
elif IS_VERCEL:
    engine_kwargs.update(
        poolclass=NullPool,
        connect_args={"prepare_threshold": None},
    )
else:
    engine_kwargs.update(
        pool_pre_ping=True,
        pool_recycle=300,
    )

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


class Base(DeclarativeBase):
    pass


_schema_lock = Lock()
_schema_ready = False

# Alembic is authoritative from v1.5 onward. This escape hatch is intentionally
# explicit for disposable local experiments only; normal environments should run
# `alembic upgrade head` before the application starts.
RUNTIME_SCHEMA_BOOTSTRAP = os.getenv("RUNTIME_SCHEMA_BOOTSTRAP", "").strip().lower() in {"1", "true", "yes", "on"}
CORE_SCHEMA_SENTINELS = {"companies", "intake_files", "readiness_evidence"}


def ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return

        if RUNTIME_SCHEMA_BOOTSTRAP:
            Base.metadata.create_all(bind=engine)
        else:
            inspector = inspect(engine)
            missing = sorted(name for name in CORE_SCHEMA_SENTINELS if not inspector.has_table(name))
            if missing:
                raise RuntimeError(
                    "Database schema is not migrated. Missing: "
                    + ", ".join(missing)
                    + ". Run `alembic upgrade head` before starting Client OS."
                )
        _schema_ready = True


def get_db():
    ensure_schema()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
