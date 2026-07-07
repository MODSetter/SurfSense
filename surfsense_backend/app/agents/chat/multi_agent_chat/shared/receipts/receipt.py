"""Receipt: structured handle returned by every mutating subagent tool.

Generalises the Hermes ``entry`` dict (see ``references/hermes-agent/tools/
delegate_tool.py:1663-1697``) for our 5 deliverable types + 15 connectors +
KB writes. The supervisor reads the Receipt to verify what actually happened
without round-tripping through LLM paraphrase.

**Why this lives under ``app.agents.chat.shared`` and not under either of the
two agent packages:** the Receipt is a *contract* shared between
``multi_agent_chat`` (where mutating tools emit it) and ``new_chat``
(where ``filesystem_state.SurfSenseFilesystemState`` declares the
``receipts`` reducer that accumulates it, and where
``middleware.kb_persistence`` emits its own KB-write receipts). Putting
the contract in either package would create a bidirectional import
between the two — see the commit that introduced this module for the
``ImportError`` chain it broke.

Each mutating tool wraps its native return shape into a Receipt via
:func:`make_receipt` (or builds one directly) and returns it under the
``"receipt"`` key alongside its existing payload. The subagent boundary
machinery in ``checkpointed_subagent_middleware.task_tool`` then folds
the receipt into the parent's ``receipts`` state via the append reducer.

The KB write path is the one exception: file-tool calls cannot emit a
durable receipt because the actual DB writes happen end-of-turn inside
:class:`app.agents.chat.multi_agent_chat.shared.middleware.kb_persistence.KnowledgeBasePersistenceMiddleware`.
KB tools therefore emit a *provisional* receipt with ``status="pending"``;
the persistence middleware flips it to ``"success"`` or ``"failed"``
before returning control to the parent.
"""

from __future__ import annotations

from typing import Any, Literal, TypedDict

# Subagent that emitted this receipt. ``mcp_discovery`` is the current
# connected-apps route; the per-connector literals below it are retained so
# historical receipts (persisted in old checkpoints) still type-check.
ReceiptRoute = Literal[
    "deliverables",
    "knowledge_base",
    "mcp_discovery",
    "notion",
    "slack",
    "gmail",
    "linear",
    "jira",
    "clickup",
    "confluence",
    "calendar",
    "luma",
    "airtable",
    "google_drive",
    "dropbox",
    "onedrive",
    "discord",
    "teams",
]

# Within-route kind of artefact / external resource the operation touched.
# Left as ``str`` rather than a giant union so each route file documents
# its own enum next to its tools.
ReceiptType = str

# Operation verb. Kept open for the same reason as ``ReceiptType``.
ReceiptOperation = str

# Pending = async backend (Celery podcast / video) that the orchestrator
# will surface progress for out of band; persistence-MW flipped this to
# ``success`` for KB writes that committed.
ReceiptStatus = Literal["success", "pending", "failed"]


class Receipt(TypedDict, total=False):
    """Structured per-mutation handle returned to the parent subagent.

    All fields are ``NotRequired`` (TypedDict ``total=False``) so each
    route's tool can populate only the fields it actually has — e.g. Gmail
    never sets ``verifiable_url`` because Gmail doesn't expose per-message
    URLs. The receipts state reducer treats missing keys as missing rather
    than ``null`` so we don't double-count.
    """

    route: ReceiptRoute
    """Subagent name. Lets the orchestrator filter ``state['receipts']``
    by route without re-deriving from ``type``."""

    type: ReceiptType
    """Within-route kind. e.g. for ``deliverables`` one of ``{report,
    podcast, video_presentation, resume, image}``; for ``notion`` ``page``;
    for ``slack`` ``message``."""

    operation: ReceiptOperation
    """Verb. e.g. ``generate`` (deliverables), ``create`` / ``update`` /
    ``delete`` (most connectors), ``send`` / ``post`` (chat), ``write_file``
    / ``edit_file`` / ``rm`` / ``rmdir`` / ``move_file`` / ``mkdir`` (KB)."""

    status: ReceiptStatus
    """``success`` / ``pending`` / ``failed``. The verification teaching
    in ``shared/snippets/verifiable_handle.md`` keys off this field."""

    external_id: str | None
    """Backend identifier. Report row id, Notion ``page_id``, Slack ``ts``,
    Gmail ``message_id``, Linear identifier, KB ``virtualPath``, etc.
    ``None`` only when the operation failed before the backend assigned one."""

    verifiable_url: str | None
    """URL the parent can crawl (via ``task(web_crawler, …)``) to verify the
    operation. ``None`` when no public URL exists (Gmail, KB, raw images
    stored in the DB)."""

    preview: str | None
    """Short snippet (~200 chars) of what was produced. First lines of
    a generated report's markdown, transcript opener for a podcast,
    thumbnail URL for an image. Lets the orchestrator decide whether to
    re-render in the UI without re-loading the artefact."""

    error: str | None
    """Filled iff ``status == "failed"``. Plain-text reason; the parent
    surfaces it in its own ``next_step``."""


def make_receipt(
    *,
    route: ReceiptRoute,
    type: str,
    operation: str,
    status: ReceiptStatus,
    external_id: str | None = None,
    verifiable_url: str | None = None,
    preview: str | None = None,
    error: str | None = None,
) -> Receipt:
    """Construct a :class:`Receipt` with non-``None`` fields only.

    Drops keys whose value is ``None`` so downstream consumers can use
    ``"verifiable_url" in receipt`` to distinguish "tool returned no URL"
    from "tool deliberately surfaced ``null``".
    """
    out: dict[str, Any] = {
        "route": route,
        "type": type,
        "operation": operation,
        "status": status,
    }
    if external_id is not None:
        out["external_id"] = external_id
    if verifiable_url is not None:
        out["verifiable_url"] = verifiable_url
    if preview is not None:
        out["preview"] = preview
    if error is not None:
        out["error"] = error
    return out  # type: ignore[return-value]


__all__ = [
    "Receipt",
    "ReceiptOperation",
    "ReceiptRoute",
    "ReceiptStatus",
    "ReceiptType",
    "make_receipt",
]
