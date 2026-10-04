"""A render's first line: written into the tool's result, read back to show the step as the document it made."""

import re
from dataclasses import dataclass

TOOL_NAME = "render_document"

_LINE = re.compile(r"Rendered artifact ([0-9]+), version ([0-9]+): (.+)")


@dataclass(frozen=True)
class RenderedArtifact:
    """The ready version a render made, as the thread links to it."""

    id: int
    title: str
    version: int


def first_line(rendered: RenderedArtifact) -> str:
    """How a successful render's result starts; only a ready version gets it."""
    title = " ".join(rendered.title.split())
    return f"Rendered artifact {rendered.id}, version {rendered.version}: {title}"


def rendered_artifact(output: str) -> RenderedArtifact | None:
    """The version a render's result names on its first line, or None for any other result."""
    match = _LINE.fullmatch(output.split("\n", 1)[0])
    if match is None:
        return None
    return RenderedArtifact(id=int(match[1]), title=match[3], version=int(match[2]))
