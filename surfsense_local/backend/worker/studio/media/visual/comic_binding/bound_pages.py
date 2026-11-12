"""The agent's comic: the pictures it drew, read from Studio's store and bound as it asked."""

from dataclasses import dataclass
from pathlib import Path

from modules.artifacts.comic.binding_recipe import ComicBinding
from worker.studio.media.visual.comic_binding.bind import BoundPage, bind
from worker.studio.shared.artifact import Built
from worker.studio.shared.text import slug


@dataclass(frozen=True)
class KeptPage:
    picture: Path
    # The words the page was drawn from: its panels and bubbles, as Studio's plan holds them.
    drawn_from: str


def render(title: str, binding: ComicBinding, pages: list[KeptPage]) -> Built:
    """`pages` are the binding's pages' files and prompts, in its order."""
    pdf = bind(
        title,
        [
            BoundPage(kept.picture.read_bytes(), page.lines)
            for kept, page in zip(pages, binding.pages, strict=True)
        ],
        layout=binding.layout,
        direction=binding.direction,
    )
    return Built(
        title=title,
        markdown=_searchable(title, binding, pages),
        primary=pdf,
        primary_mime="application/pdf",
        primary_filename=f"{slug(title, 'comic')}.pdf",
    )


def _searchable(title: str, binding: ComicBinding, pages: list[KeptPage]) -> str:
    """Each page's prompt and lines, a line every page repeats (its style, its
    cast) kept the first time only, so it does not outweigh what the pages say."""
    seen: set[str] = set()
    body = [f"# {title}"]
    for number, (kept, page) in enumerate(zip(pages, binding.pages, strict=True), 1):
        body.append(f"\n## Page {number}\n")
        for line in kept.drawn_from.splitlines():
            line = line.strip()
            if line and line not in seen:
                seen.add(line)
                body.append(line)
        body += [f"- {line}" for line in page.lines]
    return "\n".join(body)
