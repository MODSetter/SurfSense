"""One repo, as its listing describes it: every file's name, size and hash.

Opening a repo costs this and nothing else, measured at under a second. It reads
no file: the header of the chosen build is read before it downloads, not to draw
a list. The repo's own summary names an architecture Hugging Face parsed from one
arbitrary file, so it is a hint for a moment, never the answer.
"""

import asyncio
from dataclasses import dataclass

import httpx

from modules.llm.catalog.local.engines.llamacpp.builds.in_repo import ListedFile

API = "https://huggingface.co/api/models"
TIMEOUT = httpx.Timeout(15.0, connect=10.0)
# What Hugging Face writes when it parsed a projector as the repo's model.
_PROJECTOR_HINTS = frozenset({"clip"})


@dataclass(frozen=True)
class RepoListing:
    repo: str
    revision: str
    pipeline_tag: str | None
    gated: bool
    architecture_hint: str
    files: tuple[ListedFile, ...]


async def read_listing(client: httpx.AsyncClient, repo: str) -> RepoListing:
    """The repo's summary and its file tree, fetched together."""
    info_reply, tree_reply = await asyncio.gather(
        client.get(
            f"{API}/{repo}",
            params={"expand[]": ["sha", "pipeline_tag", "gated", "gguf"]},
            timeout=TIMEOUT,
        ),
        client.get(
            f"{API}/{repo}/tree/main", params={"recursive": "true"}, timeout=TIMEOUT
        ),
    )
    info_reply.raise_for_status()
    tree_reply.raise_for_status()
    info = info_reply.json()
    gguf = info.get("gguf") if isinstance(info.get("gguf"), dict) else {}
    hint = str(gguf.get("architecture") or "")
    return RepoListing(
        repo=repo,
        revision=str(info.get("sha") or "main"),
        pipeline_tag=tag if isinstance(tag := info.get("pipeline_tag"), str) else None,
        gated=bool(info.get("gated")),
        architecture_hint="" if hint.lower() in _PROJECTOR_HINTS else hint,
        files=tuple(
            ListedFile(
                row["path"], int(row.get("size", 0)), (row.get("lfs") or {}).get("oid")
            )
            for row in tree_reply.json()
            if row.get("type") == "file"
        ),
    )
