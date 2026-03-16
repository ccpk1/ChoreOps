"""Phase 4: Pipeline Guard Rails Tests.

Tests for duplicate processing detection, idempotency, and Gremlin prevention.
"""

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
import pytest

from custom_components.choreops import const
from custom_components.choreops.utils import dt_utils

from .helpers.constants import ATTR_GLOBAL_STATE, DATA_ASSIGNEE_NAME
from .helpers.setup import setup_from_yaml
from .helpers.workflows import find_chore, get_dashboard_helper

# =============================================================================
# HELPERS
# =============================================================================


def get_assignee_by_name(coordinator: Any, assignee_name: str) -> str | None:
    """Get assignee internal_id by name."""
    for assignee_id, assignee_data in coordinator.assignees_data.items():
        if assignee_data.get(DATA_ASSIGNEE_NAME) == assignee_name:
            return assignee_id
    return None


def get_chore_state_from_sensor(
    hass: HomeAssistant, assignee_slug: str, chore_name: str
) -> str:
    """Return the assignee-facing chore sensor state."""
    dashboard = get_dashboard_helper(hass, assignee_slug)
    chore = find_chore(dashboard, chore_name)
    if chore is None:
        return "not_found"

    chore_state = hass.states.get(chore["eid"])
    if chore_state is None:
        return "unavailable"

    return chore_state.state


def get_chore_global_state_from_sensor(
    hass: HomeAssistant, assignee_slug: str, chore_name: str
) -> str:
    """Return the chore sensor global_state attribute."""
    dashboard = get_dashboard_helper(hass, assignee_slug)
    chore = find_chore(dashboard, chore_name)
    if chore is None:
        return "not_found"

    chore_state = hass.states.get(chore["eid"])
    if chore_state is None:
        return "unavailable"

    return str(chore_state.attributes.get(ATTR_GLOBAL_STATE, ""))


# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def minimal_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
):
    """Load minimal scenario for Phase 4 tests."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


@pytest.fixture
async def shared_scenario(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
):
    """Load shared-first scenario for issue 28 regressions."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_shared.yaml",
    )


# =============================================================================
# TEST: IDEMPOTENCY
# =============================================================================


@pytest.mark.asyncio
async def test_idempotency_overdue_already_overdue(
    hass: HomeAssistant,
    minimal_scenario: Any,
) -> None:
    """Test Phase 4.3: _process_overdue skips if already OVERDUE.

    Scenario:
    1. Create pending chore with past due date
    2. Run periodic update → chore becomes OVERDUE
    3. Run periodic update again → should skip (idempotency)
    4. Verify only one state transition occurred
    """
    coordinator = minimal_scenario.coordinator

    # Get assignee
    assignee_id = get_assignee_by_name(coordinator, "Zoë")
    assert assignee_id, "Zoë should exist in minimal scenario"

    # Create chore without due date (avoids service validation)
    chore_response = await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_ADD_CHORE,
        {
            const.SERVICE_FIELD_NAME: "Idempotency Test Chore",
            const.SERVICE_FIELD_ASSIGNED_USER_IDS: ["Zoë"],
            const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_DAILY,
            const.SERVICE_FIELD_POINTS: 10,
            const.SERVICE_FIELD_OVERDUE_HANDLING: const.OVERDUE_HANDLING_AT_DUE_DATE,
        },
        blocking=True,
        return_response=True,
    )
    chore_id = chore_response[const.SERVICE_FIELD_CHORE_CRUD_ID]

    # Manually set past due date in storage (bypass service validation)
    past_date = (dt_utils.dt_now_local() - timedelta(days=2)).isoformat()
    chore = coordinator.chores_data[chore_id]
    chore[const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES] = {assignee_id: past_date}
    coordinator._persist()

    # First periodic update → should mark OVERDUE
    await coordinator.chore_manager._on_periodic_update(now_utc=dt_utils.dt_now_utc())
    await hass.async_block_till_done()

    # Verify OVERDUE
    chore = coordinator.chores_data[chore_id]
    assert chore[const.DATA_CHORE_STATE] == const.CHORE_STATE_OVERDUE

    # Second periodic update → should skip (idempotency)
    with patch("custom_components.choreops.const.LOGGER") as mock_logger:
        await coordinator.chore_manager._on_periodic_update(
            now_utc=dt_utils.dt_now_utc()
        )
        await hass.async_block_till_done()

        # Verify: Debug log shows skipped processing (idempotency check)
        mock_logger.debug.assert_called()
        assert any(
            "already OVERDUE" in str(call) for call in mock_logger.debug.call_args_list
        ), "Expected idempotency debug log"

    # Verify: Still OVERDUE after second run
    chore = coordinator.chores_data[chore_id]
    assert chore[const.DATA_CHORE_STATE] == const.CHORE_STATE_OVERDUE


