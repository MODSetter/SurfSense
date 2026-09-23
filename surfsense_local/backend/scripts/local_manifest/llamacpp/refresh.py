"""Read one chat model's repo at its commit and write its entry."""

from typing import Any

import httpx

from local_manifest.entry import Entry
from local_manifest.hub import header, repo_at_revision
from local_manifest.llamacpp.assemble import entry_for, pinned_builds
from local_manifest.unreadable import UnreadableBuildError
from modules.llm.catalog.local.engines.llamacpp.builds.choice import default_build

# weights path -> the llama.cpp build a person downloaded, chatted with and
# confirmed citations resolve on
VALIDATED: dict[str, str] = {}


async def refresh(client: httpx.AsyncClient, entry: Entry) -> dict[str, Any]:
    snapshot = await repo_at_revision(client, entry.repo)
    builds = pinned_builds(snapshot)
    chosen = default_build(builds)
    if chosen is None:
        raise UnreadableBuildError(f"{entry.repo}: no build in the preference order")
    weights = await header(client, entry.repo, snapshot.revision, chosen.weights.path)
    projector = (
        await header(client, entry.repo, snapshot.revision, chosen.projector.path)
        if chosen.projector
        else None
    )
    print(
        f"  {entry.name:22s} {snapshot.revision[:8]}  {len(builds):2d} builds, "
        f"default {chosen.quantization}" + (", reads images" if projector else "")
    )
    return entry_for(entry, snapshot, builds, weights, projector, VALIDATED)
