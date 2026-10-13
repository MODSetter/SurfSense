"""The server no longer knows our session: it answered 404 to a request naming one.

The server did not handle that request, so starting a new session and sending it again is
safe, even for `tools/call`.
"""


class SessionExpiredError(Exception):
    pass
