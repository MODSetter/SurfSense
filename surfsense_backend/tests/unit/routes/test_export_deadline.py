"""`GET /api/v1/export` ends in words, not a dropped connection (#2006)."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.routes import export_routes

pytestmark = pytest.mark.unit

_AUTH = SimpleNamespace(user=SimpleNamespace(id="user-1"))


async def test_an_export_past_its_deadline_is_stopped_with_something_to_act_on(
    monkeypatch: pytest.MonkeyPatch,
):
    cancelled: list[bool] = []

    async def never_finishes(session, user_id):
        try:
            await asyncio.sleep(60)
        except asyncio.CancelledError:
            cancelled.append(True)
            raise

    monkeypatch.setattr(export_routes, "build_account_export_zip", never_finishes)
    monkeypatch.setattr(export_routes.config, "ACCOUNT_EXPORT_TIMEOUT_SECONDS", 0.05)

    with pytest.raises(HTTPException) as raised:
        await export_routes.export_account(session=None, auth=_AUTH)

    assert raised.value.status_code == 504
    detail = raised.value.detail
    assert isinstance(detail, str)
    # What happened, that nothing was lost, and what to do next.
    assert "stopped" in detail
    assert "still here" in detail
    assert "/contact" in detail
    # The build itself was cancelled, not left running behind the answer.
    assert cancelled == [True]


async def test_an_export_inside_its_deadline_is_streamed_as_before(
    monkeypatch: pytest.MonkeyPatch, tmp_path
):
    archive = tmp_path / "export.zip"
    archive.write_bytes(b"PK-not-really")

    async def quick(session, user_id):
        return SimpleNamespace(
            zip_path=str(archive),
            export_name="surfsense-export",
            zip_size=archive.stat().st_size,
            skipped_docs=["one"],
        )

    monkeypatch.setattr(export_routes, "build_account_export_zip", quick)

    response = await export_routes.export_account(session=None, auth=_AUTH)

    assert response.media_type == "application/zip"
    assert response.headers["content-length"] == str(len(b"PK-not-really"))
    assert response.headers["x-skipped-documents"] == "1"
    body = b"".join([chunk async for chunk in response.body_iterator])
    assert body == b"PK-not-really"
    assert not archive.exists()


@pytest.mark.parametrize("setting", [0, -1])
async def test_a_deadline_of_zero_or_less_means_none(
    monkeypatch: pytest.MonkeyPatch, tmp_path, setting: float
):
    """Passed to the timeout as it is, a zero would be a deadline already
    missed: every export would be stopped before it began."""
    archive = tmp_path / "export.zip"
    archive.write_bytes(b"PK")

    async def slower_than_zero(session, user_id):
        await asyncio.sleep(0.01)
        return SimpleNamespace(
            zip_path=str(archive),
            export_name="surfsense-export",
            zip_size=2,
            skipped_docs=[],
        )

    monkeypatch.setattr(export_routes, "build_account_export_zip", slower_than_zero)
    monkeypatch.setattr(export_routes.config, "ACCOUNT_EXPORT_TIMEOUT_SECONDS", setting)

    response = await export_routes.export_account(session=None, auth=_AUTH)

    assert response.media_type == "application/zip"
