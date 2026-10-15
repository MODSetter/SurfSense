"""Page ranges as the model writes them: "1-3,7", "5-" to the end, "9-7" backwards."""

import re

from modules.pdf_tools.refusal import PdfRefusedError

# Seven digits are past any PDF's end; int() refuses a number of 4,300.
_ITEM = re.compile(r"([0-9]{1,7})(?:-([0-9]{0,7}))?")
# The most any call uses: 20 split parts of 1,000 pages. A short string can
# name billions, so this is counted before any list is made.
MAX_NAMED = 20_000
# How much of what was written a refusal repeats.
QUOTED_CHARS = 60
SYNTAX = (
    'write page numbers and ranges from 1, such as "1-3,7", "5-" for page 5 to '
    'the end, or "9-7" for backwards'
)


def page_numbers(written: str | None, count: int) -> list[int]:
    """The pages named, from 1, in the order written; every page when none are."""
    return [page for group in page_groups(written, count) for page in group]


def page_groups(written: str | None, count: int) -> list[list[int]]:
    """One list per comma-separated item; one group of every page when none are named."""
    if written is None or not written.strip():
        return [list(range(1, count + 1))]
    bounds = []
    named = 0
    for item in written.split(","):
        match = _ITEM.fullmatch(item.strip())
        if match is None:
            raise PdfRefusedError(f"{_quoted(written)} is not a page range: {SYNTAX}.")
        first = int(match[1])
        last = first if match[2] is None else int(match[2] or count)
        for page in (first, last):
            if page < 1:
                raise PdfRefusedError(
                    f"{_quoted(written)} is not a page range: {SYNTAX}."
                )
            if page > count:
                raise PdfRefusedError(
                    f"Page {page} is past the end: the PDF has {count} pages."
                )
        named += abs(last - first) + 1
        if named > MAX_NAMED:
            raise PdfRefusedError(
                f"Those ranges name more than {MAX_NAMED:,} pages; name each page "
                "once or a few times."
            )
        bounds.append((first, last))
    return [_run(first, last) for first, last in bounds]


def _run(first: int, last: int) -> list[int]:
    step = 1 if last >= first else -1
    return list(range(first, last + step, step))


def _quoted(written: str) -> str:
    if len(written) <= QUOTED_CHARS:
        return f'"{written}"'
    return f'"{written[: QUOTED_CHARS - 1]}…"'
