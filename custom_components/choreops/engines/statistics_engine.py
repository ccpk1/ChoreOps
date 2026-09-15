"""Statistics Engine - Unified time-series tracking for period-based data.

This engine centralizes all period-based statistics tracking across ChoreOps:
- Chore completions (claimed, approved, rejected, points)
- Point transactions (earned, spent, bonuses, penalties)
- Reward claims (claimed, redeemed)
- Badge earnings (daily/weekly/monthly/yearly counts)

Design Principles:
    - Stateless: No coordinator reference, operates on passed data structures
    - Consistent: Single source of truth for period key generation
    - Efficient: Batch updates with optional auto-pruning
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING, Any, Final

from .. import const
from ..utils.dt_utils import as_local, dt_now_utc

if TYPE_CHECKING:
    from collections.abc import Mapping


# Default retention periods (can be overridden by config)
DEFAULT_RETENTION: Final[dict[str, int]] = {
    const.PERIOD_DAILY: const.DEFAULT_RETENTION_DAILY,
    const.PERIOD_WEEKLY: const.DEFAULT_RETENTION_WEEKLY,
    const.PERIOD_MONTHLY: const.DEFAULT_RETENTION_MONTHLY,
    const.PERIOD_YEARLY: const.DEFAULT_RETENTION_YEARLY,
}


class StatisticsEngine:
    """Unified engine for tracking period-based statistics.

    This class provides methods to:
    - Generate consistent period keys (daily/weekly/monthly/yearly)
    - Record transactions to multiple period buckets atomically
    - Prune historical data based on retention policies

    Streaks are deliberately **not** calculated here. `ChoreEngine.calculate_streak`
    owns chore streaks and `ChoreEngine.has_missed_occurrence_between` owns miss
    detection, both schedule-aware. Calendar-day streak helpers used to live in this
    class and were removed: a generically named streak utility implementing
    yesterday-only logic is a trap for the next contributor.

    All methods are stateless - they operate on data structures passed as arguments.
    The engine does NOT persist data; the caller is responsible for persistence.

    Example:
        stats = StatisticsEngine()

        # Record a chore completion
        period_data = assignee_chore_data["periods"]
        stats.record_transaction(
            period_data,
            increments={"approved": 1, "points": 10},
            include_all_time=True,
        )

        # Prune old data
        stats.prune_history(period_data, retention_config)
    """

    # ────────────────────────────────────────────────────────────────
    # Period Key Generation
    # ────────────────────────────────────────────────────────────────

    @staticmethod
    def _dt_today_local() -> date:
        """Return today's date in local timezone.

        Returns:
            Current date in local timezone.
        """
        return as_local(dt_now_utc()).date()

    @staticmethod
    def _dt_now_local() -> datetime:
        """Return current datetime in local timezone.

        Returns:
            Current datetime (timezone-aware) in local timezone.
        """
        return as_local(dt_now_utc())

    def get_period_keys(
        self, reference_date: date | datetime | None = None
    ) -> dict[str, str]:
        """Generate period keys for all time granularities.

        Creates consistent period identifiers for daily, weekly, monthly,
        and yearly tracking based on the reference date.

        Args:
            reference_date: Date to generate keys for. Defaults to today (local).
                           Accepts date, datetime, or None.

        Returns:
            Dictionary with keys: "daily", "weekly", "monthly", "yearly"
            Values are formatted strings suitable for use as dictionary keys.

        Example:
            >>> stats.get_period_keys()
            {
                "daily": "2026-01-19",
                "weekly": "2026-W03",
                "monthly": "2026-01",
                "yearly": "2026"
            }
        """
        if reference_date is None:
            ref = self._dt_today_local()
        elif isinstance(reference_date, datetime):
            ref = reference_date.date()
        else:
            ref = reference_date

        return {
            const.PERIOD_DAILY: ref.strftime(const.PERIOD_FORMAT_DAILY),
            const.PERIOD_WEEKLY: ref.strftime(const.PERIOD_FORMAT_WEEKLY),
            const.PERIOD_MONTHLY: ref.strftime(const.PERIOD_FORMAT_MONTHLY),
            const.PERIOD_YEARLY: ref.strftime(const.PERIOD_FORMAT_YEARLY),
        }

    # ────────────────────────────────────────────────────────────────
    # Transaction Recording
    # ────────────────────────────────────────────────────────────────

    def record_transaction(
        self,
        period_data: dict[str, Any],
        increments: Mapping[str, int | float],
        period_key_mapping: Mapping[str, str] | None = None,
        include_all_time: bool = True,
        reference_date: date | datetime | None = None,
    ) -> None:
        """Record a transaction across all period buckets.

        Updates daily, weekly, monthly, and yearly period data with the
        provided increments. Optionally updates all_time totals.

        Special handling:
        - streak_tally: ONLY written to daily buckets
        - longest_streak: NEVER written by this method (managed separately in all_time)

        This method mutates `period_data` in place. Caller is responsible
        for persistence after calling this method.

        Args:
            period_data: Dictionary containing nested period structures.
                        Expected format: {period_type: {period_key: {metric: value}}}
            increments: Metrics to increment and their values.
                       Example: {"approved": 1, "points": 10}
                       Note: streak_tally filtered to daily only, longest_streak skipped.
            period_key_mapping: Optional mapping from logical period names to
                               data structure keys. Defaults use const values:
                               {"daily": "daily", "weekly": "weekly", ...}
            include_all_time: If True (default), also update "all_time" totals.
                             Set to False only for legacy data without all_time bucket.
            reference_date: Date for period key generation. Defaults to today.

        Example:
            # Standard chore period update
            stats.record_transaction(
                chore_data["periods"],
                increments={"approved": 1, "points": 10},
                include_all_time=True,
            )

            # Point period update with custom key mapping
            stats.record_transaction(
                point_data["periods"],
                increments={"earned": 5},
                period_key_mapping={
                    "daily": const.DATA_USER_POINT_PERIODS_DAILY,
                    "weekly": const.DATA_USER_POINT_PERIODS_WEEKLY,
                    "monthly": const.DATA_USER_POINT_PERIODS_MONTHLY,
                    "yearly": const.DATA_USER_POINT_PERIODS_YEARLY,
                },
            )
        """
        # Generate period keys for current date
        keys = self.get_period_keys(reference_date)

        # Default key mapping if not provided
        if period_key_mapping is None:
            period_key_mapping = {
                const.PERIOD_DAILY: const.PERIOD_DAILY,
                const.PERIOD_WEEKLY: const.PERIOD_WEEKLY,
                const.PERIOD_MONTHLY: const.PERIOD_MONTHLY,
                const.PERIOD_YEARLY: const.PERIOD_YEARLY,
            }

        # Update each period bucket with appropriate metrics
        for period_type, period_key in keys.items():
            data_key = period_key_mapping.get(period_type, period_type)

            # Ensure period type dict exists
            if data_key not in period_data:
                period_data[data_key] = {}

            # Ensure period key dict exists
            if period_key not in period_data[data_key]:
                period_data[data_key][period_key] = {}

            # Apply increments with period-specific filtering
            bucket = period_data[data_key][period_key]
            for metric, value in increments.items():
                # FILTER 1: streak_tally ONLY in daily buckets
                if (
                    metric == const.DATA_USER_CHORE_DATA_PERIOD_STREAK_TALLY
                    and period_type != const.PERIOD_DAILY
                ):
                    continue

                # FILTER 2: longest_streak NEVER written here (managed in all_time only)
                if metric == const.DATA_USER_CHORE_DATA_PERIOD_LONGEST_STREAK:
                    continue

                # Write all other metrics to bucket
                current = bucket.get(metric, 0)
                if isinstance(value, float):
                    bucket[metric] = round(current + value, const.DATA_FLOAT_PRECISION)
                else:
                    bucket[metric] = current + value

        # Optionally update all_time totals with appropriate metrics
        # NOTE: all_time uses nested structure: periods["all_time"]["all_time"] = {data}
        # This matches point_periods structure and migration output
        if include_all_time:
            if const.PERIOD_ALL_TIME not in period_data:
                period_data[const.PERIOD_ALL_TIME] = {}

            all_time_container = period_data[const.PERIOD_ALL_TIME]
            if const.PERIOD_ALL_TIME not in all_time_container:
                all_time_container[const.PERIOD_ALL_TIME] = {}

            all_time_bucket = all_time_container[const.PERIOD_ALL_TIME]
            for metric, value in increments.items():
                # FILTER: streak_tally NEVER in all_time (daily only)
                if metric == const.DATA_USER_CHORE_DATA_PERIOD_STREAK_TALLY:
                    continue

                # longest_streak is managed separately in _on_chore_completed
                # (high-water mark logic, not simple increment)
                # Skip it here to avoid duplicate/incorrect writes
                if metric == const.DATA_USER_CHORE_DATA_PERIOD_LONGEST_STREAK:
                    continue

                current = all_time_bucket.get(metric, 0)
                if isinstance(value, float):
                    all_time_bucket[metric] = round(
                        current + value, const.DATA_FLOAT_PRECISION
                    )
                else:
                    all_time_bucket[metric] = current + value

    def record_maximum(
        self,
        period_data: dict[str, Any],
        maximums: Mapping[str, int | float],
        period_key_mapping: Mapping[str, str] | None = None,
        include_all_time: bool = True,
        reference_date: date | datetime | None = None,
    ) -> None:
        """Record high-water marks across all period buckets.

        Unlike record_transaction(), this keeps the maximum observed value for
        each metric in the active daily/weekly/monthly/yearly buckets and the
        optional all_time bucket.

        Args:
            period_data: Dictionary containing nested period structures.
            maximums: Metrics to compare and their observed values.
            period_key_mapping: Optional mapping from logical period names to
                               data structure keys. Defaults to standard keys.
            include_all_time: If True (default), also update all_time maximums.
            reference_date: Date for period key generation. Defaults to today.
        """
        keys = self.get_period_keys(reference_date)

        if period_key_mapping is None:
            period_key_mapping = {
                const.PERIOD_DAILY: const.PERIOD_DAILY,
                const.PERIOD_WEEKLY: const.PERIOD_WEEKLY,
                const.PERIOD_MONTHLY: const.PERIOD_MONTHLY,
                const.PERIOD_YEARLY: const.PERIOD_YEARLY,
            }

        for period_type, period_key in keys.items():
            data_key = period_key_mapping.get(period_type, period_type)
            if data_key not in period_data:
                period_data[data_key] = {}
            if period_key not in period_data[data_key]:
                period_data[data_key][period_key] = {}

            bucket = period_data[data_key][period_key]
            self._apply_maximums(bucket, maximums)

        if include_all_time:
            if const.PERIOD_ALL_TIME not in period_data:
                period_data[const.PERIOD_ALL_TIME] = {}
            all_time_container = period_data[const.PERIOD_ALL_TIME]
            if const.PERIOD_ALL_TIME not in all_time_container:
                all_time_container[const.PERIOD_ALL_TIME] = {}

            self._apply_maximums(all_time_container[const.PERIOD_ALL_TIME], maximums)

    @staticmethod
    def _apply_maximums(
        bucket: dict[str, Any],
        maximums: Mapping[str, int | float],
    ) -> None:
        """Apply max updates to one period bucket."""
        for metric, value in maximums.items():
            current = bucket.get(metric)
            if isinstance(current, (int, float)):
                next_value = max(current, value)
            else:
                next_value = value

            if isinstance(next_value, float):
                bucket[metric] = round(next_value, const.DATA_FLOAT_PRECISION)
            else:
                bucket[metric] = next_value

    # ────────────────────────────────────────────────────────────────
    # History Pruning
    # ────────────────────────────────────────────────────────────────

    def prune_history(
        self,
        period_data: dict[str, Any],
        retention_config: Mapping[str, int] | None = None,
        period_key_mapping: Mapping[str, str] | None = None,
        reference_date: date | datetime | None = None,
    ) -> int:
        """Remove old period data based on retention policies.

        Prunes entries older than the configured retention period for each
        time granularity. Does NOT prune all_time data.

        This method mutates `period_data` in place. Caller is responsible
        for persistence after calling this method.

        Args:
            period_data: Dictionary containing nested period structures.
            retention_config: Dict mapping period types to retention counts.
                            Example: {"daily": 90, "weekly": 52, ...}
                            Defaults to const.DEFAULT_RETENTION_* values.
            period_key_mapping: Optional mapping from logical period names to
                               data structure keys.
            reference_date: Date to calculate cutoffs from. Defaults to today.

        Returns:
            Total number of entries pruned.

        Example:
            pruned = stats.prune_history(
                chore_data["periods"],
                retention_config={"daily": 30, "weekly": 12, "monthly": 12, "yearly": 5},
            )
            # pruned = 15 (entries removed)
        """
        if reference_date is None:
            today = self._dt_today_local()
        elif isinstance(reference_date, datetime):
            today = reference_date.date()
        else:
            today = reference_date

        # Use defaults if not provided
        if retention_config is None:
            retention_config = DEFAULT_RETENTION

        # Default key mapping if not provided
        if period_key_mapping is None:
            period_key_mapping = {
                const.PERIOD_DAILY: const.PERIOD_DAILY,
                const.PERIOD_WEEKLY: const.PERIOD_WEEKLY,
                const.PERIOD_MONTHLY: const.PERIOD_MONTHLY,
                const.PERIOD_YEARLY: const.PERIOD_YEARLY,
            }

        total_pruned = 0

        # Daily: keep configured days
        daily_key = period_key_mapping.get(
            const.PERIOD_DAILY,
            const.PERIOD_DAILY,
        )
        retention_days = retention_config.get(
            const.PERIOD_DAILY,
            DEFAULT_RETENTION[const.PERIOD_DAILY],
        )
        cutoff_daily = (today - timedelta(days=retention_days)).strftime(
            const.PERIOD_FORMAT_DAILY
        )
        daily_data = period_data.get(daily_key, {})
        for day in list(daily_data.keys()):
            if day < cutoff_daily:
                del daily_data[day]
                total_pruned += 1

        # Weekly: keep configured weeks
        weekly_key = period_key_mapping.get(
            const.PERIOD_WEEKLY,
            const.PERIOD_WEEKLY,
        )
        retention_weeks = retention_config.get(
            const.PERIOD_WEEKLY,
            DEFAULT_RETENTION[const.PERIOD_WEEKLY],
        )
        cutoff_weekly = (today - timedelta(weeks=retention_weeks)).strftime(
            const.PERIOD_FORMAT_WEEKLY
        )
        weekly_data = period_data.get(weekly_key, {})
        for week in list(weekly_data.keys()):
            if week < cutoff_weekly:
                del weekly_data[week]
                total_pruned += 1

        # Monthly: keep configured months
        monthly_key = period_key_mapping.get(
            const.PERIOD_MONTHLY,
            const.PERIOD_MONTHLY,
        )
        retention_months = retention_config.get(
            const.PERIOD_MONTHLY,
            DEFAULT_RETENTION[const.PERIOD_MONTHLY],
        )
        # Calculate cutoff month (approximate with 30 days per month)
        cutoff_date = today - timedelta(days=retention_months * 30)
        cutoff_monthly = cutoff_date.strftime(const.PERIOD_FORMAT_MONTHLY)
        monthly_data = period_data.get(monthly_key, {})
        for month in list(monthly_data.keys()):
            if month < cutoff_monthly:
                del monthly_data[month]
                total_pruned += 1

        # Yearly: keep configured years
        yearly_key = period_key_mapping.get(
            const.PERIOD_YEARLY,
            const.PERIOD_YEARLY,
        )
        retention_years = retention_config.get(
            const.PERIOD_YEARLY,
            DEFAULT_RETENTION[const.PERIOD_YEARLY],
        )
        cutoff_yearly = str(today.year - retention_years)
        yearly_data = period_data.get(yearly_key, {})
        for year in list(yearly_data.keys()):
            if year < cutoff_yearly:
                del yearly_data[year]
                total_pruned += 1

        return total_pruned

    # ────────────────────────────────────────────────────────────────
    # Utility Methods
    # ────────────────────────────────────────────────────────────────

    def get_period_total(
        self,
        period_data: Mapping[str, Any],
        period_type: str,
        metric: str,
        period_key: str | None = None,
        period_key_mapping: Mapping[str, str] | None = None,
    ) -> int | float:
        """Get total value for a metric in a specific period.

        Args:
            period_data: Dictionary containing nested period structures.
            period_type: One of "daily", "weekly", "monthly", "yearly", "all_time".
            metric: The metric to retrieve (e.g., "approved", "points").
            period_key: Specific period key to look up. If None, uses current period.
            period_key_mapping: Optional key mapping for data structure.

        Returns:
            Value of the metric, or 0 if not found.

        Example:
            # Get today's approved count
            approved = stats.get_period_total(
                chore_data["periods"],
                "daily",
                "approved",
            )
        """
        if period_key_mapping is None:
            period_key_mapping = {
                const.PERIOD_DAILY: const.PERIOD_DAILY,
                const.PERIOD_WEEKLY: const.PERIOD_WEEKLY,
                const.PERIOD_MONTHLY: const.PERIOD_MONTHLY,
                const.PERIOD_YEARLY: const.PERIOD_YEARLY,
                const.PERIOD_ALL_TIME: const.PERIOD_ALL_TIME,
            }

        data_key = period_key_mapping.get(period_type, period_type)

        # Handle all_time specially (nested structure: all_time.all_time.metric)
        if period_type == const.PERIOD_ALL_TIME:
            all_time_bucket = period_data.get(data_key, {})
            all_time_entry = all_time_bucket.get(const.PERIOD_ALL_TIME, {})
            return all_time_entry.get(metric, 0)

        # Get period key if not provided
        if period_key is None:
            keys = self.get_period_keys()
            period_key = keys.get(period_type, "")

        return period_data.get(data_key, {}).get(period_key, {}).get(metric, 0)
