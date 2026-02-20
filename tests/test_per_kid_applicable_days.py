"""Tests for PKAD-2026-001: Per-Kid Applicable Days feature.

This module tests the per-kid applicable days functionality that allows
INDEPENDENT chores to have different weekday schedules per kid.

Test Organization:
- TestPerKidValidation: Unit tests for validation functions
- TestPerKidDashboardDisplay: Verifies per-kid days appear correctly in dashboard
- TestPerKidMigration: Migration from pre-v50 chore format
- TestPerKidDataIntegrity: Ensures SHARED chores don't get per-kid data

Scenarios Used:
- scenario_minimal: 1 kid (Zoë), 1 parent
- scenario_shared: 3 kids (Zoë, Max!, Lila), 1 parent, shared chores
- scenario_per_kid: INDEPENDENT chore with per-kid days (Zoë=Mon/Wed, Max=Tue/Thu)
"""

# pylint: disable=redefined-outer-name

from typing import Any

from homeassistant.core import HomeAssistant
import pytest

from custom_components.choreops import const
from custom_components.choreops.coordinator import KidsChoresDataCoordinator
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
    """Load minimal scenario: 1 kid, 1 parent, 5 chores."""
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
    """Load shared scenario: 3 kids, 1 parent, 8 shared chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_shared.yaml",
    )


@pytest.fixture
async def scenario_per_kid(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Setup per-kid applicable days by injecting data into scenario_shared.

    Creates an INDEPENDENT chore with different schedules per kid:
    - Zoë: Mon, Wed (days 0, 2)
    - Max!: Tue, Thu (days 1, 3)

    This validates that kids see different applicable days for the same chore.
    """
    result = await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_shared.yaml",
    )
    coordinator = result.coordinator

    zoe_id = result.kid_ids.get("Zoë")
    max_id = result.kid_ids.get("Max!")

    if not zoe_id or not max_id:
        for kid_id, kid_info in coordinator.kids_data.items():
            name = kid_info.get(const.DATA_KID_NAME, "")
            if "Zo" in name or "zoe" in name.lower():
                zoe_id = kid_id
            elif "Max" in name:
                max_id = kid_id

    chores_data = coordinator._data.get(const.DATA_CHORES, {})
    modified = False

    for chore_info in chores_data.values():
        assigned_kids = chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, [])
        if (
            len(assigned_kids) >= 2
            and zoe_id in assigned_kids
            and max_id in assigned_kids
        ):
            if not modified:
                chore_info[const.DATA_CHORE_COMPLETION_CRITERIA] = (
                    const.COMPLETION_CRITERIA_INDEPENDENT
                )
                # CRITICAL: Use string format to match real UI flow data
                # UI selector returns ["mon", "wed"], NOT [0, 2]
                chore_info[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = {
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


def find_independent_chore_with_per_kid_days(
    coordinator: KidsChoresDataCoordinator,
) -> tuple[str, dict[str, Any]]:
    """Find an INDEPENDENT chore that has per_kid_applicable_days set."""
    for chore_id, chore_info in coordinator.chores_data.items():
        criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
        per_kid_days = chore_info.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
        if criteria == const.COMPLETION_CRITERIA_INDEPENDENT and per_kid_days:
            return chore_id, chore_info
    raise ValueError("No INDEPENDENT chore with per_kid_applicable_days found")


def find_shared_chore(
    coordinator: KidsChoresDataCoordinator,
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


class TestPerKidValidation:
    """Unit tests for per_kid_applicable_days validation functions.

    These test the validation logic in flow_helpers.py that runs during
    config flow to ensure user input is valid before saving.
    """

    def test_valid_weekday_list_accepted(self) -> None:
        """Valid weekday numbers [0-6] pass validation."""
        per_kid_days = {"kid-uuid-1": [0, 2, 4]}  # Mon, Wed, Fri

        is_valid, error_key = fh.validate_per_kid_applicable_days(per_kid_days)

        assert is_valid is True
        assert error_key is None

    def test_empty_dict_uses_chore_level_days(self) -> None:
        """Empty per_kid_days dict means use chore-level applicable_days."""
        per_kid_days: dict[str, list[int]] = {}

        is_valid, error_key = fh.validate_per_kid_applicable_days(per_kid_days)

        assert is_valid is True, "Empty dict should be valid (use chore-level days)"

    def test_empty_list_means_all_days_applicable(self) -> None:
        """Empty list for a kid means all 7 days are applicable."""
        per_kid_days: dict[str, list[int]] = {"kid-uuid-1": []}

        is_valid, error_key = fh.validate_per_kid_applicable_days(per_kid_days)

        assert is_valid is True, "Empty list should be valid (all days)"

    def test_day_value_above_6_rejected(self) -> None:
        """Day value 7 or higher is invalid (only 0-6 for Mon-Sun)."""
        per_kid_days = {"kid-uuid-1": [7]}

        is_valid, error_key = fh.validate_per_kid_applicable_days(per_kid_days)

        assert is_valid is False
        assert error_key == const.TRANS_KEY_CFOF_ERROR_PER_KID_APPLICABLE_DAYS_INVALID

    def test_negative_day_value_rejected(self) -> None:
        """Negative day values are invalid."""
        per_kid_days = {"kid-uuid-1": [-1]}

        is_valid, error_key = fh.validate_per_kid_applicable_days(per_kid_days)

        assert is_valid is False
        assert error_key == const.TRANS_KEY_CFOF_ERROR_PER_KID_APPLICABLE_DAYS_INVALID

    def test_duplicate_days_rejected(self) -> None:
        """Duplicate day values in list are invalid."""
        per_kid_days = {"kid-uuid-1": [0, 0, 1]}  # Monday listed twice

        is_valid, error_key = fh.validate_per_kid_applicable_days(per_kid_days)

        assert is_valid is False
        assert error_key == const.TRANS_KEY_CFOF_ERROR_PER_KID_APPLICABLE_DAYS_INVALID

    def test_all_seven_days_valid(self) -> None:
        """Full week selection [0,1,2,3,4,5,6] is valid."""
        per_kid_days = {"kid-uuid-1": [0, 1, 2, 3, 4, 5, 6]}

        is_valid, error_key = fh.validate_per_kid_applicable_days(per_kid_days)

        assert is_valid is True

    def test_unsorted_days_valid(self) -> None:
        """Days don't need to be sorted - [6, 0, 3] is valid."""
        per_kid_days = {"kid-uuid-1": [6, 0, 3]}  # Sun, Mon, Thu

        is_valid, error_key = fh.validate_per_kid_applicable_days(per_kid_days)

        assert is_valid is True

    def test_daily_multi_times_valid_format(self) -> None:
        """Valid time format for DAILY_MULTI passes validation."""
        per_kid_times = {"kid-uuid-1": "08:00|17:00"}

        is_valid, error_key = fh.validate_per_kid_daily_multi_times(
            per_kid_times, const.FREQUENCY_DAILY_MULTI
        )

        assert is_valid is True
        assert error_key is None

    def test_daily_multi_times_skipped_for_other_frequencies(self) -> None:
        """Validation is skipped for non-DAILY_MULTI frequencies."""
        per_kid_times = {"kid-uuid-1": "invalid-format"}

        # Using DAILY (not DAILY_MULTI), so validation should skip
        is_valid, error_key = fh.validate_per_kid_daily_multi_times(
            per_kid_times, const.FREQUENCY_DAILY
        )

        assert is_valid is True, "Non-DAILY_MULTI should skip validation"


# =============================================================================
# DASHBOARD DISPLAY TESTS
# =============================================================================


class TestPerKidDashboardDisplay:
    """Tests that per-kid applicable days appear correctly in dashboard helper.

    The dashboard helper sensor provides chore data to the frontend, including
    the formatted 'assigned_days' string and 'assigned_days_raw' list.
    These tests verify that INDEPENDENT chores show kid-specific days.
    """

    @pytest.mark.asyncio
    async def test_dashboard_shows_different_days_per_kid(
        self, hass: HomeAssistant, scenario_per_kid: SetupResult
    ) -> None:
        """Zoë and Max see different assigned_days for the same chore."""
        coordinator = scenario_per_kid.coordinator
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

        # Find the INDEPENDENT chore with per-kid days
        chore_id, chore_info = find_independent_chore_with_per_kid_days(coordinator)
        chore_name = chore_info.get(const.DATA_CHORE_NAME, "")

        # Find this chore in each kid's dashboard by name
        zoe_chore = next((c for c in zoe_chores if c.get("name") == chore_name), None)
        max_chore = next((c for c in max_chores if c.get("name") == chore_name), None)

        # Both kids should have this chore
        assert zoe_chore is not None, "Zoë should have the per-kid chore"
        assert max_chore is not None, "Max should have the per-kid chore"

        # They should have DIFFERENT assigned_days_raw
        zoe_days_raw = zoe_chore.get("assigned_days_raw", [])
        max_days_raw = max_chore.get("assigned_days_raw", [])

        # Per fixture: Zoë=["mon","wed"], Max=["tue","thu"] (strings, not integers)
        assert set(zoe_days_raw).isdisjoint(set(max_days_raw)), (
            f"Kids should have non-overlapping days: Zoë={zoe_days_raw}, Max={max_days_raw}"
        )


# =============================================================================
# DATA INTEGRITY TESTS
# =============================================================================


class TestPerKidDataIntegrity:
    """Tests that per_kid_applicable_days is only used for INDEPENDENT chores.

    SHARED and SHARED_FIRST chores must use chore-level applicable_days
    because all kids share the same schedule.
    """

    @pytest.mark.asyncio
    async def test_shared_chores_have_no_per_kid_days(
        self, hass: HomeAssistant, scenario_per_kid: SetupResult
    ) -> None:
        """SHARED chores should NOT have per_kid_applicable_days."""
        coordinator = scenario_per_kid.coordinator

        chore_id, chore_info = find_shared_chore(coordinator)

        per_kid_days = chore_info.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS)
        assert per_kid_days is None or per_kid_days == {}, (
            f"SHARED chore '{chore_info.get(const.DATA_CHORE_NAME)}' "
            f"should not have per_kid_applicable_days, got: {per_kid_days}"
        )

    @pytest.mark.asyncio
    async def test_independent_chore_has_per_kid_structure(
        self, hass: HomeAssistant, scenario_per_kid: SetupResult
    ) -> None:
        """INDEPENDENT chores with multi-kid assignment should have per_kid data."""
        coordinator = scenario_per_kid.coordinator

        chore_id, chore_info = find_independent_chore_with_per_kid_days(coordinator)

        # Verify it's INDEPENDENT
        criteria = chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA)
        assert criteria == const.COMPLETION_CRITERIA_INDEPENDENT

        # Verify per_kid_applicable_days has entries
        per_kid_days = chore_info.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
        assert len(per_kid_days) >= 2, (
            "INDEPENDENT chore with multiple kids should have per_kid data for each"
        )

    @pytest.mark.asyncio
    async def test_per_kid_days_match_injected_values(
        self, hass: HomeAssistant, scenario_per_kid: SetupResult
    ) -> None:
        """Per-kid days match the fixture injection: Zoë=['mon','wed'], Max=['tue','thu']."""
        coordinator = scenario_per_kid.coordinator

        _, chore_info = find_independent_chore_with_per_kid_days(coordinator)
        per_kid_days = chore_info.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})

        zoe_id = scenario_per_kid.kid_ids.get("Zoë")
        max_id = scenario_per_kid.kid_ids.get("Max!")

        if zoe_id and zoe_id in per_kid_days:
            assert per_kid_days[zoe_id] == ["mon", "wed"], "Zoë should have Mon, Wed"

        if max_id and max_id in per_kid_days:
            assert per_kid_days[max_id] == ["tue", "thu"], "Max should have Tue, Thu"


