"""
Encryption Service for Sensitive Data
Provides Fernet symmetric encryption for API keys and other sensitive data
"""
import base64
import os
from typing import Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


class EncryptionService:
    """
    Service for encrypting and decrypting sensitive data using Fernet symmetric encryption.

    Fernet provides authenticated encryption (AES-128 in CBC mode with HMAC for integrity).
    This ensures both confidentiality and integrity of encrypted data.
    """

    _instance: Optional['EncryptionService'] = None
    _fernet: Optional[Fernet] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize the encryption service with a Fernet key"""
        if self._fernet is None:
            self._initialize_fernet()

    def _initialize_fernet(self):
        """Initialize Fernet cipher from environment or generate new key"""
        # Get encryption key from environment variable
        encryption_key = os.getenv('ENCRYPTION_KEY')

        if not encryption_key:
            # For initial setup, we'll use a key derived from SECRET_KEY
            # In production, ENCRYPTION_KEY should be set separately
            secret_key = os.getenv('SECRET_KEY', 'default-secret-key-change-me')

            # Derive a Fernet key from SECRET_KEY using PBKDF2
            kdf = PBKDF2HMAC(
                algorithm=hashes.SHA256(),
                length=32,
                salt=b'surfsense-encryption-salt',  # Fixed salt for consistency
                iterations=100000,
            )
            key = base64.urlsafe_b64encode(kdf.derive(secret_key.encode()))
        else:
            key = encryption_key.encode()

        self._fernet = Fernet(key)

    def encrypt(self, plaintext: str) -> str:
        """
        Encrypt a plaintext string

        Args:
            plaintext: The string to encrypt

        Returns:
            Base64-encoded encrypted string
        """
        if not plaintext:
            return plaintext

        encrypted_bytes = self._fernet.encrypt(plaintext.encode())
        return encrypted_bytes.decode()

    def decrypt(self, ciphertext: str) -> str:
        """
        Decrypt an encrypted string

        Args:
            ciphertext: The base64-encoded encrypted string

        Returns:
            Decrypted plaintext string
        """
        if not ciphertext:
            return ciphertext

        try:
            decrypted_bytes = self._fernet.decrypt(ciphertext.encode())
            return decrypted_bytes.decode()
        except Exception as e:
            # If decryption fails, it might be plaintext (for migration purposes)
            # In production, this should raise an error
            return ciphertext

    def is_encrypted(self, value: str) -> bool:
        """
        Check if a value is encrypted

        Args:
            value: The string to check

        Returns:
            True if encrypted, False if plaintext
        """
        if not value:
            return False

        try:
            # Fernet tokens start with 'gAAAAA' after base64 encoding
            # Try to decrypt - if it works, it's encrypted
            self._fernet.decrypt(value.encode())
            return True
        except Exception:
            return False


# Singleton instance
encryption_service = EncryptionService()


def generate_encryption_key() -> str:
    """
    Generate a new Fernet encryption key

    Returns:
        Base64-encoded Fernet key
    """
    return Fernet.generate_key().decode()


if __name__ == '__main__':
    # Generate a new encryption key for production use
    print('Generated Encryption Key:')
    print(generate_encryption_key())
    print('\nAdd this to your secrets file as ENCRYPTION_KEY')
