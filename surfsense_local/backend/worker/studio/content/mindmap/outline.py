"""The model's free-form outline, read into the even one Markmap draws.

Depth is the model's to choose. Only width is cut: one Qwen3 4B map hung
300 labels under one branch until its reply ran out.
"""

import re

BRANCHES = 10
# More than any prompt asks for under one label; past it a list stops reading as a map.
CHILDREN = 12

_HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*\S)\s*$")
_BULLET = re.compile(r"^( *)(?:[-*+]|\d+[.)])\s+(.*\S)\s*$")
# Emphasis around the whole label, and heading marks inside it: `**# Causes**`.
_WRAPPED = re.compile(r"^(\*\*|__)(.+)\1$")
_HASHES = re.compile(r"^#+\s+")
# Four columns a tab: a model that indents with tabs means a level by each.
_TAB = 4


def read(raw: str) -> tuple[str | None, list[str]]:
    """The title, if the model wrote one, and the outline's lines, two spaces a level."""
    title, nodes = _nodes(raw)
    return title, _kept(_without_jumps(nodes))


def _nodes(raw: str) -> tuple[str | None, list[tuple[int, str]]]:
    """Headings and bullets as (depth, label); a bullet's depth counts from the
    heading above it, by how its indent compares with the bullets before it."""
    title: str | None = None
    nodes: list[tuple[int, str]] = []
    base = 0
    indents: list[int] = []
    for line in raw.splitlines():
        text = line.expandtabs(_TAB)
        heading = _HEADING.match(text)
        if heading:
            level, label = len(heading.group(1)), heading.group(2)
            if level == 1 and title is None:
                title = label
                continue
            depth = max(level - 2, 0)
            nodes.append((depth, label))
            base, indents = depth + 1, []
            continue
        bullet = _BULLET.match(text)
        if not bullet:
            continue
        indent = len(bullet.group(1))
        while indents and indents[-1] >= indent:
            indents.pop()
        label = _label(bullet.group(2))
        if label:
            nodes.append((base + len(indents), label))
            indents.append(indent)
    return title, nodes


def _label(text: str) -> str:
    wrapped = _WRAPPED.match(text)
    if wrapped:
        text = wrapped.group(2).strip()
    return _HASHES.sub("", text).strip()


def _without_jumps(nodes: list[tuple[int, str]]) -> list[tuple[int, str]]:
    """No node more than one level under the one before, which Markmap cannot hang."""
    even: list[tuple[int, str]] = []
    previous = -1
    for depth, label in nodes:
        previous = min(depth, previous + 1)
        even.append((previous, label))
    return even


def _kept(nodes: list[tuple[int, str]]) -> list[str]:
    """At most `BRANCHES` branches and `CHILDREN` under any label; a label cut
    takes everything under it."""
    lines: list[str] = []
    counts: list[int] = []
    kept_above: list[bool] = []
    for depth, label in nodes:
        del kept_above[depth:]
        del counts[depth + 1 :]
        counts += [0] * (depth + 1 - len(counts))
        limit = BRANCHES if depth == 0 else CHILDREN
        keep = all(kept_above) and counts[depth] < limit
        if keep:
            counts[depth] += 1
            lines.append(f"{'  ' * depth}- {label}")
        kept_above.append(keep)
    return lines
