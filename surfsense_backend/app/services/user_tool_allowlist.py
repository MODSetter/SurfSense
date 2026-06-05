"""User-scoped trusted-tools list backed by ``SearchSourceConnector.config``.

Storage is per ``(user_id, search_space_id, connector_id)`` under
``connector.config['trusted_tools']``. The list only ever encodes
``allow`` decisions; coded ``deny`` rules cannot be overridden here.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.agents.chat.multi_agent_chat.constants import (
    CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS,
)
from app.agents.chat.multi_agent_chat.shared.permissions import Rule, Ruleset
from app.db import SearchSourceConnector, async_session_maker

logger = logging.getLogger(__name__)

_TRUSTED_TOOLS_KEY = "trusted_tools"

TrustedToolSaver = Callable[[int, str], Awaitable[None]]


async def _load_owned_connector(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    connector_id: int,
) -> SearchSourceConnector | None:
    """Return the connector iff owned by ``user_id``, else ``None``."""
    result = await session.execute(
        select(SearchSourceConnector).where(
            SearchSourceConnector.id == connector_id,
            SearchSourceConnector.user_id == user_id,
        )
    )
    return result.scalars().first()


def _read_trusted(connector: SearchSourceConnector) -> list[str]:
    config = connector.config or {}
    raw = config.get(_TRUSTED_TOOLS_KEY, [])
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if isinstance(item, str)]


def _write_trusted(connector: SearchSourceConnector, trusted: list[str]) -> None:
    config = dict(connector.config or {})
    config[_TRUSTED_TOOLS_KEY] = trusted
    connector.config = config
    flag_modified(connector, "config")


async def add_user_trust(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    connector_id: int,
    tool_name: str,
) -> list[str]:
    """Append ``tool_name`` to the connector's trusted list; raise ``LookupError`` if not owned."""
    connector = await _load_owned_connector(
        session, user_id=user_id, connector_id=connector_id
    )
    if connector is None:
        raise LookupError(f"connector {connector_id} not found for user {user_id}")

    trusted = _read_trusted(connector)
    if tool_name not in trusted:
        trusted.append(tool_name)
        _write_trusted(connector, trusted)
        await session.flush()
    return trusted


async def remove_user_trust(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    connector_id: int,
    tool_name: str,
) -> list[str]:
    """Remove ``tool_name`` from the connector's trusted list; raise ``LookupError`` if not owned."""
    connector = await _load_owned_connector(
        session, user_id=user_id, connector_id=connector_id
    )
    if connector is None:
        raise LookupError(f"connector {connector_id} not found for user {user_id}")

    trusted = _read_trusted(connector)
    if tool_name in trusted:
        trusted = [t for t in trusted if t != tool_name]
        _write_trusted(connector, trusted)
        await session.flush()
    return trusted


async def fetch_user_allowlist_rulesets(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    search_space_id: int,
) -> dict[str, Ruleset]:
    """Project the user's trusted tools into per-subagent ``allow`` rulesets.

    Subagents with no trusted tools are absent from the result —
    callers must treat ``missing == empty``.
    """
    result = await session.execute(
        select(
            SearchSourceConnector.id,
            SearchSourceConnector.connector_type,
            SearchSourceConnector.config,
        ).where(
            SearchSourceConnector.user_id == user_id,
            SearchSourceConnector.search_space_id == search_space_id,
        )
    )

    rules_by_subagent: dict[str, list[Rule]] = defaultdict(list)
    for _connector_id, connector_type, config in result.all():
        subagent = CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS.get(str(connector_type))
        if subagent is None:
            continue

        cfg = config or {}
        raw = cfg.get(_TRUSTED_TOOLS_KEY, [])
        if not isinstance(raw, list):
            continue

        for tool in raw:
            if not isinstance(tool, str) or not tool:
                continue
            rules_by_subagent[subagent].append(
                Rule(permission=tool, pattern="*", action="allow")
            )

    return {
        subagent: Ruleset(rules=rules, origin=f"user_allowlist:{subagent}")
        for subagent, rules in rules_by_subagent.items()
    }


def make_trusted_tool_saver(user_id: uuid.UUID) -> TrustedToolSaver:
    """Bind ``user_id`` into a saver closure; failures are logged, never raised."""

    async def trusted_tool_saver(connector_id: int, tool_name: str) -> None:
        try:
            async with async_session_maker() as session:
                await add_user_trust(
                    session,
                    user_id=user_id,
                    connector_id=connector_id,
                    tool_name=tool_name,
                )
                await session.commit()
        except LookupError as exc:
            logger.warning("trusted-tool save skipped: %s", exc)
        except Exception:
            logger.exception(
                "trusted-tool save failed for connector=%s tool=%s",
                connector_id,
                tool_name,
            )

    return trusted_tool_saver


__all__ = [
    "TrustedToolSaver",
    "add_user_trust",
    "fetch_user_allowlist_rulesets",
    "make_trusted_tool_saver",
    "remove_user_trust",
]
