"""HTTP failure translation: status hints, server detail, and body parsing."""

from __future__ import annotations

import httpx

from surfsense_mcp.core.client import SurfSenseClient

_REQUEST = httpx.Request("GET", "http://localhost:8000/api/v1/documents")


def _response(status: int, **kwargs) -> httpx.Response:
    return httpx.Response(status, request=_REQUEST, **kwargs)


def test_explains_401_with_token_hint():
    message = SurfSenseClient._explain_failure(_response(401, json={"detail": "bad"}))
    assert "API key" in message
    assert "bad" in message


def test_explains_403_as_access_or_api_disabled():
    message = SurfSenseClient._explain_failure(_response(403, json={"detail": "no"}))
    assert "API access" in message


def test_extracts_nested_detail_message():
    response = _response(402, json={"detail": {"message": "out of credits"}})
    assert "out of credits" in SurfSenseClient._explain_failure(response)


def test_unmapped_status_still_reports_detail():
    message = SurfSenseClient._explain_failure(_response(500, json={"detail": "boom"}))
    assert "500" in message and "boom" in message


def test_parses_json_body():
    assert SurfSenseClient._parse_body(_response(200, json={"ok": 1})) == {"ok": 1}


def test_empty_body_parses_to_none():
    assert SurfSenseClient._parse_body(_response(204, content=b"")) is None


def test_non_json_body_falls_back_to_text():
    assert SurfSenseClient._parse_body(_response(200, text="hello")) == "hello"
