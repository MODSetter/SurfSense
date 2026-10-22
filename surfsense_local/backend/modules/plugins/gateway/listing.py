"""`list_tools`: the tools ready to be called, from what connected plugins recorded."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.plugins.gateway.qualified_name import qualified_name
from modules.plugins.gateway.ready_tool import ReadyTool
from modules.plugins.installed.models import (
    LICENSE_FAILURES,
    CheckFailure,
    InstalledPlugin,
    PluginSource,
    PluginTool,
)
from modules.plugins.installed.plugin_hosts import hosts_not_allowed
from modules.plugins.installed.third_party import third_party_on
from modules.plugins.lists.registry.delisted import delisted_reason, delisted_reasons
from modules.plugins.remote.mcp_client.transports import recorded_on_sse
from modules.plugins.remote.sign_in.oauth.oauth_credential import OAUTH


def list_tools(session: Session) -> list[ReadyTool]:
    third_party_allowed = third_party_on(session)
    delisted = delisted_reasons()
    ready: dict[str, bool] = {}

    def is_ready(plugin: InstalledPlugin) -> bool:
        if plugin.id not in ready:
            ready[plugin.id] = (
                (third_party_allowed or plugin.source == PluginSource.FIRST_PARTY)
                and delisted_reason(plugin, delisted) is None
                and not hosts_not_allowed(session, plugin)
                and not _signed_out(plugin)
                # The plugin host refused the license: a call would only be refused.
                and plugin.check_failure not in LICENSE_FAILURES
                # Neither engine speaks the older SSE transport.
                and not recorded_on_sse(plugin.entry)
            )
        return ready[plugin.id]

    rows = session.execute(
        select(InstalledPlugin, PluginTool)
        .join(PluginTool, PluginTool.plugin_id == InstalledPlugin.id)
        .where(
            InstalledPlugin.enabled,
            InstalledPlugin.disconnected_at.is_(None),
            PluginTool.enabled,
        )
        .order_by(InstalledPlugin.connected_at, InstalledPlugin.id, PluginTool.position)
    )
    taken: set[str] = set()

    def distinct_name(plugin_id: str, tool: str) -> str:
        name = qualified_name(plugin_id, tool, taken=taken)
        taken.add(name)
        return name

    # The first plugin connected keeps the plain name; a later one that collides is hashed.
    return [
        ReadyTool(
            qualified_name=distinct_name(plugin.id, row.tool),
            plugin_id=plugin.id,
            plugin_name=plugin.entry.get("name", plugin.id),
            plugin_source=plugin.source,
            tool=row.tool,
            title=row.title,
            description=row.description,
            input_schema=row.input_schema,
            annotations=row.annotations,
            approval=row.approval,
            exposure=row.exposure,
        )
        for plugin, row in rows
        if is_ready(plugin)
    ]


def _signed_out(plugin: InstalledPlugin) -> bool:
    """An OAuth sign-in whose refresh was refused has no token left to give."""
    return (
        plugin.credential_kind == OAUTH and plugin.check_failure == CheckFailure.SIGN_IN
    )
