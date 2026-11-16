"""Which puller takes a link: YouTube's for a video, the page reader for anything else.

The link alone decides, so a note added by a puller this version retired is read
by whichever takes its link now.
"""

from urllib.parse import urlsplit

from modules.documents.web_sources.pullers import web_page, youtube
from modules.documents.web_sources.pullers.puller import Puller

# The page reader last: it takes every link.
PULLERS = (youtube.PULLER, web_page.PULLER)


def routed(url: str) -> Puller:
    parts = urlsplit(url)
    return next(puller for puller in PULLERS if puller.takes(parts))
