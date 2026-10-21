"""The hosts a Claude plan reaches, each its own egress destination (ADR 0027)."""

from sqlalchemy.orm import Session

from modules.egress.models import EgressDestination
from modules.egress.service import EgressDeniedError, host_destination

# Every model call, and Claude Code's model list.
API_HOST = "api.anthropic.com"
# Where Claude Code refreshes its sign-in: `TOKEN_URL` in Claude Code 2.1.301.
SIGN_IN_HOST = "platform.claude.com"
CLAUDE_HOSTS = (API_HOST, SIGN_IN_HOST)
# The prompt words its question by it: one host gets chats, the other a sign-in.
PURPOSE = "claude_plan"


def hosts_still_off(session: Session) -> list[str]:
    """The Claude hosts not allowed yet, model calls first; reads, never writes."""
    off = []
    for host in CLAUDE_HOSTS:
        row = session.get(EgressDestination, host_destination(f"https://{host}"))
        if row is None or not row.enabled:
            off.append(host)
    return off


def claude_refusal(session: Session) -> EgressDeniedError | None:
    """The refusal naming every Claude host still to allow, or None."""
    off = hosts_still_off(session)
    if not off:
        return None
    first = host_destination(f"https://{off[0]}")
    assert first is not None
    return EgressDeniedError(first, hosts=off, purpose=PURPOSE)


def require_claude_hosts(session: Session) -> None:
    if (refusal := claude_refusal(session)) is not None:
        raise refusal
