"""List markers as Word renders them from numbering.xml.

Checked against Word 16's ListString on the reference fixtures. Every w:num on
one w:abstractNum shares its counters (Docling restarts each num instead). A
num's startOverride sets the counter once, on the num's first paragraph at an
overridden level. A level restarts from the starts of the num whose paragraph
reset it. An unused upper level shows its start, then keeps it. A
w:numStyleLink borrows another list's levels but keeps its own counters.
"""

import re
from collections.abc import Callable
from typing import Any, NamedTuple

from worker.ingestion.word_markdown.number_formats import SILENT_FORMATS, formatted
from worker.ingestion.word_markdown.ooxml_names import ILVL, P_STYLE, VAL, w

_ABSTRACT_NUM = w("abstractNum")
_ABSTRACT_NUM_ID = w("abstractNumId")
_NUM = w("num")
_NUM_ID_ATTR = w("numId")
_LVL = w("lvl")
_LVL_OVERRIDE = w("lvlOverride")
_START_OVERRIDE = w("startOverride")
_NUM_STYLE_LINK = w("numStyleLink")
_PLACEHOLDER = re.compile(r"%([1-9])")
_LEVELS = 9
# Both come from the file. The longest marker in 795 reference files is 10
# characters; these keep a crafted one from growing with the document.
_LONGEST_MARKER = 255
_LARGEST_START = 2**31 - 1

BULLET = "-"


class _Level(NamedTuple):
    num_fmt: str
    text: str
    start: int
    restart: int | None  # w:lvlRestart: 0 never, k after level k (1-based)
    legal: bool
    style_id: str | None  # the paragraph style a w:pStyle ties to this level


class _Num(NamedTuple):
    abstract_id: str
    start_overrides: dict[int, int]
    level_overrides: dict[int, _Level]


