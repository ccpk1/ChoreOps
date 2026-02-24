"""Test user-profile assignment-capability helper functions.

Tests validate that data_builders.build_user_assignment_profile() correctly builds
assignment-capability data and data_builders.validate_user_assignment_profile_data()
validates form input.
"""

import pytest

from custom_components.choreops import const, data_builders as db
from custom_components.choreops.data_builders import EntityValidationError


def test_build_user_assignment_profile_with_all_values() -> None:
    """Test build_user_assignment_profile extracts all values correctly."""
    user_input = {
        const.CFOF_USERS_INPUT_NAME: "Zoë",
        const.CFOF_USERS_INPUT_HA_USER_ID: "user_123",
        const.CFOF_USERS_INPUT_MOBILE_NOTIFY_SERVICE: "mobile_app_phone",
    }

    result = db.build_user_assignment_profile(user_input)

    assert result[const.DATA_USER_NAME] == "Zoë"
    assert result[const.DATA_USER_HA_USER_ID] == "user_123"
    # Notifications enabled when mobile service is set
    assert result[const.DATA_USER_MOBILE_NOTIFY_SERVICE] == "mobile_app_phone"
    # Persistent notifications are deprecated, always False
    assert result[const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS] is False
    # UUID should be generated
    assert len(result[const.DATA_USER_INTERNAL_ID]) == 36


def test_build_user_assignment_profile_generates_uuid() -> None:
    """Test build_user_assignment_profile generates UUID when internal_id not provided."""
    user_input = {
        const.CFOF_USERS_INPUT_NAME: "Tommy",
    }

    result = db.build_user_assignment_profile(user_input)

    # Should have a generated UUID
    assert len(result[const.DATA_USER_INTERNAL_ID]) == 36
    assert result[const.DATA_USER_NAME] == "Tommy"


def test_build_user_assignment_profile_with_defaults() -> None:
    """Test build_user_assignment_profile uses defaults for optional fields."""
    user_input = {
        const.CFOF_USERS_INPUT_NAME: "Alex",
    }

    result = db.build_user_assignment_profile(user_input)

    assert result[const.DATA_USER_NAME] == "Alex"
    assert result[const.DATA_USER_HA_USER_ID] == ""
    # Notifications disabled when mobile service not set (empty string)
    assert result[const.DATA_USER_MOBILE_NOTIFY_SERVICE] == ""
    # Persistent notifications are deprecated, always False
    assert result[const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS] is False


def test_build_user_assignment_profile_strips_whitespace_from_name() -> None:
    """Test build_user_assignment_profile strips leading/trailing whitespace from name."""
    user_input = {
        const.CFOF_USERS_INPUT_NAME: "  Jordan  ",
    }

    result = db.build_user_assignment_profile(user_input)

    assert result[const.DATA_USER_NAME] == "Jordan"


def test_build_user_assignment_profile_raises_on_empty_name() -> None:
    """Test build_user_assignment_profile raises EntityValidationError for empty name."""
    user_input = {
        const.CFOF_USERS_INPUT_NAME: "",
    }

    with pytest.raises(EntityValidationError) as exc_info:
        db.build_user_assignment_profile(user_input)

    assert exc_info.value.field == const.CFOF_USERS_INPUT_NAME
    assert exc_info.value.translation_key == const.TRANS_KEY_CFOF_INVALID_ASSIGNEE_NAME


def test_validate_user_assignment_profile_data_success() -> None:
    """Test validate_user_assignment_profile_data with valid input."""
    data_input = {
        const.DATA_USER_NAME: "Emma",
    }

    errors = db.validate_user_assignment_profile_data(data_input)

    assert errors == {}


def test_validate_user_assignment_profile_data_empty_name() -> None:
    """Test validate_user_assignment_profile_data rejects empty name."""
    data_input = {
        const.DATA_USER_NAME: "",
    }

    errors = db.validate_user_assignment_profile_data(data_input)

    assert const.CFOP_ERROR_USER_NAME in errors
    assert (
        errors[const.CFOP_ERROR_USER_NAME] == const.TRANS_KEY_CFOF_INVALID_ASSIGNEE_NAME
    )


def test_validate_user_assignment_profile_data_whitespace_only_name() -> None:
    """Test validate_user_assignment_profile_data rejects whitespace-only name."""
    data_input = {
        const.DATA_USER_NAME: "   ",
    }

    errors = db.validate_user_assignment_profile_data(data_input)

    assert const.CFOP_ERROR_USER_NAME in errors
    assert (
        errors[const.CFOP_ERROR_USER_NAME] == const.TRANS_KEY_CFOF_INVALID_ASSIGNEE_NAME
    )


def test_validate_user_assignment_profile_data_missing_name() -> None:
    """Test validate_user_assignment_profile_data handles missing name key."""
    data_input = {}

    errors = db.validate_user_assignment_profile_data(data_input)

    assert const.CFOP_ERROR_USER_NAME in errors
    assert (
        errors[const.CFOP_ERROR_USER_NAME] == const.TRANS_KEY_CFOF_INVALID_ASSIGNEE_NAME
    )


def test_validate_user_assignment_profile_data_duplicate_name() -> None:
    """Test validate_user_assignment_profile_data detects duplicate names."""
    existing_assignees = {
        "assignee-1": {const.DATA_USER_NAME: "Zoë"},
        "assignee-2": {const.DATA_USER_NAME: "Tommy"},
    }

    data_input = {
        const.DATA_USER_NAME: "Zoë",  # Duplicate
    }

    errors = db.validate_user_assignment_profile_data(data_input, existing_assignees)

    assert const.CFOP_ERROR_USER_NAME in errors
    assert errors[const.CFOP_ERROR_USER_NAME] == const.TRANS_KEY_CFOF_DUPLICATE_ASSIGNEE


def test_validate_user_assignment_profile_data_allows_same_name_when_no_existing() -> (
    None
):
    """Test assignment validation allows name when no existing assignees to check."""
    data_input = {
        const.DATA_USER_NAME: "Zoë",
    }

    # No existing_assignees parameter - should pass
    errors = db.validate_user_assignment_profile_data(data_input)

    assert errors == {}


def test_validate_user_assignment_profile_data_allows_unique_name() -> None:
    """Test assignment validation allows unique name with existing assignees."""
    existing_assignees = {
        "assignee-1": {const.DATA_USER_NAME: "Zoë"},
        "assignee-2": {const.DATA_USER_NAME: "Tommy"},
    }

    data_input = {
        const.DATA_USER_NAME: "Emma",  # Unique
    }

    errors = db.validate_user_assignment_profile_data(data_input, existing_assignees)

    assert errors == {}
