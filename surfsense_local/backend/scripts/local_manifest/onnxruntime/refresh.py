"""Read one embedding model's repo at its commit and write its entry."""

import hashlib
from dataclasses import replace
from typing import Any

import httpx

from local_manifest.hub import RESOLVE, repo_at_revision
from local_manifest.onnxruntime.assemble import entry_for, pinned_builds
from local_manifest.onnxruntime.entry import EmbeddingEntry
from local_manifest.unreadable import UnreadableBuildError

# weights path -> the onnxruntime a person ran the retrieval eval with
VALIDATED: dict[str, str] = {
    "model_optimized.onnx": "1.29.0",
    "onnx/model.onnx": "1.29.0",
    "onnx/model_int8.onnx": "1.29.0",
}


# A file kept in git rather than LFS lists no sha256, so it is hashed here: a
# tokenizer is a few MB, and a pinned file must be checkable on download.
_HASHED_HERE_UP_TO = 64 * 1024 * 1024


async def refresh(client: httpx.AsyncClient, entry: EmbeddingEntry) -> dict[str, Any]:
    snapshot = await repo_at_revision(client, entry.repo)
    snapshot = await _hash_small_files(client, snapshot, entry)
    builds = pinned_builds(entry, snapshot)
    reply = await client.get(
        RESOLVE.format(repo=entry.repo, revision=snapshot.revision, path="config.json")
    )
    reply.raise_for_status()
    architecture = reply.json().get("model_type")
    if not architecture:
        raise UnreadableBuildError(f"{entry.repo}: config.json names no model_type")
    written = entry_for(entry, snapshot, builds, architecture, VALIDATED)
    print(
        f"  {entry.name:34s} {snapshot.revision[:8]}  {len(builds):2d} builds, "
        f"default {builds[0].quantization}, {architecture}"
    )
    return written


async def _hash_small_files(client, snapshot, entry: EmbeddingEntry):
    wanted = {path for _, path in entry.builds} | {entry.tokenizer}
    listing = []
    for listed in snapshot.listing:
        if listed.path in wanted and not listed.sha256:
            if listed.size_bytes > _HASHED_HERE_UP_TO:
                raise UnreadableBuildError(f"{entry.repo}: {listed.path} is unhashed")
            reply = await client.get(
                RESOLVE.format(
                    repo=entry.repo, revision=snapshot.revision, path=listed.path
                )
            )
            reply.raise_for_status()
            listed = replace(listed, sha256=hashlib.sha256(reply.content).hexdigest())
        listing.append(listed)
    return replace(snapshot, listing=tuple(listing))
