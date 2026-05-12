import base64
import hashlib
import hmac
import json
import time
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.utils.oauth_security import OAuthStateManager

SECRET = "unit-test-secret"


def _encode_state(payload: dict, *, signature: str | None = None) -> str:
    """Build an OAuth state payload compatible with OAuthStateManager."""
    signature_payload = payload.copy()
    payload_str = json.dumps(signature_payload, sort_keys=True)
    computed_signature = hmac.new(
        SECRET.encode(),
        payload_str.encode(),
        hashlib.sha256,
    ).hexdigest()
    encoded_payload = {
        **signature_payload,
        "signature": signature if signature is not None else computed_signature,
    }
    return base64.urlsafe_b64encode(json.dumps(encoded_payload).encode()).decode()


def test_validate_state_accepts_fresh_signed_state():
    mgr = OAuthStateManager(secret_key=SECRET, max_age_seconds=600)
    user_id = uuid4()

    state = mgr.generate_secure_state(
        space_id=1,
        user_id=user_id,
        toolkit_id="googledrive",
    )

    decoded = mgr.validate_state(state)

    assert decoded["space_id"] == 1
    assert decoded["user_id"] == str(user_id)
    assert decoded["toolkit_id"] == "googledrive"


def test_validate_state_rejects_expired_state():
    mgr = OAuthStateManager(secret_key=SECRET, max_age_seconds=600)
    expired_state = _encode_state(
        {
            "space_id": 1,
            "user_id": str(uuid4()),
            "timestamp": int(time.time()) - 3600,
            "toolkit_id": "googledrive",
        }
    )

    with pytest.raises(HTTPException) as exc:
        mgr.validate_state(expired_state)

    assert exc.value.status_code == 400
    assert "expired" in exc.value.detail.lower()


def test_validate_state_rejects_tampered_signature():
    mgr = OAuthStateManager(secret_key=SECRET, max_age_seconds=600)
    tampered_state = _encode_state(
        {
            "space_id": 1,
            "user_id": str(uuid4()),
            "timestamp": int(time.time()),
            "toolkit_id": "googledrive",
        },
        signature="deadbeef" * 8,
    )

    with pytest.raises(HTTPException) as exc:
        mgr.validate_state(tampered_state)

    assert exc.value.status_code == 400
    assert "tampering" in exc.value.detail.lower()


def test_validate_state_rejects_malformed_state():
    mgr = OAuthStateManager(secret_key=SECRET)

    with pytest.raises(HTTPException) as exc:
        mgr.validate_state("not-base64-and-not-json")

    assert exc.value.status_code == 400
    assert "invalid state format" in exc.value.detail.lower()
