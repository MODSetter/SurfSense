"""The PDF pages tool: merge, extract, split, rotate or reorder pages into new PDF artifacts."""

from typing import Any

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.pdf_inputs import (
    WHICH_SOURCE,
    PdfInput,
    ids,
    located,
    readers,
)
from modules.agent.tool_endpoint.pdf_outputs import MadePdf, derived_title, keep
from modules.agent.tool_endpoint.tool import Tool, ToolCallError, ToolResult
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.pdf_tools.page_operations import (
    QUARTER_TURNS,
    extract,
    merge,
    reorder,
    rotate,
    split,
)
from modules.pdf_tools.page_ranges import page_groups, page_numbers
from modules.pdf_tools.refusal import PdfRefusedError

OPERATIONS = ("merge", "extract", "split", "rotate", "reorder")
# Each part is an artifact in Studio; more than this is a list nobody reads.
MAX_PARTS = 20
RANGES = (
    'Pages are numbers and ranges from 1, such as "1-3,7", "5-" for page 5 to '
    'the end, or "9-7" for backwards.'
)

LISTING: dict[str, Any] = {
    "name": "pdf_pages",
    "description": (
        "Merge, extract, split, rotate or reorder the pages of PDF sources or PDF "
        "artifacts. The PDFs named are never changed: each result is a new PDF "
        "artifact in Studio. Returns each new artifact's id, title and page count, "
        "and its pages as images when you can see images. The surfsense-pdf skill "
        "says which PDF tool fits a request."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "operation": {
                "type": "string",
                "enum": list(OPERATIONS),
                "description": (
                    "merge: several PDFs into one, in order. extract: the pages "
                    "named, in the order named. split: one new PDF per range in "
                    "pages, or per page. rotate: turn pages clockwise. reorder: "
                    "every page once, in a new order."
                ),
            },
            "document_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    f"PDF sources, each by {WHICH_SOURCE}. A merge takes these in "
                    "order, then artifact_ids."
                ),
            },
            "artifact_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "PDF artifacts in Studio, by artifact id.",
            },
            "pages": {
                "type": "string",
                "description": (
                    f"{RANGES} extract and reorder need it; split makes one PDF per "
                    "comma-separated range; rotate turns every page when it is "
                    "left out. Not for merge."
                ),
            },
            "angle": {
                "type": "integer",
                "enum": list(QUARTER_TURNS),
                "description": "For rotate: degrees clockwise. 270 turns left.",
            },
            "title": {
                "type": "string",
                "description": (
                    "The new PDF's title in Studio; a split adds each part's pages. "
                    "Left out, it is the input's title and what was done."
                ),
            },
        },
        "required": ["operation"],
    },
}


def run(
    session: Session, scope: TurnScope, arguments: dict[str, Any]
) -> str | ToolResult:
    """Read the PDFs named, make the new ones, keep each as an artifact."""
    operation = arguments.get("operation")
    if operation not in OPERATIONS:
        raise ToolCallError(f"operation must be one of: {', '.join(OPERATIONS)}.")
    document_ids = ids(arguments, "document_ids")
    artifact_ids = ids(arguments, "artifact_ids")
    pages, angle = _pages(arguments), arguments.get("angle")
    _refuse_misfits(operation, len(document_ids) + len(artifact_ids), pages, angle)
    inputs = located(session, scope, document_ids, artifact_ids)
    try:
        made = _made(operation, inputs, pages, angle, arguments.get("title"))
    except PdfRefusedError as refused:
        raise ToolCallError(str(refused)) from refused
    made_by = {"tool": LISTING["name"], "operation": operation, "pages": pages}
    if operation == "rotate":
        made_by["angle"] = angle
    return keep(session, scope, inputs, made, made_by)


def _pages(arguments: dict[str, Any]) -> str | None:
    pages = arguments.get("pages")
    if isinstance(pages, int) and not isinstance(pages, bool):
        return str(pages)
    if pages is not None and not isinstance(pages, str):
        raise ToolCallError(f'pages must be text such as "1-3,7". {RANGES}')
    if pages is None or not pages.strip():
        return None
    return pages.strip()


def _refuse_misfits(
    operation: str, count: int, pages: str | None, angle: object
) -> None:
    """Each operation's own needs, said before any file is read."""
    if operation == "merge":
        if count < 2:
            raise ToolCallError(
                "Merge needs at least two PDFs, in document_ids, artifact_ids or both."
            )
        if pages is not None:
            raise ToolCallError(
                "pages is not for merge: extract the pages from each PDF first, "
                "then merge the new PDFs."
            )
    elif count != 1:
        raise ToolCallError(
            f"{operation.capitalize()} works on one PDF: name one in document_ids "
            "or artifact_ids."
        )
    if operation in ("extract", "reorder") and pages is None:
        raise ToolCallError(f"{operation.capitalize()} needs pages. {RANGES}")
    if operation == "rotate" and angle not in QUARTER_TURNS:
        raise ToolCallError("Rotate needs angle: 90, 180 or 270 degrees clockwise.")
    if operation != "rotate" and angle is not None:
        raise ToolCallError("angle is only for rotate.")


def _made(
    operation: str,
    inputs: list[PdfInput],
    pages: str | None,
    angle: Any,
    title: object,
) -> list[MadePdf]:
    opened = readers(inputs)
    first, reader = inputs[0], opened[0]
    count = len(reader.pages)
    if operation == "merge":
        total = sum(len(r.pages) for r in opened)
        data = merge(opened)
        return [
            MadePdf(
                derived_title(title, first.title, "merged"), data, total, [1, 2, 3, 4]
            )
        ]
    if operation == "split":
        groups = (
            page_groups(pages, count) if pages else [[n] for n in range(1, count + 1)]
        )
        if len(groups) > MAX_PARTS:
            raise ToolCallError(
                f"That makes {len(groups)} PDFs; split into at most {MAX_PARTS}, "
                'with ranges such as "1-10,11-20".'
            )
        # Each part's title ends with its pages, the title asked for or not.
        asked = derived_title(title, first.title, "")
        base = asked if isinstance(title, str) and title.strip() else first.title
        return [
            MadePdf(
                derived_title(None, base, _named(group)),
                data,
                len(group),
                [1],
            )
            for group, data in zip(groups, split(reader, groups), strict=True)
        ]
    numbers = page_numbers(pages, count)
    if operation == "extract":
        suffix = (
            f"page {numbers[0]}"
            if len(numbers) == 1
            else "pages " + "".join(pages.split())
        )
        return [
            MadePdf(
                derived_title(title, first.title, suffix),
                extract(reader, numbers),
                len(numbers),
                [1, 2, 3, 4],
            )
        ]
    if operation == "rotate":
        turned = list(dict.fromkeys(numbers))
        return [
            MadePdf(
                derived_title(title, first.title, "rotated"),
                rotate(reader, turned, angle),
                count,
                turned,
            )
        ]
    return [
        MadePdf(
            derived_title(title, first.title, "reordered"),
            reorder(reader, numbers),
            count,
            [1, 2, 3, 4],
        )
    ]


def _named(group: list[int]) -> str:
    """A part's pages, as its title ends."""
    if len(group) == 1:
        return f"page {group[0]}"
    return f"pages {group[0]}-{group[-1]}"


PDF_PAGES = Tool(listing=LISTING, run=run, waits=True)
