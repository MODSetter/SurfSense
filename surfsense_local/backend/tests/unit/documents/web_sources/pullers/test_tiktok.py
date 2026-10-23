from urllib.parse import urlsplit

import pytest

from modules.documents.web_sources.pullers.puller import Fit, Listed, Pulled, ToolCall
from modules.documents.web_sources.pullers.tiktok import PULLER

pytestmark = pytest.mark.unit

VIDEO = "https://www.tiktok.com/@seaschool/video/7301"


def video(**changed: object) -> dict:
    """A video as the TikTok plugin's `scrape` answers it."""
    return {
        "webVideoUrl": VIDEO,
        "text": "Two tides a day, explained in 30 seconds #tides #science",
        "createTimeISO": "2026-05-01T08:00:00Z",
        "authorMeta": {"name": "seaschool", "nickName": "Sea School"},
        "videoMeta": {"duration": 31},
        "playCount": 54000,
        "diggCount": 3100,
        "hashtags": [{"name": "tides"}, {"name": "science"}],
    } | changed


COMMENTS = [
    {
        "videoWebUrl": VIDEO,
        "text": "Never knew this",
        "uniqueId": "ana",
        "diggCount": 12,
    },
    {
        "videoWebUrl": VIDEO,
        "text": "Same",
        "uniqueId": "ben",
        "diggCount": 0,
        "repliesToId": "1",
    },
]


def test_a_video_is_one_source() -> None:
    """A video's own page, under its author."""
    assert PULLER.fit(urlsplit(VIDEO)) == Fit.ONE


@pytest.mark.parametrize(
    "url",
    ["https://www.tiktok.com/@seaschool", "https://www.tiktok.com/tag/tides"],
)
def test_a_profile_or_hashtag_is_many_videos(url: str) -> None:
    """Refused in the dialog rather than pulled as one source."""
    assert PULLER.fit(urlsplit(url)) == Fit.LIST


def test_a_short_link_the_plugin_cannot_follow_is_refused() -> None:
    """Following it would reach a host the user has not allowed."""
    assert PULLER.fit(urlsplit("https://vm.tiktok.com/ZM123/")) == Fit.SHORT_LINK


def test_the_video_comes_with_its_comments() -> None:
    """The comments are optional: a video with comments off is still a source."""
    assert PULLER.calls(VIDEO) == [
        ToolCall("scrape", {"urls": [VIDEO], "max_items": 1}),
        ToolCall(
            "comments",
            {"video_urls": [VIDEO], "comments_per_video": 100, "max_items": 100},
            optional=True,
        ),
    ]


def test_a_video_is_written_with_its_caption_and_comments() -> None:
    """TikTok gives no transcript: the caption is the text."""
    pulled = PULLER.written(VIDEO, {"scrape": [video()], "comments": COMMENTS})

    assert pulled == Pulled(
        "Two tides a day, explained in 30 seconds #tides #science",
        """# Two tides a day, explained in 30 seconds #tides #science

- **Author:** Sea School (@seaschool)
- **Posted:** 2026-05-01T08:00:00Z
- **Duration:** 31 s
- **Plays:** 54,000
- **Likes:** 3,100
- **Hashtags:** #tides, #science
- **Link:** https://www.tiktok.com/@seaschool/video/7301

## Caption

Two tides a day, explained in 30 seconds #tides #science

## Comments

- **@ana** (12 likes): Never knew this
- **@ben**, replying (0 likes): Same""",
    )


def test_a_video_without_a_caption_is_titled_by_its_author() -> None:
    """Never an empty title in the sources list."""
    pulled = PULLER.written(VIDEO, {"scrape": [video(text="")], "comments": []})

    assert pulled is not None
    assert pulled.title == "TikTok video by @seaschool"


def test_only_an_error_from_the_plugin_is_nothing_to_keep() -> None:
    """An error item is not a video."""
    error = {"url": VIDEO, "error": "Video not found", "errorCode": "not_found"}

    assert PULLER.written(VIDEO, {"scrape": [error], "comments": []}) is None


def test_a_profile_is_listed_as_its_videos_without_its_account() -> None:
    """The account item a profile starts with is not a video to add."""
    profile = "https://www.tiktok.com/@seaschool"
    account = {"name": "seaschool", "profileUrl": profile}

    assert PULLER.listing is not None
    assert PULLER.listing.call(profile, 20) == ToolCall(
        "scrape", {"urls": [profile], "results_per_page": 20, "max_items": 20}
    )
    assert PULLER.listing.items([account, video()]) == [
        Listed(
            VIDEO,
            "Two tides a day, explained in 30 seconds #tides #science",
            "@seaschool",
        )
    ]


def test_a_search_runs_on_tiktok_s_own_search_page() -> None:
    """TikTok's search is a link the plugin reads, the words in its query."""
    assert PULLER.search is not None
    assert PULLER.search("tides & moon", 20) == ToolCall(
        "scrape",
        {
            "urls": ["https://www.tiktok.com/search?q=tides+%26+moon"],
            "results_per_page": 20,
            "max_items": 20,
        },
    )
