"""Test points configuration helper functions.

Tests validate that config flow and options flow use the same centralized
helper functions for points configuration, ensuring consistency.
"""

import datetime

import pytest
import voluptuous as vol

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


def test_build_points_schema_accepts_decimal_default_chore_points() -> None:
    """Test build_points_schema accepts decimal default chore points."""
    schema = fh.build_points_schema()

    result = schema(
        {
            const.CFOF_SYSTEM_INPUT_POINTS_LABEL: "Stars",
            const.CFOF_SYSTEM_INPUT_POINTS_ICON: "mdi:star",
            const.CFOF_SYSTEM_INPUT_DEFAULT_CHORE_POINTS: 2.5,
        }
    )

    assert result[const.CFOF_SYSTEM_INPUT_DEFAULT_CHORE_POINTS] == 2.5


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
        const.CFOF_SYSTEM_INPUT_DEFAULT_CHORE_POINTS: 2.5,
    }

    errors = fh.validate_points_inputs(user_input)

    assert errors == {}


def test_validate_points_inputs_rejects_more_than_two_decimals() -> None:
    """Test validate_points_inputs rejects precision beyond 2 decimals."""
    user_input = {
        const.CONF_POINTS_LABEL: "Stars",
        const.CONF_POINTS_ICON: "mdi:star",
        const.CFOF_SYSTEM_INPUT_DEFAULT_CHORE_POINTS: 2.555,
    }

    errors = fh.validate_points_inputs(user_input)

    assert errors[const.CFOP_ERROR_DEFAULT_CHORE_POINTS] == (
        const.TRANS_KEY_CFOF_INVALID_DEFAULT_CHORE_POINTS
    )


def test_build_points_schema_rejects_zero_default_chore_points() -> None:
    """Test build_points_schema rejects zero default chore points."""
    schema = fh.build_points_schema()

    with pytest.raises(vol.Invalid):
        schema(
            {
                const.CFOF_SYSTEM_INPUT_POINTS_LABEL: "Stars",
                const.CFOF_SYSTEM_INPUT_POINTS_ICON: "mdi:star",
                const.CFOF_SYSTEM_INPUT_DEFAULT_CHORE_POINTS: 0,
            }
        )


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


def test_build_chore_schema_accepts_decimal_chore_points() -> None:
    """Test chore schema accepts 2-decimal point values."""
    schema = fh.build_chore_schema({"Alex": "user-1"})

    result = schema(
        {
            fh.CHORE_SECTION_ROOT_FORM: {
                const.CFOF_CHORES_INPUT_NAME: "Decimal chore",
                const.CFOF_CHORES_INPUT_DEFAULT_POINTS: 10.25,
                const.CFOF_CHORES_INPUT_ASSIGNED_USER_IDS: ["Alex"],
                const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            }
        }
    )

    root_form = result[fh.CHORE_SECTION_ROOT_FORM]
    assert root_form[const.CFOF_CHORES_INPUT_DEFAULT_POINTS] == 10.25


def test_build_chore_schema_defaults_custom_fields_when_existing_values_are_none() -> (
    None
):
    """Test chore schema uses renderable defaults for null custom settings."""
    schema = fh.build_chore_schema(
        {"Alex": "user-1"},
        {
            const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY: const.FREQUENCY_CUSTOM,
            const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL: None,
            const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL_UNIT: None,
        },
    )

    result = schema(
        {
            fh.CHORE_SECTION_ROOT_FORM: {
                const.CFOF_CHORES_INPUT_NAME: "Custom chore",
                const.CFOF_CHORES_INPUT_DEFAULT_POINTS: 5,
                const.CFOF_CHORES_INPUT_ASSIGNED_USER_IDS: ["Alex"],
                const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            },
            fh.CHORE_SECTION_SCHEDULE: {},
        }
    )

    schedule = result[fh.CHORE_SECTION_SCHEDULE]
    assert schedule[const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL] == 1
    assert (
        schedule[const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL_UNIT] == const.TIME_UNIT_DAYS
    )


def test_build_chore_schema_coerces_custom_interval_to_int() -> None:
    """Test chore schema coerces custom interval selector values to int."""
    schema = fh.build_chore_schema(
        {"Alex": "user-1"},
        {
            const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY: const.FREQUENCY_CUSTOM,
        },
    )

    result = schema(
        {
            fh.CHORE_SECTION_ROOT_FORM: {
                const.CFOF_CHORES_INPUT_NAME: "Custom chore",
                const.CFOF_CHORES_INPUT_DEFAULT_POINTS: 5,
                const.CFOF_CHORES_INPUT_ASSIGNED_USER_IDS: ["Alex"],
                const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            },
            fh.CHORE_SECTION_SCHEDULE: {
                const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY: const.FREQUENCY_CUSTOM,
                const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL: 2.0,
                const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL_UNIT: const.TIME_UNIT_DAYS,
            },
        }
    )

    schedule = result[fh.CHORE_SECTION_SCHEDULE]
    assert schedule[const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL] == 2
    assert isinstance(schedule[const.CFOF_CHORES_INPUT_CUSTOM_INTERVAL], int)


