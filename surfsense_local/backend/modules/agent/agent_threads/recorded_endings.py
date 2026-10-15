"""Endings of agent replies that only SurfSense knows, kept in the opencode session.

opencode stores a Stop and a quit alike, as an abort, so a Stop is noted under
the session's metadata, which goes with the session and needs no table of
SurfSense's own. Other keys there are left as they are.
"""

from pathlib import Path
from typing import Any

from modules.agent.opencode_client import OpencodeClient

KEY = "surfsense"


async def record_ending(
    client: OpencodeClient,
    folder: Path,
    session_id: str,
    reply_id: str,
    ending: dict[str, Any],
) -> None:
    """Keep the reply's ending, replacing any recorded before."""
    metadata = await client.session_metadata(folder, session_id)
    ours = dict(metadata.get(KEY) or {})
    ours["endings"] = {**(ours.get("endings") or {}), reply_id: ending}
    await client.set_session_metadata(folder, session_id, {**metadata, KEY: ours})


def recorded_endings(metadata: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Every recorded ending in the session's metadata, by reply id."""
    return (metadata.get(KEY) or {}).get("endings") or {}
