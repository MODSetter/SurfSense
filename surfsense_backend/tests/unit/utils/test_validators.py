"""Unit tests for the input validators module."""

import pytest
from fastapi import HTTPException

pytestmark = pytest.mark.unit

# ===========================================================================
# IDs / Pagination Validators
# ===========================================================================


@pytest.mark.parametrize(
    "val,expected",
    [
        (5, 5),
        ("5", 5),
        ("  100  ", 100),
    ],
)
def test_validate_search_space_id_valid(val, expected):
    from app.utils.validators import validate_search_space_id

    assert validate_search_space_id(val) == expected


@pytest.mark.parametrize(
    "val,expected_detail",
    [
        (None, "search_space_id is required"),
        (True, "search_space_id must be an integer, not a boolean"),
        (False, "search_space_id must be an integer, not a boolean"),
        (0, "search_space_id must be a positive integer"),
        (-5, "search_space_id must be a positive integer"),
        ("   ", "search_space_id cannot be empty"),
        ("abc", "search_space_id must be a valid positive integer"),
        ("1.5", "search_space_id must be a valid positive integer"),
        ("05", "search_space_id must be a valid positive integer"),
        (
            [],
            "search_space_id must be an integer or string representation of an integer",
        ),
    ],
)
def test_validate_search_space_id_invalid(val, expected_detail):
    from app.utils.validators import validate_search_space_id

    with pytest.raises(HTTPException) as exc_info:
        validate_search_space_id(val)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == expected_detail


@pytest.mark.parametrize(
    "val,expected",
    [
        (None, 10),
        (5, 5),
        (100, 100),
        ("5", 5),
        ("100", 100),
        ("  25  ", 25),
    ],
)
def test_validate_top_k_valid(val, expected):
    from app.utils.validators import validate_top_k

    assert validate_top_k(val) == expected


@pytest.mark.parametrize(
    "val,expected_detail",
    [
        (True, "top_k must be an integer, not a boolean"),
        (0, "top_k must be a positive integer"),
        (-10, "top_k must be a positive integer"),
        (101, "top_k must not exceed 100"),
        ("   ", "top_k cannot be empty"),
        ("abc", "top_k must be a valid positive integer"),
        ("5.5", "top_k must be a valid positive integer"),
        ("05", "top_k must be a valid positive integer"),
        ("105", "top_k must not exceed 100"),
        ([], "top_k must be an integer or string representation of an integer"),
    ],
)
def test_validate_top_k_invalid(val, expected_detail):
    from app.utils.validators import validate_top_k

    with pytest.raises(HTTPException) as exc_info:
        validate_top_k(val)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == expected_detail


# ===========================================================================
# Format Validators
# ===========================================================================


@pytest.mark.parametrize(
    "email,expected",
    [
        ("test@example.com", "test@example.com"),
        ("  user@domain.co.uk  ", "user@domain.co.uk"),
    ],
)
def test_validate_email_valid(email, expected):
    from app.utils.validators import validate_email

    assert validate_email(email) == expected


@pytest.mark.parametrize(
    "email,expected_detail",
    [
        (None, "Email address is required"),
        ("   ", "Email address is required"),
        ("invalid-email", "Invalid email address format"),
        ("user@invalid", "Invalid email address format"),
    ],
)
def test_validate_email_invalid(email, expected_detail):
    from app.utils.validators import validate_email

    with pytest.raises(HTTPException) as exc_info:
        validate_email(email)
    assert exc_info.value.status_code == 400
    assert exc_info.value.detail == expected_detail


# ===========================================================================
# Connector Config Validators
# ===========================================================================


def test_validate_connector_config_valid():
    from app.utils.validators import validate_connector_config

    config = {"SERPER_API_KEY": "secret_key"}
    assert validate_connector_config("SERPER_API", config) == config


def test_validate_connector_config_invalid_type():
    from app.utils.validators import validate_connector_config

    with pytest.raises(ValueError, match="config must be a dictionary"):
        validate_connector_config("SERPER_API", "not-a-dict")


def test_validate_connector_config_unexpected_keys():
    from app.utils.validators import validate_connector_config

    config = {"SERPER_API_KEY": "key", "UNKNOWN_KEY": "val"}
    with pytest.raises(ValueError, match="config may only contain these keys"):
        validate_connector_config("SERPER_API", config)


def test_validate_connector_config_missing_required():
    from app.utils.validators import validate_connector_config

    config = {}
    with pytest.raises(ValueError, match="config must include these keys"):
        validate_connector_config("SERPER_API", config)
