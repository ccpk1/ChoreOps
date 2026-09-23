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


_PAST_DUE = "2020-01-15T08:00:00+00:00"
_FUTURE_DUE = "2099-01-15T08:00:00+00:00"


def _build_chore_data(
    assignee_due_dates: dict[str, str | None],
    assignee_states: dict[str, str],
    *,
    completion_criteria: str | None = const.COMPLETION_CRITERIA_INDEPENDENT,
    chore_level_due_date: str | None = None,
    assigned_ids: list[str] | None = None,
    global_state: str = const.CHORE_STATE_OVERDUE,
) -> dict[str, Any]:
    """Build storage data for one chore with per-assignee due dates.

    ``assignee_due_dates`` insertion order is preserved to reproduce
    dict-order-sensitive scenarios. ``completion_criteria=None`` omits the key
    so default-resolution behavior can be exercised.
    """
    chore_id = "chore-1"
    ids = assigned_ids if assigned_ids is not None else list(assignee_due_dates)
    users = {
        assignee_id: {
            const.DATA_USER_CHORE_DATA: {
                chore_id: {
                    const.DATA_USER_CHORE_DATA_STATE: assignee_states.get(
                        assignee_id, const.CHORE_STATE_PENDING
                    )
                }
            }
        }
        for assignee_id in ids
    }
    chore: dict[str, Any] = {
        const.DATA_CHORE_INTERNAL_ID: chore_id,
        const.DATA_CHORE_ASSIGNED_USER_IDS: ids,
        const.DATA_CHORE_RECURRING_FREQUENCY: const.FREQUENCY_DAILY,
        const.DATA_CHORE_DUE_DATE: chore_level_due_date,
        const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES: dict(assignee_due_dates),
        const.DATA_CHORE_STATE: global_state,
    }
    if completion_criteria is not None:
        chore[const.DATA_CHORE_COMPLETION_CRITERIA] = completion_criteria
    return {
        const.DATA_USERS: users,
        const.DATA_CHORES: {chore_id: chore},
    }


def _build_independent_chore_data(
    assignee_due_dates: dict[str, str | None],
    assignee_states: dict[str, str],
    *,
    assigned_ids: list[str] | None = None,
    global_state: str = const.CHORE_STATE_OVERDUE,
) -> dict[str, Any]:
    """Build storage data for an INDEPENDENT chore with per-assignee due dates."""
    return _build_chore_data(
        assignee_due_dates,
        assignee_states,
        assigned_ids=assigned_ids,
        global_state=global_state,
    )


def _assignee_state(data: dict[str, Any], assignee_id: str) -> Any:
    """Return the persisted state of an assignee on the test chore."""
    return data[const.DATA_USERS][assignee_id][const.DATA_USER_CHORE_DATA]["chore-1"][
        const.DATA_USER_CHORE_DATA_STATE
    ]


def _no_change_summary() -> dict[str, int]:
    """Return the all-zero summary of a repair run that changed nothing."""
    return {
        "chores_sanitized": 0,
        "stale_due_dates_cleared": 0,
        "assignee_states_normalized": 0,
        "global_states_normalized": 0,
    }


@pytest.mark.parametrize(
    "assignee_due_dates",
    [
        pytest.param(
            {
                "child-1": _FUTURE_DUE,
                "child-2": _FUTURE_DUE,
                "child-3": _PAST_DUE,
                "child-4": _FUTURE_DUE,
                "child-5": _PAST_DUE,
            },
            id="future-dates-first",
        ),
        pytest.param(
            {
                "child-3": _PAST_DUE,
                "child-5": _PAST_DUE,
                "child-1": _FUTURE_DUE,
                "child-2": _FUTURE_DUE,
                "child-4": _FUTURE_DUE,
            },
            id="past-dates-first",
        ),
    ],
)
def test_preserves_per_assignee_overdue_with_own_past_due_date(
    assignee_due_dates: dict[str, str | None],
) -> None:
    """A valid overdue is judged against its own due date, not dict order.

    Issue #318: with divergent per-assignee due dates the repair must not
    reset an assignee whose own due date is already in the past, regardless
    of which due date appears first in the chore's mapping.
    """
    data = _build_independent_chore_data(
        assignee_due_dates,
        {"child-3": const.CHORE_STATE_OVERDUE},
    )

    summary = repair_impossible_due_state_residue(data)

    assert summary == _no_change_summary()
    assert _assignee_state(data, "child-3") == const.CHORE_STATE_OVERDUE


