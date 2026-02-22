"""Test assignees configuration helper functions.

Tests validate that data_builders.build_assignee() correctly builds assignee data
and flow_helpers.validate_assignee_inputs() validates form input.
"""

import pytest

from custom_components.choreops import const, data_builders as db
from custom_components.choreops.data_builders import EntityValidationError
from custom_components.choreops.helpers import flow_helpers as fh


def test_build_assignee_with_all_values() -> None:
    """Test build_assignee extracts all values correctly."""
    user_input = {
        const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME: "Zoë",
        const.CFOF_ASSIGNEES_INPUT_HA_USER: "user_123",
        const.CFOF_ASSIGNEES_INPUT_MOBILE_NOTIFY_SERVICE: "mobile_app_phone",
    }

    result = db.build_assignee(user_input)

    assert result[const.DATA_ASSIGNEE_NAME] == "Zoë"
    assert result[const.DATA_ASSIGNEE_HA_USER_ID] == "user_123"
    # Notifications enabled when mobile service is set
    assert result[const.DATA_ASSIGNEE_MOBILE_NOTIFY_SERVICE] == "mobile_app_phone"
    # Persistent notifications are deprecated, always False
    assert result[const.DATA_ASSIGNEE_USE_PERSISTENT_NOTIFICATIONS] is False
    # UUID should be generated
    assert len(result[const.DATA_ASSIGNEE_INTERNAL_ID]) == 36


def test_build_assignee_generates_uuid() -> None:
    """Test build_assignee generates UUID when internal_id not provided."""
    user_input = {
        const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME: "Tommy",
    }

    result = db.build_assignee(user_input)

    # Should have a generated UUID
    assert len(result[const.DATA_ASSIGNEE_INTERNAL_ID]) == 36
    assert result[const.DATA_ASSIGNEE_NAME] == "Tommy"


def test_build_assignee_with_defaults() -> None:
    """Test build_assignee uses defaults for optional fields."""
    user_input = {
        const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME: "Alex",
    }

    result = db.build_assignee(user_input)

    assert result[const.DATA_ASSIGNEE_NAME] == "Alex"
    assert result[const.DATA_ASSIGNEE_HA_USER_ID] == ""
    # Notifications disabled when mobile service not set (empty string)
    assert result[const.DATA_ASSIGNEE_MOBILE_NOTIFY_SERVICE] == ""
    # Persistent notifications are deprecated, always False
    assert result[const.DATA_ASSIGNEE_USE_PERSISTENT_NOTIFICATIONS] is False


def test_build_assignee_strips_whitespace_from_name() -> None:
    """Test build_assignee strips leading/trailing whitespace from name."""
    user_input = {
        const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME: "  Jordan  ",
    }

    result = db.build_assignee(user_input)

    assert result[const.DATA_ASSIGNEE_NAME] == "Jordan"


def test_build_assignee_raises_on_empty_name() -> None:
    """Test build_assignee raises EntityValidationError for empty name."""
    user_input = {
        const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME: "",
    }

    with pytest.raises(EntityValidationError) as exc_info:
        db.build_assignee(user_input)

    assert exc_info.value.field == const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME
    assert exc_info.value.translation_key == const.TRANS_KEY_CFOF_INVALID_ASSIGNEE_NAME


def test_validate_assignee_inputs_success() -> None:
    """Test validate_assignee_inputs with valid input."""
    user_input = {
        const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME: "Emma",
    }

    errors = fh.validate_assignee_inputs(user_input)

    assert errors == {}


def test_validate_assignee_inputs_empty_name() -> None:
    """Test validate_assignee_inputs rejects empty name."""
    user_input = {
        const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME: "",
    }

    errors = fh.validate_assignee_inputs(user_input)

    assert const.CFOP_ERROR_ASSIGNEE_NAME in errors
    assert (
        errors[const.CFOP_ERROR_ASSIGNEE_NAME]
        == const.TRANS_KEY_CFOF_INVALID_ASSIGNEE_NAME
    )


def test_validate_assignee_inputs_whitespace_only_name() -> None:
    """Test validate_assignee_inputs rejects whitespace-only name."""
    user_input = {
        const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME: "   ",
    }

    errors = fh.validate_assignee_inputs(user_input)

    assert const.CFOP_ERROR_ASSIGNEE_NAME in errors
    assert (
        errors[const.CFOP_ERROR_ASSIGNEE_NAME]
        == const.TRANS_KEY_CFOF_INVALID_ASSIGNEE_NAME
    )


def test_validate_assignee_inputs_missing_name() -> None:
    """Test validate_assignee_inputs handles missing name key."""
    user_input = {}

    errors = fh.validate_assignee_inputs(user_input)

    assert const.CFOP_ERROR_ASSIGNEE_NAME in errors
    assert (
        errors[const.CFOP_ERROR_ASSIGNEE_NAME]
        == const.TRANS_KEY_CFOF_INVALID_ASSIGNEE_NAME
    )


def test_validate_assignee_inputs_duplicate_name() -> None:
    """Test validate_assignee_inputs detects duplicate names."""
    existing_assignees = {
        "assignee-1": {const.DATA_ASSIGNEE_NAME: "Zoë"},
        "assignee-2": {const.DATA_ASSIGNEE_NAME: "Tommy"},
    }

    user_input = {
        const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME: "Zoë",  # Duplicate
    }

    errors = fh.validate_assignee_inputs(user_input, existing_assignees)

    assert const.CFOP_ERROR_ASSIGNEE_NAME in errors
    assert (
        errors[const.CFOP_ERROR_ASSIGNEE_NAME]
        == const.TRANS_KEY_CFOF_DUPLICATE_ASSIGNEE
    )


def test_validate_assignee_inputs_allows_same_name_when_no_existing() -> None:
    """Test validate_assignee_inputs allows name when no existing assignees to check."""
    user_input = {
        const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME: "Zoë",
    }

    # No existing_assignees parameter - should pass
    errors = fh.validate_assignee_inputs(user_input)

    assert errors == {}


def test_validate_assignee_inputs_allows_unique_name() -> None:
    """Test validate_assignee_inputs allows unique name when checking existing assignees."""
    existing_assignees = {
        "assignee-1": {const.DATA_ASSIGNEE_NAME: "Zoë"},
        "assignee-2": {const.DATA_ASSIGNEE_NAME: "Tommy"},
    }

    user_input = {
        const.CFOF_ASSIGNEES_INPUT_ASSIGNEE_NAME: "Emma",  # Unique
    }

    errors = fh.validate_assignee_inputs(user_input, existing_assignees)

    assert errors == {}
