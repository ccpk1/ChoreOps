"""Tests for the badge streak repair service and its retained history.

A badge streak's count is destroyed when it breaks — `days_cycle_count` resets to
zero and badges keep no high-water mark — so the previous value is gone. This
suite covers the two halves that fix that:

- **Retaining the history**: a short per-day record of streak counts, keyed by
  LOCAL date, which keeps the pre-break value after the reset and self-describes
  when the break happened.
- **Repairing from it**: `repair_badge_streak` restores from that history or from an
  explicit count, and moves `last_update_day` back so the streak continues.

These are pure-logic tests against a seeded manager. The helpers only touch
`coordinator.assignees_data` / `badges_data`, so a MagicMock coordinator is enough
and no Home Assistant runtime is started.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any
from unittest.mock import MagicMock

from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.choreops import const
from custom_components.choreops.managers.gamification_manager import GamificationManager
from custom_components.choreops.utils.dt_utils import dt_today_iso, dt_today_local

BADGE_ID = "badge-1"
BADGE_NAME = "Wildfire Bronze"
ASSIGNEE_ID = "kid-1"
ASSIGNEE_NAME = "Zoë"


# =============================================================================
# Helpers
# =============================================================================


def _day_key(days_ago: int) -> str:
    """Local date key `days_ago` days before today.

    Derived rather than hardcoded so the assertions stay meaningful on any date.
    """
    return (dt_today_local() - timedelta(days=days_ago)).isoformat()


def _days_ago(day_iso: str) -> int:
    """How many days before today a local date key is."""
    return (date.fromisoformat(dt_today_iso()) - date.fromisoformat(day_iso)).days


@pytest.fixture
def manager() -> GamificationManager:
    """A GamificationManager with a mock coordinator and no seeded data."""
    hass = MagicMock()
    coordinator = MagicMock()
    coordinator.assignees_data = {}
    coordinator.badges_data = {}
    manager = GamificationManager(hass, coordinator)
    manager.coordinator._persist_and_update = MagicMock()
    return manager


def _seed_badge(
    manager: GamificationManager,
    *,
    progress: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Seed one badge and its progress, returning the progress dict.

    The progress dict is the live object held by the coordinator, so a test can
    assert against it directly after a repair.
    """
    seeded: dict[str, Any] = {
        const.DATA_USER_BADGE_PROGRESS_NAME: BADGE_NAME,
        const.DATA_USER_BADGE_PROGRESS_DAYS_CYCLE_COUNT: 0,
        const.DATA_USER_BADGE_PROGRESS_LAST_UPDATE_DAY: "",
        **(progress or {}),
    }
    manager.coordinator.assignees_data[ASSIGNEE_ID] = {
        const.DATA_USER_NAME: ASSIGNEE_NAME,
        const.DATA_USER_BADGE_PROGRESS: {BADGE_ID: seeded},
    }
    manager.coordinator.badges_data[BADGE_ID] = {
        const.DATA_BADGE_NAME: BADGE_NAME,
    }
    return seeded


def _history(progress: dict[str, Any]) -> dict[str, int]:
    """Read the retained history out of a progress dict."""
    return GamificationManager.get_badge_streak_history(progress)


# =============================================================================
# Retaining the history
# =============================================================================


class TestRecordBadgeStreakHistory:
    """The history records each day's count, keyed by local date."""

    def test_records_todays_count(self) -> None:
        """A day's count is stored under its local date key."""
        progress: dict[str, Any] = {}
        today = dt_today_iso()

        changed = GamificationManager.record_badge_streak_history(progress, 4, today)

        assert changed is True
        assert _history(progress) == {today: 4}
        assert _days_ago(today) == 0

    def test_reports_no_change_when_today_already_stored(self) -> None:
        """Re-recording the same value for today is a no-op, so persistence is not flagged."""
        today = dt_today_iso()
        progress: dict[str, Any] = {}

        GamificationManager.record_badge_streak_history(progress, 4, today)
        changed = GamificationManager.record_badge_streak_history(progress, 4, today)

        assert changed is False
        assert _history(progress) == {today: 4}

    def test_records_a_neutral_day_even_though_the_count_is_unchanged(self) -> None:
        """A day with an unchanged count still gets its own key.

        This is the reason recording is not gated on the caller's "did the count
        change" check: a neutral day leaves the count alone, but skipping its key
        would leave gaps and make "how many days ago" misleading.
        """
        progress: dict[str, Any] = {}

        GamificationManager.record_badge_streak_history(progress, 3, _day_key(1))
        GamificationManager.record_badge_streak_history(progress, 3, _day_key(0))

        assert _history(progress) == {_day_key(1): 3, _day_key(0): 3}

    def test_records_the_break_as_zero(self) -> None:
        """The break day records 0, while the earlier value survives alongside it."""
        progress: dict[str, Any] = {}

        GamificationManager.record_badge_streak_history(progress, 104, _day_key(1))
        GamificationManager.record_badge_streak_history(progress, 0, _day_key(0))

        assert _history(progress)[_day_key(0)] == 0
        assert max(_history(progress).values()) == 104


