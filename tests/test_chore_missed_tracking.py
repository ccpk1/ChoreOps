"""Test chore missed tracking (Phase 5).

Tests missed chore recording across:
- Automated miss recording on OVERDUE resets with CLEAR_AND_MARK_MISSED handling
- Manual miss recording via skip_chore_due_date service with mark_as_missed=True
- Period bucket writes (daily, weekly, monthly, yearly, all_time)
- Signal flow: ChoreManager -> StatisticsManager
- Notification delivery

Uses scenario_full.yaml (Stårblüm Family with both INDEPENDENT and SHARED chores).

See tests/AGENT_TEST_CREATION_INSTRUCTIONS.md for patterns used.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import patch

import pytest

from custom_components.choreops import const
from custom_components.choreops.utils.dt_utils import dt_now_local, dt_now_utc
from tests.helpers import (
    APPROVAL_RESET_AT_DUE_DATE_ONCE,
    CHORE_STATE_OVERDUE,
    CHORE_STATE_PENDING,
    DATA_CHORE_APPROVAL_RESET_TYPE,
    DATA_CHORE_ASSIGNED_KIDS,
    DATA_CHORE_OVERDUE_HANDLING_TYPE,
    DATA_CHORE_STATE,
    DATA_KID_CHORE_DATA,
    DATA_KID_CHORE_DATA_LAST_MISSED,
    DATA_KID_CHORE_DATA_PERIOD_MISSED,
    DATA_KID_CHORE_DATA_PERIODS,
    DATA_KID_CHORE_DATA_PERIODS_DAILY,
    DATA_KID_CHORE_DATA_PERIODS_MONTHLY,
    DATA_KID_CHORE_DATA_PERIODS_WEEKLY,
    DATA_KID_CHORE_DATA_PERIODS_YEARLY,
    DATA_KID_CHORE_PERIODS,
    DOMAIN,
    OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AND_MARK_MISSED,
    SERVICE_SKIP_CHORE_DUE_DATE,
    SIGNAL_SUFFIX_CHORE_MISSED,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
async def setup_missed_tracking_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Set up scenario with both INDEPENDENT and SHARED chores for missed tracking tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_kid_by_name(result: SetupResult, kid_name: str) -> dict[str, Any] | None:
    """Get kid dict by name from SetupResult.

    Returns a dict with internal_id key matching the kid.
    """
    kid_id = result.kid_ids.get(kid_name)
    if not kid_id:
        return None
    return {"internal_id": kid_id, "name": kid_name}


def get_chore_by_name(result: SetupResult, chore_name: str) -> dict[str, Any] | None:
    """Get chore dict by name from SetupResult.

    Returns a dict with internal_id key matching the chore.
    """
    chore_id = result.chore_ids.get(chore_name)
    if not chore_id:
        return None
    return {"internal_id": chore_id, "name": chore_name}


def get_kid_chore_last_missed(
    coordinator: Any, kid_id: str, chore_id: str
) -> str | None:
    """Get last_missed timestamp for a kid's chore."""
    kid_info = coordinator.kids_data.get(kid_id, {})
    chore_data = kid_info.get(DATA_KID_CHORE_DATA, {})
    kid_chore_data = chore_data.get(chore_id, {})
    return kid_chore_data.get(DATA_KID_CHORE_DATA_LAST_MISSED)


def get_missed_count_from_period(
    coordinator: Any,
    kid_id: str,
    chore_id: str,
    period_type: str,
    period_key: str,
) -> int:
    """Get missed count from a specific period bucket.

    Args:
        coordinator: The coordinator instance
        kid_id: Kid's internal ID
        chore_id: Chore's internal ID
        period_type: Period type constant (DATA_KID_CHORE_DATA_PERIODS_DAILY, etc.)
        period_key: Period key (e.g., "2026-02-09" for daily)

    Returns:
        Missed count from the specified bucket, or 0 if not found
    """
    kid_info = coordinator.kids_data.get(kid_id, {})
    chore_data = kid_info.get(DATA_KID_CHORE_DATA, {})
    kid_chore_data = chore_data.get(chore_id, {})
    periods = kid_chore_data.get(DATA_KID_CHORE_DATA_PERIODS, {})
    period_buckets = periods.get(period_type, {})
    bucket = period_buckets.get(period_key, {})
    return bucket.get(DATA_KID_CHORE_DATA_PERIOD_MISSED, 0)


