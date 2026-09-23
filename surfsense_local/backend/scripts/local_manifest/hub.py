"""What the refresh reads from Hugging Face. Authoring time only.

Everything is pinned to one commit: the revision is read first and every later
request names it, so the listing, the hashes and the headers describe the same
files.
"""

import json

import httpx

from local_manifest.recorded import RepoAtRevision
from modules.llm.catalog.local.engines.llamacpp.builds.in_repo import ListedFile
from modules.llm.gguf import GgufHeader, header_from_url

API = "https://huggingface.co/api/models"
RESOLVE = "https://huggingface.co/{repo}/resolve/{revision}/{path}"


async def repo_at_revision(client: httpx.AsyncClient, repo: str) -> RepoAtRevision:
    info = (
        await client.get(f"{API}/{repo}", params={"expand[]": ["sha", "pipeline_tag"]})
    ).json()
    revision = info["sha"]
    reply = await client.get(
        f"{API}/{repo}/tree/{revision}", params={"recursive": "true"}
    )
    reply.raise_for_status()
    listing = tuple(
        ListedFile(
            row["path"], int(row.get("size", 0)), (row.get("lfs") or {}).get("oid")
        )
        for row in reply.json()
        if row.get("type") == "file"
    )
    params = None
    reply = await client.get(
        RESOLVE.format(repo=repo, revision=revision, path="params")
    )
    if reply.status_code == 200:
        try:
            params = json.loads(reply.text)
        except ValueError:
            params = None
    return RepoAtRevision(repo, revision, info.get("pipeline_tag"), listing, params)


async def header(
    client: httpx.AsyncClient, repo: str, revision: str, path: str
) -> GgufHeader:
    return await header_from_url(
        client, RESOLVE.format(repo=repo, revision=revision, path=path)
    )
