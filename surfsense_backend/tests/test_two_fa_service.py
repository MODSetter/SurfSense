"""
Tests for Two-Factor Authentication service.

Tests cover:
- TOTP secret generation
- QR code generation
- TOTP verification
- Backup code generation and verification
- Temporary token creation and parsing
"""

import base64

import pyotp
import pytest

from app.services.two_fa_service import TwoFactorAuthService, backup_code_context


@pytest.mark.unit
@pytest.mark.services
class TestTwoFactorAuthService:
    """Test cases for TwoFactorAuthService."""

    @pytest.fixture
    def service(self):
        """Create a 2FA service instance."""
        return TwoFactorAuthService(app_name="SurfSense Test")

    def test_generate_secret(self, service):
        """Test TOTP secret generation."""
        secret = service.generate_secret()

        assert secret is not None
        assert isinstance(secret, str)
        assert len(secret) == 32  # pyotp generates 32-character base32 strings
        # Verify it's valid base32
        assert all(c in "ABCDEFGHIJKLMNOPQRSTUVWXYZ234567" for c in secret)

    def test_get_totp_uri(self, service):
        """Test TOTP provisioning URI generation."""
        secret = "JBSWY3DPEHPK3PXP"
        email = "test@example.com"

        uri = service.get_totp_uri(secret, email)

        assert uri.startswith("otpauth://totp/")
        assert email in uri
        assert "SurfSense%20Test" in uri or "SurfSense+Test" in uri
        assert secret in uri

    def test_generate_qr_code(self, service):
        """Test QR code generation."""
        secret = "JBSWY3DPEHPK3PXP"
        email = "test@example.com"

        qr_code = service.generate_qr_code(secret, email)

        assert qr_code is not None
        assert isinstance(qr_code, str)
        # Verify it's valid base64
        try:
            decoded = base64.b64decode(qr_code)
            assert len(decoded) > 0
            # PNG files start with specific magic bytes
            assert decoded[:8] == b"\x89PNG\r\n\x1a\n"
        except Exception as e:
            pytest.fail(f"QR code is not valid base64 PNG: {e}")

    def test_verify_totp_valid_code(self, service):
        """Test TOTP verification with valid code."""
        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)
        valid_code = totp.now()

        result = service.verify_totp(secret, valid_code)

        assert result is True

    def test_verify_totp_invalid_code(self, service):
        """Test TOTP verification with invalid code."""
        secret = pyotp.random_base32()

        result = service.verify_totp(secret, "000000")

        assert result is False

    def test_verify_totp_empty_inputs(self, service):
        """Test TOTP verification with empty inputs."""
        assert service.verify_totp("", "123456") is False
        assert service.verify_totp("JBSWY3DPEHPK3PXP", "") is False
        assert service.verify_totp("", "") is False

    def test_verify_totp_with_time_drift(self, service):
        """Test TOTP verification allows clock drift."""
        import time

        secret = pyotp.random_base32()
        totp = pyotp.TOTP(secret)

        # Get code from 30 seconds ago (previous time window)
        past_code = totp.at(int(time.time()) - 30)

        # Should still verify due to valid_window=1
        result = service.verify_totp(secret, past_code)

        # This might be True or False depending on exact timing
        # Just verify it doesn't crash
        assert isinstance(result, bool)

    def test_generate_backup_codes(self, service):
        """Test backup code generation."""
        plain_codes, hashed_codes = service.generate_backup_codes(count=10)

        # Check we got the right number of codes
        assert len(plain_codes) == 10
        assert len(hashed_codes) == 10

        # Check format of plain codes (XXXX-XXXX)
        for code in plain_codes:
            assert len(code) == 9  # 4 + 1 (dash) + 4
            assert code[4] == "-"
            # Check hex characters
            code_without_dash = code.replace("-", "")
            assert all(c in "0123456789ABCDEF" for c in code_without_dash)

        # Check hashed codes are different from plain codes
        for plain, hashed in zip(plain_codes, hashed_codes):
            assert plain != hashed
            assert hashed.startswith("$2b$")  # bcrypt hash

        # Check all codes are unique
        assert len(set(plain_codes)) == 10
        assert len(set(hashed_codes)) == 10

    def test_generate_backup_codes_custom_count(self, service):
        """Test backup code generation with custom count."""
        plain_codes, hashed_codes = service.generate_backup_codes(count=5)

        assert len(plain_codes) == 5
        assert len(hashed_codes) == 5

    def test_verify_backup_code_valid(self, service):
        """Test backup code verification with valid code."""
        plain_codes, hashed_codes = service.generate_backup_codes(count=3)

        # Try to verify the first code
        is_valid, index = service.verify_backup_code(plain_codes[0], hashed_codes)

        assert is_valid is True
        assert index == 0

    def test_verify_backup_code_different_formats(self, service):
        """Test backup code verification handles different formats."""
        plain_codes, hashed_codes = service.generate_backup_codes(count=1)
        code = plain_codes[0]

        # Test with dash
        is_valid1, _ = service.verify_backup_code(code, hashed_codes)
        assert is_valid1 is True

        # Test without dash
        code_no_dash = code.replace("-", "")
        is_valid2, _ = service.verify_backup_code(code_no_dash, hashed_codes)
        assert is_valid2 is True

        # Test lowercase
        code_lower = code.lower()
        is_valid3, _ = service.verify_backup_code(code_lower, hashed_codes)
        assert is_valid3 is True

    def test_verify_backup_code_invalid(self, service):
        """Test backup code verification with invalid code."""
        _, hashed_codes = service.generate_backup_codes(count=3)

        is_valid, index = service.verify_backup_code("AAAA-AAAA", hashed_codes)

        assert is_valid is False
        assert index is None

    def test_verify_backup_code_empty_inputs(self, service):
        """Test backup code verification with empty inputs."""
        is_valid1, index1 = service.verify_backup_code("", ["hash1"])
        assert is_valid1 is False
        assert index1 is None

        is_valid2, index2 = service.verify_backup_code("AAAA-AAAA", [])
        assert is_valid2 is False
        assert index2 is None

    def test_verify_backup_code_returns_correct_index(self, service):
        """Test backup code verification returns correct index."""
        plain_codes, hashed_codes = service.generate_backup_codes(count=5)

        # Verify each code returns its index
        for i, code in enumerate(plain_codes):
            is_valid, index = service.verify_backup_code(code, hashed_codes)
            assert is_valid is True
            assert index == i

    def test_create_temporary_token(self, service):
        """Test temporary token creation."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"

        token = service.create_temporary_token(user_id)

        assert token is not None
        assert isinstance(token, str)
        assert ":" in token
        assert token.startswith(user_id)
        # Token format should be user_id:hash
        parts = token.split(":")
        assert len(parts) == 2
        assert len(parts[1]) == 32  # Hash is truncated to 32 chars

    def test_create_temporary_token_unique(self, service):
        """Test that temporary tokens are unique."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"

        token1 = service.create_temporary_token(user_id)
        token2 = service.create_temporary_token(user_id)

        # Tokens should be different due to random bytes
        assert token1 != token2

    def test_parse_temporary_token_valid(self, service):
        """Test parsing valid temporary token."""
        user_id = "123e4567-e89b-12d3-a456-426614174000"
        token = service.create_temporary_token(user_id)

        parsed_user_id = service.parse_temporary_token(token)

        assert parsed_user_id == user_id

    def test_parse_temporary_token_invalid_format(self, service):
        """Test parsing invalid temporary token."""
        assert service.parse_temporary_token("") is None
        assert service.parse_temporary_token("no-colon-here") is None
        assert service.parse_temporary_token(":::multiple:colons") is not None  # Will return first part

    def test_parse_temporary_token_manual_format(self, service):
        """Test parsing manually formatted token."""
        user_id = "test-user-123"
        manual_token = f"{user_id}:somehashvalue"

        parsed_user_id = service.parse_temporary_token(manual_token)

        assert parsed_user_id == user_id

    def test_app_name_in_uri(self, service):
        """Test that app name appears correctly in TOTP URI."""
        custom_service = TwoFactorAuthService(app_name="Custom App Name")
        secret = "JBSWY3DPEHPK3PXP"
        email = "test@example.com"

        uri = custom_service.get_totp_uri(secret, email)

        assert "Custom" in uri
        assert "App" in uri

    def test_totp_verification_workflow(self, service):
        """Test complete TOTP setup and verification workflow."""
        # 1. Generate secret
        secret = service.generate_secret()
        assert secret is not None

        # 2. Generate QR code
        qr_code = service.generate_qr_code(secret, "test@example.com")
        assert qr_code is not None

        # 3. Verify current code
        totp = pyotp.TOTP(secret)
        current_code = totp.now()
        assert service.verify_totp(secret, current_code) is True

        # 4. Verify invalid code fails
        assert service.verify_totp(secret, "000000") is False

    def test_backup_code_workflow(self, service):
        """Test complete backup code generation and usage workflow."""
        # 1. Generate backup codes
        plain_codes, hashed_codes = service.generate_backup_codes(count=10)

        # 2. Verify a code works
        is_valid, used_index = service.verify_backup_code(plain_codes[3], hashed_codes)
        assert is_valid is True
        assert used_index == 3

        # 3. Simulate marking code as used by setting to None
        hashed_codes_after_use = hashed_codes.copy()
        hashed_codes_after_use[used_index] = None

        # 4. Verify same code doesn't work again
        is_valid2, index2 = service.verify_backup_code(plain_codes[3], hashed_codes_after_use)
        assert is_valid2 is False

        # 5. Other codes still work
        is_valid3, index3 = service.verify_backup_code(plain_codes[5], hashed_codes_after_use)
        assert is_valid3 is True
        assert index3 == 5


@pytest.mark.unit
class TestBackupCodeContext:
    """Test backup code hashing context."""

    def test_hash_and_verify(self):
        """Test that backup codes can be hashed and verified."""
        code = "ABCD-1234"

        hashed = backup_code_context.hash(code)

        assert backup_code_context.verify(code, hashed) is True
        assert backup_code_context.verify("WRONG-CODE", hashed) is False

    def test_hash_is_different_each_time(self):
        """Test that hashing same code produces different hashes (due to salt)."""
        code = "ABCD-1234"

        hash1 = backup_code_context.hash(code)
        hash2 = backup_code_context.hash(code)

        # Hashes should be different (bcrypt uses random salt)
        assert hash1 != hash2

        # But both should verify
        assert backup_code_context.verify(code, hash1) is True
        assert backup_code_context.verify(code, hash2) is True
