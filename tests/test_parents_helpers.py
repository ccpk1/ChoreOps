"""Test user-profile configuration helper functions.

Tests validate that data_builders.build_user_profile() correctly builds user-profile data
and flow_helpers.validate_users_inputs() validates form input.
"""

import pytest

from custom_components.choreops import const, data_builders as db
from custom_components.choreops.data_builders import EntityValidationError
from custom_components.choreops.helpers import flow_helpers as fh


def test_build_user_profile_with_all_values() -> None:
    """Test build_user_profile extracts all values correctly."""
    user_input = {
        const.CFOF_USERS_INPUT_NAME: "Mom",
        const.CFOF_USERS_INPUT_HA_USER_ID: "user_456",
        const.CFOF_USERS_INPUT_ASSOCIATED_USER_IDS: ["assignee-1", "assignee-2"],
        const.CFOF_USERS_INPUT_MOBILE_NOTIFY_SERVICE: "mobile_app_iphone",
    }

    result = db.build_user_profile(user_input)

    assert result[const.DATA_USER_NAME] == "Mom"
    assert result[const.DATA_USER_HA_USER_ID] == "user_456"
    assert result[const.DATA_APPROVER_ASSOCIATED_USERS] == ["assignee-1", "assignee-2"]
    # Notifications enabled when mobile service is set
    assert result[const.DATA_USER_MOBILE_NOTIFY_SERVICE] == "mobile_app_iphone"
    # Persistent notifications are deprecated, always False
    assert result[const.DATA_APPROVER_USE_PERSISTENT_NOTIFICATIONS] is False
    # UUID should be generated
    assert len(result[const.DATA_USER_INTERNAL_ID]) == 36


def test_build_user_profile_generates_uuid() -> None:
    """Test build_user_profile generates UUID when internal_id not provided."""
    user_input = {
        const.CFOF_USERS_INPUT_NAME: "Dad",
    }

    result = db.build_user_profile(user_input)

    # Should have a generated UUID
    assert len(result[const.DATA_USER_INTERNAL_ID]) == 36
    assert result[const.DATA_USER_NAME] == "Dad"


def test_build_user_profile_with_defaults() -> None:
    """Test build_user_profile uses defaults for optional fields."""
    user_input = {
        const.CFOF_USERS_INPUT_NAME: "Grandma",
    }

    result = db.build_user_profile(user_input)

    assert result[const.DATA_USER_NAME] == "Grandma"
    assert result[const.DATA_USER_HA_USER_ID] == ""
    assert result[const.DATA_APPROVER_ASSOCIATED_USERS] == []
    # Notifications disabled when mobile service not set (empty string)
    assert result[const.DATA_USER_MOBILE_NOTIFY_SERVICE] == ""
    # Persistent notifications are deprecated, always False
    assert result[const.DATA_APPROVER_USE_PERSISTENT_NOTIFICATIONS] is False


def test_build_user_profile_strips_whitespace_from_name() -> None:
    """Test build_user_profile strips leading/trailing whitespace from name."""
    user_input = {
        const.CFOF_USERS_INPUT_NAME: "  Uncle Bob  ",
    }

    result = db.build_user_profile(user_input)

    assert result[const.DATA_USER_NAME] == "Uncle Bob"


def test_build_user_profile_with_empty_associated_assignees() -> None:
    """Test build_user_profile handles empty associated assignees list."""
    user_input = {
        const.CFOF_USERS_INPUT_NAME: "Aunt Sue",
        const.CFOF_USERS_INPUT_ASSOCIATED_USER_IDS: [],
    }

    result = db.build_user_profile(user_input)

    assert result[const.DATA_APPROVER_ASSOCIATED_USERS] == []


def test_build_user_profile_raises_on_empty_name() -> None:
    """Test build_user_profile raises EntityValidationError for empty name."""
    user_input = {
        const.CFOF_USERS_INPUT_NAME: "",
    }

    with pytest.raises(EntityValidationError) as exc_info:
        db.build_user_profile(user_input)

    assert exc_info.value.field == const.CFOF_USERS_INPUT_NAME
    assert exc_info.value.translation_key == const.TRANS_KEY_CFOF_INVALID_APPROVER_NAME


