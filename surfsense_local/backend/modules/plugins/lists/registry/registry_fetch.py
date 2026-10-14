"""Fetching the signed registry and its icons from SurfSense's plugin host."""

import httpx

from modules.plugins.lists.plugin_host import PLUGIN_HOST, as_served

TIMEOUT = httpx.Timeout(10.0)
# Icons are a few kilobytes; anything far larger is not one.
MAX_ICON_BYTES = 512 * 1024


class RegistryFetchError(Exception):
    pass


def registry_url(path: str) -> str:
    """On the compiled host, or the local one a developer's build points at instead."""
    return as_served(f"{PLUGIN_HOST}/{path}")


async def fetch_signed_list() -> tuple[bytes, bytes]:
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            body = await client.get(registry_url("plugins.json"))
            body.raise_for_status()
            signature = await client.get(registry_url("plugins.json.sig"))
            signature.raise_for_status()
    except httpx.HTTPError as error:
        raise RegistryFetchError(str(error)) from error
    return body.content, signature.content


async def fetch_icon(client: httpx.AsyncClient, name: str) -> bytes | None:
    try:
        response = await client.get(registry_url(f"icons/{name}"))
    except httpx.HTTPError:
        return None
    if response.status_code != 200 or len(response.content) > MAX_ICON_BYTES:
        return None
    return response.content
