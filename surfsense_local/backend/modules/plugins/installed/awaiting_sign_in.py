"""An OAuth plugin kept before its sign-in finishes, so an abandoned one is not lost.

Saved once the authorization server's hosts are allowed, never before: a host still to be
allowed retries the same request, which would find the plugin already taken.
"""

from datetime import UTC, datetime

from sqlalchemy.orm import Session

from modules.plugins.installed.models import (
    CheckFailure,
    InstalledPlugin,
    PluginKind,
)
from modules.plugins.remote.sign_in.oauth.oauth_credential import OAUTH
from modules.plugins.remote.sign_in.oauth.plugin_draft import PluginDraft


def store_awaiting_sign_in(session: Session, draft: PluginDraft) -> None:
    """Signed out, with no tools to offer, until a sign-in on its row finishes."""
    plugin = InstalledPlugin(
        id=draft.plugin_id,
        kind=PluginKind.REMOTE,
        source=draft.source,
        url=draft.url,
        entry=draft.entry,
    )
    plugin.credential_kind = OAUTH
    plugin.check_failure = CheckFailure.SIGN_IN
    plugin.checked_at = datetime.now(UTC)
    session.add(plugin)
    session.flush()
