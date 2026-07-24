"""Behavior tests for the ``matches`` filter grammar."""

from __future__ import annotations

import pytest

from app.automations.triggers.builtin.event.filter import FilterError, matches

pytestmark = pytest.mark.unit


def test_empty_filter_matches_any_payload() -> None:
    assert matches({}, {"document_id": 42, "document_type": "FILE"}) is True
    assert matches({}, {}) is True


def test_scalar_value_is_implicit_equality() -> None:
    flt = {"document_type": "FILE"}
    assert matches(flt, {"document_type": "FILE"}) is True
    assert matches(flt, {"document_type": "WEBPAGE"}) is False


def test_multiple_fields_are_anded() -> None:
    flt = {"document_type": "FILE", "workspace_id": 7}
    assert matches(flt, {"document_type": "FILE", "workspace_id": 7}) is True
    assert matches(flt, {"document_type": "FILE", "workspace_id": 9}) is False


def test_gt_operator_compares_greater_than() -> None:
    flt = {"page_count": {"$gt": 10}}
    assert matches(flt, {"page_count": 20}) is True
    assert matches(flt, {"page_count": 10}) is False
    assert matches(flt, {"page_count": 5}) is False


def test_remaining_comparison_operators() -> None:
    assert matches({"n": {"$gte": 10}}, {"n": 10}) is True
    assert matches({"n": {"$gte": 10}}, {"n": 9}) is False

    assert matches({"n": {"$lt": 10}}, {"n": 9}) is True
    assert matches({"n": {"$lt": 10}}, {"n": 10}) is False

    assert matches({"n": {"$lte": 10}}, {"n": 10}) is True
    assert matches({"n": {"$lte": 10}}, {"n": 11}) is False

    assert matches({"s": {"$eq": "FILE"}}, {"s": "FILE"}) is True
    assert matches({"s": {"$eq": "FILE"}}, {"s": "WEB"}) is False

    assert matches({"s": {"$ne": "FILE"}}, {"s": "WEB"}) is True
    assert matches({"s": {"$ne": "FILE"}}, {"s": "FILE"}) is False


def test_multiple_operators_on_one_field_are_anded() -> None:
    flt = {"n": {"$gte": 10, "$lt": 20}}
    assert matches(flt, {"n": 15}) is True
    assert matches(flt, {"n": 10}) is True
    assert matches(flt, {"n": 20}) is False
    assert matches(flt, {"n": 5}) is False


def test_in_and_nin_membership_operators() -> None:
    flt_in = {"document_type": {"$in": ["FILE", "WEBPAGE"]}}
    assert matches(flt_in, {"document_type": "FILE"}) is True
    assert matches(flt_in, {"document_type": "SLACK"}) is False

    flt_nin = {"document_type": {"$nin": ["FILE", "WEBPAGE"]}}
    assert matches(flt_nin, {"document_type": "SLACK"}) is True
    assert matches(flt_nin, {"document_type": "FILE"}) is False


def test_or_matches_when_any_branch_holds() -> None:
    flt = {"$or": [{"document_type": "FILE"}, {"document_type": "WEBPAGE"}]}
    assert matches(flt, {"document_type": "WEBPAGE"}) is True
    assert matches(flt, {"document_type": "SLACK"}) is False


def test_and_matches_when_every_branch_holds() -> None:
    flt = {"$and": [{"n": {"$gt": 5}}, {"n": {"$lt": 10}}]}
    assert matches(flt, {"n": 7}) is True
    assert matches(flt, {"n": 12}) is False


def test_not_inverts_its_subexpression() -> None:
    flt = {"$not": {"document_type": "FILE"}}
    assert matches(flt, {"document_type": "WEBPAGE"}) is True
    assert matches(flt, {"document_type": "FILE"}) is False


def test_missing_field_never_matches_and_never_raises() -> None:
    # Conservative: an absent field fails the constraint, and comparisons must
    # not raise on the missing value — including $ne (absence isn't "not equal").
    assert matches({"document_type": "FILE"}, {}) is False
    assert matches({"page_count": {"$gt": 5}}, {}) is False
    assert matches({"document_type": {"$in": ["FILE"]}}, {}) is False
    assert matches({"document_type": {"$ne": "FILE"}}, {}) is False


def test_logical_operators_compose_with_fields() -> None:
    flt = {
        "workspace_id": 7,
        "$or": [{"document_type": "FILE"}, {"document_type": "WEBPAGE"}],
    }
    assert matches(flt, {"workspace_id": 7, "document_type": "FILE"}) is True
    assert matches(flt, {"workspace_id": 9, "document_type": "FILE"}) is False
    assert matches(flt, {"workspace_id": 7, "document_type": "SLACK"}) is False


def test_unknown_field_operator_raises_filter_error() -> None:
    with pytest.raises(FilterError):
        matches({"n": {"$regex": "x"}}, {"n": "xyz"})


def test_unknown_logical_operator_raises_filter_error() -> None:
    with pytest.raises(FilterError):
        matches({"$nor": [{"document_type": "FILE"}]}, {"document_type": "FILE"})
