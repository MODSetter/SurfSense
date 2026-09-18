from typing import Any

from modules.llm import prompting
from modules.llm.profile import Tier
from modules.llm.resolution import ResolvedGeneration
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source
from worker.studio.shared.text import as_list, as_text, parse_json

# The frontier prompt leaves the count to the material, so the ceiling is kept here.
BRANCHES = 10


def render(
    model: ResolvedGeneration, sources: list[Source], user_prompt: str | None
) -> Built:
    return build(
        generate.run_model(model, prompt(model.tier, user_prompt), sources), sources
    )


def prompt(tier: Tier, user_prompt: str | None) -> str:
    return prompting.load(
        __package__, tier, focus=prompting.focus(user_prompt), ceiling=BRANCHES
    )


def build(raw: str, _sources: list[Source]) -> Built:
    # A markdown outline: an H1 root over nested bullets, which Markmap reads
    # directly on the client and which stays readable as plain text.
    spec = parse_json(raw)
    title = as_text(spec.get("title")) or "Mind map"
    lines = [f"# {title}"]
    _render(as_list(spec.get("nodes"))[:BRANCHES], lines, depth=0)
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
