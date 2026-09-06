from __future__ import annotations

import os
import tempfile
from pathlib import Path

from alembic import command
from alembic.config import Config

ROOT = Path(__file__).resolve().parents[1]
TEST_DB = Path(tempfile.gettempdir()) / f"primestride_client_os_test_{os.getpid()}.db"
if TEST_DB.exists():
    TEST_DB.unlink()

os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ.pop("VERCEL", None)
os.environ.pop("RUNTIME_SCHEMA_BOOTSTRAP", None)
os.environ.pop("OPENAI_API_KEY", None)

config = Config(str(ROOT / "alembic.ini"))
config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
command.upgrade(config, "head")


def pytest_sessionfinish(session, exitstatus):
    try:
        TEST_DB.unlink(missing_ok=True)
    except Exception:
        pass
