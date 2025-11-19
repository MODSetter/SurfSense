"""
Tests for SOPS secrets loader functionality.

These tests verify:
- Loading secrets from encrypted files
- Fallback to plaintext files
- Environment variable injection
- Error handling
"""

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import yaml

from app.config.secrets_loader import (
    SecretsLoader,
    get_secret,
    get_secrets_loader,
    inject_secrets_to_env,
    load_secrets,
)


class TestSecretsLoader:
    """Test cases for SecretsLoader class."""

    @pytest.fixture
    def temp_dir(self):
        """Create a temporary directory for test files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def sample_secrets(self):
        """Sample secrets structure for testing."""
        return {
            'database': {
                'url': 'postgresql://test:test@localhost/test'
            },
            'app': {
                'secret_key': 'test-secret-key-12345'
            },
            'oauth': {
                'google': {
                    'client_id': 'test-client-id',
                    'client_secret': 'test-client-secret'
                }
            },
            'api_keys': {
                'openai': 'sk-test-key',
                'anthropic': 'test-anthropic-key'
            }
        }

    def test_load_plaintext_secrets(self, temp_dir, sample_secrets):
        """Test loading secrets from plaintext YAML file."""
        # Create plaintext secrets file
        secrets_file = temp_dir / "secrets.yaml"
        with open(secrets_file, 'w') as f:
            yaml.dump(sample_secrets, f)

        loader = SecretsLoader(
            plaintext_file="secrets.yaml",
            encrypted_file="secrets.enc.yaml",
            base_dir=temp_dir
        )

        secrets = loader.load()

        assert secrets == sample_secrets
        assert loader._loaded is True

    def test_get_nested_secret(self, temp_dir, sample_secrets):
        """Test retrieving nested secret values."""
        secrets_file = temp_dir / "secrets.yaml"
        with open(secrets_file, 'w') as f:
            yaml.dump(sample_secrets, f)

        loader = SecretsLoader(
            plaintext_file="secrets.yaml",
            encrypted_file="secrets.enc.yaml",
            base_dir=temp_dir
        )

        # Test nested access
        assert loader.get('database', 'url') == 'postgresql://test:test@localhost/test'
        assert loader.get('oauth', 'google', 'client_id') == 'test-client-id'
        assert loader.get('api_keys', 'openai') == 'sk-test-key'

    def test_get_flat_notation(self, temp_dir, sample_secrets):
        """Test retrieving secrets using dot notation."""
        secrets_file = temp_dir / "secrets.yaml"
        with open(secrets_file, 'w') as f:
            yaml.dump(sample_secrets, f)

        loader = SecretsLoader(
            plaintext_file="secrets.yaml",
            encrypted_file="secrets.enc.yaml",
            base_dir=temp_dir
        )

        assert loader.get_flat('database.url') == 'postgresql://test:test@localhost/test'
        assert loader.get_flat('oauth.google.client_secret') == 'test-client-secret'

    def test_get_default_value(self, temp_dir, sample_secrets):
        """Test default value when key not found."""
        secrets_file = temp_dir / "secrets.yaml"
        with open(secrets_file, 'w') as f:
            yaml.dump(sample_secrets, f)

        loader = SecretsLoader(
            plaintext_file="secrets.yaml",
            encrypted_file="secrets.enc.yaml",
            base_dir=temp_dir
        )

        assert loader.get('nonexistent', 'key', default='default-value') == 'default-value'
        assert loader.get_flat('nonexistent.key', default='fallback') == 'fallback'

    def test_inject_to_env(self, temp_dir, sample_secrets):
        """Test injecting secrets into environment variables."""
        secrets_file = temp_dir / "secrets.yaml"
        with open(secrets_file, 'w') as f:
            yaml.dump(sample_secrets, f)

        loader = SecretsLoader(
            plaintext_file="secrets.yaml",
            encrypted_file="secrets.enc.yaml",
            base_dir=temp_dir
        )

        # Clear test env vars
        test_vars = ['DATABASE_URL', 'SECRET_KEY', 'TEST_API_KEY']
        for var in test_vars:
            os.environ.pop(var, None)

        # Custom mapping for test
        mapping = {
            'DATABASE_URL': 'database.url',
            'SECRET_KEY': 'app.secret_key',
            'TEST_API_KEY': 'api_keys.openai'
        }

        loader.inject_to_env(mapping)

        assert os.environ.get('DATABASE_URL') == 'postgresql://test:test@localhost/test'
        assert os.environ.get('SECRET_KEY') == 'test-secret-key-12345'
        assert os.environ.get('TEST_API_KEY') == 'sk-test-key'

        # Cleanup
        for var in test_vars:
            os.environ.pop(var, None)

    def test_no_secrets_file(self, temp_dir):
        """Test behavior when no secrets file exists."""
        loader = SecretsLoader(
            plaintext_file="secrets.yaml",
            encrypted_file="secrets.enc.yaml",
            base_dir=temp_dir
        )

        secrets = loader.load()

        assert secrets == {}
        assert loader._loaded is True

    def test_encrypted_file_priority(self, temp_dir, sample_secrets):
        """Test that encrypted file takes priority over plaintext."""
        # Create both files with different content
        plaintext_file = temp_dir / "secrets.yaml"
        plaintext_secrets = {'database': {'url': 'plaintext-url'}}
        with open(plaintext_file, 'w') as f:
            yaml.dump(plaintext_secrets, f)

        encrypted_file = temp_dir / "secrets.enc.yaml"
        # Create a mock encrypted file (won't actually be encrypted)
        with open(encrypted_file, 'w') as f:
            f.write("mock encrypted content")

        # Mock SOPS decryption to return sample_secrets
        loader = SecretsLoader(
            plaintext_file="secrets.yaml",
            encrypted_file="secrets.enc.yaml",
            base_dir=temp_dir
        )

        with patch.object(loader, '_decrypt_sops', return_value=sample_secrets):
            secrets = loader.load()

        # Should use encrypted (mocked) content
        assert secrets['database']['url'] == 'postgresql://test:test@localhost/test'

    def test_fallback_on_decryption_error(self, temp_dir):
        """Test fallback to plaintext when decryption fails."""
        # Create both files
        plaintext_file = temp_dir / "secrets.yaml"
        plaintext_secrets = {'fallback': 'value'}
        with open(plaintext_file, 'w') as f:
            yaml.dump(plaintext_secrets, f)

        encrypted_file = temp_dir / "secrets.enc.yaml"
        with open(encrypted_file, 'w') as f:
            f.write("invalid encrypted content")

        loader = SecretsLoader(
            plaintext_file="secrets.yaml",
            encrypted_file="secrets.enc.yaml",
            base_dir=temp_dir
        )

        # Mock decryption to raise error
        with patch.object(loader, '_decrypt_sops', side_effect=RuntimeError("Decryption failed")):
            secrets = loader.load()

        # Should fall back to plaintext
        assert secrets == plaintext_secrets

    def test_cached_loading(self, temp_dir, sample_secrets):
        """Test that secrets are cached after first load."""
        secrets_file = temp_dir / "secrets.yaml"
        with open(secrets_file, 'w') as f:
            yaml.dump(sample_secrets, f)

        loader = SecretsLoader(
            plaintext_file="secrets.yaml",
            encrypted_file="secrets.enc.yaml",
            base_dir=temp_dir
        )

        # First load
        secrets1 = loader.load()

        # Modify file
        new_secrets = {'modified': 'data'}
        with open(secrets_file, 'w') as f:
            yaml.dump(new_secrets, f)

        # Second load should return cached data
        secrets2 = loader.load()

        assert secrets1 == secrets2
        assert secrets2 == sample_secrets


class TestConvenienceFunctions:
    """Test convenience functions for secrets loading."""

    @pytest.fixture
    def mock_loader(self):
        """Create a mock secrets loader."""
        mock = MagicMock(spec=SecretsLoader)
        mock.load.return_value = {'test': 'value'}
        mock.get.return_value = 'test-value'
        return mock

    def test_load_secrets_function(self, mock_loader):
        """Test load_secrets convenience function."""
        with patch('app.config.secrets_loader.get_secrets_loader', return_value=mock_loader):
            result = load_secrets()
            assert result == {'test': 'value'}
            mock_loader.load.assert_called_once()

    def test_get_secret_function(self, mock_loader):
        """Test get_secret convenience function."""
        with patch('app.config.secrets_loader.get_secrets_loader', return_value=mock_loader):
            result = get_secret('key1', 'key2', default='default')
            mock_loader.get.assert_called_once_with('key1', 'key2', default='default')


class TestSOPSDecryption:
    """Test SOPS-specific decryption functionality."""

    @pytest.fixture
    def loader_with_sops(self, temp_dir):
        """Create loader with SOPS configuration."""
        # Create encrypted file
        encrypted_file = temp_dir / "secrets.enc.yaml"
        encrypted_file.write_text("encrypted content")

        return SecretsLoader(
            plaintext_file="secrets.yaml",
            encrypted_file="secrets.enc.yaml",
            base_dir=temp_dir
        )

    def test_find_sops_in_path(self, loader_with_sops):
        """Test finding SOPS binary in PATH."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(
                returncode=0,
                stdout='/usr/local/bin/sops\n'
            )

            result = loader_with_sops._find_sops()
            assert result == '/usr/local/bin/sops'

    def test_find_sops_common_locations(self, loader_with_sops):
        """Test finding SOPS in common installation locations."""
        with patch('subprocess.run') as mock_run:
            # Simulate SOPS not in PATH
            mock_run.return_value = MagicMock(returncode=1)

            with patch('os.path.exists') as mock_exists:
                # First common path exists
                mock_exists.side_effect = lambda p: p == '/usr/local/bin/sops'

                result = loader_with_sops._find_sops()
                assert result == '/usr/local/bin/sops'

    def test_sops_not_found(self, loader_with_sops):
        """Test behavior when SOPS is not found."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = MagicMock(returncode=1)

            with patch('os.path.exists', return_value=False):
                result = loader_with_sops._find_sops()
                assert result is None


class TestEnvironmentVariableIntegration:
    """Test integration with environment variables."""

    def test_env_var_not_overwritten(self, temp_dir):
        """Test that existing env vars are not overwritten."""
        secrets_file = temp_dir / "secrets.yaml"
        yaml.dump({'database': {'url': 'from-secrets'}}, open(secrets_file, 'w'))

        # Set existing env var
        os.environ['DATABASE_URL'] = 'existing-value'

        loader = SecretsLoader(
            plaintext_file="secrets.yaml",
            encrypted_file="secrets.enc.yaml",
            base_dir=temp_dir
        )

        loader.inject_to_env({'DATABASE_URL': 'database.url'})

        # Should keep existing value
        assert os.environ['DATABASE_URL'] == 'existing-value'

        # Cleanup
        os.environ.pop('DATABASE_URL', None)

    def test_empty_env_var_overwritten(self, temp_dir):
        """Test that empty env vars are overwritten."""
        secrets_file = temp_dir / "secrets.yaml"
        yaml.dump({'database': {'url': 'from-secrets'}}, open(secrets_file, 'w'))

        # Set empty env var
        os.environ['DATABASE_URL'] = ''

        loader = SecretsLoader(
            plaintext_file="secrets.yaml",
            encrypted_file="secrets.enc.yaml",
            base_dir=temp_dir
        )

        loader.inject_to_env({'DATABASE_URL': 'database.url'})

        # Should overwrite empty value
        assert os.environ['DATABASE_URL'] == 'from-secrets'

        # Cleanup
        os.environ.pop('DATABASE_URL', None)


class TestMCPServerCLI:
    """Test the MCP server CLI functionality."""

    @pytest.fixture
    def mcp_manager(self, temp_dir, sample_secrets):
        """Create SOPS manager with test data."""
        from scripts.sops_mcp_server import SOPSManager

        # Create secrets file
        secrets_file = temp_dir / "secrets.enc.yaml"
        secrets_file.write_text("mock encrypted")

        manager = SOPSManager(base_dir=str(temp_dir))
        return manager

    def test_list_secrets_structure(self):
        """Test listing secrets returns correct structure."""
        from scripts.sops_mcp_server import SOPSManager

        manager = SOPSManager()

        # Mock decryption
        with patch.object(manager, '_find_sops', return_value='/usr/bin/sops'):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = MagicMock(
                    returncode=0,
                    stdout=yaml.dump({'test': {'key': 'value'}})
                )

                # Ensure encrypted file exists
                manager.encrypted_path.parent.mkdir(parents=True, exist_ok=True)
                manager.encrypted_path.write_text("encrypted")

                result = manager.list_secrets()

                assert 'keys' in result
                assert 'structure' in result
