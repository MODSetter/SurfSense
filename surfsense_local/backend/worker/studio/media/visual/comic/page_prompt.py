"""One page's prompt, laid out as image models read a comic page best."""

from modules.artifacts.comic.kinds import Kind
from worker.studio.media.visual.comic.plan import Panel, Plan

KEEP_CHARACTERS = (
    "Keep the characters looking exactly as in the reference picture: same faces, "
    "colours, clothes and drawing style. Draw a new page; do not copy its panels."
)
NO_WORDS = "Draw no text, no lettering, no speech bubbles."


def page_prompt(
    kind: Kind,
    plan: Plan,
    number: int,
    *,
    lettered: bool,
    referenced: bool,
) -> str:
    panels = plan.pages[number - 1]
    lines = [" ".join(part for part in (kind.looks, plan.style) if part)]
    if plan.characters:
        lines.append(f"Characters: {plan.characters}")
    if referenced:
        lines.append(KEEP_CHARACTERS)
    lines.append(
        f'{kind.unit} {number} of {len(plan.pages)} of the comic "{plan.title}". '
        f"{kind.picture}:"
    )
    lines += [
        _panel(index, panel, lettered) for index, panel in enumerate(panels, start=1)
    ]
    if not lettered:
        lines.append(NO_WORDS)
    return "\n".join(lines)


def strip_lines(panels: tuple[Panel, ...]) -> tuple[str, ...]:
    """A page's lines in reading order, for the strip under a page drawn without words."""
    return tuple(line for panel in panels for line in panel.lines)


def _panel(index: int, panel: Panel, lettered: bool) -> str:
    where = f" ({panel.where})" if panel.where else ""
    said = [_said(line) for line in panel.lines] if lettered else []
    return " ".join([f"Panel {index}{where}: {panel.shows}", *said])


def _said(line: str) -> str:
    speaker, colon, words = line.partition(":")
    if not colon or not words.strip():
        return f'Caption box: "{line.strip()}"'
    if speaker.strip().lower() == "caption":
        return f'Caption box: "{words.strip()}"'
    return f'{speaker.strip()} says: "{words.strip()}"'
