import base64
import hashlib
import logging
import os
from functools import lru_cache

from cryptography.fernet import Fernet

from shared.config import get_storage_settings

log = logging.getLogger(__name__)


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
    return _fernet().decrypt(token).decode()