def test_validate_chores_inputs_rejects_more_than_two_decimals() -> None:
    """Test chore validation rejects precision beyond 2 decimals."""
    errors, _due_date = fh.validate_chores_inputs(
        {
            const.CFOF_CHORES_INPUT_NAME: "Decimal chore",
            const.CFOF_CHORES_INPUT_DEFAULT_POINTS: 10.555,
            const.CFOF_CHORES_INPUT_ASSIGNED_USER_IDS: ["Alex"],
            const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        },
        {"Alex": "user-1"},
    )

    assert errors[const.CFOP_ERROR_CHORE_POINTS] == const.TRANS_KEY_CFOF_INVALID_POINTS


def test_validate_badge_common_inputs_accepts_decimal_awards() -> None:
    """Test badge validation accepts decimal award points and multiplier."""
    user_input = {
        const.CFOF_BADGES_INPUT_NAME: "Decimal badge",
        const.CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: ["user-1"],
        const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 100,
        const.CFOF_BADGES_INPUT_MAINTENANCE_RULES: 0,
        const.CFOF_BADGES_INPUT_RESET_SCHEDULE_GRACE_PERIOD_DAYS: 0,
        const.CFOF_BADGES_INPUT_AWARD_ITEMS: [
            const.AWARD_ITEMS_KEY_POINTS,
            const.AWARD_ITEMS_KEY_POINTS_MULTIPLIER,
        ],
        const.CFOF_BADGES_INPUT_AWARD_POINTS: 25.25,
        const.CFOF_BADGES_INPUT_POINTS_MULTIPLIER: 1.25,
    }

    errors = fh.validate_badge_common_inputs(user_input, None)

    assert errors == {}
    assert user_input[const.CFOF_BADGES_INPUT_AWARD_POINTS] == 25.25
    assert user_input[const.CFOF_BADGES_INPUT_POINTS_MULTIPLIER] == 1.25


def test_validate_badge_common_inputs_rejects_more_than_two_decimals() -> None:
    """Test badge validation rejects award precision beyond 2 decimals."""
    user_input = {
        const.CFOF_BADGES_INPUT_NAME: "Decimal badge",
        const.CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: ["user-1"],
        const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 100,
        const.CFOF_BADGES_INPUT_MAINTENANCE_RULES: 0,
        const.CFOF_BADGES_INPUT_RESET_SCHEDULE_GRACE_PERIOD_DAYS: 0,
        const.CFOF_BADGES_INPUT_AWARD_ITEMS: [
            const.AWARD_ITEMS_KEY_POINTS,
            const.AWARD_ITEMS_KEY_POINTS_MULTIPLIER,
        ],
        const.CFOF_BADGES_INPUT_AWARD_POINTS: 25.555,
        const.CFOF_BADGES_INPUT_POINTS_MULTIPLIER: 1.255,
    }

    errors = fh.validate_badge_common_inputs(user_input, None)

    assert errors[const.CFOF_BADGES_INPUT_AWARD_POINTS] == (
        const.TRANS_KEY_CFOF_ERROR_AWARD_POINTS_MINIMUM
    )
    assert errors[const.CFOF_BADGES_INPUT_POINTS_MULTIPLIER] == (
        const.TRANS_KEY_CFOF_ERROR_AWARD_INVALID_MULTIPLIER
    )


def test_validate_rewards_inputs_accepts_decimal_cost() -> None:
    """Test reward validation accepts decimal costs."""
    errors = fh.validate_rewards_inputs(
        {
            const.CFOF_REWARDS_INPUT_NAME: "Late Bedtime",
            const.CFOF_REWARDS_INPUT_COST: 12.25,
        }
    )

    assert errors == {}


def test_validate_rewards_inputs_rejects_more_than_two_decimals() -> None:
    """Test reward validation rejects costs beyond 2 decimals."""
    errors = fh.validate_rewards_inputs(
        {
            const.CFOF_REWARDS_INPUT_NAME: "Late Bedtime",
            const.CFOF_REWARDS_INPUT_COST: 12.555,
        }
    )

    assert (
        errors[const.CFOP_ERROR_REWARD_COST] == const.TRANS_KEY_CFOF_INVALID_REWARD_COST
    )


def test_validate_bonuses_inputs_accepts_decimal_points() -> None:
    """Test bonus validation accepts decimal points."""
    errors = fh.validate_bonuses_inputs(
        {
            const.CFOF_BONUSES_INPUT_NAME: "Great attitude",
            const.CFOF_BONUSES_INPUT_POINTS: 2.25,
        }
    )

    assert errors == {}


