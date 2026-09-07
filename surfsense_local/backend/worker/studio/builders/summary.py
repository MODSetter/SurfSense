from worker.studio.builders.types import Builder, Built, Source

MAX_TITLE = 200


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


summary = Builder(key="summary", prompt=prompt, build=build)