@pytest.mark.asyncio
async def test_persist_enforces_canonical_schema_on_runtime_writes(
    hass: HomeAssistant,
    minimal_scenario: Any,
) -> None:
    """Runtime persist enforces canonical schema metadata."""
    coordinator = minimal_scenario.coordinator

    coordinator._data.pop(const.DATA_META, None)
    coordinator._data[const.DATA_SCHEMA_VERSION] = 31

    coordinator._persist(immediate=True)
    await hass.async_block_till_done()

    meta = coordinator._data.get(const.DATA_META, {})
    assert meta.get(const.DATA_META_SCHEMA_VERSION) == const.SCHEMA_VERSION_CURRENT
    assert const.DATA_SCHEMA_VERSION not in coordinator._data


@pytest.mark.asyncio
async def test_persist_schema_enforcement_can_be_bypassed_for_migration(
    hass: HomeAssistant,
    minimal_scenario: Any,
) -> None:
    """Migration persist path can opt out of runtime schema enforcement."""
    coordinator = minimal_scenario.coordinator

    coordinator._data.pop(const.DATA_META, None)
    coordinator._data[const.DATA_SCHEMA_VERSION] = 31

    coordinator._persist(immediate=True, enforce_schema=False)
    await hass.async_block_till_done()

    assert const.DATA_META not in coordinator._data
    assert coordinator._data.get(const.DATA_SCHEMA_VERSION) == 31


# =============================================================================
# TEST: GREMLIN PREVENTION
# =============================================================================


