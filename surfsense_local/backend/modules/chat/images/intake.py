"""An attached image, checked by its bytes and turned into what every model decodes."""

import hashlib
import io
from dataclasses import dataclass

from PIL import Image as Pillow
from PIL import ImageOps, UnidentifiedImageError

from modules.llm.providers.types import Image

__all__ = [
    "MAX_IMAGE_BYTES",
    "MAX_SIDE",
    "ImageRefusedError",
    "NormalisedImage",
    "normalise",
]

MAX_IMAGE_BYTES = 10 * 1024 * 1024
# Qwen2.5-VL spends one token per 28 px square, so 1024 px is ~1,340 tokens: the
# most a small local window can give one picture. Also well under every
# provider's per-image limit once re-encoded.
MAX_SIDE = 1024
# Pillow's names for what the composer accepts; anything else is refused.
ACCEPTED = frozenset({"PNG", "JPEG", "WEBP", "GIF", "BMP", "TIFF"})
_JPEG_QUALITY = 90


class ImageRefusedError(ValueError):
    """The bytes are not an image the composer accepts; the message says why."""


@dataclass(frozen=True)
class NormalisedImage:
    mime: str
    data: bytes
    sha256: str

    @property
    def extension(self) -> str:
        return ".png" if self.mime == "image/png" else ".jpg"

    def as_part(self) -> Image:
        return Image(self.mime, self.data)


def normalise(data: bytes) -> NormalisedImage:
    """Upright, at most MAX_SIDE on its longest side, as PNG or JPEG.

    PNG only when the picture has transparency, which JPEG would paint black.
    """
    if len(data) > MAX_IMAGE_BYTES:
        raise ImageRefusedError(
            f"an image is larger than {MAX_IMAGE_BYTES // 2**20} MB"
        )
    try:
        with Pillow.open(io.BytesIO(data)) as source:
            if source.format not in ACCEPTED:
                raise ImageRefusedError(
                    f"{source.format or 'this'} images are not supported"
                )
            picture = ImageOps.exif_transpose(source)
            picture.thumbnail((MAX_SIDE, MAX_SIDE), Pillow.Resampling.LANCZOS)
            return _encoded(picture)
    except (UnidentifiedImageError, Pillow.DecompressionBombError, OSError) as error:
        raise ImageRefusedError("this file is not an image that can be read") from error


def _encoded(picture: Pillow.Image) -> NormalisedImage:
    out = io.BytesIO()
    if _has_alpha(picture):
        picture.convert("RGBA").save(out, format="PNG")
        mime = "image/png"
    else:
        picture.convert("RGB").save(out, format="JPEG", quality=_JPEG_QUALITY)
        mime = "image/jpeg"
    data = out.getvalue()
    return NormalisedImage(mime, data, hashlib.sha256(data).hexdigest())


def _has_alpha(picture: Pillow.Image) -> bool:
    return picture.mode in ("RGBA", "LA", "PA") or "transparency" in picture.info
