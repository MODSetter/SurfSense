"""Rehydration-blob extraction from TikTok page HTML (pure, no network)."""

from __future__ import annotations

from app.proprietary.platforms.tiktok.extraction import extract_rehydration_data

_BLOB = (
    '<html><body><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" '
    'type="application/json">'
    '{"__DEFAULT_SCOPE__":{"webapp.video-detail":{"itemInfo":{"itemStruct":'
    '{"id":"123"}}}}}'
    "</script></body></html>"
)


def test_extracts_default_scope_from_blob():
    data = extract_rehydration_data(_BLOB)
    assert data is not None
    item = data["__DEFAULT_SCOPE__"]["webapp.video-detail"]["itemInfo"]["itemStruct"]
    assert item["id"] == "123"


def test_returns_none_when_blob_absent():
    assert extract_rehydration_data("<html><body>no blob here</body></html>") is None


def test_returns_none_when_blob_json_malformed():
    broken = (
        '<script id="__UNIVERSAL_DATA_FOR_REHYDRATION__" '
        'type="application/json">{not json}</script>'
    )
    assert extract_rehydration_data(broken) is None
