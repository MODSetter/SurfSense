"""Boxes an engine read one by one, as lines in reading order.

RapidOCR boxes each run of text alone. A visual row of boxes reads as one line,
left to right, so a receipt's item and price stay together; two columns of prose
side by side read one after the other, not across.
"""

import statistics
from dataclasses import dataclass, field

from worker.ingestion.scan_ocr.page import Line, spread_words

# A gutter at least this many text heights wide can split two columns.
_GUTTER = 0.75


@dataclass(frozen=True)
class Box:
    x0: float
    y0: float
    x1: float
    y1: float
    text: str

    @property
    def h(self) -> float:
        return max(1.0, self.y1 - self.y0)

    @property
    def cy(self) -> float:
        return (self.y0 + self.y1) / 2


@dataclass
class _Row:
    boxes: list[Box] = field(default_factory=list)

    @property
    def cy(self) -> float:
        return sum(box.cy for box in self.boxes) / len(self.boxes)

    @property
    def h(self) -> float:
        return statistics.median(box.h for box in self.boxes)


# A box this much taller than wide holds a line of text turned on its side.
_TALL = 1.5


def vertical_share(boxes: list[Box]) -> float:
    """The share of characters in boxes standing on end: a page turned a quarter
    round, which RapidOCR still reads with confidence, its lines across one row."""
    chars = sum(len(box.text) for box in boxes)
    tall = sum(
        len(box.text)
        for box in boxes
        if len(box.text) > 1 and box.y1 - box.y0 > _TALL * (box.x1 - box.x0)
    )
    return tall / chars if chars else 0.0


def lines_in_order(boxes: list[Box]) -> tuple[Line, ...]:
    if not boxes:
        return ()
    unit = statistics.median(box.h for box in boxes)
    rows = [row for block in _blocks(boxes, unit) for row in _rows(block)]
    return tuple(
        Line(
            " ".join(box.text for box in row.boxes),
            tuple(
                word
                for box in row.boxes
                for word in spread_words(
                    box.text, box.x0, box.y0, box.x1 - box.x0, box.h
                )
            ),
        )
        for row in rows
    )


def _rows(boxes: list[Box]) -> list[_Row]:
    """A box joins the row above when their centres are within half the smaller
    height."""
    rows: list[_Row] = []
    for box in sorted(boxes, key=lambda b: (b.cy, b.x0)):
        if rows and abs(box.cy - rows[-1].cy) <= 0.5 * min(box.h, rows[-1].h):
            rows[-1].boxes.append(box)
        else:
            rows.append(_Row([box]))
    for row in rows:
        row.boxes.sort(key=lambda b: b.x0)
    return rows


def _gaps(spans: list[tuple[float, float]]) -> list[tuple[float, float]]:
    ordered = sorted(spans)
    gaps: list[tuple[float, float]] = []
    end = ordered[0][1]
    for start, stop in ordered[1:]:
        if start > end:
            gaps.append((end, start))
        end = max(end, stop)
    return gaps


def _column_like(side: list[Box], width: float) -> bool:
    """Several rows of long text: prose, not a table's or a receipt's column."""
    if len(side) < 3:
        return False
    if max(b.x1 for b in side) - min(b.x0 for b in side) < 0.15 * width:
        return False
    if statistics.median(len(b.text) for b in side) < 10:
        return False
    return len(_rows(side)) >= 3


def _vertical_cut(boxes: list[Box], unit: float) -> tuple[list[Box], list[Box]] | None:
    width = max(1.0, max(b.x1 for b in boxes) - min(b.x0 for b in boxes))
    best: tuple[float, list[Box], list[Box]] | None = None
    for g0, g1 in _gaps([(b.x0, b.x1) for b in boxes]):
        if g1 - g0 < _GUTTER * unit:
            continue
        left = [b for b in boxes if b.x1 <= g0]
        right = [b for b in boxes if b.x0 >= g1]
        if (
            _column_like(left, width)
            and _column_like(right, width)
            and (best is None or g1 - g0 > best[0])
        ):
            best = (g1 - g0, left, right)
    return None if best is None else (best[1], best[2])


def _bands(boxes: list[Box], unit: float) -> list[list[Box]]:
    """Strips across the page with blank space between them; bands that share a
    gutter stay together, as two columns whose lines happen to align would."""
    gaps = _gaps([(b.y0, b.y1) for b in boxes])
    if not gaps:
        return [boxes]
    cuts = [(a + b) / 2 for a, b in gaps]
    bands: list[list[Box]] = [[] for _ in range(len(cuts) + 1)]
    for box in boxes:
        bands[sum(box.cy > cut for cut in cuts)].append(box)
    bands = [band for band in bands if band]
    groups: list[list[Box]] = []
    shared: tuple[float, float] | None = None
    for band in bands:
        gutter = _band_gutter(band, unit)
        if groups and shared is not None and gutter is not None:
            lo, hi = max(shared[0], gutter[0]), min(shared[1], gutter[1])
            if hi - lo >= _GUTTER * unit:
                groups[-1].extend(band)
                shared = (lo, hi)
                continue
        groups.append(list(band))
        shared = gutter
    return bands if len(groups) == 1 else groups


def _band_gutter(band: list[Box], unit: float) -> tuple[float, float] | None:
    gaps = [
        g for g in _gaps([(b.x0, b.x1) for b in band]) if g[1] - g[0] >= _GUTTER * unit
    ]
    return max(gaps, key=lambda g: g[1] - g[0]) if gaps else None


def _blocks(boxes: list[Box], unit: float, depth: int = 0) -> list[list[Box]]:
    """Columns left to right where prose stands side by side, else bands top to
    bottom (an XY cut)."""
    if len(boxes) < 6 or depth > 24:
        return [boxes]
    cut = _vertical_cut(boxes, unit)
    if cut is not None:
        return _blocks(cut[0], unit, depth + 1) + _blocks(cut[1], unit, depth + 1)
    bands = _bands(boxes, unit)
    if len(bands) == 1:
        return [boxes]
    return [block for band in bands for block in _blocks(band, unit, depth + 1)]
