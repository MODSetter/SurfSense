"""Offline unit tests for the YouTube scraper parsers.

No network. Uses small hand-built raw ``ytInitialData`` / ``ytInitialPlayerResponse``
shapes (mirroring real nesting) plus direct normalization cases — the smallest
things that fail if the dict-walk or normalization logic breaks. If the e2e
script has captured real fixtures into ``fixtures/``, they are exercised too.
"""

import base64
import json
from pathlib import Path

import pytest

from app.proprietary.scrapers.youtube.parsers import (
    channel_about_tokens,
    comment_next_token,
    comment_reply_tokens,
    comment_section_token,
    comment_sort_tokens,
    dig,
    find_all,
    parse_channel_about,
    parse_channel_metadata,
    parse_channel_shorts,
    parse_collaborators,
    parse_comment_entities,
    parse_count,
    parse_date,
    parse_description_links,
    parse_location,
    parse_playlist_video_ids,
    parse_search_response,
    parse_translation,
    parse_video_page,
    seconds_to_duration,
)
from app.proprietary.scrapers.youtube.schemas import YouTubeScrapeInput
from app.proprietary.scrapers.youtube.search_filters import build_search_params
from app.proprietary.scrapers.youtube.url_resolver import resolve_url

pytestmark = pytest.mark.unit

_FIXTURE_DIR = Path(__file__).parent / "fixtures"


# --- normalization -----------------------------------------------------------


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("451K views", 451_000),
        ("1.2M", 1_200_000),
        ("1,234", 1_234),
        ("100", 100),
        ("2.5B", 2_500_000_000),
        (500, 500),
        ("No views", None),
        ("", None),
        (None, None),
    ],
)
def test_parse_count(raw, expected):
    assert parse_count(raw) == expected


def test_parse_date_prefers_publish_date():
    mf = {"publishDate": "2024-08-27", "uploadDate": "2024-08-20"}
    assert parse_date(mf) == "2024-08-27"
    assert parse_date({"uploadDate": "2024-08-20"}) == "2024-08-20"
    assert parse_date(None) is None


def test_seconds_to_duration():
    assert seconds_to_duration("207") == "00:03:27"
    assert seconds_to_duration(3661) == "01:01:01"
    assert seconds_to_duration(None) is None


# --- traversal helpers -------------------------------------------------------


def test_find_all_and_dig():
    data = {"a": {"b": [{"k": 1}, {"k": 2}]}, "k": 3}
    assert find_all(data, "k") == [1, 2, 3]
    assert dig(data, "a", "b", 0, "k") == 1
    assert dig(data, "a", "b", 5, "k") is None
    assert dig(data, "missing", "x") is None


# --- page parsing ------------------------------------------------------------


def _video_html() -> str:
    player = {
        "videoDetails": {
            "videoId": "abc123",
            "title": "Test Title",
            "lengthSeconds": "207",
            "viewCount": "100",
            "author": "TechReviewer",
            "channelId": "UC123",
            "shortDescription": "desc",
            "keywords": ["#tech"],
            "thumbnail": {
                "thumbnails": [
                    {
                        "url": "https://i.ytimg.com/vi/abc123/hq.jpg",
                        "width": 480,
                        "height": 360,
                    }
                ]
            },
        },
        "microformat": {
            "playerMicroformatRenderer": {
                "publishDate": "2024-08-27",
                "isFamilySafe": True,
            }
        },
        "adPlacements": [{"adPlacementRenderer": {}}],
    }
    initial = {
        "like": {"buttonViewModel": {"iconName": "LIKE", "title": "15K"}},
        "comments": {
            "itemSectionRenderer": {
                "sectionIdentifier": "comment-item-section",
                "contents": [{"continuationItemRenderer": {"trigger": "x"}}],
            }
        },
        "ctx": {"contextualInfo": {"runs": [{"text": "1,250"}]}},
        "chan": {"canonicalBaseUrl": "/@Apify"},
        "subs": {"subscriberCountText": {"simpleText": "500K subscribers"}},
        "badge": {"metadataBadgeRenderer": {"tooltip": "Verified"}},
    }
    return (
        "<html><script>var ytInitialPlayerResponse = "
        + json.dumps(player)
        + ";</script><script>var ytInitialData = "
        + json.dumps(initial)
        + ";</script></html>"
    )


