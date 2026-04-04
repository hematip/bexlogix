"""Unit guard to block deprecated SQLAlchemy db.bind usage in page layer."""

# Purpose: Prevent deprecated DB access anti-patterns in Streamlit pages.
# Workflow Role: Keeps page layer query contracts aligned with SQLAlchemy 2.0.

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_no_deprecated_db_bind_usage_in_client_pages() -> None:
    # Contract: Client page modules must not reference db.bind directly.
    root = Path(__file__).resolve().parents[2]
    page_files = list((root / "client" / "pages").glob("*.py"))
    offenders = []
    for path in page_files:
        text = path.read_text(encoding="utf-8")
        if "db.bind" in text:
            offenders.append(str(path))
    assert offenders == []
