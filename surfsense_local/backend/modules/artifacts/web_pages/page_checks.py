"""What makes bytes a page SurfSense keeps: UTF-8 text, under a size, with markup in it."""

from html.parser import HTMLParser


class PageCheckError(ValueError):
    """Why the bytes are no page to keep, in a sentence naming the fix."""


class _Tags(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.seen = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.seen = True


def checked_page(data: bytes, limit: int) -> str:
    """The page's text, or the refusal: too large, not UTF-8, or no tag in it."""
    if len(data) > limit:
        raise too_large(len(data), limit)
    try:
        page = data.decode("utf-8")
    except UnicodeDecodeError as error:
        raise PageCheckError("The page is not UTF-8 text: save it as UTF-8.") from error
    tags = _Tags()
    tags.feed(page)
    tags.close()
    if not tags.seen:
        raise PageCheckError(
            "The file has no HTML in it: write the whole page, from <!doctype html>."
        )
    return page


def too_large(size: int, limit: int) -> PageCheckError:
    return PageCheckError(
        f"The page is {_size(size)}, larger than the {_size(limit)} a page may be. "
        "Make it smaller: inline less, or draw images as SVG."
    )


def _size(count: int) -> str:
    if count >= 1024 * 1024:
        return f"{count / (1024 * 1024):.1f} MB"
    return f"{max(1, round(count / 1024))} KB"
