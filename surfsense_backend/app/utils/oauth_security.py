"""
OAuth Security Utilities.

Provides secure state parameter generation/validation and token encryption
for OAuth 2.0 flows.
"""

import base64
import hashlib
import hmac
import json
import logging
import time
from uuid import UUID

from cryptography.fernet import Fernet
from fastapi import HTTPException

logger = logging.getLogger(__name__)


class OAuthStateManager:
    """Manages secure OAuth state parameters with HMAC signatures."""

    def __init__(self, secret_key: str, max_age_seconds: int = 600):
        """
        Initialize OAuth state manager.

        Args:
            secret_key: Secret key for HMAC signing (should be SECRET_KEY from config)
            max_age_seconds: Maximum age of state parameter in seconds (default 10 minutes)
        """
        if not secret_key:
            raise ValueError("secret_key is required for OAuth state management")
        self.secret_key = secret_key
        self.max_age_seconds = max_age_seconds

    def generate_secure_state(
        self, space_id: int, user_id: UUID, **extra_fields
    ) -> str:
        """
        Generate cryptographically signed state parameter.

        Args:
            space_id: The search space ID
            user_id: The user ID
            **extra_fields: Additional fields to include in state (e.g., code_verifier for PKCE)

        Returns:
            Base64-encoded state parameter with HMAC signature
        """
        timestamp = int(time.time())
        state_payload = {
            "space_id": space_id,
            "user_id": str(user_id),
            "timestamp": timestamp,
        }

        # Add any extra fields (e.g., code_verifier for PKCE)
        state_payload.update(extra_fields)

        # Create signature
        payload_str = json.dumps(state_payload, sort_keys=True)
        signature = hmac.new(
            self.secret_key.encode(),
            payload_str.encode(),
            hashlib.sha256,
        ).hexdigest()

        # Include signature in state
        state_payload["signature"] = signature
        state_encoded = base64.urlsafe_b64encode(
            json.dumps(state_payload).encode()
        ).decode()

        return state_encoded

    def validate_state(self, state: str) -> dict:
        """
        Validate and decode state parameter with signature verification.

        Args:
            state: The state parameter from OAuth callback

        Returns:
            Decoded state data (space_id, user_id, timestamp)

        Raises:
            HTTPException: If state is invalid, expired, or tampered with
        """
        try:
            decoded = base64.urlsafe_b64decode(state.encode()).decode()
            data = json.loads(decoded)
        except Exception as e:
            raise HTTPException(
                status_code=400, detail=f"Invalid state format: {e!s}"
            ) from e

        # Verify signature exists
        signature = data.pop("signature", None)
        if not signature:
            raise HTTPException(status_code=400, detail="Missing state signature")

        # Verify signature
        payload_str = json.dumps(data, sort_keys=True)
        expected_signature = hmac.new(
            self.secret_key.encode(),
            payload_str.encode(),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(signature, expected_signature):
            raise HTTPException(
                status_code=400, detail="Invalid state signature - possible tampering"
            )

        # Verify timestamp (prevent replay attacks)
        timestamp = data.get("timestamp", 0)
        current_time = time.time()
        age = current_time - timestamp

        if age < 0:
            raise HTTPException(status_code=400, detail="Invalid state timestamp")

        if age > self.max_age_seconds:
            raise HTTPException(
                status_code=400,
                detail="State parameter expired. Please try again.",
            )

        return data


class TokenEncryption:
    """Encrypt/decrypt sensitive OAuth tokens for storage."""

    def __init__(self, secret_key: str):
        """
        Initialize token encryption.

        Args:
            secret_key: Secret key for encryption (should be SECRET_KEY from config)
        """
        if not secret_key:
            raise ValueError("secret_key is required for token encryption")
        # Derive Fernet key from secret using SHA256
        # Note: In production, consider using HKDF for key derivation
        key = base64.urlsafe_b64encode(hashlib.sha256(secret_key.encode()).digest())
        try:
            self.cipher = Fernet(key)
        except Exception as e:
            raise ValueError(f"Failed to initialize encryption cipher: {e!s}") from e

    def encrypt_token(self, token: str) -> str:
        """
        Encrypt a token for storage.

        Args:
            token: Plaintext token to encrypt

        Returns:
            Encrypted token string
        """
        if not token:
            return token
        try:
            return self.cipher.encrypt(token.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to encrypt token: {e!s}")
            raise ValueError(f"Token encryption failed: {e!s}") from e

    def decrypt_token(self, encrypted_token: str) -> str:
        """
        Decrypt a stored token.

        Args:
            encrypted_token: Encrypted token string

        Returns:
            Decrypted plaintext token
        """
        if not encrypted_token:
            return encrypted_token
        try:
            return self.cipher.decrypt(encrypted_token.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to decrypt token: {e!s}")
            raise ValueError(f"Token decryption failed: {e!s}") from e

    def is_encrypted(self, token: str) -> bool:
        """
        Check if a token appears to be encrypted.

        Args:
            token: Token string to check

        Returns:
            True if token appears encrypted, False otherwise
        """
        if not token:
            return False
        # Encrypted tokens are base64-encoded and have specific format
        # This is a heuristic check - encrypted tokens are longer and base64-like
        try:
            # Try to decode as base64
            base64.urlsafe_b64decode(token.encode())
            # If it's base64 and reasonably long, likely encrypted
            return len(token) > 20
        except Exception:
            return False
