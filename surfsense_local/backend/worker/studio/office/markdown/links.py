"""Which link targets a built document may carry."""

_SCHEMES = ("http://", "https://", "mailto:")


def safe_href(href: str | None) -> str | None:
    """The target when it is a web or mail address; anything else stays plain text."""
    if href and href.strip().lower().startswith(_SCHEMES):
        return href.strip()
    return None
