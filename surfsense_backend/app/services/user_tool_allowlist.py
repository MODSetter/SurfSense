"""User-scoped tool allow-list backed by ``SearchSourceConnector.config``.

Stores the user's "always allow" preferences as a list of tool names under
``connector.config['trusted_tools']``. Storage is per
``(user_id, search_space_id, connector_id)`` — i.e. tied to a specific
connected account inside a specific workspace, exactly what the UI cares
about.

Callers split into two roles:

- **Writers** — the ``/connectors/.../trust-tool`` and ``/untrust-tool``
  HTTP routes, and the chat resume handler when it processes a
  ``{type: "always"}`` decision. Both call
  :func:`add_user_trust` / :func:`remove_user_trust`. The FE button is
  the upstream UI trigger but it talks to the routes, never to this
  module directly.
- **Reader** — the subagent compile path, which calls
  :func:`fetch_user_allowlist_rulesets` and layers the result after the
  subagent's coded ruleset. User ``allow`` rules then override coded
  ``ask`` via the rule engine's last-match-wins evaluation.

Coded ``deny`` rules are intentionally **not** overridable by this
allow-list — only ``ask`` can be promoted to ``allow``. The rule engine
enforces this naturally because user rules only ever emit ``allow``.
"""

from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.attributes import flag_modified

from app.agents.multi_agent_chat.constants import (
    CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS,
)
from app.agents.new_chat.permissions import Rule, Ruleset
from app.db import SearchSourceConnector

_TRUSTED_TOOLS_KEY = "trusted_tools"


async def _load_owned_connector(
    session: AsyncSession,
    *,
    user_id: uuid.UUID,
    connector_id: int,
) -> SearchSourceConnector | None:
    """Return a connector iff it belongs to ``user_id``, else ``None``.

    Ownership scoping is mandatory: the trust list mutates user-private
    data, callers must never write across user boundaries.
    """
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
    """Append ``tool_name`` to the connector's trusted list (idempotent).

    Returns the updated trusted-tools list. Raises ``LookupError`` when
    the connector does not exist or is not owned by ``user_id``.
    """
    connector = await _load_owned_connector(
        session, user_id=user_id, connector_id=connector_id
    )
    if connector is None:
        raise LookupError(
            f"connector {connector_id} not found for user {user_id}"
        )

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
    """Remove ``tool_name`` from the connector's trusted list (idempotent).

    Returns the updated trusted-tools list. Raises ``LookupError`` when
    the connector does not exist or is not owned by ``user_id``.
    """
    connector = await _load_owned_connector(
        session, user_id=user_id, connector_id=connector_id
    )
    if connector is None:
        raise LookupError(
            f"connector {connector_id} not found for user {user_id}"
        )

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
    """Project the user's trusted-tool lists into per-subagent rulesets.

    Walks every connector the user owns in this workspace, maps each
    ``connector_type`` to its consuming subagent via
    :data:`CONNECTOR_TYPE_TO_CONNECTOR_AGENT_MAPS`, and emits one
    ``Rule(permission=tool_name, pattern="*", action="allow")`` per
    trusted entry. Rules from different connector accounts feeding the
    same subagent (e.g. two Linear workspaces) are merged into one
    ruleset; duplicates are harmless under last-match-wins.

    Connectors whose type is not mapped (search APIs, Github, etc.) and
    connectors with empty trust lists contribute nothing. Subagents
    with no trusted tools are absent from the returned dict — callers
    should treat ``missing == empty``.
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


__all__ = [
    "add_user_trust",
    "fetch_user_allowlist_rulesets",
    "remove_user_trust",
]