def get_kid_level_missed_count(
    coordinator: Any,
    kid_id: str,
    period_type: str,
    period_key: str,
) -> int:
    """Get missed count from kid-level chore_periods bucket (aggregated across all chores).

    Args:
        coordinator: The coordinator instance
        kid_id: Kid's internal ID
        period_type: Period type constant (DATA_KID_CHORE_DATA_PERIODS_DAILY, etc.)
        period_key: Period key (e.g., "2026-02-09" for daily)

    Returns:
        Missed count from kid-level bucket, or 0 if not found
    """
    kid_info = coordinator.kids_data.get(kid_id, {})
    kid_chore_periods = kid_info.get(DATA_KID_CHORE_PERIODS, {})
    period_buckets = kid_chore_periods.get(period_type, {})
    bucket = period_buckets.get(period_key, {})
    return bucket.get(DATA_KID_CHORE_DATA_PERIOD_MISSED, 0)


# ============================================================================
# TEST: Helper Method (_record_chore_missed)
# ============================================================================


class TestRecordChoreMissedHelper:
    """Test _record_chore_missed() helper method in ChoreManager."""

    async def test_record_missed_updates_timestamp(
        self,
        hass: HomeAssistant,
        setup_missed_tracking_scenario: SetupResult,
    ) -> None:
        """Test that _record_chore_missed() updates last_missed timestamp."""
        result = setup_missed_tracking_scenario
        coordinator = result.coordinator
        chore_manager = coordinator.chore_manager

        # Get Zoë's ID and first chore ID
        zoe = get_kid_by_name(result, "Zoë")
        assert zoe is not None
        zoe_id = zoe["internal_id"]

        # Get "Feed the cåts" chore (INDEPENDENT, assigned to Zoë)
        feed_cats_chore = get_chore_by_name(result, "Feed the cåts")
        assert feed_cats_chore is not None
        chore_id = feed_cats_chore["internal_id"]

        # Verify last_missed is initially None
        assert get_kid_chore_last_missed(coordinator, zoe_id, chore_id) is None

        # Record a miss
        chore_manager._record_chore_missed(zoe_id, chore_id)

        # Verify last_missed timestamp was set
        last_missed = get_kid_chore_last_missed(coordinator, zoe_id, chore_id)
        assert last_missed is not None
        assert isinstance(last_missed, str)

        # Verify it's a recent timestamp (within last 5 seconds)
        now = dt_now_utc()
        from custom_components.choreops.utils.dt_utils import dt_parse

        last_missed_dt = dt_parse(last_missed, return_type="datetime_utc")
        assert isinstance(last_missed_dt, datetime)
        assert (now - last_missed_dt).total_seconds() < 5

    async def test_record_missed_emits_signal(
        self,
        hass: HomeAssistant,
        setup_missed_tracking_scenario: SetupResult,
    ) -> None:
        """Test that _record_chore_missed() emits CHORE_MISSED signal."""
        result = setup_missed_tracking_scenario
        coordinator = result.coordinator
        chore_manager = coordinator.chore_manager

        # Get Zoë's ID and chore ID
        zoe = get_kid_by_name(result, "Zoë")
        assert zoe is not None
        zoe_id = zoe["internal_id"]

        feed_cats_chore = get_chore_by_name(result, "Feed the cåts")
        assert feed_cats_chore is not None
        chore_id = feed_cats_chore["internal_id"]

        # Patch async_dispatcher_send to track signal emissions
        with patch(
            "custom_components.choreops.managers.base_manager.async_dispatcher_send"
        ) as mock_dispatcher:
            # Record a miss
            chore_manager._record_chore_missed(zoe_id, chore_id)

            # Verify CHORE_MISSED signal was emitted
            mock_dispatcher.assert_called_once()
            call_args = mock_dispatcher.call_args
            # BaseManager.emit() adds coordinator entry_id to signal name
            # Signal name format: kidschores_{entry_id}_{SIGNAL_SUFFIX}
            signal_name = call_args[0][1]
            assert signal_name.endswith(SIGNAL_SUFFIX_CHORE_MISSED)
            payload = call_args[0][2]  # Third arg is the payload dict
            assert payload["kid_id"] == zoe_id
            assert payload["chore_id"] == chore_id
            assert payload["kid_name"] == "Zoë"
            assert payload["missed_streak_tally"] == 1  # First miss