# =============================================================================
# MIGRATION TESTS
# =============================================================================


class TestPerKidMigration:
    """Tests for PreV50Migrator migration of per_kid_applicable_days.

    Old INDEPENDENT chores had chore-level applicable_days. Migration copies
    these to per_kid_applicable_days for each assigned kid.
    """

    @pytest.mark.asyncio
    async def test_old_independent_chore_migrates_to_per_kid(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Pre-v50 INDEPENDENT chore gets per_kid_applicable_days populated."""
        coordinator = scenario_minimal.coordinator
        zoe_id = scenario_minimal.kid_ids["Zoë"]

        # Create old-style chore WITHOUT per_kid_applicable_days
        test_chore_id = "test-migration-chore"
        old_chore = {
            const.DATA_CHORE_NAME: "Migration Test Chore",
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.DATA_CHORE_ASSIGNED_KIDS: [zoe_id],
            const.DATA_CHORE_APPLICABLE_DAYS: [0, 1, 2],  # Mon-Wed at chore level
            const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
            const.DATA_CHORE_ICON: "mdi:test",
            const.DATA_CHORE_DEFAULT_POINTS: 5.0,
            const.DATA_CHORE_INTERNAL_ID: test_chore_id,
            # NO per_kid_applicable_days - pre-v50 format
        }

        coordinator._data[const.DATA_CHORES][test_chore_id] = old_chore

        # Run migration
        migrator = PreV50Migrator(coordinator)
        migrator._migrate_per_kid_applicable_days()

        # Verify migration result
        migrated = coordinator._data[const.DATA_CHORES][test_chore_id]

        # Should have per_kid_applicable_days with copied values
        per_kid = migrated.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
        assert zoe_id in per_kid, "Zoë should be in per_kid_applicable_days"
        assert per_kid[zoe_id] == [0, 1, 2], "Zoë should get Mon-Wed from chore-level"

        # Chore-level applicable_days should be cleared
        assert const.DATA_CHORE_APPLICABLE_DAYS not in migrated, (
            "Chore-level applicable_days should be removed after migration"
        )

    @pytest.mark.asyncio
    async def test_shared_chore_not_migrated(
        self, hass: HomeAssistant, scenario_shared: SetupResult
    ) -> None:
        """SHARED chores should NOT get per_kid_applicable_days during migration."""
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
        migrator._migrate_per_kid_applicable_days()

        # Verify SHARED chore unchanged
        chore_info = coordinator._data[const.DATA_CHORES][shared_id]
        per_kid = chore_info.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS)
        assert per_kid is None or per_kid == {}, (
            "SHARED chore should not get per_kid_applicable_days during migration"
        )

    @pytest.mark.asyncio
    async def test_already_migrated_chore_preserved(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Chore with existing per_kid_applicable_days is not modified."""
        coordinator = scenario_minimal.coordinator
        zoe_id = scenario_minimal.kid_ids["Zoë"]

        # Create chore that already has per_kid_applicable_days
        test_chore_id = "already-migrated-chore"
        existing_days = [4, 5]  # Fri, Sat
        chore = {
            const.DATA_CHORE_NAME: "Already Migrated",
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
            const.DATA_CHORE_ASSIGNED_KIDS: [zoe_id],
            const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
            const.DATA_CHORE_ICON: "mdi:check",
            const.DATA_CHORE_DEFAULT_POINTS: 3.0,
            const.DATA_CHORE_INTERNAL_ID: test_chore_id,
            const.DATA_CHORE_PER_KID_APPLICABLE_DAYS: {
                zoe_id: existing_days,
            },
        }

        coordinator._data[const.DATA_CHORES][test_chore_id] = chore

        # Run migration
        migrator = PreV50Migrator(coordinator)
        migrator._migrate_per_kid_applicable_days()

        # Verify existing data preserved
        result = coordinator._data[const.DATA_CHORES][test_chore_id]
        per_kid = result.get(const.DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
        assert per_kid.get(zoe_id) == existing_days, (
            "Migration should not overwrite existing per_kid_applicable_days"
        )
