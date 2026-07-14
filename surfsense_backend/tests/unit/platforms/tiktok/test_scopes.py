"""Navigating the rehydration blob to its useful scopes (pure, no network)."""

from __future__ import annotations

from app.proprietary.platforms.tiktok.extraction import user_info, video_item_struct


def test_video_item_struct_navigates_video_detail_scope():
    data = {
        "__DEFAULT_SCOPE__": {
            "webapp.video-detail": {"itemInfo": {"itemStruct": {"id": "123"}}}
        }
    }
    item = video_item_struct(data)
    assert item == {"id": "123"}


def test_user_info_navigates_user_detail_scope():
    data = {
        "__DEFAULT_SCOPE__": {
            "webapp.user-detail": {"userInfo": {"user": {"uniqueId": "scout2015"}}}
        }
    }
    info = user_info(data)
    assert info == {"user": {"uniqueId": "scout2015"}}


def test_scopes_return_none_when_absent():
    assert video_item_struct({}) is None
    assert user_info({"__DEFAULT_SCOPE__": {}}) is None
