"""Regression tests: "Due Today" count survives assignee removal.

Issue #205 — "Due Today" reports incorrectly after removing a user from a chore.

Bug scenario (metalblue's 100% reproduction):
  1. Create an Independent Chore assigned to multiple users
  2. Remove one user from the chore assignment
  3. Expected: "Due Today" decrements for the removed user
  4. Actual: "Due Today" stays the same

Root cause (two gaps):
  A. `chore_counts_toward_due_today_summary()` never checks whether the
     assignee is still in DATA_CHORE_ASSIGNED_USER_IDS.
  B. `update_chore()` does not clean up stale DATA_USER_CHORE_DATA entries
     from removed assignees, and `_refresh_chore_cache()` iterates those
     entries without verifying the assignment still exists.

These tests prove each gap independently.
"""

from __future__ import annotations

from types import MethodType, SimpleNamespace
from typing import Any

from custom_components.choreops import const
from custom_components.choreops.managers.chore_manager import ChoreManager
from custom_components.choreops.managers.statistics_manager import StatisticsManager

# =============================================================================
# Fix A: assignment guard in chore_counts_toward_due_today_summary
# =============================================================================


def test_chore_counts_toward_due_today_summary_excludes_unassigned() -> None:
    """FIX VERIFIED: method returns False when user is no longer assigned.

    The assignment guard checks DATA_CHORE_ASSIGNED_USER_IDS and returns
    False immediately if the assignee is not in the list, preventing stale
    DATA_USER_CHORE_DATA entries from inflating the "Due Today" count.
    """
    # ── Build a minimal ChoreManager ──────────────────────────────────────
    manager = object.__new__(ChoreManager)
    assignee_id = "zoe"
    chore_id = "make-bed"
    due_today = "2026-07-14T18:00:00+00:00"

    # The chore exists but the user is NOT in ASSIGNED_USER_IDS
    manager._coordinator = type(
        "FakeCoordinator",
        (),
        {
            "chores_data": {
                chore_id: {
                    const.DATA_CHORE_NAME: "Make bed",
                    const.DATA_CHORE_ASSIGNED_USER_IDS: [
                        "max",
                        "lila",
                    ],  # ← zoe NOT here!
                    const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
                    const.DATA_CHORE_APPLICABLE_DAYS: [],
                },
            },
        },
    )()

    # ── Status context: would normally be count-able ─────────────────────
    # PENDING + due today + claimable → would be included IF assigned
    status_context = {
        const.CHORE_CTX_STATE: const.CHORE_STATE_PENDING,
        const.CHORE_CTX_CLAIM_MODE: const.CHORE_CLAIM_MODE_CLAIMABLE,
        const.CHORE_CTX_IS_DUE: False,
        const.CHORE_CTX_DUE_DATE: due_today,
    }

    # ── Act ───────────────────────────────────────────────────────────────
    result = manager.chore_counts_toward_due_today_summary(
        assignee_id,
        chore_id,
        status_context=status_context,
        local_today_iso="2026-07-14",
    )

    # ── Assert: returns False because Zoe is NOT assigned ────────────────
    assert result is False, (
        "FIX FAILED: chore_counts_toward_due_today_summary() returned True "
        "for an unassigned user. The assignment guard may be missing or broken."
    )


# =============================================================================
# Fix A (end-to-end): _refresh_chore_cache uses the real guard
# =============================================================================


def test_refresh_chore_cache_excludes_stale_entries_via_real_method() -> None:
    """FIX VERIFIED: _refresh_chore_cache excludes stale entries end-to-end.

    Uses the real chore_counts_toward_due_today_summary (not a mock) to
    verify that the assignment guard works in the full cache refresh path.
    """
    # ── Build a StatisticsManager ─────────────────────────────────────────
    manager = StatisticsManager.__new__(StatisticsManager)
    assignee_id = "zoe"
    chore_id = "make-bed"

    # Build a real ChoreManager for the real method call
    chore_mgr = object.__new__(ChoreManager)
    chore_mgr._coordinator = SimpleNamespace(
        chores_data={
            chore_id: {
                const.DATA_CHORE_NAME: "Make bed",
                const.DATA_CHORE_ASSIGNED_USER_IDS: [
                    "max",
                    "lila",
                ],  # ← zoe NOT here!
                const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
                const.DATA_CHORE_APPLICABLE_DAYS: [],
            },
        },
        assignees_data={
            assignee_id: {
                const.DATA_USER_CHORE_DATA: {
                    chore_id: {
                        const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
                        const.DATA_USER_CHORE_DATA_NAME: "Make bed",
                        const.DATA_USER_CHORE_DATA_PERIODS: {},
                    },
                },
            },
        },
        users_data={
            assignee_id: {
                const.DATA_USER_CHORE_DATA: {
                    chore_id: {
                        const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_PENDING,
                        const.DATA_USER_CHORE_DATA_NAME: "Make bed",
                        const.DATA_USER_CHORE_DATA_PERIODS: {},
                    },
                },
            },
        },
    )
    # Wire the real method directly
    chore_mgr._parsed_due_datetime_cache = {}
    chore_mgr._offset_cache = {}
    chore_mgr._max_due_cache_entries = 1000

    # Wire the real chore_manager's coordinator with _data for
    # _is_chore_paused_for_assignee and friends.
    chores_dict = dict(chore_mgr._coordinator.chores_data)
    users_dict = dict(chore_mgr._coordinator.users_data)
    chore_mgr._coordinator._data = {
        const.DATA_CHORES: chores_dict,
        const.DATA_USERS: users_dict,
    }

    # Wire up the statistics manager with the real chore manager.
    manager._coordinator = SimpleNamespace(
        assignees_data=chore_mgr._coordinator.assignees_data,
        chores_data=chores_dict,
        chore_manager=chore_mgr,
    )
    manager.coordinator = manager._coordinator
    manager._stats_cache = {}

    # ── Monkey-patch internal helpers ─────────────────────────────────────
    def _get_assignee(
        _self: StatisticsManager, current_assignee_id: str
    ) -> dict[str, Any]:
        return _self._coordinator.assignees_data.get(current_assignee_id, {})

    def _get_domain_cache(
        _self: StatisticsManager, current_assignee_id: str, domain: str
    ) -> dict[str, Any]:
        entry = _self._stats_cache.setdefault(current_assignee_id, {})
        return entry.setdefault(domain, {})

    manager._get_assignee = MethodType(_get_assignee, manager)
    manager._get_domain_cache = MethodType(_get_domain_cache, manager)

    # ── Act ───────────────────────────────────────────────────────────────
    StatisticsManager._refresh_chore_cache(manager, assignee_id)

    # ── Assert: stale entry is correctly excluded from current_due_today ──
    stats = manager._stats_cache[assignee_id][const.CACHE_DOMAIN_CHORES]
    actual_due_today = stats[const.PRES_USER_CHORES_CURRENT_DUE_TODAY]

    assert actual_due_today == 0, (
        f"FIX FAILED: current_due_today={actual_due_today}, expected 0. "
        "The assignment guard in chore_counts_toward_due_today_summary() "
        "should have excluded the stale entry."
    )
