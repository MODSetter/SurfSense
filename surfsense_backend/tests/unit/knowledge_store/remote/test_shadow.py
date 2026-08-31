"""Shadow clone writes only the md bijection. Real git, no fakes."""

from __future__ import annotations

import pytest

from app.knowledge_store.engines.git import GitContentEngine
from app.knowledge_store.identities import user_identity
from app.knowledge_store.remote.shadow import Shadow

pytestmark = pytest.mark.unit

AUTHOR = user_identity("1")


def test_pathspec_write_leaves_png_and_markdown_outside_the_prefix(tmp_path):
    dest = GitContentEngine(tmp_path / "dest", tmp_path / "dest-wc")
    dest.record(
        writes={
            "docs/intro.md": b"old",
            "docs/gone.md": b"not on local",
            "docs/logo.png": b"PNG",
            "README.md": b"foreign",
        },
        removes=[],
        message="seed",
        author=AUTHOR,
    )
    shadow = Shadow.clone(str(dest._path), tmp_path / "shadow")
    shadow.replace_md("docs", {"intro.md": b"new", "guide.md": b"added"})
    shadow.commit(message="sync", author=AUTHOR)

    assert shadow.read("docs/logo.png") == b"PNG"
    assert shadow.read("README.md") == b"foreign"
    assert shadow.list_md("docs") == {"intro.md": b"new", "guide.md": b"added"}


def test_push_lands_on_dest_without_deleting_png(tmp_path):
    dest = GitContentEngine(tmp_path / "dest", tmp_path / "dest-wc")
    dest.record(
        writes={
            "docs/intro.md": b"old",
            "docs/logo.png": b"PNG",
            "README.md": b"foreign",
        },
        removes=[],
        message="seed",
        author=AUTHOR,
    )
    shadow = Shadow.clone(str(dest._path), tmp_path / "shadow")
    shadow.replace_md("docs", {"intro.md": b"new"})
    sha = shadow.commit(message="sync", author=AUTHOR)
    assert sha is not None
    shadow.push(url=str(dest._path), ref=shadow.head_ref())
    assert dest.read_as_of(sha, "docs/logo.png") == b"PNG"
    assert dest.read_as_of(sha, "README.md") == b"foreign"
    assert dest.read_as_of(sha, "docs/intro.md") == b"new"


def test_clone_of_empty_dest_with_named_branch_is_empty(tmp_path):
    dest = GitContentEngine(tmp_path / "dest", tmp_path / "dest-wc")
    dest._ensure_exists()
    shadow = Shadow.clone(str(dest._path), tmp_path / "shadow", branch="main")
    assert shadow.list_md("docs") == {}
    assert shadow.head_sha() is None
