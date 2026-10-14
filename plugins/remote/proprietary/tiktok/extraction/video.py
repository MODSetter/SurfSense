"""Normalize a raw TikTok ``itemStruct`` into a :class:`TikTokVideoItem` dict."""

from __future__ import annotations

from typing import Any

from ..schemas.items import TikTokVideoItem
from .author import build_author_meta
from .timestamps import epoch_to_iso

_VIDEO_URL = "https://www.tiktok.com/@{username}/video/{video_id}"


def _music_meta(music: dict[str, Any]) -> dict[str, Any]:
    return {
        "musicId": music.get("id"),
        "musicName": music.get("title"),
        "musicAuthor": music.get("authorName"),
        "musicOriginal": music.get("original"),
        "playUrl": music.get("playUrl"),
    }


def _video_meta(video: dict[str, Any]) -> dict[str, Any]:
    return {
        "height": video.get("height"),
        "width": video.get("width"),
        "duration": video.get("duration"),
        "coverUrl": video.get("cover"),
        "format": video.get("format"),
        "definition": video.get("definition"),
    }


def _hashtags(challenges: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"id": c.get("id"), "name": c.get("title")}
        for c in challenges
        if isinstance(c, dict)
    ]


def _mentions(text_extra: list[dict[str, Any]]) -> list[str]:
    # ``type`` 0 marks an @mention; hashtags (type 1) are covered by ``challenges``.
    return [
        t["userUniqueId"]
        for t in text_extra
        if isinstance(t, dict) and t.get("type") == 0 and t.get("userUniqueId")
    ]


def _slideshow_urls(image_post: dict[str, Any]) -> list[str]:
    urls = []
    for image in image_post.get("images") or []:
        url_list = ((image or {}).get("imageURL") or {}).get("urlList") or []
        if url_list:
            urls.append(url_list[0])
    return urls


def parse_video(item: dict[str, Any]) -> dict[str, Any]:
    """Map an ``itemStruct`` to the flat output contract, filling known fields."""
    author = item.get("author") or {}
    author_stats = item.get("authorStats") or {}
    stats = item.get("stats") or {}
    username = author.get("uniqueId")
    video_id = item.get("id")

    web_url = (
        _VIDEO_URL.format(username=username, video_id=video_id)
        if username and video_id
        else None
    )
    create_time = item.get("createTime")
    image_post = item.get("imagePost")

    return TikTokVideoItem(
        id=video_id,
        text=item.get("desc"),
        textLanguage=item.get("textLanguage"),
        createTime=create_time,
        createTimeISO=epoch_to_iso(create_time),
        isAd=item.get("isAd"),
        authorMeta=build_author_meta(author, author_stats),
        musicMeta=_music_meta(item.get("music") or {}),
        videoMeta=_video_meta(item.get("video") or {}),
        webVideoUrl=web_url,
        # Only slideshow images: a video's playAddr is a signed URL that expires.
        mediaUrls=_slideshow_urls(image_post) if isinstance(image_post, dict) else [],
        diggCount=stats.get("diggCount"),
        shareCount=stats.get("shareCount"),
        playCount=stats.get("playCount"),
        collectCount=stats.get("collectCount"),
        commentCount=stats.get("commentCount"),
        hashtags=_hashtags(item.get("challenges") or []),
        mentions=_mentions(item.get("textExtra") or []),
        isSlideshow="imagePost" in item,
        # Profile listings flag pinned posts; other feeds omit the key.
        isPinned=item.get("isPinnedItem"),
    ).to_output()
