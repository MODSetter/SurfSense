"""The address the user's browser is on, where a sign-in's callback must land
(docs/architecture/docker.md, Sign-ins)."""

from dataclasses import dataclass

from fastapi import Request

from api.config import get_settings

_LOOPBACK = {"localhost", "127.0.0.1", "::1", "[::1]"}


@dataclass(frozen=True)
class BrowserOrigin:
    scheme: str
    host: str
    port: int

    @classmethod
    def loopback(cls, port: int) -> "BrowserOrigin":
        return cls("http", "127.0.0.1", port)

    @property
    def is_loopback(self) -> bool:
        return self.host in _LOOPBACK

    @property
    def url(self) -> str:
        default = 443 if self.scheme == "https" else 80
        port = "" if self.port == default else f":{self.port}"
        return f"{self.scheme}://{self.host}{port}"


def browser_origin(request: Request) -> BrowserOrigin:
    """In the container, the Host the browser sent, which Caddy and the access
    service have vetted. Anywhere else the loopback port: on the desktop a page
    rebinding a name to the loopback API chooses its own Host."""
    settings = get_settings()
    loopback = BrowserOrigin.loopback(settings.browser_port())
    if not settings.in_container():
        return loopback
    scheme = request.headers.get("x-forwarded-proto", "http")
    host, _, port = request.headers.get("host", "").rpartition(":")
    if not host or not port.isdigit():
        host, port = request.headers.get("host", ""), ""
    origin = BrowserOrigin(
        scheme, host.lower(), int(port) if port else (443 if scheme == "https" else 80)
    )
    return loopback if origin.is_loopback or not origin.host else origin
