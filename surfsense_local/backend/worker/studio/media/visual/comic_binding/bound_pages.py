"""The agent's comic: the pictures it drew, read from Studio's store and bound as it asked."""

from pathlib import Path

from modules.artifacts.comic.binding_recipe import ComicBinding
from worker.studio.media.visual.comic_binding.bind import BoundPage, bind
from worker.studio.shared.artifact import Built
from worker.studio.shared.text import slug


def render(title: str, binding: ComicBinding, pictures: list[Path]) -> Built:
    """`pictures` are the pages' files, in the binding's order."""
    pdf = bind(
        title,
        [
            BoundPage(path.read_bytes(), page.lines)
            for path, page in zip(pictures, binding.pages, strict=True)
        ],
        layout=binding.layout,
        direction=binding.direction,
    )
    body = [f"# {title}"]
    for number, page in enumerate(binding.pages, start=1):
        body.append(f"\n## Page {number}\n")
        body += [f"- {line}" for line in page.lines]
    return Built(
        title=title,
        markdown="\n".join(body),
        primary=pdf,
        primary_mime="application/pdf",
        primary_filename=f"{slug(title, 'comic')}.pdf",
    )
