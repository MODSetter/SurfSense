"""Whether the user allowed SurfSense's plugin host, which serves the registry."""

from sqlalchemy.orm import Session

from modules.egress.service import EgressDeniedError, refused_named_host
from modules.plugins.lists.registry.registry_fetch import registry_url

# The prompt words its question for fetching the list, not for a plugin's tools.
PURPOSE = "plugin_registry"


def registry_refusal(session: Session) -> EgressDeniedError | None:
    """None on loopback, a developer's plugin host, where nothing leaves the machine."""
    refused = refused_named_host(session, registry_url("plugins.json"))
    if refused is not None:
        refused.purpose = PURPOSE
    return refused