class TestPruneBadgeStreakHistory:
    """The history keeps only the most recent days."""

    def test_prunes_to_the_given_depth(self) -> None:
        """Older entries are dropped once the depth is exceeded."""
        history = {_day_key(offset): offset for offset in range(7)}

        pruned = GamificationManager.prune_badge_streak_history(
            history, const.DEFAULT_BADGE_STREAK_HISTORY_DAYS
        )

        assert len(pruned) == const.DEFAULT_BADGE_STREAK_HISTORY_DAYS
        assert set(pruned) == {_day_key(offset) for offset in range(5)}

    def test_prune_depth_is_a_parameter_not_hardcoded(self) -> None:
        """A different depth is honoured, proving the value is not baked in.

        Guards against the depth being hardcoded in logic or names, which would make
        changing it a code change rather than a constant change.
        """
        history = {_day_key(offset): offset for offset in range(7)}

        assert len(GamificationManager.prune_badge_streak_history(history, 2)) == 2
        assert len(GamificationManager.prune_badge_streak_history(history, 7)) == 7

    def test_zero_depth_retains_nothing(self) -> None:
        """A non-positive depth is treated as retaining nothing."""
        history = {_day_key(0): 1, _day_key(1): 2}

        assert GamificationManager.prune_badge_streak_history(history, 0) == {}

    def test_recording_prunes_automatically(self) -> None:
        """Recording past the depth drops the oldest entry."""
        progress: dict[str, Any] = {}

        for offset in range(const.DEFAULT_BADGE_STREAK_HISTORY_DAYS + 2):
            GamificationManager.record_badge_streak_history(
                progress, offset, _day_key(offset)
            )

        retained = _history(progress)
        assert len(retained) == const.DEFAULT_BADGE_STREAK_HISTORY_DAYS
        assert _day_key(const.DEFAULT_BADGE_STREAK_HISTORY_DAYS + 1) not in retained


class TestHistoryReadsDefensively:
    """A malformed history degrades to empty rather than breaking evaluation."""

    @pytest.mark.parametrize(
        ("stored", "case"),
        [
            pytest.param("not-a-dict", "string", id="string"),
            pytest.param(["a", "b"], "list", id="list"),
            pytest.param(None, "none", id="none"),
            pytest.param(7, "int", id="int"),
        ],
    )
    def test_non_dict_history_reads_as_empty(self, stored: Any, case: str) -> None:
        """A wrongly typed container yields an empty history."""
        assert (
            GamificationManager.get_badge_streak_history(
                {const.DATA_USER_BADGE_PROGRESS_STREAK_HISTORY: stored}
            )
            == {}
        ), case

    @pytest.mark.parametrize(
        ("stored", "case"),
        [
            pytest.param({_day_key(0): "4"}, "non-int-count", id="non-int-count"),
            pytest.param({_day_key(0): True}, "bool-count", id="bool-count"),
            pytest.param({_day_key(0): None}, "none-count", id="none-count"),
        ],
    )
    def test_non_integer_counts_are_skipped(
        self, stored: dict[str, Any], case: str
    ) -> None:
        """Entries with unusable counts are dropped, keeping the rest usable."""
        assert (
            GamificationManager.get_badge_streak_history(
                {const.DATA_USER_BADGE_PROGRESS_STREAK_HISTORY: stored}
            )
            == {}
        ), case

    def test_missing_key_reads_as_empty(self) -> None:
        """A progress record without the field yields an empty history."""
        assert GamificationManager.get_badge_streak_history({}) == {}

    def test_a_valid_entry_survives_a_malformed_neighbour(self) -> None:
        """One bad entry does not discard the good ones."""
        history = GamificationManager.get_badge_streak_history(
            {
                const.DATA_USER_BADGE_PROGRESS_STREAK_HISTORY: {
                    _day_key(0): 5,
                    _day_key(1): "bad",
                }
            }
        )

        assert history == {_day_key(0): 5}


# =============================================================================
# Repairing from retained history
# =============================================================================


