"""A provider SurfSense cannot sign in to by itself: the plugin kept, marked as needing the
user's own OAuth app, so it is set up from its row rather than lost with a dialog closed."""

from dataclasses import replace
from typing import Literal

from fastapi import HTTPException
from sqlalchemy.orm import Session

from modules.plugins.installed.awaiting_sign_in import store_awaiting_sign_in
from modules.plugins.installed.models import CheckFailure, InstalledPlugin
from modules.plugins.remote.sign_in.oauth.own_app import (
    needs_own_app,
    registration_refused,
)
from modules.plugins.remote.sign_in.oauth.plugin_draft import PluginDraft

# `needs_client`: the provider registers no app. `refused`: it refused SurfSense.
OwnAppReason = Literal["needs_client", "refused"]


class OwnAppNeededError(Exception):
    def __init__(self, reason: OwnAppReason) -> None:
        super().__init__(reason)
        self.reason = reason

    def refusal(self) -> HTTPException:
        """For a sign-in asked of a saved plugin, which the screen answers with the app."""
        return (
            needs_own_app() if self.reason == "needs_client" else registration_refused()
        )


def keep_needing_own_app(
    session: Session, draft: PluginDraft, reason: OwnAppReason
) -> None:
    """A new plugin is stored signed out; a saved one is marked. Signing in clears it."""
    auth = {**draft.entry.get("auth", {}), "needs_own_app": reason}
    if not draft.existing:
        store_awaiting_sign_in(
            session, replace(draft, entry={**draft.entry, "auth": auth})
        )
        return
    plugin = session.get(InstalledPlugin, draft.plugin_id)
    if plugin is None:
        return
    plugin.entry = {**plugin.entry, "auth": {**plugin.entry.get("auth", {}), **auth}}
    plugin.check_failure = CheckFailure.SIGN_IN
    session.flush()
