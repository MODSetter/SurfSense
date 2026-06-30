"""Unit tests for WebCrawlCreditService and the chat-scrape fold helper (Phase 3c).

Covers:
  A) successes_to_micros — config-driven price (the single source of truth),
     including retune behaviour.
  B) billing_enabled gate.
  C) check_credits — sufficient / insufficient / disabled no-op.
  D) charge_credits — debit / disabled no-op / zero no-op.
  E) Chat-scrape fold helper — folds one success into the turn accumulator only
     when billing is enabled and a turn is active.

The wallet logic runs against the real service with a mock DB session at the
system boundary (mirrors tests/unit/connector_indexers/test_etl_credits.py).
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.config import config
from app.services.etl_credit_service import InsufficientCreditsError
from app.services.web_crawl_credit_service import WebCrawlCreditService

pytestmark = pytest.mark.unit

_USER_ID = "00000000-0000-0000-0000-000000000001"


@pytest.fixture(autouse=True)
def _enable_crawl_billing(monkeypatch):
    """Force crawl billing ON; default is off (self-hosted) which no-ops everything."""
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_MICROS_PER_SUCCESS", 1000)


@pytest.fixture(autouse=True)
def _stub_auto_reload(monkeypatch):
    """charge_credits fires a best-effort auto-reload check; stub it out."""
    import app.services.auto_reload_service as _ar

    monkeypatch.setattr(_ar, "maybe_trigger_auto_reload", AsyncMock())


class _FakeUser:
    def __init__(self, balance_micros: int = 0, reserved_micros: int = 0):
        self.credit_micros_balance = balance_micros
        self.credit_micros_reserved = reserved_micros


def _make_session(balance_micros: int = 100_000, reserved_micros: int = 0):
    """Mock DB session compatible with get_available_micros + charge_credits."""
    fake_user = _FakeUser(balance_micros, reserved_micros)
    session = AsyncMock()

    def _make_result(*_args, **_kwargs):
        result = MagicMock()
        result.first.return_value = (
            fake_user.credit_micros_balance,
            fake_user.credit_micros_reserved,
        )
        result.unique.return_value.scalar_one_or_none.return_value = fake_user
        return result

    session.execute = AsyncMock(side_effect=_make_result)
    return session, fake_user


# ===================================================================
# A) successes_to_micros — config-driven price
# ===================================================================


class TestSuccessesToMicros:
    def test_default_is_one_dollar_per_thousand(self, monkeypatch):
        monkeypatch.setattr(config, "WEB_CRAWL_MICROS_PER_SUCCESS", 1000)
        assert WebCrawlCreditService.successes_to_micros(1) == 1000
        assert WebCrawlCreditService.successes_to_micros(1000) == 1_000_000  # $1

    def test_zero_successes_cost_nothing(self):
        assert WebCrawlCreditService.successes_to_micros(0) == 0

    @pytest.mark.parametrize(
        ("per_success", "successes", "expected"),
        [
            (2000, 1000, 2_000_000),  # $2 / 1000
            (500, 1000, 500_000),  # $0.50 / 1000
            (5000, 10, 50_000),  # $5 / 1000
        ],
    )
    def test_retune_is_config_driven(
        self, monkeypatch, per_success, successes, expected
    ):
        """No hardcoded rate: changing the config knob changes the price."""
        monkeypatch.setattr(config, "WEB_CRAWL_MICROS_PER_SUCCESS", per_success)
        assert WebCrawlCreditService.successes_to_micros(successes) == expected


# ===================================================================
# B) billing_enabled gate
# ===================================================================


class TestBillingEnabled:
    def test_reads_config_flag(self, monkeypatch):
        monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
        assert WebCrawlCreditService.billing_enabled() is True
        monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", False)
        assert WebCrawlCreditService.billing_enabled() is False


# ===================================================================
# C) check_credits
# ===================================================================


class TestCheckCredits:
    async def test_sufficient_credit_passes(self):
        session, _user = _make_session(balance_micros=10_000)
        svc = WebCrawlCreditService(session)
        # 5 URLs * 1000 = 5000 <= 10000 → no raise
        await svc.check_credits(_USER_ID, estimated_successes=5)

    async def test_insufficient_credit_raises(self):
        session, _user = _make_session(balance_micros=3_000)
        svc = WebCrawlCreditService(session)
        # 5 URLs * 1000 = 5000 > 3000 → raise
        with pytest.raises(InsufficientCreditsError):
            await svc.check_credits(_USER_ID, estimated_successes=5)

    async def test_reserved_credit_reduces_available(self):
        session, _user = _make_session(balance_micros=10_000, reserved_micros=8_000)
        svc = WebCrawlCreditService(session)
        # available = 2000; 3 * 1000 = 3000 > 2000 → raise
        with pytest.raises(InsufficientCreditsError):
            await svc.check_credits(_USER_ID, estimated_successes=3)

    async def test_disabled_is_noop(self, monkeypatch):
        monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", False)
        session, _user = _make_session(balance_micros=0)
        svc = WebCrawlCreditService(session)
        await svc.check_credits(_USER_ID, estimated_successes=10_000)
        session.execute.assert_not_called()


# ===================================================================
# D) charge_credits
# ===================================================================


class TestChargeCredits:
    async def test_debits_per_success(self):
        session, user = _make_session(balance_micros=100_000)
        svc = WebCrawlCreditService(session)
        new_balance = await svc.charge_credits(_USER_ID, successes=3)
        assert user.credit_micros_balance == 100_000 - 3 * 1000
        assert new_balance == 97_000
        session.commit.assert_awaited()

    async def test_zero_successes_is_noop(self):
        session, user = _make_session(balance_micros=100_000)
        svc = WebCrawlCreditService(session)
        result = await svc.charge_credits(_USER_ID, successes=0)
        assert result is None
        assert user.credit_micros_balance == 100_000
        session.commit.assert_not_awaited()

    async def test_disabled_is_noop(self, monkeypatch):
        monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", False)
        session, user = _make_session(balance_micros=100_000)
        svc = WebCrawlCreditService(session)
        result = await svc.charge_credits(_USER_ID, successes=5)
        assert result is None
        assert user.credit_micros_balance == 100_000
        session.execute.assert_not_called()


# ===================================================================
# E) Chat-scrape fold helper
# ===================================================================


class TestChatScrapeFold:
    """The scrape_webpage tools fold one success into the live turn accumulator."""

    def _import_helper(self):
        from app.agents.chat.multi_agent_chat.main_agent.tools.scrape_webpage import (
            _bill_successful_scrape,
        )

        return _bill_successful_scrape

    def test_folds_into_active_turn_when_enabled(self):
        from app.services.token_tracking_service import start_turn

        acc = start_turn()
        self._import_helper()()
        assert acc.total_cost_micros == 1000
        assert len(acc.calls) == 1
        assert acc.calls[0].call_kind == "web_crawl"

    def test_noop_when_billing_disabled(self, monkeypatch):
        from app.services.token_tracking_service import start_turn

        monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", False)
        acc = start_turn()
        self._import_helper()()
        assert acc.calls == []
        assert acc.total_cost_micros == 0

    def test_noop_when_no_active_turn(self):
        import contextvars

        # Run in a fresh context so the turn ContextVar resolves to its default
        # (None) regardless of other tests — must not raise.
        contextvars.Context().run(self._import_helper())


# ===================================================================
# F) Captcha per-attempt unit (Phase 3d)
# ===================================================================


@pytest.fixture
def _enable_captcha_billing(monkeypatch):
    monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE", 3000)


class TestCaptchaStatics:
    def test_billing_enabled_reads_flag(self, monkeypatch):
        monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_BILLING_ENABLED", True)
        assert WebCrawlCreditService.captcha_billing_enabled() is True
        monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_BILLING_ENABLED", False)
        assert WebCrawlCreditService.captcha_billing_enabled() is False

    def test_solves_to_micros_is_config_driven(self, monkeypatch):
        monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE", 3000)
        assert WebCrawlCreditService.captcha_solves_to_micros(1) == 3000
        assert WebCrawlCreditService.captcha_solves_to_micros(1000) == 3_000_000
        monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_MICROS_PER_SOLVE", 5000)
        assert WebCrawlCreditService.captcha_solves_to_micros(2) == 10_000


class TestChargeCaptcha:
    async def test_debits_per_attempt(self, _enable_captcha_billing):
        session, user = _make_session(balance_micros=100_000)
        svc = WebCrawlCreditService(session)
        new_balance = await svc.charge_captcha(_USER_ID, attempts=2)
        assert user.credit_micros_balance == 100_000 - 2 * 3000
        assert new_balance == 94_000
        session.commit.assert_awaited()

    async def test_zero_attempts_is_noop(self, _enable_captcha_billing):
        session, user = _make_session(balance_micros=100_000)
        svc = WebCrawlCreditService(session)
        assert await svc.charge_captcha(_USER_ID, attempts=0) is None
        assert user.credit_micros_balance == 100_000
        session.commit.assert_not_awaited()

    async def test_disabled_is_noop(self, monkeypatch):
        monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_BILLING_ENABLED", False)
        session, user = _make_session(balance_micros=100_000)
        svc = WebCrawlCreditService(session)
        assert await svc.charge_captcha(_USER_ID, attempts=5) is None
        assert user.credit_micros_balance == 100_000
        session.execute.assert_not_called()


class TestCheckBalance:
    """Combined (crawl + captcha) pre-flight primitive — ungated."""

    async def test_passes_when_affordable(self):
        session, _user = _make_session(balance_micros=10_000)
        await WebCrawlCreditService(session).check_balance(_USER_ID, 5_000)

    async def test_raises_when_short(self):
        session, _user = _make_session(balance_micros=3_000)
        with pytest.raises(InsufficientCreditsError):
            await WebCrawlCreditService(session).check_balance(_USER_ID, 5_000)

    async def test_zero_required_is_noop(self):
        session, _user = _make_session(balance_micros=0)
        await WebCrawlCreditService(session).check_balance(_USER_ID, 0)
        session.execute.assert_not_called()


class TestCaptchaChatFold:
    """The scrape tools fold captcha attempts into the live turn accumulator."""

    def _import_helper(self):
        from app.agents.chat.multi_agent_chat.main_agent.tools.scrape_webpage import (
            _bill_captcha_attempts,
        )

        return _bill_captcha_attempts

    def _outcome(self, attempts):
        o = MagicMock()
        o.captcha_attempts = attempts
        return o

    def test_folds_attempts_when_enabled(self, _enable_captcha_billing):
        from app.services.token_tracking_service import start_turn

        acc = start_turn()
        self._import_helper()(self._outcome(2))
        assert acc.total_cost_micros == 6000
        assert len(acc.calls) == 1
        assert acc.calls[0].call_kind == "web_crawl_captcha"

    def test_noop_when_zero_attempts(self, _enable_captcha_billing):
        from app.services.token_tracking_service import start_turn

        acc = start_turn()
        self._import_helper()(self._outcome(0))
        assert acc.calls == []

    def test_noop_when_billing_disabled(self, monkeypatch):
        from app.services.token_tracking_service import start_turn

        monkeypatch.setattr(config, "WEB_CRAWL_CAPTCHA_BILLING_ENABLED", False)
        acc = start_turn()
        self._import_helper()(self._outcome(3))
        assert acc.calls == []
