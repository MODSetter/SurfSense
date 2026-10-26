from urllib.parse import urlsplit

import pytest

from modules.documents.web_sources.pullers.puller import Fit, Listed, Pulled, ToolCall
from modules.documents.web_sources.pullers.reddit import PULLER

pytestmark = pytest.mark.unit

POST = "https://www.reddit.com/r/oceanography/comments/1abc/why_two_tides_a_day/"


def post(**changed: object) -> dict:
    """A post as the Reddit plugin's `scrape` answers it."""
    return {
        "dataType": "post",
        "id": "t3_1abc",
        "url": POST,
        "title": "Why are there two tides a day?",
        "body": "The moon is on one side, so why two bulges?",
        "username": "seaschool",
        "communityName": "r/oceanography",
        "createdAt": "2026-05-01T08:00:00.000Z",
        "upVotes": 1520,
        "numberOfComments": 2,
        "flair": "Question",
        "link": None,
    } | changed


COMMENTS = [
    {
        "dataType": "comment",
        "username": "ana",
        "body": "Inertia on the far side.",
        "upVotes": 12,
        "parentId": "t3_1abc",
    },
    {
        "dataType": "comment",
        "username": "ben",
        "body": "This.",
        "upVotes": 0,
        "parentId": "t1_9xyz",
    },
]


def test_a_post_is_one_source() -> None:
    """A post's own page, with or without its slug, on any Reddit host."""
    assert PULLER.fit(urlsplit(POST)) == Fit.ONE
    assert (
        PULLER.fit(urlsplit("https://old.reddit.com/r/oceanography/comments/1abc"))
        == Fit.ONE
    )


@pytest.mark.parametrize(
    "url",
    [
        "https://www.reddit.com/r/oceanography/",
        "https://www.reddit.com/r/oceanography/top/",
        "https://www.reddit.com/user/seaschool/",
        "https://www.reddit.com/search/?q=tides",
        "https://www.reddit.com/r/oceanography/search/?q=tides",
    ],
)
def test_a_subreddit_user_or_search_is_many_posts(url: str) -> None:
    """Opened into its posts rather than pulled as one source."""
    assert PULLER.fit(urlsplit(url)) == Fit.LIST


@pytest.mark.parametrize(
    "url",
    ["https://redd.it/1abc", "https://www.reddit.com/r/oceanography/s/Xy12Ab"],
)
def test_a_share_link_the_plugin_cannot_follow_is_refused(url: str) -> None:
    """Both redirect; the plugin would read the share link as the subreddit itself."""
    assert PULLER.fit(urlsplit(url)) == Fit.SHORT_LINK


def test_a_reddit_page_the_plugin_does_not_read_is_left_to_the_web() -> None:
    """The plugin reads posts, subreddits, users and searches, nothing else."""
    assert PULLER.fit(urlsplit("https://www.reddit.com/settings")) is None
    assert PULLER.fit(urlsplit("https://example.com/r/x/comments/1")) is None


def test_the_post_comes_with_its_comments_in_one_call() -> None:
    """The post counts toward the plugin's 100 items, so 99 comments fit."""
    assert PULLER.calls(POST) == [
        ToolCall("scrape", {"urls": [POST], "max_comments": 99, "max_items": 100})
    ]


def test_a_post_is_written_with_its_text_and_comments() -> None:
    """A reply says so, as TikTok's do."""
    pulled = PULLER.written(POST, {"scrape": [post(), *COMMENTS]})

    assert pulled == Pulled(
        "Why are there two tides a day?",
        """# Why are there two tides a day?

- **Subreddit:** r/oceanography
- **Author:** u/seaschool
- **Posted:** 2026-05-01T08:00:00.000Z
- **Score:** 1,520
- **Comments:** 2
- **Flair:** Question
- **Link:** https://www.reddit.com/r/oceanography/comments/1abc/why_two_tides_a_day/

## Post

The moon is on one side, so why two bulges?

## Comments

- **u/ana** (12 points): Inertia on the far side.
- **u/ben**, replying (0 points): This.""",
    )


def test_a_link_post_names_the_page_it_shares() -> None:
    """A link post has no text of its own: the page it points to is the fact."""
    pulled = PULLER.written(
        POST, {"scrape": [post(body=None, link="https://tides.example/explained")]}
    )

    assert pulled is not None
    assert "- **Shares:** https://tides.example/explained" in pulled.markdown


def test_nothing_but_comments_is_nothing_to_keep() -> None:
    """A removed or NSFW post answers without the post itself."""
    assert PULLER.written(POST, {"scrape": COMMENTS}) is None


def test_a_subreddit_is_listed_as_its_posts_without_comments() -> None:
    """The community item it starts with is one more item, not a post to add."""
    subreddit = "https://www.reddit.com/r/oceanography/"
    community = {"dataType": "community", "url": subreddit, "title": "Oceanography"}

    assert PULLER.listing is not None
    assert PULLER.listing.call(subreddit, 20) == ToolCall(
        "scrape",
        {"urls": [subreddit], "skip_comments": True, "max_posts": 20, "max_items": 21},
    )
    assert PULLER.listing.items([community, post()]) == [
        Listed(POST, "Why are there two tides a day?", "r/oceanography · u/seaschool")
    ]


def test_a_list_never_asks_past_the_plugin_s_100_items() -> None:
    """The last page asks for 100 posts; the community item cannot push it to 101."""
    assert PULLER.listing is not None
    call = PULLER.listing.call("https://www.reddit.com/r/oceanography/", 100)

    assert call.arguments["max_items"] == 100


def test_a_user_is_listed_as_the_posts_they_submitted() -> None:
    """Their overview mixes in comments, which are not posts to add."""
    assert PULLER.listing is not None
    call = PULLER.listing.call("https://www.reddit.com/user/seaschool/comments/", 20)

    assert call.arguments["urls"] == ["https://www.reddit.com/user/seaschool/submitted"]


def test_a_search_runs_on_reddit_s_own_search() -> None:
    """Posts only, best matches first."""
    assert PULLER.search is not None
    assert PULLER.search("tides & moon", 20) == ToolCall(
        "scrape",
        {
            "search_queries": ["tides & moon"],
            "skip_comments": True,
            "max_posts": 20,
            "max_items": 20,
        },
    )
