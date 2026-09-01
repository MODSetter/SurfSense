"""Staged paths must stay inside {sourcepath} and be synced text documents."""

from __future__ import annotations

import pytest

from app.knowledge_store.remote.exceptions import RemoteError
from app.knowledge_store.remote.guards import check_staged

pytestmark = pytest.mark.unit


def test_text_documents_under_sourcepath_are_allowed():
    check_staged(
        sourcepath="docs",
        paths=("docs/intro.md", "docs/guides/a.rst", "docs/notes.txt"),
    )


def test_a_png_under_sourcepath_is_refused():
    with pytest.raises(RemoteError) as exc:
        check_staged(sourcepath="docs", paths=("docs/logo.png",))
    assert exc.value.code == "would_delete_foreign"


def test_a_file_outside_sourcepath_is_refused():
    with pytest.raises(RemoteError) as exc:
        check_staged(sourcepath="docs", paths=("src/app.ts",))
    assert exc.value.code == "would_delete_foreign"


def test_markdown_outside_sourcepath_is_refused():
    with pytest.raises(RemoteError) as exc:
        check_staged(sourcepath="docs", paths=("handbook/intro.md",))
    assert exc.value.code == "would_delete_foreign"


def test_empty_sourcepath_allows_markdown_at_repo_root():
    check_staged(sourcepath="", paths=("readme.md", "guides/a.md"))