# ============================================================================
# TEST: Automated Miss Recording (OVERDUE Resets)
# ============================================================================


class TestAutomatedMissRecording:
    """Test automated miss recording during OVERDUE reset with CLEAR_AND_MARK_MISSED."""

    async def test_overdue_reset_shared_chore_marks_missed(
        self,
        hass: HomeAssistant,
        setup_missed_tracking_scenario: SetupResult,
    ) -> None:
        """Test SHARED chore reset with CLEAR_AND_MARK_MISSED marks all assigned kids as missed."""
        result = setup_missed_tracking_scenario
        coordinator = result.coordinator

        # Get a SHARED chore: "Family Dinner Prep" (assigned to Zoë, Max, Lila)
        dinner_prep = get_chore_by_name(result, "Family Dinner Prep")
        assert dinner_prep is not None
        chore_id = dinner_prep["internal_id"]

        # Set overdue handling to CLEAR_AND_MARK_MISSED
        coordinator.chores_data[chore_id][DATA_CHORE_OVERDUE_HANDLING_TYPE] = (
            OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AND_MARK_MISSED
        )
        # Set approval_reset_type to AT_DUE_DATE so scanner includes this chore
        # when trigger="due_date" (the default). Without this, the chore's default
        # AT_MIDNIGHT_ONCE type causes should_process_at_boundary to return False.
        coordinator.chores_data[chore_id][DATA_CHORE_APPROVAL_RESET_TYPE] = (
            APPROVAL_RESET_AT_DUE_DATE_ONCE
        )

        # Get all assigned kids
        assigned_kids = coordinator.chores_data[chore_id][DATA_CHORE_ASSIGNED_KIDS]
        assert len(assigned_kids) == 3  # Zoë, Max, Lila

        # Set past due date for all kids (required for shared chores to trigger overdue)
        past_date = (dt_now_local() - timedelta(days=1)).isoformat()
        # For shared chores, set BOTH due_date and per_kid_due_dates
        coordinator.chores_data[chore_id][const.DATA_CHORE_DUE_DATE] = past_date
        coordinator.chores_data[chore_id][const.DATA_CHORE_PER_KID_DUE_DATES] = (
            dict.fromkeys(assigned_kids, past_date)
        )
        # Pre-set chore state to OVERDUE so Phase A (approval reset) finds it
        # and calls _record_chore_missed. The two-phase lifecycle is:
        # Phase B marks overdue -> Phase A resets and records miss.
        # We simulate the chore already being in overdue state.
        coordinator.chores_data[chore_id][DATA_CHORE_STATE] = CHORE_STATE_OVERDUE
        for kid_id in assigned_kids:
            kid_chore = coordinator.kids_data[kid_id].get("chore_data", {})
            if chore_id in kid_chore:
                kid_chore[chore_id]["state"] = CHORE_STATE_OVERDUE
        coordinator._persist()

        # Verify no misses recorded yet
        for kid_id in assigned_kids:
            assert get_kid_chore_last_missed(coordinator, kid_id, chore_id) is None

        # Trigger periodic update - Phase A finds overdue chore and records miss
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()
        today_key = coordinator.stats.get_period_keys()["daily"]

        # Verify all kids have last_missed timestamp
        for kid_id in assigned_kids:
            last_missed = get_kid_chore_last_missed(coordinator, kid_id, chore_id)
            assert last_missed is not None
            assert isinstance(last_missed, str)

            # Verify missed_streak_tally written to daily bucket (Phase 5)
            missed_count = get_missed_count_from_period(
                coordinator,
                kid_id,
                chore_id,
                DATA_KID_CHORE_DATA_PERIODS_DAILY,
                today_key,
            )
            assert missed_count == 1  # First miss recorded

        # Verify chore was reset to PENDING
        assert (
            coordinator.chores_data[chore_id][DATA_CHORE_STATE] == CHORE_STATE_PENDING
        )

    async def test_overdue_reset_independent_chore_marks_missed(
        self,
        hass: HomeAssistant,
        setup_missed_tracking_scenario: SetupResult,
    ) -> None:
        """Test INDEPENDENT chore reset with CLEAR_AND_MARK_MISSED marks assigned kid as missed."""
        result = setup_missed_tracking_scenario
        coordinator = result.coordinator

        # Get an INDEPENDENT chore: "Feed the cåts" (assigned to Zoë only)
        feed_cats = get_chore_by_name(result, "Feed the cåts")
        assert feed_cats is not None
        chore_id = feed_cats["internal_id"]

        # Get Zoë's ID
        zoe = get_kid_by_name(result, "Zoë")
        assert zoe is not None
        zoe_id = zoe["internal_id"]

        # Set overdue handling to CLEAR_AND_MARK_MISSED
        coordinator.chores_data[chore_id][DATA_CHORE_OVERDUE_HANDLING_TYPE] = (
            OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AND_MARK_MISSED
        )
        # Set approval_reset_type to AT_DUE_DATE so scanner includes this chore
        coordinator.chores_data[chore_id][DATA_CHORE_APPROVAL_RESET_TYPE] = (
            APPROVAL_RESET_AT_DUE_DATE_ONCE
        )

        # Set past due date for Zoë (required to trigger overdue)
        past_date = (dt_now_local() - timedelta(days=1)).isoformat()
        # For independent chores, set due_date and per_kid_due_dates
        coordinator.chores_data[chore_id][const.DATA_CHORE_DUE_DATE] = past_date
        if const.DATA_CHORE_PER_KID_DUE_DATES not in coordinator.chores_data[chore_id]:
            coordinator.chores_data[chore_id][const.DATA_CHORE_PER_KID_DUE_DATES] = {}
        coordinator.chores_data[chore_id][const.DATA_CHORE_PER_KID_DUE_DATES][
            zoe_id
        ] = past_date
        # Pre-set chore and kid-level state to OVERDUE so Phase A (approval reset)
        # finds it and calls _record_chore_missed.
        coordinator.chores_data[chore_id][DATA_CHORE_STATE] = CHORE_STATE_OVERDUE
        kid_chore = coordinator.kids_data[zoe_id].get("chore_data", {})
        if chore_id in kid_chore:
            kid_chore[chore_id]["state"] = CHORE_STATE_OVERDUE
        coordinator._persist()

        # Verify no miss recorded yet
        assert get_kid_chore_last_missed(coordinator, zoe_id, chore_id) is None

        # Trigger periodic update - Phase A finds overdue chore and records miss
        await coordinator.chore_manager._on_periodic_update(now_utc=dt_now_utc())
        await hass.async_block_till_done()
        today_key = coordinator.stats.get_period_keys()["daily"]

        # Verify last_missed timestamp was set
        last_missed = get_kid_chore_last_missed(coordinator, zoe_id, chore_id)
        assert last_missed is not None
        assert isinstance(last_missed, str)

        # Verify missed_streak_tally written to daily bucket (Phase 5)
        missed_count = get_missed_count_from_period(
            coordinator,
            zoe_id,
            chore_id,
            DATA_KID_CHORE_DATA_PERIODS_DAILY,
            today_key,
        )
        assert missed_count == 1  # First miss recorded


