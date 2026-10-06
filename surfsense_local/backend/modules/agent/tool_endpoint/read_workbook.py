"""The read tool over a workbook: a ticked .xlsx or .xlsm source, or a revised copy of one, as its cell map."""

from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.script_page import PAGE_BYTES
from modules.agent.tool_endpoint.tool import ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.artifacts.models import Artifact
from modules.artifacts.revised_copies.cell_map import (
    CellMap,
    SheetNotFoundError,
    cell_map,
)
from modules.artifacts.revised_copies.formats import revisable_format
from modules.artifacts.revised_copies.revision import revision_of
from modules.artifacts.revised_copies.versions import primary_path, versions_of
from modules.artifacts.script_documents.version import version_of
from modules.documents.models import Document, DocumentStatus, DocumentType
from modules.documents.original_file import original_path

WORKBOOK_SUFFIXES = (".xlsx", ".xlsm")
CELLS_SENTENCE = (
    "Each cell below is address = its value, text in quotes, or its formula as "
    "written, not its result."
)


def read_source_workbook(
    session: Session, scope: TurnScope, document_id: int, arguments: dict[str, Any]
) -> str:
    """A ticked workbook source's cells, read from the file the user uploaded."""
    scope.refuse_unselected([document_id])
    document = session.get(Document, document_id)
    if (
        document is None
        or document.workspace_id != scope.workspace_id
        or document.document_type is not DocumentType.FILE
    ):
        raise ToolCallError(f"There is no source file {document_id} in this workspace.")
    path = original_path(document)
    if path is None or path.suffix.lower() not in WORKBOOK_SUFFIXES:
        raise ToolCallError(
            f'Source {document_id} ("{document.title}") is no workbook. '
            "surfsense_read_document reads a workbook source's cells (.xlsx, .xlsm); "
            "read any other source's text in sources/."
        )
    opening = (
        f'Source {document_id} ("{document.title}") is a workbook. {CELLS_SENTENCE} '
        f"Revise it with surfsense_revise_document and document_id {document_id}."
    )
    session.rollback()  # reads only; a big workbook takes seconds, past other writers' wait
    return _mapped(path, opening, arguments)


def read_revised_workbook(
    session: Session, scope: TurnScope, named: Artifact, arguments: dict[str, Any]
) -> str:
    """The cells of the revised copy's newest ready version, which the next edit starts from."""
    revision = revision_of(named.artifact_metadata) or {}
    source_name = str(revision.get("source_name", ""))
    found = revisable_format(source_name)
    if found is None or found.format != "xlsx":
        raise ToolCallError(
            f"Artifact {named.id} is a revised copy of {source_name} and keeps no "
            "script: only a revised workbook's cells are read here."
        )
    version = version_of(named.artifact_metadata)
    assert version is not None  # every revised copy's version has one
    ready = next(
        (
            v
            for v in versions_of(session, scope.workspace_id, version.root)
            if v.document.status is DocumentStatus.READY
        ),
        None,
    )
    path = primary_path(ready) if ready is not None else None
    if ready is None or path is None:
        raise ToolCallError(
            f"Artifact {named.id}'s revised copy has no ready version to read."
        )
    number = version_of(ready.artifact_metadata).number
    opening = (
        f'Artifact {ready.id}, version {number} of the revised copy of "{source_name}", '
        f"is a workbook. {CELLS_SENTENCE} Revise it with surfsense_revise_document "
        f"and artifact_id {ready.id}."
    )
    session.rollback()  # reads only; a big workbook takes seconds, past other writers' wait
    return _mapped(path, opening, arguments)


def _mapped(path: Path, opening: str, arguments: dict[str, Any]) -> str:
    sheet = arguments.get("sheet")
    if sheet is not None and not isinstance(sheet, str):
        raise ToolCallError("sheet must be a sheet's name, or left out.")
    offset = arguments.get("offset")
    offset = 1 if offset is None else offset
    if not isinstance(offset, int) or isinstance(offset, bool) or offset < 1:
        raise ToolCallError(
            "offset must be a row number from 1, or left out to start at the top."
        )
    try:
        mapped = cell_map(path, sheet or None, offset, PAGE_BYTES)
    except SheetNotFoundError as missing:
        sheets = ", ".join(f'"{name}"' for name in missing.sheets)
        raise ToolCallError(
            f'There is no sheet "{missing.sheet}". Its sheets: {sheets}.'
        ) from missing
    except Exception as unreadable:  # openpyxl raises many kinds on a broken file
        raise ToolCallError(
            f"{path.name} could not be read as a workbook: {unreadable}"
        ) from unreadable
    return "\n".join([opening, *_sections(mapped)])


def _sections(mapped: CellMap) -> list[str]:
    lines: list[str] = []
    for sheet in mapped.sheets:
        lines.append("")
        if sheet.used_range is None:
            lines.append(f'Sheet "{sheet.name}" is empty.')
            continue
        lines.append(f'Sheet "{sheet.name}", used range {sheet.used_range}:')
        lines.extend(sheet.lines)
        if sheet.left_out:
            cells = "cell" if sheet.left_out == 1 else "cells"
            lines.append(f"{sheet.left_out:,} more {cells} not shown.")
    if mapped.named or mapped.unnamed:
        lines.append("")
        lines.append(_not_read(mapped))
    cut = mapped.cut
    if cut is not None:
        lines.append("")
        if cut.row_too_wide:
            lines.append(
                f'Row {cut.row} of sheet "{cut.sheet}" holds more cells than one map '
                f"shows: those from {cut.column}{cut.row} on are left out. Call again "
                f'with sheet "{cut.sheet}" and offset {cut.row + 1} to read on from '
                "the next row."
            )
        else:
            lines.append(
                f'The map was cut at row {cut.row} of sheet "{cut.sheet}". Call again '
                f'with sheet "{cut.sheet}" and offset {cut.row} to read on from there, '
                "or with another sheet's name."
            )
    return lines


def _not_read(mapped: CellMap) -> str:
    count = len(mapped.named) + mapped.unnamed
    sheets = "sheet" if count == 1 else "sheets"
    names = ", ".join(f'"{name}"' for name in mapped.named)
    if mapped.unnamed:
        names += f" and {mapped.unnamed:,} more"
    return (
        f"{count:,} more {sheets} not read here: {names}. Read one with sheet and "
        "its name."
    )
