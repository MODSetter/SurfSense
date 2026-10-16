"""A page's text as a reader sees it, without the marks pdfium leaves in it.

pdfium takes the line break out after a line-end hyphen and leaves U+FFFE in the
hyphen's place ('Her<U+FFFE>mes'): the embedder reads such a word as [UNK], and
full-text search splits it there.
"""

import re

_HYPHEN_MARK = re.compile("\ufffe(.?)", re.DOTALL)
# What a broken font map leaves: never text, and python-docx refuses it in a draft.
_CONTROL = re.compile("[\x00-\x08\x0b-\x1f\x7f]")


def printable(text: str) -> str:
    """Lines already end in "\\n"; a tab and a line break are kept."""
    return _CONTROL.sub("", _HYPHEN_MARK.sub(_rejoined, text))


def _rejoined(mark: re.Match[str]) -> str:
    # A word split at the line's end goes on in lower case, as Docling joins it;
    # before a capital, as in 'above-Referenced', the hyphen is the word's own.
    after = mark.group(1)
    return after if after.islower() else "-" + after
