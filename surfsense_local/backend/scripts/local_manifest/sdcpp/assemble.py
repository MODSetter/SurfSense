"""One image model's manifest entry from its repos at their commits and one header.

Pure, like the llama.cpp assembly: every rule is a unit test over recorded input.
"""

import math
from collections.abc import Mapping
from typing import Any

from local_manifest.recorded import RepoAtRevision
from local_manifest.sdcpp.entry import Companion, ImageEntry, VideoEntry
from local_manifest.unreadable import UnreadableBuildError
from modules.llm.catalog.local.build import Build, BuildFile, FileRole
from modules.llm.catalog.local.engines.sdcpp.builds.in_repo import builds_in
from modules.llm.catalog.local.engines.sdcpp.evidence import diffusion_architecture
from modules.llm.gguf import GgufHeader


def pinned_builds(
    entry: ImageEntry,
    snapshot: RepoAtRevision,
    companions: Mapping[str, RepoAtRevision] | None = None,
) -> list[Build]:
    """The builds the entry names, in its order, each with its companions and
    every file with a hash and a size."""
    in_repo = {
        b.quantization: b
        for b in builds_in(
            snapshot.listing, repo=snapshot.repo, revision=snapshot.revision
        )
    }
    shared = tuple(_companion(c, (companions or {})[c.repo]) for c in entry.companions)
    builds = []
    for label in entry.builds:
        build = in_repo.get(label)
        if build is None:
            raise UnreadableBuildError(f"{snapshot.repo}: no {label} build")
        builds.append(Build(label, build.files + shared))
    for build in builds:
        for file in build.files:
            if not file.sha256 or file.size_bytes <= 0:
                raise UnreadableBuildError(
                    f"{file.repo}: {file.path} has no hash or size"
                )
    return builds


def _companion(companion: Companion, snapshot: RepoAtRevision) -> BuildFile:
    listed = next((f for f in snapshot.listing if f.path == companion.path), None)
    if listed is None:
        raise UnreadableBuildError(
            f"{snapshot.repo}: no {companion.path} at {snapshot.revision[:8]}"
        )
    return BuildFile(
        FileRole(companion.role),
        listed.path,
        listed.size_bytes,
        listed.sha256,
        snapshot.repo,
        snapshot.revision,
    )


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
    upstream = {(c.repo, c.path): c.upstream_repo for c in entry.companions}
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
        **(
            {"video": dict(entry.video)}
            if isinstance(entry, VideoEntry)
            else {"image": dict(entry.image)}
        ),
        "builds": [
            {
                "quantization": build.quantization,
                "files": [
                    {
                        "role": file.role.value,
                        "repo": file.repo,
                        "upstream_repo": upstream.get(
                            (file.repo, file.path), entry.upstream_repo
                        ),
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
