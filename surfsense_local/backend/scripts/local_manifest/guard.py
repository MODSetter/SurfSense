"""What a refresh drops, so nothing leaves the manifest unread."""

from typing import Any


def losses(previous: dict[str, Any], proposed: dict[str, Any]) -> list[str]:
    """Models and builds the new file no longer carries. Empty means none."""
    after = {m["id"]: m for m in proposed["models"]}
    problems = []
    for model in previous.get("models", []):
        kept = after.get(model["id"])
        if kept is None:
            problems.append(f"model {model['id']} disappeared")
            continue
        labels = {b["quantization"] for b in kept["builds"]}
        problems += [
            f"{model['id']} lost {b['quantization']}"
            for b in model["builds"]
            if b["quantization"] not in labels
        ]
    return problems
