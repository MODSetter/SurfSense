"""A bot wall answering in a page's place, which a reader without a browser cannot pass.

The markers are Web Crawl's: Cloudflare's interstitial and DataDome's captcha frame.
A Turnstile or reCAPTCHA widget alone also sits on healthy pages, so it is no sign.
"""

import re

_CLOUDFLARE = re.compile(
    r"just a moment"
    r"|checking your browser"
    r"|enable javascript and cookies to continue"
    r"|verify you are human"
    r"|cf-mitigated"
    r"|id=\"(?:cf-)?challenge-running\""
    r"|id=\"turnstile-wrapper\""
    r"|ddos-guard",
    re.IGNORECASE,
)
_DATADOME_WALL = re.compile(r"captcha-delivery\.com", re.IGNORECASE)
# Challenge markers sit near the top of a wall page.
HEAD_CHARACTERS = 65_536
# Under this much text, a page with a wall's markers is the wall itself.
WALL_MAX_CHARACTERS = 1000


def is_wall(html: str, text: str) -> bool:
    if len(text) >= WALL_MAX_CHARACTERS:
        return False
    head = html[:HEAD_CHARACTERS]
    return bool(_CLOUDFLARE.search(head) or _DATADOME_WALL.search(head))
