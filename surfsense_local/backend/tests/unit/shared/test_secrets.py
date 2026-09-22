import pytest

from modules.llm.models import ProviderConnection
from shared.secrets import UnreadableSecretError, decrypt, encrypt


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


def test_unreadable_ciphertext_fails_closed_as_a_named_condition() -> None:
    """A flipped byte yields no key, and says which condition it hit.

    Named rather than left as the library's `InvalidToken`, because this is
    reachable without any tampering: the per install secret lives in the OS
    keychain, and a keychain reset or a backup restored onto another machine
    leaves every stored key undecryptable. Callers have to tell that apart from
    a bug to say anything useful about it.
    """
    token = bytearray(encrypt("sk-1"))
    token[-1] ^= 0xFF
    with pytest.raises(UnreadableSecretError):
        decrypt(bytes(token))


def test_rotated_secret_reads_as_no_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """secret.bin reminted: the old ciphertext is gone, not a 500."""
    connection = ProviderConnection(
        label="x", provider="openai_compatible", base_url="http://h", api_key="sk-1"
    )
    token = connection.api_key_ciphertext
    monkeypatch.setenv("SURFSENSE_LOCAL_SECRET", "a-different-secret")
    from shared.secrets import _fernet

    _fernet.cache_clear()
    stale = ProviderConnection(
        label="y", provider="openai_compatible", base_url="http://h"
    )
    stale.api_key_ciphertext = token
    assert stale.api_key is None
    assert stale.api_key_ciphertext is None