@pytest.mark.asyncio
async def test_gremlin1_prevention_overdue_after_approval(
    hass: HomeAssistant,
    minimal_scenario: Any,
) -> None:
    """Test Gremlin #1 Prevention: Overdue-After-Approval bug.

    Scenario (Phase 1 fixes this):
    1. Create chore with AT_MIDNIGHT_ONCE + past due date
    2. Claim and approve chore
    3. Run midnight rollover
    4. Expected: Chore resets to PENDING (not OVERDUE)
    5. Reason: Reset processes BEFORE overdue check
    """
    coordinator = minimal_scenario.coordinator

    # Get assignee
    assignee_id = get_assignee_by_name(coordinator, "Zoë")
    assert assignee_id, "Zoë should exist"

    # Create chore without due date (avoid service validation)
    chore_response = await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_ADD_CHORE,
        {
            const.SERVICE_FIELD_NAME: "Gremlin 1 Test Chore",
            const.SERVICE_FIELD_ASSIGNED_USER_IDS: ["Zoë"],
            const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_DAILY,
            const.SERVICE_FIELD_POINTS: 10,
            const.SERVICE_FIELD_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.SERVICE_FIELD_OVERDUE_HANDLING: const.OVERDUE_HANDLING_AT_DUE_DATE,
        },
        blocking=True,
        return_response=True,
    )
    chore_id = chore_response[const.SERVICE_FIELD_CHORE_CRUD_ID]

    # Manually set past due date in storage (bypass validation)
    past_date = (dt_utils.dt_now_local() - timedelta(hours=12)).isoformat()
    chore = coordinator.chores_data[chore_id]
    chore[const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES] = {assignee_id: past_date}
    coordinator._persist()

    # Claim and approve chore
    await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_CLAIM_CHORE,
        {
            const.SERVICE_FIELD_USER_NAME: "Zoë",
            const.SERVICE_FIELD_CHORE_NAME: "Gremlin 1 Test Chore",
        },
        blocking=True,
    )

    await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_APPROVE_CHORE,
        {
            const.SERVICE_FIELD_APPROVER_NAME: "Môm Astrid Stârblüm",
            const.SERVICE_FIELD_USER_NAME: "Zoë",
            const.SERVICE_FIELD_CHORE_NAME: "Gremlin 1 Test Chore",
        },
        blocking=True,
    )

    # Verify APPROVED
    chore = coordinator.chores_data[chore_id]
    assert chore[const.DATA_CHORE_STATE] == const.CHORE_STATE_APPROVED

    # Run midnight rollover
    await coordinator.chore_manager._on_midnight_rollover(now_utc=dt_utils.dt_now_utc())
    await hass.async_block_till_done()

    # Verify: Should be PENDING (not OVERDUE)
    # Phase 1 fix ensures reset processes BEFORE overdue check
    chore = coordinator.chores_data[chore_id]
    assert chore[const.DATA_CHORE_STATE] == const.CHORE_STATE_PENDING, (
        "Gremlin #1 Prevention: Chore should reset to PENDING (not OVERDUE) "
        "because reset processes BEFORE overdue check"
    )


@pytest.mark.asyncio
async def test_gremlin2_prevention_double_processing(
    hass: HomeAssistant,
    minimal_scenario: Any,
) -> None:
    """Test Gremlin #2 Prevention: Chore processed twice in one tick.

    Scenario (Phase 1 fixes this):
    1. Create chore that appears in BOTH reset and overdue lists
    2. Run midnight rollover
    3. Verify: Only reset happens (overdue filtered out)
    4. Reason: Set-based exclusion removes reset pairs from overdue list
    """
    coordinator = minimal_scenario.coordinator

    # Get assignee
    assignee_id = get_assignee_by_name(coordinator, "Zoë")
    assert assignee_id, "Zoë should exist"

    # Create chore with AT_MIDNIGHT reset (triggers during midnight rollover)
    # We'll claim it and make it past due so it appears in BOTH reset AND overdue lists
    chore_response = await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_ADD_CHORE,
        {
            const.SERVICE_FIELD_NAME: "Gremlin 2 Test Chore",
            const.SERVICE_FIELD_ASSIGNED_USER_IDS: ["Zoë"],
            const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_DAILY,
            const.SERVICE_FIELD_POINTS: 10,
            const.SERVICE_FIELD_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
            const.SERVICE_FIELD_OVERDUE_HANDLING: const.OVERDUE_HANDLING_AT_DUE_DATE,
        },
        blocking=True,
        return_response=True,
    )
    chore_id = chore_response[const.SERVICE_FIELD_CHORE_CRUD_ID]

    # Set past due date
    past_date = (dt_utils.dt_now_local() - timedelta(days=1)).isoformat()
    chore = coordinator.chores_data[chore_id]
    chore[const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES] = {assignee_id: past_date}
    coordinator._persist()

    # Claim the chore (now it's CLAIMED + past due → eligible for overdue list)
    await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_CLAIM_CHORE,
        {
            const.SERVICE_FIELD_USER_NAME: "Zoë",
            const.SERVICE_FIELD_CHORE_NAME: "Gremlin 2 Test Chore",
        },
        blocking=True,
    )

    # Verify CLAIMED
    chore = coordinator.chores_data[chore_id]
    assert chore[const.DATA_CHORE_STATE] == const.CHORE_STATE_CLAIMED

    # Run midnight with debug tracking enabled
    with patch.object(const, "DEBUG_PIPELINE_GUARDS", True):
        # Track state modifications
        coordinator.chore_manager._reset_pipeline_tracking()

        await coordinator.chore_manager._on_midnight_rollover(
            now_utc=dt_utils.dt_now_utc()
        )
        await hass.async_block_till_done()

        # Verify: Only ONE modification for this (assignee_id, chore_id) pair
        modifications = coordinator.chore_manager._pipeline_modified_pairs
        pair = (assignee_id, chore_id)
        assert pair in modifications, "Pair should be modified once"
        # Note: If Gremlin #2 occurred, pair would appear twice (reset + overdue)

    # Verify final state: PENDING (reset happened, overdue was filtered)
    chore = coordinator.chores_data[chore_id]
    assert chore[const.DATA_CHORE_STATE] == const.CHORE_STATE_PENDING, (
        "Gremlin #2 Prevention: Chore should be PENDING (reset happened, overdue filtered)"
    )