# ============================================================================
# TEST: Manual Miss Recording (skip_chore_due_date Service)
# ============================================================================


class TestSkipChoreWithMissMarking:
    """Test skip_chore_due_date service with mark_as_missed parameter."""

    async def test_skip_independent_chore_with_mark_as_missed(
        self,
        hass: HomeAssistant,
        setup_missed_tracking_scenario: SetupResult,
    ) -> None:
        """Test skip_chore_due_date with mark_as_missed=True for INDEPENDENT chore."""
        result = setup_missed_tracking_scenario
        coordinator = result.coordinator

        # Get Zoë and her chore
        zoe = get_kid_by_name(result, "Zoë")
        assert zoe is not None
        zoe_id = zoe["internal_id"]

        feed_cats = get_chore_by_name(result, "Feed the cåts")
        assert feed_cats is not None
        chore_id = feed_cats["internal_id"]

        # Verify no miss recorded yet
        assert get_kid_chore_last_missed(coordinator, zoe_id, chore_id) is None

        # Call skip_chore_due_date with mark_as_missed=True
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SKIP_CHORE_DUE_DATE,
            {
                "chore_id": chore_id,
                "assignee_id": zoe_id,
                "mark_as_missed": True,
            },
            blocking=True,
        )

        # Verify miss was recorded
        last_missed = get_kid_chore_last_missed(coordinator, zoe_id, chore_id)
        assert last_missed is not None
        assert isinstance(last_missed, str)

        # Verify missed_streak_tally written to daily bucket (Phase 5)
        await hass.async_block_till_done()  # Allow signal processing
        today_key = coordinator.stats.get_period_keys()["daily"]
        missed_count = get_missed_count_from_period(
            coordinator,
            zoe_id,
            chore_id,
            DATA_KID_CHORE_DATA_PERIODS_DAILY,
            today_key,
        )
        assert missed_count == 1  # First miss recorded

    async def test_skip_shared_chore_with_mark_as_missed_all_kids(
        self,
        hass: HomeAssistant,
        setup_missed_tracking_scenario: SetupResult,
    ) -> None:
        """Test skip_chore_due_date with mark_as_missed=True for SHARED chore marks all kids."""
        result = setup_missed_tracking_scenario
        coordinator = result.coordinator

        # Get SHARED chore: "Family Dinner Prep"
        dinner_prep = get_chore_by_name(result, "Family Dinner Prep")
        assert dinner_prep is not None
        chore_id = dinner_prep["internal_id"]

        # Get assigned kids
        assigned_kids = coordinator.chores_data[chore_id][DATA_CHORE_ASSIGNED_KIDS]
        assert len(assigned_kids) == 3

        # Set a due_date so skip_due_date validation passes (shared chores require due_date)
        past_date = (dt_now_local() - timedelta(days=1)).isoformat()
        coordinator.chores_data[chore_id][const.DATA_CHORE_DUE_DATE] = past_date
        coordinator.chores_data[chore_id][const.DATA_CHORE_PER_KID_DUE_DATES] = (
            dict.fromkeys(assigned_kids, past_date)
        )
        coordinator._persist()

        # Verify no misses recorded yet
        for kid_id in assigned_kids:
            assert get_kid_chore_last_missed(coordinator, kid_id, chore_id) is None

        # Call skip_chore_due_date without kid_id (SHARED chore behavior)
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SKIP_CHORE_DUE_DATE,
            {
                "chore_id": chore_id,
                "mark_as_missed": True,
            },
            blocking=True,
        )

        # Verify all kids have miss recorded
        await hass.async_block_till_done()  # Allow signal processing
        today_key = coordinator.stats.get_period_keys()["daily"]
        for kid_id in assigned_kids:
            last_missed = get_kid_chore_last_missed(coordinator, kid_id, chore_id)
            assert last_missed is not None
            assert isinstance(last_missed, str)

            # Verify missed_streak_tally written to daily bucket (Phase 5)
            missed_count = get_missed_count_from_period(
                coordinator,
                kid_id,
                chore_id,
                DATA_KID_CHORE_DATA_PERIODS_DAILY,
                today_key,
            )
            assert missed_count == 1  # First miss recorded

    async def test_skip_chore_without_mark_as_missed_no_record(
        self,
        hass: HomeAssistant,
        setup_missed_tracking_scenario: SetupResult,
    ) -> None:
        """Test skip_chore_due_date with mark_as_missed=False does NOT record miss."""
        result = setup_missed_tracking_scenario
        coordinator = result.coordinator

        # Get Zoë and her chore
        zoe = get_kid_by_name(result, "Zoë")
        assert zoe is not None
        zoe_id = zoe["internal_id"]

        feed_cats = get_chore_by_name(result, "Feed the cåts")
        assert feed_cats is not None
        chore_id = feed_cats["internal_id"]

        # Verify no miss recorded yet
        assert get_kid_chore_last_missed(coordinator, zoe_id, chore_id) is None

        # Call skip_chore_due_date with mark_as_missed=False (default)
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SKIP_CHORE_DUE_DATE,
            {
                "chore_id": chore_id,
                "assignee_id": zoe_id,
                "mark_as_missed": False,
            },
            blocking=True,
        )

        # Verify NO miss was recorded
        assert get_kid_chore_last_missed(coordinator, zoe_id, chore_id) is None


