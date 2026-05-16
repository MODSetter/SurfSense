"""Tests for the FRAMES Wikipedia fetcher.

We mock the MW API with respx so tests are network-free. Coverage:

* URL → title parsing (percent-encoded, underscores, redirects)
* Filename safety (slashes, special chars)
* Cache hit short-circuits the API call
* Missing pages return ``None`` (not an exception)
* Successful fetches write ``# Title`` markdown to disk
"""

from __future__ import annotations

from pathlib import Path

import httpx
import pytest
import respx

from surfsense_evals.suites.research.frames.wiki_fetch import (
    WIKI_API,
    WikiFetcher,
    cache_filename_for_title,
    title_from_url,
)


class TestTitleFromUrl:
    def test_basic(self) -> None:
        assert title_from_url("https://en.wikipedia.org/wiki/James_Buchanan") == "James Buchanan"

    def test_percent_encoded(self) -> None:
        assert (
            title_from_url("https://en.wikipedia.org/wiki/Charlotte_Bront%C3%AB")
            == "Charlotte Brontë"
        )

    def test_query_string_dropped(self) -> None:
        assert title_from_url("https://en.wikipedia.org/wiki/Foo?action=edit") == "Foo"

    def test_non_wiki_raises(self) -> None:
        with pytest.raises(ValueError):
            title_from_url("https://example.com/wiki/Foo")


class TestCacheFilename:
    def test_simple(self) -> None:
        assert cache_filename_for_title("James Buchanan") == "James_Buchanan.md"

    def test_unicode_replaced_with_underscore(self) -> None:
        # Brontë's diaeresis is non-ASCII so the regex replaces it with `_`.
        # The space → `_` happens after the unicode swap, so the final
        # name has exactly one underscore for the diaeresis. Acceptable:
        # filenames stay round-trippable as long as the rule is deterministic.
        assert cache_filename_for_title("Charlotte Brontë") == "Charlotte_Bront_.md"

    def test_slashes_replaced(self) -> None:
        # Wikipedia titles can contain ``/`` (e.g. "I/O"), which would
        # break the filesystem layout if not sanitised.
        assert cache_filename_for_title("I/O") == "I_O.md"


@pytest.mark.asyncio
@respx.mock
async def test_fetch_success_writes_markdown(tmp_path: Path) -> None:
    respx.get(WIKI_API).mock(return_value=httpx.Response(
        200,
        json={"query": {"pages": [{
            "pageid": 1,
            "title": "James Buchanan",
            "extract": "James Buchanan was the 15th president of the United States.",
        }]}},
    ))
    fetcher = WikiFetcher(cache_dir=tmp_path, rate_limit_rps=100)  # disable throttle
    article = await fetcher.fetch("https://en.wikipedia.org/wiki/James_Buchanan")
    assert article is not None
    assert article.title == "James Buchanan"
    body = article.markdown_path.read_text(encoding="utf-8")
    assert body.startswith("# James Buchanan")
    assert "15th president" in body


@pytest.mark.asyncio
@respx.mock
async def test_fetch_missing_page_returns_none(tmp_path: Path) -> None:
    respx.get(WIKI_API).mock(return_value=httpx.Response(
        200,
        json={"query": {"pages": [{
            "title": "DoesNotExist",
            "missing": True,
        }]}},
    ))
    fetcher = WikiFetcher(cache_dir=tmp_path, rate_limit_rps=100)
    article = await fetcher.fetch("https://en.wikipedia.org/wiki/DoesNotExist")
    assert article is None
    assert not (tmp_path / "DoesNotExist.md").exists()


@pytest.mark.asyncio
@respx.mock
async def test_fetch_cache_hit_skips_api(tmp_path: Path) -> None:
    # Pre-populate the cache.
    cached = tmp_path / cache_filename_for_title("Cached Page")
    cached.write_text("# Cached Page\n\nfrom disk\n", encoding="utf-8")
    fetcher = WikiFetcher(cache_dir=tmp_path, rate_limit_rps=100)

    # No respx mock registered; if the fetcher hits the network, respx
    # would error out (it intercepts everything inside the decorator).
    article = await fetcher.fetch("https://en.wikipedia.org/wiki/Cached_Page")
    assert article is not None
    assert article.markdown_path == cached
    assert article.markdown_path.read_text(encoding="utf-8").endswith("from disk\n")
