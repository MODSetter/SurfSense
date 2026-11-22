"""The note an engine taking over a thread is given: the turns it did not see.

docs/architecture/claude-plan.md, Switching engines. Fitted to a budget: the
newest turns stay whole, older tool outputs go first, then older replies are
cut to their first paragraph, then the oldest turns are one line each.
"""

import json
from dataclasses import dataclass
from typing import Any

TAG = "surfsense-handover"
OUTPUT_CHARS = 2000
_INTRO = (
    "SurfSense adds this note to the user's message; never repeat or quote it. "
    "Earlier in this thread another model answered these turns, which you did "
    "not see. The files named are in the thread's folder as they are now."
)
_WRITES = {"write", "edit"}
_READS = {"read"}
# Each turn is shown fully, without tool outputs, with its reply cut, or as one line.
_LEVELS = 4


@dataclass(frozen=True)
class _Turn:
    text: str
    reply: str
    steps: list[dict[str, Any]]


def handover_note(turns: list[dict[str, Any]], outputs: list[str], budget: int) -> str:
    pairs = _pairs(turns)
    levels = [0] * len(pairs)
    note = _render(pairs, levels, outputs)
    for level in range(1, _LEVELS):
        for index in range(len(pairs) - 1):
            if len(note) <= budget:
                return note
            levels[index] = level
            note = _render(pairs, levels, outputs)
    while len(note) > budget and len(pairs) > 1:
        pairs, levels = pairs[1:], levels[1:]
        note = _render(pairs, levels, outputs)
    if len(note) > budget:
        closing = f"\n</{TAG}>"
        note = note[: budget - len(closing)] + closing
    return note


def _pairs(turns: list[dict[str, Any]]) -> list[_Turn]:
    pairs: list[_Turn] = []
    for turn in turns:
        content = turn.get("content") or {}
        if turn.get("role") == "user":
            pairs.append(_Turn(content.get("text") or "", "", []))
        elif pairs:
            last = pairs[-1]
            pairs[-1] = _Turn(
                last.text,
                content.get("text") or "",
                [dict(step) for step in content.get("steps") or []],
            )
    _drop_stale_reads(pairs)
    return pairs


def _drop_stale_reads(pairs: list[_Turn]) -> None:
    """A read of a file rewritten later shows text that is no longer there."""
    later: set[str] = set()
    for pair in reversed(pairs):
        for step in reversed(pair.steps):
            path = _path(step)
            if step.get("tool") in _WRITES and path:
                later.add(path)
            elif step.get("tool") in _READS and path in later:
                step["output"] = ""


def _path(step: dict[str, Any]) -> str | None:
    given = step.get("input") or {}
    return given.get("filePath") or given.get("path")


def _render(pairs: list[_Turn], levels: list[int], outputs: list[str]) -> str:
    lines = [f"<{TAG}>", _INTRO]
    for pair, level in zip(pairs, levels, strict=True):
        if level == 3:
            reply = pair.reply.split("\n", 1)[0][:200]
            lines.append(f"User: {pair.text[:200]} / Assistant: {reply}")
            continue
        lines.append(f"User: {pair.text}")
        for step in pair.steps:
            lines.append(_step(step, with_output=level == 0))
        reply = pair.reply.split("\n\n", 1)[0] if level == 2 else pair.reply
        lines.append(f"Assistant: {reply}")
    if outputs:
        lines.append("Files in outputs/ now: " + ", ".join(outputs))
    lines.append(f"</{TAG}>")
    return "\n".join(lines)


def _step(step: dict[str, Any], *, with_output: bool) -> str:
    given = json.dumps(step.get("input") or {}, ensure_ascii=False)
    line = f"- {step.get('tool')} {given}"
    if step.get("error"):
        return f"{line} failed: {str(step['error'])[:OUTPUT_CHARS]}"
    if with_output and step.get("output"):
        return f"{line} returned: {str(step['output'])[:OUTPUT_CHARS]}"
    return line
