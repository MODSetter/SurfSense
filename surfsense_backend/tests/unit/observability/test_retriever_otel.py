"""Tests for retriever OTel wrappers."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Any

import pytest

from app.retriever.documents_hybrid_search import _instrument_search

pytestmark = pytest.mark.unit


class _Span:
    def __init__(self) -> None:
        self.attrs: dict[str, Any] = {}

    def set_attribute(self, key: str, value: Any) -> None:
        self.attrs[key] = value


@contextmanager
def _fake_span(**kwargs):
    span = _Span()
    span.attrs.update(kwargs)
    yield span


@pytest.mark.asyncio
async def test_retriever_wrapper_records_one_span_and_metric(monkeypatch) -> None:
    calls: list[dict[str, Any]] = []

    monkeypatch.setattr(
        "app.retriever.documents_hybrid_search.ot.kb_search_span",
        lambda **kwargs: _fake_span(**kwargs),
    )
    monkeypatch.setattr(
        "app.retriever.documents_hybrid_search.ot_metrics.record_kb_search_duration",
        lambda duration_ms, **attrs: calls.append(
            {"duration_ms": duration_ms, **attrs}
        ),
    )

    class Retriever:
        @_instrument_search("hybrid")
        async def search(
            self,
            query_text: str,
            top_k: int,
            workspace_id: int,
        ) -> list[str]:
            del query_text, top_k, workspace_id
            return ["doc-1", "doc-2"]

    result = await Retriever().search("hello", 3, 42)

    assert result == ["doc-1", "doc-2"]
    assert len(calls) == 1
    assert calls[0]["workspace_id"] == 42
    assert calls[0]["surface"] == "documents"
