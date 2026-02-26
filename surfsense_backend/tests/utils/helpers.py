"""Shared test helpers for authentication, polling, and cleanup."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path

import httpx

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

BACKEND_URL = os.environ.get("TEST_BACKEND_URL", "http://localhost:8000")
TEST_EMAIL = os.environ.get("TEST_USER_EMAIL", "testuser@surfsense.com")
TEST_PASSWORD = os.environ.get("TEST_USER_PASSWORD", "testpassword123")


async def get_auth_token(client: httpx.AsyncClient) -> str:
    """Log in and return a Bearer JWT token, registering the user first if needed."""
    response = await client.post(
        "/auth/jwt/login",
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    if response.status_code == 200:
        return response.json()["access_token"]

    reg_response = await client.post(
        "/auth/register",
        json={"email": TEST_EMAIL, "password": TEST_PASSWORD},
    )
    assert reg_response.status_code == 201, (
        f"Registration failed ({reg_response.status_code}): {reg_response.text}"
    )

    response = await client.post(
        "/auth/jwt/login",
        data={"username": TEST_EMAIL, "password": TEST_PASSWORD},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert response.status_code == 200, (
        f"Login after registration failed ({response.status_code}): {response.text}"
    )
    return response.json()["access_token"]


async def get_search_space_id(client: httpx.AsyncClient, token: str) -> int:
    """Fetch the first search space owned by the test user."""
    resp = await client.get(
        "/api/v1/searchspaces",
        headers=auth_headers(token),
    )
    assert resp.status_code == 200, (
        f"Failed to list search spaces ({resp.status_code}): {resp.text}"
    )
    spaces = resp.json()
    assert len(spaces) > 0, "No search spaces found for test user"
    return spaces[0]["id"]


def auth_headers(token: str) -> dict[str, str]:
    """Return Authorization header dict for a Bearer token."""
    return {"Authorization": f"Bearer {token}"}


async def upload_file(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    fixture_name: str,
    *,
    search_space_id: int,
    filename_override: str | None = None,
) -> httpx.Response:
    """Upload a single fixture file and return the raw response."""
    file_path = FIXTURES_DIR / fixture_name
    upload_name = filename_override or fixture_name
    with open(file_path, "rb") as f:
        return await client.post(
            "/api/v1/documents/fileupload",
            headers=headers,
            files={"files": (upload_name, f)},
            data={"search_space_id": str(search_space_id)},
        )


async def upload_multiple_files(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    fixture_names: list[str],
    *,
    search_space_id: int,
) -> httpx.Response:
    """Upload multiple fixture files in a single request."""
    files = []
    open_handles = []
    try:
        for name in fixture_names:
            fh = open(FIXTURES_DIR / name, "rb")  # noqa: SIM115
            open_handles.append(fh)
            files.append(("files", (name, fh)))

        return await client.post(
            "/api/v1/documents/fileupload",
            headers=headers,
            files=files,
            data={"search_space_id": str(search_space_id)},
        )
    finally:
        for fh in open_handles:
            fh.close()


async def poll_document_status(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    document_ids: list[int],
    *,
    search_space_id: int,
    timeout: float = 180.0,
    interval: float = 3.0,
) -> dict[int, dict]:
    """
    Poll ``GET /api/v1/documents/status`` until every document reaches a
    terminal state (``ready`` or ``failed``) or *timeout* seconds elapse.

    Returns a mapping of ``{document_id: status_item_dict}``.

    Retries on transient transport errors until timeout.
    """
    ids_param = ",".join(str(d) for d in document_ids)
    terminal_states = {"ready", "failed"}
    elapsed = 0.0
    items: dict[int, dict] = {}
    last_transport_error: Exception | None = None

    while elapsed < timeout:
        try:
            resp = await client.get(
                "/api/v1/documents/status",
                headers=headers,
                params={
                    "search_space_id": search_space_id,
                    "document_ids": ids_param,
                },
            )
        except (httpx.ReadError, httpx.ConnectError, httpx.TimeoutException) as exc:
            last_transport_error = exc
            await asyncio.sleep(interval)
            elapsed += interval
            continue

        assert resp.status_code == 200, (
            f"Status poll failed ({resp.status_code}): {resp.text}"
        )

        items = {item["id"]: item for item in resp.json()["items"]}
        if all(
            items.get(did, {}).get("status", {}).get("state") in terminal_states
            for did in document_ids
        ):
            return items

        await asyncio.sleep(interval)
        elapsed += interval

    raise TimeoutError(
        f"Documents {document_ids} did not reach terminal state within {timeout}s. "
        f"Last status: {items}. "
        f"Last transport error: {last_transport_error!r}"
    )


async def get_document(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    document_id: int,
) -> dict:
    """Fetch a single document by ID."""
    resp = await client.get(
        f"/api/v1/documents/{document_id}",
        headers=headers,
    )
    assert resp.status_code == 200, (
        f"GET document {document_id} failed ({resp.status_code}): {resp.text}"
    )
    return resp.json()


async def delete_document(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    document_id: int,
) -> httpx.Response:
    """Delete a document by ID, returning the raw response."""
    return await client.delete(
        f"/api/v1/documents/{document_id}",
        headers=headers,
    )


async def get_notifications(
    client: httpx.AsyncClient,
    headers: dict[str, str],
    *,
    type_filter: str | None = None,
    search_space_id: int | None = None,
    limit: int = 50,
) -> list[dict]:
    """Fetch notifications for the authenticated user, optionally filtered by type."""
    params: dict[str, str | int] = {"limit": limit}
    if type_filter:
        params["type"] = type_filter
    if search_space_id is not None:
        params["search_space_id"] = search_space_id

    resp = await client.get(
        "/api/v1/notifications",
        headers=headers,
        params=params,
    )
    assert resp.status_code == 200, (
        f"GET notifications failed ({resp.status_code}): {resp.text}"
    )
    return resp.json()["items"]
