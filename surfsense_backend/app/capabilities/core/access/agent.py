"""Generate the agent door from the capability registry (05).

One LangChain tool per verb; each runs the same thin adapter as the REST door
(``access/rest.py``): meter-gate -> executor -> charge. Every run is recorded to
the ``runs`` table (best-effort). Outputs that fit under ``RUN_OUTPUT_CHAR_CAP``
are returned inline; larger ones are stored and the model gets a char-budgeted
preview plus a ``run_<id>`` reference it can page with ``read_run``/``search_run``.
Those two read tools are appended to the tool list so every capability-using
subagent can follow a truncation reference without extra wiring.
"""

from __future__ import annotations

import json
import time

from langchain.tools import ToolRuntime
from langchain_core.messages import ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
from langgraph.types import Command

from app.capabilities.core.billing import charge_capability, gate_capability
from app.capabilities.core.progress import progress_scope
from app.capabilities.core.runs import (
    RUN_OUTPUT_CHAR_CAP,
    record_run,
    serialize_output,
)
from app.capabilities.core.store import all_capabilities
from app.capabilities.core.types import Capability, CapabilityContext
from app.db import async_session_maker
from app.services.web_crawl_credit_service import InsufficientCreditsError


def build_capability_tools(
    *,
    workspace_id: int,
    capabilities: list[Capability] | None = None,
) -> list[BaseTool]:
    """Emit one tool per verb (defaults to the whole registry), plus the run readers."""
    caps = capabilities if capabilities is not None else all_capabilities()
    tools = [_capability_tool(cap, workspace_id) for cap in caps]
    # Deferred import: the reader lives in the agents package (which imports from
    # here), so importing it lazily avoids an import-time cycle.
    from app.agents.chat.multi_agent_chat.subagents.shared.run_reader import (
        build_run_reader_tools,
    )

    tools.extend(build_run_reader_tools(workspace_id=workspace_id))
    return tools


def _current_thread_id() -> str | None:
    """Best-effort ``configurable.thread_id`` from the active LangGraph config."""
    try:
        from langgraph.config import get_config

        cfg = get_config()
        tid = (cfg.get("configurable") or {}).get("thread_id")
        return str(tid) if tid is not None else None
    except Exception:
        return None


def _capability_tool(capability: Capability, workspace_id: int) -> BaseTool:
    input_model = capability.input_schema
    unit = capability.billing_unit
    executor = capability.executor
    name = capability.name

    async def _run(runtime: ToolRuntime, **kwargs: object) -> dict | str | Command:
        payload = input_model(**kwargs)
        input_dump = payload.model_dump(exclude_none=True)
        thread_id = _current_thread_id()

        # A buffer-only reporter: coarse progress lands in ``runs.progress`` and,
        # because we're inside a LangGraph tool call, ``emit_progress`` also fires
        # ``scraper_progress`` custom events that surface on the chat thinking step.
        with progress_scope() as reporter:
            async with async_session_maker() as session:
                ctx = CapabilityContext(session=session, workspace_id=workspace_id)
                try:
                    await gate_capability(payload, unit, ctx)
                except InsufficientCreditsError as exc:
                    return str(exc)

                started = time.perf_counter()
                try:
                    output = await executor(payload)
                except Exception as exc:
                    duration_ms = int((time.perf_counter() - started) * 1000)
                    async with async_session_maker() as rec_session:
                        await record_run(
                            rec_session,
                            workspace_id=workspace_id,
                            capability=name,
                            origin="agent",
                            status="error",
                            input=input_dump,
                            error=str(exc),
                            thread_id=thread_id,
                            duration_ms=duration_ms,
                            progress=reporter.coarse,
                        )
                    raise

                duration_ms = int((time.perf_counter() - started) * 1000)
                cost_micros = await charge_capability(output, unit, ctx)

            serialized = serialize_output(output)
            async with async_session_maker() as rec_session:
                run_id = await record_run(
                    rec_session,
                    workspace_id=workspace_id,
                    capability=name,
                    origin="agent",
                    status="success",
                    serialized=serialized,
                    input=input_dump,
                    thread_id=thread_id,
                    duration_ms=duration_ms,
                    cost_micros=cost_micros,
                    progress=reporter.coarse,
                )

        # No stored run to cite: keep the legacy return shape, no citation.
        if run_id is None:
            if serialized.char_count <= RUN_OUTPUT_CHAR_CAP:
                return output.model_dump(exclude_none=True)
            return _build_preview(serialized, run_id)

        run_external_id = f"run_{run_id}"
        if serialized.char_count <= RUN_OUTPUT_CHAR_CAP:
            dump = output.model_dump(exclude_none=True)
            dump["run_id"] = run_external_id
            content = json.dumps(dump, ensure_ascii=False, default=str)
        else:
            content = _build_preview(serialized, run_id)

        # Deferred import: the citation spine imports from here; lazy avoids a cycle.
        from app.agents.chat.multi_agent_chat.shared.citations import load_registry
        from app.capabilities.core.access.run_citation import attach_run_citation

        registry = load_registry(getattr(runtime, "state", None))
        _, label = attach_run_citation(
            registry, run_external_id=run_external_id, capability=name
        )
        return Command(
            update={
                "messages": [
                    ToolMessage(
                        content=content + label,
                        tool_call_id=runtime.tool_call_id,
                    )
                ],
                "citation_registry": registry,
            }
        )

    # Un-stringify for StructuredTool's signature-based runtime injection.
    _run.__annotations__["runtime"] = ToolRuntime

    return StructuredTool.from_function(
        coroutine=_run,
        name=name.replace(".", "_"),
        description=capability.description,
        args_schema=input_model,
    )


def _build_preview(serialized, run_id: str | None) -> str:
    """Char-budgeted preview: whole JSONL items until the cap is spent."""
    lines = serialized.text.split("\n")
    preview_lines: list[str] = []
    used = 0
    for line in lines:
        cost = len(line) + 1
        if used + cost > RUN_OUTPUT_CHAR_CAP:
            break
        preview_lines.append(line)
        used += cost

    if not preview_lines and lines:
        # A single item larger than the cap: show a clipped head so the model
        # still sees the shape and can page/search for the rest.
        preview_lines = [lines[0][:RUN_OUTPUT_CHAR_CAP]]

    shown = len(preview_lines)
    preview = "\n".join(preview_lines)

    if run_id is None:
        return (
            f"{preview}\n\n...Showing {shown} of {serialized.item_count} items "
            f"({serialized.char_count} chars). Full output unavailable (storage error)."
        )
    return (
        f"{preview}\n\n...Showing {shown} of {serialized.item_count} items "
        f"({serialized.char_count} chars). Full run stored as run_{run_id}. Use "
        f"read_run('run_{run_id}', offset, limit) or search_run('run_{run_id}', "
        "pattern) to inspect the rest."
    )
