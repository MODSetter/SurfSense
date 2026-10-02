import uuid

from shared.secrets import install_digest


def host_id() -> str:
    """The `ext_agent_host_id` OpenAI requires: stable for this install, stored nowhere.

    Derived from the install secret, so it survives restarts and sign-outs and
    changes only when the install does.
    """
    raw = install_digest("chatgpt-ext-agent-host-id")[:16]
    return f"urn:uuid:{uuid.UUID(bytes=raw, version=4)}"
