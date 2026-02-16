"""Test parents configuration helper functions.

Tests validate that data_builders.build_parent() correctly builds parent data
and flow_helpers.validate_parents_inputs() validates form input.
"""

import pytest

from custom_components.kidschores import const, data_builders as db
from custom_components.kidschores.data_builders import EntityValidationError
from custom_components.kidschores.helpers import flow_helpers as fh


def test_build_parent_with_all_values() -> None:
    """Test build_parent extracts all values correctly."""
    user_input = {
        const.CFOF_PARENTS_INPUT_NAME: "Mom",
        const.CFOF_PARENTS_INPUT_HA_USER: "user_456",
        const.CFOF_PARENTS_INPUT_ASSOCIATED_KIDS: ["kid-1", "kid-2"],
        const.CFOF_PARENTS_INPUT_MOBILE_NOTIFY_SERVICE: "mobile_app_iphone",
    }

    result = db.build_parent(user_input)

    assert result[const.DATA_PARENT_NAME] == "Mom"
    assert result[const.DATA_PARENT_HA_USER_ID] == "user_456"
    assert result[const.DATA_PARENT_ASSOCIATED_KIDS] == ["kid-1", "kid-2"]
    # Notifications enabled when mobile service is set
    assert result[const.DATA_PARENT_MOBILE_NOTIFY_SERVICE] == "mobile_app_iphone"
    # Persistent notifications are deprecated, always False
    assert result[const.DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS] is False
    # UUID should be generated
    assert len(result[const.DATA_PARENT_INTERNAL_ID]) == 36


def test_build_parent_generates_uuid() -> None:
    """Test build_parent generates UUID when internal_id not provided."""
    user_input = {
        const.CFOF_PARENTS_INPUT_NAME: "Dad",
    }

    result = db.build_parent(user_input)

    # Should have a generated UUID
    assert len(result[const.DATA_PARENT_INTERNAL_ID]) == 36
    assert result[const.DATA_PARENT_NAME] == "Dad"


def test_build_parent_with_defaults() -> None:
    """Test build_parent uses defaults for optional fields."""
    user_input = {
        const.CFOF_PARENTS_INPUT_NAME: "Grandma",
    }

    result = db.build_parent(user_input)

    assert result[const.DATA_PARENT_NAME] == "Grandma"
    assert result[const.DATA_PARENT_HA_USER_ID] == ""
    assert result[const.DATA_PARENT_ASSOCIATED_KIDS] == []
    # Notifications disabled when mobile service not set (empty string)
    assert result[const.DATA_PARENT_MOBILE_NOTIFY_SERVICE] == ""
    # Persistent notifications are deprecated, always False
    assert result[const.DATA_PARENT_USE_PERSISTENT_NOTIFICATIONS] is False


def test_build_parent_strips_whitespace_from_name() -> None:
    """Test build_parent strips leading/trailing whitespace from name."""
    user_input = {
        const.CFOF_PARENTS_INPUT_NAME: "  Uncle Bob  ",
    }

    result = db.build_parent(user_input)

    assert result[const.DATA_PARENT_NAME] == "Uncle Bob"


def test_build_parent_with_empty_associated_kids() -> None:
    """Test build_parent handles empty associated kids list."""
    user_input = {
        const.CFOF_PARENTS_INPUT_NAME: "Aunt Sue",
        const.CFOF_PARENTS_INPUT_ASSOCIATED_KIDS: [],
    }

    result = db.build_parent(user_input)

    assert result[const.DATA_PARENT_ASSOCIATED_KIDS] == []


def test_build_parent_raises_on_empty_name() -> None:
    """Test build_parent raises EntityValidationError for empty name."""
    user_input = {
        const.CFOF_PARENTS_INPUT_NAME: "",
    }

    with pytest.raises(EntityValidationError) as exc_info:
        db.build_parent(user_input)

    assert exc_info.value.field == const.CFOF_PARENTS_INPUT_NAME
    assert exc_info.value.translation_key == const.TRANS_KEY_CFOF_INVALID_PARENT_NAME


def test_validate_parents_inputs_success() -> None:
    """Test validate_parents_inputs with valid input."""
    user_input = {
        const.CFOF_PARENTS_INPUT_NAME: "Mom",
    }

    errors = fh.validate_parents_inputs(user_input)

    assert errors == {}


def test_validate_parents_inputs_empty_name() -> None:
    """Test validate_parents_inputs rejects empty name."""
    user_input = {
        const.CFOF_PARENTS_INPUT_NAME: "",
    }

    errors = fh.validate_parents_inputs(user_input)

    assert const.CFOP_ERROR_PARENT_NAME in errors
    assert (
        errors[const.CFOP_ERROR_PARENT_NAME] == const.TRANS_KEY_CFOF_INVALID_PARENT_NAME
    )


def test_validate_parents_inputs_whitespace_only_name() -> None:
    """Test validate_parents_inputs rejects whitespace-only name."""
    user_input = {
        const.CFOF_PARENTS_INPUT_NAME: "   ",
    }

    errors = fh.validate_parents_inputs(user_input)

    assert const.CFOP_ERROR_PARENT_NAME in errors
    assert (
        errors[const.CFOP_ERROR_PARENT_NAME] == const.TRANS_KEY_CFOF_INVALID_PARENT_NAME
    )


def test_validate_parents_inputs_missing_name() -> None:
    """Test validate_parents_inputs handles missing name key."""
    user_input = {}

    errors = fh.validate_parents_inputs(user_input)

    assert const.CFOP_ERROR_PARENT_NAME in errors
    assert (
        errors[const.CFOP_ERROR_PARENT_NAME] == const.TRANS_KEY_CFOF_INVALID_PARENT_NAME
    )


def test_validate_parents_inputs_duplicate_name() -> None:
    """Test validate_parents_inputs detects duplicate names."""
    existing_parents = {
        "parent-1": {const.DATA_PARENT_NAME: "Mom"},
        "parent-2": {const.DATA_PARENT_NAME: "Dad"},
    }

    user_input = {
        const.CFOF_PARENTS_INPUT_NAME: "Mom",  # Duplicate
    }

    errors = fh.validate_parents_inputs(user_input, existing_parents)

    assert const.CFOP_ERROR_PARENT_NAME in errors
    assert errors[const.CFOP_ERROR_PARENT_NAME] == const.TRANS_KEY_CFOF_DUPLICATE_PARENT


def test_validate_parents_inputs_allows_same_name_when_no_existing() -> None:
    """Test validate_parents_inputs allows name when no existing parents to check."""
    user_input = {
        const.CFOF_PARENTS_INPUT_NAME: "Mom",
    }

    # No existing_parents parameter - should pass
    errors = fh.validate_parents_inputs(user_input)

    assert errors == {}


def test_validate_parents_inputs_allows_unique_name() -> None:
    """Test validate_parents_inputs allows unique name when checking existing parents."""
    existing_parents = {
        "parent-1": {const.DATA_PARENT_NAME: "Mom"},
        "parent-2": {const.DATA_PARENT_NAME: "Dad"},
    }

    user_input = {
        const.CFOF_PARENTS_INPUT_NAME: "Grandpa",  # Unique
    }

    errors = fh.validate_parents_inputs(user_input, existing_parents)

    assert errors == {}
