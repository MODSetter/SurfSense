"""Fonts for the letters ReportLab's built-in Helvetica cannot set.

Helvetica covers Latin-1 only and draws anything else as a black box. Latin-1
text keeps the default look; other letters switch to DejaVu Sans, which
matplotlib ships, and Chinese, Japanese and Korean to ReportLab's CID fonts.
Right-to-left text is set in logical order and Indic scripts need shaping:
neither is solved here.
"""

import functools
from pathlib import Path
from xml.sax.saxutils import escape

import matplotlib
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont
from reportlab.pdfbase.ttfonts import TTFont

_UNICODE = "DejaVuSans"
_FACES = {
    "normal": "DejaVuSans",
    "bold": "DejaVuSans-Bold",
    "italic": "DejaVuSans-Oblique",
    "boldItalic": "DejaVuSans-BoldOblique",
}
_CHINESE = "STSong-Light"
_JAPANESE = "HeiseiKakuGo-W5"
_KOREAN = "HYGothic-Medium"


@functools.cache
def register_fonts() -> None:
    folder = Path(matplotlib.get_data_path()) / "fonts" / "ttf"
    for face in _FACES.values():
        pdfmetrics.registerFont(TTFont(face, str(folder / f"{face}.ttf")))
    pdfmetrics.registerFontFamily(_UNICODE, **_FACES)
    # The CID fonts have one face; bold and italic markup keeps it.
    for name in (_CHINESE, _JAPANESE, _KOREAN):
        pdfmetrics.registerFont(UnicodeCIDFont(name))
        pdfmetrics.registerFontFamily(
            name, normal=name, bold=name, italic=name, boldItalic=name
        )


def font_markup(text: str) -> str:
    """The text escaped for a Paragraph, each run Helvetica cannot set in a font that can."""
    register_fonts()
    han = _han_font(text)
    parts: list[str] = []
    run: list[str] = []
    current: str | None = None
    for character in text:
        font = _font_for(character, han)
        if font != current and run:
            parts.append(_wrapped("".join(run), current))
            run = []
        current = font
        run.append(character)
    if run:
        parts.append(_wrapped("".join(run), current))
    return "".join(parts)


def _wrapped(text: str, font: str | None) -> str:
    escaped = escape(text)
    return escaped if font is None else f'<font name="{font}">{escaped}</font>'


def _han_font(text: str) -> str:
    """Han characters take the font of the language around them: kana is Japanese."""
    if any(_is_kana(character) for character in text):
        return _JAPANESE
    if any(_is_hangul(character) for character in text):
        return _KOREAN
    return _CHINESE


def _font_for(character: str, han: str) -> str | None:
    if character in "\n\t ":
        return None
    try:
        character.encode("cp1252")
        return None
    except UnicodeEncodeError:
        pass
    if _is_kana(character):
        return _JAPANESE
    if _is_hangul(character):
        return _KOREAN
    if _is_han(character):
        return han
    return _UNICODE


def _is_kana(character: str) -> bool:
    code = ord(character)
    return (
        0x3040 <= code <= 0x30FF or 0x31F0 <= code <= 0x31FF or 0xFF65 <= code <= 0xFF9F
    )


def _is_hangul(character: str) -> bool:
    code = ord(character)
    return (
        0x1100 <= code <= 0x11FF or 0x3130 <= code <= 0x318F or 0xAC00 <= code <= 0xD7AF
    )


def _is_han(character: str) -> bool:
    """Ideographs, and the CJK punctuation and full-width forms set beside them."""
    code = ord(character)
    return (
        0x3000 <= code <= 0x303F
        or 0x3400 <= code <= 0x4DBF
        or 0x4E00 <= code <= 0x9FFF
        or 0xF900 <= code <= 0xFAFF
        or 0xFF00 <= code <= 0xFF64
        or 0xFFA0 <= code <= 0xFFEF
    )
