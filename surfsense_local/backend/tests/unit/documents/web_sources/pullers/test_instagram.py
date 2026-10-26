from urllib.parse import urlsplit

import pytest

from modules.documents.web_sources.pullers.instagram import PULLER
from modules.documents.web_sources.pullers.puller import Fit, Listed, Pulled, ToolCall

pytestmark = pytest.mark.unit

POST = "https://www.instagram.com/p/DAbc123/"
PROFILE = "https://www.instagram.com/seaschool/"


def media(**changed: object) -> dict:
    """A post as the Instagram plugin's `scrape` answers it."""
    return {
        "type": "Image",
        "url": POST,
        "caption": "Spring tide at dawn\nShot on the north beach #tides",
        "ownerUsername": "seaschool",
        "ownerFullName": "Sea School",
        "timestamp": "2026-05-01T08:00:00.000Z",
        "likesCount": 3100,
        "commentsCount": 42,
        "hashtags": ["tides"],
        "locationName": "North Beach",
        "alt": "Waves over a wide sandy beach at sunrise.",
    } | changed


@pytest.mark.parametrize(
    "url",
    [
        POST,
        "https://instagram.com/reel/DXyz789/",
        "https://www.instagram.com/reels/DXyz789/",
    ],
)
def test_a_post_or_reel_is_one_source(url: str) -> None:
    """Each has a page of its own."""
    assert PULLER.fit(urlsplit(url)) == Fit.ONE


def test_a_profile_is_many_posts() -> None:
    """Opened into its posts rather than pulled as one source."""
    assert PULLER.fit(urlsplit(PROFILE)) == Fit.LIST


@pytest.mark.parametrize(
    "url",
    ["https://instagr.am/p/DAbc123/", "https://www.instagram.com/share/BAbc123/"],
)
def test_a_share_link_the_plugin_cannot_follow_is_refused(url: str) -> None:
    """Both redirect, and the plugin follows no redirect."""
    assert PULLER.fit(urlsplit(url)) == Fit.SHORT_LINK


@pytest.mark.parametrize(
    "url",
    [
        "https://www.instagram.com/explore/tags/tides/",
        "https://www.instagram.com/",
        "https://example.com/p/DAbc123/",
    ],
)
def test_a_page_the_plugin_does_not_read_is_left_to_the_web(url: str) -> None:
    """Hashtags and places are behind Instagram's login."""
    assert PULLER.fit(urlsplit(url)) is None


def test_a_post_is_read_from_its_own_page() -> None:
    """Comments are behind the login, so there is no second call."""
    assert PULLER.calls(POST) == [ToolCall("scrape", {"urls": [POST], "max_items": 1})]


def test_a_post_is_written_with_its_caption_and_image_description() -> None:
    """The caption's first line is the title."""
    pulled = PULLER.written(POST, {"scrape": [media()]})

    assert pulled == Pulled(
        "Spring tide at dawn",
        """# Spring tide at dawn

- **Author:** Sea School (@seaschool)
- **Posted:** 2026-05-01T08:00:00.000Z
- **Likes:** 3,100
- **Comments:** 42
- **Hashtags:** #tides
- **Location:** North Beach
- **Link:** https://www.instagram.com/p/DAbc123/

## Caption

Spring tide at dawn
Shot on the north beach #tides

## Image description

Waves over a wide sandy beach at sunrise.""",
    )


def test_a_reel_counts_its_plays() -> None:
    """Only a reel's page gives a play count."""
    pulled = PULLER.written(
        POST, {"scrape": [media(type="Video", videoPlayCount=54000, alt=None)]}
    )

    assert pulled is not None
    assert "- **Plays:** 54,000" in pulled.markdown


def test_a_post_without_a_caption_is_titled_by_its_author() -> None:
    """Never an empty title in the sources list."""
    pulled = PULLER.written(POST, {"scrape": [media(caption=None)]})

    assert pulled is not None
    assert pulled.title == "Instagram post by @seaschool"


def test_only_an_error_from_the_plugin_is_nothing_to_keep() -> None:
    """An error item is not a post."""
    error = {"inputUrl": POST, "error": "not_found", "errorDescription": "Gone"}

    assert PULLER.written(POST, {"scrape": [error]}) is None


def test_a_profile_is_listed_as_its_posts() -> None:
    """A logged-out visitor sees its latest 12, so a page past them finds none."""
    assert PULLER.listing is not None
    assert PULLER.listing.call(PROFILE, 20) == ToolCall(
        "scrape", {"urls": [PROFILE], "max_per_target": 20, "max_items": 20}
    )
    assert PULLER.listing.items([media()]) == [
        Listed(POST, "Spring tide at dawn", "@seaschool")
    ]


def test_a_profiles_reels_tab_is_listed_as_its_reels() -> None:
    """The plugin reads the tab as its profile, so the feed is asked for by name."""
    reels = "https://www.instagram.com/seaschool/reels/"
    assert PULLER.listing is not None
    assert PULLER.listing.call(reels, 20) == ToolCall(
        "scrape",
        {
            "urls": [reels],
            "result_type": "reels",
            "max_per_target": 20,
            "max_items": 20,
        },
    )


def test_a_search_finds_profiles_to_open() -> None:
    """Instagram's own search is behind the login; the plugin finds profiles by Google."""
    profile = {
        "detailKind": "profile",
        "url": PROFILE,
        "username": "seaschool",
        "fullName": "Sea School",
        "followersCount": 12000,
    }

    assert PULLER.search is not None
    assert PULLER.search("tides", 20) == ToolCall(
        "details", {"search_queries": ["tides"], "search_limit": 20, "max_items": 20}
    )
    assert PULLER.listing is not None
    assert PULLER.listing.items([profile]) == [
        Listed(PROFILE, "Sea School", "@seaschool · 12,000 followers")
    ]
