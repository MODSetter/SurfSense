"""One image model's manifest entry from its repo at a commit and one header.

Pure, like the llama.cpp assembly: every rule is a unit test over recorded input.
"""

import math
from typing import Any

from local_manifest.recorded import RepoAtRevision
from local_manifest.sdcpp.entry import ImageEntry
from local_manifest.unreadable import UnreadableBuildError
from modules.llm.catalog.local.build import Build
from modules.llm.catalog.local.engines.sdcpp.builds.choice import PREFERENCE
from modules.llm.catalog.local.engines.sdcpp.builds.in_repo import builds_in
from modules.llm.catalog.local.engines.sdcpp.evidence import diffusion_architecture
from modules.llm.gguf import GgufHeader


def pinned_builds(snapshot: RepoAtRevision) -> list[Build]:
    """Every build in sd.cpp's order, each with a hash and a size."""
    builds = [
        b
        for b in builds_in(
            snapshot.listing, repo=snapshot.repo, revision=snapshot.revision
        )
        if b.quantization in PREFERENCE
    ]
    for build in builds:
        for file in build.files:
            if not file.sha256 or file.size_bytes <= 0:
                raise UnreadableBuildError(
                    f"{snapshot.repo}: {file.path} has no hash or size"
                )
    return builds


def entry_for(
    entry: ImageEntry,
    snapshot: RepoAtRevision,
    builds: list[Build],
    weights: GgufHeader,
    validated: dict[str, str],
) -> dict[str, Any]:
    """The written entry. `weights` is the default build's own header."""
    architecture = diffusion_architecture(weights.tensors)
    if architecture is None:
        raise UnreadableBuildError(
            f"{snapshot.repo}: its tensors name no model sd.cpp is known to run"
        )
    total = sum(math.prod(t.dims) for t in weights.tensors)
    return {
        "id": entry.id,
        "name": entry.name,
        "family": entry.family,
        "publisher": entry.publisher,
        "description": entry.description,
        "license": entry.license,
        "source_repo": entry.source_repo,
        "aliases": list(entry.aliases),
        "evidence": {
            "architecture": architecture,
            "pipeline_tag": snapshot.pipeline_tag,
            "parameters_b": round(total / 1e9, 2) or None,
        },
        "image": dict(entry.image),
        "builds": [
            {
                "quantization": build.quantization,
                "files": [
                    {
                        "role": file.role.value,
                        "repo": file.repo,
                        "upstream_repo": entry.upstream_repo,
                        "revision": file.revision,
                        "path": file.path,
                        "size_bytes": file.size_bytes,
                        "sha256": file.sha256,
                    }
                    for file in build.files
                ],
                "run": {"args": list(entry.run_args)},
                "validated": {"sd_cpp": validated.get(build.weights.path)},
            }
            for build in builds
        ],
    }
