import base64
import hashlib
import logging
import os
from functools import lru_cache

from cryptography.fernet import Fernet, InvalidToken

from shared.config import get_storage_settings

log = logging.getLogger(__name__)


class UnreadableSecretError(Exception):
    """Stored ciphertext this install's secret cannot open.

    Not a corruption bug. The secret lives in the OS keychain, so a keychain
    reset or a backup restored onto another machine leaves every stored key
    undecryptable while the rows themselves are intact. The key is gone either
    way, and the only recovery is entering it again, so this is raised as its
    own condition rather than leaking `InvalidToken` to a caller that can only
    treat it as a crash.
    """

    def __init__(self) -> None:
        super().__init__(
            "the stored key could not be read on this machine, so it has to be "
            "entered again"
        )


@lru_cache
def _fernet() -> Fernet:
    secret = os.environ.get("SURFSENSE_LOCAL_SECRET") or _file_secret()
    digest = hashlib.sha256(secret.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def _file_secret() -> str:
    # ponytail: bare `uv run` only; the secret sits next to the database it
    # protects. Electron always passes SURFSENSE_LOCAL_SECRET from the OS keychain.
    path = get_storage_settings().data_dir / "secret"
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(os.urandom(32).hex())
        path.chmod(0o600)
        log.warning("SURFSENSE_LOCAL_SECRET unset; using %s", path)
    return path.read_text().strip()


def encrypt(value: str) -> bytes:
    """Encrypt a provider API key for storage."""
    return _fernet().encrypt(value.encode())


def decrypt(token: bytes) -> str:
    """Recover a provider API key stored by ``encrypt``."""
    try:
        return _fernet().decrypt(token).decode()
    except InvalidToken as error:
        raise UnreadableSecretError from error
