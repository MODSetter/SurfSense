"""Billing charges the workspace owner once per billable success at the executor (03c).

Boundaries mocked: the DB session and the audit helper. NOT mocked: the real
WebCrawlCreditService debit math and the owner-billed decision.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

import app.capabilities.billing as billing
from app.capabilities.billing import charge_capability
from app.capabilities.types import BillingUnit, CapabilityContext
from app.capabilities.web.scrape.schemas import ScrapeOutput, ScrapeRow
from app.config import config

pytestmark = pytest.mark.unit

_WORKSPACE_ID = 1
_OWNER = UUID("00000000-0000-0000-0000-0000000000bb")


class _FakeUser:
    def __init__(self, balance_micros: int, reserved_micros: int = 0):
        self.credit_micros_balance = balance_micros
        self.credit_micros_reserved = reserved_micros


def _make_session(owner_id, balance_micros):
    """Mock session serving owner-resolution and the charge_credits debit."""
    fake_user = _FakeUser(balance_micros)
    session = AsyncMock()
    session.add = MagicMock()

    def _make_result(*_args, **_kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = owner_id  # owner resolution
        result.unique.return_value.scalar_one_or_none.return_value = fake_user  # debit
        return result

    session.execute = AsyncMock(side_effect=_make_result)
    return session, fake_user


def _output(*statuses: str) -> ScrapeOutput:
    return ScrapeOutput(
        rows=[
            ScrapeRow(url=f"https://{i}.com", status=status)
            for i, status in enumerate(statuses)
        ]
    )


def _ctx(session) -> CapabilityContext:
    return CapabilityContext(session=session, workspace_id=_WORKSPACE_ID)


@pytest.fixture(autouse=True)
def _stub_auto_reload(monkeypatch):
    import app.services.auto_reload_service as ar

    monkeypatch.setattr(ar, "maybe_trigger_auto_reload", AsyncMock())


@pytest.fixture
def record_usage(monkeypatch):
    rec = AsyncMock(return_value=MagicMock())
    monkeypatch.setattr(billing, "record_token_usage", rec)
    return rec


async def test_charges_workspace_owner_per_successful_crawl(monkeypatch, record_usage):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_MICROS_PER_SUCCESS", 1000)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    await charge_capability(
        _output("success", "empty", "success"), BillingUnit.WEB_CRAWL, _ctx(session)
    )

    # Owner debited 2 * 1000; one web_crawl audit row billed to the OWNER.
    assert user.credit_micros_balance == 100_000 - 2000
    record_usage.assert_awaited_once()
    kwargs = record_usage.await_args.kwargs
    assert kwargs["usage_type"] == "web_crawl"
    assert kwargs["user_id"] == _OWNER
    assert kwargs["workspace_id"] == _WORKSPACE_ID
    assert kwargs["cost_micros"] == 2000


async def test_no_successful_rows_is_free(monkeypatch, record_usage):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    await charge_capability(
        _output("empty", "failed"), BillingUnit.WEB_CRAWL, _ctx(session)
    )

    record_usage.assert_not_awaited()
    assert user.credit_micros_balance == 100_000


async def test_disabled_is_noop(monkeypatch, record_usage):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", False)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    await charge_capability(
        _output("success", "success"), BillingUnit.WEB_CRAWL, _ctx(session)
    )

    record_usage.assert_not_awaited()
    session.execute.assert_not_called()
    assert user.credit_micros_balance == 100_000


async def test_free_verb_without_a_unit_is_noop(monkeypatch, record_usage):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    await charge_capability(_output("success", "success"), None, _ctx(session))

    record_usage.assert_not_awaited()
    session.execute.assert_not_called()
    assert user.credit_micros_balance == 100_000
