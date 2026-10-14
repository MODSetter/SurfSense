"""The PDF form tool: list a form's fields, or fill them on a new copy, optionally flattened."""

from typing import Any

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.pdf_inputs import WHICH_SOURCE, located, one_pdf
from modules.agent.tool_endpoint.pdf_outputs import MadePdf, derived_title, keep
from modules.agent.tool_endpoint.tool import Tool, ToolCallError, ToolResult
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.pdf_tools.form_fields import FormField, form_fields
from modules.pdf_tools.form_fill import fill_form
from modules.pdf_tools.refusal import PdfRefusedError

ACTIONS = ("list", "fill")
# A long form's listing still fits well inside opencode's cut of a tool result
# (50 KB): opencode keeps a longer one where every thread's agent can read it.
LISTED_FIELDS = 200
LISTED_BYTES = 30_000
LISTED_OPTIONS = 20
VALUE_CHARS = 100

LISTING: dict[str, Any] = {
    "name": "pdf_form",
    "description": (
        "List the fields of a PDF form, or fill them. list returns each field's "
        "name, kind, page, current value and options. fill never changes the PDF "
        "named: it returns a new PDF artifact in Studio with its id, the fields "
        "filled, and those pages as images when you can see images. List before "
        "you fill."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": list(ACTIONS)},
            "document_id": {
                "type": "integer",
                "description": f"A PDF source, by {WHICH_SOURCE}. Or give artifact_id.",
            },
            "artifact_id": {
                "type": "integer",
                "description": "A PDF artifact in Studio, by artifact id.",
            },
            "fields": {
                "type": "object",
                "description": (
                    "For fill: each field's name, exactly as list gives it, to its "
                    "value: text for a text field, true or false for a checkbox, "
                    "one of the options for a radio group, dropdown or list."
                ),
            },
            "flatten": {
                "type": "boolean",
                "description": (
                    "For fill: true prints the values into the pages and removes "
                    "the fields, so nobody can change them. Default false."
                ),
            },
            "title": {
                "type": "string",
                "description": (
                    "For fill: the new PDF's title in Studio. Left out, it is the "
                    "form's title, filled."
                ),
            },
        },
        "required": ["action"],
    },
}


def run(
    session: Session, scope: TurnScope, arguments: dict[str, Any]
) -> str | ToolResult:
    """List the form's fields, or fill a copy and keep it as an artifact."""
    action = arguments.get("action")
    if action not in ACTIONS:
        raise ToolCallError("action must be list or fill.")
    values = arguments.get("fields")
    flatten = arguments.get("flatten")
    if action == "fill":
        if not isinstance(values, dict):
            raise ToolCallError(
                "Give fields: each field's name, as list gives it, to its value."
            )
        if flatten is not None and not isinstance(flatten, bool):
            raise ToolCallError("flatten must be true or false.")
    document_ids, artifact_ids = one_pdf(arguments)
    inputs = located(session, scope, document_ids, artifact_ids)
    (pdf,) = inputs
    reader = pdf.reader()
    try:
        if action == "list":
            return _listed(pdf.name, form_fields(reader))
        filled = fill_form(reader, values, flatten=bool(flatten))
    except PdfRefusedError as refused:
        raise ToolCallError(str(refused)) from refused
    title = derived_title(arguments.get("title"), pdf.title, "filled")
    made = MadePdf(title, filled.data, len(reader.pages), filled.pages)
    names = list(values)
    notes = [
        f"Filled {len(names)} field{'' if len(names) == 1 else 's'}: "
        f"{', '.join(names)}.",
        "The values are flattened into the pages: the copy has no fields left to "
        "change."
        if flatten
        else "The copy keeps its fields, so the user can still change them.",
    ]
    if filled.dropped_xfa:
        notes.append(
            "The form also carried an XFA copy of its fields, which the new PDF "
            "leaves out so every viewer shows these values."
        )
    made_by = {
        "tool": LISTING["name"],
        "action": "fill",
        "fields": names,
        "flatten": bool(flatten),
    }
    return keep(session, scope, inputs, [made], made_by, tuple(notes))


def _listed(name: str, fields: list[FormField]) -> str:
    if not fields:
        return (
            f"{name} has no form fields. To put text on its pages, use "
            "surfsense_pdf_stamp."
        )
    lines = [
        f"{name} has {len(fields)} form field{'' if len(fields) == 1 else 's'}, "
        "named as fill takes them:"
    ]
    room = LISTED_BYTES
    for field in fields[:LISTED_FIELDS]:
        line = _line(field)
        room -= len(line.encode()) + 1
        if room < 0:
            break
        lines.append(line)
    left = len(fields) - (len(lines) - 1)
    if left:
        lines.append(f"…and {left} more.")
    lines.append(
        "Fill them with action fill. The PDF is never changed: the filled form is "
        "a new PDF artifact."
    )
    return "\n".join(lines)


def _line(field: FormField) -> str:
    """One field: kind and pages, its value now, then what it takes."""
    parts = [f'- "{field.name}": {field.kind} {_on(field.pages)}, now {_now(field)}']
    if field.kind == "checkbox":
        parts.append("true or false")
    elif field.options:
        listed = [
            option if not field.shown or option == shown else f"{option} ({shown})"
            for option, shown in zip(
                field.options, field.shown or field.options, strict=True
            )
        ]
        many = " (one or more)" if field.multiple else ""
        named = ", ".join(listed[:LISTED_OPTIONS])
        if len(listed) > LISTED_OPTIONS:
            named += (
                f" and {len(listed) - LISTED_OPTIONS:,} more: give the one the user "
                "named"
            )
        parts.append(f"options{many}: {named}")
        if field.editable:
            parts.append("or any text")
    if field.max_length is not None:
        parts.append(f"at most {field.max_length} characters")
    if field.read_only or field.kind in ("signature", "button"):
        parts.append("cannot be filled")
    return "; ".join(parts)


def _on(pages: tuple[int, ...]) -> str:
    if not pages:
        return "on no page"
    if len(pages) == 1:
        return f"on page {pages[0]}"
    return f"on pages {', '.join(map(str, pages[:-1]))} and {pages[-1]}"


def _now(field: FormField) -> str:
    if field.kind == "checkbox":
        return "off" if field.value in ("Off", "") else "on"
    if isinstance(field.value, tuple):
        return (
            ", ".join(f'"{_cut(v)}"' for v in field.value[:LISTED_OPTIONS]) or "empty"
        )
    return f'"{_cut(field.value)}"' if field.value else "empty"


def _cut(value: str) -> str:
    return value if len(value) <= VALUE_CHARS else f"{value[: VALUE_CHARS - 1]}…"


PDF_FORM = Tool(listing=LISTING, run=run, waits=True)