@pytest.mark.asyncio
async def test_gremlin3_prevention_non_recurring_past_due(
    hass: HomeAssistant,
    minimal_scenario: Any,
) -> None:
    """Test Gremlin #3 Prevention: Non-recurring chore goes OVERDUE after approval.

    Scenario (Phase 1 fixes this):
    1. Create FREQUENCY_NONE chore with UPON_COMPLETION reset
    2. Set past due date and approve
    3. Verify: Due date cleared (won't reschedule or go OVERDUE)
    4. Reason: _approve_chore_locked clears due_date for FREQUENCY_NONE + should_reset_immediately
    """
    coordinator = minimal_scenario.coordinator

    # Get assignee
    assignee_id = get_assignee_by_name(coordinator, "Zoë")
    assert assignee_id, "Zoë should exist"

    # Create non-recurring chore without due date
    chore_response = await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_ADD_CHORE,
        {
            const.SERVICE_FIELD_NAME: "Gremlin 3 Test Chore",
            const.SERVICE_FIELD_ASSIGNED_USER_IDS: ["Zoë"],
            const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_NONE,
            const.SERVICE_FIELD_POINTS: 10,
            const.SERVICE_FIELD_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_UPON_COMPLETION,
            const.SERVICE_FIELD_OVERDUE_HANDLING: const.OVERDUE_HANDLING_AT_DUE_DATE,
        },
        blocking=True,
        return_response=True,
    )
    chore_id = chore_response[const.SERVICE_FIELD_CHORE_CRUD_ID]

    # Manually set past due date before approval
    past_date = (dt_utils.dt_now_local() - timedelta(days=2)).isoformat()
    chore = coordinator.chores_data[chore_id]
    chore[const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES] = {assignee_id: past_date}
    coordinator._persist()

    # Verify chore has past due date before approval
    chore = coordinator.chores_data[chore_id]
    per_assignee_due_dates = chore.get(const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {})
    assert (
        assignee_id in per_assignee_due_dates
        and per_assignee_due_dates[assignee_id] is not None
    )

    # Claim and approve
    await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_CLAIM_CHORE,
        {
            const.SERVICE_FIELD_USER_NAME: "Zoë",
            const.SERVICE_FIELD_CHORE_NAME: "Gremlin 3 Test Chore",
        },
        blocking=True,
    )

    await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_APPROVE_CHORE,
        {
            const.SERVICE_FIELD_APPROVER_NAME: "Môm Astrid Stârblüm",
            const.SERVICE_FIELD_USER_NAME: "Zoë",
            const.SERVICE_FIELD_CHORE_NAME: "Gremlin 3 Test Chore",
        },
        blocking=True,
    )

    # Verify: Due date cleared (Phase 1 fix)
    chore = coordinator.chores_data[chore_id]
    per_assignee_due_dates = chore.get(const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {})
    assert (
        assignee_id not in per_assignee_due_dates
        or per_assignee_due_dates[assignee_id] is None
    ), "Gremlin #3 Prevention: Due date should be cleared for non-recurring chores"

    # Run periodic update - should NOT mark OVERDUE (no due date)
    await coordinator.chore_manager._on_periodic_update(now_utc=dt_utils.dt_now_utc())
    await hass.async_block_till_done()

    # Verify: Still PENDING (not OVERDUE)
    chore = coordinator.chores_data[chore_id]
    assert chore[const.DATA_CHORE_STATE] == const.CHORE_STATE_PENDING, (
        "Should be PENDING (no due date means can't go OVERDUE)"
    )


