"""Tests for PKAD-2026-001: Per-Assignee Applicable Days feature.

This module tests the per-assignee applicable days functionality that allows
INDEPENDENT chores to have different weekday schedules per assignee.

Test Organization:
- TestPerAssigneeValidation: Unit tests for validation functions
- TestPerAssigneeDashboardDisplay: Verifies per-assignee days appear correctly in dashboard
- TestPerAssigneeMigration: Migration from pre-v50 chore format
- TestPerAssigneeDataIntegrity: Ensures SHARED chores don't get per-assignee data

Scenarios Used:
- scenario_minimal: 1 assignee (Zoë), 1 approver
- scenario_shared: 3 assignees (Zoë, Max!, Lila), 1 approver, shared chores
- scenario_per_assignee: INDEPENDENT chore with per-assignee days (Zoë=Mon/Wed, Max=Tue/Thu)
"""

# pylint: disable=redefined-outer-name

from typing import Any

from homeassistant.core import HomeAssistant
import pytest

from custom_components.choreops import const
from custom_components.choreops.coordinator import ChoreOpsDataCoordinator
from custom_components.choreops.helpers import flow_helpers as fh
from custom_components.choreops.migration_pre_v50 import PreV50Migrator
from tests.helpers.setup import SetupResult, setup_from_yaml

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario: 1 assignee, 1 approver, 5 chores."""
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
    """Load shared scenario: 3 assignees, 1 approver, 8 shared chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_shared.yaml",
    )


