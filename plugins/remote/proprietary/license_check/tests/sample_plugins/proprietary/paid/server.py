import os

from mcp.server.mcpserver import MCPServer

from proprietary.license_check.keygen import Keygen
from proprietary.license_check.license_access import LicenseAccess
from proprietary.license_check.tests.stand_in_keygen import ACCOUNT

access = LicenseAccess(Keygen(os.environ["STAND_IN_KEYGEN_URL"], ACCOUNT))


def server() -> MCPServer:
    paid = MCPServer("paid")

    @paid.tool()
    def scrape(url: str) -> str:
        """Scrape a page."""
        return f"scraped {url}"

    return paid
