"""The analysis tool: run a pandas script over ticked spreadsheets and CSVs, and return what it found.

The Studio worker runs it in the script runner; the tool waits, since the
model fixes its script from the error, as it does a document's.
"""

import logging
from pathlib import Path
from typing import Any

from huey.exceptions import ResultTimeout, TaskException
from sqlalchemy.orm import Session

from modules.agent.data_analysis.chart_names import (
    CHART_SUFFIX,
    chart_name,
    new_run,
    run_folder,
)
from modules.agent.data_analysis.source_files import (
    SourceRefusedError,
    analysis_inputs,
)
from modules.agent.data_analysis.table_preview import table_preview
from modules.agent.data_analysis.task import analyse_data
from modules.agent.opencode_config import CONFIG_FILE, declares_image_input
from modules.agent.previews.inline_images import inline_image
from modules.agent.thread_folder.layout import SOURCES
from modules.agent.tool_endpoint.failed_renders import (
    FailedRunError,
    stop_after_three_failures,
)
from modules.agent.tool_endpoint.registration import SERVER, TOOL_CALL_SECONDS
from modules.agent.tool_endpoint.rendered_label import TOOL_NAME as RENDER_TOOL
from modules.agent.tool_endpoint.tool import (
    InlineImage,
    Tool,
    ToolCallError,
    ToolResult,
)
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.artifacts.script_documents.service import SCRIPT_CHARS
from shared.config import get_storage_settings
from worker.document_script.analysis_folder import MANIFEST_NAME
from worker.document_script.analysis_run import AnalysisRun
from worker.document_script.kept_outputs import MAX_FILE_BYTES, MAX_FILES

logger = logging.getLogger(__name__)

TOOL_NAME = "analyze_data"
TITLE_CHARS = 200
# The call answers inside the registration's timeout, as a render's does.
CALL_SECONDS = TOOL_CALL_SECONDS - 10
# Enough for the numbers asked for; a frame printed whole is cut here. opencode
# moves a result past 2,000 lines or 50 KB where every thread's agent reads it.
STDOUT_CHARS = 6000
STDOUT_LINES = 200
# A failure's error line, and the traceback's last lines that fit after it.
ERROR_CHARS = 2000
TRACEBACK_CHARS = 6000
NAMED_LEFT_OUT = 20
TABLES_SHOWN = 5
# With the printout, under opencode's 50 KB, which counts bytes: a Chinese
# cell takes three a character.
TABLES_BYTES = 24_000
# Each image costs about 1,000 tokens on every later request of the turn.
CHARTS_SHOWN = 6
RUNS = "analysis runs"
STOP_RULE = (
    "If this is your third failed run for this request, stop and tell the user "
    "what failed."
)

LISTING: dict[str, Any] = {
    "name": TOOL_NAME,
    "description": (
        "Run a Python script with pandas, numpy and matplotlib over spreadsheet "
        "and CSV sources (.xlsx, .csv, .tsv) to compute totals, trends or "
        "comparisons, and draw charts. Load the surfsense-data skill first. "
        "Copies of the sources are in INPUT_DIR under their file names, with "
        f"{MANIFEST_NAME} naming each one's source; save tables as .csv and charts "
        "as .png in OUTPUT_DIR. Waits for the run, then returns what the script "
        "printed, each saved table's first rows, each chart's name to place it "
        f"with {SERVER}_{RENDER_TOOL}'s images and the charts as images, or the "
        "error to fix."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": (
                    "What the analysis finds out, in a few words, as the user sees it."
                ),
            },
            "document_ids": {
                "type": "array",
                "items": {"type": "integer"},
                "description": (
                    "The spreadsheet and CSV sources to read: the number in "
                    f"brackets at the end of each file name in {SOURCES}/."
                ),
            },
            "script": {
                "type": "string",
                "description": (
                    "The whole Python script. It reads the files in the folder in "
                    "the INPUT_DIR environment variable, prints its findings, and "
                    "saves tables and charts in OUTPUT_DIR."
                ),
            },
        },
        "required": ["title", "document_ids", "script"],
    },
}


