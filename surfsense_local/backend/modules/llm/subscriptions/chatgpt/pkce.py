import base64
import hashlib
import secrets
from dataclasses import dataclass, field


def _random() -> str:
    return secrets.token_urlsafe(48)


@dataclass(frozen=True)
class Pkce:
    """One sign-in's single-use values: PKCE verifier, CSRF state and ID-token nonce."""

    verifier: str = field(default_factory=_random)
    state: str = field(default_factory=_random)
    nonce: str = field(default_factory=_random)

    @property
    def challenge(self) -> str:
        digest = hashlib.sha256(self.verifier.encode()).digest()
        return base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
