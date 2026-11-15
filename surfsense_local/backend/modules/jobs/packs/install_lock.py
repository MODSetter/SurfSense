"""One install at a time, process-wide: a developer's packs, the path route, an import, a download
and the daily check all install, and two at once could each move the other's version away.

Re-entrant, since an install lists the installed packs for its caller's rules while holding it.
"""

import threading

INSTALLING = threading.RLock()
