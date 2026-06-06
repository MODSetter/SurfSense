"""Entry-point based plugin loader for SurfSense agent middleware.

LangChain's :class:`AgentMiddleware` ABC already covers the practical
surface most plugins need (``before_agent`` / ``before_model`` /
``wrap_tool_call`` / their async counterparts), so a SurfSense-specific
plugin protocol would be redundant. We just need a way to discover and
admit third-party middleware safely.

A plugin is therefore just an installable Python package that registers a
factory callable under the ``surfsense.plugins`` entry-point group:

.. code-block:: toml

    # in a plugin package's pyproject.toml
    [project.entry-points."surfsense.plugins"]
    year_substituter = "my_plugin:make_middleware"

The factory has the signature ``Callable[[PluginContext], AgentMiddleware]``.
It receives a small, sanitized :class:`PluginContext` with the IDs and the
LLM the plugin is allowed to talk to — and **never** raw secrets, DB
sessions, or other connectors.

## Trust model

Plugins are loaded **only if** their entry-point ``name`` appears in
``allowed_plugins`` (admin-controlled, sourced from
``global_llm_config.yaml`` or :func:`load_allowed_plugin_names_from_env`).
There is **no env-driven auto-load**. A plugin failure is logged and
isolated; it does not break agent construction.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Iterable
from importlib.metadata import entry_points
from typing import TYPE_CHECKING

from langchain.agents.middleware import AgentMiddleware

if TYPE_CHECKING:  # pragma: no cover - type-only
    from langchain_core.language_models import BaseChatModel

    from app.db import ChatVisibility


logger = logging.getLogger(__name__)


PLUGIN_ENTRY_POINT_GROUP = "surfsense.plugins"


class PluginContext(dict):
    """Sanitized DI bag handed to each plugin factory.

    Backed by ``dict`` so plugins can inspect the keys they care about
    without coupling to a concrete dataclass shape. Required keys:

    * ``search_space_id`` (int)
    * ``user_id`` (str | None)
    * ``thread_visibility`` (:class:`app.db.ChatVisibility`)
    * ``llm`` (:class:`langchain_core.language_models.BaseChatModel`)

    The context **never** carries DB sessions, raw secrets, or other
    connectors. If a future plugin genuinely needs DB access, that
    integration goes through a rate-limited service interface, not
    through this bag.
    """

    @classmethod
    def build(
        cls,
        *,
        search_space_id: int,
        user_id: str | None,
        thread_visibility: ChatVisibility,
        llm: BaseChatModel,
    ) -> PluginContext:
        return cls(
            search_space_id=search_space_id,
            user_id=user_id,
            thread_visibility=thread_visibility,
            llm=llm,
        )


def load_plugin_middlewares(
    ctx: PluginContext,
    allowed_plugin_names: Iterable[str],
) -> list[AgentMiddleware]:
    """Discover, allowlist-filter, and instantiate plugin middleware.

    For each entry-point in :data:`PLUGIN_ENTRY_POINT_GROUP` whose name is
    in ``allowed_plugin_names``, load the factory and call it with ``ctx``.
    The factory's return value must be an :class:`AgentMiddleware` instance;
    anything else is logged and skipped.

    Errors are isolated — a plugin that raises during ``ep.load()`` or
    factory invocation is logged at ``ERROR`` and ignored. Agent
    construction continues with whatever plugins did succeed.
    """
    allowed = {name for name in allowed_plugin_names if name}
    if not allowed:
        return []

    out: list[AgentMiddleware] = []
    try:
        eps = entry_points(group=PLUGIN_ENTRY_POINT_GROUP)
    except Exception:  # pragma: no cover - defensive (entry_points is robust)
        logger.exception("Failed to enumerate plugin entry points")
        return []

    for ep in eps:
        if ep.name not in allowed:
            logger.info("Skipping non-allowlisted plugin %s", ep.name)
            continue
        try:
            factory = ep.load()
        except Exception:
            logger.exception("Failed to load plugin %s", ep.name)
            continue
        try:
            mw = factory(ctx)
        except Exception:
            logger.exception("Plugin %s factory raised", ep.name)
            continue
        if not isinstance(mw, AgentMiddleware):
            logger.warning(
                "Plugin %s returned %s, expected AgentMiddleware; skipping",
                ep.name,
                type(mw).__name__,
            )
            continue
        out.append(mw)
        logger.info("Loaded plugin %s as %s", ep.name, type(mw).__name__)
    return out


def load_allowed_plugin_names_from_env() -> set[str]:
    """Read ``SURFSENSE_ALLOWED_PLUGINS`` (comma-separated) into a set.

    Provided as a thin convenience for deployments that don't surface plugins
    through ``global_llm_config.yaml`` yet. Whitespace is stripped and empty
    entries are dropped.
    """
    raw = os.environ.get("SURFSENSE_ALLOWED_PLUGINS", "").strip()
    if not raw:
        return set()
    return {token.strip() for token in raw.split(",") if token.strip()}


__all__ = [
    "PLUGIN_ENTRY_POINT_GROUP",
    "PluginContext",
    "load_allowed_plugin_names_from_env",
    "load_plugin_middlewares",
]
