"""Strict Confluence indexer fake for Playwright E2E."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import patch

_FIXTURE_PATH = Path(__file__).parent / "fixtures" / "confluence_pages.json"


def _load_fixture() -> dict[str, Any]:
    with _FIXTURE_PATH.open() as f:
        return json.load(f)


_FIXTURE = _load_fixture()


class _FakeConfluenceHistoryConnector:
    def __init__(self, *, session: Any, connector_id: int, **kwargs: Any):
        del session, kwargs
        self.connector_id = connector_id

    async def get_pages_by_date_range(
        self,
        *,
        start_date: str,
        end_date: str,
        include_comments: bool = False,
    ) -> tuple[list[dict[str, Any]], None]:
        if not start_date or not end_date:
            raise ValueError(
                "Confluence indexer fake expected start_date and end_date."
            )
        del include_comments
        return _FIXTURE["pages"], None

    async def close(self) -> None:
        return None

    def __getattr__(self, name: str) -> Any:
        raise NotImplementedError(
            "E2E Confluence indexer fake missing surface: "
            f"ConfluenceHistoryConnector.{name!r}. "
            "Add it to surfsense_backend/tests/e2e/fakes/confluence_indexer.py."
        )


def install(active_patches: list[Any]) -> None:
    """Patch only the Confluence indexer's bound connector class."""
    p = patch(
        "app.tasks.connector_indexers.confluence_indexer.ConfluenceHistoryConnector",
        _FakeConfluenceHistoryConnector,
    )
    p.start()
    active_patches.append(p)
