"""Parser fixes checked against trimmed live captures in ``fixtures/``.

The captures were taken on 2026-10-14 and trimmed to the nodes the parsers
read; continuation tokens are replaced by ``TOKEN-n`` stand-ins and tracking
fields are dropped. No network.
"""

import json
from pathlib import Path

from proprietary.youtube.parsers import (
    comment_next_token,
    comment_reply_tokens,
    comment_section_token,
    extract_yt_initial_data,
    find_all,
    find_first,
    parse_channel_sort_tokens,
    parse_channel_videos,
    parse_comment_entities,
    parse_comment_entity,
    parse_search_response,
    parse_translation,
    parse_video_page,
)

_FIXTURES = Path(__file__).parent / "fixtures"


def load(name: str) -> dict:
    return json.loads((_FIXTURES / name).read_text(encoding="utf-8"))


def watch_html(player: dict, initial: dict) -> str:
    return (
        "<script>var ytInitialPlayerResponse = "
        + json.dumps(player)
        + ";</script><script>var ytInitialData = "
        + json.dumps(initial)
        + ";</script>"
    )


def test_search_items_keep_the_whole_snippet_and_title() -> None:
    """Bold query words split the snippet into runs; all of them are the text."""
    items, _ = parse_search_response(load("search_sourdough.json"))

    assert items[1]["text"].startswith(
        "Learn how to bake sourdough bread with the perfect rise, ear, and texture"
    )
    assert items[0]["title"] == "How To Bake Sourdough Like A Pro"


def test_search_view_counts_are_exact() -> None:
    items, _ = parse_search_response(load("search_sourdough.json"))

    # viewCountText "3,666,349 views", not shortViewCountText "3.6M views".
    assert [item["viewCount"] for item in items] == [3_666_349, 3_371_533, 16_389_309]


def test_search_durations_match_watch_page_durations() -> None:
    items, _ = parse_search_response(load("search_sourdough.json"))

    assert [item["duration"] for item in items] == ["00:17:42", "00:11:53", "00:16:09"]


def test_search_items_say_whether_the_channel_is_verified() -> None:
    items, _ = parse_search_response(load("search_sourdough.json"))

    assert [item["isChannelVerified"] for item in items] == [True, True, None]


def test_watch_page_likes_are_exact() -> None:
    capture = load("watch_kCc8FmEb1nY.json")

    result = parse_video_page(watch_html(capture["player"], capture["initial"]))

    # The button reads "170K"; its a11y text says "along with 170,857 other people".
    assert result["likes"] == 170_857


def test_watch_page_keywords_are_not_hashtags() -> None:
    capture = load("watch_kCc8FmEb1nY.json")

    result = parse_video_page(watch_html(capture["player"], capture["initial"]))

    assert result["hashtags"] == []  # the description has no #tags
    assert result["keywords"][:3] == [
        "deep learning",
        "neural network",
        "language model",
    ]
    assert result["isChannelVerified"] is None  # the owner has no badge
    assert result["commentsCount"] == 3_300  # rounded at the source


def test_watch_page_hashtags_come_from_description_and_super_title() -> None:
    player = {
        "videoDetails": {
            "videoId": "abc",
            "shortDescription": (
                "Bake #bread at home &#39;n see https://x.com/a/#frag #Bread2 #bread"
            ),
            "keywords": ["bread"],
        }
    }
    initial = {
        "videoPrimaryInfoRenderer": {
            "superTitleLink": {"runs": [{"text": "#shorts"}, {"text": " "}]}
        }
    }

    result = parse_video_page(watch_html(player, initial))

    assert result["hashtags"] == ["#bread", "#Bread2", "#shorts"]
    assert result["keywords"] == ["bread"]


def test_an_official_artist_channel_is_verified() -> None:
    player = {"videoDetails": {"videoId": "abc"}}
    initial = {
        "videoSecondaryInfoRenderer": {
            "owner": {
                "videoOwnerRenderer": {
                    "badges": [
                        {
                            "metadataBadgeRenderer": {
                                "style": "BADGE_STYLE_TYPE_VERIFIED_ARTIST",
                                "tooltip": "Official Artist Channel",
                            }
                        }
                    ]
                }
            }
        },
        # Another channel's badge elsewhere on the page must not count.
        "sidebar": {"metadataBadgeRenderer": {"tooltip": "Verified"}},
    }

    assert parse_video_page(watch_html(player, initial))["isChannelVerified"] is True


def test_another_channel_s_badge_does_not_verify_the_uploader() -> None:
    player = {"videoDetails": {"videoId": "abc"}}
    initial = {"sidebar": {"metadataBadgeRenderer": {"tooltip": "Verified"}}}

    assert parse_video_page(watch_html(player, initial))["isChannelVerified"] is None