def analyse(
    session: Session, scope: TurnScope, arguments: dict[str, Any]
) -> str | ToolResult:
    """Copy the named sources for the worker, wait for its run, and say what it found."""
    title, document_ids, script = _request(arguments)
    scope.refuse_unselected(document_ids)
    try:
        inputs = analysis_inputs(session, scope.workspace_id, document_ids)
    except SourceRefusedError as refused:
        raise ToolCallError(str(refused)) from refused
    # The run takes up to two minutes; no transaction may stay open meanwhile.
    session.commit()
    run = new_run()
    keep_in = run_folder(scope.folder, run)
    queued = analyse_data(script, inputs, str(keep_in))
    try:
        outcome: AnalysisRun = queued.get(
            blocking=True, timeout=CALL_SECONDS, max_delay=0.5
        )
    except ResultTimeout:
        queued.revoke()
        raise ToolCallError(
            f'Analysis "{title}" did not finish within {CALL_SECONDS} s: SurfSense\'s '
            "Studio worker is busy or not running. Tell the user, and do not run it "
            "again in this request."
        ) from None
    except TaskException as error:
        logger.error("analysis %s failed in the worker: %s", run, error)
        raise ToolCallError(
            f'Analysis "{title}" could not run: {error.metadata.get("error")}. Tell '
            "the user what failed."
        ) from None
    if not outcome.ok:
        raise FailedRunError(_failed(title, outcome))
    return _found(scope.folder, run, title, outcome, keep_in)


def _request(arguments: dict[str, Any]) -> tuple[str, list[int], str]:
    """The call's arguments, refused in a sentence naming the one to fix."""
    title = arguments.get("title")
    document_ids = arguments.get("document_ids")
    script = arguments.get("script")
    if not isinstance(title, str) or not 1 <= len(title.strip()) <= TITLE_CHARS:
        raise ToolCallError(
            f"Give the analysis a title of 1 to {TITLE_CHARS} characters."
        )
    if (
        not isinstance(document_ids, list)
        or not document_ids
        or not all(isinstance(i, int) and not isinstance(i, bool) for i in document_ids)
    ):
        raise ToolCallError(
            "Name at least one source in document_ids: the number in brackets at "
            f"the end of its file name in {SOURCES}/."
        )
    if not isinstance(script, str) or not script.strip() or len(script) > SCRIPT_CHARS:
        raise ToolCallError(
            f"Give the script: Python of 1 to {SCRIPT_CHARS:,} characters that reads "
            "INPUT_DIR and saves what it makes in OUTPUT_DIR."
        )
    return " ".join(title.split()), document_ids, script


def _found(
    folder: Path, run: str, title: str, outcome: AnalysisRun, keep_in: Path
) -> str | ToolResult:
    """What it printed, its tables, its charts by name and as images, and where all of it is kept."""
    kept_at = keep_in.relative_to(folder).as_posix()
    tables = [name for name in outcome.kept if Path(name).suffix in {".csv", ".tsv"}]
    charts = [name for name in outcome.kept if Path(name).suffix == CHART_SUFFIX]
    others = [
        name for name in outcome.kept if name not in tables and name not in charts
    ]
    parts = [f"Analysis run {run}: {title}", _printed(outcome, "It printed:")]
    shown, room = 0, TABLES_BYTES
    for name in tables[:TABLES_SHOWN]:
        preview = table_preview(keep_in / name)
        room -= len(preview.encode())
        if room < 0:
            break
        parts.append(preview)
        shown += 1
    if len(tables) > shown:
        parts.append(f"{len(tables) - shown} more tables are kept; open one with read.")
    images: tuple[InlineImage, ...] = ()
    if charts:
        chart_text, images = _charts(run, charts, keep_in, kept_at)
        parts.append(chart_text)
    if others:
        parts.append(f"Also kept: {', '.join(others)}.")
    if outcome.left_out:
        left_out = ", ".join(outcome.left_out[:NAMED_LEFT_OUT])
        if len(outcome.left_out) > NAMED_LEFT_OUT:
            left_out += f" and {len(outcome.left_out) - NAMED_LEFT_OUT:,} more"
        parts.append(
            f"Not kept: {left_out}. Only .csv, .tsv, .png, .jpg, "
            ".svg, .xlsx, .json and .txt files at the top of OUTPUT_DIR are kept, at "
            f"most {MAX_FILES}, each at most {MAX_FILE_BYTES // (1024 * 1024)} MB."
        )
    if outcome.kept:
        parts.append(f"Everything it saved is in {kept_at}/.")
    else:
        parts.append("It saved no files in OUTPUT_DIR.")
    text = "\n\n".join(parts)
    return ToolResult(text, images) if images else text


