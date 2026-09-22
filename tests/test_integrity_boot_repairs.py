"""Tests for boot-time integrity repairs."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

import pytest

from custom_components.choreops import const
from custom_components.choreops.integrity import (
    repair_impossible_due_state_residue,
    repair_point_all_time_ledger,
    run_boot_repairs,
)

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


def _build_integrity_test_coordinator(data: dict[str, Any]) -> SimpleNamespace:
    """Build a minimal coordinator stub for integrity repair tests."""
    return SimpleNamespace(
        _data=data,
        config_entry=SimpleNamespace(
            entry_id="entry-1",
            options={const.CONF_SHOW_LEGACY_ENTITIES: False},
        ),
    )


@pytest.mark.asyncio
async def test_sanitizes_impossible_overdue_residue_without_due_date(
    hass: HomeAssistant,
) -> None:
    """Boot integrity clears stale overdue residue when no due date exists."""
    chore_id = "chore-1"
    assignee_id = "user-1"
    coordinator = _build_integrity_test_coordinator(
        {
            const.DATA_USERS: {
                assignee_id: {
                    const.DATA_USER_CHORE_DATA: {
                        chore_id: {
                            const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_OVERDUE,
                        }
                    }
                }
            },
            const.DATA_CHORES: {
                chore_id: {
                    const.DATA_CHORE_INTERNAL_ID: chore_id,
                    const.DATA_CHORE_ASSIGNED_USER_IDS: [assignee_id],
                    const.DATA_CHORE_COMPLETION_CRITERIA: (
                        const.COMPLETION_CRITERIA_SHARED_FIRST
                    ),
                    const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_NONE,
                    const.DATA_CHORE_DUE_DATE: None,
                    const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES: {
                        assignee_id: "2026-01-15T08:00:00+00:00"
                    },
                    const.DATA_CHORE_STATE: const.CHORE_STATE_OVERDUE,
                }
            },
        }
    )

    summary = repair_impossible_due_state_residue(coordinator._data)

    chore_data = coordinator._data[const.DATA_CHORES][chore_id]
    assignee_chore_data = coordinator._data[const.DATA_USERS][assignee_id][
        const.DATA_USER_CHORE_DATA
    ][chore_id]

    assert summary == {
        "chores_sanitized": 1,
        "stale_due_dates_cleared": 1,
        "assignee_states_normalized": 1,
        "global_states_normalized": 1,
    }
    assert chore_data[const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES][assignee_id] is None
    assert chore_data[const.DATA_CHORE_STATE] == const.CHORE_STATE_PENDING
    assert (
        assignee_chore_data[const.DATA_USER_CHORE_DATA_STATE]
        == const.CHORE_STATE_PENDING
    )


@pytest.mark.asyncio
async def test_preserves_claimed_state_without_due_date(
    hass: HomeAssistant,
) -> None:
    """Boot integrity keeps valid claimed state while fixing impossible global overdue."""
    chore_id = "chore-1"
    assignee_id = "user-1"
    coordinator = _build_integrity_test_coordinator(
        {
            const.DATA_USERS: {
                assignee_id: {
                    const.DATA_USER_CHORE_DATA: {
                        chore_id: {
                            const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_CLAIMED,
                        }
                    }
                }
            },
            const.DATA_CHORES: {
                chore_id: {
                    const.DATA_CHORE_INTERNAL_ID: chore_id,
                    const.DATA_CHORE_ASSIGNED_USER_IDS: [assignee_id],
                    const.DATA_CHORE_COMPLETION_CRITERIA: (
                        const.COMPLETION_CRITERIA_SHARED_FIRST
                    ),
                    const.DATA_CHORE_DUE_DATE: None,
                    const.DATA_CHORE_STATE: const.CHORE_STATE_OVERDUE,
                }
            },
        }
    )

    summary = repair_impossible_due_state_residue(coordinator._data)

    chore_data = coordinator._data[const.DATA_CHORES][chore_id]
    assignee_chore_data = coordinator._data[const.DATA_USERS][assignee_id][
        const.DATA_USER_CHORE_DATA
    ][chore_id]

    assert summary == {
        "chores_sanitized": 1,
        "stale_due_dates_cleared": 0,
        "assignee_states_normalized": 0,
        "global_states_normalized": 1,
    }
    assert chore_data[const.DATA_CHORE_STATE] == const.CHORE_STATE_CLAIMED
    assert (
        assignee_chore_data[const.DATA_USER_CHORE_DATA_STATE]
        == const.CHORE_STATE_CLAIMED
    )


@pytest.mark.asyncio
async def test_sanitizes_stale_overdue_with_future_due_date(
    hass: HomeAssistant,
) -> None:
    """Boot integrity clears stale overdue residue when the due date is in the future.

    Issue #248: a shared_all chore whose due date moved to the future but whose
    per-assignee persisted states remain `overdue` (from a prior cycle) must be
    normalized to `pending`. The prior guard skipped chores WITH an active due date.
    """
    chore_id = "chore-1"
    assignee_id = "user-1"
    coordinator = _build_integrity_test_coordinator(
        {
            const.DATA_USERS: {
                assignee_id: {
                    const.DATA_USER_CHORE_DATA: {
                        chore_id: {
                            const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_OVERDUE,
                        }
                    }
                }
            },
            const.DATA_CHORES: {
                chore_id: {
                    const.DATA_CHORE_INTERNAL_ID: chore_id,
                    const.DATA_CHORE_ASSIGNED_USER_IDS: [assignee_id],
                    const.DATA_CHORE_COMPLETION_CRITERIA: (
                        const.COMPLETION_CRITERIA_SHARED
                    ),
                    const.DATA_CHORE_DUE_DATE: "2099-01-15T08:00:00+00:00",
                    const.DATA_CHORE_STATE: const.CHORE_STATE_OVERDUE,
                }
            },
        }
    )

    summary = repair_impossible_due_state_residue(coordinator._data)

    chore_data = coordinator._data[const.DATA_CHORES][chore_id]
    assignee_chore_data = coordinator._data[const.DATA_USERS][assignee_id][
        const.DATA_USER_CHORE_DATA
    ][chore_id]

    assert summary["assignee_states_normalized"] == 1
    assert summary["chores_sanitized"] == 1
    assert (
        assignee_chore_data[const.DATA_USER_CHORE_DATA_STATE]
        == const.CHORE_STATE_PENDING
    )
    assert chore_data[const.DATA_CHORE_STATE] == const.CHORE_STATE_PENDING


@pytest.mark.asyncio
async def test_preserves_genuine_overdue_with_past_due_date(
    hass: HomeAssistant,
) -> None:
    """Boot integrity keeps a legitimate overdue when the due date is in the past."""
    chore_id = "chore-1"
    assignee_id = "user-1"
    coordinator = _build_integrity_test_coordinator(
        {
            const.DATA_USERS: {
                assignee_id: {
                    const.DATA_USER_CHORE_DATA: {
                        chore_id: {
                            const.DATA_USER_CHORE_DATA_STATE: const.CHORE_STATE_OVERDUE,
                        }
                    }
                }
            },
            const.DATA_CHORES: {
                chore_id: {
                    const.DATA_CHORE_INTERNAL_ID: chore_id,
                    const.DATA_CHORE_ASSIGNED_USER_IDS: [assignee_id],
                    const.DATA_CHORE_COMPLETION_CRITERIA: (
                        const.COMPLETION_CRITERIA_SHARED
                    ),
                    const.DATA_CHORE_DUE_DATE: "2020-01-15T08:00:00+00:00",
                    const.DATA_CHORE_STATE: const.CHORE_STATE_OVERDUE,
                }
            },
        }
    )

    summary = repair_impossible_due_state_residue(coordinator._data)

    chore_data = coordinator._data[const.DATA_CHORES][chore_id]
    assignee_chore_data = coordinator._data[const.DATA_USERS][assignee_id][
        const.DATA_USER_CHORE_DATA
    ][chore_id]

    # Genuine overdue (past due date) must NOT be normalized.
    assert summary["assignee_states_normalized"] == 0
    assert (
        assignee_chore_data[const.DATA_USER_CHORE_DATA_STATE]
        == const.CHORE_STATE_OVERDUE
    )
    assert chore_data[const.DATA_CHORE_STATE] == const.CHORE_STATE_OVERDUE


_EMPTY_LEDGER_SUMMARY = {
    "assignees_repaired": 0,
    "ledger_gaps_folded": 0,
    "history_nets_folded": 0,
    "history_signs_fixed": 0,
    "history_sign_fixes_deferred": 0,
    "highest_floored": 0,
}


def _build_point_user(
    balance: float,
    earned: float,
    spent: float,
    highest: float,
    by_source: dict[str, float],
) -> dict[str, Any]:
    """Build a user payload carrying an all-time point ledger."""
    return {
        const.DATA_USER_POINTS: balance,
        const.DATA_USER_POINT_PERIODS: {
            const.DATA_USER_POINT_PERIODS_ALL_TIME: {
                const.PERIOD_ALL_TIME: {
                    const.DATA_USER_POINT_PERIOD_POINTS_EARNED: earned,
                    const.DATA_USER_POINT_PERIOD_POINTS_SPENT: spent,
                    const.DATA_USER_POINT_PERIOD_HIGHEST_BALANCE: highest,
                    const.DATA_USER_POINT_PERIOD_BY_SOURCE: dict(by_source),
                }
            }
        },
    }


def _all_time_entry(user: dict[str, Any]) -> dict[str, Any]:
    """Return the all-time ledger entry from a user payload."""
    periods: dict[str, Any] = user[const.DATA_USER_POINT_PERIODS]
    bucket: dict[str, Any] = periods[const.DATA_USER_POINT_PERIODS_ALL_TIME]
    return bucket[const.PERIOD_ALL_TIME]


def test_point_ledger_repair_reconciles_legacy_migrated_data() -> None:
    """Legacy fabricated ledger is repaired to full reconciliation (issue #306).

    Fixture mirrors the reported instance: balance 366, migration-fabricated
    earned 767 / spent -401, and by_source history summing to -156.
    """
    user = _build_point_user(
        balance=366.0,
        earned=767.0,
        spent=-401.0,
        highest=767.0,
        by_source={
            const.POINTS_SOURCE_CHORES: 724.0,
            const.POINTS_SOURCE_REWARDS: -880.0,
        },
    )
    data = {const.DATA_USERS: {"user-1": user}}

    summary = repair_point_all_time_ledger(data)

    entry = _all_time_entry(user)
    by_source: dict[str, float] = entry[const.DATA_USER_POINT_PERIOD_BY_SOURCE]
    positive = sum(value for value in by_source.values() if value > 0)
    negative = sum(value for value in by_source.values() if value < 0)

    assert summary == {
        "assignees_repaired": 1,
        "ledger_gaps_folded": 0,
        "history_nets_folded": 1,
        "history_signs_fixed": 1,
        "history_sign_fixes_deferred": 0,
        "highest_floored": 0,
    }
    # The ledger already balanced against the balance, so earned/spent stay.
    assert entry[const.DATA_USER_POINT_PERIOD_POINTS_EARNED] == 767.0
    assert entry[const.DATA_USER_POINT_PERIOD_POINTS_SPENT] == -401.0
    # All three views now agree: balance == earned + spent == sum(by_source).
    assert round(positive, 2) == 767.0
    assert round(negative, 2) == -401.0
    assert round(positive + negative, 2) == user[const.DATA_USER_POINTS]
    # Category history on the positive side is untouched; only generic
    # carriers and the overstated negative side absorb the reconciliation.
    assert by_source[const.POINTS_SOURCE_CHORES] == 724.0
    assert by_source[const.POINTS_SOURCE_OTHER] == 43.0
    assert by_source[const.POINTS_SOURCE_REWARDS] == -401.0


def test_point_ledger_repair_is_idempotent() -> None:
    """A second run over repaired data reports all zeros and changes nothing."""
    user = _build_point_user(
        balance=366.0,
        earned=767.0,
        spent=-401.0,
        highest=767.0,
        by_source={
            const.POINTS_SOURCE_CHORES: 724.0,
            const.POINTS_SOURCE_REWARDS: -880.0,
        },
    )
    data = {const.DATA_USERS: {"user-1": user}}

    repair_point_all_time_ledger(data)
    snapshot = deepcopy(user)
    second_summary = repair_point_all_time_ledger(data)

    assert second_summary == _EMPTY_LEDGER_SUMMARY
    assert user == snapshot


def test_point_ledger_repair_raises_earned_over_unrecorded_balance() -> None:
    """A balance with no matching ledger raises earned, never lowers it.

    Cumulative badge progress reads earned from storage, so the repair must
    only push earned up to cover balance that provably exists.
    """
    user = _build_point_user(
        balance=100.0, earned=0.0, spent=0.0, highest=0.0, by_source={}
    )

    summary = repair_point_all_time_ledger({const.DATA_USERS: {"user-1": user}})

    entry = _all_time_entry(user)
    assert entry[const.DATA_USER_POINT_PERIOD_POINTS_EARNED] == 100.0
    assert entry[const.DATA_USER_POINT_PERIOD_POINTS_SPENT] == 0.0
    assert entry[const.DATA_USER_POINT_PERIOD_HIGHEST_BALANCE] == 100.0
    assert entry[const.DATA_USER_POINT_PERIOD_BY_SOURCE] == {
        const.POINTS_SOURCE_OTHER: 100.0
    }
    assert summary["assignees_repaired"] == 1
    assert summary["ledger_gaps_folded"] == 1
    assert summary["history_nets_folded"] == 1
    assert summary["highest_floored"] == 1


def test_point_ledger_repair_grows_positive_history_with_carriers() -> None:
    """When earned exceeds positive history, generic carriers absorb the gap."""
    user = _build_point_user(
        balance=70.0,
        earned=100.0,
        spent=-30.0,
        highest=100.0,
        by_source={const.POINTS_SOURCE_MANUAL: 70.0},
    )

    summary = repair_point_all_time_ledger({const.DATA_USERS: {"user-1": user}})

    entry = _all_time_entry(user)
    by_source: dict[str, float] = entry[const.DATA_USER_POINT_PERIOD_BY_SOURCE]
    positive = sum(value for value in by_source.values() if value > 0)
    negative = sum(value for value in by_source.values() if value < 0)

    assert positive == 100.0
    assert negative == -30.0
    assert round(positive + negative, 2) == 70.0
    # The existing generic entry grows; a free generic carrier covers the
    # missing negative side without touching category sources.
    assert by_source[const.POINTS_SOURCE_MANUAL] == 100.0
    assert by_source[const.POINTS_SOURCE_OTHER] == -30.0
    assert summary["history_signs_fixed"] == 1
    assert summary["history_sign_fixes_deferred"] == 0


def test_point_ledger_repair_skips_empty_payloads() -> None:
    """Users without point data and empty stores are left untouched."""
    user: dict[str, Any] = {}

    summary = repair_point_all_time_ledger({const.DATA_USERS: {"user-1": user}})
    empty_summary = repair_point_all_time_ledger({})

    assert summary == _EMPTY_LEDGER_SUMMARY
    assert empty_summary == _EMPTY_LEDGER_SUMMARY
    assert user == {}


def test_point_ledger_repair_registered_in_boot_repairs() -> None:
    """run_boot_repairs exposes the ledger repair alongside existing repairs."""
    summaries = run_boot_repairs({})

    assert summaries["repair_point_all_time_ledger"] == _EMPTY_LEDGER_SUMMARY
    assert "repair_impossible_due_state_residue" in summaries
