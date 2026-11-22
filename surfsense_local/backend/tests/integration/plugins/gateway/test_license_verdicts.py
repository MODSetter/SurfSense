import pytest
from sqlalchemy.orm import Session

from modules.plugins.gateway.listing import list_tools
from modules.plugins.installed.models import CheckFailure
from modules.plugins.installed.plugin_check import record_check
from modules.plugins.remote.mcp_client.server_error import ServerError
from tests.integration.plugins.gateway.conftest import FakeSource, connect, tool

pytestmark = pytest.mark.integration

LICENSE_REFUSED = [
    CheckFailure.NEEDS_LICENSE,
    CheckFailure.LICENSE_EXPIRED,
    CheckFailure.LICENSE_REVOKED,
    CheckFailure.LICENSE_INVALID,
]


@pytest.mark.parametrize("failure", LICENSE_REFUSED)
async def test_a_plugin_its_server_refused_a_license_for_offers_nothing(
    session: Session, failure: CheckFailure
) -> None:
    """Out of `@` and the agent: a call would only be refused."""
    plugin = await connect(session, "amazon", FakeSource([tool("search")]))
    plugin.check_failure = failure
    session.commit()

    assert list_tools(session) == []


async def test_a_server_down_for_a_minute_still_offers_its_tools(
    session: Session,
) -> None:
    """Only a license verdict holds a plugin out; a server out of reach may come back."""
    plugin = await connect(session, "amazon", FakeSource([tool("search")]))
    plugin.check_failure = CheckFailure.UNREACHABLE
    session.commit()

    assert [t.tool for t in list_tools(session)] == ["search"]


async def test_a_server_that_cannot_be_reached_keeps_a_license_verdict(
    session: Session,
) -> None:
    """A non-answer is no news: only the server saying so changes a license verdict."""
    plugin = await connect(session, "amazon", FakeSource([tool("search")]))
    plugin.check_failure = CheckFailure.NEEDS_LICENSE

    record_check(session, plugin, ServerError("down", retryable=True, status=503))

    assert plugin.check_failure == CheckFailure.NEEDS_LICENSE


async def test_a_listing_that_works_clears_a_license_verdict(
    session: Session,
) -> None:
    """A listing the server answered is its verdict too: the license works."""
    plugin = await connect(session, "amazon", FakeSource([tool("search")]))
    plugin.check_failure = CheckFailure.NEEDS_LICENSE

    record_check(session, plugin, await FakeSource([tool("search")]).list_tools())

    assert plugin.check_failure is None
