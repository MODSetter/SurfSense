"""A filled form flattened: each field's look drawn into its page, and the fields removed.

pypdf's own flatten leaves the widgets in place and names a radio group's
appearances alike, so the second button of a group is lost.
"""

import pypdf
from pypdf.generic import (
    ArrayObject,
    DictionaryObject,
    IndirectObject,
    NameObject,
)

from modules.pdf_tools.drawn_over import Matrix, draw_over

# Annotation flags: hidden, and not shown on screen.
HIDDEN = 2
NO_VIEW = 32


def flatten_form(writer: pypdf.PdfWriter) -> None:
    """Draw every visible widget's current appearance onto its page, then drop the form."""
    for page in writer.pages:
        annotations = page.get("/Annots")
        if not annotations:
            continue
        kept = ArrayObject()
        drawn: list[tuple[IndirectObject, Matrix]] = []
        for ref in annotations.get_object():
            widget = ref.get_object()
            if widget.get("/Subtype") != "/Widget":
                kept.append(ref)
                continue
            placed = _placed(widget)
            if placed is not None:
                drawn.append(placed)
        draw_over(page, writer, drawn)
        if kept:
            page[NameObject("/Annots")] = kept
        else:
            del page[NameObject("/Annots")]
    if "/AcroForm" in writer.root_object:
        del writer.root_object[NameObject("/AcroForm")]


def _placed(widget: DictionaryObject) -> tuple[IndirectObject, Matrix] | None:
    """The widget's appearance and the matrix that fits it to its rectangle."""
    if int(widget.get("/F", 0)) & (HIDDEN | NO_VIEW):
        return None
    appearance = _normal_appearance(widget)
    if appearance is None:
        return None
    stream = appearance.get_object()
    x0, y0, x1, y1 = _box(stream)
    left, bottom, right, top = sorted_rect(widget["/Rect"])
    if x1 - x0 <= 0 or y1 - y0 <= 0:
        return None
    sx, sy = (right - left) / (x1 - x0), (top - bottom) / (y1 - y0)
    return appearance, (sx, 0, 0, sy, left - x0 * sx, bottom - y0 * sy)


def _normal_appearance(widget: DictionaryObject) -> IndirectObject | None:
    """The widget's normal appearance stream for its current state, by reference."""
    appearances = widget.get("/AP")
    if appearances is None:
        return None
    appearances = appearances.get_object()
    normal = appearances.raw_get("/N") if "/N" in appearances else None
    if normal is None:
        return None
    resolved = normal.get_object()
    if isinstance(resolved, DictionaryObject) and "/BBox" not in resolved:
        state = widget.get("/AS")
        if state is None or state not in resolved:
            return None
        normal = resolved.raw_get(state)
    return normal if isinstance(normal, IndirectObject) else None


def _box(stream: DictionaryObject) -> tuple[float, float, float, float]:
    """The appearance's bounding box once its own matrix is applied."""
    x0, y0, x1, y1 = (float(v) for v in stream["/BBox"])
    a, b, c, d, e, f = (float(v) for v in stream.get("/Matrix", (1, 0, 0, 1, 0, 0)))
    corners = [
        (a * x + c * y + e, b * x + d * y + f) for x in (x0, x1) for y in (y0, y1)
    ]
    xs, ys = [p[0] for p in corners], [p[1] for p in corners]
    return min(xs), min(ys), max(xs), max(ys)


def sorted_rect(rect: ArrayObject) -> tuple[float, float, float, float]:
    """A rectangle as left, bottom, right, top, whichever corners it was written with."""
    x0, y0, x1, y1 = (float(v) for v in rect)
    return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)
