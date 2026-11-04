"""The confirm tool: when the user asks, confirm a finished job run's suggested answers as the next
version of its revised copy, the one step a person takes once they have checked them.

Offered only while a job pack is installed. The version is a Studio job; the tool waits for it
as long as a call may last.
"""

import time
from typing import Any

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.job_outcome import wait_for_outcome
from modules.agent.tool_endpoint.render_document import CALL_SECONDS, WAIT_SECONDS
from modules.agent.tool_endpoint.rendered_label import (
    RenderedArtifact,
    first_line,
    queued_line,
)
from modules.agent.tool_endpoint.tool import Tool, ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.artifacts.script_documents.version import version_of
from modules.documents.models import DocumentStatus
from modules.jobs.packs.installed import installed_packs
from modules.jobs.runs.confirm import confirm_suggestions
from modules.jobs.runs.start import JobRunRefusedError

TOOL_NAME = "confirm_job_suggestions"


def confirm_listing() -> dict[str, Any] | None:
    """The tool as the model is shown it; None while no job pack is installed."""
    if not installed_packs():
        return None
    return {
        "name": TOOL_NAME,
        "description": (
            "Only when the user asks you to: confirm the suggested answers a finished "
            "SurfSense job run left to a person, such as N/A for a control a provider runs "
            "for the firm. Each is written as the job would have written it, in a new "
            "version of the run's revised copy in Studio. Never confirm them unasked."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "artifact_id": {
                    "type": "integer",
                    "description": "The job run's revised copy, as the run reported it.",
                },
                "cells": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        'The answer cells to confirm, as "Sheet!B12"; leave out to '
                        "confirm every suggestion not yet confirmed."
                    ),
                },
            },
            "required": ["artifact_id"],
        },
    }


def run(session: Session, scope: TurnScope, arguments: dict[str, Any]) -> str:
    deadline = time.monotonic() + CALL_SECONDS
    artifact_id = arguments.get("artifact_id")
    if not isinstance(artifact_id, int) or isinstance(artifact_id, bool):
        raise ToolCallError("Give artifact_id, the job run's revised copy.")
    cells = _cells(arguments.get("cells"))
    try:
        made = confirm_suggestions(session, scope.workspace_id, artifact_id, cells)
    except JobRunRefusedError as refused:
        session.rollback()
        raise ToolCallError(str(refused)) from refused
    made_id = made.id
    # Read before the commit: the first line names the version, so the thread links it.
    numbered = version_of(made.artifact_metadata)
    rendered = RenderedArtifact(
        made_id, made.document.title, numbered.number if numbered is not None else 1
    )
    # Making the version committed it; the run's record of what it confirms commits here.
    session.commit()
    outcome = wait_for_outcome(
        session, made_id, min(WAIT_SECONDS, deadline - time.monotonic())
    )
    named = f"The confirmed version (artifact {made_id})"
    if outcome is None:
        raise ToolCallError(f"{named} was deleted before it was made.")
    if outcome.status is DocumentStatus.FAILED:
        raise ToolCallError(
            f"{named} failed: {outcome.error_message or 'no reason given'}"
        )
    if outcome.status is DocumentStatus.CANCELLED:
        return (
            f"{named} was cancelled in Studio, so its suggestions are still waiting to be "
            "confirmed. Ask the user before confirming them again."
        )
    if outcome.status is not DocumentStatus.READY:
        return (
            f"{queued_line(rendered)}\n{named} is still being made. It appears in Studio "
            "when it is done."
        )
    return (
        f"{first_line(rendered)}\nDone: {named} is in Studio, with the suggested answers "
        "written in their cells and marked confirmed on the exceptions sheet."
    )


def _cells(value: object) -> list[tuple[str, str]] | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        raise ToolCallError('cells is a list like ["Sheet1!B12"], or left out.')
    cells = []
    for text in value:
        sheet, _, cell = text.rpartition("!")
        if not sheet or not cell:
            raise ToolCallError(f'"{text}" is not a cell; write it as "Sheet1!B12".')
        cells.append((sheet.strip("'"), cell))
    return cells


CONFIRM_JOB = Tool(
    listing={"name": TOOL_NAME, "description": "", "inputSchema": {"type": "object"}},
    run=run,
    waits=True,
)