@pytest.mark.asyncio
async def test_gremlin_3_post_approval_sensor_state_does_not_stay_overdue(
    hass: HomeAssistant,
    minimal_scenario: Any,
) -> None:
    """Non-recurring immediate reset should publish non-overdue sensor state.

    This regression test targets the user-visible failure mode, not just the
    coordinator storage contract. After approval triggers an immediate reset and
    clears the stale due date, the chore sensor should no longer publish either
    assignee state or global_state as OVERDUE.
    """
    coordinator = minimal_scenario.coordinator

    assignee_id = get_assignee_by_name(coordinator, "Zoë")
    assert assignee_id, "Zoë should exist"

    chore_name = "Gremlin 3 Sensor Regression"
    chore_response = await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_ADD_CHORE,
        {
            const.SERVICE_FIELD_NAME: chore_name,
            const.SERVICE_FIELD_ASSIGNED_USER_IDS: ["Zoë"],
            const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_NONE,
            const.SERVICE_FIELD_POINTS: 10,
            const.SERVICE_FIELD_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_UPON_COMPLETION,
            const.SERVICE_FIELD_OVERDUE_HANDLING: const.OVERDUE_HANDLING_AT_DUE_DATE,
        },
        blocking=True,
        return_response=True,
    )
    chore_id = chore_response[const.SERVICE_FIELD_CHORE_CRUD_ID]

    past_date = (dt_utils.dt_now_local() - timedelta(days=2)).isoformat()
    chore = coordinator.chores_data[chore_id]
    chore[const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES] = {assignee_id: past_date}
    coordinator._persist()
    await hass.async_block_till_done()

    await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_CLAIM_CHORE,
        {
            const.SERVICE_FIELD_USER_NAME: "Zoë",
            const.SERVICE_FIELD_CHORE_NAME: chore_name,
        },
        blocking=True,
    )

    await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_APPROVE_CHORE,
        {
            const.SERVICE_FIELD_APPROVER_NAME: "Môm Astrid Stârblüm",
            const.SERVICE_FIELD_USER_NAME: "Zoë",
            const.SERVICE_FIELD_CHORE_NAME: chore_name,
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    chore = coordinator.chores_data[chore_id]
    per_assignee_due_dates = chore.get(const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES, {})
    assert (
        assignee_id not in per_assignee_due_dates
        or per_assignee_due_dates[assignee_id] is None
    ), "Due date should be cleared after immediate reset"

    assert (
        get_chore_state_from_sensor(hass, "zoe", chore_name)
        != const.CHORE_STATE_OVERDUE
    )
    assert (
        get_chore_global_state_from_sensor(hass, "zoe", chore_name)
        != const.CHORE_STATE_OVERDUE
    )
    assert chore[const.DATA_CHORE_STATE] != const.CHORE_STATE_OVERDUE


@pytest.mark.asyncio
async def test_issue_28_shared_first_blocked_peers_do_not_emit_overdue(
    hass: HomeAssistant,
    shared_scenario: Any,
) -> None:
    """Shared-first peers blocked by another claimer must not emit overdue events."""
    coordinator = shared_scenario.coordinator

    zoe_id = shared_scenario.assignee_ids["Zoë"]
    max_id = shared_scenario.assignee_ids["Max!"]
    lila_id = shared_scenario.assignee_ids["Lila"]
    chore_id = shared_scenario.chore_ids["Take out trash"]

    chore = coordinator.chores_data[chore_id]
    chore[const.DATA_CHORE_DUE_DATE] = (
        dt_utils.dt_now_local() - timedelta(hours=2)
    ).isoformat()
    chore[const.DATA_CHORE_OVERDUE_HANDLING_TYPE] = const.OVERDUE_HANDLING_AT_DUE_DATE
    chore[const.DATA_CHORE_APPROVAL_RESET_TYPE] = const.APPROVAL_RESET_AT_MIDNIGHT_ONCE
    chore[const.DATA_CHORE_RECURRING_FREQUENCY] = const.FREQUENCY_DAILY
    coordinator._persist()
    await hass.async_block_till_done()

    with patch(
        "custom_components.choreops.managers.notification_manager.async_send_notification",
        new=AsyncMock(),
    ):
        await coordinator.chore_manager.claim_chore(zoe_id, chore_id, "Zoë")
        await hass.async_block_till_done()

        assert (
            coordinator.chore_manager.get_chore_status_context(max_id, chore_id)[
                const.CHORE_CTX_STATE
            ]
            == "completed_by_other"
        )
        assert (
            coordinator.chore_manager.get_chore_status_context(lila_id, chore_id)[
                const.CHORE_CTX_STATE
            ]
            == "completed_by_other"
        )

        emitted_events: list[tuple[str, dict[str, Any]]] = []
        original_emit = coordinator.chore_manager.emit

        def tracking_emit(suffix: str, **kwargs: Any) -> None:
            emitted_events.append((suffix, kwargs))
            original_emit(suffix, **kwargs)

        coordinator.chore_manager.emit = tracking_emit
        try:
            await coordinator.chore_manager._on_periodic_update(
                now_utc=dt_utils.dt_now_utc()
            )
            await hass.async_block_till_done()
        finally:
            coordinator.chore_manager.emit = original_emit

    blocked_peer_overdue_events = [
        event
        for event in emitted_events
        if event[0] == const.SIGNAL_SUFFIX_CHORE_OVERDUE
        and event[1].get("chore_id") == chore_id
        and event[1].get("user_id") in {max_id, lila_id}
    ]
    assert blocked_peer_overdue_events == [], (
        "Blocked shared_first peers should not receive overdue events after "
        "another assignee has already claimed the chore"
    )


@pytest.mark.asyncio
async def test_issue_28_shared_first_claim_clears_peer_transient_notifications(
    hass: HomeAssistant,
    shared_scenario: Any,
) -> None:
    """Claiming a shared-first chore should clear stale peer transient notifications."""
    coordinator = shared_scenario.coordinator
    notification_manager = coordinator.notification_manager

    zoe_id = shared_scenario.assignee_ids["Zoë"]
    max_id = shared_scenario.assignee_ids["Max!"]
    lila_id = shared_scenario.assignee_ids["Lila"]
    chore_id = shared_scenario.chore_ids["Take out trash"]

    payload = {
        "user_id": zoe_id,
        "user_name": "Zoë",
        "chore_id": chore_id,
        "chore_name": "Take out trash",
    }

    with (
        patch.object(
            notification_manager,
            "notify_approvers_translated",
            new=AsyncMock(),
        ),
        patch.object(
            notification_manager,
            "_clear_assignee_chore_transient_notifications",
            new=AsyncMock(),
        ) as clear_actor_transients,
        patch.object(
            notification_manager,
            "_clear_reset_chore_notifications",
            new=AsyncMock(),
        ) as clear_peer_transients,
    ):
        await notification_manager._handle_chore_claimed(payload)

    clear_actor_transients.assert_awaited_once_with(zoe_id, chore_id)
    peer_clear_calls = {call.args for call in clear_peer_transients.await_args_list}
    assert peer_clear_calls == {
        (max_id, chore_id),
        (lila_id, chore_id),
    }, "Claim should clear stale peer notifications for blocked shared_first assignees"


@pytest.mark.asyncio
async def test_issue_28_shared_first_approval_clears_peer_transient_notifications(
    hass: HomeAssistant,
    shared_scenario: Any,
) -> None:
    """Approving a shared-first chore should clear stale peer transient notifications."""
    coordinator = shared_scenario.coordinator
    notification_manager = coordinator.notification_manager

    zoe_id = shared_scenario.assignee_ids["Zoë"]
    max_id = shared_scenario.assignee_ids["Max!"]
    lila_id = shared_scenario.assignee_ids["Lila"]
    chore_id = shared_scenario.chore_ids["Take out trash"]

    payload = {
        "user_id": zoe_id,
        "chore_id": chore_id,
        "chore_name": "Take out trash",
    }

    with (
        patch.object(
            notification_manager,
            "clear_notification_for_approvers",
            new=AsyncMock(),
        ),
        patch.object(
            notification_manager,
            "_clear_assignee_chore_transient_notifications",
            new=AsyncMock(),
        ) as clear_actor_transients,
        patch.object(
            notification_manager,
            "_clear_reset_chore_notifications",
            new=AsyncMock(),
        ) as clear_peer_transients,
    ):
        await notification_manager._handle_chore_approved(payload)

    clear_actor_transients.assert_awaited_once_with(zoe_id, chore_id)
    peer_clear_calls = {call.args for call in clear_peer_transients.await_args_list}
    assert peer_clear_calls == {
        (max_id, chore_id),
        (lila_id, chore_id),
    }, (
        "Approval should clear stale peer notifications for blocked shared_first assignees"
    )


@pytest.mark.asyncio
async def test_gremlin_3_immediate_reset_does_not_leave_stale_overdue_scan_window(
    hass: HomeAssistant,
    minimal_scenario: Any,
) -> None:
    """Immediate reset should clear stale due date before pending is scan-visible.

    Root-cause contract:
    when a non-recurring chore resets immediately on approval, there must not be
    an intermediate state where the chore has already been transitioned back to
    PENDING while the old past due date is still present. If that happens, a
    time scan built at that instant can still classify the chore as overdue.
    """
    coordinator = minimal_scenario.coordinator
    chore_manager = coordinator.chore_manager

    assignee_id = get_assignee_by_name(coordinator, "Zoë")
    assert assignee_id, "Zoë should exist"

    chore_name = "Gremlin 3 Scan Window Regression"
    chore_response = await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_ADD_CHORE,
        {
            const.SERVICE_FIELD_NAME: chore_name,
            const.SERVICE_FIELD_ASSIGNED_USER_IDS: ["Zoë"],
            const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_NONE,
            const.SERVICE_FIELD_POINTS: 10,
            const.SERVICE_FIELD_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_UPON_COMPLETION,
            const.SERVICE_FIELD_OVERDUE_HANDLING: const.OVERDUE_HANDLING_AT_DUE_DATE,
        },
        blocking=True,
        return_response=True,
    )
    chore_id = chore_response[const.SERVICE_FIELD_CHORE_CRUD_ID]

    past_date = (dt_utils.dt_now_local() - timedelta(days=2)).isoformat()
    chore = coordinator.chores_data[chore_id]
    chore[const.DATA_CHORE_PER_ASSIGNEE_DUE_DATES] = {assignee_id: past_date}
    coordinator._persist()
    await hass.async_block_till_done()

    await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_CLAIM_CHORE,
        {
            const.SERVICE_FIELD_USER_NAME: "Zoë",
            const.SERVICE_FIELD_CHORE_NAME: chore_name,
        },
        blocking=True,
    )

    original_transition = chore_manager._transition_chore_state

    def wrapped_transition(
        wrapped_assignee_id: str,
        wrapped_chore_id: str,
        new_state: str,
        *,
        reset_approval_period: bool = False,
        clear_ownership: bool = False,
        emit: bool = True,
        persist: bool = True,
    ) -> None:
        original_transition(
            wrapped_assignee_id,
            wrapped_chore_id,
            new_state,
            reset_approval_period=reset_approval_period,
            clear_ownership=clear_ownership,
            emit=emit,
            persist=persist,
        )

        if (
            wrapped_assignee_id != assignee_id
            or wrapped_chore_id != chore_id
            or new_state != const.CHORE_STATE_PENDING
        ):
            return

        scan = chore_manager.process_time_checks(
            dt_utils.dt_now_utc(),
            trigger=const.CHORE_SCAN_TRIGGER_DUE_DATE,
        )
        overdue_entries = [
            entry
            for entry in scan[const.CHORE_SCAN_RESULT_OVERDUE]
            if entry[const.CHORE_SCAN_ENTRY_CHORE_ID] == chore_id
            and entry[const.CHORE_SCAN_ENTRY_USER_ID] == assignee_id
        ]
        assert not overdue_entries, (
            "Immediate reset left a stale scan window where the chore was PENDING "
            "but still classified as overdue before the due date was cleared"
        )

    chore_manager._transition_chore_state = wrapped_transition
    try:
        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_APPROVE_CHORE,
            {
                const.SERVICE_FIELD_APPROVER_NAME: "Môm Astrid Stârblüm",
                const.SERVICE_FIELD_USER_NAME: "Zoë",
                const.SERVICE_FIELD_CHORE_NAME: chore_name,
            },
            blocking=True,
        )
    finally:
        chore_manager._transition_chore_state = original_transition


