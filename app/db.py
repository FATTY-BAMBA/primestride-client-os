import os
from threading import Lock

from sqlalchemy import create_engine
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
    # Vercel + transaction-pooler path. NullPool avoids stale serverless
    # connections. We intentionally do not enable pool_pre_ping here because
    # NullPool opens a new connection per checkout and pre_ping would add an
    # extra network round trip to every request.
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

# Runtime create_all was useful while the prototype was changing daily, but on
# serverless Postgres it creates avoidable cold-start database work. Existing
# Preview/Production databases are now treated as provisioned. Set
# RUNTIME_SCHEMA_BOOTSTRAP=1 only when intentionally bootstrapping a fresh DB.
RUNTIME_SCHEMA_BOOTSTRAP = os.getenv("RUNTIME_SCHEMA_BOOTSTRAP", "").strip().lower() in {"1", "true", "yes", "on"}


def ensure_schema() -> None:
    global _schema_ready
    if _schema_ready:
        return
    with _schema_lock:
        if _schema_ready:
            return
        if is_sqlite or not IS_VERCEL or RUNTIME_SCHEMA_BOOTSTRAP:
            Base.metadata.create_all(bind=engine)
        _schema_ready = True


def get_db():
    ensure_schema()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# v1.2 compatibility bridge.
#
# app/main.py still constructs FastAPI during module import. Until that file is
# moved behind an application factory, route-shadowing extensions must install at
# construction time so they remain ahead of legacy prototype routes. The actual
# extension registry now lives in platform_bootstrap.py; database infrastructure
# no longer owns component imports or route ordering.
def _install_app_factory_compatibility_bridge() -> None:
    try:
        from fastapi import FastAPI

        if getattr(FastAPI, "_primestride_platform_bridge", False):
            return

        original_init = FastAPI.__init__

        def wrapped_init(self, *args, **kwargs):
            original_init(self, *args, **kwargs)
            from .platform_bootstrap import install_platform_extensions
            install_platform_extensions(self)

        FastAPI.__init__ = wrapped_init
        FastAPI._primestride_platform_bridge = True
    except Exception as exc:
        print(f"[PrimeStride platform bridge] warning: {exc!r}")


_install_app_factory_compatibility_bridge()
