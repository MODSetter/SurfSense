"""Read one image model's repo at its commit and write its entry."""

from typing import Any

import httpx

from local_manifest.hub import header, repo_at_revision
from local_manifest.sdcpp.assemble import entry_for, pinned_builds
from local_manifest.sdcpp.entry import ImageEntry
from local_manifest.unreadable import UnreadableBuildError
from modules.llm.catalog.local.engines.sdcpp.builds.choice import default_build

# weights path -> the sd.cpp build a person generated an image with
VALIDATED: dict[str, str] = {}


async def refresh(client: httpx.AsyncClient, entry: ImageEntry) -> dict[str, Any]:
    snapshot = await repo_at_revision(client, entry.repo)
    builds = pinned_builds(snapshot)
    chosen = default_build(builds)
    if chosen is None:
        raise UnreadableBuildError(f"{entry.repo}: no build in sd.cpp's order")
    weights = await header(client, entry.repo, snapshot.revision, chosen.weights.path)
    written = entry_for(entry, snapshot, builds, weights, VALIDATED)
    print(
        f"  {entry.name:22s} {snapshot.revision[:8]}  {len(builds):2d} builds, "
        f"default {chosen.quantization}, {written['evidence']['architecture']}"
    )
    return written
