"""Test fixtures. Uses an isolated temp SQLite DB and the mock LLM provider."""

from __future__ import annotations

import os
import tempfile

import pytest

# Configure environment BEFORE importing app modules.
_tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
os.environ["DATABASE_URL"] = f"sqlite:///{_tmp.name}"
os.environ["DEMO_MODE"] = "true"
os.environ["LLM_PROVIDER"] = "mock"


@pytest.fixture(scope="session")
def seeded_session():
    from app.db import SessionLocal, init_db
    from app.seed import seed

    init_db()
    session = SessionLocal()
    seed(session)
    yield session
    session.close()


@pytest.fixture()
def session():
    from app.db import SessionLocal, init_db

    init_db()
    s = SessionLocal()
    yield s
    s.close()
