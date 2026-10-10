"""Every redirect hop is checked, and credentials stay with the host they were for."""

import sys
import urllib.parse
import urllib.request
from http.client import HTTPMessage
from typing import IO

from surfsense_plugin_sdk.http.declared_hosts import checked_host

# What requests and httpx also drop when a redirect leaves the host.
CREDENTIALS = ("Authorization", "Cookie")


class CheckEveryHop(urllib.request.HTTPRedirectHandler):
    """Follows a redirect only to a declared host."""

    def redirect_request(
        self,
        req: urllib.request.Request,
        fp: IO[bytes],
        code: int,
        msg: str,
        headers: HTTPMessage,
        newurl: str,
    ) -> urllib.request.Request | None:
        """Per hop: log it, check the next host, drop credentials if it changes."""
        here = urllib.parse.urlsplit(req.full_url).hostname
        sys.stderr.write(f"http: {req.get_method()} {here} {code}\n")
        there = checked_host(newurl)

        following = super().redirect_request(req, fp, code, msg, headers, newurl)
        if following is not None and there != here:
            for name in CREDENTIALS:
                following.remove_header(name)
        return following
