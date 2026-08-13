"""The podcast backfill only touches its own tool parts and carries the id."""

from __future__ import annotations

import pytest

from scripts.backfill_podcast_artifacts import _repoint, _tool_parts

pytestmark = pytest.mark.unit


def test_tool_parts_matches_only_podcast_tool_calls_with_a_result():
    content = [
        {"type": "text", "text": "hi"},
        {"type": "tool-call", "toolName": "generate_image", "result": {"artifact_id": 1}},
        {"type": "tool-call", "toolName": "generate_podcast"},  # no result
        {
            "type": "tool-call",
            "toolName": "generate_podcast",
            "result": {"podcast_id": 7},
        },
    ]

    parts = list(_tool_parts(content))

    assert len(parts) == 1
    assert parts[0]["result"]["podcast_id"] == 7


def test_repoint_adds_ids_without_dropping_the_legacy_id():
    result = {"status": "ready", "podcast_id": 7, "title": "Ep"}

    repointed = _repoint(result, 42, 3)

    assert repointed["artifact_id"] == 42
    assert repointed["workspace_id"] == 3
    # legacy id stays so pre-cutover shares still resolve
    assert repointed["podcast_id"] == 7