# ============================================================================
# TEST: Period Bucket Writes (Statistics)
# ============================================================================


class TestMissedPeriodBuckets:
    """Test that missed metrics are written to period buckets."""

    async def test_missed_count_written_to_daily_bucket(
        self,
        hass: HomeAssistant,
        setup_missed_tracking_scenario: SetupResult,
    ) -> None:
        """Test that missed count is written to today's daily bucket."""
        result = setup_missed_tracking_scenario
        coordinator = result.coordinator
        stats_engine = coordinator.stats

        # Get Zoë and chore
        zoe = get_kid_by_name(result, "Zoë")
        assert zoe is not None
        zoe_id = zoe["internal_id"]

        feed_cats = get_chore_by_name(result, "Feed the cåts")
        assert feed_cats is not None
        chore_id = feed_cats["internal_id"]

        # Get today's period key
        today_key = stats_engine.get_period_keys()["daily"]

        # Verify missed count is 0 initially
        assert (
            get_missed_count_from_period(
                coordinator,
                zoe_id,
                chore_id,
                DATA_KID_CHORE_DATA_PERIODS_DAILY,
                today_key,
            )
            == 0
        )

        # Record a miss
        coordinator.chore_manager._record_chore_missed(zoe_id, chore_id)
        await hass.async_block_till_done()

        # Verify missed count is now 1 in today's bucket
        assert (
            get_missed_count_from_period(
                coordinator,
                zoe_id,
                chore_id,
                DATA_KID_CHORE_DATA_PERIODS_DAILY,
                today_key,
            )
            == 1
        )

    async def test_missed_count_written_to_all_period_buckets(
        self,
        hass: HomeAssistant,
        setup_missed_tracking_scenario: SetupResult,
    ) -> None:
        """Test that missed count is written to daily, weekly, monthly, yearly buckets."""
        result = setup_missed_tracking_scenario
        coordinator = result.coordinator
        stats_engine = coordinator.stats

        # Get Zoë and chore
        zoe = get_kid_by_name(result, "Zoë")
        assert zoe is not None
        zoe_id = zoe["internal_id"]

        feed_cats = get_chore_by_name(result, "Feed the cåts")
        assert feed_cats is not None
        chore_id = feed_cats["internal_id"]

        # Get period keys
        period_keys = stats_engine.get_period_keys()

        # Record a miss
        coordinator.chore_manager._record_chore_missed(zoe_id, chore_id)
        await hass.async_block_till_done()

        # Verify missed count in all period types
        assert (
            get_missed_count_from_period(
                coordinator,
                zoe_id,
                chore_id,
                DATA_KID_CHORE_DATA_PERIODS_DAILY,
                period_keys["daily"],
            )
            == 1
        )
        assert (
            get_missed_count_from_period(
                coordinator,
                zoe_id,
                chore_id,
                DATA_KID_CHORE_DATA_PERIODS_WEEKLY,
                period_keys["weekly"],
            )
            == 1
        )
        assert (
            get_missed_count_from_period(
                coordinator,
                zoe_id,
                chore_id,
                DATA_KID_CHORE_DATA_PERIODS_MONTHLY,
                period_keys["monthly"],
            )
            == 1
        )
        assert (
            get_missed_count_from_period(
                coordinator,
                zoe_id,
                chore_id,
                DATA_KID_CHORE_DATA_PERIODS_YEARLY,
                period_keys["yearly"],
            )
            == 1
        )

    async def test_missed_count_written_to_kid_level_bucket(
        self,
        hass: HomeAssistant,
        setup_missed_tracking_scenario: SetupResult,
    ) -> None:
        """Test that missed count is also written to kid-level chore_periods bucket."""
        result = setup_missed_tracking_scenario
        coordinator = result.coordinator
        stats_engine = coordinator.stats

        # Get Zoë and chore
        zoe = get_kid_by_name(result, "Zoë")
        assert zoe is not None
        zoe_id = zoe["internal_id"]

        feed_cats = get_chore_by_name(result, "Feed the cåts")
        assert feed_cats is not None
        chore_id = feed_cats["internal_id"]

        # Get today's period key
        today_key = stats_engine.get_period_keys()["daily"]

        # Verify kid-level missed count is 0 initially
        assert (
            get_kid_level_missed_count(
                coordinator,
                zoe_id,
                DATA_KID_CHORE_DATA_PERIODS_DAILY,
                today_key,
            )
            == 0
        )

        # Record a miss
        coordinator.chore_manager._record_chore_missed(zoe_id, chore_id)
        await hass.async_block_till_done()

        # Verify kid-level missed count is now 1
        assert (
            get_kid_level_missed_count(
                coordinator,
                zoe_id,
                DATA_KID_CHORE_DATA_PERIODS_DAILY,
                today_key,
            )
            == 1
        )


