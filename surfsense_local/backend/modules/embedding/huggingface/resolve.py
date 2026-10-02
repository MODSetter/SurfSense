"""One Hugging Face repo, opened: whether it can run here, and as what.

Reads its summary and security scan, its file list at that commit, and the few
small files that say how it embeds. No weights are downloaded.
"""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from typing import Any

import httpx

from modules.embedding.huggingface import hub
from modules.embedding.huggingface.pick import (
    TOKENIZER,
    NotRunnableError,
    PickedFiles,
    pick_files,
    scan_verdict,
)
from modules.embedding.huggingface.spec_from_repo import RepoConfig, spec_from_repo
from modules.embedding.spec import EmbedderSpec
from modules.llm.catalog.local.listed_file import ListedFile

_CONFIG_FILES = (
    "config.json",
    "1_Pooling/config.json",
    "modules.json",
    "config_sentence_transformers.json",
    "sentence_bert_config.json",
)
# Hugging Face keeps files under 10 MB out of LFS, so lists no sha256 for them.
_SMALL_FILE_BYTES = 10 * 1024 * 1024


@dataclass(frozen=True)
class Resolved:
    repo: str
    revision: str | None
    picked: PickedFiles | None
    spec: EmbedderSpec | None
    # Why it cannot be an embedder here; None when it can.
    reason: str | None
    gated: bool = False


async def resolve(repo: str) -> Resolved:
    async with hub.client() as client:
        info = await _json(
            client,
            f"/api/models/{repo}",
            {"securityStatus": "true", "expand[]": ["sha", "pipeline_tag", "gated"]},
        )
        revision = info["sha"]
        if info.get("gated"):
            return Resolved(
                repo,
                revision,
                None,
                None,
                "This repo needs an account to download.",
                gated=True,
            )
        tree = await _json(
            client, f"/api/models/{repo}/tree/{revision}", {"recursive": "true"}
        )
        listing = [
            ListedFile(
                row["path"], int(row.get("size", 0)), (row.get("lfs") or {}).get("oid")
            )
            for row in tree
            if row.get("type") == "file"
        ]
        listing = [
            await _hashed(client, repo, revision, f) if f.path == TOKENIZER else f
            for f in listing
        ]
        try:
            picked = pick_files(listing)
        except NotRunnableError as error:
            return Resolved(repo, revision, None, None, str(error))
        ours = {f.path for f in picked.all}
        if refused := scan_verdict(info.get("securityRepoStatus"), ours):
            return Resolved(repo, revision, None, None, refused)
        listed = {f.path for f in listing}
        configs = await asyncio.gather(
            *(
                _optional(client, f"/{repo}/resolve/{revision}/{path}")
                if path in listed
                else _none()
                for path in _CONFIG_FILES
            )
        )
    config, pooling, modules, sentence, bert = configs
    found = RepoConfig(
        config=config,
        pooling=pooling,
        modules=modules,
        prompts=(sentence or {}).get("prompts"),
        max_seq_length=(bert or {}).get("max_seq_length"),
    )
    spec = spec_from_repo(repo, revision, picked, found, info.get("pipeline_tag"))
    return Resolved(repo, revision, picked, spec, None)


async def _json(client: httpx.AsyncClient, path: str, params: dict[str, Any]) -> Any:
    reply = await client.get(path, params=params)
    reply.raise_for_status()
    return reply.json()


async def _hashed(
    client: httpx.AsyncClient, repo: str, revision: str, file: ListedFile
) -> ListedFile:
    """A small file without an LFS hash, hashed from its bytes at the pinned
    commit, so its download is checked like any other."""
    if file.sha256 or file.size_bytes > _SMALL_FILE_BYTES:
        return file
    reply = await client.get(f"/{repo}/resolve/{revision}/{file.path}")
    if reply.status_code != 200:
        return file
    return ListedFile(
        file.path, file.size_bytes, hashlib.sha256(reply.content).hexdigest()
    )


async def _optional(client: httpx.AsyncClient, path: str) -> Any:
    reply = await client.get(path)
    if reply.status_code != 200:
        return None
    try:
        return json.loads(reply.content)
    except ValueError:
        return None


async def _none() -> None:
    return None
