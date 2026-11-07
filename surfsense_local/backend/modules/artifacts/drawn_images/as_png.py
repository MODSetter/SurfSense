"""A kept picture as document scripts are promised it: a PNG, whatever the model answered in."""

from io import BytesIO

from PIL import Image

# Past this a picture is refused unread: a small file can decode to gigabytes,
# and no image model draws anywhere near it.
MOST_PIXELS = 40_000_000
_PNG_MODES = frozenset({"1", "L", "LA", "I", "I;16", "P", "RGB", "RGBA"})


def as_png(data: bytes, mime_type: str) -> bytes:
    """Raises OSError or ValueError when the bytes are not a picture to place."""
    try:
        with Image.open(BytesIO(data)) as image:
            if image.width * image.height > MOST_PIXELS:
                raise ValueError(f"too large: {image.width} x {image.height}")
            if mime_type == "image/png":
                return data
            # A JPEG can be CMYK, which a PNG cannot hold.
            writable = image if image.mode in _PNG_MODES else image.convert("RGB")
            out = BytesIO()
            writable.save(out, format="PNG")
    except Image.DecompressionBombError as error:
        raise ValueError(str(error)) from error
    return out.getvalue()
