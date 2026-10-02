"""The one way this slice reaches Hugging Face."""

import httpx

BASE = "https://huggingface.co"
TIMEOUT = httpx.Timeout(15.0, connect=10.0)


def transport() -> httpx.AsyncBaseTransport | None:
    """The network itself; tests answer in its place."""
    return None


def client() -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=BASE, transport=transport(), timeout=TIMEOUT, follow_redirects=True
    )
