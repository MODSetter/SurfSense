"""
Two-Factor Authentication service using TOTP.
"""

import base64
import hashlib
import io
import secrets
from typing import Any

import pyotp
import qrcode
from passlib.context import CryptContext

# Password context for hashing backup codes
backup_code_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class TwoFactorAuthService:
    """Service for managing TOTP-based two-factor authentication."""

    def __init__(self, app_name: str = "SurfSense"):
        """
        Initialize the 2FA service.

        Args:
            app_name: Application name shown in authenticator apps
        """
        self.app_name = app_name

    def generate_secret(self) -> str:
        """
        Generate a new TOTP secret.

        Returns:
            Base32 encoded secret string
        """
        return pyotp.random_base32()

    def get_totp_uri(self, secret: str, email: str) -> str:
        """
        Generate the TOTP provisioning URI for authenticator apps.

        Args:
            secret: TOTP secret
            email: User's email address

        Returns:
            otpauth:// URI string
        """
        totp = pyotp.TOTP(secret)
        return totp.provisioning_uri(name=email, issuer_name=self.app_name)

    def generate_qr_code(self, secret: str, email: str) -> str:
        """
        Generate a QR code image for the TOTP secret.

        Args:
            secret: TOTP secret
            email: User's email address

        Returns:
            Base64 encoded PNG image
        """
        uri = self.get_totp_uri(secret, email)

        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(uri)
        qr.make(fit=True)

        # Create image
        img = qr.make_image(fill_color="black", back_color="white")

        # Convert to base64
        buffer = io.BytesIO()
        img.save(buffer, format="PNG")
        buffer.seek(0)

        return base64.b64encode(buffer.getvalue()).decode("utf-8")

    def verify_totp(self, secret: str, code: str) -> bool:
        """
        Verify a TOTP code.

        Args:
            secret: TOTP secret
            code: 6-digit code from authenticator app

        Returns:
            True if code is valid, False otherwise
        """
        if not secret or not code:
            return False

        try:
            totp = pyotp.TOTP(secret)
            # Allow 1 step of clock drift (30 seconds before/after)
            return totp.verify(code, valid_window=1)
        except Exception:
            return False

    def generate_backup_codes(self, count: int = 10) -> tuple[list[str], list[str]]:
        """
        Generate backup codes for account recovery.

        Args:
            count: Number of backup codes to generate

        Returns:
            Tuple of (plain_codes, hashed_codes)
        """
        plain_codes = []
        hashed_codes = []

        for _ in range(count):
            # Generate 8-character code in format XXXX-XXXX
            code_part1 = secrets.token_hex(2).upper()
            code_part2 = secrets.token_hex(2).upper()
            plain_code = f"{code_part1}-{code_part2}"

            plain_codes.append(plain_code)
            hashed_codes.append(backup_code_context.hash(plain_code))

        return plain_codes, hashed_codes

    def verify_backup_code(
        self, code: str, hashed_codes: list[str]
    ) -> tuple[bool, int | None]:
        """
        Verify a backup code and return the index if valid.

        Args:
            code: Plain text backup code
            hashed_codes: List of hashed backup codes

        Returns:
            Tuple of (is_valid, index_of_used_code)
        """
        if not code or not hashed_codes:
            return False, None

        # Normalize code (remove dashes, uppercase)
        normalized_code = code.replace("-", "").upper()
        # Add dash back for comparison
        if len(normalized_code) == 8:
            formatted_code = f"{normalized_code[:4]}-{normalized_code[4:]}"
        else:
            formatted_code = code.upper()

        for i, hashed in enumerate(hashed_codes):
            if hashed and backup_code_context.verify(formatted_code, hashed):
                return True, i

        return False, None

    def create_temporary_token(self, user_id: str) -> str:
        """
        Create a temporary token for 2FA verification step.

        Args:
            user_id: User's ID

        Returns:
            Temporary token string
        """
        # Create a token that includes user_id and random bytes
        random_bytes = secrets.token_bytes(32)
        token_data = f"{user_id}:{random_bytes.hex()}"

        # Hash it for the token
        token_hash = hashlib.sha256(token_data.encode()).hexdigest()

        return f"{user_id}:{token_hash[:32]}"

    def parse_temporary_token(self, token: str) -> str | None:
        """
        Parse a temporary token and extract user_id.

        Args:
            token: Temporary token string

        Returns:
            User ID or None if invalid format
        """
        if not token or ":" not in token:
            return None

        parts = token.split(":", 1)
        if len(parts) != 2:
            return None

        return parts[0]


# Create a singleton instance
two_fa_service = TwoFactorAuthService()
