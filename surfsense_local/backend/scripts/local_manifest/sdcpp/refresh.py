"""Read one image model's repos at their commits and write its entry."""

from typing import Any

import httpx

from local_manifest.hub import header, repo_at_revision
from local_manifest.sdcpp.assemble import entry_for, pinned_builds
from local_manifest.sdcpp.entry import ImageEntry

# weights path -> the sd.cpp build a person generated an image with
VALIDATED: dict[str, str] = {}


async def refresh(client: httpx.AsyncClient, entry: ImageEntry) -> dict[str, Any]:
    snapshot = await repo_at_revision(client, entry.repo)
    companions = {
        repo: await repo_at_revision(client, repo)
        for repo in dict.fromkeys(c.repo for c in entry.companions)
    }
    builds = pinned_builds(entry, snapshot, companions)
    chosen = builds[0]
    weights = await header(client, entry.repo, snapshot.revision, chosen.weights.path)
    written = entry_for(entry, snapshot, builds, weights, VALIDATED)
    print(
        f"  {entry.name:22s} {snapshot.revision[:8]}  {len(builds):2d} builds, "
        f"default {chosen.quantization}, {written['evidence']['architecture']}, "
        f"{len(entry.companions)} companions"
    )
    return written