# =============================================================================
# TEST: DEBUG TRACKING
# =============================================================================


@pytest.mark.asyncio
async def test_debug_mode_tracking_warns_on_duplicate(
    hass: HomeAssistant,
    minimal_scenario: Any,
) -> None:
    """Test Phase 4.1: Debug mode tracks and warns on duplicate modifications.

    Scenario:
    1. Enable DEBUG_PIPELINE_GUARDS
    2. Manually call _track_state_modification twice for same pair
    3. Verify: Warning logged on second call
    """
    coordinator = minimal_scenario.coordinator

    assignee_id = get_assignee_by_name(coordinator, "Zoë")

    # Create a chore to get a valid chore_id
    chore_response = await hass.services.async_call(
        const.DOMAIN,
        const.SERVICE_ADD_CHORE,
        {
            const.SERVICE_FIELD_NAME: "Debug Tracking Test Chore",
            const.SERVICE_FIELD_ASSIGNED_USER_IDS: ["Zoë"],
            const.SERVICE_FIELD_FREQUENCY: const.FREQUENCY_DAILY,
            const.SERVICE_FIELD_POINTS: 10,
        },
        blocking=True,
        return_response=True,
    )
    chore_id = chore_response[const.SERVICE_FIELD_CHORE_CRUD_ID]

    assert assignee_id and chore_id, "Assignee and chore should exist"

    with (
        patch.object(const, "DEBUG_PIPELINE_GUARDS", True),
        patch.object(const.LOGGER, "warning") as mock_warning,
    ):
        # Reset tracking
        coordinator.chore_manager._reset_pipeline_tracking()

        # First modification - should be fine
        coordinator.chore_manager._track_state_modification(assignee_id, chore_id)

        # Second modification - should warn
        coordinator.chore_manager._track_state_modification(assignee_id, chore_id)

        # Verify warning logged
        assert mock_warning.called, "Should log warning on duplicate modification"
        warning_message = str(mock_warning.call_args)
        assert "GUARD RAIL VIOLATION" in warning_message
        assert "modified TWICE in single tick" in warning_message