def test_validate_users_inputs_success() -> None:
    """Test validate_users_inputs with valid input."""
    user_input = {
        const.CFOF_USERS_INPUT_NAME: "Mom",
    }

    errors = fh.validate_users_inputs(user_input)

    assert errors == {}


def test_validate_users_inputs_empty_name() -> None:
    """Test validate_users_inputs rejects empty name."""
    user_input = {
        const.CFOF_USERS_INPUT_NAME: "",
    }

    errors = fh.validate_users_inputs(user_input)

    assert const.CFOP_ERROR_USER_NAME in errors
    assert (
        errors[const.CFOP_ERROR_USER_NAME] == const.TRANS_KEY_CFOF_INVALID_APPROVER_NAME
    )


def test_validate_users_inputs_whitespace_only_name() -> None:
    """Test validate_users_inputs rejects whitespace-only name."""
    user_input = {
        const.CFOF_USERS_INPUT_NAME: "   ",
    }

    errors = fh.validate_users_inputs(user_input)

    assert const.CFOP_ERROR_USER_NAME in errors
    assert (
        errors[const.CFOP_ERROR_USER_NAME] == const.TRANS_KEY_CFOF_INVALID_APPROVER_NAME
    )


def test_validate_users_inputs_missing_name() -> None:
    """Test validate_users_inputs handles missing name key."""
    user_input = {}

    errors = fh.validate_users_inputs(user_input)

    assert const.CFOP_ERROR_USER_NAME in errors
    assert (
        errors[const.CFOP_ERROR_USER_NAME] == const.TRANS_KEY_CFOF_INVALID_APPROVER_NAME
    )


def test_validate_users_inputs_duplicate_name() -> None:
    """Test validate_users_inputs detects duplicate names."""
    existing_approvers = {
        "approver-1": {const.DATA_USER_NAME: "Mom"},
        "approver-2": {const.DATA_USER_NAME: "Dad"},
    }

    user_input = {
        const.CFOF_USERS_INPUT_NAME: "Mom",  # Duplicate
    }

    errors = fh.validate_users_inputs(user_input, existing_approvers)

    assert const.CFOP_ERROR_USER_NAME in errors
    assert errors[const.CFOP_ERROR_USER_NAME] == const.TRANS_KEY_CFOF_DUPLICATE_APPROVER


def test_validate_users_inputs_allows_same_name_when_no_existing() -> None:
    """Test validate_users_inputs allows name when no existing approvers to check."""
    user_input = {
        const.CFOF_USERS_INPUT_NAME: "Mom",
    }

    # No existing_approvers parameter - should pass
    errors = fh.validate_users_inputs(user_input)

    assert errors == {}


def test_validate_users_inputs_allows_unique_name() -> None:
    """Test validate_users_inputs allows unique name when checking existing approvers."""
    existing_approvers = {
        "approver-1": {const.DATA_USER_NAME: "Mom"},
        "approver-2": {const.DATA_USER_NAME: "Dad"},
    }

    user_input = {
        const.CFOF_USERS_INPUT_NAME: "Grandpa",  # Unique
    }

    errors = fh.validate_users_inputs(user_input, existing_approvers)

    assert errors == {}


def test_validate_users_inputs_update_ignores_self_in_assignee_conflict() -> None:
    """Editing user should not self-conflict with assignable view of same record."""
    current_user_id = "user-1"
    user_input = {
        const.CFOF_USERS_INPUT_NAME: "Mom",
        const.CFOF_USERS_INPUT_CAN_BE_ASSIGNED: True,
        const.CFOF_USERS_INPUT_ENABLE_CHORE_WORKFLOW: False,
        const.CFOF_USERS_INPUT_ENABLE_GAMIFICATION: False,
        const.CFOF_USERS_INPUT_CAN_APPROVE: False,
        const.CFOF_USERS_INPUT_ASSOCIATED_USER_IDS: [],
    }
    existing_users = {
        current_user_id: {
            const.DATA_USER_NAME: "Mom",
        }
    }
    existing_assignees = {
        "shadow-view-id": {
            const.DATA_USER_INTERNAL_ID: current_user_id,
            const.DATA_USER_NAME: "Mom",
        }
    }

    errors = fh.validate_users_inputs(
        user_input,
        existing_users,
        existing_assignees,
        current_user_id=current_user_id,
    )

    assert errors == {}
