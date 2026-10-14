"""Every host a plugin contacts, and whether the user allowed all of them."""

from urllib.parse import urlsplit

from sqlalchemy.orm import Session

from modules.egress.models import EgressDestination
from modules.egress.service import EgressDeniedError, host_destination
from modules.plugins.installed.models import InstalledPlugin


def plugin_hosts(plugin: InstalledPlugin) -> list[str]:
    """The URL's host first, then the hosts its entry declares, each once."""
    hosts = [urlsplit(plugin.url).hostname or "", *plugin.entry.get("hosts", [])]
    return list(dict.fromkeys(host for host in hosts if host))


def hosts_not_allowed(session: Session, plugin: InstalledPlugin) -> list[str]:
    """Hosts still to allow; loopback never needs consent, since nothing leaves the machine."""
    missing = []
    for host in plugin_hosts(plugin):
        destination = host_destination(f"https://{host}")
        if destination is None:
            continue
        row = session.get(EgressDestination, destination)
        if row is None or not row.enabled:
            missing.append(host)
    return missing


def refused_hosts(session: Session, hosts: list[str]) -> EgressDeniedError | None:
    """The refusal naming every host still to allow, or None when all are allowed.

    A refused host with no row is recorded off, so Settings > Network lists it to allow.
    Returned rather than raised, so the caller's commit keeps those rows.
    """
    missing = []
    for host in dict.fromkeys(hosts):
        destination = host_destination(f"https://{host}")
        if destination is None:
            continue
        row = session.get(EgressDestination, destination)
        if row is None:
            session.add(EgressDestination(destination=destination, enabled=False))
        if row is None or not row.enabled:
            missing.append(host)
    if not missing:
        return None
    session.flush()
    first = host_destination(f"https://{missing[0]}")
    return EgressDeniedError(first, hosts=missing, purpose="plugin")
