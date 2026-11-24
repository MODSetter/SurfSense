"""The passages a call is shown, as the model reads and cites them: by number, title, section and
lines, in the sources' order."""

from __future__ import annotations

from modules.jobs.evidence.passages import Passage


def passages_block(
    passages: list[Passage],
    shown: list[int],
    standing: list[int] | None = None,
    labels: tuple[str, str] = ("", ""),
) -> str:
    """The passages as the model reads them, in the sources' order; with the pack's labels,
    those every question is shown come first under theirs, so the model knows which apply
    to all the firm's policies."""
    pinned = [i for i in standing or () if i in shown]
    if not pinned or not any(labels):
        return _listed(passages, shown)
    own = [i for i in shown if i not in pinned]
    parts = [labels[0], _listed(passages, pinned)]
    if own:
        parts += [labels[1], _listed(passages, own)]
    return "\n\n".join(part for part in parts if part)


def _listed(passages: list[Passage], shown: list[int]) -> str:
    blocks = []
    for index in shown:
        passage = passages[index]
        where = f" — {passage.section}" if passage.section else ""
        blocks.append(
            f"[{index + 1}] {passage.title}{where} (lines {passage.first_line}-{passage.last_line})\n"
            f"{passage.text}"
        )
    return "\n\n".join(blocks)
