from modules.llm.resolution import ResolvedGeneration
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source

MAX_TITLE = 200


def render(
    model: ResolvedGeneration, sources: list[Source], user_prompt: str | None
) -> Built:
    return build(
        generate.run_model(model, prompt(sources, user_prompt), sources), sources
    )


def prompt(sources: list[Source], user_prompt: str | None) -> str:
    focus = f"\n\nFocus especially on: {user_prompt}" if user_prompt else ""
    return (
        "Summarise the sources below in Markdown. Open with a one-line title as "
        "an H1 (`# ...`), then the key points as short sections. Stay faithful "
        "to the sources and add nothing they do not support." + focus
    )


def build(raw: str, _sources: list[Source]) -> Built:
    # The markdown is the document body — no file, the summary is the artifact.
    markdown = raw.strip()
    return Built(title=_title(markdown), markdown=markdown)


def _title(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()[:MAX_TITLE] or "Summary"
    return "Summary"
