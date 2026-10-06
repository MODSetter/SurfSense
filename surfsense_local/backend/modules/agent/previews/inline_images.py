"""A page image as a tool result carries it to the model: smaller than the PNG kept on disk."""

import math
from io import BytesIO
from pathlib import Path

from PIL import Image

from modules.agent.tool_endpoint.tool import InlineImage

# Anthropic bills an image at its pixels over 750: about 1,000 tokens, with body
# text on an A4 page (~728 x 1030) still readable. It is paid again on every
# later request until a compaction.
INLINE_PIXELS = 750_000
# Anthropic scales down any image longer than this, so more is paid for nothing.
INLINE_LONG_SIDE = 1568
# About half a PNG's bytes; JPEG decodes everywhere SurfSense sends images, WebP
# not on llama-server. Deterministic, which the live harness relies on.
JPEG_QUALITY = 80


def inline_image(path: Path) -> InlineImage:
    """The PNG at `path` on white, scaled down to both limits, as a JPEG.

    Raises OSError or ValueError when the file is not an image Pillow reads.
    """
    with Image.open(path) as image:
        flat = _on_white(image)
    scale = min(
        1.0,
        math.sqrt(INLINE_PIXELS / (flat.width * flat.height)),
        INLINE_LONG_SIDE / max(flat.size),
    )
    if scale < 1.0:
        size = (max(1, int(flat.width * scale)), max(1, int(flat.height * scale)))
        flat = flat.resize(size, Image.Resampling.LANCZOS)
    out = BytesIO()
    flat.save(out, format="JPEG", quality=JPEG_QUALITY, progressive=False)
    return InlineImage(out.getvalue(), "image/jpeg")


def _on_white(image: Image.Image) -> Image.Image:
    if image.mode in ("RGBA", "LA", "PA") or "transparency" in image.info:
        rgba = image.convert("RGBA")
        flat = Image.new("RGB", rgba.size, "white")
        flat.paste(rgba, mask=rgba.getchannel("A"))
        return flat
    return image.convert("RGB")