def test_parse_video_page():
    result = parse_video_page(_video_html())
    assert result is not None
    assert result["id"] == "abc123"
    assert result["url"] == "https://www.youtube.com/watch?v=abc123"
    assert result["title"] == "Test Title"
    assert result["viewCount"] == 100
    assert result["duration"] == "00:03:27"
    assert result["date"] == "2024-08-27"
    assert result["thumbnailUrl"] == "https://i.ytimg.com/vi/abc123/hq.jpg"
    assert result["hashtags"] == ["#tech"]
    assert result["channelName"] == "TechReviewer"
    assert result["channelId"] == "UC123"
    assert result["likes"] == 15_000
    assert result["commentsCount"] == 1_250
    assert result["channelUrl"] == "https://www.youtube.com/@Apify"
    assert result["channelUsername"] == "Apify"
    assert result["numberOfSubscribers"] == 500_000
    assert result["isChannelVerified"] is True
    assert result["isMonetized"] is True  # adPlacements present
    assert result["isAgeRestricted"] is None  # family safe, no age gate
    assert result["commentsTurnedOff"] is False  # section has a continuation


def test_parse_video_page_comments_turned_off():
    player = {"videoDetails": {"videoId": "x", "title": "t"}}
    initial = {
        "itemSectionRenderer": {
            "sectionIdentifier": "comment-item-section",
            "contents": [{"messageRenderer": {"text": {"simpleText": "off"}}}],
        }
    }
    html = (
        "<script>var ytInitialPlayerResponse = "
        + json.dumps(player)
        + ";</script><script>var ytInitialData = "
        + json.dumps(initial)
        + ";</script>"
    )
    result = parse_video_page(html)
    assert result is not None
    assert result["commentsTurnedOff"] is True
    assert result["commentsCount"] is None


def test_parse_video_page_age_restricted():
    player = {
        "videoDetails": {"videoId": "x", "title": "t"},
        "playabilityStatus": {
            "status": "LOGIN_REQUIRED",
            "desktopLegacyAgeGateReason": 1,
        },
    }
    html = "<script>var ytInitialPlayerResponse = " + json.dumps(player) + ";</script>"
    result = parse_video_page(html)
    assert result is not None
    assert result["isAgeRestricted"] is True
    assert result["isMonetized"] is None  # no ad slots → can't confirm


def test_parse_video_page_members_only_and_paid():
    player = {
        "videoDetails": {"videoId": "m", "title": "t"},
        "playabilityStatus": {"errorScreen": {"x": {"offerId": "sponsors_only_video"}}},
        "paidContentOverlay": {
            "paidContentOverlayRenderer": {"text": "Includes paid promotion"}
        },
    }
    initial = {
        "badges": [
            {
                "metadataBadgeRenderer": {
                    "style": "BADGE_STYLE_TYPE_MEMBERS_ONLY",
                    "label": "Members only",
                }
            }
        ]
    }
    html = (
        "<script>var ytInitialPlayerResponse = "
        + json.dumps(player)
        + ";</script><script>var ytInitialData = "
        + json.dumps(initial)
        + ";</script>"
    )
    result = parse_video_page(html)
    assert result is not None
    assert result["isMembersOnly"] is True
    assert result["isPaidContent"] is True


def test_parse_video_page_returns_none_without_player():
    assert parse_video_page("<html>no data here</html>") is None


