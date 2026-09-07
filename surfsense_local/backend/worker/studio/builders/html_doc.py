import html

from worker.studio.builders.types import Builder, Built, Source
from worker.studio.builders.util import as_list, as_text, parse_json, slug

MIME = "text/html"

_SCHEMA = (
    'Return only JSON, no prose: {"title": str, "sections": '
    '[{"heading": str, "paragraphs": [str]}]}.'
)


def prompt(_sources: list[Source], user_prompt: str | None) -> str:
    focus = f" Emphasise: {user_prompt}." if user_prompt else ""
    return (
        "Write a structured web page from the sources below, using their facts "
        "only." + focus + " " + _SCHEMA
    )


def build(raw: str, _sources: list[Source]) -> Built:
    spec = parse_json(raw)
    title = as_text(spec.get("title")) or "Page"

    # The model supplies text, never markup: every value is escaped into a fixed
    # template, so a generated page cannot carry a script.
    body: list[str] = [f"<h1>{html.escape(title)}</h1>"]
    lines = [f"# {title}"]
    for section in as_list(spec.get("sections")):
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


html_doc = Builder(key="html", prompt=prompt, build=build)
