"""notify_document posts a row change only when an API address is configured."""

import pytest

from modules.documents.models import Document, DocumentStatus, DocumentType
from worker import notify
from worker.notify import notify_document_updates

pytestmark = pytest.mark.unit


def _document() -> Document:
    return Document(
        id=7,
        workspace_id=3,
        title="n",
        document_type=DocumentType.NOTE,
        status=DocumentStatus.READY,
    )


def test_it_posts_the_change_when_the_api_address_is_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """With host and port in the env, it POSTs the workspace, kind, ids and status."""
    monkeypatch.setenv("SURFSENSE_LOCAL_HOST", "127.0.0.1")
    monkeypatch.setenv("SURFSENSE_LOCAL_PORT", "8123")
    sent: dict = {}

    def fake_post(url: str, *, json: dict, timeout: float) -> None:
        sent["url"] = url
        sent["json"] = json

    monkeypatch.setattr(notify.httpx, "post", fake_post)

    notify_document_updates(_document())

    assert sent["url"] == "http://127.0.0.1:8123/internal/events"
    assert sent["json"] == {
        "workspace_id": 3,
        "kind": "documents",
        "ids": [7],
        "status": "ready",
    }


def test_it_is_a_no_op_without_a_port(monkeypatch: pytest.MonkeyPatch) -> None:
    """No supervising API to tell (tests, a bare worker): it must not post."""
    monkeypatch.delenv("SURFSENSE_LOCAL_PORT", raising=False)
    posted = False

    def fake_post(*args: object, **kwargs: object) -> None:
        nonlocal posted
        posted = True

    monkeypatch.setattr(notify.httpx, "post", fake_post)

    notify_document_updates(_document())

    assert posted is False