class ListNumbering:
    """Advances and renders the counters of one document, in reading order."""

    def __init__(
        self, root: Any | None, numbering_style_num: Callable[[str], str | None]
    ) -> None:
        self._abstracts: dict[str, Any] = {}
        self._nums: dict[str, _Num] = {}
        if root is not None:
            for element in root.iterchildren(_ABSTRACT_NUM):
                self._abstracts.setdefault(element.get(_ABSTRACT_NUM_ID, ""), element)
            for element in root.iterchildren(_NUM):
                num = _num(element)
                if num is not None:
                    self._nums.setdefault(element.get(_NUM_ID_ATTR, ""), num)
        self._numbering_style_num = numbering_style_num
        self._levels: dict[str, dict[int, _Level]] = {}
        self._defining: dict[str, str | None] = {}
        self._counters: dict[str, list[int | None]] = {}
        # Per abstract list: the value a reset level counts from next.
        self._restarts: dict[str, list[int | None]] = {}
        self._overridden: set[str] = set()

    def exists(self, num_id: str) -> bool:
        return num_id in self._nums and self._levels_abstract(num_id) is not None

    def style_of_level(self, num_id: str, ilvl: int) -> str | None:
        level = self._levels_of(num_id).get(ilvl)
        return None if level is None else level.style_id

    def next_marker(self, num_id: str, ilvl: int) -> str | None:
        """Count this paragraph and return its marker: BULLET, the rendered
        number, "" when the level shows nothing, or None for no such list."""
        if not self.exists(num_id):
            return None
        num = self._nums[num_id]
        ilvl = min(max(ilvl, 0), _LEVELS - 1)
        levels = self._levels_of(num_id)
        counters = self._counters.setdefault(num.abstract_id, [None] * _LEVELS)
        restarts = self._restarts.setdefault(num.abstract_id, [None] * _LEVELS)

        def start(at: int) -> int:
            pending = restarts[at]
            return self._start(num, levels, at) if pending is None else pending

        if num_id not in self._overridden and ilvl in num.start_overrides:
            self._overridden.add(num_id)
            counters[ilvl] = num.start_overrides[ilvl] - 1
        for upper in range(ilvl):
            if counters[upper] is None:
                counters[upper] = start(upper)
        current = counters[ilvl]
        counters[ilvl] = start(ilvl) if current is None else current + 1
        for deeper in range(ilvl + 1, _LEVELS):
            restart = levels[deeper].restart if deeper in levels else None
            if restart != 0 and ilvl < (deeper if restart is None else restart):
                counters[deeper] = None
                restarts[deeper] = self._start(num, levels, deeper)

        def shown_value(at: int) -> int:
            value = counters[at]
            return start(at) if value is None else value

        level = levels.get(ilvl)
        if level is None:
            return ""
        if level.num_fmt == "bullet":
            return BULLET

        def number(match: re.Match[str]) -> str:
            at = int(match.group(1)) - 1
            value = shown_value(at)
            shown = levels.get(at)
            if shown is not None and shown.num_fmt in SILENT_FORMATS:
                return ""
            # Legal numbering shows every level in decimal: 2.1, never II.a.
            legal = level.legal or shown is None
            return formatted(value, "decimal" if legal else shown.num_fmt)

        return _PLACEHOLDER.sub(number, level.text).strip()[:_LONGEST_MARKER]

    def _start(self, num: _Num, levels: dict[int, _Level], ilvl: int) -> int:
        if ilvl in num.start_overrides:
            return num.start_overrides[ilvl]
        level = levels.get(ilvl)
        return level.start if level is not None else 1

    def _levels_abstract(self, num_id: str) -> str | None:
        """The abstract list that defines the num's levels, through numStyleLink."""
        if num_id not in self._defining:
            self._defining[num_id] = self._follow_style_links(num_id)
        return self._defining[num_id]

    def _follow_style_links(self, num_id: str) -> str | None:
        num = self._nums.get(num_id)
        seen: set[str] = set()
        while num is not None and num.abstract_id not in seen:
            seen.add(num.abstract_id)
            abstract = self._abstracts.get(num.abstract_id)
            if abstract is None:
                return None
            link = abstract.find(_NUM_STYLE_LINK)
            if link is None:
                return num.abstract_id
            linked_num = self._numbering_style_num(link.get(VAL, ""))
            num = self._nums.get(linked_num) if linked_num else None
        return None

    def _levels_of(self, num_id: str) -> dict[int, _Level]:
        if num_id not in self._levels:
            levels: dict[int, _Level] = {}
            abstract_id = self._levels_abstract(num_id)
            if abstract_id is not None:
                for element in self._abstracts[abstract_id].iterchildren(_LVL):
                    ilvl = _int(element.get(ILVL))
                    if ilvl is not None and 0 <= ilvl < _LEVELS:
                        levels.setdefault(ilvl, _level(element))
            num = self._nums.get(num_id)
            if num is not None and num.level_overrides:
                # Word then shows nothing at a level the num restarts but
                # does not redefine.
                for ilvl in num.start_overrides.keys() - num.level_overrides.keys():
                    if ilvl in levels:
                        levels[ilvl] = levels[ilvl]._replace(text="")
                levels.update(num.level_overrides)
            self._levels[num_id] = levels
        return self._levels[num_id]


def _num(element: Any) -> _Num | None:
    abstract = element.find(_ABSTRACT_NUM_ID)
    if abstract is None or abstract.get(VAL) is None:
        return None
    starts: dict[int, int] = {}
    levels: dict[int, _Level] = {}
    for override in element.iterchildren(_LVL_OVERRIDE):
        ilvl = _int(override.get(ILVL))
        if ilvl is None or not 0 <= ilvl < _LEVELS:
            continue
        start = override.find(_START_OVERRIDE)
        value = None if start is None else _start_value(start.get(VAL))
        if value is not None:
            starts[ilvl] = value
        replaced = override.find(_LVL)
        if replaced is not None:
            levels[ilvl] = _level(replaced)
    return _Num(abstract.get(VAL), starts, levels)


def _level(element: Any) -> _Level:
    def value(name: str) -> str | None:
        child = element.find(w(name))
        return None if child is None else child.get(VAL)

    style = element.find(P_STYLE)
    start = _start_value(value("start"))
    legal = element.find(w("isLgl"))
    return _Level(
        num_fmt=value("numFmt") or "decimal",
        text=(value("lvlText") or "")[:_LONGEST_MARKER],
        start=1 if start is None else start,
        restart=_int(value("lvlRestart")),
        legal=legal is not None and legal.get(VAL) not in ("0", "false", "off"),
        style_id=None if style is None else style.get(VAL),
    )


def _start_value(text: str | None) -> int | None:
    """A start a 32-bit counter holds; any other is ignored, as if not given."""
    value = _int(text)
    return value if value is not None and abs(value) <= _LARGEST_START else None


def _int(text: str | None) -> int | None:
    try:
        return int(text) if text is not None else None
    except ValueError:
        return None
