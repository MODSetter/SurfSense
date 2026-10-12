"""An HTTP client for signing in that reaches only the hosts the user allowed.

Discovery can name any host (a resource metadata URL, an authorization server's
endpoints); a request to one not yet asked about is refused here, before it leaves.
"""

import httpx2

from modules.egress.service import host_destination

SIGN_IN_TIMEOUT_SECONDS = 30


class HostNotAllowedError(Exception):
    def __init__(self, host: str) -> None:
        super().__init__(f"{host} is not allowed in Settings > Network")
        self.host = host


def consented_client(allowed_hosts: set[str]) -> httpx2.AsyncClient:
    async def refuse_unasked(request: httpx2.Request) -> None:
        host = request.url.host
        if host not in allowed_hosts and host_destination(str(request.url)) is not None:
            raise HostNotAllowedError(host)

    return httpx2.AsyncClient(
        timeout=SIGN_IN_TIMEOUT_SECONDS, event_hooks={"request": [refuse_unasked]}
    )
