"""
config.py -- environment-driven settings.

NOTE ON DATABASE_URL DEFAULT: this dev environment has no usable Docker
install (Docker Desktop's service is registered but its program files are
absent -- confirmed while building this backend), so Postgres-via-Docker
isn't actually runnable here today. `docker-compose.yml` still stands ready
for when Docker *is* available (Blueprint Section 21/22 require it), and the
SQLAlchemy models below are plain, dialect-agnostic column types that run
unchanged against Postgres. Until then, DATABASE_URL defaults to a local
SQLite file so the rest of the stack (API, seeding, endpoints) can actually
run and be tested today, per this session's instructions to run things for
real rather than only writing code for them.
"""

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
DEFAULT_SQLITE_PATH = BACKEND_DIR / "predictrace.db"

DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DEFAULT_SQLITE_PATH}")
DATA_DIR = os.getenv("DATA_DIR", str(BACKEND_DIR.parent / "data" / "output"))
MODEL_ARTIFACTS_DIR = os.getenv(
    "MODEL_ARTIFACTS_DIR", str(BACKEND_DIR / "app" / "ml" / "artifacts")
)