def test_parse_channel_metadata():
    initial = {
        "metadata": {
            "channelMetadataRenderer": {
                "title": "Apify",
                "externalId": "UCabc123",
                "description": "We scrape the web.",
                "vanityChannelUrl": "https://www.youtube.com/@Apify",
                "avatar": {
                    "thumbnails": [
                        {"url": "https://a/avatar.jpg", "width": 88, "height": 88}
                    ]
                },
            }
        },
        "header": {
            "pageHeaderViewModel": {
                "banner": {
                    "imageBannerViewModel": {
                        "image": {
                            "sources": [
                                {
                                    "url": "https://a/banner.jpg",
                                    "width": 1060,
                                    "height": 175,
                                }
                            ]
                        }
                    }
                }
            }
        },
    }
    meta = parse_channel_metadata(initial)
    assert meta["channelName"] == "Apify"
    assert meta["channelId"] == "UCabc123"
    assert meta["channelDescription"] == "We scrape the web."
    assert meta["channelUrl"] == "https://www.youtube.com/@Apify"
    assert meta["channelAvatarUrl"] == "https://a/avatar.jpg"
    assert meta["channelBannerUrl"] == "https://a/banner.jpg"
    assert parse_channel_metadata({}) == {}


def test_parse_channel_about():
    about = {
        "description": "Official channel.",
        "country": "United States",
        "subscriberCountText": "45.6M subscribers",
        "viewCountText": "1,132,903,744 views",
        "videoCountText": "1,471 videos",
        "joinedDateText": {"content": "Joined Feb 8, 2005"},
    }
    out = parse_channel_about(about)
    assert out["channelDescription"] == "Official channel."
    assert out["channelLocation"] == "United States"
    assert out["numberOfSubscribers"] == 45_600_000
    assert out["channelTotalViews"] == 1_132_903_744
    assert out["channelTotalVideos"] == 1_471
    assert out["channelJoinedDate"] == "Feb 8, 2005"


def test_parse_description_links():
    initial = {
        "attributedDescription": {
            "content": "See #tag and my site here",
            "commandRuns": [
                {
                    "startIndex": 4,
                    "length": 4,
                    "onTap": {
                        "innertubeCommand": {"urlEndpoint": {"url": "/hashtag/tag"}}
                    },
                },
                {
                    "startIndex": 21,
                    "length": 4,
                    "onTap": {
                        "innertubeCommand": {
                            "commandMetadata": {
                                "webCommandMetadata": {
                                    "url": "https://www.youtube.com/redirect?q=https%3A%2F%2Fexample.com%2Fp&v=x"
                                }
                            }
                        }
                    },
                },
            ],
        }
    }
    links = parse_description_links(initial)
    assert links == [
        {"url": "https://www.youtube.com/hashtag/tag", "text": "#tag"},
        {"url": "https://example.com/p", "text": "here"},
    ]
    assert parse_description_links({}) is None


def test_channel_about_tokens():
    initial = {
        "a": {
            "showEngagementPanelEndpoint": {
                "x": {"continuationCommand": {"token": "T1"}}
            }
        },
        "b": {
            "showEngagementPanelEndpoint": {
                "y": {"continuationCommand": {"token": "T2"}}
            }
        },
    }
    assert channel_about_tokens(initial) == ["T1", "T2"]
    assert channel_about_tokens({}) == []


def test_parse_search_response():
    data = {
        "contents": [
            {
                "videoRenderer": {
                    "videoId": "mx3g7XoPVNQ",
                    "title": {"runs": [{"text": "A bad day"}]},
                    "detailedMetadataSnippets": [
                        {"snippetText": {"runs": [{"text": "become an engineer"}]}}
                    ],
                    "publishedTimeText": {"simpleText": "7 days ago"},
                    "lengthText": {"simpleText": "8:39"},
                    "shortViewCountText": {"simpleText": "451K views"},
                    "thumbnail": {
                        "thumbnails": [
                            {
                                "url": "https://i.ytimg.com/vi/x/hq.jpg",
                                "width": 360,
                                "height": 202,
                            }
                        ]
                    },
                    "ownerText": {
                        "runs": [
                            {
                                "text": "Life of Boris",
                                "navigationEndpoint": {
                                    "browseEndpoint": {
                                        "browseId": "UCS5tt2z_DFvG7-39J3aE-bQ",
                                        "canonicalBaseUrl": "/@LifeofBoris",
                                    }
                                },
                            }
                        ]
                    },
                }
            }
        ],
        "continuationCommand": {"token": "TOKEN123"},
    }
    items, token = parse_search_response(data)
    assert token == "TOKEN123"
    assert len(items) == 1
    item = items[0]
    assert item["id"] == "mx3g7XoPVNQ"
    assert item["title"] == "A bad day"
    assert item["viewCount"] == 451_000
    assert item["duration"] == "8:39"
    assert item["publishedTimeText"] == "7 days ago"
    assert item["date"] is None  # list pages have no real date
    assert item["channelName"] == "Life of Boris"
    assert item["channelId"] == "UCS5tt2z_DFvG7-39J3aE-bQ"
    assert item["channelUrl"] == "https://www.youtube.com/@LifeofBoris"
    assert item["channelUsername"] == "LifeofBoris"


