"""GET /documents/{id} content-negotiates its representation (real HTTP, DB).

Proves the live wiring the unit tests can't: ``Accept: text/markdown`` returns a
conformant OKF concept, and the default request still returns the JSON record -
both off the same endpoint, through the real FastAPI stack.
"""

from __future__ import annotations

import httpx
import pytest

from app.services.okf import is_conformant_concept
from tests.utils.helpers import poll_document_status, upload_file

pytestmark = pytest.mark.integration


async def _ready_doc_id(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    workspace_id: int,
    cleanup_doc_ids: list[int],
) -> int:
    resp = await upload_file(client, headers, "sample.txt", workspace_id=workspace_id)
    assert resp.status_code == 200
    doc_ids = resp.json()["document_ids"]
    cleanup_doc_ids.extend(doc_ids)
    statuses = await poll_document_status(
        client, headers, doc_ids, workspace_id=workspace_id
    )
    assert statuses[doc_ids[0]]["status"]["state"] == "ready"
    return doc_ids[0]


async def test_accept_markdown_returns_conformant_okf_concept(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    workspace_id: int,
    cleanup_doc_ids: list[int],
):
    doc_id = await _ready_doc_id(client, headers, workspace_id, cleanup_doc_ids)

    resp = await client.get(
        f"/api/v1/documents/{doc_id}",
        headers={**headers, "Accept": "text/markdown"},
    )

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/markdown")
    assert is_conformant_concept(resp.text)


async def test_default_accept_returns_json_record(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    workspace_id: int,
    cleanup_doc_ids: list[int],
):
    doc_id = await _ready_doc_id(client, headers, workspace_id, cleanup_doc_ids)

    resp = await client.get(f"/api/v1/documents/{doc_id}", headers=headers)

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/json")
    assert resp.json()["id"] == doc_id
