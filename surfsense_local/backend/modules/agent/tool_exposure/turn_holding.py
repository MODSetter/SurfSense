"""What a turn of the opencode agent holds as it starts, and the catalogue that names the rest."""

import logging
from dataclasses import dataclass

from sqlalchemy.orm import Session
from starlette.concurrency import run_in_threadpool

from api.dependencies import transact
from modules.agent.opencode_client import OpencodeClient
from modules.agent.plugin_tools.turn_plugins import TurnPlugin, opencode_tool_name
from modules.agent.tool_exposure.held_tools import Asked, held_tools
from modules.agent.tool_exposure.holdings import Holding
from modules.agent.tool_exposure.ranking import Embed
from modules.agent.tool_exposure.thread_history import asked_of
from modules.agent.tool_exposure.tool_vectors import tool_vectors
from modules.agent.tool_exposure.turn_tools import TurnTools

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Starting:
    holding: Holding
    # SurfSense's server instructions: every ready plugin, when not all are held.
    catalogue: str


async def turn_holding(
    session: Session,
    client: OpencodeClient,
    session_id: str,
    plugins: list[TurnPlugin],
    servers: set[str],
    tools: TurnTools,
    message: str,
    mentioned: frozenset[str],
) -> Starting:
    asked = Asked(message, mentioned=mentioned)
    embed: Embed | None = None
    if tools.fit:
        chosen = [t.ready for t in tools.tools]
    else:
        # Only past the share: the thread's history and the embedder cost a read each.
        asked = asked_of(await client.messages(session_id), message, mentioned)
        embed = await transact(session, tool_vectors)
        chosen, embed = await _chosen(tools, asked, embed)
    holding = Holding(
        session_id=session_id,
        plugins=plugins,
        servers=servers | {p.name for p in plugins},
        held={opencode_tool_name(t.plugin_id, t.tool) for t in chosen},
        tools=tools.tools,
        asked=asked,
        embed=embed,
        limit=tools.limit,
    )
    return Starting(holding, tools.catalogue())


async def _chosen(
    tools: TurnTools, asked: Asked, embed: Embed | None
) -> tuple[list, Embed | None]:
    """The tools held, and the embedder, unless it could not run: the turn's growth
    then ranks by keyword alone rather than failing at every call."""
    try:
        held = await run_in_threadpool(
            held_tools, tools.tools, asked, tools.share, tools.limit, embed
        )
    except Exception:
        # An embedder that cannot run leaves the keyword leg, which still ranks.
        logger.warning("tools were ranked by keyword alone", exc_info=True)
        held = await run_in_threadpool(
            held_tools, tools.tools, asked, tools.share, tools.limit, None
        )
        return held.tools, None
    return held.tools, embed
