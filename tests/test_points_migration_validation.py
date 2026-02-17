"""Test points data migration and sensor attribute validation.

This module validates:
1. v40beta1 → v43 migration transforms point_data to point_periods correctly
2. Kid _points sensor exposes all required attributes
3. Sensor attributes update correctly on manual point adjustments
4. Earned/spent/net relationships and by_source tracking

Strategy:
- Migration tests: Place old storage file, setup integration, verify transformed structure
- Sensor tests: Use existing scenario fixtures (scenario_minimal) which are already migrated
"""

# pylint: disable=redefined-outer-name  # Pytest fixture pattern

import json
from pathlib import Path
from typing import Any

from homeassistant.core import Context, HomeAssistant
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,  # type: ignore[import-untyped]
)

from tests.helpers import (
    CONF_POINTS_ICON,
    CONF_POINTS_LABEL,
    CONF_UPDATE_INTERVAL,
    DOMAIN,
    SetupResult,
    get_dashboard_helper,
    get_kid_points,
)
from tests.helpers.setup import setup_from_yaml

STORAGE_KEY_SCOPED = "choreops/choreops_data"

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario: 1 kid (zoe), 1 parent."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def verify_points_sensor_attributes_complete(
    hass: HomeAssistant,
    kid_slug: str,
    expected_values: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify _points sensor has all required attributes with optional value checks.

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug
        expected_values: Optional dict of attribute names → expected values

    Returns:
        Dict of all attributes for further validation

    Raises:
        AssertionError: If any required attribute is missing or value mismatches
    """
    dashboard = get_dashboard_helper(hass, kid_slug)
    core_sensors = dashboard.get("core_sensors", {})
    points_eid = core_sensors.get("points_eid")
    assert points_eid is not None, (
        f"points_eid not found in dashboard helper for {kid_slug}"
    )

    points_sensor = hass.states.get(points_eid)
    assert points_sensor is not None, f"Points sensor not found: {points_eid}"

    attrs = points_sensor.attributes

    # Define all required attributes (grouped for clarity)
    # NOTE: Temporal attributes use "week/month/year" NOT "this_week/this_month/this_year"
    REQUIRED_ATTRS = {
        # All-time persistent
        "point_stat_points_earned_all_time",
        "point_stat_points_spent_all_time",
        "point_stat_points_net_all_time",
        "point_stat_points_by_source_all_time",
        "point_stat_highest_balance_all_time",
        # Today
        "point_stat_points_earned_today",
        "point_stat_points_spent_today",
        "point_stat_points_net_today",
        "point_stat_points_by_source_today",
        # Week (NO "this_" prefix)
        "point_stat_points_earned_week",
        "point_stat_points_spent_week",
        "point_stat_points_net_week",
        "point_stat_points_by_source_week",
        # Month (NO "this_" prefix)
        "point_stat_points_earned_month",
        "point_stat_points_spent_month",
        "point_stat_points_net_month",
        "point_stat_points_by_source_month",
        # Year (NO "this_" prefix)
        "point_stat_points_earned_year",
        "point_stat_points_spent_year",
        "point_stat_points_net_year",
        "point_stat_points_by_source_year",
        # Averages
        "point_stat_avg_points_per_day_week",
        "point_stat_avg_points_per_day_month",
    }

    # Check all required attributes exist
    missing = REQUIRED_ATTRS - set(attrs.keys())
    assert not missing, f"Missing required attributes: {sorted(missing)}"

    # Verify expected values if provided
    if expected_values:
        for attr_name, expected_value in expected_values.items():
            actual_value = attrs.get(attr_name)
            assert actual_value == expected_value, (
                f"Attribute '{attr_name}' mismatch: "
                f"expected {expected_value}, got {actual_value}"
            )

    return attrs


def verify_by_source_structure(by_source: dict[str, float] | str) -> None:
    """Verify by_source dict has expected structure.

    Args:
        by_source: Dictionary mapping source names to point values, or empty string

    Raises:
        AssertionError: If structure is incorrect
    """
    # Empty by_source shows as empty string in attributes
    if by_source == "":
        return

    # All source keys should be from expected set (may not all be present)
    EXPECTED_SOURCES = {"chores", "rewards", "bonuses", "penalties", "other", "manual"}
    assert set(by_source.keys()).issubset(EXPECTED_SOURCES), (
        f"by_source has unexpected keys. "
        f"Expected subset of {EXPECTED_SOURCES}, got {set(by_source.keys())}"
    )
    # All values should be floats
    for source, value in by_source.items():
        assert isinstance(value, (int, float)), (
            f"by_source['{source}'] should be numeric, got {type(value)}"
        )


def find_adjust_button(dashboard: dict[str, Any], value: int) -> dict[str, Any] | None:
    """Find manual adjustment button by value.

    Args:
        dashboard: Dashboard helper sensor attributes
        value: Adjustment value to find (e.g., 5 for +5, -3 for -3)

    Returns:
        Button dict with 'eid' and 'name', or None if not found
    """
    points_buttons = dashboard.get("points_buttons", [])
    # Button names like "Points +5.0" or "Points -3.0"
    target_name = f"Points {'+' if value > 0 else ''}{float(value)}"
    return next(
        (btn for btn in points_buttons if target_name in btn.get("name", "")), None
    )


# =============================================================================
# MIGRATION STRUCTURE VALIDATION
# =============================================================================


class TestPointsMigrationFromV40:
    """Verify v40beta1 → v43 migration transforms points data correctly."""

    async def test_migration_creates_point_periods_structure(
        self,
        hass: HomeAssistant,
        hass_storage: dict[str, Any],
    ) -> None:
        """Verify migration creates v43 point_periods flat structure."""
        # Load v40beta1 sample (has nested point_data.periods structure)
        sample_path = (
            Path(__file__).parent / "migration_samples" / "kidschores_data_40beta1"
        )
        v40beta1_data = json.loads(sample_path.read_text())

        # Pre-load v40beta1 data into storage (pytest-homeassistant mocks this)
        hass_storage["kidschores_data"] = v40beta1_data

        # Setup integration (triggers migration during coordinator init)
        # Use v40 schema version so migration runs
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="KidsChores",
            data={"schema_version": 40},  # v40 to trigger migration
            options={
                CONF_POINTS_LABEL: "Points",
                CONF_POINTS_ICON: "mdi:star",
                CONF_UPDATE_INTERVAL: 5,
            },
        )
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify migration transformed structure
        migrated_data = hass_storage[STORAGE_KEY_SCOPED]["data"]
        kids = migrated_data["kids"]

        for kid_id, kid_data in kids.items():
            # Verify new v43 structure exists
            assert "points" in kid_data, f"Kid {kid_id} missing 'points'"
            assert "point_periods" in kid_data, f"Kid {kid_id} missing 'point_periods'"

            # Verify point_periods is flat structure (not nested)
            point_periods = kid_data["point_periods"]
            assert isinstance(point_periods, dict), (
                "point_periods should be dict at top level"
            )

            # Verify all_time bucket always exists (migration creates this)
            assert "all_time" in point_periods, "Missing 'all_time' bucket"

            # Verify all_time has the all_time entry (not periods wrapper)
            all_time_bucket = point_periods["all_time"]
            assert "all_time" in all_time_bucket, "Missing 'all_time' entry"

            # Verify all_time entry has v43 fields
            all_time_entry = all_time_bucket["all_time"]
            assert "points_earned" in all_time_entry, (
                "Missing 'points_earned' in all_time"
            )
            assert "points_spent" in all_time_entry, (
                "Missing 'points_spent' in all_time"
            )
            assert "highest_balance" in all_time_entry, (
                "Missing 'highest_balance' in all_time"
            )
            assert "by_source" in all_time_entry, "Missing 'by_source' in all_time"

            # Verify period-specific buckets exist if they were in v40 data
            # (not all kids will have all period types - some may only have yearly data)
            for bucket_name in ["yearly", "monthly", "weekly", "daily"]:
                if bucket_name in point_periods:
                    bucket_data = point_periods[bucket_name]
                    assert isinstance(bucket_data, dict), (
                        f"{bucket_name} bucket should be dict"
                    )

            # Verify old v42 structure is gone
            assert "point_data" not in kid_data, (
                f"Kid {kid_id} still has old 'point_data' structure"
            )

    async def test_migration_preserves_historical_data(
        self,
        hass: HomeAssistant,
        hass_storage: dict[str, Any],
    ) -> None:
        """Verify migration preserves monthly/yearly historical periods."""
        # Load v40beta1 sample
        sample_path = (
            Path(__file__).parent / "migration_samples" / "kidschores_data_40beta1"
        )
        v40beta1_data = json.loads(sample_path.read_text())

        # Pre-load into hass_storage
        hass_storage["kidschores_data"] = v40beta1_data

        # Count historical periods in original data
        original_kids = v40beta1_data["data"]["kids"]
        first_kid_id = next(iter(original_kids.keys()))
        original_kid = original_kids[first_kid_id]
        original_monthly_count = len(
            original_kid.get("point_data", {})
            .get("periods", {})
            .get("monthly", {})
            .keys()
        )

        # Setup integration (triggers migration)
        # Use v40 schema version so migration runs
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="KidsChores",
            data={"schema_version": 40},  # v40 to trigger migration
            options={
                CONF_POINTS_LABEL: "Points",
                CONF_POINTS_ICON: "mdi:star",
                CONF_UPDATE_INTERVAL: 5,
            },
        )
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify historical periods preserved
        migrated_data = hass_storage[STORAGE_KEY_SCOPED]["data"]
        migrated_kid = migrated_data["kids"][first_kid_id]
        migrated_monthly = migrated_kid["point_periods"].get("monthly", {})

        # Should have same number of monthly periods
        assert len(migrated_monthly.keys()) == original_monthly_count, (
            f"Monthly period count mismatch: "
            f"original {original_monthly_count}, migrated {len(migrated_monthly.keys())}"
        )

        # Verify each monthly period has v43 structure
        for period_key, period_data in migrated_monthly.items():
            assert "points_earned" in period_data, (
                f"Monthly period {period_key} missing 'points_earned'"
            )
            assert "points_spent" in period_data, (
                f"Monthly period {period_key} missing 'points_spent'"
            )
            assert "by_source" in period_data, (
                f"Monthly period {period_key} missing 'by_source'"
            )

    async def test_migration_calculates_all_time_correctly(
        self,
        hass: HomeAssistant,
        hass_storage: dict[str, Any],
    ) -> None:
        """Verify all_time earned/spent calculated correctly from v42 data."""
        # Load v40beta1 sample
        sample_path = (
            Path(__file__).parent / "migration_samples" / "kidschores_data_40beta1"
        )
        v40beta1_data = json.loads(sample_path.read_text())

        # Pre-load into hass_storage
        hass_storage["kidschores_data"] = v40beta1_data

        # Get original values for comparison
        original_kids = v40beta1_data["data"]["kids"]
        first_kid_id = next(iter(original_kids.keys()))
        original_kid = original_kids[first_kid_id]
        original_balance = original_kid.get("points", 0.0)

        # Setup integration (triggers migration)
        # Use v40 schema version so migration runs
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            title="KidsChores",
            data={"schema_version": 40},  # v40 to trigger migration
            options={
                CONF_POINTS_LABEL: "Points",
                CONF_POINTS_ICON: "mdi:star",
                CONF_UPDATE_INTERVAL: 5,
            },
        )
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify all_time calculation
        migrated_data = hass_storage[STORAGE_KEY_SCOPED]["data"]
        migrated_kid = migrated_data["kids"][first_kid_id]
        all_time_entry = migrated_kid["point_periods"]["all_time"]["all_time"]

        earned = all_time_entry["points_earned"]
        spent = all_time_entry["points_spent"]
        highest_balance = all_time_entry["highest_balance"]

        # Verify all_time logic: earned = highest_balance
        assert earned == highest_balance, (
            f"all_time earned should equal highest_balance: "
            f"earned={earned}, highest={highest_balance}"
        )

        # Verify spent = current_balance - highest_balance
        expected_spent = original_balance - highest_balance
        assert spent == expected_spent, (
            f"all_time spent incorrect: expected {expected_spent}, got {spent}"
        )

        # Verify earned + spent = current_balance (net relationship)
        assert earned + spent == original_balance, (
            f"Net relationship broken: "
            f"earned({earned}) + spent({spent}) != balance({original_balance})"
        )


# =============================================================================
# SENSOR ATTRIBUTE VALIDATION
# =============================================================================


class TestPointsSensorAttributes:
    """Verify _points sensor attributes using scenario fixtures."""

    async def test_all_attributes_exist(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Verify ALL 26+ sensor attributes exist."""
        # scenario_minimal has kid "zoe" already setup
        attrs = verify_points_sensor_attributes_complete(hass, "zoe")

        # Verify structure of by_source dicts
        verify_by_source_structure(attrs["point_stat_points_by_source_all_time"])
        verify_by_source_structure(attrs["point_stat_points_by_source_today"])
        verify_by_source_structure(attrs["point_stat_points_by_source_week"])
        verify_by_source_structure(attrs["point_stat_points_by_source_month"])
        verify_by_source_structure(attrs["point_stat_points_by_source_year"])

    async def test_net_values_are_derived(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Verify net values are always earned + spent (derived, not stored)."""
        # Get all attributes
        attrs = verify_points_sensor_attributes_complete(hass, "zoe")

        # Verify net = earned + spent for all periods
        assert attrs["point_stat_points_net_all_time"] == round(
            attrs["point_stat_points_earned_all_time"]
            + attrs["point_stat_points_spent_all_time"],
            2,
        ), "all_time net != earned + spent"

        assert attrs["point_stat_points_net_today"] == round(
            attrs["point_stat_points_earned_today"]
            + attrs["point_stat_points_spent_today"],
            2,
        ), "today net != earned + spent"

        assert attrs["point_stat_points_net_week"] == round(
            attrs["point_stat_points_earned_week"]
            + attrs["point_stat_points_spent_week"],
            2,
        ), "week net != earned + spent"

        assert attrs["point_stat_points_net_month"] == round(
            attrs["point_stat_points_earned_month"]
            + attrs["point_stat_points_spent_month"],
            2,
        ), "month net != earned + spent"

        assert attrs["point_stat_points_net_year"] == round(
            attrs["point_stat_points_earned_year"]
            + attrs["point_stat_points_spent_year"],
            2,
        ), "year net != earned + spent"


# =============================================================================
# MANUAL ADJUSTMENT VALIDATION
# =============================================================================


class TestPointsSensorUpdatesOnManualAdjustment:
    """Verify _points sensor updates correctly when manual points added/removed."""

    async def test_plus_ten_updates_all_earned_attributes(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Verify +10 manual adjustment updates all earned attributes."""
        # Get initial state
        initial_attrs = verify_points_sensor_attributes_complete(hass, "zoe")
        initial_balance = get_kid_points(hass, "zoe")

        # Press +10 button with parent context
        dashboard = get_dashboard_helper(hass, "zoe")
        plus_10_btn = find_adjust_button(dashboard, 10)
        assert plus_10_btn is not None, "No +10 adjustment button found"

        parent_context = Context(user_id=mock_hass_users["parent1"].id)
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": plus_10_btn["eid"]},
            blocking=True,
            context=parent_context,
        )

        # Get updated state
        new_attrs = verify_points_sensor_attributes_complete(hass, "zoe")
        new_balance = get_kid_points(hass, "zoe")

        # Verify balance increased
        assert new_balance == initial_balance + 10.0

        # Verify ALL earned values increased by 10.0
        assert new_attrs["point_stat_points_earned_all_time"] == (
            initial_attrs["point_stat_points_earned_all_time"] + 10.0
        )
        assert new_attrs["point_stat_points_earned_today"] == (
            initial_attrs["point_stat_points_earned_today"] + 10.0
        )
        assert new_attrs["point_stat_points_earned_week"] == (
            initial_attrs["point_stat_points_earned_week"] + 10.0
        )
        assert new_attrs["point_stat_points_earned_month"] == (
            initial_attrs["point_stat_points_earned_month"] + 10.0
        )
        assert new_attrs["point_stat_points_earned_year"] == (
            initial_attrs["point_stat_points_earned_year"] + 10.0
        )

        # Verify spent UNCHANGED (deposit doesn't affect spent)
        assert (
            new_attrs["point_stat_points_spent_all_time"]
            == (initial_attrs["point_stat_points_spent_all_time"])
        )
        assert (
            new_attrs["point_stat_points_spent_today"]
            == (initial_attrs["point_stat_points_spent_today"])
        )

    async def test_plus_two_updates_all_net_attributes(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Verify +2 manual adjustment updates all net attributes."""
        # Get initial state
        initial_attrs = verify_points_sensor_attributes_complete(hass, "zoe")

        # Press +2 button
        dashboard = get_dashboard_helper(hass, "zoe")
        plus_2_btn = find_adjust_button(dashboard, 2)
        assert plus_2_btn is not None

        parent_context = Context(user_id=mock_hass_users["parent1"].id)
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": plus_2_btn["eid"]},
            blocking=True,
            context=parent_context,
        )

        # Get updated state
        new_attrs = verify_points_sensor_attributes_complete(hass, "zoe")

        # Verify ALL net values increased by 2.0 (deposit = positive)
        assert new_attrs["point_stat_points_net_all_time"] == (
            initial_attrs["point_stat_points_net_all_time"] + 2.0
        )
        assert new_attrs["point_stat_points_net_today"] == (
            initial_attrs["point_stat_points_net_today"] + 2.0
        )
        assert new_attrs["point_stat_points_net_week"] == (
            initial_attrs["point_stat_points_net_week"] + 2.0
        )
        assert new_attrs["point_stat_points_net_month"] == (
            initial_attrs["point_stat_points_net_month"] + 2.0
        )
        assert new_attrs["point_stat_points_net_year"] == (
            initial_attrs["point_stat_points_net_year"] + 2.0
        )

    async def test_plus_two_updates_by_source_other(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Verify +2 manual adjustment tracked in 'manual' source."""
        # Get initial state
        initial_attrs = verify_points_sensor_attributes_complete(hass, "zoe")

        # Press +2 button
        dashboard = get_dashboard_helper(hass, "zoe")
        plus_2_btn = find_adjust_button(dashboard, 2)
        assert plus_2_btn is not None

        parent_context = Context(user_id=mock_hass_users["parent1"].id)
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": plus_2_btn["eid"]},
            blocking=True,
            context=parent_context,
        )

        # Get updated state
        new_attrs = verify_points_sensor_attributes_complete(hass, "zoe")

        # Verify by_source["manual"] increased by 2.0 for all periods
        # (Manual adjustments use 'manual' source, not 'other')
        assert new_attrs["point_stat_points_by_source_all_time"]["manual"] == 2.0
        assert new_attrs["point_stat_points_by_source_today"]["manual"] == 2.0
        assert new_attrs["point_stat_points_by_source_week"]["manual"] == 2.0
        assert new_attrs["point_stat_points_by_source_month"]["manual"] == 2.0
        assert new_attrs["point_stat_points_by_source_year"]["manual"] == 2.0

        # Verify other sources DON'T exist (not populated until used)
        for source in ["chores", "rewards", "bonuses", "penalties", "other"]:
            assert source not in new_attrs["point_stat_points_by_source_all_time"], (
                f"Source '{source}' should not exist when unused"
            )

    async def test_plus_ten_updates_highest_balance(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Verify highest_balance updates when new balance exceeds it."""
        # Get initial state
        initial_attrs = verify_points_sensor_attributes_complete(hass, "zoe")
        initial_balance = get_kid_points(hass, "zoe")

        # Press +10 button
        dashboard = get_dashboard_helper(hass, "zoe")
        plus_10_btn = find_adjust_button(dashboard, 10)
        assert plus_10_btn is not None

        parent_context = Context(user_id=mock_hass_users["parent1"].id)
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": plus_10_btn["eid"]},
            blocking=True,
            context=parent_context,
        )

        # Get updated state
        new_attrs = verify_points_sensor_attributes_complete(hass, "zoe")
        new_balance = get_kid_points(hass, "zoe")

        # Verify highest_balance updated if new balance is higher
        expected_highest = max(
            initial_attrs["point_stat_highest_balance_all_time"], new_balance
        )
        assert new_attrs["point_stat_highest_balance_all_time"] == expected_highest, (
            f"highest_balance should be {expected_highest}"
        )

    async def test_minus_two_updates_spent_not_earned(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Verify -2 manual adjustment increases spent, not earned."""
        # Get initial state
        initial_attrs = verify_points_sensor_attributes_complete(hass, "zoe")
        initial_balance = get_kid_points(hass, "zoe")

        # Press -2 button with parent context
        dashboard = get_dashboard_helper(hass, "zoe")
        minus_2_btn = find_adjust_button(dashboard, -2)
        assert minus_2_btn is not None, "No -2 adjustment button found"

        parent_context = Context(user_id=mock_hass_users["parent1"].id)
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": minus_2_btn["eid"]},
            blocking=True,
            context=parent_context,
        )

        # Get updated state
        new_attrs = verify_points_sensor_attributes_complete(hass, "zoe")
        new_balance = get_kid_points(hass, "zoe")

        # Verify balance decreased
        assert new_balance == initial_balance - 2.0

        # Verify earned UNCHANGED (withdrawals don't affect earned)
        assert (
            new_attrs["point_stat_points_earned_all_time"]
            == (initial_attrs["point_stat_points_earned_all_time"])
        )
        assert (
            new_attrs["point_stat_points_earned_today"]
            == (initial_attrs["point_stat_points_earned_today"])
        )

        # Verify spent INCREASED by 2.0 (withdrawal = negative, stored as negative)
        assert new_attrs["point_stat_points_spent_all_time"] == (
            initial_attrs["point_stat_points_spent_all_time"] - 2.0
        )
        assert new_attrs["point_stat_points_spent_today"] == (
            initial_attrs["point_stat_points_spent_today"] - 2.0
        )

        # Verify net DECREASED by 2.0
        assert new_attrs["point_stat_points_net_all_time"] == (
            initial_attrs["point_stat_points_net_all_time"] - 2.0
        )
        assert new_attrs["point_stat_points_net_today"] == (
            initial_attrs["point_stat_points_net_today"] - 2.0
        )

    async def test_multiple_adjustments_cumulative(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Verify multiple adjustments (+2, +10, -2) cumulate correctly."""
        # Get initial state
        initial_attrs = verify_points_sensor_attributes_complete(hass, "zoe")
        initial_balance = get_kid_points(hass, "zoe")

        dashboard = get_dashboard_helper(hass, "zoe")
        parent_context = Context(user_id=mock_hass_users["parent1"].id)

        # Press +2
        plus_2_btn = find_adjust_button(dashboard, 2)
        assert plus_2_btn is not None
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": plus_2_btn["eid"]},
            blocking=True,
            context=parent_context,
        )

        # Press +10
        plus_10_btn = find_adjust_button(dashboard, 10)
        assert plus_10_btn is not None
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": plus_10_btn["eid"]},
            blocking=True,
            context=parent_context,
        )

        # Press -2
        minus_2_btn = find_adjust_button(dashboard, -2)
        assert minus_2_btn is not None
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": minus_2_btn["eid"]},
            blocking=True,
            context=parent_context,
        )

        # Get final state
        final_attrs = verify_points_sensor_attributes_complete(hass, "zoe")
        final_balance = get_kid_points(hass, "zoe")

        # Verify balance: +2 +10 -2 = +10
        assert final_balance == initial_balance + 10.0

        # Verify earned: +2 +10 = +12 (withdrawal doesn't affect earned)
        assert final_attrs["point_stat_points_earned_all_time"] == (
            initial_attrs["point_stat_points_earned_all_time"] + 12.0
        )

        # Verify spent: -2 only
        assert final_attrs["point_stat_points_spent_all_time"] == (
            initial_attrs["point_stat_points_spent_all_time"] - 2.0
        )

        # Verify net: +2 +10 -2 = +10
        assert final_attrs["point_stat_points_net_all_time"] == (
            initial_attrs["point_stat_points_net_all_time"] + 10.0
        )
