"""Test points configuration helper functions.

Tests validate that config flow and options flow use the same centralized
helper functions for points configuration, ensuring consistency.
"""

from custom_components.choreops import const
from custom_components.choreops.helpers import flow_helpers as fh


def test_build_points_schema_default_values() -> None:
    """Test build_points_schema with default values."""
    schema = fh.build_points_schema()

    # Verify schema has required fields
    assert const.CONF_POINTS_LABEL in schema.schema
    assert const.CONF_POINTS_ICON in schema.schema


def test_build_points_schema_custom_defaults() -> None:
    """Test build_points_schema with custom default values."""
    custom_label = "Stars"
    custom_icon = "mdi:star"

    schema = fh.build_points_schema(
        default_label=custom_label, default_icon=custom_icon
    )

    # Verify schema accepts custom defaults
    assert const.CONF_POINTS_LABEL in schema.schema
    assert const.CONF_POINTS_ICON in schema.schema


def test_build_points_data_with_values() -> None:
    """Test build_points_data extracts values correctly."""
    user_input = {
        const.CONF_POINTS_LABEL: "Gold Coins",
        const.CONF_POINTS_ICON: "mdi:coin",
    }

    result = fh.build_points_data(user_input)

    assert result[const.CONF_POINTS_LABEL] == "Gold Coins"
    assert result[const.CONF_POINTS_ICON] == "mdi:coin"


def test_build_points_data_with_defaults() -> None:
    """Test build_points_data falls back to defaults when keys missing."""
    user_input = {}

    result = fh.build_points_data(user_input)

    assert result[const.CONF_POINTS_LABEL] == const.DEFAULT_POINTS_LABEL
    assert result[const.CONF_POINTS_ICON] == const.DEFAULT_POINTS_ICON


def test_validate_points_inputs_success() -> None:
    """Test validate_points_inputs with valid input."""
    user_input = {
        const.CONF_POINTS_LABEL: "Stars",
        const.CONF_POINTS_ICON: "mdi:star",
    }

    errors = fh.validate_points_inputs(user_input)

    assert errors == {}


def test_validate_points_inputs_empty_label() -> None:
    """Test validate_points_inputs rejects empty label."""
    user_input = {
        const.CONF_POINTS_LABEL: "",
        const.CONF_POINTS_ICON: "mdi:star",
    }

    errors = fh.validate_points_inputs(user_input)

    assert "base" in errors
    assert errors["base"] == "points_label_required"


def test_validate_points_inputs_whitespace_only_label() -> None:
    """Test validate_points_inputs rejects whitespace-only label."""
    user_input = {
        const.CONF_POINTS_LABEL: "   ",
        const.CONF_POINTS_ICON: "mdi:star",
    }

    errors = fh.validate_points_inputs(user_input)

    assert "base" in errors
    assert errors["base"] == "points_label_required"


def test_validate_points_inputs_missing_label() -> None:
    """Test validate_points_inputs handles missing label key."""
    user_input = {
        const.CONF_POINTS_ICON: "mdi:star",
    }

    errors = fh.validate_points_inputs(user_input)

    assert "base" in errors
    assert errors["base"] == "points_label_required"
