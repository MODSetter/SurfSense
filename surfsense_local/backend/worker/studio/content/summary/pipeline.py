from modules.llm import prompting
from modules.llm.profile import Tier
from modules.llm.resolution import ResolvedGeneration
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source

MAX_TITLE = 200


def render(
    model: ResolvedGeneration, sources: list[Source], user_prompt: str | None
) -> Built:
    return build(
        generate.run_model(model, prompt(model.tier, user_prompt), sources), sources
    )


def prompt(tier: Tier, user_prompt: str | None) -> str:
    return prompting.load(__package__, tier, focus=prompting.focus(user_prompt))


def build(raw: str, _sources: list[Source]) -> Built:
    # The markdown is the document body — no file, the summary is the artifact.
    markdown = raw.strip()
    return Built(title=_title(markdown), markdown=markdown)


def _title(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()[:MAX_TITLE] or "Summary"
    return "Summary"
