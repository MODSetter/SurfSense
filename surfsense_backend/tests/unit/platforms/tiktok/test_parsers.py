"""Raw TikTok payload -> normalized item mapping (pure, no network)."""

from __future__ import annotations

from app.proprietary.platforms.tiktok.extraction import parse_author, parse_video

_ITEM_STRUCT = {
    "id": "7534061113365859586",
    "desc": "haha #comeramabanana",
    "createTime": 1_700_000_000,
    "author": {
        "id": "6733",
        "uniqueId": "bruniela_",
        "nickname": "Bruni",
        "verified": False,
        "signature": "bio here",
        "avatarLarger": "https://cdn/avatar.jpg",
    },
    "authorStats": {
        "followerCount": 51200,
        "followingCount": 269,
        "heartCount": 3_000_000,
        "videoCount": 259,
    },
    "stats": {
        "diggCount": 5344,
        "shareCount": 701,
        "playCount": 55700,
        "commentCount": 24,
        "collectCount": 291,
    },
    "music": {
        "id": "7529",
        "title": "som original",
        "authorName": "fox_rus0",
        "original": True,
        "playUrl": "https://cdn/music.mp3",
    },
    "video": {
        "height": 1024,
        "width": 576,
        "duration": 16,
        "cover": "https://cdn/cover.jpg",
        "format": "mp4",
        "definition": "540p",
    },
    "challenges": [{"id": "4982299", "title": "comeramabanana"}],
}


def test_parse_video_maps_core_and_derived_fields():
    item = parse_video(_ITEM_STRUCT)

    assert item["id"] == "7534061113365859586"
    assert item["text"] == "haha #comeramabanana"
    assert item["createTimeISO"] == "2023-11-14T22:13:20.000Z"

    assert item["authorMeta"]["name"] == "bruniela_"
    assert item["authorMeta"]["nickName"] == "Bruni"
    assert item["authorMeta"]["profileUrl"] == "https://www.tiktok.com/@bruniela_"
    assert item["authorMeta"]["fans"] == 51200

    assert item["musicMeta"]["musicName"] == "som original"
    assert item["videoMeta"]["duration"] == 16

    assert item["diggCount"] == 5344
    assert item["playCount"] == 55700

    assert item["hashtags"] == [{"id": "4982299", "name": "comeramabanana"}]
    assert (
        item["webVideoUrl"]
        == "https://www.tiktok.com/@bruniela_/video/7534061113365859586"
    )


_USER_INFO = {
    "user": {
        "id": "6733",
        "uniqueId": "bruniela_",
        "nickname": "Bruni",
        "verified": True,
        "signature": "bio here",
        "avatarLarger": "https://cdn/avatar.jpg",
        "privateAccount": False,
    },
    "stats": {
        "followerCount": 51200,
        "followingCount": 269,
        "heartCount": 3_000_000,
        "videoCount": 259,
    },
}


def test_parse_author_maps_user_and_stats():
    author = parse_author(_USER_INFO)
    assert author["name"] == "bruniela_"
    assert author["nickName"] == "Bruni"
    assert author["verified"] is True
    assert author["profileUrl"] == "https://www.tiktok.com/@bruniela_"
    assert author["fans"] == 51200
    assert author["video"] == 259