def test_parse_channel_shorts():
    data = {
        "richItemRenderer": {
            "content": {
                "shortsLockupViewModel": {
                    "entityId": "shorts-shelf-item-0UfLo9SOUeE",
                    "onTap": {
                        "innertubeCommand": {
                            "reelWatchEndpoint": {"videoId": "0UfLo9SOUeE"}
                        }
                    },
                    "overlayMetadata": {
                        "primaryText": {"content": "is the west coast the best?"},
                        "secondaryText": {"content": "812 views"},
                    },
                    "thumbnailViewModel": {
                        "image": {
                            "sources": [
                                {
                                    "url": "https://i.ytimg.com/s.jpg",
                                    "width": 405,
                                    "height": 720,
                                }
                            ]
                        }
                    },
                }
            }
        },
        "continuationCommand": {"token": "SHORTSTOKEN"},
    }
    items, token = parse_channel_shorts(data)
    assert token == "SHORTSTOKEN"
    assert len(items) == 1
    it = items[0]
    assert it["id"] == "0UfLo9SOUeE"
    assert it["url"] == "https://www.youtube.com/shorts/0UfLo9SOUeE"
    assert it["title"] == "is the west coast the best?"
    assert it["viewCount"] == 812
    assert it["thumbnailUrl"] == "https://i.ytimg.com/s.jpg"


def test_parse_playlist_video_ids():
    # Playlists now return lockupViewModel with contentId (not playlistVideoRenderer).
    # Guards against the exact renderer-migration that silently broke the flow:
    # keep videos (11-char ids) in order, dedup, and drop non-video lockups.
    data = {
        "contents": {
            "items": [
                {
                    "lockupViewModel": {
                        "contentId": "fNk_zzaMoSs",
                        "contentType": "VIDEO",
                    }
                },
                {
                    "lockupViewModel": {
                        "contentId": "k7RM-ot2NWY",
                        "contentType": "VIDEO",
                    }
                },
                {
                    "lockupViewModel": {
                        "contentId": "fNk_zzaMoSs",
                        "contentType": "VIDEO",
                    }
                },  # dup
            ]
        },
        # a playlist self-lockup (non-video, longer id) that must be ignored
        "sidebar": {
            "lockupViewModel": {"contentId": "PLZHQObOWTQDPD3MizzM2xVFitgF8hE_ab"}
        },
        "continuationItemRenderer": {
            "continuationEndpoint": {"continuationCommand": {"token": "PAGE2"}}
        },
    }
    ids, token = parse_playlist_video_ids(data)
    assert ids == ["fNk_zzaMoSs", "k7RM-ot2NWY"]
    assert token == "PAGE2"


# --- search filter (sp=) encoder --------------------------------------------


@pytest.mark.parametrize(
    "kwargs,expected",
    [
        ({}, None),
        ({"sortingOrder": "relevance"}, None),  # default sort → no bytes
        ({"sortingOrder": "rating"}, "CAE="),
        ({"sortingOrder": "date"}, "CAI="),
        ({"sortingOrder": "views"}, "CAM="),
        ({"videoType": "video"}, "EgIQAQ=="),
        ({"videoType": "movie"}, "EgIQBA=="),
        ({"dateFilter": "hour"}, "EgIIAQ=="),
        ({"dateFilter": "year"}, "EgIIBQ=="),
        ({"lengthFilter": "under4"}, "EgIYAQ=="),
        ({"lengthFilter": "between420"}, "EgIYAw=="),
        ({"lengthFilter": "plus20"}, "EgIYAg=="),
    ],
)
def test_build_search_params_matches_youtube_tokens(kwargs, expected):
    assert build_search_params(YouTubeScrapeInput(**kwargs)) == expected


