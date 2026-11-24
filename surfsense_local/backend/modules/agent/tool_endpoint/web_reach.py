"""The hosts the agent's web tools may reach: those the user allowed in Settings > Network.

A turn cannot raise the consent question, so a host not allowed yet is refused,
recorded off so Settings > Network lists it, and named in the result's first line,
which the thread's step reads back to offer the question on a click (ADR 0060).
"""

from sqlalchemy.orm import Session

from modules.agent.tool_endpoint.tool import ToolCallError
from modules.documents.web_sources.pullers.puller import HostCheck
from modules.egress.last_calls import record_last_call
from modules.egress.service import EgressDeniedError, host_destination, require
from modules.plugins.installed.plugin_hosts import refused_hosts

# A refusal's first words; the step takes the hosts after them.
REFUSED = "Not allowed in Settings > Network yet: "


def require_hosts(session: Session, hosts: list[str], purpose: str) -> None:
    """Raises ToolCallError naming each host still to allow; stamps the others as called."""
    refusal = refused_hosts(session, hosts, purpose=purpose)
    if refusal is not None:
        session.commit()
        raise ToolCallError(refused_text(refusal.hosts))
    for host in hosts:
        if (destination := host_destination(f"https://{host}")) is not None:
            record_last_call(session, destination)
    session.commit()


def host_check(session: Session) -> HostCheck:
    """A redirect's host, checked as it is reached, each in its own short transaction."""

    def reach(host: str) -> None:
        try:
            require(session, host_destination(f"https://{host}"), host)
        except EgressDeniedError:
            session.rollback()
            raise
        session.commit()

    return reach


def refused_text(hosts: list[str]) -> str:
    return (
        f"{REFUSED}{', '.join(hosts)}.\n"
        "Tell the user: they can allow it from this step or in Settings > Network. "
        "Try again once they have."
    )


def refused_hosts_in(result: str) -> list[str]:
    """The hosts a refusal names; none for any other result."""
    first = result.split("\n", 1)[0]
    if not first.startswith(REFUSED):
        return []
    named = first.removeprefix(REFUSED).rstrip(".")
    return [host.strip() for host in named.split(",") if host.strip()]