# ============================================================================
# TEST: Notification Delivery (FUTURE - NOT IMPLEMENTED YET)
# ============================================================================

# TODO: Uncomment when notification infrastructure is implemented
# class TestMissedNotifications:
#     """Test notification delivery when chores are marked as missed."""
#
#     async def test_missed_notification_sent(
#         self,
#         hass: HomeAssistant,
#         setup_missed_tracking_scenario: SetupResult,
#     ) -> None:
#         """Test that notification is sent when chore is marked as missed."""
#         result = setup_missed_tracking_scenario
#         coordinator = result.coordinator
#
#         # Get Zoë and chore
#         zoe = get_kid_by_name(result, "Zoë")
#         assert zoe is not None
#         zoe_id = zoe["internal_id"]
#
#         feed_cats = get_chore_by_name(result, "Feed the cåts")
#         assert feed_cats is not None
#         chore_id = feed_cats["internal_id"]
#
#         # Mock the notification method
#         with patch.object(coordinator, "_notify_kid", new=AsyncMock()) as mock_notify:
#             # Record a miss
#             coordinator.chore_manager._record_chore_missed(zoe_id, chore_id)
#             await hass.async_block_till_done()
#
#             # Verify notification was sent to Zoë
#             mock_notify.assert_called_once()
#             call_args = mock_notify.call_args
#             assert call_args[0][0] == zoe_id  # Kid ID
# Note: Exact notification keys depend on const.py translation keys
