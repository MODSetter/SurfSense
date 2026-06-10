from datetime import UTC, datetime, timedelta

import pytest

from app.db import ExternalChatBindingState
from app.gateway.pairing import generate_pairing_code, redeem_pairing_code


def test_generate_pairing_code_is_short_display_token():
    code = generate_pairing_code()

    assert len(code) >= 8
    assert "\n" not in code


@pytest.mark.asyncio
async def test_redeem_pairing_code_binds_pending_row(mocker):
    binding = mocker.Mock()
    binding.state = ExternalChatBindingState.PENDING
    binding.pairing_code_expires_at = datetime.now(UTC) + timedelta(minutes=1)
    scalars = mocker.Mock()
    scalars.first.return_value = binding
    result = mocker.Mock()
    result.scalars.return_value = scalars
    session = mocker.AsyncMock()
    session.execute.return_value = result

    redeemed = await redeem_pairing_code(
        session,
        code="abc",
        external_peer_id="telegram:123",
        external_peer_kind="direct",
        external_display_name="Anish",
        external_username="anish",
    )

    assert redeemed is binding
    assert binding.state == ExternalChatBindingState.BOUND
    assert binding.external_peer_id == "telegram:123"
    assert binding.pairing_code is None
