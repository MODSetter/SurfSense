"""Every ready plugin tool a turn of the opencode agent could hold, and how much it may.

Read alike by the turn and by SurfSense's own server, which shows the catalogue
and the tools that load more only when the plugin tools do not all fit.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from api.dependencies import transact
from modules.agent.model_call_route import selected_call_route
from modules.agent.model_window import selected_model_window, selected_text_model
from modules.agent.tool_exposure.catalogue import CataloguedPlugin, catalogue
from modules.agent.tool_exposure.held_tools import all_fit
from modules.agent.tool_exposure.ranking import IndexedTool
from modules.agent.tool_exposure.share import plugin_share, plugin_tool_limit
from modules.plugins.gateway.listing import list_tools
from modules.plugins.installed.models import CheckFailure, InstalledPlugin

# opencode's own tools as SurfSense configures it: edit, glob, grep, read, skill,
# write and todowrite. SurfSense's are counted from its listing.
OPENCODE_TOOLS = 7


@dataclass(frozen=True)
class TurnTools:
    tools: list[IndexedTool]
    share: int
    limit: int | None
    catalogued: list[CataloguedPlugin]

    @property
    def fit(self) -> bool:
        return all_fit(self.tools, self.share, self.limit)

    def catalogue(self) -> str:
        """The agent's view of every ready plugin; nothing when every tool is held."""
        return "" if self.fit else catalogue(self.catalogued)


async def turn_tools(session: Session, surfsense_tools: int) -> TurnTools:
    _, window = await selected_model_window(session)
    _, provider = await transact(session, selected_text_model)
    route = await transact(session, selected_call_route)
    tools, catalogued = await transact(session, _indexed)
    limit = plugin_tool_limit(provider, route, OPENCODE_TOOLS + surfsense_tools)
    return TurnTools(tools, plugin_share(window), limit, catalogued)


def _indexed(session: Session) -> tuple[list[IndexedTool], list[CataloguedPlugin]]:
    tools: list[IndexedTool] = []
    plugins: dict[str, CataloguedPlugin] = {}
    for ready in list_tools(session):
        row = session.get_one(InstalledPlugin, ready.plugin_id)
        description = str(row.entry.get("description") or "")
        line = f"{ready.plugin_name}: {description}".rstrip(": ")
        tools.append(IndexedTool(ready, line))
        listed = plugins.setdefault(
            ready.plugin_id,
            CataloguedPlugin(
                ready.plugin_id,
                ready.plugin_name,
                description,
                [],
                reachable=row.check_failure != CheckFailure.UNREACHABLE,
            ),
        )
        listed.tools.append(ready.tool)
    return tools, list(plugins.values())
