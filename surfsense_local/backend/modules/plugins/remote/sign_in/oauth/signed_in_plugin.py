"""Storing a plugin whose sign-in just succeeded: a new row, or the same row signed in again."""

from sqlalchemy.orm import Session

from modules.plugins.gateway.source_tool import SourceTool
from modules.plugins.installed.custom_plugin import connected_name
from modules.plugins.installed.models import InstalledPlugin, PluginKind
from modules.plugins.installed.plugin_check import record_check
from modules.plugins.remote.sign_in.oauth.oauth_credential import (
    OAuthCredential,
    write_credential,
)
from modules.plugins.remote.sign_in.oauth.plugin_draft import PluginDraft
from modules.plugins.remote.sign_in.oauth.sign_in_failure import SignInFailure


class NotStoredError(Exception):
    """The row changed while the user was signing in; the message says how."""

    def __init__(self, code: SignInFailure, message: str) -> None:
        super().__init__(message)
        self.code = code


def store_signed_in(
    session: Session,
    draft: PluginDraft,
    credential: OAuthCredential,
    tools: list[SourceTool],
) -> InstalledPlugin:
    if draft.existing:
        plugin = session.get(InstalledPlugin, draft.plugin_id)
        if plugin is None:
            raise NotStoredError(
                SignInFailure.PLUGIN_DISCONNECTED,
                f"{draft.name} was disconnected meanwhile.",
            )
    else:
        taken = (
            draft.name
            if session.get(InstalledPlugin, draft.plugin_id) is not None
            else connected_name(session, draft.url)
        )
        if taken is not None:
            raise NotStoredError(
                SignInFailure.PLUGIN_ALREADY_CONNECTED,
                f"This server is already connected as {taken}.",
            )
        plugin = InstalledPlugin(
            id=draft.plugin_id,
            kind=PluginKind.REMOTE,
            source=draft.source,
            url=draft.url,
        )
        session.add(plugin)
    plugin.entry = draft.entry
    write_credential(plugin, credential)
    plugin.disconnected_at = None
    session.flush()
    record_check(session, plugin, tools)
    return plugin
