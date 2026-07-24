"""Pulling item structs out of captured item_list / search API responses."""

from __future__ import annotations

from app.proprietary.platforms.tiktok.extraction import items_from_response


def test_reads_item_list_shape():
    body = {"itemList": [{"id": "1"}, {"id": "2"}], "hasMore": True}
    assert items_from_response(body) == [{"id": "1"}, {"id": "2"}]


def test_reads_search_data_shape():
    body = {"data": [{"type": 1, "item": {"id": "9"}}, {"type": 4, "item": {}}]}
    assert items_from_response(body) == [{"id": "9"}, {}]


def test_skips_malformed_entries():
    body = {"data": [{"type": 1}, "junk", {"item": {"id": "7"}}]}
    assert items_from_response(body) == [{"id": "7"}]


def test_returns_empty_for_unrelated_json():
    assert items_from_response({"statusCode": 0}) == []
    assert items_from_response("nope") == []