def test_the_channel_seed_page_is_the_latest_chip_page() -> None:
    """The default sort skips the Latest chip request on this assumption."""
    seed, _ = parse_channel_videos(load("channel_mkbhd_seed.json"))
    latest, _ = parse_channel_videos(load("channel_mkbhd_latest_chip.json"))

    assert [item["id"] for item in seed] == [item["id"] for item in latest]
    # The seed page prints "10h ago" where the chip page prints "10 hours ago".
    assert [item["publishedTimeText"] for item in seed] == [
        item["publishedTimeText"] for item in latest
    ]
    assert set(parse_channel_sort_tokens(load("channel_mkbhd_seed.json"))) == {
        "Latest",
        "Popular",
        "Oldest",
    }


def test_channel_lockup_durations_are_hh_mm_ss() -> None:
    seed, _ = parse_channel_videos(load("channel_mkbhd_seed.json"))

    assert seed[0]["duration"] == "00:11:47"


def test_compact_stream_times_are_spelled_out() -> None:
    lockup = {
        "contentId": "abcdefghijk",
        "metadata": {
            "lockupMetadataViewModel": {
                "metadata": {
                    "contentMetadataViewModel": {
                        "metadataRows": [
                            {
                                "metadataParts": [
                                    {"text": {"content": "1.2K views"}},
                                    {"text": {"content": "Streamed 1y ago"}},
                                ]
                            }
                        ]
                    }
                }
            }
        },
    }
    items, _ = parse_channel_videos(
        {"richItemRenderer": {"content": {"lockupViewModel": lockup}}}
    )

    assert items[0]["publishedTimeText"] == "Streamed 1 year ago"


def test_a_live_badge_is_not_a_duration() -> None:
    lockup = {
        "contentId": "abcdefghijk",
        "contentImage": {
            "thumbnailViewModel": {
                "overlays": [
                    {
                        "thumbnailBottomOverlayViewModel": {
                            "badges": [{"thumbnailBadgeViewModel": {"text": "LIVE"}}]
                        }
                    }
                ]
            }
        },
    }
    items, _ = parse_channel_videos(
        {"richItemRenderer": {"content": {"lockupViewModel": lockup}}}
    )

    assert items[0]["duration"] is None


def test_next_by_video_id_seeds_the_comments() -> None:
    data = load("next_video_jNQXAC9IVRw.json")

    assert comment_section_token(data) == "TOKEN-1"
    assert parse_translation(data)[0] == "Me at the zoo"


def test_reply_pages_continue_behind_the_show_more_button() -> None:
    page = load("replies_page_jNQXAC9IVRw.json")

    replies = parse_comment_entities(page)

    assert len(replies) == 10
    assert {reply["type"] for reply in replies} == {"reply"}
    assert comment_next_token(page) == "TOKEN-7"


def test_comment_pages_still_page_on_their_own_token() -> None:
    page = load("comments_page_jNQXAC9IVRw.json")

    assert comment_next_token(page) == "TOKEN-6"
    assert len(comment_reply_tokens(page)) == 3


def test_captured_repliers_are_stand_ins() -> None:
    # Unverified repliers are private people: their handles, channel ids and
    # avatars are replaced. The verified top-level commenters are public.
    replies = parse_comment_entities(load("replies_page_jNQXAC9IVRw.json"))

    assert {r["author"] for r in replies} == {f"@commenter-{n}" for n in range(1, 11)}


def test_zero_counts_are_zero_when_the_toolbar_is_there() -> None:
    replies = parse_comment_entities(load("replies_page_jNQXAC9IVRw.json"))
    blank = parse_comment_entity(
        {"properties": {"commentId": "c"}, "toolbar": {"likeCountNotliked": " "}}
    )
    unknown = parse_comment_entity({"properties": {"commentId": "c"}})

    assert {reply["replyCount"] for reply in replies} == {0}
    assert (blank["voteCount"], blank["replyCount"]) == (0, 0)
    assert (unknown["voteCount"], unknown["replyCount"]) == (None, None)


def test_find_first_stops_at_the_same_hit_find_all_lists_first() -> None:
    initial = load("watch_kCc8FmEb1nY.json")["initial"]
    keys = [
        "contextualInfo",
        "canonicalBaseUrl",
        "subscriberCountText",
        "videoSecondaryInfoRenderer",
        "buttonViewModel",
        "continuationCommand",
        "no-such-key",
    ]

    for key in keys:
        everything = find_all(initial, key)
        assert find_first(initial, key) == (everything[0] if everything else None)


def test_the_embedded_object_ends_where_its_json_ends() -> None:
    page = load("watch_kCc8FmEb1nY.json")
    html = watch_html(page["player"], page["initial"]) + "<script>var x = {1: 2};"

    assert extract_yt_initial_data(html) == page["initial"]


def test_a_truncated_object_is_no_object() -> None:
    page = load("watch_kCc8FmEb1nY.json")
    html = watch_html(page["player"], page["initial"])

    assert extract_yt_initial_data(html[: -len(";</script>") - 5]) is None
