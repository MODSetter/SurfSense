"""The search tool: the chat's own search over the workspace's sources."""

from typing import Any

from sqlalchemy.orm import Session

from modules.agent.sources_folder import SOURCES, source_file_names
from modules.agent.tool_endpoint.passage_label import opening, without_passage_tags
from modules.agent.tool_endpoint.tool import Tool, ToolCallError
from modules.agent.tool_endpoint.turn_scope import TurnScope
from modules.embedding.active import EmbeddingNotChosenError, require_active_index
from shared.search import Hit, retrieve

# Before onboarding chooses an embedder, or while its files are missing.
_NOT_READY = (
    "SurfSense's search is not ready on this computer. Use grep on {files} instead."
)
_NO_MATCH = "No passage matched. Try other words, or grep {files}."

_NOTHING_SELECTED = (
    "No sources are selected for this request, so there is nothing to search. "
    "Ask the user to select the sources to use."
)

# Written out flat: small local models garble a schema that refers to definitions.
LISTING: dict[str, Any] = {
    "name": "search_sources",
    "description": (
        "Search the user's sources by meaning and by keyword. Returns up to 5 "
        "passages, each with its citation label, the file in sources/ it comes "
        "from, and its lines in that file."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "What to look for, in the user's own words or close to them.",
            }
        },
        "required": ["query"],
    },
}


def search(session: Session, scope: TurnScope, arguments: dict[str, Any]) -> str:
    """The passages that best match the query, among the files the turn may read."""
    query = arguments.get("query")
    if not isinstance(query, str) or not query.strip():
        raise ToolCallError("Give a query: the words or the question to look for.")
    selected = scope.selected()
    if selected is not None and not selected:
        return _NOTHING_SELECTED
    # Keep numpy/onnxruntime lazy, as the chat does.
    from modules.embedding.encoder import missing_files

    try:
        index = require_active_index(session)
    except EmbeddingNotChosenError as error:
        raise ToolCallError(_NOT_READY.format(files=_grep_in(selected))) from error
    if missing_files(index.spec):
        raise ToolCallError(_NOT_READY.format(files=_grep_in(selected)))
    files = source_file_names(session, scope.workspace_id)
    searched = [i for i in files if selected is None or i in selected]
    hits = retrieve(session, scope.workspace_id, query, document_ids=searched)
    if not hits:
        return _NO_MATCH.format(files=_grep_in(selected))
    return "\n\n".join(_passage(hit, files[hit.document_id]) for hit in hits)


def _grep_in(selected: frozenset[int] | None) -> str:
    """Where the model may grep instead: never the files of sources it may not use."""
    if selected is None:
        return f"the files in {SOURCES}/"
    return f"the selected sources' files in {SOURCES}/"


def _passage(hit: Hit, source_file: str) -> str:
    """One passage, labelled the way the agent is told to cite it."""
    lines = (
        f' lines="{hit.start_line}-{hit.end_line}"'
        if hit.start_line is not None and hit.end_line is not None
        else ""
    )
    text = without_passage_tags(hit.content).strip()
    return (
        f'{opening(hit.chunk_id)} source="{SOURCES}/{source_file}"{lines}>\n'
        f"{text}\n</passage>"
    )


SEARCH_SOURCES = Tool(listing=LISTING, run=search)
