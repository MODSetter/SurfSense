"""The hosts the installed Claude Code signs in through are ones SurfSense allows.

A release that moved its sign-in refresh to a new host would be refused by the
Claude proxy, and users would be signed out once their token expired. This reads
where the binary says it refreshes, so that shows here first.
"""

import mmap
import os
from pathlib import Path
from urllib.parse import urlsplit

import pytest

from modules.llm.subscriptions.claude.hosts import CLAUDE_HOSTS

pytestmark = pytest.mark.claude_code
MARKER = b'TOKEN_URL:"'


def _token_hosts(binary: Path) -> set[str]:
    """Every host a literal `TOKEN_URL:"https://…"` in the binary names."""
    hosts = set()
    with (
        binary.open("rb") as file,
        mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as data,
    ):
        start = data.find(MARKER)
        while start != -1:
            begin = start + len(MARKER)
            end = data.find(b'"', begin, begin + 200)
            if end != -1:
                url = data[begin:end].decode("ascii", errors="replace")
                if url.startswith("https://"):
                    hosts.add(urlsplit(url).hostname or "")
            start = data.find(MARKER, begin)
    return hosts


def test_claude_code_refreshes_its_sign_in_on_an_allowed_host(
    claude_binary: Path,
) -> None:
    """Found on 2.1.301: platform.claude.com, which the Claude proxy lets through."""
    hosts = _token_hosts(Path(os.path.realpath(claude_binary)))

    assert hosts, (
        "no TOKEN_URL found: Claude Code changed how it names its sign-in host"
    )
    assert hosts <= set(CLAUDE_HOSTS), (
        f"Claude Code signs in through hosts SurfSense does not allow: {hosts - set(CLAUDE_HOSTS)}"
    )