class TestRepairFromHistory:
    """Omitting a count restores the highest retained value."""

    def test_restores_the_highest_retained_value(
        self, manager: GamificationManager
    ) -> None:
        """The pre-break value is what comes back, not the zero that replaced it."""
        progress = _seed_badge(
            manager,
            progress={
                const.DATA_USER_BADGE_PROGRESS_STREAK_HISTORY: {
                    _day_key(2): 41,
                    _day_key(1): 42,
                    _day_key(0): 0,
                }
            },
        )

        result = manager.repair_badge_streak(ASSIGNEE_ID, BADGE_ID)

        assert result["restored_count"] == 42
        assert result["source"] == "history"
        assert progress[const.DATA_USER_BADGE_PROGRESS_DAYS_CYCLE_COUNT] == 42

    def test_sets_last_update_day_to_yesterday(
        self, manager: GamificationManager
    ) -> None:
        """The anchor moves to yesterday so today advances rather than holding.

        Today would be read as "already counted" by the evaluator, which would hold
        the restored value instead of continuing the streak.
        """
        progress = _seed_badge(
            manager,
            progress={
                const.DATA_USER_BADGE_PROGRESS_STREAK_HISTORY: {_day_key(0): 0},
            },
        )

        manager.repair_badge_streak(ASSIGNEE_ID, BADGE_ID, count=12)

        stored_day = progress[const.DATA_USER_BADGE_PROGRESS_LAST_UPDATE_DAY]
        assert stored_day == _day_key(1)
        assert _days_ago(stored_day) == 1

    def test_persists_the_change(self, manager: GamificationManager) -> None:
        """The write goes through the coordinator, per CRUD ownership."""
        _seed_badge(
            manager,
            progress={const.DATA_USER_BADGE_PROGRESS_STREAK_HISTORY: {_day_key(0): 0}},
        )

        manager.repair_badge_streak(ASSIGNEE_ID, BADGE_ID, count=5)

        manager.coordinator._persist_and_update.assert_called()

    def test_response_reports_the_retained_history_sorted(
        self, manager: GamificationManager
    ) -> None:
        """The response carries date/value pairs, oldest first."""
        _seed_badge(
            manager,
            progress={
                const.DATA_USER_BADGE_PROGRESS_STREAK_HISTORY: {
                    _day_key(0): 0,
                    _day_key(2): 9,
                    _day_key(1): 10,
                }
            },
        )

        result = manager.repair_badge_streak(ASSIGNEE_ID, BADGE_ID)

        assert result["history"] == {
            _day_key(2): 9,
            _day_key(1): 10,
            _day_key(0): 0,
        }
        assert list(result["history"]) == sorted(result["history"])
        assert result["retention_days"] == const.DEFAULT_BADGE_STREAK_HISTORY_DAYS

    def test_reports_badge_and_assignee_identity(
        self, manager: GamificationManager
    ) -> None:
        """Identity is reported so a response is self-describing."""
        _seed_badge(
            manager,
            progress={const.DATA_USER_BADGE_PROGRESS_STREAK_HISTORY: {_day_key(0): 0}},
        )

        result = manager.repair_badge_streak(ASSIGNEE_ID, BADGE_ID, count=3)

        assert result["assignee_id"] == ASSIGNEE_ID
        assert result["assignee_name"] == ASSIGNEE_NAME
        assert result["badge_id"] == BADGE_ID
        assert result["badge_name"] == BADGE_NAME

    def test_assignee_and_badge_names_do_not_collide(
        self, manager: GamificationManager
    ) -> None:
        """Both names survive in one response.

        `DATA_USER_NAME` and `DATA_BADGE_NAME` are both `"name"`, so a response keyed
        on those constants would silently drop one of them. Pinned here because the
        collision is invisible in the payload dict and only shows up on read.
        """
        _seed_badge(
            manager,
            progress={const.DATA_USER_BADGE_PROGRESS_STREAK_HISTORY: {_day_key(0): 0}},
        )

        result = manager.repair_badge_streak(ASSIGNEE_ID, BADGE_ID, count=3)

        assert result["assignee_name"] != result["badge_name"]
        assert len({result["assignee_id"], result["badge_id"]}) == 2


# =============================================================================
# Repairing from an explicit count
# =============================================================================


