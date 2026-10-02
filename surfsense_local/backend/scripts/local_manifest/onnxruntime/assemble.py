"""One embedding model's manifest entry from its repo at a commit.

Pure, like the other engines' assemblies: every rule is a unit test over
recorded input.
"""

from typing import Any

from local_manifest.onnxruntime.entry import EmbeddingEntry
from local_manifest.recorded import RepoAtRevision
from local_manifest.unreadable import UnreadableBuildError
from modules.llm.catalog.local.build import Build, BuildFile, FileRole


def pinned_builds(entry: EmbeddingEntry, snapshot: RepoAtRevision) -> list[Build]:
    """Each build's weights with the repo's tokenizer, every file hashed."""
    listed = {f.path: f for f in snapshot.listing}
    builds = []
    for label, weights in entry.builds:
        files = []
        for role, path in (
            (FileRole.WEIGHTS, weights),
            (FileRole.TOKENIZER, entry.tokenizer),
        ):
            found = listed.get(path)
            if found is None or not found.sha256 or found.size_bytes <= 0:
                raise UnreadableBuildError(
                    f"{snapshot.repo}: {path} has no hash or size"
                )
            files.append(
                BuildFile(
                    role,
                    path,
                    found.size_bytes,
                    found.sha256,
                    snapshot.repo,
                    snapshot.revision,
                )
            )
        builds.append(Build(label, tuple(files)))
    return builds


def entry_for(
    entry: EmbeddingEntry,
    snapshot: RepoAtRevision,
    builds: list[Build],
    architecture: str,
    validated: dict[str, str] | None = None,
) -> dict[str, Any]:
    """The written entry. `architecture` is the repo config's `model_type`."""
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
        "evidence": {
            "architecture": architecture,
            "pipeline_tag": snapshot.pipeline_tag,
        },
        "embedding": dict(entry.embedding),
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
                "validated": {"onnxruntime": validated.get(build.weights.path)},
            }
            for build in builds
        ],
    }
