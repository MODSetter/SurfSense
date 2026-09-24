"""One audio model's manifest entry from its repo at a commit and its family.

Pure, like the other engines' assemblies: every rule is a unit test over
recorded input.
"""

from typing import Any

from local_manifest.audiocpp.entry import AudioEntry
from local_manifest.recorded import RepoAtRevision
from local_manifest.unreadable import UnreadableBuildError
from modules.llm.catalog.local.build import Build
from modules.llm.catalog.local.engines.audiocpp.builds.in_repo import builds_in


def pinned_builds(entry: AudioEntry, snapshot: RepoAtRevision) -> list[Build]:
    """The entry's builds in its order, each with a hash and a size."""
    found = {
        b.quantization: b
        for b in builds_in(
            snapshot.listing,
            entry.folder,
            repo=snapshot.repo,
            revision=snapshot.revision,
        )
    }
    builds = []
    for label in entry.builds:
        build = found.get(label)
        if build is None:
            raise UnreadableBuildError(f"{snapshot.repo}/{entry.folder}: no {label}")
        for file in build.files:
            if not file.sha256 or file.size_bytes <= 0:
                raise UnreadableBuildError(
                    f"{snapshot.repo}: {file.path} has no hash or size"
                )
        builds.append(build)
    return builds


def entry_for(
    entry: AudioEntry,
    snapshot: RepoAtRevision,
    builds: list[Build],
    family: str,
    validated: dict[str, str] | None = None,
) -> dict[str, Any]:
    """The written entry. `family` is the default build's, read from its header."""
    validated = validated or {}
    return {
        "id": entry.id,
        "name": entry.name,
        "family": entry.family,
        "publisher": entry.publisher,
        "description": entry.description,
        "license": entry.license,
        "source_repo": entry.source_repo,
        "aliases": list(entry.aliases),
        "evidence": {"architecture": family, "pipeline_tag": snapshot.pipeline_tag},
        "audio": dict(entry.audio),
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
                "validated": {"audio_cpp": validated.get(build.weights.path)},
            }
            for build in builds
        ],
    }
