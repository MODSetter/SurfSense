#!/usr/bin/env python3
"""
SOPS MCP Server for SurfSense

This MCP (Model Context Protocol) server provides Claude Code with secure
tools to manage SOPS-encrypted secrets. It allows listing, viewing, updating,
and rotating secrets without exposing them in plaintext to the conversation.

Usage:
    python scripts/sops_mcp_server.py

Configure in Claude Code settings to use this as an MCP server.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

import yaml

# Default paths
DEFAULT_SECRETS_FILE = "secrets.enc.yaml"
DEFAULT_PLAINTEXT_FILE = "secrets.yaml"
DEFAULT_SOPS_CONFIG = ".sops.yaml"


class SOPSManager:
    """Manages SOPS-encrypted secrets for SurfSense."""

    def __init__(self, base_dir: str | None = None):
        if base_dir:
            self.base_dir = Path(base_dir)
        else:
            # Try to find the SurfSense backend directory
            script_dir = Path(__file__).resolve().parent
            self.base_dir = script_dir.parent  # surfsense_backend

        self.encrypted_path = self.base_dir / DEFAULT_SECRETS_FILE
        self.sops_config = self.base_dir / DEFAULT_SOPS_CONFIG

    def _find_sops(self) -> str:
        """Find SOPS binary."""
        result = subprocess.run(
            ['which', 'sops'],
            capture_output=True,
            text=True
        )
        if result.returncode == 0:
            return result.stdout.strip()

        common_paths = [
            '/usr/local/bin/sops',
            '/usr/bin/sops',
            '/opt/homebrew/bin/sops',
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path

        raise RuntimeError("SOPS binary not found")

    def _get_age_key_file(self) -> str:
        """Get the age key file path."""
        return os.environ.get(
            'SOPS_AGE_KEY_FILE',
            os.path.expanduser('~/.config/sops/age/keys.txt')
        )

    def list_secrets(self) -> dict[str, Any]:
        """
        List all secret keys (not values) in the encrypted file.

        Returns a hierarchical structure of secret keys.
        """
        if not self.encrypted_path.exists():
            return {"error": f"Encrypted file not found: {self.encrypted_path}"}

        try:
            sops = self._find_sops()
            env = os.environ.copy()
            env['SOPS_AGE_KEY_FILE'] = self._get_age_key_file()

            result = subprocess.run(
                [sops, '--decrypt', str(self.encrypted_path)],
                capture_output=True,
                text=True,
                env=env
            )

            if result.returncode != 0:
                return {"error": f"Decryption failed: {result.stderr}"}

            secrets = yaml.safe_load(result.stdout) or {}

            # Extract keys only (not values)
            def extract_keys(obj, prefix=""):
                keys = []
                if isinstance(obj, dict):
                    for key, value in obj.items():
                        full_key = f"{prefix}.{key}" if prefix else key
                        if isinstance(value, dict):
                            keys.extend(extract_keys(value, full_key))
                        else:
                            keys.append(full_key)
                return keys

            return {
                "keys": extract_keys(secrets),
                "structure": self._get_structure(secrets)
            }

        except Exception as e:
            return {"error": str(e)}

    def _get_structure(self, obj: dict, depth: int = 0) -> dict:
        """Get the structure of secrets without values."""
        result = {}
        for key, value in obj.items():
            if isinstance(value, dict):
                result[key] = self._get_structure(value, depth + 1)
            else:
                result[key] = f"<{type(value).__name__}>"
        return result

    def get_secret(self, key_path: str) -> dict[str, Any]:
        """
        Get a specific secret value.

        Args:
            key_path: Dot-notation path to secret (e.g., 'database.url')
        """
        if not self.encrypted_path.exists():
            return {"error": f"Encrypted file not found: {self.encrypted_path}"}

        try:
            sops = self._find_sops()
            env = os.environ.copy()
            env['SOPS_AGE_KEY_FILE'] = self._get_age_key_file()

            result = subprocess.run(
                [sops, '--decrypt', str(self.encrypted_path)],
                capture_output=True,
                text=True,
                env=env
            )

            if result.returncode != 0:
                return {"error": f"Decryption failed: {result.stderr}"}

            secrets = yaml.safe_load(result.stdout) or {}

            # Navigate to the key
            keys = key_path.split('.')
            value = secrets
            for key in keys:
                if isinstance(value, dict) and key in value:
                    value = value[key]
                else:
                    return {"error": f"Key not found: {key_path}"}

            return {"key": key_path, "value": value}

        except Exception as e:
            return {"error": str(e)}

    def set_secret(self, key_path: str, value: str) -> dict[str, Any]:
        """
        Set or update a secret value.

        Args:
            key_path: Dot-notation path to secret (e.g., 'api_keys.openai')
            value: The new value for the secret
        """
        if not self.encrypted_path.exists():
            return {"error": f"Encrypted file not found: {self.encrypted_path}"}

        try:
            sops = self._find_sops()
            env = os.environ.copy()
            env['SOPS_AGE_KEY_FILE'] = self._get_age_key_file()

            # Decrypt current secrets
            result = subprocess.run(
                [sops, '--decrypt', str(self.encrypted_path)],
                capture_output=True,
                text=True,
                env=env
            )

            if result.returncode != 0:
                return {"error": f"Decryption failed: {result.stderr}"}

            secrets = yaml.safe_load(result.stdout) or {}

            # Navigate and set the value
            keys = key_path.split('.')
            current = secrets
            for key in keys[:-1]:
                if key not in current:
                    current[key] = {}
                current = current[key]

            old_value = current.get(keys[-1], "<not set>")
            current[keys[-1]] = value

            # Write to temp file and encrypt
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.yaml', delete=False
            ) as f:
                yaml.dump(secrets, f, default_flow_style=False)
                temp_path = f.name

            try:
                # Encrypt the updated file
                result = subprocess.run(
                    [sops, '--encrypt', temp_path],
                    capture_output=True,
                    text=True,
                    env=env
                )

                if result.returncode != 0:
                    return {"error": f"Encryption failed: {result.stderr}"}

                # Write encrypted content back
                with open(self.encrypted_path, 'w') as f:
                    f.write(result.stdout)

                return {
                    "success": True,
                    "key": key_path,
                    "message": f"Secret updated successfully",
                    "old_value_masked": "***" if old_value != "<not set>" else old_value
                }

            finally:
                os.unlink(temp_path)

        except Exception as e:
            return {"error": str(e)}

    def delete_secret(self, key_path: str) -> dict[str, Any]:
        """
        Delete a secret from the encrypted file.

        Args:
            key_path: Dot-notation path to secret to delete
        """
        if not self.encrypted_path.exists():
            return {"error": f"Encrypted file not found: {self.encrypted_path}"}

        try:
            sops = self._find_sops()
            env = os.environ.copy()
            env['SOPS_AGE_KEY_FILE'] = self._get_age_key_file()

            # Decrypt current secrets
            result = subprocess.run(
                [sops, '--decrypt', str(self.encrypted_path)],
                capture_output=True,
                text=True,
                env=env
            )

            if result.returncode != 0:
                return {"error": f"Decryption failed: {result.stderr}"}

            secrets = yaml.safe_load(result.stdout) or {}

            # Navigate and delete
            keys = key_path.split('.')
            current = secrets
            for key in keys[:-1]:
                if key not in current:
                    return {"error": f"Key not found: {key_path}"}
                current = current[key]

            if keys[-1] not in current:
                return {"error": f"Key not found: {key_path}"}

            del current[keys[-1]]

            # Write to temp file and encrypt
            with tempfile.NamedTemporaryFile(
                mode='w', suffix='.yaml', delete=False
            ) as f:
                yaml.dump(secrets, f, default_flow_style=False)
                temp_path = f.name

            try:
                result = subprocess.run(
                    [sops, '--encrypt', temp_path],
                    capture_output=True,
                    text=True,
                    env=env
                )

                if result.returncode != 0:
                    return {"error": f"Encryption failed: {result.stderr}"}

                with open(self.encrypted_path, 'w') as f:
                    f.write(result.stdout)

                return {
                    "success": True,
                    "key": key_path,
                    "message": "Secret deleted successfully"
                }

            finally:
                os.unlink(temp_path)

        except Exception as e:
            return {"error": str(e)}

    def rotate_key(self) -> dict[str, Any]:
        """
        Rotate the encryption by re-encrypting all secrets.

        This is useful after updating the age public key in .sops.yaml
        """
        if not self.encrypted_path.exists():
            return {"error": f"Encrypted file not found: {self.encrypted_path}"}

        try:
            sops = self._find_sops()
            env = os.environ.copy()
            env['SOPS_AGE_KEY_FILE'] = self._get_age_key_file()

            result = subprocess.run(
                [sops, 'updatekeys', str(self.encrypted_path)],
                capture_output=True,
                text=True,
                env=env,
                input='y\n'  # Confirm key rotation
            )

            if result.returncode != 0:
                return {"error": f"Key rotation failed: {result.stderr}"}

            return {
                "success": True,
                "message": "Encryption keys rotated successfully"
            }

        except Exception as e:
            return {"error": str(e)}

    def export_env(self) -> dict[str, Any]:
        """
        Export secrets as environment variable format.

        Returns the secrets formatted as KEY=value pairs for .env files.
        """
        if not self.encrypted_path.exists():
            return {"error": f"Encrypted file not found: {self.encrypted_path}"}

        try:
            sops = self._find_sops()
            env = os.environ.copy()
            env['SOPS_AGE_KEY_FILE'] = self._get_age_key_file()

            result = subprocess.run(
                [sops, '--decrypt', str(self.encrypted_path)],
                capture_output=True,
                text=True,
                env=env
            )

            if result.returncode != 0:
                return {"error": f"Decryption failed: {result.stderr}"}

            secrets = yaml.safe_load(result.stdout) or {}

            # Convert to flat env format
            env_vars = {}

            # Database
            if 'database' in secrets:
                env_vars['DATABASE_URL'] = secrets['database'].get('url', '')

            # App
            if 'app' in secrets:
                env_vars['SECRET_KEY'] = secrets['app'].get('secret_key', '')

            # OAuth
            if 'oauth' in secrets:
                google = secrets['oauth'].get('google', {})
                env_vars['GOOGLE_OAUTH_CLIENT_ID'] = google.get('client_id', '')
                env_vars['GOOGLE_OAUTH_CLIENT_SECRET'] = google.get('client_secret', '')

                airtable = secrets['oauth'].get('airtable', {})
                env_vars['AIRTABLE_CLIENT_ID'] = airtable.get('client_id', '')
                env_vars['AIRTABLE_CLIENT_SECRET'] = airtable.get('client_secret', '')

            # API Keys
            if 'api_keys' in secrets:
                api_keys = secrets['api_keys']
                env_vars['FIRECRAWL_API_KEY'] = api_keys.get('firecrawl', '')
                env_vars['UNSTRUCTURED_API_KEY'] = api_keys.get('unstructured', '')
                env_vars['LLAMA_CLOUD_API_KEY'] = api_keys.get('llama_cloud', '')
                env_vars['LANGSMITH_API_KEY'] = api_keys.get('langsmith', '')

            # Services
            if 'services' in secrets:
                celery = secrets['services'].get('celery', {})
                env_vars['CELERY_BROKER_URL'] = celery.get('broker_url', '')
                env_vars['CELERY_RESULT_BACKEND'] = celery.get('result_backend', '')

            return {"env_vars": env_vars}

        except Exception as e:
            return {"error": str(e)}


def handle_mcp_request(request: dict) -> dict:
    """Handle an MCP request and return the response."""
    manager = SOPSManager()

    method = request.get('method', '')
    params = request.get('params', {})

    if method == 'tools/list':
        return {
            "tools": [
                {
                    "name": "sops_list_secrets",
                    "description": "List all secret keys (not values) in the encrypted file",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "sops_get_secret",
                    "description": "Get a specific secret value by key path",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "key_path": {
                                "type": "string",
                                "description": "Dot-notation path to secret (e.g., 'database.url')"
                            }
                        },
                        "required": ["key_path"]
                    }
                },
                {
                    "name": "sops_set_secret",
                    "description": "Set or update a secret value",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "key_path": {
                                "type": "string",
                                "description": "Dot-notation path to secret"
                            },
                            "value": {
                                "type": "string",
                                "description": "New value for the secret"
                            }
                        },
                        "required": ["key_path", "value"]
                    }
                },
                {
                    "name": "sops_delete_secret",
                    "description": "Delete a secret from the encrypted file",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "key_path": {
                                "type": "string",
                                "description": "Dot-notation path to secret to delete"
                            }
                        },
                        "required": ["key_path"]
                    }
                },
                {
                    "name": "sops_rotate_keys",
                    "description": "Rotate encryption keys by re-encrypting all secrets",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                },
                {
                    "name": "sops_export_env",
                    "description": "Export secrets as environment variables format",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                        "required": []
                    }
                }
            ]
        }

    elif method == 'tools/call':
        tool_name = params.get('name', '')
        arguments = params.get('arguments', {})

        if tool_name == 'sops_list_secrets':
            result = manager.list_secrets()
        elif tool_name == 'sops_get_secret':
            result = manager.get_secret(arguments.get('key_path', ''))
        elif tool_name == 'sops_set_secret':
            result = manager.set_secret(
                arguments.get('key_path', ''),
                arguments.get('value', '')
            )
        elif tool_name == 'sops_delete_secret':
            result = manager.delete_secret(arguments.get('key_path', ''))
        elif tool_name == 'sops_rotate_keys':
            result = manager.rotate_key()
        elif tool_name == 'sops_export_env':
            result = manager.export_env()
        else:
            result = {"error": f"Unknown tool: {tool_name}"}

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(result, indent=2)
                }
            ]
        }

    return {"error": f"Unknown method: {method}"}


def main():
    """Main MCP server loop using stdio transport."""
    # Read from stdin, write to stdout
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = handle_mcp_request(request)
            print(json.dumps(response), flush=True)
        except json.JSONDecodeError:
            print(json.dumps({"error": "Invalid JSON"}), flush=True)
        except Exception as e:
            print(json.dumps({"error": str(e)}), flush=True)


def redact_value(value: str, show_chars: int = 4) -> str:
    """Redact a secret value, showing only first few characters."""
    if not value or len(value) <= show_chars:
        return "[REDACTED]"
    return value[:show_chars] + "..." + "[REDACTED]"


def redact_dict_values(obj: dict) -> dict:
    """Recursively redact all string values in a dictionary."""
    result = {}
    for key, value in obj.items():
        if isinstance(value, dict):
            result[key] = redact_dict_values(value)
        elif isinstance(value, str):
            result[key] = redact_value(value)
        else:
            result[key] = value
    return result


if __name__ == '__main__':
    # If running directly (not as MCP server), provide CLI interface
    if len(sys.argv) > 1:
        manager = SOPSManager()
        command = sys.argv[1]

        # Check for --show-values flag for commands that output secrets
        show_values = '--show-values' in sys.argv

        if command == 'list':
            result = manager.list_secrets()
            # List only shows keys, not values - safe to print
            print(json.dumps(result, indent=2))
        elif command == 'get' and len(sys.argv) > 2:
            key_path = sys.argv[2] if sys.argv[2] != '--show-values' else sys.argv[3] if len(sys.argv) > 3 else ''
            result = manager.get_secret(key_path)
            if not show_values and 'value' in result:
                # Redact the value in CLI output
                result['value'] = redact_value(str(result['value']))
                result['note'] = "Use --show-values flag to see actual value"
            print(json.dumps(result, indent=2))
        elif command == 'set' and len(sys.argv) > 3:
            # Filter out flags from arguments
            args = [a for a in sys.argv[2:] if not a.startswith('--')]
            if len(args) >= 2:
                result = manager.set_secret(args[0], args[1])
                print(json.dumps(result, indent=2))
            else:
                print("Usage: sops_mcp_server.py set <key_path> <value>")
                sys.exit(1)
        elif command == 'delete' and len(sys.argv) > 2:
            key_path = sys.argv[2] if sys.argv[2] != '--show-values' else sys.argv[3] if len(sys.argv) > 3 else ''
            print(json.dumps(manager.delete_secret(key_path), indent=2))
        elif command == 'rotate':
            print(json.dumps(manager.rotate_key(), indent=2))
        elif command == 'export':
            result = manager.export_env()
            if not show_values and 'env_vars' in result:
                # Redact all values in export output
                result['env_vars'] = redact_dict_values(result['env_vars'])
                result['note'] = "Use --show-values flag to see actual values"
            print(json.dumps(result, indent=2))
        else:
            print("Usage: sops_mcp_server.py [list|get|set|delete|rotate|export] [args...] [--show-values]")
            print("\nCommands:")
            print("  list              - List all secret keys (not values)")
            print("  get <key_path>    - Get a secret value (redacted by default)")
            print("  set <key> <value> - Set or update a secret")
            print("  delete <key_path> - Delete a secret")
            print("  rotate            - Rotate encryption keys")
            print("  export            - Export as env vars (redacted by default)")
            print("\nFlags:")
            print("  --show-values     - Show actual secret values (use with caution)")
            sys.exit(1)
    else:
        main()
