"""Validation and parsing tests for enhanced frequency features (CFE-2026-001).

Tests for:
- DAILY_MULTI validation (incompatible reset types, kid restrictions)
- parse_daily_multi_times() function unit tests

Test Organization:
- TestDailyMultiValidation: Validation tests (V-01 to V-12)
- TestParseDailyMultiTimes: Parse function unit tests (P-01 to P-08)

See: docs/in-process/CHORE_FREQUENCY_ENHANCEMENTS_IN-PROCESS.md
"""

# pylint: disable=redefined-outer-name

from datetime import UTC, datetime
from typing import Any
from zoneinfo import ZoneInfo

from homeassistant.core import HomeAssistant
import pytest

from custom_components.choreops import const
from custom_components.choreops.helpers import flow_helpers
from custom_components.choreops.utils.dt_utils import parse_daily_multi_times
from tests.helpers import (
    APPROVAL_RESET_AT_DUE_DATE_MULTI,
    APPROVAL_RESET_AT_DUE_DATE_ONCE,
    APPROVAL_RESET_AT_MIDNIGHT_MULTI,
    APPROVAL_RESET_AT_MIDNIGHT_ONCE,
    APPROVAL_RESET_UPON_COMPLETION,
    CFOF_CHORES_INPUT_NAME,
    COMPLETION_CRITERIA_INDEPENDENT,
    COMPLETION_CRITERIA_SHARED,
    FREQUENCY_DAILY_MULTI,
    SetupResult,
    setup_from_yaml,
)

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario for validation tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


@pytest.fixture
async def scenario_shared(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load shared scenario for multi-kid validation tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_shared.yaml",
    )


# =============================================================================
# DAILY_MULTI VALIDATION TESTS
# =============================================================================


