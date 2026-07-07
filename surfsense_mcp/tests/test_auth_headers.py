"""API key extraction from request headers: Bearer, fallback, and rejection."""

from __future__ import annotations

from starlette.datastructures import Headers

from surfsense_mcp.core.auth.headers import extract_api_key


def _headers(**pairs: str) -> Headers:
    return Headers(pairs)


def test_reads_bearer_token():
    assert extract_api_key(_headers(authorization="Bearer ss_pat_abc")) == "ss_pat_abc"


def test_bearer_scheme_is_case_insensitive():
    assert extract_api_key(_headers(authorization="bearer ss_pat_abc")) == "ss_pat_abc"


def test_falls_back_to_x_api_key():
    assert extract_api_key(Headers({"x-api-key": "ss_pat_xyz"})) == "ss_pat_xyz"


def test_bearer_wins_over_fallback():
    headers = Headers({"authorization": "Bearer primary", "x-api-key": "secondary"})
    assert extract_api_key(headers) == "primary"


def test_missing_headers_return_none():
    assert extract_api_key(_headers()) is None


def test_empty_bearer_is_rejected():
    assert extract_api_key(_headers(authorization="Bearer   ")) is None


def test_non_bearer_authorization_is_ignored():
    assert extract_api_key(_headers(authorization="Basic abc123")) is None