def _printed(outcome: AnalysisRun, heading: str) -> str:
    printed = outcome.stdout.strip("\n")
    if not printed:
        return f"{heading} nothing."
    lines = printed[:STDOUT_CHARS].split("\n")
    shown = "\n".join(lines[:STDOUT_LINES])
    if len(lines) > STDOUT_LINES:
        cut_at = f"{STDOUT_LINES} lines"
    elif len(printed) > STDOUT_CHARS or outcome.stdout_cut > 0:
        cut_at = f"{STDOUT_CHARS:,} characters"
    else:
        cut_at = None
    note = (
        f"\n[Printed output cut after {cut_at}: print only the numbers you need, "
        "or save a table.]"
        if cut_at
        else ""
    )
    return f"{heading}\n{shown}{note}"


def _charts(
    run: str, charts: list[str], keep_in: Path, kept_at: str
) -> tuple[str, tuple[InlineImage, ...]]:
    """Each chart's name for a document, and the first CHARTS_SHOWN as images when the model reads them."""
    lines = [
        f"Charts, by the name to pass in {SERVER}_{RENDER_TOOL}'s images (each is "
        "then at IMAGES_DIR/<name>.png):"
    ]
    lines += [f"- {chart_name(run, name)} ({kept_at}/{name})" for name in charts]
    if not declares_image_input(get_storage_settings().agent_dir / CONFIG_FILE):
        lines.append(
            "No chart images: the selected model cannot read images. Check the "
            "numbers the script printed instead."
        )
        return "\n".join(lines), ()
    images: list[InlineImage] = []
    shown: list[str] = []
    for name in charts[:CHARTS_SHOWN]:
        try:
            images.append(inline_image(keep_in / name))
        # A chart that will not encode costs that chart, never the run.
        except Exception:
            logger.exception("chart %s of analysis %s not attached", name, run)
            lines.append(f"{name} could not be attached; open it with read.")
            continue
        shown.append(name)
    if shown:
        lines.append(
            "These charts come with this result as images, in order: "
            f"{', '.join(shown)}. Look at each before you use it."
        )
    if len(charts) > CHARTS_SHOWN:
        lines.append("The other charts are not attached; open one with read.")
    return "\n".join(lines), tuple(images)


def _failed(title: str, outcome: AnalysisRun) -> str:
    """The error and traceback tail to fix the script from, what it printed first, and the stop rule."""
    parts = [f'Analysis "{title}" failed:\n{_error(outcome)}']
    if outcome.stdout.strip():
        parts.append(_printed(outcome, "Before failing it printed:"))
    parts.append(f"Fix the script and run it again.\n{STOP_RULE}")
    return "\n\n".join(parts)


def _error(outcome: AnalysisRun) -> str:
    """The error line, cut, then as many of the traceback's last lines as fit:
    they name the script's failing line."""
    error = outcome.error or "the script failed"
    if len(error) > ERROR_CHARS:
        error = f"{error[: ERROR_CHARS - 1]}…"
    kept: list[str] = []
    room = TRACEBACK_CHARS
    for line in reversed((outcome.traceback_tail or "").splitlines()):
        if len(line) > ERROR_CHARS:
            line = f"{line[: ERROR_CHARS - 1]}…"
        room -= len(line) + 1
        if room < 0:
            break
        kept.insert(0, line)
    return "\n".join([error, *kept])


ANALYZE_DATA = Tool(
    listing=LISTING, run=stop_after_three_failures(analyse, RUNS), waits=True
)
