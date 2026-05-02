"""Unit tests for ``KnowledgeTreeMiddleware`` rendering.

The empty-folder marker is critical UX: without it, the LLM cannot
distinguish a leaf folder containing one document from a leaf folder
that has no descendants at all, and ends up firing ``rmdir`` on
non-empty folders. These tests pin the rendering contract so that
contract cannot silently regress.
"""

from __future__ import annotations

from app.agents.new_chat.middleware.knowledge_tree import KnowledgeTreeMiddleware
from app.agents.new_chat.path_resolver import DOCUMENTS_ROOT


def _compute(folder_paths: list[str], doc_paths: list[str]) -> set[str]:
    return KnowledgeTreeMiddleware._compute_non_empty_folders(folder_paths, doc_paths)


class TestComputeNonEmptyFolders:
    def test_folder_with_direct_document_is_non_empty(self):
        folder_paths = [f"{DOCUMENTS_ROOT}/Travel/Boarding Pass"]
        doc_paths = [
            f"{DOCUMENTS_ROOT}/Travel/Boarding Pass/southwest.pdf.xml",
        ]
        non_empty = _compute(folder_paths, doc_paths)
        assert f"{DOCUMENTS_ROOT}/Travel/Boarding Pass" in non_empty

    def test_truly_empty_leaf_folder_is_not_non_empty(self):
        folder_paths = [f"{DOCUMENTS_ROOT}/Travel/Boarding Pass"]
        doc_paths: list[str] = []
        assert _compute(folder_paths, doc_paths) == set()

    def test_documents_propagate_up_to_all_ancestors(self):
        folder_paths = [
            f"{DOCUMENTS_ROOT}/A",
            f"{DOCUMENTS_ROOT}/A/B",
            f"{DOCUMENTS_ROOT}/A/B/C",
        ]
        doc_paths = [f"{DOCUMENTS_ROOT}/A/B/C/file.xml"]
        non_empty = _compute(folder_paths, doc_paths)
        assert non_empty == {
            f"{DOCUMENTS_ROOT}/A",
            f"{DOCUMENTS_ROOT}/A/B",
            f"{DOCUMENTS_ROOT}/A/B/C",
        }

    def test_chain_with_subfolders_marks_only_leaf_empty(self):
        # POSIX-like semantic: a folder is "empty" only if it has no
        # immediate children (docs OR sub-folders). The model needs this
        # because parallel ``rmdir`` calls all see the same starting state,
        # so trying to rmdir a parent before its children is never safe.
        folder_paths = [
            f"{DOCUMENTS_ROOT}/X",
            f"{DOCUMENTS_ROOT}/X/Y",
            f"{DOCUMENTS_ROOT}/X/Y/Z",
        ]
        non_empty = _compute(folder_paths, [])
        # Only ``X/Y/Z`` (the leaf) is empty. ``X`` and ``X/Y`` each have a
        # sub-folder child, so they are non-empty and should NOT carry the
        # ``(empty)`` marker.
        assert non_empty == {f"{DOCUMENTS_ROOT}/X", f"{DOCUMENTS_ROOT}/X/Y"}

    def test_sibling_with_doc_does_not_mark_other_sibling_non_empty(self):
        # Mirrors a real DB layout where every intermediate folder is
        # materialized in the ``folders`` table.
        folder_paths = [
            f"{DOCUMENTS_ROOT}/Travel",
            f"{DOCUMENTS_ROOT}/Travel/Boarding Pass",
            f"{DOCUMENTS_ROOT}/Travel/Notes",
        ]
        doc_paths = [f"{DOCUMENTS_ROOT}/Travel/Notes/itinerary.xml"]
        non_empty = _compute(folder_paths, doc_paths)
        # ``Travel`` is non-empty because it has children, ``Notes`` is non-empty
        # because of the doc, but ``Boarding Pass`` (sibling leaf) is empty.
        assert f"{DOCUMENTS_ROOT}/Travel" in non_empty
        assert f"{DOCUMENTS_ROOT}/Travel/Notes" in non_empty
        assert f"{DOCUMENTS_ROOT}/Travel/Boarding Pass" not in non_empty


class TestFormatTreeRendering:
    """Integration check: empty leaf gets ``(empty)`` marker; non-empty doesn't."""

    def _render(
        self,
        folder_paths: list[str],
        doc_specs: list[dict],
    ) -> str:
        from app.agents.new_chat.path_resolver import PathIndex

        index = PathIndex(
            folder_paths={i + 1: p for i, p in enumerate(folder_paths)},
        )

        class _Row:
            def __init__(self, **kw):
                self.__dict__.update(kw)

        docs = [_Row(**spec) for spec in doc_specs]

        mw = KnowledgeTreeMiddleware(
            search_space_id=1,
            filesystem_mode=None,  # type: ignore[arg-type]
        )
        return mw._format_tree(index, docs)

    def test_renders_empty_marker_only_for_truly_empty_folders(self):
        # Reproduces the failure scenario from the bug report:
        # ``Boarding Pass`` is empty (its only doc was just deleted), while
        # ``Tax Returns`` still has ``federal.pdf``. All intermediate
        # folders are present in the index, mirroring the real DB layout.
        folder_paths = [
            "/documents/File Upload",
            "/documents/File Upload/2026-04-08",
            "/documents/File Upload/2026-04-08/Travel",
            "/documents/File Upload/2026-04-08/Travel/Boarding Pass",
            "/documents/File Upload/2026-04-15",
            "/documents/File Upload/2026-04-15/Finance",
            "/documents/File Upload/2026-04-15/Finance/Tax Returns",
        ]
        tax_returns_folder_id = (
            folder_paths.index("/documents/File Upload/2026-04-15/Finance/Tax Returns")
            + 1
        )
        rendered = self._render(
            folder_paths=folder_paths,
            doc_specs=[
                {
                    "id": 100,
                    "title": "federal.pdf",
                    "folder_id": tax_returns_folder_id,
                },
            ],
        )
        assert "Boarding Pass/ (empty)" in rendered
        assert "Tax Returns/ (empty)" not in rendered
        # Intermediate ancestors of the doc must NOT be marked empty.
        assert "Finance/ (empty)" not in rendered
        assert "2026-04-15/ (empty)" not in rendered