def test_validate_bonuses_inputs_rejects_more_than_two_decimals() -> None:
    """Test bonus validation rejects points beyond 2 decimals."""
    errors = fh.validate_bonuses_inputs(
        {
            const.CFOF_BONUSES_INPUT_NAME: "Great attitude",
            const.CFOF_BONUSES_INPUT_POINTS: 2.555,
        }
    )

    assert errors[const.DATA_BONUS_POINTS] == const.TRANS_KEY_CFOF_INVALID_BONUS


def test_validate_penalties_inputs_accepts_decimal_points() -> None:
    """Test penalty validation accepts decimal points."""
    errors = fh.validate_penalties_inputs(
        {
            const.CFOF_PENALTIES_INPUT_NAME: "Screen time overrun",
            const.CFOF_PENALTIES_INPUT_POINTS: 1.75,
        }
    )

    assert errors == {}


def test_validate_penalties_inputs_rejects_more_than_two_decimals() -> None:
    """Test penalty validation rejects points beyond 2 decimals."""
    errors = fh.validate_penalties_inputs(
        {
            const.CFOF_PENALTIES_INPUT_NAME: "Screen time overrun",
            const.CFOF_PENALTIES_INPUT_POINTS: 1.755,
        }
    )

    assert errors[const.DATA_PENALTY_POINTS] == const.TRANS_KEY_CFOF_INVALID_PENALTY


def test_validate_achievements_inputs_accepts_decimal_reward_points() -> None:
    """Test achievement validation accepts decimal reward points."""
    errors = fh.validate_achievements_inputs(
        {
            const.CFOF_ACHIEVEMENTS_INPUT_NAME: "Five chores",
            const.CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_USER_IDS: ["user-1"],
            const.CFOF_ACHIEVEMENTS_INPUT_TYPE: const.ACHIEVEMENT_TYPE_TOTAL,
            const.CFOF_ACHIEVEMENTS_INPUT_REWARD_POINTS: 3.25,
        }
    )

    assert errors == {}


def test_validate_achievements_inputs_rejects_more_than_two_decimals() -> None:
    """Test achievement validation rejects reward points beyond 2 decimals."""
    errors = fh.validate_achievements_inputs(
        {
            const.CFOF_ACHIEVEMENTS_INPUT_NAME: "Five chores",
            const.CFOF_ACHIEVEMENTS_INPUT_ASSIGNED_USER_IDS: ["user-1"],
            const.CFOF_ACHIEVEMENTS_INPUT_TYPE: const.ACHIEVEMENT_TYPE_TOTAL,
            const.CFOF_ACHIEVEMENTS_INPUT_REWARD_POINTS: 3.255,
        }
    )

    assert errors[const.DATA_ACHIEVEMENT_REWARD_POINTS] == (
        const.TRANS_KEY_CFOF_INVALID_ACHIEVEMENT_REWARD_POINTS
    )


def test_validate_challenges_inputs_accepts_decimal_reward_points() -> None:
    """Test challenge validation accepts decimal reward points."""
    now = datetime.datetime.now(datetime.UTC)
    errors = fh.validate_challenges_inputs(
        {
            const.CFOF_CHALLENGES_INPUT_NAME: "Weekend sprint",
            const.CFOF_CHALLENGES_INPUT_ASSIGNED_USER_IDS: ["user-1"],
            const.CFOF_CHALLENGES_INPUT_START_DATE: now + datetime.timedelta(days=1),
            const.CFOF_CHALLENGES_INPUT_END_DATE: now + datetime.timedelta(days=2),
            const.CFOF_CHALLENGES_INPUT_TARGET_VALUE: 5,
            const.CFOF_CHALLENGES_INPUT_REWARD_POINTS: 4.5,
        }
    )

    assert errors == {}


def test_validate_challenges_inputs_rejects_more_than_two_decimals() -> None:
    """Test challenge validation rejects reward points beyond 2 decimals."""
    now = datetime.datetime.now(datetime.UTC)
    errors = fh.validate_challenges_inputs(
        {
            const.CFOF_CHALLENGES_INPUT_NAME: "Weekend sprint",
            const.CFOF_CHALLENGES_INPUT_ASSIGNED_USER_IDS: ["user-1"],
            const.CFOF_CHALLENGES_INPUT_START_DATE: now + datetime.timedelta(days=1),
            const.CFOF_CHALLENGES_INPUT_END_DATE: now + datetime.timedelta(days=2),
            const.CFOF_CHALLENGES_INPUT_TARGET_VALUE: 5,
            const.CFOF_CHALLENGES_INPUT_REWARD_POINTS: 4.555,
        }
    )

    assert errors[const.DATA_CHALLENGE_REWARD_POINTS] == (
        const.TRANS_KEY_CFOF_CHALLENGE_POINTS_INVALID
    )
