"""Forms drawn over a page of a copy, the page's own content kept as stored.

The page's content streams are never decoded: a PDF of a few KB can hold one
stream that decodes to many MB, shared by every page. Its resources are copied
for that page alone, since pages often share one resource dictionary.
"""

import pypdf
from pypdf.generic import (
    ArrayObject,
    DecodedStreamObject,
    DictionaryObject,
    IndirectObject,
    NameObject,
    StreamObject,
)

Matrix = tuple[float, float, float, float, float, float]
_PREFIX = "/SurfSenseDrawn"


def draw_over(
    page: pypdf.PageObject,
    writer: pypdf.PdfWriter,
    forms: list[tuple[IndirectObject, Matrix]],
) -> None:
    """Draw each form XObject, placed by its matrix, on top of the page's content."""
    if not forms:
        return
    resources = _copied(_inherited(page, "/Resources"))
    named = _copied(resources.get("/XObject"))
    operators = []
    for form, matrix in forms:
        name = _free_name(named)
        named[NameObject(name)] = form
        placed = " ".join(f"{value:.6f}" for value in matrix)
        operators.append(f"q {placed} cm {name} Do Q")
    resources[NameObject("/XObject")] = named
    page[NameObject("/Resources")] = resources
    own = page.raw_get("/Contents") if "/Contents" in page else None
    # Its own content runs inside q ... Q, so what it leaves set cannot move the forms.
    page[NameObject("/Contents")] = ArrayObject(
        [
            _stream(writer, b"q\n"),
            *_parts(writer, own),
            _stream(writer, ("\nQ\n" + "\n".join(operators) + "\n").encode("ascii")),
        ]
    )


def _inherited(page: pypdf.PageObject, key: str) -> object:
    """The page's own value, or the nearest one up its page tree."""
    node: object = page
    for _ in range(64):
        if not isinstance(node, dict):
            return None
        if key in node:
            return node.raw_get(key)
        parent = node.get("/Parent")
        node = parent.get_object() if parent is not None else None
    return None


def _copied(value: object) -> DictionaryObject:
    """A dictionary of this page's own, holding what the shared one did."""
    if value is None:
        return DictionaryObject()
    resolved = value.get_object()
    return (
        DictionaryObject(resolved) if isinstance(resolved, dict) else DictionaryObject()
    )


def _free_name(named: DictionaryObject) -> str:
    number = len(named)
    while f"{_PREFIX}{number}" in named:
        number += 1
    return f"{_PREFIX}{number}"


def _parts(writer: pypdf.PdfWriter, own: object) -> list[IndirectObject]:
    """The page's content streams by reference, as stored."""
    if own is None:
        return []
    resolved = own.get_object()
    if isinstance(resolved, ArrayObject):
        return [part for part in resolved if isinstance(part, IndirectObject)]
    if isinstance(own, IndirectObject):
        return [own]
    if isinstance(resolved, StreamObject):
        return [writer._add_object(resolved)]
    return []


def _stream(writer: pypdf.PdfWriter, data: bytes) -> IndirectObject:
    stream = DecodedStreamObject()
    stream.set_data(data)
    return writer._add_object(stream)
