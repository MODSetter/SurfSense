"""A PDF form's fields as the agent reads them: name, kind, value, choices and pages."""

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import pypdf
from pypdf.generic import ArrayObject, DictionaryObject, IndirectObject

from modules.pdf_tools.refusal import PdfRefusedError

# Field flags (PDF 32000-1, tables 221, 226, 228, 230).
READ_ONLY = 1
RADIO = 1 << 15
PUSHBUTTON = 1 << 16
COMBO = 1 << 17
EDITABLE = 1 << 18
MULTIPLE = 1 << 21

XFA_ONLY = (
    "is an XFA form, which SurfSense cannot read or fill: its fields exist only "
    "in Adobe's XFA format. Ask the user to fill it in Adobe Acrobat or Reader, "
    "or for a copy saved as a standard PDF form."
)


@dataclass(frozen=True)
class FormField:
    """One field to fill, by its full name, as a person sees it on the page."""

    name: str
    kind: str  # text, checkbox, radio, dropdown, list, signature or button
    value: str | tuple[str, ...]
    # A checkbox's or radio's states, or a choice's export values, in order.
    options: tuple[str, ...]
    # What a choice shows for each option, where it differs from its value.
    shown: tuple[str, ...]
    pages: tuple[int, ...]
    read_only: bool = False
    editable: bool = False
    multiple: bool = False
    max_length: int | None = None


def form_fields(reader: pypdf.PdfReader) -> list[FormField]:
    """Every field in form order; none for a PDF without a form.

    An XFA-only form is refused: its fields are not PDF fields.
    """
    root = reader.trailer["/Root"]
    form = root.get("/AcroForm")
    form = form.get_object() if form is not None else None
    fields = form.get("/Fields") if isinstance(form, DictionaryObject) else None
    fields = fields.get_object() if fields is not None else ArrayObject()
    if root.get("/NeedsRendering") or (
        isinstance(form, DictionaryObject) and "/XFA" in form and not fields
    ):
        raise PdfRefusedError(f"This PDF {XFA_ONLY}")
    terminals = list(_terminals(fields, ""))
    pages = _pages_of(reader)
    return [_field(name, node, pages.get(key, ())) for name, node, key in terminals]


def _terminals(
    nodes: ArrayObject, prefix: str
) -> Iterator[tuple[str, DictionaryObject, int]]:
    """Each field that holds a value: its full name, its dictionary and its identity."""
    for ref in nodes:
        node = ref.get_object()
        if not isinstance(node, DictionaryObject):
            continue
        name = f"{prefix}{node['/T']}" if "/T" in node else prefix.rstrip(".")
        kids = node.get("/Kids")
        kids = kids.get_object() if kids is not None else ArrayObject()
        # Kids with names are fields of their own; kids without are its widgets.
        if any("/T" in kid.get_object() for kid in kids):
            yield from _terminals(kids, f"{name}.")
        elif "/T" in node:
            yield name, node, _identity(ref)


def _identity(ref: Any) -> int:
    return ref.idnum if isinstance(ref, IndirectObject) else id(ref)


def _pages_of(reader: pypdf.PdfReader) -> dict[int, tuple[int, ...]]:
    """The pages each field's widgets are on, from 1."""
    found: dict[int, list[int]] = {}
    for number, page in enumerate(reader.pages, 1):
        for ref in page.get("/Annots") or ():
            widget = ref.get_object()
            if widget.get("/Subtype") != "/Widget":
                continue
            owner = ref if "/T" in widget else widget.raw_get("/Parent")
            if owner is None:
                continue
            numbers = found.setdefault(_identity(owner), [])
            if number not in numbers:
                numbers.append(number)
    return {key: tuple(numbers) for key, numbers in found.items()}


def _field(name: str, node: DictionaryObject, pages: tuple[int, ...]) -> FormField:
    kind_name = _inherited(node, "/FT")
    flags = int(_inherited(node, "/Ff") or 0)
    raw_value = _inherited(node, "/V")
    if kind_name == "/Btn":
        kind = (
            "button" if flags & PUSHBUTTON else "radio" if flags & RADIO else "checkbox"
        )
        options = _states(node)
        value = _name(raw_value) if raw_value is not None else "Off"
        shown: tuple[str, ...] = ()
    elif kind_name == "/Ch":
        kind = "dropdown" if flags & COMBO else "list"
        options, shown = _choices(_inherited(node, "/Opt"))
        value = _choice_value(raw_value)
    elif kind_name == "/Sig":
        kind, options, shown, value = "signature", (), (), ""
    else:
        kind, options, shown = "text", (), ()
        value = str(raw_value) if raw_value is not None else ""
    length = _inherited(node, "/MaxLen")
    return FormField(
        name=name,
        kind=kind,
        value=value,
        options=options,
        shown=shown,
        pages=pages,
        read_only=bool(flags & READ_ONLY),
        editable=bool(flags & EDITABLE),
        multiple=bool(flags & MULTIPLE),
        max_length=int(length) if length is not None else None,
    )


def _inherited(node: DictionaryObject, key: str) -> Any:
    """A field's own value for `key`, else its nearest ancestor's."""
    while node is not None:
        if key in node:
            return node[key]
        parent = node.get("/Parent")
        node = parent.get_object() if parent is not None else None
    return None


def _states(node: DictionaryObject) -> tuple[str, ...]:
    """The on-states of a checkbox's or radio group's widgets, in order."""
    kids = node.get("/Kids")
    widgets = [kid.get_object() for kid in kids] if kids is not None else [node]
    states: list[str] = []
    for widget in widgets:
        appearance = widget.get("/AP")
        normal = appearance.get_object().get("/N") if appearance is not None else None
        normal = normal.get_object() if normal is not None else None
        if isinstance(normal, DictionaryObject) and "/Type" not in normal:
            states += [
                _name(state)
                for state in normal
                if state != "/Off" and _name(state) not in states
            ]
    return tuple(states)


def _choices(raw: Any) -> tuple[tuple[str, ...], tuple[str, ...]]:
    """A choice's export values, and what it shows for each."""
    values: list[str] = []
    shown: list[str] = []
    for option in raw.get_object() if raw is not None else ():
        option = option.get_object()
        if isinstance(option, list) and len(option) == 2:
            values.append(str(option[0]))
            shown.append(str(option[1]))
        else:
            values.append(str(option))
            shown.append(str(option))
    return tuple(values), tuple(shown) if shown != values else ()


def _choice_value(raw: Any) -> str | tuple[str, ...]:
    if raw is None:
        return ""
    raw = raw.get_object()
    if isinstance(raw, list):
        return tuple(str(item) for item in raw)
    return str(raw)


def _name(value: Any) -> str:
    return str(value).removeprefix("/")
