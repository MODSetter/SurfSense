"""How an infographic's content is asked for, whether Studio or the agent wrote it."""

_TASK = (
    "Create a polished, complete infographic from the supplied factual source. "
    "Choose the clearest visual hierarchy and composition. Summarize or omit "
    "secondary detail when necessary for readability. Keep all important content "
    "fully visible within the canvas, preserve factual accuracy, and follow the "
    "selected visual style."
)
# ponytail: one style for now. A picker rides on the job's `options` once the
# panel offers one.
_STYLE = (
    "Use a hand-drawn editorial sketchnote style with mostly black ink on a warm "
    "white background, one restrained accent color, simple icons, arrows, "
    "connectors, loose organic lines, generous whitespace, short hand-lettered "
    "headings, and highly legible labels. Avoid photorealism, dense paragraphs, "
    "decorative illegible handwriting, and watermarks."
)


def in_infographic_style(content: str) -> str:
    return f"{_TASK}\n\nCONTENT\n{content}\n\nVISUAL STYLE\n{_STYLE}"
