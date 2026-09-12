"""Unit tests for ensure_folder_hierarchy_with_depth_validation."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_creates_missing_folders_in_chain():
    """Should create all folders when none exist."""
    from app.services.folder_service import (
        ensure_folder_hierarchy_with_depth_validation,
    )

    session = AsyncMock()
    # All lookups return None (no existing folders)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    session.execute.return_value = mock_result

    folder_instances = []

    def track_add(obj):
        folder_instances.append(obj)

    session.add = track_add

    with (
        patch(
            "app.services.folder_service.validate_folder_depth", new_callable=AsyncMock
        ),
        patch(
            "app.services.folder_service.generate_folder_position",
            new_callable=AsyncMock,
            return_value="a0",
        ),
    ):
        # Mock flush to assign IDs
        call_count = 0

        async def mock_flush():
            nonlocal call_count
            call_count += 1
            if folder_instances:
                folder_instances[-1].id = call_count

        session.flush = mock_flush

        segments = [
            {"name": "Slack", "metadata": {"source": "slack"}},
            {"name": "2025-03-15", "metadata": {"source": "slack"}},
        ]

        result = await ensure_folder_hierarchy_with_depth_validation(
            session, 1, segments
        )

        assert len(folder_instances) == 2
        assert folder_instances[0].name == "Slack"
        assert folder_instances[1].name == "2025-03-15"
        assert result is folder_instances[-1]


@pytest.mark.asyncio
async def test_reuses_existing_folder():
    """When a folder already exists, it should be reused, not created."""
    from app.services.folder_service import (
        ensure_folder_hierarchy_with_depth_validation,
    )

    session = AsyncMock()

    existing_folder = MagicMock()
    existing_folder.id = 42

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_folder
    session.execute.return_value = mock_result

    segments = [{"name": "Existing", "metadata": None}]

    result = await ensure_folder_hierarchy_with_depth_validation(session, 1, segments)

    assert result is existing_folder
    session.add.assert_not_called()


def _session_yielding(scalar_values):
    """AsyncMock session whose ``execute().scalar_one_or_none()`` walks the list."""
    values = iter(scalar_values)

    def make_result(*_args, **_kwargs):
        res = MagicMock()
        res.scalar_one_or_none.return_value = next(values)
        return res

    session = AsyncMock()
    session.execute.side_effect = make_result
    return session


@pytest.mark.asyncio
async def test_resolve_returns_leaf_id_for_existing_chain():
    """Every segment exists -> the deepest folder id, without creating rows."""
    from app.services.folder_service import resolve_folder_id_by_parts

    session = _session_yielding([10, 11, 12])

    result = await resolve_folder_id_by_parts(
        session, workspace_id=1, folder_parts=["GitHub", "owner", "repo"]
    )

    assert result == 12
    assert session.execute.await_count == 3
    session.add.assert_not_called()


@pytest.mark.asyncio
async def test_resolve_returns_none_when_a_segment_is_missing():
    """A gap anywhere short-circuits to None (folder not indexed yet)."""
    from app.services.folder_service import resolve_folder_id_by_parts

    session = _session_yielding([10, None])

    result = await resolve_folder_id_by_parts(
        session, workspace_id=1, folder_parts=["GitHub", "owner", "repo"]
    )

    assert result is None
    # Stops at the missing segment; never looks up "repo".
    assert session.execute.await_count == 2


@pytest.mark.asyncio
async def test_resolve_returns_none_for_empty_parts():
    from app.services.folder_service import resolve_folder_id_by_parts

    session = AsyncMock()

    result = await resolve_folder_id_by_parts(
        session, workspace_id=1, folder_parts=[]
    )

    assert result is None
    session.execute.assert_not_called()
