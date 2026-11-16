from urllib.parse import urlsplit

import pytest

from modules.documents.web_sources.links import routed

pytestmark = pytest.mark.unit

VIDEO_ID = "dQw4w9WgXcQ"


@pytest.mark.parametrize(
    "url",
    [
        f"https://www.youtube.com/watch?v={VIDEO_ID}&t=42",
        f"https://youtu.be/{VIDEO_ID}?si=x",
        f"https://m.youtube.com/shorts/{VIDEO_ID}",
        f"https://www.youtube.com/embed/{VIDEO_ID}",
        f"https://www.youtube.com/live/{VIDEO_ID}?si=x",
    ],
)
def test_a_video_link_is_read_as_its_transcript_from_www_youtube_com(
    url: str,
) -> None:
    """A watch page, a short link, a short, an embed or a live stream's link: the
    video's id is all that is sent, so one host is asked about whatever the link's."""
    puller = routed(url)

    assert puller.id == "youtube"
    assert puller.hosts(url) == ["www.youtube.com"]


@pytest.mark.parametrize(
    "url",
    [
        "https://www.youtube.com/@seaschool",
        "https://www.youtube.com/playlist?list=PL1",
        "https://www.youtube.com/results?search_query=tides",
        "https://www.youtube.com/watch?v=short",
        "https://youtu.be/",
    ],
)
def test_a_youtube_link_naming_no_video_is_read_as_a_page(url: str) -> None:
    """A channel, a playlist, a search, or an id no video could have."""
    puller = routed(url)

    assert puller.id == "web_page"
    assert puller.hosts(url) == [urlsplit(url).hostname]


def test_any_other_link_is_read_from_its_own_host() -> None:
    """A page, on the site the user named."""
    assert routed("https://vimeo.com/123").hosts("https://vimeo.com/123") == [
        "vimeo.com"
    ]
