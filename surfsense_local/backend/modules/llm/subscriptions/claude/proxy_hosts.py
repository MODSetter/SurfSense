from sqlalchemy.orm import Session, sessionmaker

from modules.agent.runtime_proxy.allowed_hosts import HTTPS_PORT, AllowedHosts
from modules.egress.models import EgressDestination
from modules.egress.service import host_destination
from modules.llm.subscriptions.claude.hosts import CLAUDE_HOSTS

DEFAULT_HOSTS = tuple((host, HTTPS_PORT) for host in CLAUDE_HOSTS)


class ClaudeHosts(AllowedHosts):
    """Anthropic's hosts, each only while its egress is on, and nothing else.

    Its own list, not opencode's: opencode must never reach Anthropic directly
    (ADR 0050), and Claude Code reaches plugins only through the gateway (ADR 0064).
    """

    def __init__(
        self,
        sessions: sessionmaker[Session],
        hosts: tuple[tuple[str, int], ...] = DEFAULT_HOSTS,
    ) -> None:
        super().__init__(sessions)
        self._hosts = hosts

    def _ready(self, session: Session) -> frozenset[tuple[str, int]]:
        allowed = set()
        for host, port in self._hosts:
            destination = host_destination(f"https://{host}")
            # A loopback host is not egress, as everywhere else.
            row = session.get(EgressDestination, destination) if destination else None
            if destination is None or (row is not None and row.enabled):
                allowed.add((host, port))
        return frozenset(allowed)