class TestDailyMultiValidation:
    """Tests for DAILY_MULTI validation rules.

    Validation rules:
    - V-01 to V-03: Compatible reset types (allowed)
    - V-04 to V-05: Incompatible reset types (rejected)
    - V-06 to V-08: Kid assignment restrictions
    - V-09 to V-12: Time format validation
    """

    @pytest.mark.asyncio
    async def test_v01_daily_multi_upon_completion_valid(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """V-01: DAILY_MULTI + UPON_COMPLETION is valid."""
        errors = flow_helpers.validate_chore_frequency_reset_combination(
            FREQUENCY_DAILY_MULTI,
            APPROVAL_RESET_UPON_COMPLETION,
        )
        assert errors == {}

    @pytest.mark.asyncio
    async def test_v02_daily_multi_at_due_date_once_valid(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """V-02: DAILY_MULTI + AT_DUE_DATE_ONCE is valid."""
        errors = flow_helpers.validate_chore_frequency_reset_combination(
            FREQUENCY_DAILY_MULTI,
            APPROVAL_RESET_AT_DUE_DATE_ONCE,
        )
        assert errors == {}

    @pytest.mark.asyncio
    async def test_v03_daily_multi_at_due_date_multi_valid(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """V-03: DAILY_MULTI + AT_DUE_DATE_MULTI is valid."""
        errors = flow_helpers.validate_chore_frequency_reset_combination(
            FREQUENCY_DAILY_MULTI,
            APPROVAL_RESET_AT_DUE_DATE_MULTI,
        )
        assert errors == {}

    @pytest.mark.asyncio
    async def test_v04_daily_multi_at_midnight_once_rejected(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """V-04: DAILY_MULTI + AT_MIDNIGHT_ONCE is rejected."""
        errors = flow_helpers.validate_chore_frequency_reset_combination(
            FREQUENCY_DAILY_MULTI,
            APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        assert const.CFOP_ERROR_DAILY_MULTI_RESET in errors
        assert (
            errors[const.CFOP_ERROR_DAILY_MULTI_RESET]
            == const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_REQUIRES_COMPATIBLE_RESET
        )

    @pytest.mark.asyncio
    async def test_v05_daily_multi_at_midnight_multi_rejected(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """V-05: DAILY_MULTI + AT_MIDNIGHT_MULTI is rejected."""
        errors = flow_helpers.validate_chore_frequency_reset_combination(
            FREQUENCY_DAILY_MULTI,
            APPROVAL_RESET_AT_MIDNIGHT_MULTI,
        )
        assert const.CFOP_ERROR_DAILY_MULTI_RESET in errors
        assert (
            errors[const.CFOP_ERROR_DAILY_MULTI_RESET]
            == const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_REQUIRES_COMPATIBLE_RESET
        )

    @pytest.mark.asyncio
    async def test_v06_daily_multi_independent_single_kid_ok(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """V-06: DAILY_MULTI + INDEPENDENT + 1 kid is valid."""
        errors = flow_helpers.validate_daily_multi_kids(
            FREQUENCY_DAILY_MULTI,
            COMPLETION_CRITERIA_INDEPENDENT,
            ["kid1_id"],  # Single kid
        )
        assert errors == {}

    @pytest.mark.asyncio
    async def test_v07_daily_multi_independent_multi_kids_rejected(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """V-07: DAILY_MULTI + INDEPENDENT + multiple kids is rejected."""
        errors = flow_helpers.validate_daily_multi_kids(
            FREQUENCY_DAILY_MULTI,
            COMPLETION_CRITERIA_INDEPENDENT,
            ["kid1_id", "kid2_id"],  # Multiple kids
        )
        assert const.CFOP_ERROR_DAILY_MULTI_KIDS in errors
        assert (
            errors[const.CFOP_ERROR_DAILY_MULTI_KIDS]
            == const.TRANS_KEY_CFOF_ERROR_DAILY_MULTI_INDEPENDENT_MULTI_KIDS
        )

    @pytest.mark.asyncio
    async def test_v08_daily_multi_shared_multi_kids_ok(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """V-08: DAILY_MULTI + SHARED + multiple kids is valid."""
        errors = flow_helpers.validate_daily_multi_kids(
            FREQUENCY_DAILY_MULTI,
            COMPLETION_CRITERIA_SHARED,
            ["kid1_id", "kid2_id", "kid3_id"],  # Multiple kids OK for shared
        )
        assert errors == {}

    @pytest.mark.asyncio
    async def test_v09_invalid_time_format_rejected(
        self,
        hass: HomeAssistant,
    ) -> None:
        """V-09: Invalid time format (8am|5pm) is rejected."""
        errors = flow_helpers.validate_daily_multi_times("8am|5pm")
        assert errors != {}

    @pytest.mark.asyncio
    async def test_v10_single_time_rejected(
        self,
        hass: HomeAssistant,
    ) -> None:
        """V-10: Single time (only 1) is rejected."""
        errors = flow_helpers.validate_daily_multi_times("08:00")
        assert errors != {}

    @pytest.mark.asyncio
    async def test_v11_seven_times_rejected(
        self,
        hass: HomeAssistant,
    ) -> None:
        """V-11: Seven times (>6) is rejected."""
        errors = flow_helpers.validate_daily_multi_times(
            "06:00|07:00|08:00|09:00|10:00|11:00|12:00"
        )
        assert errors != {}

    @pytest.mark.asyncio
    async def test_v12_empty_times_rejected(
        self,
        hass: HomeAssistant,
    ) -> None:
        """V-12: Empty times string is rejected."""
        errors = flow_helpers.validate_daily_multi_times("")
        assert errors != {}


# =============================================================================
# PARSE FUNCTION UNIT TESTS
# =============================================================================


class TestParseDailyMultiTimes:
    """Unit tests for parse_daily_multi_times() function.

    Tests parsing of pipe-separated time strings into sorted datetime list.
    """

    @pytest.mark.asyncio
    async def test_p01_parse_two_times_valid(
        self,
        hass: HomeAssistant,
    ) -> None:
        """P-01: Parse two valid times correctly."""
        current = datetime(2026, 1, 14, 12, 0, 0, tzinfo=UTC)
        result = parse_daily_multi_times("08:00|17:00", current, current.tzinfo)

        assert len(result) == 2
        assert result[0].hour == 8
        assert result[0].minute == 0
        assert result[1].hour == 17
        assert result[1].minute == 0

    @pytest.mark.asyncio
    async def test_p02_parse_six_times_valid(
        self,
        hass: HomeAssistant,
    ) -> None:
        """P-02: Parse six valid times correctly."""
        current = datetime(2026, 1, 14, 12, 0, 0, tzinfo=UTC)
        result = parse_daily_multi_times(
            "06:00|08:00|10:00|12:00|14:00|16:00",
            current,
            current.tzinfo,
        )

        assert len(result) == 6
        hours = [slot.hour for slot in result]
        assert hours == [6, 8, 10, 12, 14, 16]

    @pytest.mark.asyncio
    async def test_p03_parse_unsorted_gets_sorted(
        self,
        hass: HomeAssistant,
    ) -> None:
        """P-03: Unsorted input gets sorted in output."""
        current = datetime(2026, 1, 14, 12, 0, 0, tzinfo=UTC)
        result = parse_daily_multi_times("17:00|08:00|12:00", current, current.tzinfo)

        assert len(result) == 3
        hours = [slot.hour for slot in result]
        assert hours == [8, 12, 17]  # Sorted

    @pytest.mark.asyncio
    async def test_p04_parse_invalid_hour_skipped(
        self,
        hass: HomeAssistant,
    ) -> None:
        """P-04: Invalid hour (25) is skipped."""
        current = datetime(2026, 1, 14, 12, 0, 0, tzinfo=UTC)
        result = parse_daily_multi_times("25:00|08:00|17:00", current, current.tzinfo)

        assert len(result) == 2
        hours = [slot.hour for slot in result]
        assert 25 not in hours
        assert hours == [8, 17]

    @pytest.mark.asyncio
    async def test_p05_parse_invalid_minute_skipped(
        self,
        hass: HomeAssistant,
    ) -> None:
        """P-05: Invalid minute (70) is skipped."""
        current = datetime(2026, 1, 14, 12, 0, 0, tzinfo=UTC)
        result = parse_daily_multi_times("08:70|17:00", current, current.tzinfo)

        assert len(result) == 1
        assert result[0].hour == 17

    @pytest.mark.asyncio
    async def test_p06_parse_non_numeric_skipped(
        self,
        hass: HomeAssistant,
    ) -> None:
        """P-06: Non-numeric entries are skipped."""
        current = datetime(2026, 1, 14, 12, 0, 0, tzinfo=UTC)
        result = parse_daily_multi_times("morning|17:00", current, current.tzinfo)

        assert len(result) == 1
        assert result[0].hour == 17

    @pytest.mark.asyncio
    async def test_p07_parse_whitespace_handled(
        self,
        hass: HomeAssistant,
    ) -> None:
        """P-07: Whitespace is trimmed correctly."""
        current = datetime(2026, 1, 14, 12, 0, 0, tzinfo=UTC)
        result = parse_daily_multi_times(" 08:00 | 17:00 ", current, current.tzinfo)

        assert len(result) == 2
        assert result[0].hour == 8
        assert result[1].hour == 17

    @pytest.mark.asyncio
    async def test_p08_parse_returns_timezone_aware(
        self,
        hass: HomeAssistant,
    ) -> None:
        """P-08: Parsed times have timezone info set."""
        eastern = ZoneInfo("America/New_York")
        current = datetime(2026, 1, 14, 12, 0, 0, tzinfo=eastern)
        result = parse_daily_multi_times("08:00|17:00", current, eastern)

        assert len(result) == 2
        for slot in result:
            assert slot.tzinfo is not None


# =============================================================================
# ADDITIONAL EDGE CASE TESTS
# =============================================================================


class TestValidationEdgeCases:
    """Additional edge case tests for validation functions."""

    @pytest.mark.asyncio
    async def test_non_daily_multi_no_reset_restriction(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Non-DAILY_MULTI frequencies have no reset restrictions."""
        # DAILY frequency should work with AT_MIDNIGHT_ONCE
        errors = flow_helpers.validate_chore_frequency_reset_combination(
            const.FREQUENCY_DAILY,
            APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        assert errors == {}

    @pytest.mark.asyncio
    async def test_non_daily_multi_no_kids_restriction(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Non-DAILY_MULTI frequencies have no kid restrictions."""
        # DAILY + INDEPENDENT + multiple kids should work
        errors = flow_helpers.validate_daily_multi_kids(
            const.FREQUENCY_DAILY,
            COMPLETION_CRITERIA_INDEPENDENT,
            ["kid1_id", "kid2_id"],
        )
        assert errors == {}

    @pytest.mark.asyncio
    async def test_custom_from_complete_no_reset_restriction(
        self,
        hass: HomeAssistant,
    ) -> None:
        """CUSTOM_FROM_COMPLETE has no reset type restrictions."""
        errors = flow_helpers.validate_chore_frequency_reset_combination(
            const.FREQUENCY_CUSTOM_FROM_COMPLETE,
            APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        )
        assert errors == {}

    @pytest.mark.asyncio
    async def test_valid_times_two_entries(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Two valid time entries pass validation."""
        errors = flow_helpers.validate_daily_multi_times("08:00|17:00")
        assert errors == {}

    @pytest.mark.asyncio
    async def test_valid_times_six_entries(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Six valid time entries pass validation."""
        errors = flow_helpers.validate_daily_multi_times(
            "06:00|08:00|10:00|12:00|14:00|16:00"
        )
        assert errors == {}

    @pytest.mark.asyncio
    async def test_valid_times_with_leading_zeros(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Times with leading zeros are valid."""
        errors = flow_helpers.validate_daily_multi_times("06:00|09:30")
        assert errors == {}

    @pytest.mark.asyncio
    async def test_valid_times_midnight_and_noon(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Midnight (00:00) and noon (12:00) are valid."""
        errors = flow_helpers.validate_daily_multi_times("00:00|12:00")
        assert errors == {}

    @pytest.mark.asyncio
    async def test_valid_times_late_night(
        self,
        hass: HomeAssistant,
    ) -> None:
        """Late night times (23:30) are valid."""
        errors = flow_helpers.validate_daily_multi_times("06:45|23:30")
        assert errors == {}


# =============================================================================
# TEST CLASS: AT_DUE_DATE Reset Type Due Date Requirement Validation
# =============================================================================


class TestAtDueDateResetRequiresDueDate:
    """Test validation that AT_DUE_DATE_* reset types require due dates.

    Test Scenarios:
    - Shared chores: Must have due date (no exception)
    - Independent 1-kid: Must have due date (no exception)
    - Independent 2+ kids: May skip due date (per-kid dates set in helper/Configure)
    """

    @pytest.mark.asyncio
    async def test_shared_at_due_date_once_requires_due_date(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """SHARED + AT_DUE_DATE_ONCE without due date → error."""
        zoe_id = scenario_minimal.kid_ids["Zoë"]

        user_input = {
            CFOF_CHORES_INPUT_NAME: "Test Chore",
            const.CFOF_CHORES_INPUT_ASSIGNED_KIDS: ["Zoë"],
            const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_SHARED,
            const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY: const.FREQUENCY_WEEKLY,
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
            const.CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: const.OVERDUE_HANDLING_AT_DUE_DATE,
            # No due_date provided
        }

        kids_dict = {"Zoë": zoe_id}
        errors, _due_date_str = flow_helpers.validate_chores_inputs(
            user_input, kids_dict, {}
        )

        assert const.CFOP_ERROR_AT_DUE_DATE_RESET_REQUIRES_DUE_DATE in errors

    @pytest.mark.asyncio
    async def test_independent_single_kid_at_due_date_multi_requires_due_date(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """INDEPENDENT (1 kid) + AT_DUE_DATE_MULTI without due date → error."""
        zoe_id = scenario_minimal.kid_ids["Zoë"]

        user_input = {
            CFOF_CHORES_INPUT_NAME: "Test Chore",
            const.CFOF_CHORES_INPUT_ASSIGNED_KIDS: ["Zoë"],
            const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY: const.FREQUENCY_WEEKLY,
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
            const.CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: const.OVERDUE_HANDLING_AT_DUE_DATE,
            # No due_date provided
        }

        kids_dict = {"Zoë": zoe_id}
        errors, _due_date_str = flow_helpers.validate_chores_inputs(
            user_input, kids_dict, {}
        )

        assert const.CFOP_ERROR_AT_DUE_DATE_RESET_REQUIRES_DUE_DATE in errors

    @pytest.mark.asyncio
    async def test_independent_multikid_at_due_date_once_allows_missing_due_date(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """INDEPENDENT (2+ kids) + AT_DUE_DATE_ONCE without due date → allowed.

        Exception: Per-kid due dates will be set in helper step or via Configure.
        """
        kid_ids = scenario_shared.kid_ids
        zoe_id = kid_ids["Zoë"]
        max_id = kid_ids["Max!"]

        user_input = {
            CFOF_CHORES_INPUT_NAME: "Test Chore",
            const.CFOF_CHORES_INPUT_ASSIGNED_KIDS: ["Zoë", "Max!"],
            const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY: const.FREQUENCY_WEEKLY,
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
            const.CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: const.OVERDUE_HANDLING_AT_DUE_DATE,
            # No due_date provided - should be allowed for Independent multi-kid
        }

        kids_dict = {"Zoë": zoe_id, "Max!": max_id}
        errors, _due_date_str = flow_helpers.validate_chores_inputs(
            user_input, kids_dict, {}
        )

        # Should NOT have validation error
        assert const.CFOP_ERROR_AT_DUE_DATE_RESET_REQUIRES_DUE_DATE not in errors

    @pytest.mark.asyncio
    async def test_independent_multikid_at_due_date_multi_allows_missing_due_date(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """INDEPENDENT (2+ kids) + AT_DUE_DATE_MULTI without due date → allowed."""

        kid_ids = scenario_shared.kid_ids
        zoe_id = kid_ids["Zoë"]
        max_id = kid_ids["Max!"]

        user_input = {
            CFOF_CHORES_INPUT_NAME: "Test Chore",
            const.CFOF_CHORES_INPUT_ASSIGNED_KIDS: ["Zoë", "Max!"],
            const.CFOF_CHORES_INPUT_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.CFOF_CHORES_INPUT_RECURRING_FREQUENCY: const.FREQUENCY_WEEKLY,
            const.CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_DUE_DATE_MULTI,
            const.CFOF_CHORES_INPUT_OVERDUE_HANDLING_TYPE: const.OVERDUE_HANDLING_AT_DUE_DATE,
            # No due_date provided - should be allowed for Independent multi-kid
        }

        kids_dict = {"Zoë": zoe_id, "Max!": max_id}
        errors, _due_date_str = flow_helpers.validate_chores_inputs(
            user_input, kids_dict, {}
        )

        # Should NOT have validation error
        assert const.CFOP_ERROR_AT_DUE_DATE_RESET_REQUIRES_DUE_DATE not in errors
