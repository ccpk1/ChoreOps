"""Tests for periodic badge date clearing fix (Issue #237).

Covers two bug fixes:
1. START_DATE is no longer force-cleared when editing a badge with a
   non-custom recurring frequency (previously only preserved END_DATE).
2. New clear_start_date / clear_end_date checkboxes allow dates to be
   cleared from the badge edit form (date selectors can't be emptied).

These are unit tests on the validation layer, which is where both fixes
are implemented. Follows test_points_helpers.py patterns.
"""

from typing import Any

from custom_components.choreops import const, data_builders as db
from custom_components.choreops.helpers import flow_helpers as fh


def _periodic_badge_input(
    *,
    start_date: str | None = "2026-08-12",
    end_date: str | None = "2026-08-24",
    frequency: str = const.FREQUENCY_WEEKLY,
) -> dict[str, Any]:
    """Build a minimal periodic badge user_input dict for validation."""
    return {
        const.CFOF_BADGES_INPUT_NAME: "Perfect Week",
        const.CFOF_BADGES_INPUT_ASSIGNED_USER_IDS: ["user-1"],
        const.CFOF_BADGES_INPUT_TARGET_THRESHOLD_VALUE: 5,
        const.CFOF_BADGES_INPUT_RESET_SCHEDULE_RECURRING_FREQUENCY: frequency,
        const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE: start_date,
        const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE: end_date,
        const.CFOF_BADGES_INPUT_AWARD_POINTS: 5.0,
        const.CFOF_BADGES_INPUT_AWARD_ITEMS: ["points"],
    }


# ============================================================================
# PHASE 1 FIX: START_DATE preserved for non-custom frequencies
# ============================================================================


def test_non_custom_frequency_preserves_start_date() -> None:
    """START_DATE must survive validation for weekly frequency (issue #237).

    Regression for the bug where START_DATE was force-cleared alongside the
    custom-interval fields when the frequency was anything other than custom.
    """
    user_input = _periodic_badge_input(
        start_date="2026-08-12",
        end_date="2026-08-24",
        frequency=const.FREQUENCY_WEEKLY,
    )

    errors = fh.validate_badge_common_inputs(
        user_input, None, badge_type=const.BADGE_TYPE_PERIODIC
    )

    assert errors == {}
    assert user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE] == "2026-08-12"
    assert user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE] == "2026-08-24"


def test_non_custom_frequency_preserves_start_date_across_frequency_change() -> None:
    """Changing between non-custom frequencies preserves start_date."""
    for frequency in (
        const.FREQUENCY_WEEKLY,
        const.FREQUENCY_MONTHLY,
        const.FREQUENCY_DAILY,
        const.FREQUENCY_NONE,
    ):
        user_input = _periodic_badge_input(
            start_date="2026-08-12",
            end_date="2026-08-24",
            frequency=frequency,
        )

        errors = fh.validate_badge_common_inputs(
            user_input, None, badge_type=const.BADGE_TYPE_PERIODIC
        )

        assert errors == {}
        assert (
            user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE]
            == "2026-08-12"
        ), f"start_date not preserved for frequency {frequency}"
        # END_DATE was always preserved (existing behavior) - now matches
        assert (
            user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE] == "2026-08-24"
        ), f"end_date not preserved for frequency {frequency}"


def test_custom_frequency_still_clears_custom_interval_but_preserves_start() -> None:
    """Custom frequency clears custom-interval fields but preserves start_date."""
    user_input = _periodic_badge_input(
        start_date="2026-08-12",
        end_date="2026-08-24",
        frequency=const.FREQUENCY_CUSTOM,
    )
    user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL] = 3
    user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT] = (
        const.TIME_UNIT_DAYS
    )

    errors = fh.validate_badge_common_inputs(
        user_input, None, badge_type=const.BADGE_TYPE_PERIODIC
    )

    assert errors == {}
    assert user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE] == "2026-08-12"
    assert user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL] == 3
    assert (
        user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT]
        == const.TIME_UNIT_DAYS
    )


