import html

from modules.llm import prompting
from modules.llm.profile import Tier
from modules.llm.resolution import ResolvedGeneration
from worker.studio.shared import generate
from worker.studio.shared.artifact import Built, Source
from worker.studio.shared.text import as_list, as_text, parse_json, slug

MIME = "text/html"
# The frontier prompt leaves the count to the material, so the ceiling is kept here.
SECTIONS = 10


def render(
    model: ResolvedGeneration, sources: list[Source], user_prompt: str | None
) -> Built:
    return build(
        generate.run_model(model, prompt(model.tier, user_prompt), sources), sources
    )


def prompt(tier: Tier, user_prompt: str | None) -> str:
    return prompting.load(
        __package__, tier, focus=prompting.focus(user_prompt), ceiling=SECTIONS
    )


def build(raw: str, _sources: list[Source]) -> Built:
    spec = parse_json(raw)
    title = as_text(spec.get("title")) or "Page"

    # The model supplies text, never markup: every value is escaped into a fixed
    # template, so a generated page cannot carry a script.
    body: list[str] = [f"<h1>{html.escape(title)}</h1>"]
    lines = [f"# {title}"]
    for section in as_list(spec.get("sections"))[:SECTIONS]:
        if not isinstance(section, dict):
            continue
        heading = as_text(section.get("heading"))
        if heading:
            body.append(f"<h2>{html.escape(heading)}</h2>")
            lines.append(f"\n## {heading}")
        for paragraph in as_list(section.get("paragraphs")):
            text = as_text(paragraph)
            if text:
                body.append(f"<p>{html.escape(text)}</p>")
                lines.append(text)

    page = (
        '<!doctype html>\n<html lang="en">\n<head>\n'
        f'<meta charset="utf-8">\n<title>{html.escape(title)}</title>\n'
        "</head>\n<body>\n" + "\n".join(body) + "\n</body>\n</html>\n"
    )
    return Built(
        title=title,
        markdown="\n".join(lines),
        primary=page.encode("utf-8"),
        primary_mime=MIME,
        primary_filename=f"{slug(title, 'page')}.html",
    )
