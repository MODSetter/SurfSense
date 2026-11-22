"""Whether SurfSense's licensing runs at all. Off since SurfSense became free on 27 Nov 2026
(ADR 0092): every job runs, and nothing asks a licence server or sends a licence key. The
code stays, so licensing can come back by flipping the constant.
"""

import os

LICENSING_ON = False
# The maintainer's own tests run the licensing code through this; no release sets it.
OVERRIDE = "SURFSENSE_LOCAL_LICENSING"


def licensing_on() -> bool:
    return LICENSING_ON or os.environ.get(OVERRIDE) == "1"
