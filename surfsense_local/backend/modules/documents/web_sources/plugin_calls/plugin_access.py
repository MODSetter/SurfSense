"""What a call to one of SurfSense's plugins needs: a license to send, and the host allowed.

The license is checked first, so someone without one is told so before any network
question. Whether the license is valid is the plugin host's to judge, never the app's.
"""

from dataclasses import dataclass

from sqlalchemy.orm import Session

from modules.egress.last_calls import record_last_call
from modules.egress.service import host_destination
from modules.license.license_key import license_key
from modules.plugins.installed.plugin_hosts import refused_hosts
from modules.plugins.lists.first_party.first_party_list import first_party_entries
from modules.plugins.lists.list_entry import ListEntry
from modules.plugins.remote.sign_in.plugin_headers import license_headers

# The plugin host's own word for a request with no license, as `{"reason": ...}`.
MISSING_LICENSE = "missing_license"


class LicenseRefusedError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        # `missing_license`, or the host's verdict: `expired`, `revoked`, `invalid`.
        self.reason = reason


@dataclass(frozen=True)
class PluginAccess:
    url: str
    headers: dict[str, str]


def require_plugin_access(session: Session, plugin_id: str) -> ListEntry:
    """Raises LicenseRefusedError, or EgressDeniedError naming the host to allow."""
    entry = next(e for e in first_party_entries() if e.id == plugin_id)
    if license_key(session) is None:
        raise LicenseRefusedError(MISSING_LICENSE)
    refusal = refused_hosts(session, entry.hosts)
    if refusal is not None:
        raise refusal
    return entry


def plugin_access(session: Session, plugin_id: str) -> PluginAccess:
    """For a call about to be made, recorded for Settings > Network."""
    entry = require_plugin_access(session, plugin_id)
    for host in entry.hosts:
        if (destination := host_destination(f"https://{host}")) is not None:
            record_last_call(session, destination)
    return PluginAccess(entry.url, license_headers(session, entry.url))
