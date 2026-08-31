"""Where a connected repo lands under /documents."""

from __future__ import annotations

import pytest

from app.knowledge_store.remote.exceptions import RemoteError
from app.knowledge_store.remote.paths import full_name_from_url, mount, to_local, to_remote

pytestmark = pytest.mark.unit


def test_github_docs_folder_lands_under_reserved_github_root():
    assert (
        mount(provider="github", full_name="acme/app", sourcepath="docs")
        == "documents/GitHub/acme/app/docs"
    )


def test_empty_sourcepath_omits_the_extra_segment():
    assert (
        mount(provider="github", full_name="acme/app", sourcepath="")
        == "documents/GitHub/acme/app"
    )


def test_gitlab_nested_group_stays_in_the_path():
    assert (
        mount(provider="gitlab", full_name="acme/team/app", sourcepath="handbook")
        == "documents/GitLab/acme/team/app/handbook"
    )


def test_parent_segments_are_rejected():
    with pytest.raises(RemoteError) as exc:
        mount(provider="github", full_name="acme/../x", sourcepath="docs")
    assert exc.value.code == "unsafe_path"
    with pytest.raises(RemoteError) as exc:
        mount(provider="github", full_name="acme/app", sourcepath="../docs")
    assert exc.value.code == "unsafe_path"


def test_rel_maps_between_mount_and_sourcepath():
    prefix = mount(provider="github", full_name="acme/app", sourcepath="docs")
    assert to_local(mount=prefix, rel="a.md") == "documents/GitHub/acme/app/docs/a.md"
    assert to_remote(sourcepath="docs", rel="a.md") == "docs/a.md"


def test_github_url_yields_owner_and_repo():
    assert full_name_from_url("https://github.com/acme/app.git") == "acme/app"


def test_empty_sourcepath_maps_rel_to_repo_root():
    prefix = mount(provider="github", full_name="acme/app", sourcepath="")
    assert to_local(mount=prefix, rel="readme.md") == "documents/GitHub/acme/app/readme.md"
    assert to_remote(sourcepath="", rel="readme.md") == "readme.md"


def test_rel_parent_segments_are_rejected():
    with pytest.raises(RemoteError) as exc:
        to_local(mount="documents/GitHub/acme/app/docs", rel="../secret.md")
    assert exc.value.code == "unsafe_path"


def test_non_markdown_rel_is_rejected():
    with pytest.raises(RemoteError) as exc:
        to_remote(sourcepath="docs", rel="logo.png")
    assert exc.value.code == "unsafe_path"
