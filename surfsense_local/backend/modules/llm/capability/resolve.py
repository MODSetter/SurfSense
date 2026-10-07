"""What a model is measured to do on the connection that serves it.

docs/proposals/file-agent/05-model-ladder-and-evals.md: an unmeasured model
keeps what it has; only a measured failure takes something away.
"""

from dataclasses import dataclass, field
from ipaddress import ip_address
from urllib.parse import urlsplit

from modules.egress.service import host_destination
from modules.llm.capability.level import Level
from modules.llm.capability.measured.loader import find_row
from modules.llm.capability.measured.schema import MeasuredModel
from modules.llm.capability.model_key import model_key
from modules.llm.models import ProviderConnection

__all__ = ["Capability", "Reason", "capability_of"]

_MEASURED_REASON = {
    Level.AGENT: "measured_pass",
    Level.AGENT_LIMITED: "measured_near",
    Level.STUDIO_ONLY: "measured_fail",
}


@dataclass(frozen=True)
class Reason:
    """Why, as a code and the values the interface words it with."""

    code: str
    values: dict[str, str | int] = field(default_factory=dict)


@dataclass(frozen=True)
class Capability:
    level: Level
    reason: Reason
    # The row the level was read from; also set when the row did not hold here.
    row: MeasuredModel | None = None


def capability_of(model: str, connection: ProviderConnection | None) -> Capability:
    """The level for a model id on its connection; no connection is llama.cpp.

    Synchronous and offline: reads only the list shipped with the app.
    """
    if model_key(model) is None:
        code = "alias" if model.strip() else "no_row"
        return Capability(Level.NOT_MEASURED, Reason(code))
    row = find_row(model)
    if row is None:
        return Capability(Level.NOT_MEASURED, Reason("no_row"))
    if _served(connection) not in row.match.served:
        return Capability(
            Level.NOT_MEASURED, Reason("measured_elsewhere", {"host": row.host}), row
        )
    level = Level(row.level)
    if row.assumed:
        return Capability(level, Reason("assumed"), row)
    values: dict[str, str | int] = {
        "passed": row.passes.passed,
        "counted": row.passes.counted,
        "suite_version": row.suite_version,
        "measured_on": row.measured_on.isoformat(),
    }
    return Capability(level, Reason(_MEASURED_REASON[level], values), row)


# Names only a home or office network resolves.
_OWN_NETWORK_SUFFIXES = (".local", ".lan", ".internal", ".home.arpa")


def _served(connection: ProviderConnection | None) -> str:
    """Local for llama.cpp, a loopback host, or a server on the user's own network.

    A copy on a machine of one's own is its own quantization and window, so a
    pass measured on a provider's host does not hold there.
    """
    if connection is None or host_destination(connection.base_url) is None:
        return "local"
    host = (urlsplit(connection.base_url).hostname or "").rstrip(".")
    try:
        own_network = not ip_address(host).is_global
    except ValueError:
        own_network = "." not in host or host.endswith(_OWN_NETWORK_SUFFIXES)
    return "local" if own_network else "remote"
