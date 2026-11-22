"""The policy that leaves a model-written page no network (ADR 0066).

A page is built from the user's sources, which can carry instructions aimed at
the model; a request's URL can carry what the page read, so it may make none.
"""

import re

# No host at all, fonts and CDNs included: a stylesheet's URL leaks as well as a fetch.
NO_NETWORK_POLICY = (
    "default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; "
    "img-src data: blob:; font-src data:; media-src data: blob:; "
    "form-action 'none'; base-uri 'none'"
)
_META = f'<meta http-equiv="Content-Security-Policy" content="{NO_NETWORK_POLICY}">'
# Only what may precede a doctype: a byte order mark, whitespace and comments.
_LEADING_DOCTYPE = re.compile(
    r"\A\uFEFF?\s*(?:<!--.*?-->\s*)*<!doctype[^>]*>", re.IGNORECASE | re.DOTALL
)


def without_network(page: str) -> str:
    """The page with the policy's meta first, so nothing it wrote runs before it.

    After the doctype rather than inside `<head>`: a script placed ahead of the
    head would run unpoliced, and the parser opens the head for the meta itself.
    """
    leading = _LEADING_DOCTYPE.match(page)
    at = leading.end() if leading else 0
    return page[:at] + _META + page[at:]
