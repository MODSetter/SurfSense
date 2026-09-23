"""One manifest entry from a repo at a commit and the headers read from it.

Pure: no network, so every rule here is a unit test over recorded input. It
pins every build whose quantization the preference order names, so a machine
that cannot run the default has a smaller build of the same model to step down
to, and it refuses to write a build it could not read completely.
"""

import math
from dataclasses import asdict
from typing import Any

from local_manifest.entries import Entry
from local_manifest.recorded import RepoAtRevision
from modules.llm.catalog.local.engines.llamacpp.builds.choice import PREFERENCE
from modules.llm.catalog.local.engines.llamacpp.builds.in_repo import Build, FileRole, builds_in
from modules.llm.catalog.local.engines.llamacpp.support import (
    PROJECTOR_KEYS,
    projector_fits_model,
    projector_reads_images,
    template_support,
)
from modules.llm.gguf import GgufHeader, to_shape

_TEMPLATE = "tokenizer.chat_template"
_SAMPLING_KEYS = ("temperature", "top_p", "top_k", "min_p")
_NOT_SHAPE = ("architecture", "context_length")


class UnreadableBuildError(Exception):
    """A build or file this refresh could not read completely. Nothing unknown is
    written, so nothing unknown can be recommended."""


def pinned_builds(snapshot: RepoAtRevision) -> list[Build]:
    """Every build in the preference order, each file with a hash and a size."""
    ranked = {label: i for i, label in enumerate(PREFERENCE)}
    builds = [
        b
        for b in builds_in(
            snapshot.listing, repo=snapshot.repo, revision=snapshot.revision
        )
        if b.quantization in ranked
    ]
    for build in builds:
        for file in build.files:
            if not file.sha256 or file.size_bytes <= 0:
                raise UnreadableBuildError(
                    f"{snapshot.repo}: {file.path} has no hash or size"
                )
    return builds


def entry_for(
    entry: Entry,
    snapshot: RepoAtRevision,
    builds: list[Build],
    weights: GgufHeader,
    projector: GgufHeader | None,
    validated: dict[str, str],
) -> dict[str, Any]:
    """The written entry. `weights` is the default build's own header; every
    quantization of a model shares its architecture fields."""
    meta = weights.metadata
    shape = to_shape(weights)
    template = meta.get(_TEMPLATE)
    tools, reasoning = template_support(template if isinstance(template, str) else None)

    projector_keys: dict[str, Any] = {}
    if projector is not None:
        if not projector_reads_images(projector.metadata):
            raise UnreadableBuildError(
                f"{snapshot.repo}: its projector does not read images"
            )
        if not projector_fits_model(projector.metadata, meta):
            raise UnreadableBuildError(
                f"{snapshot.repo}: its projector belongs to another model"
            )
        projector_keys = {
            k: projector.metadata[k] for k in PROJECTOR_KEYS if k in projector.metadata
        }

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
            "architecture": shape.architecture,
            "pipeline_tag": snapshot.pipeline_tag,
            "parameters_b": _parameters_b(weights),
        },
        "context": shape.context_length,
        "template": {
            "tools": tools,
            "reasoning": reasoning,
            "system_role": ("system" in template)
            if isinstance(template, str)
            else None,
        },
        "sampling": _sampling(snapshot, reasoning),
        "image": None,
        "shape": _shape_fields(shape),
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
                        **(
                            {"gguf": projector_keys}
                            if file.role is FileRole.PROJECTOR
                            else {}
                        ),
                    }
                    for file in build.files
                ],
                "run": {"args": []},
                "validated": {"llama_cpp": validated.get(build.weights.path)},
            }
            for build in builds
        ],
    }


def _parameters_b(header: GgufHeader) -> float | None:
    """Counted from the tensor table, never read off a name."""
    total = sum(math.prod(t.dims) for t in header.tensors)
    return round(total / 1e9, 2) if total else None


def _shape_fields(shape) -> dict[str, Any]:
    fields = {k: v for k, v in asdict(shape).items() if k not in _NOT_SHAPE}
    fields["sliding_window_layers"] = list(fields["sliding_window_layers"])
    fields["head_count_kv_layers"] = list(fields["head_count_kv_layers"])
    return fields


def _sampling(
    snapshot: RepoAtRevision, reasoning: bool | None
) -> dict[str, Any] | None:
    """The repo's own `params`, recorded with its origin, for a person to review."""
    params = snapshot.params or {}
    settings = {k: params[k] for k in _SAMPLING_KEYS if k in params}
    if not settings:
        return None
    mode = "thinking" if reasoning else "non_thinking"
    return {
        "origin": f"{snapshot.repo}@{snapshot.revision}/params",
        "thinking": None,
        "non_thinking": None,
        mode: settings,
    }