@pytest.mark.parametrize(
    "assignee_due_dates",
    [
        pytest.param(
            {
                "child-1": _FUTURE_DUE,
                "child-2": None,
                "child-3": _PAST_DUE,
            },
            id="future-dates-first",
        ),
        pytest.param(
            {
                "child-3": _PAST_DUE,
                "child-2": None,
                "child-1": _FUTURE_DUE,
            },
            id="past-dates-first",
        ),
    ],
)
def test_normalizes_only_assignees_whose_own_due_date_is_not_past(
    assignee_due_dates: dict[str, str | None],
) -> None:
    """Residue is cleared per assignee while a genuine overdue survives.

    Issue #318 mirror case: an assignee whose own due date is future or
    missing holds impossible residue and must be normalized even when another
    assignee on the same chore is legitimately overdue.
    """
    data = _build_independent_chore_data(
        assignee_due_dates,
        {
            "child-1": const.CHORE_STATE_OVERDUE,
            "child-2": const.CHORE_STATE_MISSED,
            "child-3": const.CHORE_STATE_OVERDUE,
        },
    )
    data[const.DATA_USERS]["child-1"][const.DATA_USER_CHORE_DATA]["chore-1"][
        const.DATA_USER_CHORE_DATA_OVERDUE_STARTED_AT
    ] = "2020-01-15T08:00:00+00:00"

    summary = repair_impossible_due_state_residue(data)

    assert summary == {
        "chores_sanitized": 1,
        "stale_due_dates_cleared": 0,
        "assignee_states_normalized": 2,
        "global_states_normalized": 0,
    }
    assert _assignee_state(data, "child-1") == const.CHORE_STATE_PENDING
    assert _assignee_state(data, "child-2") == const.CHORE_STATE_PENDING
    assert _assignee_state(data, "child-3") == const.CHORE_STATE_OVERDUE
    assert (
        const.DATA_USER_CHORE_DATA_OVERDUE_STARTED_AT
        not in data[const.DATA_USERS]["child-1"][const.DATA_USER_CHORE_DATA]["chore-1"]
    )
    # Genuine overdue on child-3 keeps the chore-level state legitimate.
    assert (
        data[const.DATA_CHORES]["chore-1"][const.DATA_CHORE_STATE]
        == const.CHORE_STATE_OVERDUE
    )


def test_preserves_missed_state_with_past_per_assignee_due_date() -> None:
    """A missed state shares the past-due-date legitimacy rule."""
    data = _build_independent_chore_data(
        {"child-1": _PAST_DUE},
        {"child-1": const.CHORE_STATE_MISSED},
        global_state=const.CHORE_STATE_MISSED,
    )

    summary = repair_impossible_due_state_residue(data)

    assert summary == _no_change_summary()
    assert _assignee_state(data, "child-1") == const.CHORE_STATE_MISSED
    assert (
        data[const.DATA_CHORES]["chore-1"][const.DATA_CHORE_STATE]
        == const.CHORE_STATE_MISSED
    )


def test_normalizes_residue_when_no_assignee_due_date_is_past() -> None:
    """Issue #248 residue cleanup still fires per assignee for INDEPENDENT chores."""
    data = _build_independent_chore_data(
        {"child-1": _FUTURE_DUE, "child-2": None},
        {
            "child-1": const.CHORE_STATE_OVERDUE,
            "child-2": const.CHORE_STATE_OVERDUE,
        },
    )

    summary = repair_impossible_due_state_residue(data)

    assert summary == {
        "chores_sanitized": 1,
        "stale_due_dates_cleared": 0,
        "assignee_states_normalized": 2,
        "global_states_normalized": 1,
    }
    assert _assignee_state(data, "child-1") == const.CHORE_STATE_PENDING
    assert _assignee_state(data, "child-2") == const.CHORE_STATE_PENDING
    assert (
        data[const.DATA_CHORES]["chore-1"][const.DATA_CHORE_STATE]
        == const.CHORE_STATE_PENDING
    )


def test_normalizes_global_residue_without_assigned_users() -> None:
    """A chore nobody is assigned to cannot be overdue for anyone.

    Lingering per-assignee due dates of removed users must not legitimize an
    impossible global overdue residue.
    """
    data = _build_independent_chore_data(
        {"child-1": _PAST_DUE},
        {},
        assigned_ids=[],
    )

    summary = repair_impossible_due_state_residue(data)

    assert summary == {
        "chores_sanitized": 1,
        "stale_due_dates_cleared": 0,
        "assignee_states_normalized": 0,
        "global_states_normalized": 1,
    }
    assert (
        data[const.DATA_CHORES]["chore-1"][const.DATA_CHORE_STATE]
        == const.CHORE_STATE_PENDING
    )


