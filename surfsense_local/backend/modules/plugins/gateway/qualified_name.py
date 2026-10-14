"""`<plugin>__<tool>`: the one name permissions, steps, history and `@` mentions use."""

import hashlib
import re

# opencode adds `plugins_`, and providers allow 64 characters in all.
MAX_LENGTH = 55
HASH_LENGTH = 8


def qualified_name(plugin_id: str, tool: str, *, taken: set[str] | None = None) -> str:
    """The name, made distinct with a short hash when it is too long or already `taken`."""
    name = re.sub(r"[^A-Za-z0-9_]", "_", f"{plugin_id}__{tool}")
    if len(name) <= MAX_LENGTH and name not in (taken or set()):
        return name
    digest = hashlib.sha256(f"{plugin_id}__{tool}".encode()).hexdigest()[:HASH_LENGTH]
    return f"{name[: MAX_LENGTH - HASH_LENGTH - 1]}_{digest}"
