"""Billing charges the workspace owner once per billable success at the executor (03c).

Boundaries mocked: the DB session and the audit helper. NOT mocked: the real
WebCrawlCreditService debit math and the owner-billed decision.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

import app.capabilities.core.billing as billing
from app.capabilities.core.billing import charge_capability, gate_capability
from app.capabilities.core.types import BillingUnit, CapabilityContext
from app.capabilities.web.scrape.schemas import ScrapeInput, ScrapeOutput, ScrapeRow
from app.config import config
from app.services.web_crawl_credit_service import InsufficientCreditsError

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


def _output_with_captcha(*statuses: str, attempts: int, solved: int) -> ScrapeOutput:
    out = _output(*statuses)
    out.captcha_attempts = attempts
    out.captcha_solved = solved
    return out


async def test_charges_workspace_owner_per_captcha_attempt_even_when_crawl_failed(
    monkeypatch, record_usage
):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE", 3000)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    # Crawl failed (no billable success) but the solver ran twice — attempts bill.
    await charge_capability(
        _output_with_captcha("failed", attempts=2, solved=1),
        BillingUnit.WEB_CRAWL,
        _ctx(session),
    )

    assert user.credit_micros_balance == 100_000 - 2 * 3000
    record_usage.assert_awaited_once()
    kwargs = record_usage.await_args.kwargs
    assert kwargs["usage_type"] == "web_crawl_captcha"
    assert kwargs["user_id"] == _OWNER
    assert kwargs["cost_micros"] == 6000


async def test_captcha_billing_disabled_does_not_charge_attempts(
    monkeypatch, record_usage
):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_BILLING_ENABLED", False)
    session, user = _make_session(_OWNER, balance_micros=100_000)

    await charge_capability(
        _output_with_captcha("failed", attempts=2, solved=1),
        BillingUnit.WEB_CRAWL,
        _ctx(session),
    )

    record_usage.assert_not_awaited()
    assert user.credit_micros_balance == 100_000


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


def _gate_session(owner_id, balance_micros):
    """Mock session serving owner-resolution and the spendable-balance read."""
    session = AsyncMock()

    def _make_result(*_args, **_kwargs):
        result = MagicMock()
        result.scalar_one_or_none.return_value = owner_id  # owner resolution
        result.first.return_value = (balance_micros, 0)  # balance, reserved
        return result

    session.execute = AsyncMock(side_effect=_make_result)
    return session


async def test_gate_blocks_when_worst_case_exceeds_balance(monkeypatch):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_MICROS_PER_SUCCESS", 1000)
    session = _gate_session(_OWNER, balance_micros=1500)  # affords 1 crawl, not 2

    with pytest.raises(InsufficientCreditsError):
        await gate_capability(
            ScrapeInput(urls=["https://a.com", "https://b.com"]),
            BillingUnit.WEB_CRAWL,
            _ctx(session),
        )


async def test_gate_passes_when_balance_covers_worst_case(monkeypatch):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_MICROS_PER_SUCCESS", 1000)
    session = _gate_session(_OWNER, balance_micros=100_000)

    await gate_capability(
        ScrapeInput(urls=["https://a.com", "https://b.com"]),
        BillingUnit.WEB_CRAWL,
        _ctx(session),
    )


async def test_gate_is_noop_when_disabled(monkeypatch):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", False)
    session = _gate_session(_OWNER, balance_micros=0)

    await gate_capability(
        ScrapeInput(urls=["https://a.com"]), BillingUnit.WEB_CRAWL, _ctx(session)
    )


async def test_gate_reserves_worst_case_captcha_when_solving_enabled(monkeypatch):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", False)
    monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE", 3000)
    monkeypatch.setattr(config, "CAPTCHA_MAX_ATTEMPTS_PER_URL", 3)
    monkeypatch.setattr(billing, "captcha_enabled", lambda: True)
    session = _gate_session(_OWNER, balance_micros=5000)  # < 1 url * 3 * 3000

    with pytest.raises(InsufficientCreditsError):
        await gate_capability(
            ScrapeInput(urls=["https://a.com"]), BillingUnit.WEB_CRAWL, _ctx(session)
        )


async def test_gate_does_not_reserve_captcha_when_solving_disabled(monkeypatch):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", False)
    monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_BILLING_ENABLED", True)
    monkeypatch.setattr(billing, "captcha_enabled", lambda: False)
    session = _gate_session(_OWNER, balance_micros=0)

    # Solving off → attempts can never happen → nothing to reserve → passes.
    await gate_capability(
        ScrapeInput(urls=["https://a.com"]), BillingUnit.WEB_CRAWL, _ctx(session)
    )


async def test_gate_is_noop_for_free_verb(monkeypatch):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    session = _gate_session(_OWNER, balance_micros=0)

    await gate_capability(ScrapeInput(urls=["https://a.com"]), None, _ctx(session))

    session.execute.assert_not_called()
