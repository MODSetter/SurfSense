from __future__ import annotations

import pytest

from app.artifacts.verification.formats.registry import get_format_adapter


@pytest.mark.parametrize(
    (
        "path",
        "name",
        "mime_type",
        "rendered_min_chars",
        "expects_exact_page_count",
        "review_kind",
    ),
    [
        ("/workspace/report.pdf", "pdf", "application/pdf", 20, False, "document"),
        (
            "/workspace/report.docx",
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            20,
            False,
            "document",
        ),
        (
            "/workspace/report.pptx",
            "pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            0,
            True,
            "slides",
        ),
    ],
)
def test_format_adapters_own_rendering_policy(
    path,
    name,
    mime_type,
    rendered_min_chars,
    expects_exact_page_count,
    review_kind,
):
    adapter = get_format_adapter(path)

    assert adapter.name == name
    assert adapter.mime_type == mime_type
    assert adapter.rendered_min_chars == rendered_min_chars
    assert adapter.expects_exact_page_count is expects_exact_page_count
    assert adapter.review_kind == review_kind


def test_longest_case_insensitive_suffix_selects_mindmap_only():
    adapter = get_format_adapter("/workspace/Strategy.MINDMAP.PNG")

    assert adapter.name == "mindmap"
    assert adapter.suffix == ".mindmap.png"
    assert adapter.mime_type == "image/png"
    assert adapter.requires_markdown_binding
    assert not adapter.requires_visual_review

    with pytest.raises(ValueError, match=r"\.png"):
        get_format_adapter("/workspace/unrelated.png")
