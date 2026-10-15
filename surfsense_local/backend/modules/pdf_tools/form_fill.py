"""A PDF form filled on a copy, each value checked against its field first."""

from dataclasses import dataclass
from typing import Any

import pypdf
from pypdf.generic import NameObject

from modules.pdf_tools.form_fields import FormField, form_fields
from modules.pdf_tools.form_flatten import flatten_form
from modules.pdf_tools.page_operations import written
from modules.pdf_tools.refusal import PdfRefusedError

# Past this many, a refusal names the first ones and counts the rest.
NAMED_FIELDS = 30
NAMED_CHOICES = 50
_ON = {"true", "yes", "on", "checked", "x", "1"}
_OFF = {"false", "no", "off", "unchecked", "", "0"}


@dataclass(frozen=True)
class FilledForm:
    """The filled copy, the pages holding the fields filled, and whether XFA was dropped."""

    data: bytes
    pages: list[int]
    dropped_xfa: bool


def fill_form(
    reader: pypdf.PdfReader, values: dict[str, Any], *, flatten: bool
) -> FilledForm:
    """A copy with each named field set; flattened, the values become page content and no field stays.

    A hybrid form also carries XFA, which Acrobat would show instead of the
    values set here, so the copy drops it.
    """
    fields = form_fields(reader)
    if not fields:
        raise PdfRefusedError(
            "This PDF has no form fields to fill. To add text to its pages, use "
            "surfsense_pdf_stamp."
        )
    if not values:
        raise PdfRefusedError(
            "Name at least one field to fill; list the fields with action list."
        )
    by_name = {field.name: field for field in fields}
    checked = {name: _checked(by_name, name, value) for name, value in values.items()}
    writer = pypdf.PdfWriter(clone_from=reader)
    form = writer.root_object["/AcroForm"].get_object()
    dropped_xfa = "/XFA" in form
    if dropped_xfa:
        del form[NameObject("/XFA")]
    # Unflattened, viewers redraw each field in their own fonts as well.
    writer.update_page_form_field_values(None, checked, auto_regenerate=not flatten)
    if flatten:
        flatten_form(writer)
    pages = sorted({page for name in checked for page in by_name[name].pages})
    return FilledForm(written(writer), pages, dropped_xfa)


def _checked(by_name: dict[str, FormField], name: str, value: Any) -> Any:
    """The value as pypdf sets it, or a refusal saying what the field takes."""
    field = by_name.get(name)
    if field is None:
        known = list(by_name)
        listed = ", ".join(known[:NAMED_FIELDS])
        if len(known) > NAMED_FIELDS:
            listed += f" and {len(known) - NAMED_FIELDS} more"
        raise PdfRefusedError(
            f'This form has no field "{name}". Its fields are: {listed}.'
        )
    if field.read_only:
        raise PdfRefusedError(f'Field "{name}" is read-only and cannot be filled.')
    if field.kind in ("signature", "button"):
        raise PdfRefusedError(
            f'Field "{name}" is a {field.kind}, which cannot be filled here.'
        )
    if field.kind == "checkbox":
        return _checkbox(field, value)
    if field.kind == "radio":
        return f"/{_one_of(field, value)}"
    if field.kind in ("dropdown", "list"):
        return _choice(field, value)
    return _text(field, value)


def _checkbox(field: FormField, value: Any) -> str:
    on = field.options[0] if field.options else "Yes"
    if isinstance(value, bool):
        return f"/{on}" if value else "/Off"
    text = str(value).strip() if isinstance(value, str | int) else None
    if text is not None and (text.casefold() in _ON or text == on):
        return f"/{on}"
    if text is not None and (text.casefold() in _OFF or text == "Off"):
        return "/Off"
    raise PdfRefusedError(f'Field "{field.name}" is a checkbox: give true or false.')


def _one_of(field: FormField, value: Any) -> str:
    if isinstance(value, str):
        for option, label in zip(
            field.options, field.shown or field.options, strict=True
        ):
            if value.strip() in (option, label):
                return option
    choices = _choices(field)
    named = ", ".join(choices[:NAMED_CHOICES])
    if len(choices) > NAMED_CHOICES:
        named += f" and {len(choices) - NAMED_CHOICES:,} more"
    raise PdfRefusedError(f'Field "{field.name}" takes one of: {named}.')


def _choice(field: FormField, value: Any) -> str | list[str]:
    if field.multiple and isinstance(value, list):
        return [_one_of(field, item) for item in value]
    if field.editable and isinstance(value, str):
        return value
    return _one_of(field, value)


def _choices(field: FormField) -> list[str]:
    if not field.shown:
        return list(field.options)
    return [
        option if option == label else f"{option} ({label})"
        for option, label in zip(field.options, field.shown, strict=True)
    ]


def _text(field: FormField, value: Any) -> str:
    if isinstance(value, bool) or not isinstance(value, str | int | float):
        raise PdfRefusedError(f'Field "{field.name}" is a text field: give text.')
    text = str(value)
    if field.max_length is not None and len(text) > field.max_length:
        raise PdfRefusedError(
            f'Field "{field.name}" holds at most {field.max_length} characters.'
        )
    return text
