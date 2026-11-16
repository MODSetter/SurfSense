"""The exact bytes CI signs and the app verifies: one formatting, so a re-sign changes nothing."""

import json
from typing import Any


def registry_bytes(registry: dict[str, Any]) -> bytes:
    return (json.dumps(registry, indent=2, ensure_ascii=False) + "\n").encode()
