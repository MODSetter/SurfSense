"""Unit tests: connector type acceptance sets include both native and Composio types.

The indexer ``ACCEPTED_*_CONNECTOR_TYPES`` sets and the shared
``COMPOSIO_GOOGLE_CONNECTOR_TYPES`` set are the constants that control
whether a connector is accepted by an indexer and which credential path
is used.  These tests verify those sets are correctly defined so that
both native and Composio connectors are handled by the unified pipeline.
"""

import pytest

from app.db import SearchSourceConnectorType

pytestmark = pytest.mark.unit


def test_drive_indexer_accepts_both_native_and_composio():
    """ACCEPTED_DRIVE_CONNECTOR_TYPES should include both native and Composio Drive types."""
    from app.tasks.connector_indexers.google_drive_indexer import (
        ACCEPTED_DRIVE_CONNECTOR_TYPES,
    )

    assert (
        SearchSourceConnectorType.GOOGLE_DRIVE_CONNECTOR
        in ACCEPTED_DRIVE_CONNECTOR_TYPES
    )
    assert (
        SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR
        in ACCEPTED_DRIVE_CONNECTOR_TYPES
    )


def test_gmail_indexer_accepts_both_native_and_composio():
    """ACCEPTED_GMAIL_CONNECTOR_TYPES should include both native and Composio Gmail types."""
    from app.tasks.connector_indexers.google_gmail_indexer import (
        ACCEPTED_GMAIL_CONNECTOR_TYPES,
    )

    assert (
        SearchSourceConnectorType.GOOGLE_GMAIL_CONNECTOR
        in ACCEPTED_GMAIL_CONNECTOR_TYPES
    )
    assert (
        SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR
        in ACCEPTED_GMAIL_CONNECTOR_TYPES
    )


def test_calendar_indexer_accepts_both_native_and_composio():
    """ACCEPTED_CALENDAR_CONNECTOR_TYPES should include both native and Composio Calendar types."""
    from app.tasks.connector_indexers.google_calendar_indexer import (
        ACCEPTED_CALENDAR_CONNECTOR_TYPES,
    )

    assert (
        SearchSourceConnectorType.GOOGLE_CALENDAR_CONNECTOR
        in ACCEPTED_CALENDAR_CONNECTOR_TYPES
    )
    assert (
        SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR
        in ACCEPTED_CALENDAR_CONNECTOR_TYPES
    )


def test_composio_connector_types_set_covers_all_google_services():
    """COMPOSIO_GOOGLE_CONNECTOR_TYPES should contain all three Composio Google types."""
    from app.utils.google_credentials import COMPOSIO_GOOGLE_CONNECTOR_TYPES

    assert (
        SearchSourceConnectorType.COMPOSIO_GOOGLE_DRIVE_CONNECTOR
        in COMPOSIO_GOOGLE_CONNECTOR_TYPES
    )
    assert (
        SearchSourceConnectorType.COMPOSIO_GMAIL_CONNECTOR
        in COMPOSIO_GOOGLE_CONNECTOR_TYPES
    )
    assert (
        SearchSourceConnectorType.COMPOSIO_GOOGLE_CALENDAR_CONNECTOR
        in COMPOSIO_GOOGLE_CONNECTOR_TYPES
    )
