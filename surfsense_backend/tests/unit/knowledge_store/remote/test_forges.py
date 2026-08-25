"""Forge validate + credentials. No network."""

from __future__ import annotations

import pytest

from app.knowledge_store.remote.exceptions import RemoteError
from app.knowledge_store.remote.forges import provider_for
from app.knowledge_store.remote.forges.github import GithubProvider
from app.knowledge_store.remote.forges.gitlab import GitlabProvider
from app.knowledge_store.remote.schemas import GithubSpec, GitlabSpec

pytestmark = pytest.mark.unit


def test_unknown_provider_is_invalid():
    with pytest.raises(RemoteError) as exc:
        provider_for("gitea")
    assert exc.value.code == "invalid_spec"


def test_github_requires_installation_id_and_github_host():
    provider = GithubProvider()
    with pytest.raises(RemoteError) as exc:
        provider.validate(
            GithubSpec(
                provider="github",
                url="https://github.com/o/r.git",
                installation_id="",
            )
        )
    assert exc.value.code == "invalid_spec"
    with pytest.raises(RemoteError):
        provider.validate(
            GithubSpec(
                provider="github",
                url="https://gitlab.com/o/r.git",
                installation_id="1",
            )
        )
    provider.validate(
        GithubSpec(
            provider="github",
            url="https://github.com/o/r.git",
            installation_id="1",
        )
    )


def test_gitlab_requires_pat_and_gitlab_host():
    provider = GitlabProvider()
    with pytest.raises(RemoteError) as exc:
        provider.validate(
            GitlabSpec(
                provider="gitlab",
                url="https://gitlab.com/o/r.git",
                token="",
            )
        )
    assert exc.value.code == "invalid_spec"
    with pytest.raises(RemoteError):
        provider.validate(
            GitlabSpec(
                provider="gitlab",
                url="https://github.com/o/r.git",
                token="glpat-x",
            )
        )
    provider.validate(
        GitlabSpec(
            provider="gitlab",
            url="https://gitlab.com/o/r.git",
            token="glpat-x",
        )
    )


async def test_gitlab_credentials_use_oauth2_and_plaintext_pat():
    creds = await GitlabProvider().credentials(
        GitlabSpec(
            provider="gitlab",
            url="https://gitlab.com/o/r.git",
            token="glpat-x",
        )
    )
    assert creds.username == "oauth2"
    assert creds.password == "glpat-x"


def test_github_install_url_needs_slug(monkeypatch):
    from app.config import config as app_config

    monkeypatch.setattr(app_config, "GITHUB_APP_SLUG", "")
    with pytest.raises(RemoteError) as exc:
        GithubProvider().install_url(state="abc")
    assert exc.value.code == "forge"
    monkeypatch.setattr(app_config, "GITHUB_APP_SLUG", "surfsense")
    url = GithubProvider().install_url(state="a/b")
    assert url.startswith("https://github.com/apps/surfsense/installations/new?state=")
    assert "a/b" not in url
    assert "a%2Fb" in url
