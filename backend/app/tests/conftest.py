"""
conftest.py -- shared pytest fixtures.

Deliberately does NOT spin up an isolated in-memory test database or mock
the models. This project's whole ethos (see PROGRESS_LOG.md) is running
everything for real against real generated data -- these tests hit the
same seeded SQLite DB and the same trained model artifacts a developer has
on disk. Precondition: `python scripts/seed_db.py --data-dir data/output`
and `python -m ml.train` have already been run (from `backend/app`) before
`pytest` is invoked. If either hasn't, `test_models_ready` fails first with
a clear message instead of every other test failing confusingly.

Run with: `cd backend/app && ../venv/Scripts/python -m pytest`
"""

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c
