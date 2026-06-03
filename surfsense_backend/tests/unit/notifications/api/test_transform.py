"""Unit tests for pure notifications API request/response helpers."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest

from app.notifications.api.transform import (
    parse_before_date,
    parse_source_type,
    to_response,
)
from app.notifications.persistence import Notification

pytestmark = pytest.mark.unit


class TestParseSourceType:
    def test_connector_prefix(self):
        """A 'connector:' filter selects the connector types and JSONB facet."""
        parsed = parse_source_type("connector:GITHUB_CONNECTOR")
        assert parsed.types == ("connector_indexing", "connector_deletion")
        assert parsed.metadata_key == "connector_type"
        assert parsed.value == "GITHUB_CONNECTOR"

    def test_doctype_prefix(self):
        """A 'doctype:' filter selects the document type and JSONB facet."""
        parsed = parse_source_type("doctype:FILE")
        assert parsed.types == ("document_processing",)
        assert parsed.metadata_key == "document_type"
        assert parsed.value == "FILE"

    def test_unknown_prefix_returns_none(self):
        """An unrecognized prefix yields no filter."""
        assert parse_source_type("mystery:thing") is None


class TestParseBeforeDate:
    def test_parses_iso_with_zulu(self):
        """An ISO date with a 'Z' suffix parses to a UTC datetime."""
        parsed = parse_before_date("2024-01-15T00:00:00Z")
        assert parsed == datetime(2024, 1, 15, tzinfo=UTC)

    def test_invalid_raises_value_error(self):
        """A malformed date raises ValueError for the endpoint to turn into a 400."""
        with pytest.raises(ValueError):
            parse_before_date("not-a-date")


def _notification(**overrides) -> Notification:
    defaults = dict(
        id=1,
        user_id=uuid.uuid4(),
        search_space_id=3,
        type="document_processing",
        title="Title",
        message="Message",
        read=False,
        notification_metadata={"k": "v"},
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
        updated_at=datetime(2024, 1, 2, tzinfo=UTC),
    )
    defaults.update(overrides)
    return Notification(**defaults)


class TestToResponse:
    def test_maps_core_fields(self):
        """A persisted notification maps its core fields onto the response shape."""
        notification = _notification()
        response = to_response(notification)
        assert response.id == 1
        assert response.user_id == str(notification.user_id)
        assert response.type == "document_processing"
        assert response.metadata == {"k": "v"}
        assert response.created_at == "2024-01-01T00:00:00+00:00"
        assert response.updated_at == "2024-01-02T00:00:00+00:00"

    def test_missing_updated_at_maps_to_none(self):
        """A missing updated_at is represented as None in the response."""
        response = to_response(_notification(updated_at=None))
        assert response.updated_at is None

    def test_missing_created_at_maps_to_empty_string(self):
        """A missing created_at is represented as an empty string in the response."""
        response = to_response(_notification(created_at=None))
        assert response.created_at == ""

    def test_null_metadata_maps_to_empty_dict(self):
        """Null metadata is normalized to an empty dict in the response."""
        response = to_response(_notification(notification_metadata=None))
        assert response.metadata == {}
