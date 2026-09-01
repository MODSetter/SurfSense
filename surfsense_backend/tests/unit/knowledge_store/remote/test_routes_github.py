"""OAuth callback routing: sole install auto-picks, many offer a choice."""

from __future__ import annotations

import pytest

from app.config import config as app_config
from app.knowledge_store.remote.api.routes import _github_callback_target

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def _frontend(monkeypatch):
    monkeypatch.setattr(app_config, "NEXT_FRONTEND_URL", "https://app.example.com")


def test_no_installation_sends_an_error():
    url = _github_callback_target(7, [])
    assert url.endswith("/dashboard/7/workspace-settings/git-remote?github_error=no_installation")


def test_single_installation_is_auto_picked():
    url = _github_callback_target(7, [{"id": "111", "account": "me"}])
    assert url.endswith("?github_installation_id=111")


def test_many_installations_offer_a_choice():
    url = _github_callback_target(
        7,
        [{"id": "111", "account": "acme"}, {"id": "222", "account": "me"}],
    )
    assert "github_installations=111%3Aacme%2C222%3Ame" in url
