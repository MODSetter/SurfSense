"""Unit tests for registering a scraper run as a citation."""

from __future__ import annotations

import pytest

from app.agents.chat.multi_agent_chat.shared.citations import (
    CitationRegistry,
    CitationSourceType,
    to_frontend_payload,
)
from app.capabilities.core.access.run_citation import attach_run_citation

pytestmark = pytest.mark.unit


def test_attaches_run_and_returns_label_with_ordinal() -> None:
    registry = CitationRegistry()

    n, label = attach_run_citation(
        registry, run_external_id="run_abc-123", capability="walmart.scrape"
    )

    assert n == 1
    assert f"[{n}]" in label
    entry = registry.resolve(n)
    assert entry is not None
    assert entry.source_type is CitationSourceType.RUN
    assert to_frontend_payload(entry) == "run_abc-123"


def test_same_run_dedups_to_one_label() -> None:
    registry = CitationRegistry()

    first, _ = attach_run_citation(
        registry, run_external_id="run_x", capability="walmart.scrape"
    )
    again, _ = attach_run_citation(
        registry, run_external_id="run_x", capability="walmart.reviews"
    )

    assert first == again
    assert len(registry.by_n) == 1
