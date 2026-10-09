"""The font a stamp's text is drawn in: Helvetica for Western text, else one this computer has.

Helvetica is one of PDF's standard fonts, so it needs no file and nothing is
embedded; it covers only Windows-1252. Other scripts need a TrueType font with
every character, embedded as a subset.
"""

import os
from functools import cache
from pathlib import Path

from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

STANDARD = "Helvetica"


def font_for(text: str) -> str | None:
    """The registered name of a font that draws every character of `text`, or None."""
    try:
        text.encode("cp1252")
        return STANDARD
    except UnicodeEncodeError:
        pass
    wanted = {ord(character) for character in text if not character.isspace()}
    for path in _candidates():
        font = _loaded(str(path))
        if font is not None and wanted <= font.face.charToGlyph.keys():
            return font.fontName
    return None


def _candidates() -> list[Path]:
    """Fonts that ship with Windows, macOS and common Linux desktops, widest first per script."""
    windows = Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"
    found = [
        windows / name
        for name in (
            "arial.ttf",
            "Nirmala.ttf",
            "malgun.ttf",
            "msyh.ttc",
            "YuGothR.ttc",
            "msgothic.ttc",
            "simsun.ttc",
        )
    ]
    found += map(
        Path,
        (
            "/System/Library/Fonts/Supplemental/Arial Unicode.ttf",
            "/Library/Fonts/Arial Unicode.ttf",
            "/System/Library/Fonts/Supplemental/Arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
            "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf",
            "/usr/share/fonts/truetype/noto/NotoSansDevanagari-Regular.ttf",
            "/usr/share/fonts/truetype/droid/DroidSansFallbackFull.ttf",
            "/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
        ),
    )
    return [path for path in found if path.is_file()]


@cache
def _loaded(path: str) -> TTFont | None:
    """The font registered under its path, or None when reportlab cannot read it (a CFF outline)."""
    name = f"Stamp-{Path(path).stem}"
    try:
        font = TTFont(name, path, subfontIndex=0)
    # reportlab raises its own TTFError, and others on a font it half reads.
    except Exception:
        return None
    pdfmetrics.registerFont(font)
    return font
