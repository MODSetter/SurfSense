"""Static guards for Zero authorization wiring."""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[3]
WEB_ROOT = REPO_ROOT / "surfsense_web"


def test_zero_query_route_uses_authoritative_backend_context() -> None:
    route = WEB_ROOT / "app/api/zero/query/route.ts"
    text = route.read_text()

    assert "/zero/context" in text
    assert "/users/me" not in text
    assert "userID: auth.ctx.userId" in text
    assert "handleQueryRequest({" in text
