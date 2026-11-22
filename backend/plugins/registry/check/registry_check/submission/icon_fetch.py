"""The submitted icon: an image dropped into the form, or a link to one, fetched once.

A stranger names the address, so only https to a public host, and never more than the
icon rules allow.
"""

import re

import httpx2

from registry_check.live.failure_reason import failure_reason
from registry_check.live.web import web_client
from registry_check.static.icon_rules import LARGEST_BYTES, PNG_SIGNATURE
from registry_check.submission.public_address import address_problem

# A dropped image renders as markdown or an <img> tag; a pasted link is bare.
_ADDRESS = re.compile(r"https://[^\s)\"'<>]+")
# GitHub serves a dropped image from its own hosts after a redirect or two.
_REDIRECTS = 3


class IconRefusedError(Exception):
    """Why the icon could not be fetched, in words fit for a public comment."""


def icon_address(answer: str) -> str | None:
    found = _ADDRESS.search(answer)
    return found.group(0) if found else None


def icon_extension(content: bytes) -> str:
    return "png" if content.startswith(PNG_SIGNATURE) else "svg"


async def fetch_icon(url: str) -> bytes:
    try:
        return await _fetched(url)
    except httpx2.HTTPError as error:
        raise IconRefusedError(
            f"could not be reached: {failure_reason(error)}"
        ) from None


async def _fetched(url: str) -> bytes:
    async with web_client() as http:
        for _ in range(_REDIRECTS + 1):
            _refuse_unless_public(url)
            async with http.stream("GET", url) as response:
                if response.is_redirect:
                    url = (
                        str(response.next_request.url) if response.next_request else ""
                    )
                    continue
                if response.status_code != 200:
                    raise IconRefusedError(f"answered {response.status_code}")
                content = b""
                async for chunk in response.aiter_bytes():
                    content += chunk
                    if len(content) > LARGEST_BYTES:
                        raise IconRefusedError("is larger than 32 KB")
                return content
    raise IconRefusedError("redirected too many times")


def _refuse_unless_public(url: str) -> None:
    problem = address_problem(url)
    if problem:
        raise IconRefusedError(problem)