def test_per_assignee_repair_is_idempotent() -> None:
    """A second run over repaired data reports all zeros and changes nothing."""
    data = _build_independent_chore_data(
        {
            "child-1": _FUTURE_DUE,
            "child-2": None,
            "child-3": _PAST_DUE,
        },
        {
            "child-1": const.CHORE_STATE_OVERDUE,
            "child-2": const.CHORE_STATE_MISSED,
            "child-3": const.CHORE_STATE_OVERDUE,
        },
    )

    repair_impossible_due_state_residue(data)
    snapshot = deepcopy(data)
    second_summary = repair_impossible_due_state_residue(data)

    assert second_summary == _no_change_summary()
    assert data == snapshot


_CHORE_LEVEL_CRITERIA = [
    pytest.param(const.COMPLETION_CRITERIA_SHARED, id="shared-all"),
    pytest.param(const.COMPLETION_CRITERIA_SHARED_FIRST, id="shared-first"),
    pytest.param(const.COMPLETION_CRITERIA_ROTATION_SIMPLE, id="rotation-simple"),
    pytest.param(const.COMPLETION_CRITERIA_ROTATION_SMART, id="rotation-smart"),
    pytest.param(
        const.COMPLETION_CRITERIA_ROTATION_PRIMARY_STANDBY,
        id="rotation-primary-standby",
    ),
    pytest.param(
        const.COMPLETION_CRITERIA_ROTATION_SIMPLE_FROM_TURN_HOLDER,
        id="rotation-from-turn-holder",
    ),
]


def _assert_residue_gate(
    completion_criteria: str | None,
    *,
    genuine_chore_level_due: str | None,
    genuine_assignee_due: str | None,
    residue_chore_level_due: str | None,
    residue_assignee_due: str | None,
) -> None:
    """Assert overdue is kept only past its applicable due date.

    The unused due-date source (chore-level vs per-assignee map) carries the
    opposite verdict and must never leak into the decision.
    """
    kept = _build_chore_data(
        {"child-1": genuine_assignee_due},
        {"child-1": const.CHORE_STATE_OVERDUE},
        completion_criteria=completion_criteria,
        chore_level_due_date=genuine_chore_level_due,
    )
    assert repair_impossible_due_state_residue(kept) == _no_change_summary()
    assert _assignee_state(kept, "child-1") == const.CHORE_STATE_OVERDUE

    residue = _build_chore_data(
        {"child-1": residue_assignee_due},
        {"child-1": const.CHORE_STATE_OVERDUE},
        completion_criteria=completion_criteria,
        chore_level_due_date=residue_chore_level_due,
    )
    assert repair_impossible_due_state_residue(residue) == {
        "chores_sanitized": 1,
        "stale_due_dates_cleared": 0,
        "assignee_states_normalized": 1,
        "global_states_normalized": 1,
    }
    assert _assignee_state(residue, "child-1") == const.CHORE_STATE_PENDING


@pytest.mark.parametrize("completion_criteria", _CHORE_LEVEL_CRITERIA)
def test_chore_level_types_ignore_divergent_per_assignee_due_dates(
    completion_criteria: str,
) -> None:
    """Shared/rotation types judge overdue only against the chore-level due date.

    Covers all six chore-level completion criteria: a lingering per-assignee
    due-date map must never legitimize or invalidate their overdue states.
    """
    _assert_residue_gate(
        completion_criteria,
        genuine_chore_level_due=_PAST_DUE,
        genuine_assignee_due=_FUTURE_DUE,
        residue_chore_level_due=_FUTURE_DUE,
        residue_assignee_due=_PAST_DUE,
    )


def test_independent_ignores_chore_level_due_date() -> None:
    """INDEPENDENT judges each assignee only against their own map entry."""
    _assert_residue_gate(
        const.COMPLETION_CRITERIA_INDEPENDENT,
        genuine_chore_level_due=_FUTURE_DUE,
        genuine_assignee_due=_PAST_DUE,
        residue_chore_level_due=_PAST_DUE,
        residue_assignee_due=_FUTURE_DUE,
    )


def test_missing_completion_criteria_uses_per_assignee_due_dates() -> None:
    """A chore without a completion criteria key resolves like INDEPENDENT."""
    _assert_residue_gate(
        None,
        genuine_chore_level_due=_FUTURE_DUE,
        genuine_assignee_due=_PAST_DUE,
        residue_chore_level_due=_PAST_DUE,
        residue_assignee_due=_FUTURE_DUE,
    )


def test_unknown_completion_criteria_uses_chore_level_due_date() -> None:
    """An unrecognized completion criteria resolves by the chore-level due date.

    Matches ChoreEngine.get_due_date_for_assignee, which falls back to the
    chore-level date for anything except INDEPENDENT.
    """
    _assert_residue_gate(
        "legacy_custom",
        genuine_chore_level_due=_PAST_DUE,
        genuine_assignee_due=_FUTURE_DUE,
        residue_chore_level_due=_FUTURE_DUE,
        residue_assignee_due=_PAST_DUE,
    )


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
