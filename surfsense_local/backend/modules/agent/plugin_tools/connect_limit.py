"""How long an engine tries a plugin before the turn names it unreachable.

The same for both engines, so a plugin is reported alike whichever runs the
thread. Under OpencodeClient's 30 s, so one server's hang fails its own add,
not the turn's.
"""

CONNECT_SECONDS = 25
