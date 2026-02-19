"""Tests for StatisticsEngine.

Tests cover:
- Period key generation (daily, weekly, monthly, yearly formats)
- Transaction recording (increments, all_time, custom mappings)
- Streak management (update, get, edge cases)
- History pruning (retention policies, cutoff calculations)
- Utility methods (get_period_total)
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from unittest.mock import patch

import pytest

from custom_components.choreops import const
from custom_components.choreops.engines.statistics_engine import StatisticsEngine


@pytest.fixture
def stats() -> StatisticsEngine:
    """Return a StatisticsEngine instance."""
    return StatisticsEngine()


@pytest.fixture
def sample_period_data() -> dict[str, Any]:
    """Return sample period data structure."""
    return {
        "daily": {},
        "weekly": {},
        "monthly": {},
        "yearly": {},
        "all_time": {},
    }


class TestGetPeriodKeys:
    """Tests for get_period_keys method."""

    def test_returns_all_period_types(self, stats: StatisticsEngine) -> None:
        """Should return keys for all period types."""
        keys = stats.get_period_keys(reference_date=date(2026, 1, 19))

        assert const.PERIOD_DAILY in keys
        assert const.PERIOD_WEEKLY in keys
        assert const.PERIOD_MONTHLY in keys
        assert const.PERIOD_YEARLY in keys

    def test_daily_format(self, stats: StatisticsEngine) -> None:
        """Daily key should be YYYY-MM-DD format."""
        keys = stats.get_period_keys(reference_date=date(2026, 1, 19))

        assert keys[const.PERIOD_DAILY] == "2026-01-19"

    def test_weekly_format(self, stats: StatisticsEngine) -> None:
        """Weekly key should be YYYY-WNN format."""
        # Jan 19, 2026 is in week 4 (ISO week number)
        keys = stats.get_period_keys(reference_date=date(2026, 1, 19))

        assert keys[const.PERIOD_WEEKLY] == "2026-W04"

    def test_monthly_format(self, stats: StatisticsEngine) -> None:
        """Monthly key should be YYYY-MM format."""
        keys = stats.get_period_keys(reference_date=date(2026, 1, 19))

        assert keys[const.PERIOD_MONTHLY] == "2026-01"

    def test_yearly_format(self, stats: StatisticsEngine) -> None:
        """Yearly key should be YYYY format."""
        keys = stats.get_period_keys(reference_date=date(2026, 1, 19))

        assert keys[const.PERIOD_YEARLY] == "2026"

    def test_accepts_datetime(self, stats: StatisticsEngine) -> None:
        """Should accept datetime and extract date."""
        dt = datetime(2026, 7, 15, 14, 30, 0, tzinfo=UTC)
        keys = stats.get_period_keys(reference_date=dt)

        assert keys[const.PERIOD_DAILY] == "2026-07-15"
        assert keys[const.PERIOD_MONTHLY] == "2026-07"

    def test_none_uses_today(self, stats: StatisticsEngine) -> None:
        """None reference_date should use today."""
        with patch.object(
            stats,
            "_dt_today_local",
            return_value=date(2026, 3, 10),
        ):
            keys = stats.get_period_keys(reference_date=None)

        assert keys[const.PERIOD_DAILY] == "2026-03-10"
        assert keys[const.PERIOD_MONTHLY] == "2026-03"

    def test_week_boundary_sunday(self, stats: StatisticsEngine) -> None:
        """Test week key at year end boundary."""
        # Dec 31, 2025 is Wednesday - ISO week 1 of 2026 (week starts Monday)
        keys = stats.get_period_keys(reference_date=date(2025, 12, 31))
        assert keys[const.PERIOD_WEEKLY] == "2025-W01"

    def test_week_boundary_new_year(self, stats: StatisticsEngine) -> None:
        """Test week key crossing into new year."""
        # Jan 1, 2026 is Thursday - still week 1 of 2026
        keys = stats.get_period_keys(reference_date=date(2026, 1, 1))
        assert keys[const.PERIOD_WEEKLY] == "2026-W01"


class TestRecordTransaction:
    """Tests for record_transaction method."""

    def test_basic_increment(
        self, stats: StatisticsEngine, sample_period_data: dict[str, Any]
    ) -> None:
        """Should increment metrics in all period buckets."""
        stats.record_transaction(
            sample_period_data,
            increments={"approved": 1, "points": 10},
            reference_date=date(2026, 1, 19),
        )

        # Check daily
        assert sample_period_data["daily"]["2026-01-19"]["approved"] == 1
        assert sample_period_data["daily"]["2026-01-19"]["points"] == 10

        # Check weekly
        assert sample_period_data["weekly"]["2026-W04"]["approved"] == 1

        # Check monthly
        assert sample_period_data["monthly"]["2026-01"]["approved"] == 1

        # Check yearly
        assert sample_period_data["yearly"]["2026"]["approved"] == 1

    def test_completed_metric_increment(
        self, stats: StatisticsEngine, sample_period_data: dict[str, Any]
    ) -> None:
        """Should increment completed metric in all period buckets.

        The 'completed' metric tracks work completion by work date (claim time),
        separate from 'approved' which tracks approval date. This enables
        approver-lag-proof statistics where assignees get credit for the day they
        did the work, not the day the approver approved it.
        """
        stats.record_transaction(
            sample_period_data,
            increments={"completed": 1},
            reference_date=date(2026, 1, 19),
        )

        # Check all period buckets have completed metric
        assert sample_period_data["daily"]["2026-01-19"]["completed"] == 1
        assert sample_period_data["weekly"]["2026-W04"]["completed"] == 1
        assert sample_period_data["monthly"]["2026-01"]["completed"] == 1
        assert sample_period_data["yearly"]["2026"]["completed"] == 1

    def test_completed_and_approved_independent(
        self, stats: StatisticsEngine, sample_period_data: dict[str, Any]
    ) -> None:
        """Completed and approved metrics should track independently.

        Scenario: Assignee claims Monday, approver approves Wednesday.
        - completed +1 in Monday bucket (work date)
        - approved +1 in Wednesday bucket (approval date)
        """
        # Record completed for Monday (when assignee did the work)
        stats.record_transaction(
            sample_period_data,
            increments={"completed": 1},
            reference_date=date(2026, 1, 19),  # Monday
        )

        # Record approved for Wednesday (when approver approved)
        stats.record_transaction(
            sample_period_data,
            increments={"approved": 1},
            reference_date=date(2026, 1, 21),  # Wednesday
        )

        # Completed in Monday bucket
        assert sample_period_data["daily"]["2026-01-19"]["completed"] == 1
        assert sample_period_data["daily"]["2026-01-19"].get("approved") is None

        # Approved in Wednesday bucket
        assert sample_period_data["daily"]["2026-01-21"]["approved"] == 1
        assert sample_period_data["daily"]["2026-01-21"].get("completed") is None

    def test_cumulative_increments(
        self, stats: StatisticsEngine, sample_period_data: dict[str, Any]
    ) -> None:
        """Multiple calls should accumulate values."""
        ref_date = date(2026, 1, 19)

        stats.record_transaction(
            sample_period_data,
            increments={"approved": 1},
            reference_date=ref_date,
        )
        stats.record_transaction(
            sample_period_data,
            increments={"approved": 1},
            reference_date=ref_date,
        )
        stats.record_transaction(
            sample_period_data,
            increments={"approved": 3},
            reference_date=ref_date,
        )

        assert sample_period_data["daily"]["2026-01-19"]["approved"] == 5

    def test_include_all_time(
        self, stats: StatisticsEngine, sample_period_data: dict[str, Any]
    ) -> None:
        """Should update all_time totals when flag is set."""
        stats.record_transaction(
            sample_period_data,
            increments={"points": 50},
            include_all_time=True,
            reference_date=date(2026, 1, 19),
        )

        # all_time uses nested structure: all_time.all_time.{metric}
        assert sample_period_data["all_time"]["all_time"]["points"] == 50

    def test_include_all_time_by_default(
        self, stats: StatisticsEngine, sample_period_data: dict[str, Any]
    ) -> None:
        """Should update all_time by default (v0.6.0+: all entities have all_time)."""
        stats.record_transaction(
            sample_period_data,
            increments={"points": 50},
            reference_date=date(2026, 1, 19),
        )

        # all_time should be updated by default with nested structure
        assert sample_period_data["all_time"]["all_time"]["points"] == 50

    def test_exclude_all_time_when_disabled(
        self, stats: StatisticsEngine, sample_period_data: dict[str, Any]
    ) -> None:
        """Should not update all_time when explicitly disabled (legacy data)."""
        stats.record_transaction(
            sample_period_data,
            increments={"points": 50},
            include_all_time=False,
            reference_date=date(2026, 1, 19),
        )

        # all_time should remain empty when explicitly disabled
        assert sample_period_data.get("all_time", {}).get("points") is None

    def test_float_precision(
        self, stats: StatisticsEngine, sample_period_data: dict[str, Any]
    ) -> None:
        """Float increments should respect DATA_FLOAT_PRECISION."""
        stats.record_transaction(
            sample_period_data,
            increments={"points": 3.333333},
            reference_date=date(2026, 1, 19),
        )

        # Should be rounded to DATA_FLOAT_PRECISION decimal places
        result = sample_period_data["daily"]["2026-01-19"]["points"]
        assert result == round(3.333333, const.DATA_FLOAT_PRECISION)

    def test_creates_missing_structure(self, stats: StatisticsEngine) -> None:
        """Should create missing period dicts."""
        empty_data: dict[str, Any] = {}

        stats.record_transaction(
            empty_data,
            increments={"count": 1},
            reference_date=date(2026, 1, 19),
        )

        assert "daily" in empty_data
        assert "2026-01-19" in empty_data["daily"]
        assert empty_data["daily"]["2026-01-19"]["count"] == 1

    def test_custom_period_key_mapping(self, stats: StatisticsEngine) -> None:
        """Should use custom key mapping when provided."""
        data: dict[str, Any] = {}
        custom_mapping = {
            const.PERIOD_DAILY: "d",
            const.PERIOD_WEEKLY: "w",
            const.PERIOD_MONTHLY: "m",
            const.PERIOD_YEARLY: "y",
        }

        stats.record_transaction(
            data,
            increments={"value": 1},
            period_key_mapping=custom_mapping,
            reference_date=date(2026, 1, 19),
        )

        assert "d" in data
        assert "w" in data
        assert "m" in data
        assert "y" in data

    def test_multiple_metrics_same_transaction(
        self, stats: StatisticsEngine, sample_period_data: dict[str, Any]
    ) -> None:
        """Should handle multiple metrics in single transaction."""
        stats.record_transaction(
            sample_period_data,
            increments={
                "claimed": 1,
                "approved": 1,
                "points": 15,
                "bonus": 5,
            },
            reference_date=date(2026, 1, 19),
        )

        bucket = sample_period_data["daily"]["2026-01-19"]
        assert bucket["claimed"] == 1
        assert bucket["approved"] == 1
        assert bucket["points"] == 15
        assert bucket["bonus"] == 5


class TestUpdateStreak:
    """Tests for update_streak method."""

    def test_first_activity_sets_streak_to_one(self, stats: StatisticsEngine) -> None:
        """First activity should set streak to 1."""
        container: dict[str, Any] = {}

        result = stats.update_streak(
            container,
            streak_key="current_streak",
            last_date_key="last_completed",
            reference_date=date(2026, 1, 19),
        )

        assert result == 1
        assert container["current_streak"] == 1
        assert container["last_completed"] == "2026-01-19"

    def test_same_day_no_change(self, stats: StatisticsEngine) -> None:
        """Activity on same day should not change streak."""
        container = {
            "current_streak": 5,
            "last_completed": "2026-01-19",
        }

        result = stats.update_streak(
            container,
            streak_key="current_streak",
            last_date_key="last_completed",
            reference_date=date(2026, 1, 19),
        )

        assert result == 5
        assert container["current_streak"] == 5

    def test_consecutive_day_increments(self, stats: StatisticsEngine) -> None:
        """Activity on consecutive day should increment streak."""
        container = {
            "current_streak": 5,
            "last_completed": "2026-01-18",  # Yesterday
        }

        result = stats.update_streak(
            container,
            streak_key="current_streak",
            last_date_key="last_completed",
            reference_date=date(2026, 1, 19),
        )

        assert result == 6
        assert container["current_streak"] == 6
        assert container["last_completed"] == "2026-01-19"

    def test_gap_resets_streak(self, stats: StatisticsEngine) -> None:
        """Gap of 2+ days should reset streak to 1."""
        container = {
            "current_streak": 10,
            "last_completed": "2026-01-15",  # 4 days ago
        }

        result = stats.update_streak(
            container,
            streak_key="current_streak",
            last_date_key="last_completed",
            reference_date=date(2026, 1, 19),
        )

        assert result == 1
        assert container["current_streak"] == 1

    def test_without_last_date_key(self, stats: StatisticsEngine) -> None:
        """Should work without updating last_date_key."""
        container: dict[str, Any] = {"streak": 3}

        result = stats.update_streak(
            container,
            streak_key="streak",
            last_date_key=None,
            reference_date=date(2026, 1, 19),
        )

        # Without last_date_key, always resets (no comparison possible)
        assert result == 1
        assert "last_completed" not in container

    def test_year_boundary(self, stats: StatisticsEngine) -> None:
        """Streak should continue across year boundary."""
        container = {
            "current_streak": 5,
            "last_completed": "2025-12-31",
        }

        result = stats.update_streak(
            container,
            streak_key="current_streak",
            last_date_key="last_completed",
            reference_date=date(2026, 1, 1),
        )

        assert result == 6

    def test_accepts_datetime_reference(self, stats: StatisticsEngine) -> None:
        """Should accept datetime and extract date."""
        container = {
            "current_streak": 3,
            "last_completed": "2026-01-18",
        }

        result = stats.update_streak(
            container,
            streak_key="current_streak",
            last_date_key="last_completed",
            reference_date=datetime(2026, 1, 19, 14, 30, tzinfo=UTC),
        )

        assert result == 4


class TestGetStreak:
    """Tests for get_streak method."""

    def test_returns_existing_streak(self, stats: StatisticsEngine) -> None:
        """Should return existing streak value."""
        container = {"my_streak": 7}

        result = stats.get_streak(container, "my_streak")

        assert result == 7

    def test_returns_zero_for_missing(self, stats: StatisticsEngine) -> None:
        """Should return 0 for missing streak key."""
        container: dict[str, Any] = {}

        result = stats.get_streak(container, "nonexistent")

        assert result == 0


class TestPruneHistory:
    """Tests for prune_history method."""

    def test_prunes_old_daily_data(self, stats: StatisticsEngine) -> None:
        """Should remove daily entries older than retention."""
        data: dict[str, Any] = {
            "daily": {
                "2026-01-19": {"count": 1},  # Today
                "2026-01-18": {"count": 1},  # Yesterday
                "2025-10-01": {"count": 1},  # Very old
                "2025-06-15": {"count": 1},  # Even older
            },
        }

        pruned = stats.prune_history(
            data,
            retention_config={"daily": 30},
            reference_date=date(2026, 1, 19),
        )

        # Should keep recent, remove old
        assert "2026-01-19" in data["daily"]
        assert "2026-01-18" in data["daily"]
        assert "2025-10-01" not in data["daily"]
        assert "2025-06-15" not in data["daily"]
        assert pruned == 2

    def test_prunes_old_weekly_data(self, stats: StatisticsEngine) -> None:
        """Should remove weekly entries older than retention."""
        data: dict[str, Any] = {
            "weekly": {
                "2026-W03": {"count": 1},  # Current
                "2026-W02": {"count": 1},  # Last week
                "2025-W01": {"count": 1},  # Old
            },
        }

        pruned = stats.prune_history(
            data,
            retention_config={"weekly": 12},
            reference_date=date(2026, 1, 19),
        )

        assert "2026-W03" in data["weekly"]
        assert "2025-W01" not in data["weekly"]
        assert pruned >= 1

    def test_prunes_old_monthly_data(self, stats: StatisticsEngine) -> None:
        """Should remove monthly entries older than retention."""
        data: dict[str, Any] = {
            "monthly": {
                "2026-01": {"count": 1},  # Current
                "2025-12": {"count": 1},  # Last month
                "2024-01": {"count": 1},  # Very old
            },
        }

        stats.prune_history(
            data,
            retention_config={"monthly": 6},
            reference_date=date(2026, 1, 19),
        )

        assert "2026-01" in data["monthly"]
        assert "2024-01" not in data["monthly"]

    def test_prunes_old_yearly_data(self, stats: StatisticsEngine) -> None:
        """Should remove yearly entries older than retention."""
        data: dict[str, Any] = {
            "yearly": {
                "2026": {"count": 1},
                "2025": {"count": 1},
                "2020": {"count": 1},
            },
        }

        pruned = stats.prune_history(
            data,
            retention_config={"yearly": 3},
            reference_date=date(2026, 1, 19),
        )

        assert "2026" in data["yearly"]
        assert "2025" in data["yearly"]
        assert "2020" not in data["yearly"]
        assert pruned >= 1

    def test_uses_default_retention(self, stats: StatisticsEngine) -> None:
        """Should use default retention values when not provided."""
        data: dict[str, Any] = {
            "daily": {"2020-01-01": {"count": 1}},  # Very old
        }

        # Should use const.DEFAULT_RETENTION_DAILY (typically 90)
        stats.prune_history(data, reference_date=date(2026, 1, 19))

        # Old entry should be pruned with default retention
        assert "2020-01-01" not in data["daily"]

    def test_does_not_prune_all_time(self, stats: StatisticsEngine) -> None:
        """Should never prune all_time data."""
        data: dict[str, Any] = {
            "all_time": {"total_points": 1000},
        }

        stats.prune_history(data, reference_date=date(2026, 1, 19))

        assert data["all_time"]["total_points"] == 1000

    def test_custom_period_key_mapping(self, stats: StatisticsEngine) -> None:
        """Should respect custom key mapping."""
        data: dict[str, Any] = {
            "d": {"2020-01-01": {"count": 1}},
        }
        custom_mapping = {
            const.PERIOD_DAILY: "d",
            const.PERIOD_WEEKLY: "w",
            const.PERIOD_MONTHLY: "m",
            const.PERIOD_YEARLY: "y",
        }

        pruned = stats.prune_history(
            data,
            retention_config={"daily": 30},
            period_key_mapping=custom_mapping,
            reference_date=date(2026, 1, 19),
        )

        assert "2020-01-01" not in data["d"]
        assert pruned == 1

    def test_returns_total_pruned_count(self, stats: StatisticsEngine) -> None:
        """Should return total count of pruned entries."""
        data: dict[str, Any] = {
            "daily": {"2020-01-01": {}, "2020-01-02": {}},
            "weekly": {"2020-W01": {}},
            "monthly": {"2020-01": {}},
            "yearly": {"2015": {}},
        }

        pruned = stats.prune_history(
            data,
            retention_config={
                "daily": 30,
                "weekly": 12,
                "monthly": 6,
                "yearly": 3,
            },
            reference_date=date(2026, 1, 19),
        )

        assert pruned == 5

    def test_handles_empty_period_data(self, stats: StatisticsEngine) -> None:
        """Should handle empty or missing period dicts gracefully."""
        data: dict[str, Any] = {}

        # Should not raise
        pruned = stats.prune_history(data, reference_date=date(2026, 1, 19))

        assert pruned == 0


class TestGetPeriodTotal:
    """Tests for get_period_total method."""

    def test_gets_daily_total(self, stats: StatisticsEngine) -> None:
        """Should get value from daily period."""
        data = {
            "daily": {"2026-01-19": {"approved": 5, "points": 100}},
        }

        with patch.object(
            stats,
            "_dt_today_local",
            return_value=date(2026, 1, 19),
        ):
            result = stats.get_period_total(data, const.PERIOD_DAILY, "approved")

        assert result == 5

    def test_gets_all_time_total(self, stats: StatisticsEngine) -> None:
        """Should get value from all_time (nested structure)."""
        data = {
            "all_time": {"all_time": {"total_points": 1500}},
        }

        result = stats.get_period_total(data, const.PERIOD_ALL_TIME, "total_points")

        assert result == 1500

    def test_returns_zero_for_missing(self, stats: StatisticsEngine) -> None:
        """Should return 0 for missing metric."""
        data: dict[str, Any] = {"daily": {}}

        result = stats.get_period_total(data, const.PERIOD_DAILY, "nonexistent")

        assert result == 0

    def test_specific_period_key(self, stats: StatisticsEngine) -> None:
        """Should use provided period_key instead of current."""
        data = {
            "monthly": {
                "2025-12": {"sales": 50},
                "2026-01": {"sales": 75},
            },
        }

        result = stats.get_period_total(
            data,
            const.PERIOD_MONTHLY,
            "sales",
            period_key="2025-12",
        )

        assert result == 50


class TestEdgeCases:
    """Tests for edge cases and integration scenarios."""

    def test_full_workflow(self, stats: StatisticsEngine) -> None:
        """Test complete workflow: record, update streak, prune."""
        data: dict[str, Any] = {
            "daily": {},
            "weekly": {},
            "monthly": {},
            "yearly": {},
            "all_time": {},
        }
        container: dict[str, Any] = {}

        # Day 1
        stats.record_transaction(
            data,
            increments={"approved": 1, "points": 10},
            include_all_time=True,
            reference_date=date(2026, 1, 17),
        )
        stats.update_streak(
            container,
            "streak",
            "last_date",
            reference_date=date(2026, 1, 17),
        )

        # Day 2 (consecutive)
        stats.record_transaction(
            data,
            increments={"approved": 1, "points": 15},
            include_all_time=True,
            reference_date=date(2026, 1, 18),
        )
        stats.update_streak(
            container,
            "streak",
            "last_date",
            reference_date=date(2026, 1, 18),
        )

        # Day 3 (consecutive)
        stats.record_transaction(
            data,
            increments={"approved": 2, "points": 25},
            include_all_time=True,
            reference_date=date(2026, 1, 19),
        )
        streak = stats.update_streak(
            container,
            "streak",
            "last_date",
            reference_date=date(2026, 1, 19),
        )

        # Verify results
        assert streak == 3
        # all_time uses nested structure: all_time.all_time.{metric}
        assert data["all_time"]["all_time"]["approved"] == 4
        assert data["all_time"]["all_time"]["points"] == 50
        assert data["daily"]["2026-01-19"]["approved"] == 2

    def test_negative_increments(
        self, stats: StatisticsEngine, sample_period_data: dict[str, Any]
    ) -> None:
        """Should handle negative increments (point deductions)."""
        # Add some points
        stats.record_transaction(
            sample_period_data,
            increments={"points": 100},
            include_all_time=True,
            reference_date=date(2026, 1, 19),
        )

        # Deduct points
        stats.record_transaction(
            sample_period_data,
            increments={"points": -30},
            include_all_time=True,
            reference_date=date(2026, 1, 19),
        )

        # all_time uses nested structure: all_time.all_time.{metric}
        assert sample_period_data["all_time"]["all_time"]["points"] == 70
        assert sample_period_data["daily"]["2026-01-19"]["points"] == 70

    def test_dst_transition(self, stats: StatisticsEngine) -> None:
        """Streak should work correctly across DST transitions."""
        container = {
            "current_streak": 5,
            # March 8, 2026 is before DST (US), March 9 is DST transition
            "last_completed": "2026-03-08",
        }

        result = stats.update_streak(
            container,
            streak_key="current_streak",
            last_date_key="last_completed",
            reference_date=date(2026, 3, 9),
        )

        # Should still be consecutive
        assert result == 6
