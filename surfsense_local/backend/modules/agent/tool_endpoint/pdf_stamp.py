"""The PDF stamp tool: a watermark, page numbers, a header or a footer on a new copy."""

from typing import Any

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.pdf_inputs import WHICH_SOURCE, located, one_pdf
from modules.agent.tool_endpoint.pdf_outputs import MadePdf, derived_title, keep
from modules.agent.tool_endpoint.tool import Tool, ToolCallError, ToolResult
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.pdf_tools.page_ranges import page_numbers
from modules.pdf_tools.refusal import PdfRefusedError
from modules.pdf_tools.stamp import KINDS, PAGE_NUMBER_TEXT, POSITIONS, stamp

_SUFFIX = {
    "watermark": "watermarked",
    "page_numbers": "numbered",
    "header": "with header",
    "footer": "with footer",
}

LISTING: dict[str, Any] = {
    "name": "pdf_stamp",
    "description": (
        "Stamp text on a PDF source or PDF artifact: a watermark, page numbers, a "
        "header or a footer. The PDF named is never changed: the result is a new "
        "PDF artifact in Studio. Returns its id, title and page count, and the "
        "stamped pages as images when you can see images."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "kind": {
                "type": "string",
                "enum": list(KINDS),
                "description": (
                    "watermark: large pale text corner to corner. page_numbers, "
                    "header, footer: one small line at the page's edge."
                ),
            },
            "document_id": {
                "type": "integer",
                "description": f"A PDF source, by {WHICH_SOURCE}. Or give artifact_id.",
            },
            "artifact_id": {
                "type": "integer",
                "description": "A PDF artifact in Studio, by artifact id.",
            },
            "text": {
                "type": "string",
                "description": (
                    "The words to stamp, in the PDF's language. For page_numbers, "
                    "{page} is each page's number and {total} the page count; left "
                    f'out, "{PAGE_NUMBER_TEXT}".'
                ),
            },
            "position": {
                "type": "string",
                "enum": list(POSITIONS),
                "description": (
                    "Where a header, footer or page number goes. Left out: "
                    "top-center for a header, bottom-center for a footer or page "
                    "numbers. A watermark ignores it."
                ),
            },
            "pages": {
                "type": "string",
                "description": (
                    'The pages to stamp, such as "2-" to skip a cover; every page '
                    "when left out."
                ),
            },
            "title": {
                "type": "string",
                "description": (
                    "The new PDF's title in Studio. Left out, it is the input's "
                    "title and what was stamped."
                ),
            },
        },
        "required": ["kind"],
    },
}


def run(
    session: Session, scope: TurnScope, arguments: dict[str, Any]
) -> str | ToolResult:
    """Read the PDF named, stamp a copy, keep it as an artifact."""
    kind = arguments.get("kind")
    if kind not in KINDS:
        raise ToolCallError(f"kind must be one of: {', '.join(KINDS)}.")
    text, position, pages = (
        _text(arguments, "text"),
        _text(arguments, "position"),
        _text(arguments, "pages"),
    )
    document_ids, artifact_ids = one_pdf(arguments)
    inputs = located(session, scope, document_ids, artifact_ids)
    (pdf,) = inputs
    reader = pdf.reader()
    try:
        numbers = page_numbers(pages, len(reader.pages))
        data = stamp(reader, kind, text, position, numbers)
    except PdfRefusedError as refused:
        raise ToolCallError(str(refused)) from refused
    title = derived_title(arguments.get("title"), pdf.title, _SUFFIX[kind])
    made = MadePdf(title, data, len(reader.pages), list(dict.fromkeys(numbers)))
    made_by = {
        "tool": LISTING["name"],
        "kind": kind,
        "text": text,
        "position": position,
        "pages": pages,
    }
    return keep(session, scope, inputs, [made], made_by)


def _text(arguments: dict[str, Any], key: str) -> str | None:
    value = arguments.get(key)
    if value is not None and not isinstance(value, str):
        raise ToolCallError(f"{key} must be text, or left out.")
    return value if value is None or value.strip() else None


PDF_STAMP = Tool(listing=LISTING, run=run, waits=True)
