"""Creating a podcast proposes a brief and opens the review gate.

Driven through the real POST endpoint (auth + DB on one transaction): the row is
created, a brief is proposed inline from defaults, and the podcast lands in
``awaiting_brief`` with a complete spec and nothing generated yet.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.integration

BASE = "/api/v1/podcasts"


async def test_create_proposes_brief_and_opens_gate(client, db_search_space):
    resp = await client.post(
        BASE,
        json={
            "title": "My Episode",
            "search_space_id": db_search_space.id,
            "source_content": "A long piece of source content about a topic.",
        },
    )

    assert resp.status_code == 201
    body = resp.json()
    assert body["title"] == "My Episode"
    assert body["status"] == "awaiting_brief"
    assert body["spec_version"] == 1
    assert body["spec"] is not None
    assert body["spec"]["language"] == "en"
    assert len(body["spec"]["speakers"]) == 2
    assert body["transcript"] is None
    assert body["has_audio"] is False


async def test_create_honors_requested_speaker_count(client, db_search_space):
    resp = await client.post(
        BASE,
        json={
            "title": "Solo",
            "search_space_id": db_search_space.id,
            "source_content": "Content.",
            "speaker_count": 3,
        },
    )

    assert resp.status_code == 201
    assert len(resp.json()["spec"]["speakers"]) == 3
