"""The comic the chat model plans from the sources: its look, its cast, and every page's panels."""

from dataclasses import dataclass

from modules.artifacts.comic.kinds import Kind
from modules.llm import prompting
from modules.llm.profile import Tier
from worker.studio.shared.text import as_list, as_text, parse_json

_BUBBLES = (
    "Give each panel its lines: one short line a bubble, at most about eight words, "
    'two or three a panel, each as "NAME: words", or "Caption: words" for narration. '
    "Write every line word for word."
)
_UNDER = (
    "Give each picture one panel. Its lines are the text set under the picture, never "
    "in it: a picture book's words, or a storyboard shot's number, camera and movement."
)


@dataclass(frozen=True)
class Panel:
    where: str
    shows: str
    lines: tuple[str, ...]


@dataclass(frozen=True)
class Plan:
    title: str
    style: str
    characters: str
    pages: tuple[tuple[Panel, ...], ...]


def prompt(tier: Tier, user_prompt: str | None, kind: Kind, count: int) -> str:
    return prompting.load(
        __package__,
        tier,
        focus=prompting.focus(user_prompt),
        kind=kind.name,
        picture=kind.picture,
        count=count,
        unit=kind.unit.lower(),
        lettering=_BUBBLES if kind.bubbles else _UNDER,
    )


def parse(raw: str, untitled: str, count: int) -> Plan:
    """The plan, cut to the pages asked for: each one drawn is billed or takes minutes.

    One short of them is refused, so it is asked for again before any is drawn.
    """
    spec = parse_json(raw)
    pages = tuple(
        panels
        for page in as_list(spec.get("pages"))
        if isinstance(page, dict) and (panels := _panels(page))
    )[:count]
    if len(pages) < count:
        raise ValueError(f"the plan has {len(pages)} of the {count} pages asked for")
    return Plan(
        title=as_text(spec.get("title")) or untitled,
        style=as_text(spec.get("style")),
        characters=as_text(spec.get("characters")),
        pages=pages,
    )


def _panels(page: dict) -> tuple[Panel, ...]:
    return tuple(
        Panel(
            where=as_text(panel.get("where")),
            shows=as_text(panel.get("shows")),
            lines=tuple(
                line for item in as_list(panel.get("lines")) if (line := as_text(item))
            ),
        )
        for panel in as_list(page.get("panels"))
        if isinstance(panel, dict) and as_text(panel.get("shows"))
    )
