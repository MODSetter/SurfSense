"""A render's first line: written into the tool's result, read back to show the step as the document it made."""

import re
from dataclasses import dataclass

TOOL_NAME = "render_document"

_READY = re.compile(r"Rendered artifact ([0-9]+), version ([0-9]+): (.+)")
_QUEUED = re.compile(r"Queued artifact ([0-9]+), version ([0-9]+): (.+)")


@dataclass(frozen=True)
class RenderedArtifact:
    """The ready version a render made, as the thread links to it."""

    id: int
    title: str
    version: int


def first_line(rendered: RenderedArtifact) -> str:
    """How a successful render's result starts; only a ready version gets it."""
    return f"Rendered artifact {_label(rendered)}"


def queued_line(rendered: RenderedArtifact) -> str:
    """How the result of a render still being made when the call answered starts."""
    return f"Queued artifact {_label(rendered)}"


def rendered_artifact(output: str) -> RenderedArtifact | None:
    """The version a render's result names on its first line, or None for any other result."""
    return _named(_READY, output)


def queued_artifact(output: str) -> RenderedArtifact | None:
    """The version a render left being made, or None for any other result."""
    return _named(_QUEUED, output)


def _named(line: re.Pattern[str], output: str) -> RenderedArtifact | None:
    match = line.fullmatch(output.split("\n", 1)[0])
    if match is None:
        return None
    return RenderedArtifact(id=int(match[1]), title=match[3], version=int(match[2]))


def _label(rendered: RenderedArtifact) -> str:
    title = " ".join(rendered.title.split())
    return f"{rendered.id}, version {rendered.version}: {title}"
