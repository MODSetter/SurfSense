from __future__ import annotations

import io

import pytest
from PIL import Image, ImageDraw

from app.artifacts.verification.formats.mindmap import (
    MINDMAP_HEIGHT,
    MINDMAP_MAX_LABEL_CHARS,
    MINDMAP_MAX_NODES,
    MINDMAP_WIDTH,
    check_mindmap_markdown,
    check_mindmap_png,
)


def _png(*, mode: str = "RGB", size=(MINDMAP_WIDTH, MINDMAP_HEIGHT)) -> bytes:
    background = (255, 255, 255, 255) if mode == "RGBA" else (255, 255, 255)
    foreground = (0, 0, 0, 255) if mode == "RGBA" else (0, 0, 0)
    image = Image.new(mode, size, background)
    ImageDraw.Draw(image).rectangle((100, 100, 300, 300), fill=foreground)
    output = io.BytesIO()
    image.save(output, "PNG")
    return output.getvalue()


def test_valid_mindmap_markdown_reports_shape():
    result = check_mindmap_markdown(
        b"# Product launch\r\n\r\n- Research\r\n  - Customers\r\n- Delivery"
    )

    assert result.clean
    assert result.notes == ("Mind-map hierarchy: 4 nodes, depth 3",)


@pytest.mark.parametrize(
    ("markdown", "finding"),
    [
        ("", "one non-empty H1"),
        ("# Root", "at least one child"),
        ("# Root\n# Other\n- Child", "exactly one heading"),
        ("# Root\n  - Child", "first list level"),
        ("# Root\n- Child\n   - Grandchild\n  - Inconsistent", "inconsistently"),
        ("# Root\n- [link](https://example.com)", "unsafe"),
        ("# Root\n- <script>alert(1)</script>", "unsafe"),
        ("# Root\n- ```python", "unsafe"),
        ("# Root\nparagraph", "unordered-list"),
        ("# Root\n- ok\x00", "control"),
    ],
)
def test_invalid_mindmap_markdown_is_rejected(markdown, finding):
    result = check_mindmap_markdown(markdown.encode())

    assert not result.clean
    assert finding in result.findings[0]


def test_mindmap_markdown_enforces_all_limits():
    too_many = "# Root\n" + "\n".join(
        f"- Node {index}" for index in range(MINDMAP_MAX_NODES)
    )
    too_deep = "# Root\n" + "\n".join(
        f"{'  ' * index}- Level {index}" for index in range(6)
    )
    long_label = f"# Root\n- {'x' * (MINDMAP_MAX_LABEL_CHARS + 1)}"

    assert "exceeds 60 nodes" in check_mindmap_markdown(too_many.encode()).findings[0]
    assert "exceeds depth 6" in check_mindmap_markdown(too_deep.encode()).findings[0]
    assert (
        "exceeds 120 characters"
        in check_mindmap_markdown(long_label.encode()).findings[0]
    )


def test_mindmap_markdown_requires_utf8():
    assert "valid UTF-8" in check_mindmap_markdown(b"\xff").findings[0]


@pytest.mark.parametrize("mode", ["RGB", "RGBA"])
def test_mindmap_png_accepts_fully_decoded_expected_image(mode):
    result = check_mindmap_png(_png(mode=mode))

    assert result.clean
    assert result.notes == ("Mind-map PNG: 2400x1600",)


def test_mindmap_png_rejects_corrupt_trailing_and_wrong_size_data():
    valid = _png()

    assert "complete PNG" in check_mindmap_png(valid[:-10]).findings[0]
    assert "complete PNG" in check_mindmap_png(valid + b"trailing").findings[0]
    assert "exactly 2400x1600" in check_mindmap_png(_png(size=(100, 100))).findings[0]


def test_mindmap_png_rejects_blank_and_transparent_images():
    blank = Image.new("RGB", (MINDMAP_WIDTH, MINDMAP_HEIGHT), "white")
    transparent = Image.new("RGBA", (MINDMAP_WIDTH, MINDMAP_HEIGHT), (0, 0, 0, 0))
    partly_transparent = Image.new(
        "RGBA", (MINDMAP_WIDTH, MINDMAP_HEIGHT), (255, 255, 255, 255)
    )
    ImageDraw.Draw(partly_transparent).rectangle(
        (100, 100, 300, 300), fill=(0, 0, 0, 128)
    )

    def encode(image):
        output = io.BytesIO()
        image.save(output, "PNG")
        return output.getvalue()

    assert "single color" in check_mindmap_png(encode(blank)).findings[0]
    assert "fully opaque" in check_mindmap_png(encode(transparent)).findings[0]
    assert "fully opaque" in check_mindmap_png(encode(partly_transparent)).findings[0]
