from urllib.parse import urlsplit

import pytest

from modules.documents.web_sources.pullers.puller import Fit, Listed, Pulled, ToolCall
from modules.documents.web_sources.pullers.youtube import PULLER

pytestmark = pytest.mark.unit

VIDEO = "https://www.youtube.com/watch?v=tide1"
SRT = """1
00:00:00,000 --> 00:00:02,500
The moon pulls on the sea.

2
00:00:02,500 --> 00:00:05,000
The moon pulls on the sea.

3
00:00:05,000 --> 00:00:08,000
So the tide comes in twice a day.
"""


def video(**changed: object) -> dict:
    """A watch page as the YouTube plugin's `scrape` answers it."""
    return {
        "type": "video",
        "title": "Why tides happen",
        "url": VIDEO,
        "channelName": "Sea School",
        "date": "2026-03-02T10:00:00Z",
        "duration": "00:03:12",
        "viewCount": 120400,
        "likes": 4100,
        "text": "A short film about the moon and the sea.",
        "subtitles": [
            {
                "language": "en",
                "type": "auto_generated",
                "srt": "1\n00:00:00,000 --> 00:00:01,000\nwrong track\n",
            },
            {"language": "en", "type": "user_generated", "srt": SRT},
        ],
    } | changed


COMMENTS = [
    {
        "type": "comment",
        "author": "@ana",
        "comment": "Finally it makes sense.",
        "voteCount": 312,
    },
    {
        "type": "reply",
        "author": "@seaschool",
        "comment": "Glad it helped!",
        "voteCount": 4,
        "replyToCid": "c1",
    },
]


@pytest.mark.parametrize(
    "url",
    [VIDEO, "https://youtu.be/tide1", "https://m.youtube.com/shorts/tide1"],
)
def test_a_video_is_one_source(url: str) -> None:
    """A watch page, a short link, or a short."""
    assert PULLER.fit(urlsplit(url)) == Fit.ONE


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/@seaschool",
        "https://www.youtube.com/playlist?list=PL1",
        "https://www.youtube.com/results?search_query=tides",
    ],
)
def test_a_channel_playlist_or_search_is_many_videos(url: str) -> None:
    """Refused in the dialog rather than pulled as one source."""
    assert PULLER.fit(urlsplit(url)) == Fit.LIST


def test_another_site_is_not_youtube_s() -> None:
    """Left to the next puller, and to Web Crawl last."""
    assert PULLER.fit(urlsplit("https://vimeo.com/123")) is None


def test_the_video_comes_with_its_subtitles_and_its_top_comments() -> None:
    """The comments are optional: a video with comments off is still a source."""
    assert PULLER.calls(VIDEO) == [
        ToolCall(
            "scrape", {"urls": [VIDEO], "max_results": 1, "download_subtitles": True}
        ),
        ToolCall(
            "comments",
            {"urls": [VIDEO], "max_comments": 100, "sort_by": "TOP_COMMENTS"},
            optional=True,
        ),
    ]


def test_a_video_is_written_with_its_transcript_and_comments() -> None:
    """The person-written track wins; timings and repeated captions are dropped."""
    pulled = PULLER.written(VIDEO, {"scrape": [video()], "comments": COMMENTS})

    assert pulled == Pulled(
        "Why tides happen",
        """# Why tides happen

- **Channel:** Sea School
- **Published:** 2026-03-02T10:00:00Z
- **Duration:** 00:03:12
- **Views:** 120,400
- **Likes:** 4,100
- **Link:** https://www.youtube.com/watch?v=tide1

## Description

A short film about the moon and the sea.

## Transcript

The moon pulls on the sea.
So the tide comes in twice a day.

## Comments

- **@ana** (312 likes): Finally it makes sense.
- **@seaschool**, replying (4 likes): Glad it helped!""",
    )


def test_a_video_without_subtitles_or_comments_keeps_what_it_has() -> None:
    """An empty section is left out, not written as a heading alone."""
    pulled = PULLER.written(
        VIDEO, {"scrape": [video(subtitles=None, text=None)], "comments": []}
    )

    assert pulled is not None
    assert "## Transcript" not in pulled.markdown
    assert "## Comments" not in pulled.markdown
    assert "## Description" not in pulled.markdown


def test_a_video_the_plugin_did_not_find_is_nothing_to_keep() -> None:
    """Comments alone are not the video that was asked for."""
    assert PULLER.written(VIDEO, {"scrape": [], "comments": COMMENTS}) is None


def test_a_channel_is_listed_as_its_videos() -> None:
    """Each video becomes a row: its link, its title, its channel and length."""
    channel = "https://www.youtube.com/@seaschool"

    assert PULLER.listing is not None
    assert PULLER.listing.call(channel, 20) == ToolCall(
        "scrape", {"urls": [channel], "max_results": 20}
    )
    assert PULLER.listing.items([video()]) == [
        Listed(VIDEO, "Why tides happen", "Sea School · 00:03:12")
    ]


def test_a_search_runs_on_youtube_itself() -> None:
    """Only the query is sent: the plugin's defaults do the rest."""
    assert PULLER.search is not None
    assert PULLER.search("how tides work", 20) == ToolCall(
        "scrape", {"search_queries": ["how tides work"], "max_results": 20}
    )
