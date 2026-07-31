"""Shared fixture: a real git engine in a temp dir (no infra, no fakes)."""

from __future__ import annotations

import pytest

from app.knowledge_store.engines.git import GitContentEngine


@pytest.fixture
def engine(tmp_path) -> GitContentEngine:
    # Virgin store: first use must bootstrap it, no setup ceremony.
    return GitContentEngine(tmp_path / "ws1", tmp_path / ".working_copies" / "ws1")
