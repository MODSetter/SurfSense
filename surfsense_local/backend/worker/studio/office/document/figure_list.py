"""The prompt's list of the figures a document may place, each with its caption."""

from collections.abc import Iterable

# A caption is the source's own text; a long one costs the window and says no
# more. The refine route's window check counts the same cut.
from modules.artifacts.studio_documents.window import CAPTION_CHARS
from worker.studio.shared.artifact import SourceImage


def markdown_figures(figures: Iterable[SourceImage]) -> str:
    lines = [f"- ![{_caption(figure)}](image:{figure.name})" for figure in figures]
    if not lines:
        return "The sources hold no figures, so place none."
    return "Figures you may place, each written as shown:\n\n" + "\n".join(lines)


def script_figures(figures: Iterable[SourceImage]) -> str:
    lines = [f'- "{figure.name}": {_caption(figure)}' for figure in figures]
    if not lines:
        return "The sources hold no figures, so place none."
    return (
        "Figures you may place, by name, each a PNG at "
        'os.path.join(os.environ["IMAGES_DIR"], name + ".png"):\n\n' + "\n".join(lines)
    )


def _caption(figure: SourceImage) -> str:
    caption = " ".join((figure.caption or "").split())
    if len(caption) > CAPTION_CHARS:
        caption = caption[: CAPTION_CHARS - 1].rstrip() + "…"
    return (caption or "no caption").replace("[", "(").replace("]", ")")
