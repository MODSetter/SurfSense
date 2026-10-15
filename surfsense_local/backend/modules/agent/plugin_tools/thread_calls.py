"""A token for a thread's calls to SurfSense's plugin host, so Stop can end them there.

The host keeps no MCP session, so opencode's own cancel cannot reach a call; the
app's Stop names the thread's calls by this token instead. Derived, never stored,
and stable per thread, so giving the servers again each turn changes nothing.
"""

from shared.secrets import install_digest

CALLS_HEADER = "x-surfsense-calls"


def thread_calls_token(thread_id: int) -> str:
    return install_digest(f"plugin-calls:thread:{thread_id}").hex()[:32]
