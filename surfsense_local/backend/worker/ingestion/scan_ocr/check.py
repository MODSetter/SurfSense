"""For the release build: the frozen worker carries its OCR readers and reads a
line with each. Their imports are lazy, so a spec that drops them fails only here."""

import sys

from PIL import Image, ImageDraw, ImageFont

from worker.ingestion.scan_ocr.frames import Frame
from worker.ingestion.scan_ocr.reader import PageReader, rapid_reader, vision_reader

SAMPLE = "SurfSense reads scanned pages"
_FONTS = (
    "arial.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
)


def check_scan_ocr() -> str:
    """What each reader read; raises when one cannot be imported or started."""
    import rapidocr  # noqa: F401

    readers: list[PageReader | None] = [rapid_reader()]
    if sys.platform == "darwin":
        import Quartz  # noqa: F401
        import Vision  # noqa: F401

        readers.append(vision_reader())
    if any(reader is None for reader in readers):
        raise RuntimeError("an OCR reader could not start")
    return "; ".join(_read(reader) for reader in readers if reader is not None)


def _read(reader: PageReader) -> str:
    """Raises unless every word of the sample came back."""
    [(_, page)] = list(reader.read([Frame(1, _sample(), 0.05)]))
    text = page.text()
    missing = [word for word in SAMPLE.split() if word.lower() not in text.lower()]
    if missing:
        raise RuntimeError(f"{reader.name} read {text!r}, missing {missing}")
    return f"{reader.name} read {text!r}"


def _sample() -> Image.Image:
    image = Image.new("L", (1400, 200), 255)
    ImageDraw.Draw(image).text((40, 60), SAMPLE, fill=0, font=_font())
    return image


def _font() -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for name in _FONTS:
        try:
            return ImageFont.truetype(name, 64)
        except OSError:
            continue
    return ImageFont.load_default(size=64)
