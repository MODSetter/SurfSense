"""The headers every request to a connected plugin's server carries, for its sign-in."""

from sqlalchemy.orm import Session

from modules.license.license_key import license_key
from modules.plugins.installed.models import InstalledPlugin
from modules.plugins.lists.plugin_host import on_plugin_host
from modules.plugins.remote.sign_in.token_headers import token_headers

LICENSE = "license"


def sign_in_headers(session: Session, plugin: InstalledPlugin) -> dict[str, str]:
    if plugin.credential_kind == LICENSE:
        return license_headers(session, plugin.url)
    return token_headers(plugin.credential)


def license_headers(session: Session, url: str) -> dict[str, str]:
    """`License <key>` only on SurfSense's plugin host: the key never goes anywhere else."""
    key = license_key(session) if on_plugin_host(url) else None
    return {"authorization": f"License {key}"} if key else {}
