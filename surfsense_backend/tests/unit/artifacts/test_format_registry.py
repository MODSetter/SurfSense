from __future__ import annotations

import pytest

from app.artifacts.verification.formats.registry import get_format_adapter


@pytest.mark.parametrize(
    ("path", "name", "mime_type"),
    [
        ("/workspace/report.pdf", "pdf", "application/pdf"),
        (
            "/workspace/report.docx",
            "docx",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        ),
    ],
)
def test_format_adapters_own_canonical_mime(path, name, mime_type):
    adapter = get_format_adapter(path)

    assert adapter.name == name
    assert adapter.mime_type == mime_type
