"""Root conftest — shared fixtures available to all test modules."""

from __future__ import annotations

import os

_DEFAULT_TEST_DB = (
    "postgresql+asyncpg://postgres:postgres@localhost:5432/surfsense_test"
)
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", _DEFAULT_TEST_DB)

# Force the app to use the test database regardless of any pre-existing
# DATABASE_URL in the environment (e.g. from .env or shell profile).
os.environ["DATABASE_URL"] = TEST_DATABASE_URL

# Integration tests authenticate over HTTP via email/password, so the
# password-auth routers must be mounted (they are skipped under AUTH_TYPE=GOOGLE).
# setdefault (not load_dotenv, which runs later with override=False) lets a
# developer's .env=GOOGLE be overridden here while still honouring an explicitly
# exported shell AUTH_TYPE.
os.environ.setdefault("AUTH_TYPE", "LOCAL")
os.environ.setdefault("REGISTRATION_ENABLED", "TRUE")

import pytest  # noqa: E402

from app.db import DocumentType  # noqa: E402
from app.indexing_pipeline.connector_document import ConnectorDocument  # noqa: E402

# ---------------------------------------------------------------------------
# Unit test fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def sample_user_id() -> str:
    return "00000000-0000-0000-0000-000000000001"


@pytest.fixture
def sample_workspace_id() -> int:
    return 1


@pytest.fixture
def sample_connector_id() -> int:
    return 42


@pytest.fixture
def make_connector_document():
    """
    Generic factory for unit tests. Overridden in tests/integration/conftest.py
    with real DB-backed IDs for integration tests.
    """

    def _make(**overrides):
        defaults = {
            "title": "Test Document",
            "source_markdown": "## Heading\n\nSome content.",
            "unique_id": "test-id-001",
            "document_type": DocumentType.CLICKUP_CONNECTOR,
            "workspace_id": 1,
            "connector_id": 1,
            "created_by_id": "00000000-0000-0000-0000-000000000001",
        }
        defaults.update(overrides)
        return ConnectorDocument(**defaults)

    return _make
