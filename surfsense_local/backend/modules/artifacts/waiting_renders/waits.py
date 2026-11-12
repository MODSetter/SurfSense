"""The pictures a pending document waits for, kept in its metadata until it is queued."""

from typing import Any

from modules.artifacts.drawn_images.names import image_name

KEY = "waits_for"


def waits_for(metadata: dict[str, Any] | None) -> tuple[int, ...]:
    return tuple(int(i) for i in (metadata or {}).get(KEY) or ())


def waiting_sentence(artifact_ids: tuple[int, ...]) -> str:
    """How the render's call answers: what it waits for, and not to render again."""
    names = [image_name(i) for i in artifact_ids]
    drawn = (
        f"{names[0]} is drawn"
        if len(names) == 1
        else f"{', '.join(names[:-1])} and {names[-1]} are drawn"
    )
    return (
        f"It renders once {drawn}, and appears in Studio then: tell the user so, "
        "and do not render it again."
    )
