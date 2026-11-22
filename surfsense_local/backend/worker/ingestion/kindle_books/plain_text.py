import html
import re

_BLANK_LINE = re.compile(r"\r?\n\s*\r?\n")


def as_paragraphs(text: str) -> str:
    """A plain PalmDOC e-text as HTML: each blank-line-separated block a paragraph,
    escaped, since a < in it is a word and not markup."""
    blocks = (block.strip() for block in _BLANK_LINE.split(text))
    paragraphs = "".join(
        f"<p>{html.escape(block, quote=False)}</p>" for block in blocks if block
    )
    return f"<html><body>{paragraphs}</body></html>"