@pytest.fixture
async def scenario_per_assignee(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Setup per-assignee applicable days by injecting data into scenario_shared.

    Creates an INDEPENDENT chore with different schedules per assignee:
    - Zoë: Mon, Wed (days 0, 2)
    - Max!: Tue, Thu (days 1, 3)

    This validates that assignees see different applicable days for the same chore.
    """
    result = await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_shared.yaml",
    )
    coordinator = result.coordinator

    zoe_id = result.assignee_ids.get("Zoë")
    max_id = result.assignee_ids.get("Max!")

    if not zoe_id or not max_id:
        for assignee_id, assignee_info in coordinator.assignees_data.items():
            name = assignee_info.get(const.DATA_ASSIGNEE_NAME, "")
            if "Zo" in name or "zoe" in name.lower():
                zoe_id = assignee_id
            elif "Max" in name:
                max_id = assignee_id

    chores_data = coordinator._data.get(const.DATA_CHORES, {})
    modified = False

    for chore_info in chores_data.values():
        assigned_assignees = chore_info.get(const.DATA_CHORE_ASSIGNED_ASSIGNEES, [])
        if (
            len(assigned_assignees) >= 2
            and zoe_id in assigned_assignees
            and max_id in assigned_assignees
        ):
            if not modified:
                chore_info[const.DATA_CHORE_COMPLETION_CRITERIA] = (
                    const.COMPLETION_CRITERIA_INDEPENDENT
                )
                # CRITICAL: Use string format to match real UI flow data
                # UI selector returns ["mon", "wed"], NOT [0, 2]
                chore_info[const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS] = {
                    zoe_id: ["mon", "wed"],  # Mon, Wed (strings, not integers)
                    max_id: ["tue", "thu"],  # Tue, Thu (strings, not integers)
                }
                modified = True

    await coordinator.async_refresh()
    await hass.async_block_till_done()

    return result


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def find_independent_chore_with_per_assignee_days(
    coordinator: ChoreOpsDataCoordinator,
) -> tuple[str, dict[str, Any]]:
    """Find an INDEPENDENT chore that has per_assignee_applicable_days set."""
    for chore_id, chore_info in coordinator.chores_data.items():
        criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
        per_assignee_days = chore_info.get(
            const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS, {}
        )
        if criteria == const.COMPLETION_CRITERIA_INDEPENDENT and per_assignee_days:
            return chore_id, chore_info
    raise ValueError("No INDEPENDENT chore with per_assignee_applicable_days found")


def find_shared_chore(
    coordinator: ChoreOpsDataCoordinator,
) -> tuple[str, dict[str, Any]]:
    """Find a SHARED or SHARED_FIRST chore."""
    for chore_id, chore_info in coordinator.chores_data.items():
        criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
        if criteria in [
            const.COMPLETION_CRITERIA_SHARED,
            const.COMPLETION_CRITERIA_SHARED_FIRST,
        ]:
            return chore_id, chore_info
    raise ValueError("No SHARED chore found")


# =============================================================================
# VALIDATION FUNCTION TESTS
# =============================================================================


class TestPerAssigneeValidation:
    """Unit tests for per_assignee_applicable_days validation functions.

    These test the validation logic in flow_helpers.py that runs during
    config flow to ensure user input is valid before saving.
    """

    def test_valid_weekday_list_accepted(self) -> None:
        """Valid weekday numbers [0-6] pass validation."""
        per_assignee_days = {"assignee-uuid-1": [0, 2, 4]}  # Mon, Wed, Fri

        is_valid, error_key = fh.validate_per_assignee_applicable_days(
            per_assignee_days
        )

        assert is_valid is True
        assert error_key is None

    def test_empty_dict_uses_chore_level_days(self) -> None:
        """Empty per_assignee_days dict means use chore-level applicable_days."""
        per_assignee_days: dict[str, list[int]] = {}

        is_valid, error_key = fh.validate_per_assignee_applicable_days(
            per_assignee_days
        )

        assert is_valid is True, "Empty dict should be valid (use chore-level days)"

    def test_empty_list_means_all_days_applicable(self) -> None:
        """Empty list for a assignee means all 7 days are applicable."""
        per_assignee_days: dict[str, list[int]] = {"assignee-uuid-1": []}

        is_valid, error_key = fh.validate_per_assignee_applicable_days(
            per_assignee_days
        )

        assert is_valid is True, "Empty list should be valid (all days)"

    def test_day_value_above_6_rejected(self) -> None:
        """Day value 7 or higher is invalid (only 0-6 for Mon-Sun)."""
        per_assignee_days = {"assignee-uuid-1": [7]}

        is_valid, error_key = fh.validate_per_assignee_applicable_days(
            per_assignee_days
        )

        assert is_valid is False
        assert (
            error_key == const.TRANS_KEY_CFOF_ERROR_PER_ASSIGNEE_APPLICABLE_DAYS_INVALID
        )

    def test_negative_day_value_rejected(self) -> None:
        """Negative day values are invalid."""
        per_assignee_days = {"assignee-uuid-1": [-1]}

        is_valid, error_key = fh.validate_per_assignee_applicable_days(
            per_assignee_days
        )

        assert is_valid is False
        assert (
            error_key == const.TRANS_KEY_CFOF_ERROR_PER_ASSIGNEE_APPLICABLE_DAYS_INVALID
        )

    def test_duplicate_days_rejected(self) -> None:
        """Duplicate day values in list are invalid."""
        per_assignee_days = {"assignee-uuid-1": [0, 0, 1]}  # Monday listed twice

        is_valid, error_key = fh.validate_per_assignee_applicable_days(
            per_assignee_days
        )

        assert is_valid is False
        assert (
            error_key == const.TRANS_KEY_CFOF_ERROR_PER_ASSIGNEE_APPLICABLE_DAYS_INVALID
        )

    def test_all_seven_days_valid(self) -> None:
        """Full week selection [0,1,2,3,4,5,6] is valid."""
        per_assignee_days = {"assignee-uuid-1": [0, 1, 2, 3, 4, 5, 6]}

        is_valid, error_key = fh.validate_per_assignee_applicable_days(
            per_assignee_days
        )

        assert is_valid is True

    def test_unsorted_days_valid(self) -> None:
        """Days don't need to be sorted - [6, 0, 3] is valid."""
        per_assignee_days = {"assignee-uuid-1": [6, 0, 3]}  # Sun, Mon, Thu

        is_valid, error_key = fh.validate_per_assignee_applicable_days(
            per_assignee_days
        )

        assert is_valid is True

    def test_daily_multi_times_valid_format(self) -> None:
        """Valid time format for DAILY_MULTI passes validation."""
        per_assignee_times = {"assignee-uuid-1": "08:00|17:00"}

        is_valid, error_key = fh.validate_per_assignee_daily_multi_times(
            per_assignee_times, const.FREQUENCY_DAILY_MULTI
        )

        assert is_valid is True
        assert error_key is None

    def test_daily_multi_times_skipped_for_other_frequencies(self) -> None:
        """Validation is skipped for non-DAILY_MULTI frequencies."""
        per_assignee_times = {"assignee-uuid-1": "invalid-format"}

        # Using DAILY (not DAILY_MULTI), so validation should skip
        is_valid, error_key = fh.validate_per_assignee_daily_multi_times(
            per_assignee_times, const.FREQUENCY_DAILY
        )

        assert is_valid is True, "Non-DAILY_MULTI should skip validation"


# =============================================================================
# DASHBOARD DISPLAY TESTS
# =============================================================================


class TestPerAssigneeDashboardDisplay:
    """Tests that per-assignee applicable days appear correctly in dashboard helper.

    The dashboard helper sensor provides chore data to the frontend, including
    the formatted 'assigned_days' string and 'assigned_days_raw' list.
    These tests verify that INDEPENDENT chores show assignee-specific days.
    """

    @pytest.mark.asyncio
    async def test_dashboard_shows_different_days_per_assignee(
        self, hass: HomeAssistant, scenario_per_assignee: SetupResult
    ) -> None:
        """Zoë and Max see different assigned_days for the same chore."""
        coordinator = scenario_per_assignee.coordinator
        await coordinator.async_refresh()
        await hass.async_block_till_done()

        # Get Zoë's dashboard helper
        zoe_helper = hass.states.get("sensor.zoe_choreops_ui_dashboard_helper")
        assert zoe_helper is not None, "Zoë's dashboard helper not found"

        # Get Max's dashboard helper
        max_helper = hass.states.get("sensor.max_choreops_ui_dashboard_helper")
        assert max_helper is not None, "Max's dashboard helper not found"

        zoe_chores = zoe_helper.attributes.get("chores", [])
        max_chores = max_helper.attributes.get("chores", [])

        assert len(zoe_chores) > 0, "Zoë should have chores assigned"
        assert len(max_chores) > 0, "Max should have chores assigned"

        # Find the INDEPENDENT chore with per-assignee days
        chore_id, chore_info = find_independent_chore_with_per_assignee_days(
            coordinator
        )
        chore_name = chore_info.get(const.DATA_CHORE_NAME, "")

        # Find this chore in each assignee's dashboard by name
        zoe_chore = next((c for c in zoe_chores if c.get("name") == chore_name), None)
        max_chore = next((c for c in max_chores if c.get("name") == chore_name), None)

        # Both assignees should have this chore
        assert zoe_chore is not None, "Zoë should have the per-assignee chore"
        assert max_chore is not None, "Max should have the per-assignee chore"

        # They should have DIFFERENT assigned_days_raw
        zoe_days_raw = zoe_chore.get("assigned_days_raw", [])
        max_days_raw = max_chore.get("assigned_days_raw", [])

        # Per fixture: Zoë=["mon","wed"], Max=["tue","thu"] (strings, not integers)
        assert set(zoe_days_raw).isdisjoint(set(max_days_raw)), (
            f"Assignees should have non-overlapping days: Zoë={zoe_days_raw}, Max={max_days_raw}"
        )


# =============================================================================
# DATA INTEGRITY TESTS
# =============================================================================


class TestPerAssigneeDataIntegrity:
    """Tests that per_assignee_applicable_days is only used for INDEPENDENT chores.

    SHARED and SHARED_FIRST chores must use chore-level applicable_days
    because all assignees share the same schedule.
    """

    @pytest.mark.asyncio
    async def test_shared_chores_have_no_per_assignee_days(
        self, hass: HomeAssistant, scenario_per_assignee: SetupResult
    ) -> None:
        """SHARED chores should NOT have per_assignee_applicable_days."""
        coordinator = scenario_per_assignee.coordinator

        chore_id, chore_info = find_shared_chore(coordinator)

        per_assignee_days = chore_info.get(
            const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS
        )
        assert per_assignee_days is None or per_assignee_days == {}, (
            f"SHARED chore '{chore_info.get(const.DATA_CHORE_NAME)}' "
            f"should not have per_assignee_applicable_days, got: {per_assignee_days}"
        )

    @pytest.mark.asyncio
    async def test_independent_chore_has_per_assignee_structure(
        self, hass: HomeAssistant, scenario_per_assignee: SetupResult
    ) -> None:
        """INDEPENDENT chores with multi-assignee assignment should have per_assignee data."""
        coordinator = scenario_per_assignee.coordinator

        chore_id, chore_info = find_independent_chore_with_per_assignee_days(
            coordinator
        )

        # Verify it's INDEPENDENT
        criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
        assert criteria == const.COMPLETION_CRITERIA_INDEPENDENT

        # Verify per_assignee_applicable_days has entries
        per_assignee_days = chore_info.get(
            const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS, {}
        )
        assert len(per_assignee_days) >= 2, (
            "INDEPENDENT chore with multiple assignees should have per_assignee data for each"
        )

    @pytest.mark.asyncio
    async def test_per_assignee_days_match_injected_values(
        self, hass: HomeAssistant, scenario_per_assignee: SetupResult
    ) -> None:
        """Per-assignee days match the fixture injection: Zoë=['mon','wed'], Max=['tue','thu']."""
        coordinator = scenario_per_assignee.coordinator

        _, chore_info = find_independent_chore_with_per_assignee_days(coordinator)
        per_assignee_days = chore_info.get(
            const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS, {}
        )

        zoe_id = scenario_per_assignee.assignee_ids.get("Zoë")
        max_id = scenario_per_assignee.assignee_ids.get("Max!")

        if zoe_id and zoe_id in per_assignee_days:
            assert per_assignee_days[zoe_id] == ["mon", "wed"], (
                "Zoë should have Mon, Wed"
            )

        if max_id and max_id in per_assignee_days:
            assert per_assignee_days[max_id] == ["tue", "thu"], (
                "Max should have Tue, Thu"
            )


# =============================================================================
# MIGRATION TESTS
# =============================================================================


class TestPerAssigneeMigration:
    """Tests for PreV50Migrator migration of per_assignee_applicable_days.

    Old INDEPENDENT chores had chore-level applicable_days. Migration copies
    these to per_assignee_applicable_days for each assigned assignee.
    """

    @pytest.mark.asyncio
    async def test_old_independent_chore_migrates_to_per_assignee(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Pre-v50 INDEPENDENT chore gets per_assignee_applicable_days populated."""
        coordinator = scenario_minimal.coordinator
        zoe_id = scenario_minimal.assignee_ids["Zoë"]

        # Create old-style chore WITHOUT per_assignee_applicable_days
        test_chore_id = "test-migration-chore"
        old_chore = {
            const.DATA_CHORE_NAME: "Migration Test Chore",
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.DATA_CHORE_ASSIGNED_ASSIGNEES: [zoe_id],
            const.DATA_CHORE_APPLICABLE_DAYS: [0, 1, 2],  # Mon-Wed at chore level
            const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
            const.DATA_CHORE_ICON: "mdi:test",
            const.DATA_CHORE_DEFAULT_POINTS: 5.0,
            const.DATA_CHORE_INTERNAL_ID: test_chore_id,
            # NO per_assignee_applicable_days - pre-v50 format
        }

        coordinator._data[const.DATA_CHORES][test_chore_id] = old_chore

        # Run migration
        migrator = PreV50Migrator(coordinator)
        migrator._migrate_per_assignee_applicable_days()

        # Verify migration result
        migrated = coordinator._data[const.DATA_CHORES][test_chore_id]

        # Should have per_assignee_applicable_days with copied values
        per_assignee = migrated.get(const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS, {})
        assert zoe_id in per_assignee, "Zoë should be in per_assignee_applicable_days"
        assert per_assignee[zoe_id] == [0, 1, 2], (
            "Zoë should get Mon-Wed from chore-level"
        )

        # Chore-level applicable_days should be cleared
        assert const.DATA_CHORE_APPLICABLE_DAYS not in migrated, (
            "Chore-level applicable_days should be removed after migration"
        )

    @pytest.mark.asyncio
    async def test_shared_chore_not_migrated(
        self, hass: HomeAssistant, scenario_shared: SetupResult
    ) -> None:
        """SHARED chores should NOT get per_assignee_applicable_days during migration."""
        coordinator = scenario_shared.coordinator

        # Find a SHARED chore
        shared_id = None
        for chore_id, chore_info in coordinator.chores_data.items():
            if chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA) in [
                const.COMPLETION_CRITERIA_SHARED,
                const.COMPLETION_CRITERIA_SHARED_FIRST,
            ]:
                shared_id = chore_id
                break

        assert shared_id is not None, "Need a SHARED chore to test"

        # Run migration
        migrator = PreV50Migrator(coordinator)
        migrator._migrate_per_assignee_applicable_days()

        # Verify SHARED chore unchanged
        chore_info = coordinator._data[const.DATA_CHORES][shared_id]
        per_assignee = chore_info.get(const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS)
        assert per_assignee is None or per_assignee == {}, (
            "SHARED chore should not get per_assignee_applicable_days during migration"
        )

    @pytest.mark.asyncio
    async def test_already_migrated_chore_preserved(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Chore with existing per_assignee_applicable_days is not modified."""
        coordinator = scenario_minimal.coordinator
        zoe_id = scenario_minimal.assignee_ids["Zoë"]

        # Create chore that already has per_assignee_applicable_days
        test_chore_id = "already-migrated-chore"
        existing_days = [4, 5]  # Fri, Sat
        chore = {
            const.DATA_CHORE_NAME: "Already Migrated",
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.DATA_CHORE_ASSIGNED_ASSIGNEES: [zoe_id],
            const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
            const.DATA_CHORE_ICON: "mdi:check",
            const.DATA_CHORE_DEFAULT_POINTS: 3.0,
            const.DATA_CHORE_INTERNAL_ID: test_chore_id,
            const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS: {
                zoe_id: existing_days,
            },
        }

        coordinator._data[const.DATA_CHORES][test_chore_id] = chore

        # Run migration
        migrator = PreV50Migrator(coordinator)
        migrator._migrate_per_assignee_applicable_days()

        # Verify existing data preserved
        result = coordinator._data[const.DATA_CHORES][test_chore_id]
        per_assignee = result.get(const.DATA_CHORE_PER_ASSIGNEE_APPLICABLE_DAYS, {})
        assert per_assignee.get(zoe_id) == existing_days, (
            "Migration should not overwrite existing per_assignee_applicable_days"
        )
