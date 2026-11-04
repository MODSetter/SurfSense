"""SurfSense's license server, compiled in: where a renewed license file comes from."""

from shared.config import get_license_server_settings

# The license server's own name. plugins.surfsense.com serves the same routes
# today, but it is the plugin host's name, under the plugin host's consent.
LICENSE_SERVER = "https://api.surfsense.com"


def license_server() -> str:
    """The compiled server, or the one a developer or a firm's mirror sets instead."""
    configured = get_license_server_settings().license_server_url
    return (configured or LICENSE_SERVER).rstrip("/")
