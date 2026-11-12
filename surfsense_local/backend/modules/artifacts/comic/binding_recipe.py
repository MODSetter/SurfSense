"""How the agent's comic is made: the pictures it drew, in reading order, bound as it asked.

Kept so Regenerate binds the same pages again, and a later version can change one.
"""

from dataclasses import dataclass
from typing import Any, cast

from modules.artifacts.comic.reading import DIRECTIONS, LAYOUTS, Direction, Layout
from modules.artifacts.studio_documents.recipe import RECIPE_KEY

COMIC_BOUND = "comic_bound"


@dataclass(frozen=True)
class ComicPage:
    # The picture's artifact id.
    picture: int
    lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class ComicBinding:
    pages: tuple[ComicPage, ...]
    layout: Layout
    direction: Direction


def comic_bound(binding: ComicBinding) -> dict[str, Any]:
    return {
        "kind": COMIC_BOUND,
        "pages": [
            {"picture": page.picture, "lines": list(page.lines)}
            for page in binding.pages
        ],
        "layout": binding.layout,
        "direction": binding.direction,
    }


def comic_binding_of(metadata: dict[str, Any] | None) -> ComicBinding | None:
    recipe = (metadata or {}).get(RECIPE_KEY)
    if not isinstance(recipe, dict) or recipe.get("kind") != COMIC_BOUND:
        return None
    layout = recipe.get("layout")
    direction = recipe.get("direction")
    return ComicBinding(
        pages=tuple(
            ComicPage(int(page["picture"]), tuple(page.get("lines") or ()))
            for page in recipe.get("pages") or ()
        ),
        layout=cast(Layout, layout) if layout in LAYOUTS else "pages",
        direction=cast(Direction, direction) if direction in DIRECTIONS else "ltr",
    )
