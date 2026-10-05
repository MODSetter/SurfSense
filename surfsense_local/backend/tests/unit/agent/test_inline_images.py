"""A page preview as the image a tool result carries to the model."""

from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image

from modules.agent.previews.inline_images import (
    INLINE_LONG_SIDE,
    INLINE_PIXELS,
    inline_image,
)

pytestmark = pytest.mark.unit


def _png(tmp_path: Path, size: tuple[int, int], mode: str = "RGB", colour=None) -> Path:
    path = tmp_path / f"page-{size[0]}x{size[1]}-{mode}.png"
    image = Image.new(mode, size, colour if colour is not None else "white")
    image.save(path, format="PNG")
    return path


def _decoded(data: bytes) -> Image.Image:
    with Image.open(BytesIO(data)) as image:
        image.load()
        return image.copy()


def test_an_a4_page_is_scaled_to_the_pixel_budget_keeping_its_shape(
    tmp_path: Path,
) -> None:
    """Anthropic bills an image by its pixels; 750K is about 1,000 tokens."""
    image = _decoded(inline_image(_png(tmp_path, (1000, 1415))).data)

    assert image.width * image.height <= INLINE_PIXELS
    assert image.width * image.height > INLINE_PIXELS * 0.99
    assert abs(image.height / image.width - 1.415) < 0.01


def test_a_long_page_is_scaled_to_the_long_side_limit(tmp_path: Path) -> None:
    """At the pixel budget alone a 1:4 page would still be 1,732 px tall."""
    image = _decoded(inline_image(_png(tmp_path, (1000, 4000))).data)

    assert max(image.size) <= INLINE_LONG_SIDE


def test_a_page_within_both_limits_keeps_its_size(tmp_path: Path) -> None:
    """A 16:9 slide is never scaled up."""
    image = _decoded(inline_image(_png(tmp_path, (1000, 563))).data)

    assert image.size == (1000, 563)


def test_a_transparent_page_is_flattened_on_white(tmp_path: Path) -> None:
    """JPEG has no alpha: a clear background must not turn black."""
    image = _decoded(
        inline_image(_png(tmp_path, (200, 200), "RGBA", (0, 0, 0, 0))).data
    )

    assert image.mode == "RGB"
    assert all(channel > 245 for channel in image.getpixel((100, 100)))


def test_the_image_is_a_jpeg(tmp_path: Path) -> None:
    """JPEG decodes everywhere SurfSense sends images; WebP fails on llama-server."""
    inline = inline_image(_png(tmp_path, (1000, 1415)))

    assert inline.mime == "image/jpeg"
    assert inline.data.startswith(b"\xff\xd8\xff")


def test_one_page_always_encodes_to_the_same_bytes(tmp_path: Path) -> None:
    """The live harness finds a page in the requests by these exact bytes."""
    page = _png(tmp_path, (1000, 1415), colour=(30, 120, 60))

    assert inline_image(page).data == inline_image(page).data
