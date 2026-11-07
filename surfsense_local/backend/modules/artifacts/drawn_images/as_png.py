"""A kept picture as document scripts are promised it: a PNG, whatever the model answered in."""

from io import BytesIO

from PIL import Image

# Past this a picture is refused unread: a small file can decode to gigabytes,
# and no image model draws anywhere near it.
MOST_PIXELS = 40_000_000


def as_png(data: bytes, mime_type: str) -> bytes:
    """Raises OSError or ValueError when the bytes are not a picture Pillow reads."""
    if mime_type == "image/png":
        return data
    with Image.open(BytesIO(data)) as image:
        if image.width * image.height > MOST_PIXELS:
            raise ValueError(f"too large: {image.width} x {image.height}")
        out = BytesIO()
        image.save(out, format="PNG")
    return out.getvalue()