class TestRepairWithExplicitCount:
    """A supplied count is used verbatim, with no cap."""

    def test_uses_the_supplied_count(self, manager: GamificationManager) -> None:
        """The supplied value wins over the retained history."""
        progress = _seed_badge(
            manager,
            progress={const.DATA_USER_BADGE_PROGRESS_STREAK_HISTORY: {_day_key(0): 15}},
        )

        result = manager.repair_badge_streak(ASSIGNEE_ID, BADGE_ID, count=100)

        assert result["restored_count"] == 100
        assert result["source"] == "manual"
        assert progress[const.DATA_USER_BADGE_PROGRESS_DAYS_CYCLE_COUNT] == 100

    def test_no_cap_is_applied(self, manager: GamificationManager) -> None:
        """A value above the retained maximum is accepted, per the agreed scope.

        There are deliberately no guards: an admin may set any value, including onto
        a live streak.
        """
        progress = _seed_badge(
            manager,
            progress={
                const.DATA_USER_BADGE_PROGRESS_DAYS_CYCLE_COUNT: 3,
                const.DATA_USER_BADGE_PROGRESS_STREAK_HISTORY: {_day_key(0): 3},
            },
        )

        result = manager.repair_badge_streak(ASSIGNEE_ID, BADGE_ID, count=999)

        assert result["restored_count"] == 999
        assert progress[const.DATA_USER_BADGE_PROGRESS_DAYS_CYCLE_COUNT] == 999

    def test_works_with_no_retained_history(self, manager: GamificationManager) -> None:
        """An explicit count does not require history, so pre-existing breaks are fixable."""
        _seed_badge(manager, progress={})

        result = manager.repair_badge_streak(ASSIGNEE_ID, BADGE_ID, count=7)

        assert result["restored_count"] == 7
        assert result["history"] == {}


# =============================================================================
# Refusals
# =============================================================================


class TestRepairRefusals:
    """Unusable targets are refused with a translated error."""

    def test_unknown_badge_is_refused(self, manager: GamificationManager) -> None:
        """A badge with no progress record cannot be repaired."""
        _seed_badge(manager)
        manager.coordinator.assignees_data[ASSIGNEE_ID][
            const.DATA_USER_BADGE_PROGRESS
        ] = {}

        with pytest.raises(HomeAssistantError) as err:
            manager.repair_badge_streak(ASSIGNEE_ID, BADGE_ID, count=1)

        assert err.value.translation_key == const.TRANS_KEY_ERROR_NOT_FOUND
        assert err.value.translation_placeholders == {
            "entity_type": const.LABEL_BADGE,
            "name": BADGE_NAME,
        }

    def test_non_streak_badge_is_refused(self, manager: GamificationManager) -> None:
        """A badge with no streak counter is refused by behaviour, not target type."""
        progress = _seed_badge(manager)
        progress.pop(const.DATA_USER_BADGE_PROGRESS_DAYS_CYCLE_COUNT)

        with pytest.raises(HomeAssistantError) as err:
            manager.repair_badge_streak(ASSIGNEE_ID, BADGE_ID, count=1)

        assert err.value.translation_key == const.TRANS_KEY_ERROR_BADGE_NOT_STREAK

    def test_empty_history_without_a_count_is_refused(
        self, manager: GamificationManager
    ) -> None:
        """Nothing to restore from is reported clearly rather than failing obscurely."""
        _seed_badge(manager, progress={})

        with pytest.raises(HomeAssistantError) as err:
            manager.repair_badge_streak(ASSIGNEE_ID, BADGE_ID)

        assert (
            err.value.translation_key
            == const.TRANS_KEY_ERROR_BADGE_STREAK_NOTHING_TO_RESTORE
        )


# =============================================================================
# The whole point: a restored streak continues
# =============================================================================


class TestRestoredStreakContinues:
    """A repaired streak is not merely written, it is live again."""

    def test_restored_anchor_is_one_day_back(
        self, manager: GamificationManager
    ) -> None:
        """Setting the anchor to yesterday leaves an empty window, clearing the break.

        The miss check anchors on `last_update_day`, so a window of
        `[yesterday, today)` contains no occurrence and the old break cannot be
        re-detected. This is what makes the repair stick rather than being undone on
        the next evaluation.
        """
        progress = _seed_badge(
            manager,
            progress={
                const.DATA_USER_BADGE_PROGRESS_STREAK_HISTORY: {_day_key(0): 0},
                const.DATA_USER_BADGE_PROGRESS_LAST_UPDATE_DAY: _day_key(9),
            },
        )

        manager.repair_badge_streak(ASSIGNEE_ID, BADGE_ID, count=20)

        stored_day = progress[const.DATA_USER_BADGE_PROGRESS_LAST_UPDATE_DAY]
        assert _days_ago(stored_day) == 1, "anchor must leave a one-day miss window"
