"""Programmatic checks for Markdown-backed generated infographic PNGs."""

from __future__ import annotations

import io
import re
import struct

from PIL import Image, ImageChops, UnidentifiedImageError

from .base import StructuralCheckResult

_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_MAX_MARKDOWN_CHARS = 16_000
_MIN_CHANGED_PIXELS = 1_000
_MAX_DIMENSION = 8_192
_MAX_PIXELS = 40_000_000


def check_infographic_markdown(data: bytes) -> StructuralCheckResult:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return StructuralCheckResult(("Infographic Markdown must be valid UTF-8",))
    if not text.strip():
        return StructuralCheckResult(("Infographic Markdown must not be empty",))
    if len(text) > _MAX_MARKDOWN_CHARS:
        return StructuralCheckResult(
            (f"Infographic Markdown exceeds {_MAX_MARKDOWN_CHARS} characters",)
        )
    if _CONTROL_RE.search(text):
        return StructuralCheckResult(
            ("Infographic Markdown contains unsupported control characters",)
        )
    headings = [line for line in text.splitlines() if line.startswith("#")]
    if not headings or not headings[0].startswith("# "):
        return StructuralCheckResult(
            ("Infographic Markdown must start its hierarchy with one H1 title",)
        )
    if len(headings) < 2:
        return StructuralCheckResult(
            ("Infographic Markdown needs at least one content section",)
        )
    return StructuralCheckResult(())


def _png_ends_at_iend(data: bytes) -> bool:
    offset = len(_PNG_SIGNATURE)
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_end = offset + 12 + length
        if chunk_end > len(data):
            return False
        if data[offset + 4 : offset + 8] == b"IEND":
            return chunk_end == len(data) and length == 0
        offset = chunk_end
    return False


def check_infographic_png(data: bytes) -> StructuralCheckResult:
    if not data.startswith(_PNG_SIGNATURE) or not _png_ends_at_iend(data):
        return StructuralCheckResult(("Infographic output must be one complete PNG",))
    try:
        with Image.open(io.BytesIO(data)) as image:
            if getattr(image, "n_frames", 1) != 1:
                return StructuralCheckResult(
                    ("Infographic output must not be animated",)
                )
            image.load()
            width, height = image.size
            if (
                width < 256
                or height < 256
                or width > _MAX_DIMENSION
                or height > _MAX_DIMENSION
                or width * height > _MAX_PIXELS
            ):
                return StructuralCheckResult(
                    ("Infographic output dimensions are unsupported",)
                )
            if image.mode not in {"RGB", "RGBA"}:
                return StructuralCheckResult(
                    ("Infographic PNG must use RGB or RGBA color",)
                )
            if image.mode == "RGBA":
                alpha = image.getchannel("A")
                if alpha.getextrema() != (255, 255):
                    return StructuralCheckResult(
                        ("Infographic PNG must use a fully opaque canvas",)
                    )
                image = image.convert("RGB")
            extrema = image.getextrema()
            background = Image.new("RGB", image.size, image.getpixel((0, 0)))
            channels = ImageChops.difference(image, background).split()
            changed = ImageChops.lighter(
                ImageChops.lighter(channels[0], channels[1]),
                channels[2],
            )
            changed_pixels = width * height - changed.histogram()[0]
    except (Image.DecompressionBombError, OSError, UnidentifiedImageError, ValueError):
        return StructuralCheckResult(("Infographic PNG is corrupt or truncated",))

    if all(low == high for low, high in extrema):
        return StructuralCheckResult(("Infographic PNG must not be a single color",))
    if changed_pixels < _MIN_CHANGED_PIXELS:
        return StructuralCheckResult(("Infographic PNG is effectively blank",))
    return StructuralCheckResult(
        (),
        page_count=1,
        notes=(f"Infographic PNG: {width}x{height}",),
    )


__all__ = ["check_infographic_markdown", "check_infographic_png"]
