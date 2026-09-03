import os
from threading import Lock

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import NullPool

DATABASE_URL = os.getenv("DATABASE_URL")
IS_VERCEL = bool(os.getenv("VERCEL"))

# Local development can use a normal SQLite file. Vercel previews use /tmp only
# as a disposable demo fallback; production should always set DATABASE_URL to
# persistent PostgreSQL.
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
    """Create tables lazily once per runtime instance.

    This does not rely solely on ASGI startup hooks, which makes the app more
    resilient in serverless runtimes where instances can be created/frozen at
    different times.
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
