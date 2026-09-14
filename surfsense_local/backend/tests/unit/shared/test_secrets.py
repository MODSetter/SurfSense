import pytest
from cryptography.fernet import InvalidToken

from modules.llm.models import ProviderConnection
from shared.secrets import decrypt, encrypt


def test_api_key_round_trips_and_is_not_stored_in_clear() -> None:
    """The column holds ciphertext; the attribute still reads the key back."""
    connection = ProviderConnection(
        label="x", provider="openai_compatible", base_url="http://h", api_key="sk-1"
    )
    assert connection.api_key_ciphertext is not None
    assert b"sk-1" not in connection.api_key_ciphertext
    assert connection.api_key == "sk-1"

    connection.api_key = None
    assert connection.api_key_ciphertext is None
    assert connection.api_key is None


def test_tampered_ciphertext_is_rejected() -> None:
    """A flipped byte fails closed instead of yielding a wrong key."""
    token = bytearray(encrypt("sk-1"))
    token[-1] ^= 0xFF
    with pytest.raises(InvalidToken):
        decrypt(bytes(token))
