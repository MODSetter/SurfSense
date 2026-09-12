from __future__ import annotations

import pytest

from app.artifacts.verification.formats.registry import (
    get_format_adapter,
    validate_format_path,
)


@pytest.mark.parametrize(
    (
        "format_name",
        "name",
        "mime_type",
        "rendered_min_chars",
        "expects_exact_page_count",
        "review_kind",
    ),
    [
        ("pdf", "pdf", "application/pdf", 20, False, "document"),
        (
            "docx",
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            20,
            False,
            "document",
        ),
        (
            "pptx",
            "pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            0,
            True,
            "slides",
        ),
    ],
)
def test_format_adapters_own_rendering_policy(
    format_name,
    name,
    mime_type,
    rendered_min_chars,
    expects_exact_page_count,
    review_kind,
):
    adapter = get_format_adapter(format_name)

    assert adapter.name == name
    assert adapter.mime_type == mime_type
    assert adapter.rendered_min_chars == rendered_min_chars
    assert adapter.expects_exact_page_count is expects_exact_page_count
    assert adapter.review_kind == review_kind


def test_explicit_case_insensitive_format_selects_mindmap():
    adapter = get_format_adapter(" MINDMAP ")

    assert adapter.name == "mindmap"
    assert adapter.suffix == ".png"
    assert adapter.mime_type == "image/png"
    assert adapter.requires_markdown_binding
    assert not adapter.requires_visual_review

    with pytest.raises(ValueError, match="format image"):
        get_format_adapter("image")

    validate_format_path(adapter, "/workspace/strategy.png")
    with pytest.raises(ValueError, match=r"must use \.png"):
        validate_format_path(adapter, "/workspace/strategy.jpg")
