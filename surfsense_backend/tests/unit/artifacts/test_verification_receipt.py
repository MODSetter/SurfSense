from __future__ import annotations

import json

import pytest

from app.artifacts.verification.receipt import (
    RECEIPT_MAX_AGE_SECONDS,
    VerificationReceipt,
    read_receipt,
    receipt_path,
    write_receipt,
)
from tests.utils.fake_sandbox import FakeSandboxSession

SECRET = "test-secret"
WORKSPACE_ID = 7


def _receipt() -> VerificationReceipt:
    return VerificationReceipt(
        workspace_id=WORKSPACE_ID,
        session_id=FakeSandboxSession.session_id,
        format="docx",
        primary_path="/workspace/report.docx",
        primary_sha256="a" * 64,
        preview_path="/tmp/report.pdf",
        preview_sha256="b" * 64,
        page_count=2,
        visual="clean",
        issued_at=100,
    )


async def test_receipt_round_trip():
    session = FakeSandboxSession()

    await write_receipt(session, _receipt(), SECRET)

    assert (
        await read_receipt(
            session,
            SECRET,
            workspace_id=WORKSPACE_ID,
            primary_path=_receipt().primary_path,
            now=100,
        )
        == _receipt()
    )


async def test_receipts_for_multiple_artifacts_do_not_overwrite_each_other():
    session = FakeSandboxSession()
    docx_receipt = _receipt()
    pdf_receipt = docx_receipt.model_copy(
        update={
            "format": "pdf",
            "primary_path": "/workspace/report.pdf",
            "primary_sha256": "c" * 64,
            "preview_path": None,
            "preview_sha256": None,
        }
    )

    await write_receipt(session, docx_receipt, SECRET)
    await write_receipt(session, pdf_receipt, SECRET)

    assert await read_receipt(
        session,
        SECRET,
        workspace_id=WORKSPACE_ID,
        primary_path=docx_receipt.primary_path,
        now=100,
    ) == docx_receipt
    assert await read_receipt(
        session,
        SECRET,
        workspace_id=WORKSPACE_ID,
        primary_path=pdf_receipt.primary_path,
        now=100,
    ) == pdf_receipt


async def test_receipt_rejects_tampered_payload():
    session = FakeSandboxSession()
    await write_receipt(session, _receipt(), SECRET)
    path = receipt_path(_receipt().primary_path)
    envelope = json.loads(session.files[path])
    envelope["payload"]["primary_sha256"] = "c" * 64
    session.files[path] = json.dumps(envelope).encode()

    with pytest.raises(ValueError, match="invalid signature"):
        await read_receipt(
            session,
            SECRET,
            workspace_id=WORKSPACE_ID,
            primary_path=_receipt().primary_path,
            now=100,
        )


async def test_receipt_rejects_wrong_key():
    session = FakeSandboxSession()
    await write_receipt(session, _receipt(), SECRET)

    with pytest.raises(ValueError, match="invalid signature"):
        await read_receipt(
            session,
            "wrong-secret",
            workspace_id=WORKSPACE_ID,
            primary_path=_receipt().primary_path,
            now=100,
        )


async def test_receipt_rejects_expired_payload():
    session = FakeSandboxSession()
    await write_receipt(session, _receipt(), SECRET)

    with pytest.raises(ValueError, match="expired"):
        await read_receipt(
            session,
            SECRET,
            workspace_id=WORKSPACE_ID,
            primary_path=_receipt().primary_path,
            now=100 + RECEIPT_MAX_AGE_SECONDS + 1,
        )


async def test_blank_receipt_is_not_verified():
    path = _receipt().primary_path
    session = FakeSandboxSession({receipt_path(path): b""})

    with pytest.raises(ValueError, match="has not been verified"):
        await read_receipt(
            session,
            SECRET,
            workspace_id=WORKSPACE_ID,
            primary_path=path,
        )


async def test_receipt_rejects_another_workspace():
    session = FakeSandboxSession()
    await write_receipt(session, _receipt(), SECRET)

    with pytest.raises(ValueError, match="another workspace or sandbox"):
        await read_receipt(
            session,
            SECRET,
            workspace_id=WORKSPACE_ID + 1,
            primary_path=_receipt().primary_path,
            now=100,
        )


async def test_receipt_rejects_unsigned_extra_fields():
    session = FakeSandboxSession()
    await write_receipt(session, _receipt(), SECRET)
    path = receipt_path(_receipt().primary_path)
    envelope = json.loads(session.files[path])
    envelope["payload"]["admin"] = True
    session.files[path] = json.dumps(envelope).encode()

    with pytest.raises(ValueError, match="unreadable"):
        await read_receipt(
            session,
            SECRET,
            workspace_id=WORKSPACE_ID,
            primary_path=_receipt().primary_path,
            now=100,
        )
