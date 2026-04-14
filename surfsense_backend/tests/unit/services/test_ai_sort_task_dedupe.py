"""Unit tests for AI sort task Redis deduplication lock."""

from unittest.mock import MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


def test_lock_key_format():
    from app.tasks.celery_tasks.document_tasks import _ai_sort_lock_key

    key = _ai_sort_lock_key(42)
    assert key == "ai_sort:search_space:42:lock"


def test_lock_prevents_duplicate_run():
    """When the Redis lock already exists, the task should skip execution."""

    mock_redis = MagicMock()
    mock_redis.set.return_value = False  # Lock already held

    with (
        patch(
            "app.tasks.celery_tasks.document_tasks._get_ai_sort_redis",
            return_value=mock_redis,
        ),
        patch(
            "app.tasks.celery_tasks.document_tasks.get_celery_session_maker"
        ) as mock_session_maker,
    ):
        import asyncio

        from app.tasks.celery_tasks.document_tasks import _ai_sort_search_space_async

        loop = asyncio.new_event_loop()
        try:
            loop.run_until_complete(_ai_sort_search_space_async(1, "user-123"))
        finally:
            loop.close()

        # Session maker should never be called since lock was not acquired
        mock_session_maker.assert_not_called()