def test_build_search_params_combines_filters():
    # sort=date + upload=week + type=video + HD + subtitles, all in one token.
    token = build_search_params(
        YouTubeScrapeInput(
            sortingOrder="date",
            dateFilter="week",
            videoType="video",
            isHD=True,
            hasSubtitles=True,
        )
    )
    raw = base64.b64decode(token)
    # top-level: field1 (sort=2), field2 (Filters submessage)
    assert raw[:2] == b"\x08\x02"  # sort = date
    assert b"\x12" in raw  # Filters message tag present
    # Filters payload contains upload_date=week(3), type=video(1), hd, subtitles
    assert b"\x08\x03" in raw  # uploadDate = week
    assert b"\x10\x01" in raw  # type = video
    assert b"\x20\x01" in raw  # feature 4 (HD) = 1
    assert b"\x28\x01" in raw  # feature 5 (subtitles) = 1


# --- location & collaborators ------------------------------------------------


def _primary_info(super_title_link):
    return {
        "contents": {
            "twoColumnWatchNextResults": {
                "results": {
                    "results": {
                        "contents": [
                            {
                                "videoPrimaryInfoRenderer": {
                                    "superTitleLink": super_title_link
                                }
                            }
                        ]
                    }
                }
            }
        }
    }


def test_parse_location_from_geo_tag_label():
    initial = _primary_info(
        {
            "runs": [{"text": "ROME"}],
            "accessibility": {
                "accessibilityData": {
                    "label": "Link to a location restricted search for videos geo tagged with Rome"
                }
            },
        }
    )
    assert parse_location(initial) == "Rome"


def test_parse_location_hashtag_supertitle_is_none():
    # Same slot, but hashtags carry no geo-tag a11y label.
    initial = _primary_info({"runs": [{"text": "#music"}, {"text": "#video"}]})
    assert parse_location(initial) is None


def test_parse_location_absent_is_none():
    assert parse_location({}) is None


def _owner(video_owner_renderer):
    return {
        "contents": {
            "twoColumnWatchNextResults": {
                "results": {
                    "results": {
                        "contents": [
                            {
                                "videoSecondaryInfoRenderer": {
                                    "owner": {
                                        "videoOwnerRenderer": video_owner_renderer
                                    }
                                }
                            }
                        ]
                    }
                }
            }
        }
    }


def _collab_row(name, base_url):
    return {
        "listItemViewModel": {
            "title": {
                "content": name,
                "commandRuns": [
                    {
                        "onTap": {
                            "innertubeCommand": {
                                "browseEndpoint": {
                                    "browseId": "UCx",
                                    "canonicalBaseUrl": base_url,
                                }
                            }
                        }
                    }
                ],
            },
            # A nested subscribe submenu — must NOT be picked up as a collaborator.
            "subscribeMenu": {
                "listItemViewModel": {"title": {"content": "Unsubscribe"}}
            },
        }
    }


