"""Pages merged, taken out, split, turned or put in a new order: each a new PDF.

The PDF read is never changed: every operation writes a copy.
"""

from collections import Counter
from io import BytesIO

import pypdf

from modules.pdf_tools import opened_pdf
from modules.pdf_tools.refusal import PdfRefusedError

QUARTER_TURNS = (90, 180, 270)


def merge(readers: list[pypdf.PdfReader]) -> bytes:
    """Every page of each PDF, in the order given, with their bookmarks."""
    total = sum(len(reader.pages) for reader in readers)
    if total > opened_pdf.MAX_PAGES:
        raise PdfRefusedError(
            f"The merged PDF would have {total:,} pages; the PDF tools make files "
            f"of at most {opened_pdf.MAX_PAGES:,} pages."
        )
    writer = pypdf.PdfWriter()
    for reader in readers:
        writer.append(reader)
    return written(writer)


def extract(reader: pypdf.PdfReader, pages: list[int]) -> bytes:
    """The pages named, from 1, in that order; a page named twice comes twice."""
    if len(pages) > opened_pdf.MAX_PAGES:
        raise PdfRefusedError(
            f"That names {len(pages):,} pages; the PDF tools make files of at most "
            f"{opened_pdf.MAX_PAGES:,} pages."
        )
    writer = pypdf.PdfWriter()
    writer.append(reader, pages=[page - 1 for page in pages])
    return written(writer)


def split(reader: pypdf.PdfReader, groups: list[list[int]]) -> list[bytes]:
    """One PDF per group of pages."""
    return [extract(reader, group) for group in groups]


def rotate(reader: pypdf.PdfReader, pages: list[int], angle: int) -> bytes:
    """The whole PDF, with the pages named turned clockwise by `angle` on top of their own turn."""
    if angle not in QUARTER_TURNS:
        raise PdfRefusedError(
            "angle must be 90, 180 or 270 degrees clockwise; 270 turns a page "
            "a quarter to the left."
        )
    writer = pypdf.PdfWriter(clone_from=reader)
    for page in dict.fromkeys(pages):
        turned = writer.pages[page - 1]
        # pypdf adds without wrapping; a viewer may refuse /Rotate 450.
        turned.rotation = (turned.rotation + angle) % 360
    return written(writer)


def reorder(reader: pypdf.PdfReader, pages: list[int]) -> bytes:
    """Every page once, in the order named; a page left out or named twice is refused."""
    count = len(reader.pages)
    twice = sorted(page for page, times in Counter(pages).items() if times > 1)
    missing = sorted(set(range(1, count + 1)) - set(pages))
    problems = []
    if twice:
        problems.append(f"{_pages(twice)} {_is(twice)} named twice")
    if missing:
        problems.append(f"{_pages(missing)} {_are(missing)} missing")
    if problems:
        raise PdfRefusedError(
            f"A new order names every one of the {count} pages once: "
            f"{'; '.join(problems)}. To keep only some pages, use extract."
        )
    return extract(reader, pages)


def written(writer: pypdf.PdfWriter) -> bytes:
    """The writer's PDF as bytes."""
    out = BytesIO()
    writer.write(out)
    return out.getvalue()


def _pages(numbers: list[int]) -> str:
    if len(numbers) == 1:
        return f"page {numbers[0]}"
    listed = ", ".join(map(str, numbers[:-1]))
    return f"pages {listed} and {numbers[-1]}"


def _is(numbers: list[int]) -> str:
    return "is" if len(numbers) == 1 else "are"


def _are(numbers: list[int]) -> str:
    return _is(numbers)
