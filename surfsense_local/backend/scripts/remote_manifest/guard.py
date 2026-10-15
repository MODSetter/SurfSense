"""What a refresh loses or reads differently, so a bad upstream day never ships unread."""

from typing import Any

from modules.llm.catalog.remote.manifest.lookup import (
    RemoteClassification,
    RemoteLookup,
)
from modules.llm.catalog.remote.manifest.schema import SCHEMA_VERSION, RemoteManifest

__all__ = ["MAX_MODEL_LOSS", "reclassified", "shrinkage"]

# Providers retire models every week, so some loss is ordinary. A fifth of the
# catalogue at once is an upstream outage or a broken fetch, not a retirement.
MAX_MODEL_LOSS = 0.2

# What the app decides from a model's entry: the agent's window, whether images
# reach it, and whether it is offered for tool calls.
_READ = (
    ("reads_images", "reads images"),
    ("tool_call", "tool calls"),
    ("context_window", "window"),
)


def shrinkage(previous: dict[str, Any], proposed: dict[str, Any]) -> list[str]:
    """Why this refresh needs a person's say-so. Empty means it does not."""
    before = previous["providers"]
    after = proposed["providers"]
    problems = [
        f"provider {name} disappeared" for name in sorted(set(before) - set(after))
    ]

    count_before = sum(len(provider["models"]) for provider in before.values())
    count_after = sum(len(provider["models"]) for provider in after.values())
    if count_before and (count_before - count_after) / count_before > MAX_MODEL_LOSS:
        problems.append(f"models fell from {count_before} to {count_after}")
    return problems


def reclassified(previous: dict[str, Any], proposed: dict[str, Any]) -> list[str]:
    """Each model the previous manifest carried that the app would now read differently.

    Through a connection to its provider, then through any other connection,
    where every gateway carrying the id has a say and one dissenter unsettles it.
    """
    before, after = _lookup(previous), _lookup(proposed)
    lines = []
    for provider, served in sorted(previous["providers"].items()):
        for model_id in sorted(served["models"]):
            changes = _changes(
                before.classify(model_id, provider), after.classify(model_id, provider)
            )
            usable = (
                before.unusable_reason(model_id, provider),
                after.unusable_reason(model_id, provider),
            )
            if usable[0] != usable[1]:
                changes.append(f"{usable[0] or 'usable'} -> {usable[1] or 'usable'}")
            lines += [f"{provider} {model_id}: {change}" for change in changes]
    every_id = {
        m for provider in previous["providers"].values() for m in provider["models"]
    }
    for model_id in sorted(every_id):
        lines += [
            f"any connection {model_id}: {change}"
            for change in _changes(before.classify(model_id), after.classify(model_id))
        ]
    return lines


def _lookup(manifest: dict[str, Any]) -> RemoteLookup:
    return RemoteLookup(
        RemoteManifest.model_validate(
            {
                "schema_version": SCHEMA_VERSION,
                "source": "",
                "refreshed_at": "",
                "providers": manifest["providers"],
            }
        )
    )


def _changes(before: RemoteClassification, after: RemoteClassification) -> list[str]:
    if before.known != after.known:
        return ["known -> unknown" if before.known else "unknown -> known"]
    if before.supports is None or after.supports is None:
        return []
    return [
        f"{label} {old} -> {new}"
        for field, label in _READ
        if (old := getattr(before.supports, field))
        != (new := getattr(after.supports, field))
    ]