# ============================================================================
# PHASE 2 FIX: clear_start_date / clear_end_date checkboxes
# ============================================================================


def test_clear_start_date_checkbox_nulls_start_date() -> None:
    """clear_start_date=True must null start_date in user_input."""
    user_input = _periodic_badge_input(
        start_date="2026-08-12",
        end_date="2026-08-24",
    )
    user_input[const.CFOF_BADGES_INPUT_CLEAR_START_DATE] = True

    errors = fh.validate_badge_common_inputs(
        user_input, None, badge_type=const.BADGE_TYPE_PERIODIC
    )

    assert errors == {}
    assert user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE] is None
    assert user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE] == "2026-08-24"


def test_clear_end_date_checkbox_nulls_end_date() -> None:
    """clear_end_date=True must null the stored end_date."""
    user_input = _periodic_badge_input(
        start_date="2026-08-12",
        end_date="2026-08-24",
    )
    user_input[const.CFOF_BADGES_INPUT_CLEAR_END_DATE] = True

    errors = fh.validate_badge_common_inputs(
        user_input, None, badge_type=const.BADGE_TYPE_PERIODIC
    )

    assert errors == {}
    assert user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE] is None
    assert user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE] == "2026-08-12"


def test_clear_both_dates_checkboxes_null_both() -> None:
    """Checking both clear boxes clears both dates."""
    user_input = _periodic_badge_input(
        start_date="2026-08-12",
        end_date="2026-08-24",
    )
    user_input[const.CFOF_BADGES_INPUT_CLEAR_START_DATE] = True
    user_input[const.CFOF_BADGES_INPUT_CLEAR_END_DATE] = True

    errors = fh.validate_badge_common_inputs(
        user_input, None, badge_type=const.BADGE_TYPE_PERIODIC
    )

    assert errors == {}
    assert user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE] is None
    assert user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_END_DATE] is None


def test_clear_checkbox_does_not_affect_custom_frequency_required_dates() -> None:
    """Custom frequency still requires start_date even when clear flag set.

    Clearing is intended for editing to return to unset state. For custom
    frequency, start_date remains required by validation after clearing.
    """
    user_input = _periodic_badge_input(
        start_date=None,
        end_date=None,
        frequency=const.FREQUENCY_CUSTOM,
    )
    user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL] = 1
    user_input[const.CFOF_BADGES_INPUT_RESET_SCHEDULE_CUSTOM_INTERVAL_UNIT] = (
        const.TIME_UNIT_DAYS
    )

    errors = fh.validate_badge_common_inputs(
        user_input, None, badge_type=const.BADGE_TYPE_PERIODIC
    )

    assert errors != {}
    assert const.CFOF_BADGES_INPUT_RESET_SCHEDULE_START_DATE in errors


# ============================================================================
# DATA BUILDER ROUND-TRIP: cleared dates stored as null
# ============================================================================


def test_build_badge_stores_cleared_dates_as_null() -> None:
    """build_badge persists None dates as null in reset_schedule."""
    user_input = _periodic_badge_input(
        start_date="2026-08-12",
        end_date="2026-08-24",
    )
    user_input[const.CFOF_BADGES_INPUT_CLEAR_START_DATE] = True
    user_input[const.CFOF_BADGES_INPUT_CLEAR_END_DATE] = True
    user_input[const.CFOF_BADGES_INPUT_SELECTED_CHORES] = []

    fh.validate_badge_common_inputs(
        user_input, None, badge_type=const.BADGE_TYPE_PERIODIC
    )

    badge = db.build_badge(user_input, badge_type=const.BADGE_TYPE_PERIODIC)
    reset_schedule = badge[const.DATA_BADGE_RESET_SCHEDULE]

    assert reset_schedule[const.DATA_BADGE_RESET_SCHEDULE_START_DATE] is None
    assert reset_schedule[const.DATA_BADGE_RESET_SCHEDULE_END_DATE] is None
