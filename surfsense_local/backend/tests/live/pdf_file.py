"""A PDF the agent made, read the way a live case checks it: pages, text, headings and what is set in bold."""

import ctypes
import re
from collections import Counter
from functools import cached_property

import pypdfium2 as pdfium
import pypdfium2.raw as pdfium_c

_BOLD_FONT = re.compile(r"bold|black|heavy|semibold|demi", re.IGNORECASE)


class PdfFile:
    def __init__(self, data: bytes) -> None:
        self.data = data

    @cached_property
    def pages(self) -> int:
        return len(pdfium.PdfDocument(self.data))

    @cached_property
    def text(self) -> str:
        document = pdfium.PdfDocument(self.data)
        return "\n".join(page.get_textpage().get_text_range() for page in document)

    @cached_property
    def bold_text(self) -> list[str]:
        """Each line's runs of characters set in a bold font, in reading order."""
        runs: list[str] = []
        name = ctypes.create_string_buffer(256)
        flags = ctypes.c_int()
        for page in pdfium.PdfDocument(self.data):
            text = page.get_textpage()
            current: list[str] = []
            for index in range(text.count_chars()):
                char = text.get_text_range(index, 1)
                pdfium_c.FPDFText_GetFontInfo(
                    text.raw, index, name, len(name), ctypes.byref(flags)
                )
                bold = bool(_BOLD_FONT.search(name.value.decode(errors="replace")))
                if bold and char not in "\r\n":
                    current.append(char)
                    continue
                if char.isspace() and current and char not in "\r\n":
                    current.append(char)
                    continue
                runs.append("".join(current))
                current = []
            runs.append("".join(current))
        return [" ".join(run.split()) for run in runs if run.strip()]

    @cached_property
    def headings(self) -> list[str]:
        """Each line set wholly larger than the body text, in reading order."""
        lines: list[list[tuple[str, float]]] = []
        for page in pdfium.PdfDocument(self.data):
            text = page.get_textpage()
            line: list[tuple[str, float]] = []
            for index in range(text.count_chars()):
                char = text.get_text_range(index, 1)
                if char in "\r\n":
                    lines.append(line)
                    line = []
                else:
                    line.append((char, pdfium_c.FPDFText_GetFontSize(text.raw, index)))
            lines.append(line)
        sizes = Counter(
            round(size, 1)
            for line in lines
            for char, size in line
            if not char.isspace()
        )
        if not sizes:
            return []
        body = sizes.most_common(1)[0][0]
        return [
            "".join(char for char, _ in line).strip()
            for line in lines
            if any(not c.isspace() for c, _ in line)
            and all(size > body + 0.5 for c, size in line if not c.isspace())
        ]
