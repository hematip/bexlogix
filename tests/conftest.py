"""Shared pytest fixtures for isolated local test execution."""

# Purpose: Central pytest fixture definitions for test suite stability.
# Workflow Role: Builds per-test in-memory database sessions for deterministic tests.

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.app.models.model_registry import register_models
from server.db.base import Base


@pytest.fixture(scope="function")
def db() -> Session:
    # FIX: [TEST-01] In-memory SQLite for isolated deterministic tests.
    register_models()
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()
