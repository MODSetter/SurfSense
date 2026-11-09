"""A runtime's offer to ask the user for input on a server's behalf, taken out before the server sees it.

opencode 2.x tells servers it accepts elicitation and waits on a form for each
request; SurfSense shows no such form, so a call that asked would hang until its
limit. A server told nothing of it does not ask.
"""

import json


def without_elicitation(body: bytes) -> bytes:
    """The body as sent, unless it is an `initialize` offering elicitation."""
    try:
        message = json.loads(body)
    except (ValueError, UnicodeDecodeError):
        return body
    if not isinstance(message, dict) or message.get("method") != "initialize":
        return body
    capabilities = (message.get("params") or {}).get("capabilities")
    if not isinstance(capabilities, dict) or "elicitation" not in capabilities:
        return body
    del capabilities["elicitation"]
    return json.dumps(message).encode()
