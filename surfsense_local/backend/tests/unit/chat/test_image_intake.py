"""What an attached image becomes before it is stored or sent."""

import io

import pytest
from PIL import Image as Pillow

from modules.chat.images.intake import (
    MAX_IMAGE_BYTES,
    MAX_SIDE,
    ImageRefusedError,
    normalise,
)

pytestmark = pytest.mark.unit


def encoded(image: Pillow.Image, format: str, **params: object) -> bytes:
    """The picture saved as the given format."""
    out = io.BytesIO()
    image.save(out, format=format, **params)
    return out.getvalue()


def decoded(data: bytes) -> Pillow.Image:
    """The picture normalised bytes hold."""
    return Pillow.open(io.BytesIO(data))


def test_a_photo_becomes_a_jpeg_no_wider_than_the_cap() -> None:
    """Small enough for every provider's limit and cheap in tokens."""
    photo = Pillow.new("RGB", (4000, 3000), "navy")

    image = normalise(encoded(photo, "PNG"))

    assert image.mime == "image/jpeg"
    assert decoded(image.data).size == (MAX_SIDE, MAX_SIDE * 3 // 4)


def test_transparency_is_kept_as_png() -> None:
    """A JPEG would paint the transparent parts black."""
    logo = Pillow.new("RGBA", (64, 64), (255, 0, 0, 0))

    image = normalise(encoded(logo, "PNG"))

    assert image.mime == "image/png"
    assert decoded(image.data).mode == "RGBA"


def test_a_small_image_is_not_scaled_up() -> None:
    """Scaling up spends tokens on pixels the picture never had."""
    image = normalise(encoded(Pillow.new("RGB", (40, 30)), "JPEG"))

    assert decoded(image.data).size == (40, 30)


@pytest.mark.parametrize("format", ["WEBP", "GIF", "BMP", "TIFF"])
def test_formats_a_runtime_may_not_decode_are_converted(format: str) -> None:
    """llama.cpp's loader and some providers decode PNG and JPEG alone."""
    image = normalise(encoded(Pillow.new("RGB", (20, 20), "teal"), format))

    assert image.mime in {"image/jpeg", "image/png"}


def test_a_phone_photo_is_turned_upright() -> None:
    """Phones store a sideways sensor image and an EXIF note to rotate it."""
    sideways = Pillow.new("RGB", (40, 20))
    exif = sideways.getexif()
    exif[0x0112] = 6  # rotate 90° clockwise to display

    image = normalise(encoded(sideways, "JPEG", exif=exif))

    assert decoded(image.data).size == (20, 40)


def test_bytes_that_are_not_an_image_are_refused() -> None:
    """A PDF with an image name is not an image."""
    with pytest.raises(ImageRefusedError):
        normalise(b"%PDF-1.7 not a picture")


def test_a_format_outside_the_list_is_refused() -> None:
    """The bytes decide, never a claimed type."""
    with pytest.raises(ImageRefusedError):
        normalise(encoded(Pillow.new("RGB", (16, 16)), "ICO"))


def test_an_image_over_the_size_limit_is_refused() -> None:
    """Checked before decoding, so a huge upload costs nothing."""
    with pytest.raises(ImageRefusedError):
        normalise(b"\x89PNG\r\n\x1a\n" + b"\0" * MAX_IMAGE_BYTES)


def test_the_same_picture_normalises_to_the_same_bytes() -> None:
    """Stored by content hash, so a repeat attach reuses one file."""
    picture = encoded(Pillow.new("RGB", (32, 32), "olive"), "PNG")

    assert normalise(picture).sha256 == normalise(picture).sha256
