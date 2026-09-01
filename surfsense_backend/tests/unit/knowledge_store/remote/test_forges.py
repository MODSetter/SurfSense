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


def test_oauth_authorize_url_needs_client_id(monkeypatch):
    from app.config import config as app_config

    monkeypatch.setattr(app_config, "GITHUB_APP_CLIENT_ID", "")
    with pytest.raises(RemoteError) as exc:
        GithubProvider().oauth_authorize_url(state="s")
    assert exc.value.code == "forge"


def test_oauth_authorize_url_carries_client_redirect_and_state(monkeypatch):
    from app.config import config as app_config

    monkeypatch.setattr(app_config, "GITHUB_APP_CLIENT_ID", "Iv1.deadbeef")
    monkeypatch.setattr(app_config, "BACKEND_URL", "https://api.example.com")
    url = GithubProvider().oauth_authorize_url(state="a/b")
    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert "client_id=Iv1.deadbeef" in url
    # backend callback is the redirect target, url-encoded
    assert (
        "redirect_uri=https%3A%2F%2Fapi.example.com%2Fapi%2Fv1%2Fworkspaces%2F"
        "git-remotes%2Fgithub%2Foauth%2Fcallback" in url
    )
    assert "state=a%2Fb" in url


def test_folders_from_tree_keeps_dirs_sorted():
    payload = {
        "tree": [
            {"path": "src", "type": "tree"},
            {"path": "docs", "type": "tree"},
            {"path": "docs/intro.md", "type": "blob"},
            {"path": "docs/api", "type": "tree"},
            {"path": "README.md", "type": "blob"},
        ],
        "truncated": False,
    }
    assert GithubProvider._folders_from_tree(payload) == ["docs", "docs/api", "src"]


def test_repos_from_payload_carries_default_branch_and_drops_cloneless():
    payload = {
        "repositories": [
            {"full_name": "o/a", "clone_url": "https://github.com/o/a.git", "default_branch": "trunk"},
            {"full_name": "o/b", "clone_url": "https://github.com/o/b.git"},
            {"full_name": "o/c", "clone_url": ""},
        ]
    }
    assert GithubProvider._repos_from_payload(payload) == [
        {"full_name": "o/a", "url": "https://github.com/o/a.git", "default_branch": "trunk"},
        {"full_name": "o/b", "url": "https://github.com/o/b.git", "default_branch": "main"},
    ]


def test_branches_from_payload_keeps_names():
    payload = [{"name": "main"}, {"name": "dev"}, {"protected": True}]
    assert GithubProvider._branches_from_payload(payload) == ["main", "dev"]


def test_installations_from_payload_maps_id_and_account():
    payload = {
        "total_count": 2,
        "installations": [
            {"id": 111, "account": {"login": "acme"}},
            {"id": 222, "account": {"login": "me"}},
        ],
    }
    assert GithubProvider._installations_from_payload(payload) == [
        {"id": "111", "account": "acme"},
        {"id": "222", "account": "me"},
    ]


def test_token_from_oauth_payload_raises_on_error():
    with pytest.raises(RemoteError) as exc:
        GithubProvider._token_from_oauth_payload({"error": "bad_verification_code"})
    assert exc.value.code == "forge"
    assert (
        GithubProvider._token_from_oauth_payload({"access_token": "ghu_x"}) == "ghu_x"
    )
