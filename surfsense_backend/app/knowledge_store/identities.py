"""Authorship conventions for recorded revisions.

Author = whose content change it is; committer = who recorded it.
"""

from __future__ import annotations

#: Committer of every agent-recorded revision; author of autonomous writes.
AGENT_IDENTITY = "SurfSense Agent <agent@surfsense>"

#: Author of the one-time seed revision that migrates a workspace into the store.
MIGRATION_IDENTITY = "SurfSense Migration <migration@surfsense>"


def user_identity(user_id: str | None) -> str:
    """Revision author for a user action; autonomous actions author as the agent."""
    if user_id is None:
        return AGENT_IDENTITY
    return f"SurfSense User <{user_id}@users.surfsense>"
