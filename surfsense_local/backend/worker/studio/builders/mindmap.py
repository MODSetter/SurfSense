from typing import Any

from worker.studio.builders.types import Builder, Built, Source
from worker.studio.builders.util import as_list, as_text, parse_json

_SCHEMA = (
    'Return only JSON, no prose: {"title": str, "nodes": '
    '[{"label": str, "children": [{"label": str, "children": [...]}]}]}.'
)


def prompt(_sources: list[Source], user_prompt: str | None) -> str:
    focus = f" Centre it on: {user_prompt}." if user_prompt else ""
    return (
        "Organise the sources below into a mind map — a shallow tree of short "
        "labels, using their facts only." + focus + " " + _SCHEMA
    )


def build(raw: str, _sources: list[Source]) -> Built:
    # A markdown outline: an H1 root over nested bullets, which Markmap reads
    # directly on the client and which stays readable as plain text.
    spec = parse_json(raw)
    title = as_text(spec.get("title")) or "Mind map"
    lines = [f"# {title}"]
    _render(as_list(spec.get("nodes")), lines, depth=0)
    return Built(title=title, markdown="\n".join(lines))


def _render(nodes: list[Any], lines: list[str], depth: int) -> None:
    for node in nodes:
        if not isinstance(node, dict):
            continue
        label = as_text(node.get("label"))
        if not label:
            continue
        lines.append(f"{'  ' * depth}- {label}")
        _render(as_list(node.get("children")), lines, depth + 1)


mindmap = Builder(key="mindmap", prompt=prompt, build=build)
