import html
import textwrap

from worker.studio.artifact import Built, Source
from worker.studio.builder import Builder
from worker.studio.text import as_list, as_text, parse_json, slug

MIME = "image/svg+xml"
WIDTH = 1200
CARD_HEIGHT = 190
_SCHEMA = (
    'Return only JSON, no prose: {"title": str, "summary": str, "sections": '
    '[{"label": str, "value": str, "detail": str}]}. Use at most 6 sections. '
    "Keep every value factual and grounded in the supplied sources."
)


def prompt(_sources: list[Source], user_prompt: str | None) -> str:
    focus = f" Emphasise: {user_prompt}." if user_prompt else ""
    return (
        "Create the structured content for a concise factual infographic from "
        f"the sources below.{focus} {_SCHEMA}"
    )


def _lines(value: str, width: int, maximum: int) -> list[str]:
    return textwrap.wrap(value, width=width, break_long_words=False)[:maximum]


def _text(x: int, y: int, value: str, css: str) -> str:
    return (
        f'<text x="{x}" y="{y}" class="{css}">'
        f"{html.escape(value)}</text>"
    )


def build(raw: str, _sources: list[Source]) -> Built:
    spec = parse_json(raw)
    title = as_text(spec.get("title")) or "Infographic"
    summary = as_text(spec.get("summary"))
    sections = [
        section
        for section in as_list(spec.get("sections"))[:6]
        if isinstance(section, dict)
    ]
    rows = max(1, (len(sections) + 1) // 2)
    height = 270 + rows * (CARD_HEIGHT + 24)

    nodes = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {WIDTH} {height}" '
        'role="img">',
        f"<title>{html.escape(title)}</title>",
        "<style>",
        ".bg{fill:#f8fafc}.card{fill:#fff;stroke:#cbd5e1;stroke-width:2}"
        ".title{font:700 42px system-ui;fill:#0f172a}"
        ".summary{font:400 21px system-ui;fill:#475569}"
        ".label{font:600 18px system-ui;fill:#475569}"
        ".value{font:700 34px system-ui;fill:#0f766e}"
        ".detail{font:400 17px system-ui;fill:#334155}",
        "</style>",
        f'<rect class="bg" width="{WIDTH}" height="{height}"/>',
        _text(64, 72, title[:80], "title"),
    ]
    for index, line in enumerate(_lines(summary, 88, 2)):
        nodes.append(_text(64, 116 + index * 30, line, "summary"))

    markdown = [f"# {title}"]
    if summary:
        markdown.append(summary)
    for index, section in enumerate(sections):
        column = index % 2
        row = index // 2
        x = 64 + column * 548
        y = 190 + row * (CARD_HEIGHT + 24)
        label = as_text(section.get("label"))[:60]
        value = as_text(section.get("value"))[:80]
        detail = as_text(section.get("detail"))
        nodes.append(
            f'<rect class="card" x="{x}" y="{y}" width="524" '
            f'height="{CARD_HEIGHT}" rx="18"/>'
        )
        nodes.append(_text(x + 28, y + 40, label, "label"))
        nodes.append(_text(x + 28, y + 88, value, "value"))
        for line_index, line in enumerate(_lines(detail, 54, 3)):
            nodes.append(
                _text(x + 28, y + 126 + line_index * 23, line, "detail")
            )
        markdown.append(f"\n## {label}\n\n**{value}**\n\n{detail}")
    nodes.append("</svg>")

    # ponytail: SVG is the deterministic primary; add a packaged rasterizer
    # only if downstream consumers prove they need PNG previews.
    return Built(
        title=title,
        markdown="\n".join(markdown),
        primary="\n".join(nodes).encode(),
        primary_mime=MIME,
        primary_filename=f"{slug(title, 'infographic')}.svg",
    )


infographic = Builder(key="infographic", prompt=prompt, build=build)
