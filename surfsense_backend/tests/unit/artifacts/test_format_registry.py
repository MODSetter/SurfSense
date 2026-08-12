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
