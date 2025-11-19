"""
SOPS Secrets Loader for SurfSense

This module provides functionality to decrypt and load secrets from SOPS-encrypted
YAML files at runtime. It supports both encrypted and plaintext fallback modes
for development environments.
"""

import os
import subprocess
import yaml
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Base directory for the backend
BASE_DIR = Path(__file__).resolve().parent.parent.parent


class SecretsLoader:
    """
    Loads and decrypts secrets from SOPS-encrypted YAML files.

    The loader supports:
    - Decrypting secrets using SOPS CLI with age encryption
    - Falling back to plaintext secrets.yaml for development
    - Loading from environment variables as ultimate fallback
    """

    def __init__(
        self,
        encrypted_file: str = "secrets.enc.yaml",
        plaintext_file: str = "secrets.yaml",
        base_dir: Optional[Path] = None
    ):
        self.base_dir = base_dir or BASE_DIR
        self.encrypted_path = self.base_dir / encrypted_file
        self.plaintext_path = self.base_dir / plaintext_file
        self._secrets: dict = {}
        self._loaded = False

    def load(self) -> dict:
        """
        Load secrets from the appropriate source.

        Priority:
        1. Decrypt secrets.enc.yaml using SOPS
        2. Fall back to plaintext secrets.yaml (development only)
        3. Return empty dict (rely on environment variables)
        """
        if self._loaded:
            return self._secrets

        # Try to load encrypted secrets first
        if self.encrypted_path.exists():
            try:
                self._secrets = self._decrypt_sops()
                self._loaded = True
                logger.info(f"Loaded encrypted secrets from {self.encrypted_path}")
                return self._secrets
            except Exception as e:
                logger.warning(f"Failed to decrypt secrets: {e}")

        # Fall back to plaintext for development
        if self.plaintext_path.exists():
            logger.warning(
                f"Using plaintext secrets from {self.plaintext_path}. "
                "This should only be used in development!"
            )
            try:
                with open(self.plaintext_path, 'r') as f:
                    self._secrets = yaml.safe_load(f) or {}
                self._loaded = True
                return self._secrets
            except Exception as e:
                logger.error(f"Failed to load plaintext secrets: {e}")

        # No secrets file found - will rely on environment variables
        logger.info("No secrets file found. Using environment variables only.")
        self._loaded = True
        return self._secrets

    def _decrypt_sops(self) -> dict:
        """
        Decrypt secrets using SOPS CLI.

        Requires:
        - sops binary in PATH
        - Age private key in ~/.config/sops/age/keys.txt or SOPS_AGE_KEY_FILE env var
        """
        # Check for SOPS binary
        sops_path = self._find_sops()
        if not sops_path:
            raise RuntimeError(
                "SOPS binary not found. Install it from https://github.com/getsops/sops"
            )

        # Set age key file location if not set
        age_key_file = os.environ.get(
            'SOPS_AGE_KEY_FILE',
            os.path.expanduser('~/.config/sops/age/keys.txt')
        )

        if not os.path.exists(age_key_file):
            raise RuntimeError(
                f"Age key file not found at {age_key_file}. "
                "Set SOPS_AGE_KEY_FILE environment variable or place key at default location."
            )

        env = os.environ.copy()
        env['SOPS_AGE_KEY_FILE'] = age_key_file

        # Decrypt using SOPS
        result = subprocess.run(
            [sops_path, '--decrypt', str(self.encrypted_path)],
            capture_output=True,
            text=True,
            env=env
        )

        if result.returncode != 0:
            raise RuntimeError(f"SOPS decryption failed: {result.stderr}")

        return yaml.safe_load(result.stdout) or {}

    def _find_sops(self) -> Optional[str]:
        """Find the SOPS binary in PATH or common locations."""
        # Check PATH
        result = subprocess.run(
            ['which', 'sops'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()

        # Check common locations
        common_paths = [
            '/usr/local/bin/sops',
            '/usr/bin/sops',
            '/opt/homebrew/bin/sops',
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path

        return None

    def get(self, *keys: str, default: Any = None) -> Any:
        """
        Get a nested secret value using dot notation keys.

        Example:
            loader.get('database', 'url')  # Gets secrets['database']['url']
            loader.get('oauth', 'google', 'client_id')
        """
        if not self._loaded:
            self.load()

        value = self._secrets
        for key in keys:
            if isinstance(value, dict):
                value = value.get(key)
            else:
                return default
            if value is None:
                return default
        return value

    def get_flat(self, key: str, default: Any = None) -> Any:
        """
        Get a secret using dot notation string.

        Example:
            loader.get_flat('database.url')
        """
        keys = key.split('.')
        return self.get(*keys, default=default)

    def inject_to_env(self, mapping: Optional[dict] = None) -> None:
        """
        Inject secrets into environment variables.

        Args:
            mapping: Dict mapping env var names to secret paths.
                    Example: {'DATABASE_URL': 'database.url'}
        """
        if not self._loaded:
            self.load()

        if mapping is None:
            # Default mapping for SurfSense
            mapping = {
                'DATABASE_URL': 'database.url',
                'SECRET_KEY': 'app.secret_key',
                'GOOGLE_OAUTH_CLIENT_ID': 'oauth.google.client_id',
                'GOOGLE_OAUTH_CLIENT_SECRET': 'oauth.google.client_secret',
                'AIRTABLE_CLIENT_ID': 'oauth.airtable.client_id',
                'AIRTABLE_CLIENT_SECRET': 'oauth.airtable.client_secret',
                'FIRECRAWL_API_KEY': 'api_keys.firecrawl',
                'UNSTRUCTURED_API_KEY': 'api_keys.unstructured',
                'LLAMA_CLOUD_API_KEY': 'api_keys.llama_cloud',
                'LANGSMITH_API_KEY': 'api_keys.langsmith',
                'CELERY_BROKER_URL': 'services.celery.broker_url',
                'CELERY_RESULT_BACKEND': 'services.celery.result_backend',
                'TTS_SERVICE_API_KEY': 'services.tts_api_key',
                'STT_SERVICE_API_KEY': 'services.stt_api_key',
            }

        for env_var, secret_path in mapping.items():
            value = self.get_flat(secret_path)
            if value is not None and value != "":
                # Only override if not already set in environment
                if env_var not in os.environ or os.environ[env_var] == "":
                    os.environ[env_var] = str(value)
                    logger.debug(f"Injected secret into {env_var}")


# Global instance for easy access
_secrets_loader: Optional[SecretsLoader] = None


def get_secrets_loader() -> SecretsLoader:
    """Get or create the global secrets loader instance."""
    global _secrets_loader
    if _secrets_loader is None:
        _secrets_loader = SecretsLoader()
    return _secrets_loader


def load_secrets() -> dict:
    """Convenience function to load secrets."""
    return get_secrets_loader().load()


def get_secret(*keys: str, default: Any = None) -> Any:
    """Convenience function to get a secret value."""
    return get_secrets_loader().get(*keys, default=default)


def inject_secrets_to_env(mapping: Optional[dict] = None) -> None:
    """Convenience function to inject secrets into environment."""
    get_secrets_loader().inject_to_env(mapping)
