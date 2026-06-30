"""Phase 3c crawl-billing wiring in the webcrawler indexer.

System boundaries mocked: DB session, TaskLoggingService, the crawler, and the
document-conversion helpers. NOT mocked: WebCrawlCreditService (our own code)
and the indexer's billing decisions (owner resolution, pre-flight gate,
audit-then-charge, success counting).
"""

from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

import app.tasks.connector_indexers.webcrawler_indexer as _mod
from app.config import config
from app.proprietary.web_crawler import CrawlOutcomeStatus

pytestmark = pytest.mark.unit

_CONNECTOR_ID = 7
_WORKSPACE_ID = 1
_TRIGGER_USER = "00000000-0000-0000-0000-0000000000aa"
_OWNER_USER = UUID("00000000-0000-0000-0000-0000000000bb")


class _FakeUser:
    def __init__(self, balance_micros: int, reserved_micros: int = 0):
        self.credit_micros_balance = balance_micros
        self.credit_micros_reserved = reserved_micros


def _make_session(owner_id, balance_micros, reserved_micros=0):
    """Mock session serving owner-resolution, get_available_micros and charge."""
    fake_user = _FakeUser(balance_micros, reserved_micros)
    session = AsyncMock()
    session.add = MagicMock()
    session.no_autoflush = MagicMock()

    def _make_result(*_args, **_kwargs):
        result = MagicMock()
        # _resolve_workspace_owner → select(Workspace.user_id).scalar_one_or_none()
        result.scalar_one_or_none.return_value = owner_id
        # get_available_micros → .first() → (balance, reserved)
        result.first.return_value = (
            fake_user.credit_micros_balance,
            fake_user.credit_micros_reserved,
        )
        # charge_credits → .unique().scalar_one_or_none() → User
        result.unique.return_value.scalar_one_or_none.return_value = fake_user
        return result

    session.execute = AsyncMock(side_effect=_make_result)
    return session, fake_user


def _outcome(success: bool, content: str = "Hello content"):
    o = MagicMock()
    if success:
        o.status = CrawlOutcomeStatus.SUCCESS
        o.result = {
            "content": content,
            "metadata": {"title": "Title"},
            "crawler_type": "scrapling-static",
        }
        o.error = None
    else:
        o.status = CrawlOutcomeStatus.FAILED
        o.result = None
        o.error = "blocked"
    return o


@pytest.fixture
def indexer_env(monkeypatch):
    """Patch every system boundary the indexer touches; return the handles."""
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", True)
    monkeypatch.setattr(config, "WEB_CRAWL_MICROS_PER_SUCCESS", 1000)

    # Task logger: async no-op methods, log_task_start returns a sentinel.
    task_logger = MagicMock()
    task_logger.log_task_start = AsyncMock(return_value=MagicMock())
    task_logger.log_task_progress = AsyncMock()
    task_logger.log_task_failure = AsyncMock()
    task_logger.log_task_success = AsyncMock()
    monkeypatch.setattr(_mod, "TaskLoggingService", MagicMock(return_value=task_logger))

    # Connector + URL parsing.
    connector = MagicMock()
    connector.name = "wc"
    monkeypatch.setattr(_mod, "get_connector_by_id", AsyncMock(return_value=connector))
    monkeypatch.setattr(_mod, "parse_webcrawler_urls", lambda raw: list(raw))

    # Crawler.
    crawler = MagicMock()
    crawler.crawl_url = AsyncMock()
    crawler.format_to_structured_document = MagicMock(return_value="doc")
    monkeypatch.setattr(_mod, "WebCrawlerConnector", MagicMock(return_value=crawler))

    # Document-conversion + persistence helpers (system boundary).
    monkeypatch.setattr(
        _mod, "check_document_by_unique_identifier", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(
        _mod, "check_duplicate_document_by_hash", AsyncMock(return_value=None)
    )
    monkeypatch.setattr(_mod, "embed_text", lambda *_a, **_k: [0.1, 0.2])
    monkeypatch.setattr(_mod, "create_document_chunks", AsyncMock(return_value=[]))
    monkeypatch.setattr(_mod, "safe_set_chunks", AsyncMock())
    monkeypatch.setattr(_mod, "update_connector_last_indexed", AsyncMock())

    # Audit helper — assert it's the owner who is billed.
    record_usage = AsyncMock(return_value=MagicMock())
    monkeypatch.setattr(_mod, "record_token_usage", record_usage)

    return {
        "connector": connector,
        "crawler": crawler,
        "record_usage": record_usage,
        "task_logger": task_logger,
    }


async def _run(env, session, urls):
    env["connector"].config = {"INITIAL_URLS": urls}
    return await _mod.index_crawled_urls(
        session,
        _CONNECTOR_ID,
        _WORKSPACE_ID,
        _TRIGGER_USER,
    )


async def test_charges_owner_for_successful_crawls(indexer_env):
    session, user = _make_session(_OWNER_USER, balance_micros=100_000)
    indexer_env["crawler"].crawl_url.side_effect = [_outcome(True), _outcome(True)]

    total, warning = await _run(indexer_env, session, ["https://a.com", "https://b.com"])

    assert total == 2
    assert warning is None
    # Owner debited 2 * 1000.
    assert user.credit_micros_balance == 100_000 - 2000
    # One audit row, billed to the OWNER (not the triggering user), correct cost.
    indexer_env["record_usage"].assert_awaited_once()
    kwargs = indexer_env["record_usage"].await_args.kwargs
    assert kwargs["usage_type"] == "web_crawl"
    assert kwargs["user_id"] == _OWNER_USER
    assert kwargs["workspace_id"] == _WORKSPACE_ID
    assert kwargs["cost_micros"] == 2000


async def test_preflight_blocks_run_when_insufficient(indexer_env):
    # balance 1000 < 3 URLs * 1000 required.
    session, user = _make_session(_OWNER_USER, balance_micros=1000)

    total, warning = await _run(
        indexer_env, session, ["https://a.com", "https://b.com", "https://c.com"]
    )

    assert total == 0
    assert "insufficient crawl credit" in warning.lower()
    # Never crawled, never billed, balance untouched.
    indexer_env["crawler"].crawl_url.assert_not_awaited()
    indexer_env["record_usage"].assert_not_awaited()
    assert user.credit_micros_balance == 1000


async def test_failed_crawls_are_free(indexer_env):
    session, user = _make_session(_OWNER_USER, balance_micros=100_000)
    indexer_env["crawler"].crawl_url.side_effect = [_outcome(False)]

    total, _warning = await _run(indexer_env, session, ["https://a.com"])

    assert total == 0
    # crawls_succeeded == 0 → no audit, no charge.
    indexer_env["record_usage"].assert_not_awaited()
    assert user.credit_micros_balance == 100_000


async def test_disabled_skips_billing_but_still_crawls(indexer_env, monkeypatch):
    monkeypatch.setattr(config, "WEB_CRAWL_CREDIT_BILLING_ENABLED", False)
    session, user = _make_session(_OWNER_USER, balance_micros=100_000)
    indexer_env["crawler"].crawl_url.side_effect = [_outcome(True)]

    total, _warning = await _run(indexer_env, session, ["https://a.com"])

    assert total == 1
    indexer_env["crawler"].crawl_url.assert_awaited_once()
    indexer_env["record_usage"].assert_not_awaited()
    assert user.credit_micros_balance == 100_000
