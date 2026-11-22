"""One verdict on the license, applied to every connected paid plugin at once."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from modules.plugins.installed.models import (
    LICENSE_FAILURES,
    CheckFailure,
    InstalledPlugin,
)
from modules.plugins.lists.plugin_host import on_plugin_host
from modules.plugins.remote.sign_in.plugin_headers import LICENSE


def paid_plugins(session: Session) -> list[InstalledPlugin]:
    """Connected plugins that sign in with the license; only the plugin host takes one."""
    connected = session.scalars(
        select(InstalledPlugin)
        .where(
            InstalledPlugin.credential_kind == LICENSE,
            InstalledPlugin.disconnected_at.is_(None),
        )
        .order_by(InstalledPlugin.connected_at, InstalledPlugin.id)
    )
    return [plugin for plugin in connected if on_plugin_host(plugin.url)]


def apply_verdict(session: Session, failure: CheckFailure | None) -> list[str]:
    """The names of switched-on plugins this verdict newly holds out, to tell the user."""
    held_out = []
    for plugin in paid_plugins(session):
        before = plugin.check_failure
        if failure is not None:
            plugin.check_failure = failure
            if before not in LICENSE_FAILURES and plugin.enabled:
                held_out.append(plugin.entry.get("name", plugin.id))
        elif before in LICENSE_FAILURES:
            # A valid license says nothing of a server that was out of reach.
            plugin.check_failure = None
    session.flush()
    return held_out
