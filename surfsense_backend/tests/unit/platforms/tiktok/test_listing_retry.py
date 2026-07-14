"""Retry-on-empty for the browser ``item_list`` seam (no browser, fake fetch).

``fetch_item_list`` re-fetches an empty capture up to ``TIKTOK_LISTING_MAX_ATTEMPTS``
so a flagged rotating exit IP on the first draw doesn't collapse straight to an
``ErrorItem``. These drive that loop deterministically by faking ``_fetch_sync``.
"""

from __future__ import annotations

from app.proprietary.platforms.tiktok.session import listing


class _Fake:
    """Returns each queued result once, repeating the last; counts calls."""

    def __init__(self, results: list[list[dict]]):
        self.results = results
        self.calls = 0

    def __call__(self, *args, **kwargs):
        out = self.results[min(self.calls, len(self.results) - 1)]
        self.calls += 1
        return out


def _patch(monkeypatch, fake: _Fake, attempts: int) -> None:
    monkeypatch.setattr(listing, "_fetch_sync", fake)
    monkeypatch.setattr(listing.config, "TIKTOK_LISTING_MAX_ATTEMPTS", attempts)


async def test_returns_first_nonempty_without_retrying(monkeypatch):
    fake = _Fake([[{"id": "1"}]])
    _patch(monkeypatch, fake, 3)
    items = await listing.fetch_item_list("https://tt/@x", 5)
    assert items == [{"id": "1"}]
    assert fake.calls == 1  # a draw with items never retries


async def test_retries_past_empty_draws_then_hits(monkeypatch):
    fake = _Fake([[], [], [{"id": "9"}]])
    _patch(monkeypatch, fake, 3)
    items = await listing.fetch_item_list("https://tt/@x", 5)
    assert items == [{"id": "9"}]
    assert fake.calls == 3  # two empty (flagged-IP) draws retried, third lands


async def test_stops_at_attempt_ceiling_when_always_empty(monkeypatch):
    fake = _Fake([[]])
    _patch(monkeypatch, fake, 3)
    items = await listing.fetch_item_list("https://tt/@x", 5)
    assert items == []
    assert fake.calls == 3  # capped; caller then emits the ErrorItem


async def test_single_attempt_config_disables_retry(monkeypatch):
    fake = _Fake([[]])
    _patch(monkeypatch, fake, 1)
    items = await listing.fetch_item_list("https://tt/@x", 5)
    assert items == []
    assert fake.calls == 1  # static-IP setups opt out via attempts=1