def test_parse_collaborators_from_dialog():
    initial = _owner(
        {
            "attributedTitle": {
                "content": "Alice and Bob",
                "commandRuns": [
                    {
                        "onTap": {
                            "innertubeCommand": {
                                "showDialogCommand": {
                                    "panelLoadingStrategy": {
                                        "inlineContent": {
                                            "dialogViewModel": {
                                                "header": {
                                                    "dialogHeaderViewModel": {
                                                        "headline": {
                                                            "content": "Collaborators"
                                                        }
                                                    }
                                                },
                                                "customContent": {
                                                    "listViewModel": {
                                                        "listItems": [
                                                            _collab_row(
                                                                "Alice", "/@alice"
                                                            ),
                                                            _collab_row(
                                                                "Bob",
                                                                "/channel/UCbob123",
                                                            ),
                                                        ]
                                                    }
                                                },
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                ],
            }
        }
    )
    collaborators = parse_collaborators(initial)
    assert collaborators == [
        {"name": "Alice", "username": "alice", "url": "https://www.youtube.com/@alice"},
        {
            "name": "Bob",
            "username": None,
            "url": "https://www.youtube.com/channel/UCbob123",
        },
    ]


def test_parse_collaborators_single_owner_is_none():
    # Ordinary videos use title.runs, not attributedTitle.
    initial = _owner({"title": {"runs": [{"text": "Some Channel"}]}})
    assert parse_collaborators(initial) is None


def test_parse_translation_from_next():
    next_data = {
        "contents": {
            "twoColumnWatchNextResults": {
                "results": {
                    "results": {
                        "contents": [
                            {
                                "videoPrimaryInfoRenderer": {
                                    "title": {
                                        "runs": [
                                            {"text": "Título "},
                                            {"text": "traducido"},
                                        ]
                                    }
                                }
                            },
                            {
                                "videoSecondaryInfoRenderer": {
                                    "attributedDescription": {
                                        "content": "Descripción traducida"
                                    }
                                }
                            },
                        ]
                    }
                }
            }
        }
    }
    title, description = parse_translation(next_data)
    assert title == "Título traducido"
    assert description == "Descripción traducida"


def test_parse_translation_description_runs_fallback():
    next_data = {
        "videoSecondaryInfoRenderer": {
            "description": {"runs": [{"text": "old "}, {"text": "style"}]}
        }
    }
    title, description = parse_translation(next_data)
    assert title is None
    assert description == "old style"


# --- comments ----------------------------------------------------------------


def _comment_cep(cid, *, level=0, hearted=False, owner=False, replies="5"):
    """Mirror a real commentEntityPayload's relevant fields."""
    toolbar = {"likeCountNotliked": "1.2K", "replyCount": replies}
    if hearted:
        toolbar["creatorThumbnailUrl"] = "https://yt3.ggpht.com/heart"
    return {
        "properties": {
            "commentId": cid,
            "content": {"content": f"text {cid}"},
            "publishedTime": "2 days ago",
            "replyLevel": level,
        },
        "author": {"displayName": f"@user{cid}", "isCreator": owner},
        "toolbar": toolbar,
    }


def _next_comments_response():
    """A /next comments response: sort menu, two threads, a page token."""

    def _reply_loader(token):
        return {
            "continuationItemRenderer": {
                "continuationEndpoint": {"continuationCommand": {"token": token}}
            }
        }

    def _thread(cid, reply_token):
        return {
            "commentThreadRenderer": {
                "commentViewModel": {"commentViewModel": {"commentId": cid}},
                "replies": {
                    "commentRepliesRenderer": {"contents": [_reply_loader(reply_token)]}
                },
            }
        }

    return {
        "frameworkUpdates": {
            "entityBatchUpdate": {
                "mutations": [
                    {
                        "payload": {
                            "commentEntityPayload": _comment_cep(
                                "C1", hearted=True, owner=True
                            )
                        }
                    },
                    {"payload": {"commentEntityPayload": _comment_cep("C2")}},
                ]
            }
        },
        "onResponseReceivedEndpoints": [
            {
                "reloadContinuationItemsCommand": {
                    "continuationItems": [
                        _thread("C1", "REPLYTOK1"),
                        _thread("C2", "REPLYTOK2"),
                        {
                            "continuationItemRenderer": {
                                "continuationEndpoint": {
                                    "continuationCommand": {"token": "PAGE2"}
                                }
                            }
                        },
                    ]
                }
            }
        ],
        "header": {
            "sortFilterSubMenuRenderer": {
                "subMenuItems": [
                    {
                        "title": "Top",
                        "serviceEndpoint": {"continuationCommand": {"token": "TOPTOK"}},
                    },
                    {
                        "title": "Newest",
                        "serviceEndpoint": {"continuationCommand": {"token": "NEWTOK"}},
                    },
                ]
            }
        },
    }


def test_parse_comment_entities():
    data = _next_comments_response()
    comments = parse_comment_entities(data)
    assert len(comments) == 2
    first = comments[0]
    assert first["cid"] == "C1"
    assert first["comment"] == "text C1"
    assert first["author"] == "@userC1"
    assert first["voteCount"] == 1200  # "1.2K"
    assert first["replyCount"] == 5
    assert first["type"] == "comment"
    assert first["hasCreatorHeart"] is True
    assert first["authorIsChannelOwner"] is True
    # second is a plain, non-hearted comment
    assert comments[1]["hasCreatorHeart"] is False
    assert comments[1]["authorIsChannelOwner"] is False


def test_comment_entity_reply_level_and_empty_reply_count():
    reply = parse_comment_entities(
        {
            "frameworkUpdates": {
                "entityBatchUpdate": {
                    "mutations": [
                        {
                            "payload": {
                                "commentEntityPayload": _comment_cep(
                                    "R1", level=1, replies=""
                                )
                            }
                        }
                    ]
                }
            }
        }
    )[0]
    assert reply["type"] == "reply"
    assert reply["replyCount"] is None  # empty string -> None


def test_comment_sort_tokens():
    tokens = comment_sort_tokens(_next_comments_response())
    assert tokens == {"Top": "TOPTOK", "Newest": "NEWTOK"}


def test_comment_reply_tokens():
    tokens = comment_reply_tokens(_next_comments_response())
    assert tokens == {"C1": "REPLYTOK1", "C2": "REPLYTOK2"}


def test_comment_next_token_is_trailing_bare_continuation():
    # The page token is the last top-level continuationItemRenderer, not a
    # reply loader nested inside a thread.
    assert comment_next_token(_next_comments_response()) == "PAGE2"


def test_comment_section_token_from_watch_page():
    initial = {
        "contents": {
            "twoColumnWatchNextResults": {
                "results": {
                    "results": {
                        "contents": [
                            {
                                "itemSectionRenderer": {
                                    "sectionIdentifier": "comment-item-section",
                                    "contents": [
                                        {
                                            "continuationItemRenderer": {
                                                "continuationEndpoint": {
                                                    "continuationCommand": {
                                                        "token": "SECTIONTOK"
                                                    }
                                                }
                                            }
                                        }
                                    ],
                                }
                            }
                        ]
                    }
                }
            }
        }
    }
    assert comment_section_token(initial) == "SECTIONTOK"


# --- url resolution ----------------------------------------------------------


@pytest.mark.parametrize(
    "url,kind,value",
    [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "video", "dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ", "video", "dQw4w9WgXcQ"),
        ("https://www.youtube.com/shorts/abc123", "video", "abc123"),
        ("https://www.youtube.com/@Apify", "channel", "Apify"),
        (
            "https://www.youtube.com/channel/UC123456789abc/videos",
            "channel",
            "UC123456789abc",
        ),
        ("https://www.youtube.com/playlist?list=PL123", "playlist", "PL123"),
        (
            "https://www.youtube.com/results?search_query=web+scraping",
            "search",
            "web scraping",
        ),
        ("https://www.youtube.com/hashtag/tech", "hashtag", "tech"),
    ],
)
def test_resolve_url(url, kind, value):
    resolved = resolve_url(url)
    assert resolved is not None
    assert resolved.kind == kind
    assert resolved.value == value


def test_resolve_url_unrecognized():
    assert resolve_url("https://example.com/foo") is None


# --- optional: exercise captured real fixtures if present --------------------


def test_parse_captured_video_fixture_if_present():
    player_path = _FIXTURE_DIR / "video_player_response.json"
    initial_path = _FIXTURE_DIR / "video_initial_data.json"
    if not player_path.exists():
        pytest.skip("no captured fixture (run scripts/e2e_youtube_scraper.py first)")
    html = (
        "<script>var ytInitialPlayerResponse = "
        + player_path.read_text(encoding="utf-8")
        + ";</script>"
    )
    if initial_path.exists():
        html += (
            "<script>var ytInitialData = "
            + initial_path.read_text(encoding="utf-8")
            + ";</script>"
        )
    result = parse_video_page(html)
    assert result is not None
    assert result["id"]
    assert result["title"]
