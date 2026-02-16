"""Tests for ChoreManager - stateful chore workflow orchestration.

Tests verify:
- Claim, approve, disapprove, undo, reset workflows
- Race condition protection via locks
- Event emission
- Integration with EconomyManager
"""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock

from homeassistant.exceptions import ServiceValidationError
import pytest

from custom_components.kidschores import const, data_builders as db
from custom_components.kidschores.engines.chore_engine import TransitionEffect
from custom_components.kidschores.managers.chore_manager import ChoreManager
from custom_components.kidschores.utils.dt_utils import dt_now_utc

if TYPE_CHECKING:
    from custom_components.kidschores.type_defs import ResetContext, ResetDecision

# ============================================================================
# Test Fixtures
# ============================================================================


@pytest.fixture
def mock_hass() -> MagicMock:
    """Create mock Home Assistant instance."""
    hass = MagicMock()

    # Use a proper handler that cancels the coroutine to avoid warnings
    def handle_create_task(coro):
        """Mock async_create_task that properly closes coroutines."""
        coro.close()  # Close the coroutine to avoid 'never awaited' warning
        return MagicMock()  # Return a mock task

    hass.async_create_task = MagicMock(side_effect=handle_create_task)
    return hass


@pytest.fixture
def sample_chore_data() -> dict[str, Any]:
    """Create sample chore data."""
    return {
        const.DATA_CHORE_NAME: "Wash Dishes",
        const.DATA_CHORE_DEFAULT_POINTS: 10.0,
        const.DATA_CHORE_ASSIGNED_KIDS: ["kid-1", "kid-2"],
        const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        const.DATA_CHORE_APPROVAL_RESET_TYPE: const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
        const.DATA_CHORE_AUTO_APPROVE: False,
        const.DATA_CHORE_LABELS: ["kitchen", "daily"],
    }


@pytest.fixture
def sample_kid_data() -> dict[str, Any]:
    """Create sample kid data."""
    return {
        const.DATA_KID_NAME: "Alice",
        const.DATA_KID_POINTS_MULTIPLIER: 1.0,
        const.DATA_KID_CHORE_DATA: {},
    }


@pytest.fixture
def mock_coordinator(sample_chore_data: dict, sample_kid_data: dict) -> MagicMock:
    """Create mock coordinator with sample data."""
    coordinator = MagicMock()
    coordinator.config_entry.entry_id = "test-entry-123"
    coordinator.chores_data = {"chore-1": sample_chore_data}
    coordinator.kids_data = {
        "kid-1": sample_kid_data.copy(),
        "kid-2": {
            const.DATA_KID_NAME: "Bob",
            const.DATA_KID_POINTS_MULTIPLIER: 1.5,
            const.DATA_KID_CHORE_DATA: {},
        },
    }
    coordinator._persist = MagicMock()
    coordinator._persist_and_update = MagicMock()
    coordinator.async_set_updated_data = MagicMock()
    # Include chores data for tests that access _data[DATA_CHORES]
    coordinator._data = {
        const.DATA_CHORES: {"chore-1": sample_chore_data.copy()},
    }

    # Mock chore_is_approved_in_period
    coordinator.chore_is_approved_in_period = MagicMock(return_value=False)

    return coordinator


@pytest.fixture
def chore_manager(
    mock_hass: MagicMock,
    mock_coordinator: MagicMock,
) -> ChoreManager:
    """Create ChoreManager instance with mocks."""
    manager = ChoreManager(mock_hass, mock_coordinator)
    # Mock the emit method to track events
    manager.emit = MagicMock()
    return manager


# ============================================================================
# Test Class: Basic Validation
# ============================================================================


class TestValidation:
    """Tests for entity validation."""

    def test_validate_kid_and_chore_success(self, chore_manager: ChoreManager) -> None:
        """Test validation passes for existing entities."""
        # Should not raise
        chore_manager._validate_kid_and_chore("kid-1", "chore-1")

    def test_validate_chore_not_found(self, chore_manager: ChoreManager) -> None:
        """Test validation fails for missing chore."""
        from homeassistant.exceptions import HomeAssistantError

        with pytest.raises(HomeAssistantError) as exc_info:
            chore_manager._validate_kid_and_chore("kid-1", "invalid-chore")

        assert exc_info.value.translation_key == const.TRANS_KEY_ERROR_NOT_FOUND

    def test_validate_kid_not_found(self, chore_manager: ChoreManager) -> None:
        """Test validation fails for missing kid."""
        from homeassistant.exceptions import HomeAssistantError

        with pytest.raises(HomeAssistantError) as exc_info:
            chore_manager._validate_kid_and_chore("invalid-kid", "chore-1")

        assert exc_info.value.translation_key == const.TRANS_KEY_ERROR_NOT_FOUND


class TestTimeScanCache:
    """Tests for Phase 3 time-scan caching helpers."""

    def test_parse_due_datetime_cache_reuses_dt_to_utc(
        self,
        chore_manager: ChoreManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Same due string should be parsed only once."""
        calls = {"count": 0}

        def _fake_dt_to_utc(_value: str | None):
            calls["count"] += 1
            return dt_now_utc()

        monkeypatch.setattr(
            "custom_components.kidschores.managers.chore_manager.dt_to_utc",
            _fake_dt_to_utc,
        )

        due_str = "2026-01-01T10:00:00+00:00"
        first = chore_manager._parse_due_datetime_cached(due_str)
        second = chore_manager._parse_due_datetime_cached(due_str)

        assert first is not None
        assert second is not None
        assert calls["count"] == 1

    def test_get_chore_offsets_cached_reuses_parsed_offsets(
        self,
        chore_manager: ChoreManager,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Offset parsing should run once when chore strings are unchanged."""
        calls = {"count": 0}

        def _fake_parse_duration(_value: str | None):
            calls["count"] += 1
            return timedelta(hours=1)

        monkeypatch.setattr(
            "custom_components.kidschores.managers.chore_manager.dt_parse_duration",
            _fake_parse_duration,
        )

        chore_info = {
            const.DATA_CHORE_DUE_WINDOW_OFFSET: "P1DT0H",
            const.DATA_CHORE_DUE_REMINDER_OFFSET: "PT4H",
        }

        first = chore_manager._get_chore_offsets_cached("chore-1", chore_info)
        second = chore_manager._get_chore_offsets_cached("chore-1", chore_info)

        assert first == second
        assert calls["count"] == 2

    @pytest.mark.asyncio
    async def test_time_scan_signal_handler_clears_caches(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Mutation signal handler should clear due and offset caches."""
        chore_manager._parsed_due_datetime_cache["2026-01-01T00:00:00+00:00"] = (
            dt_now_utc()
        )
        chore_manager._offset_cache["chore-1"] = (
            "P1DT0H",
            "PT4H",
            timedelta(days=1),
            timedelta(hours=4),
        )

        await chore_manager._on_time_scan_inputs_changed({"chore_id": "chore-1"})

        assert chore_manager._parsed_due_datetime_cache == {}
        assert chore_manager._offset_cache == {}


class TestResetPolicyDecision:
    """Table-driven tests for reset policy decision helper."""

    @pytest.mark.parametrize(
        ("context", "expected"),
        [
            pytest.param(
                {
                    "trigger": const.CHORE_RESET_TRIGGER_APPROVAL,
                    "approval_reset_type": const.APPROVAL_RESET_UPON_COMPLETION,
                    "overdue_handling_type": const.DEFAULT_OVERDUE_HANDLING_TYPE,
                    "completion_criteria": const.COMPLETION_CRITERIA_INDEPENDENT,
                },
                const.CHORE_RESET_DECISION_RESET_AND_RESCHEDULE,
                id="approval-upon-completion-independent",
            ),
            pytest.param(
                {
                    "trigger": const.CHORE_RESET_TRIGGER_APPROVAL,
                    "approval_reset_type": const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
                    "overdue_handling_type": const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE,
                    "approval_after_reset": True,
                    "completion_criteria": const.COMPLETION_CRITERIA_SHARED,
                    "all_kids_approved": True,
                },
                const.CHORE_RESET_DECISION_RESET_AND_RESCHEDULE,
                id="approval-immediate-on-late-shared-all-approved",
            ),
            pytest.param(
                {
                    "trigger": const.CHORE_RESET_TRIGGER_APPROVAL,
                    "approval_reset_type": const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
                    "overdue_handling_type": const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE,
                    "approval_after_reset": False,
                    "completion_criteria": const.COMPLETION_CRITERIA_INDEPENDENT,
                },
                const.CHORE_RESET_DECISION_HOLD,
                id="approval-immediate-on-late-not-late",
            ),
            pytest.param(
                {
                    "trigger": const.CHORE_RESET_TRIGGER_APPROVAL,
                    "approval_reset_type": const.APPROVAL_RESET_UPON_COMPLETION,
                    "overdue_handling_type": const.DEFAULT_OVERDUE_HANDLING_TYPE,
                    "completion_criteria": const.COMPLETION_CRITERIA_SHARED,
                    "all_kids_approved": False,
                },
                const.CHORE_RESET_DECISION_HOLD,
                id="approval-upon-completion-shared-not-all-approved",
            ),
            pytest.param(
                {
                    "trigger": const.CHORE_SCAN_TRIGGER_DUE_DATE,
                    "boundary_category": const.CHORE_RESET_BOUNDARY_CATEGORY_HOLD,
                    "has_pending_claim": True,
                    "pending_claim_action": const.APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE,
                },
                const.CHORE_RESET_DECISION_HOLD,
                id="timer-hold-category-wins",
            ),
            pytest.param(
                {
                    "trigger": const.CHORE_SCAN_TRIGGER_DUE_DATE,
                    "boundary_category": const.CHORE_RESET_BOUNDARY_CATEGORY_CLEAR_ONLY,
                    "has_pending_claim": False,
                },
                const.CHORE_RESET_DECISION_RESET_ONLY,
                id="timer-clear-only-no-pending",
            ),
            pytest.param(
                {
                    "trigger": const.CHORE_SCAN_TRIGGER_DUE_DATE,
                    "boundary_category": const.CHORE_RESET_BOUNDARY_CATEGORY_RESET_AND_RESCHEDULE,
                    "has_pending_claim": True,
                    "pending_claim_action": const.APPROVAL_RESET_PENDING_CLAIM_HOLD,
                },
                const.CHORE_RESET_DECISION_HOLD,
                id="timer-pending-hold",
            ),
            pytest.param(
                {
                    "trigger": const.CHORE_SCAN_TRIGGER_DUE_DATE,
                    "boundary_category": const.CHORE_RESET_BOUNDARY_CATEGORY_RESET_AND_RESCHEDULE,
                    "has_pending_claim": True,
                    "pending_claim_action": const.APPROVAL_RESET_PENDING_CLAIM_AUTO_APPROVE,
                },
                const.CHORE_RESET_DECISION_AUTO_APPROVE_PENDING,
                id="timer-pending-auto-approve",
            ),
            pytest.param(
                {
                    "trigger": const.CHORE_SCAN_TRIGGER_DUE_DATE,
                    "boundary_category": const.CHORE_RESET_BOUNDARY_CATEGORY_RESET_AND_RESCHEDULE,
                    "has_pending_claim": True,
                    "pending_claim_action": const.APPROVAL_RESET_PENDING_CLAIM_CLEAR,
                },
                const.CHORE_RESET_DECISION_RESET_AND_RESCHEDULE,
                id="timer-pending-clear",
            ),
        ],
    )
    def test_decide_reset_action_table(
        self,
        context: ResetContext,
        expected: ResetDecision,
    ) -> None:
        """Decision helper returns expected policy action for each context."""
        decision = ChoreManager._decide_reset_action(context)
        assert decision == expected


class TestResetExecutor:
    """Focused tests for Phase 2 reset executor helpers."""

    def test_apply_reset_action_reschedules_for_reschedule_decision(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Executor applies state transition and reschedules when required."""
        chore_manager._transition_chore_state = MagicMock()
        chore_manager._reschedule_chore_due = MagicMock()

        chore_manager._apply_reset_action(
            {
                "kid_id": "kid-1",
                "chore_id": "chore-1",
                "decision": const.CHORE_RESET_DECISION_RESET_AND_RESCHEDULE,
                "reschedule_kid_id": "kid-1",
            }
        )

        chore_manager._transition_chore_state.assert_called_once_with(
            "kid-1",
            "chore-1",
            const.CHORE_STATE_PENDING,
            reset_approval_period=True,
            clear_ownership=True,
        )
        chore_manager._reschedule_chore_due.assert_called_once_with("chore-1", "kid-1")

    def test_apply_reset_action_skips_reschedule_for_reset_only(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Executor does not reschedule for reset-only decisions."""
        chore_manager._transition_chore_state = MagicMock()
        chore_manager._reschedule_chore_due = MagicMock()

        chore_manager._apply_reset_action(
            {
                "kid_id": "kid-1",
                "chore_id": "chore-1",
                "decision": const.CHORE_RESET_DECISION_RESET_ONLY,
                "reschedule_kid_id": None,
            }
        )

        chore_manager._transition_chore_state.assert_called_once()
        chore_manager._reschedule_chore_due.assert_not_called()

    def test_finalize_reset_batch_persist_then_emit(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Batch finalizer persists before emitting rotation signals."""
        calls: list[str] = []

        def _persist() -> None:
            calls.append("persist")

        def _emit(_signal: str, **_kwargs: Any) -> None:
            calls.append("emit")

        chore_manager._coordinator._persist = MagicMock(side_effect=_persist)
        chore_manager.emit = MagicMock(side_effect=_emit)

        chore_manager._finalize_reset_batch(
            persist=True,
            reset_count=1,
            rotation_payloads=[{"chore_id": "chore-1", "kid_id": "kid-1"}],
        )

        assert calls == ["persist", "emit"]

    @pytest.mark.asyncio
    async def test_process_approval_reset_entries_uses_executor(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Approval reset processing routes through shared reset executor."""
        chore_manager._apply_reset_action = MagicMock()
        chore_manager._get_kid_chore_data = MagicMock(
            return_value={const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING}
        )
        chore_manager._coordinator._persist = MagicMock()
        chore_manager._coordinator.async_set_updated_data = MagicMock()

        scan: dict[str, list[dict[str, Any]]] = {
            const.CHORE_SCAN_RESULT_APPROVAL_RESET_SHARED: [
                {
                    const.CHORE_SCAN_ENTRY_CHORE_ID: "chore-1",
                    const.CHORE_SCAN_ENTRY_CHORE_INFO: {
                        const.DATA_CHORE_ASSIGNED_KIDS: ["kid-1"],
                        const.DATA_CHORE_STATE: const.CHORE_STATE_PENDING,
                        const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION: (
                            const.APPROVAL_RESET_PENDING_CLAIM_CLEAR
                        ),
                        const.DATA_CHORE_APPROVAL_RESET_TYPE: (
                            const.APPROVAL_RESET_AT_DUE_DATE_ONCE
                        ),
                        const.DATA_CHORE_OVERDUE_HANDLING_TYPE: (
                            const.DEFAULT_OVERDUE_HANDLING_TYPE
                        ),
                        const.DATA_CHORE_COMPLETION_CRITERIA: (
                            const.COMPLETION_CRITERIA_SHARED
                        ),
                    },
                }
            ],
            const.CHORE_SCAN_RESULT_APPROVAL_RESET_INDEPENDENT: [],
        }

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                "custom_components.kidschores.managers.chore_manager.ChoreEngine.get_boundary_category",
                lambda **_kwargs: (
                    const.CHORE_RESET_BOUNDARY_CATEGORY_RESET_AND_RESCHEDULE
                ),
            )

            (
                reset_count,
                reset_pairs,
            ) = await chore_manager._process_approval_reset_entries(
                scan,
                dt_now_utc(),
                trigger=const.CHORE_SCAN_TRIGGER_DUE_DATE,
                persist=True,
            )

        assert reset_count == 1
        assert ("kid-1", "chore-1") in reset_pairs
        chore_manager._apply_reset_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_approval_reset_entries_shared_uses_chore_reschedule(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Periodic shared reset routes through executor with chore-level reschedule."""
        chore_manager._apply_reset_action = MagicMock()
        chore_manager._get_kid_chore_data = MagicMock(
            return_value={const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING}
        )
        chore_manager._coordinator._persist = MagicMock()
        chore_manager._coordinator.async_set_updated_data = MagicMock()

        scan: dict[str, list[dict[str, Any]]] = {
            const.CHORE_SCAN_RESULT_APPROVAL_RESET_SHARED: [
                {
                    const.CHORE_SCAN_ENTRY_CHORE_ID: "chore-1",
                    const.CHORE_SCAN_ENTRY_CHORE_INFO: {
                        const.DATA_CHORE_ASSIGNED_KIDS: ["kid-1", "kid-2"],
                        const.DATA_CHORE_STATE: const.CHORE_STATE_PENDING,
                        const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION: (
                            const.APPROVAL_RESET_PENDING_CLAIM_CLEAR
                        ),
                        const.DATA_CHORE_APPROVAL_RESET_TYPE: (
                            const.APPROVAL_RESET_AT_DUE_DATE_ONCE
                        ),
                        const.DATA_CHORE_OVERDUE_HANDLING_TYPE: (
                            const.DEFAULT_OVERDUE_HANDLING_TYPE
                        ),
                        const.DATA_CHORE_COMPLETION_CRITERIA: (
                            const.COMPLETION_CRITERIA_SHARED
                        ),
                    },
                }
            ],
            const.CHORE_SCAN_RESULT_APPROVAL_RESET_INDEPENDENT: [],
        }

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                "custom_components.kidschores.managers.chore_manager.ChoreEngine.get_boundary_category",
                lambda **_kwargs: (
                    const.CHORE_RESET_BOUNDARY_CATEGORY_RESET_AND_RESCHEDULE
                ),
            )

            await chore_manager._process_approval_reset_entries(
                scan,
                dt_now_utc(),
                trigger=const.CHORE_SCAN_TRIGGER_DUE_DATE,
                persist=True,
            )

        assert chore_manager._apply_reset_action.call_count == 2
        first_call = chore_manager._apply_reset_action.call_args_list[0].args[0]
        second_call = chore_manager._apply_reset_action.call_args_list[1].args[0]
        assert first_call["reschedule_kid_id"] is None
        assert second_call["reschedule_kid_id"] is None

    @pytest.mark.asyncio
    async def test_process_approval_reset_entries_independent_uses_kid_reschedule(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Periodic independent reset routes through executor with per-kid reschedule."""
        chore_manager._apply_reset_action = MagicMock()
        chore_manager._get_kid_chore_data = MagicMock(
            return_value={const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING}
        )
        chore_manager._coordinator._persist = MagicMock()
        chore_manager._coordinator.async_set_updated_data = MagicMock()

        scan: dict[str, list[dict[str, Any]]] = {
            const.CHORE_SCAN_RESULT_APPROVAL_RESET_SHARED: [],
            const.CHORE_SCAN_RESULT_APPROVAL_RESET_INDEPENDENT: [
                {
                    const.CHORE_SCAN_ENTRY_CHORE_ID: "chore-1",
                    const.CHORE_SCAN_ENTRY_CHORE_INFO: {
                        const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION: (
                            const.APPROVAL_RESET_PENDING_CLAIM_CLEAR
                        ),
                        const.DATA_CHORE_APPROVAL_RESET_TYPE: (
                            const.APPROVAL_RESET_AT_DUE_DATE_ONCE
                        ),
                        const.DATA_CHORE_OVERDUE_HANDLING_TYPE: (
                            const.DEFAULT_OVERDUE_HANDLING_TYPE
                        ),
                        const.DATA_CHORE_COMPLETION_CRITERIA: (
                            const.COMPLETION_CRITERIA_INDEPENDENT
                        ),
                    },
                    "kids": [{const.CHORE_SCAN_ENTRY_KID_ID: "kid-1"}],
                }
            ],
        }

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                "custom_components.kidschores.managers.chore_manager.ChoreEngine.get_boundary_category",
                lambda **_kwargs: (
                    const.CHORE_RESET_BOUNDARY_CATEGORY_RESET_AND_RESCHEDULE
                ),
            )

            await chore_manager._process_approval_reset_entries(
                scan,
                dt_now_utc(),
                trigger=const.CHORE_SCAN_TRIGGER_DUE_DATE,
                persist=True,
            )

        chore_manager._apply_reset_action.assert_called_once_with(
            {
                "kid_id": "kid-1",
                "chore_id": "chore-1",
                "decision": const.CHORE_RESET_DECISION_RESET_AND_RESCHEDULE,
                "reschedule_kid_id": "kid-1",
            }
        )

    @pytest.mark.asyncio
    async def test_rotation_boundary_advances_once_for_missed_turn_holder(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Midnight missed boundary advances rotation once and emits once."""
        chore_manager._get_kid_chore_data = MagicMock(
            return_value={const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_MISSED}
        )
        chore_manager._coordinator._persist = MagicMock()
        chore_manager._coordinator.async_set_updated_data = MagicMock()
        chore_manager._advance_rotation = MagicMock(
            return_value={"chore_id": "chore-1", "kid_id": "kid-2"}
        )
        chore_manager.emit = MagicMock()

        scan: dict[str, list[dict[str, Any]]] = {
            const.CHORE_SCAN_RESULT_APPROVAL_RESET_SHARED: [
                {
                    const.CHORE_SCAN_ENTRY_CHORE_ID: "chore-1",
                    const.CHORE_SCAN_ENTRY_CHORE_INFO: {
                        const.DATA_CHORE_ASSIGNED_KIDS: ["kid-1", "kid-2"],
                        const.DATA_CHORE_STATE: const.CHORE_STATE_MISSED,
                        const.DATA_CHORE_ROTATION_CURRENT_KID_ID: "kid-1",
                        const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION: (
                            const.APPROVAL_RESET_PENDING_CLAIM_CLEAR
                        ),
                        const.DATA_CHORE_APPROVAL_RESET_TYPE: (
                            const.APPROVAL_RESET_AT_MIDNIGHT_ONCE
                        ),
                        const.DATA_CHORE_OVERDUE_HANDLING_TYPE: (
                            const.OVERDUE_HANDLING_AT_DUE_DATE_MARK_MISSED_AND_LOCK
                        ),
                        const.DATA_CHORE_COMPLETION_CRITERIA: (
                            const.COMPLETION_CRITERIA_SHARED
                        ),
                    },
                }
            ],
            const.CHORE_SCAN_RESULT_APPROVAL_RESET_INDEPENDENT: [],
        }

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                "custom_components.kidschores.managers.chore_manager.ChoreEngine.get_boundary_category",
                lambda **_kwargs: (
                    const.CHORE_RESET_BOUNDARY_CATEGORY_RESET_AND_RESCHEDULE
                ),
            )
            monkeypatch.setattr(
                "custom_components.kidschores.managers.chore_manager.ChoreEngine.is_rotation_mode",
                lambda _chore_info: True,
            )

            await chore_manager._process_approval_reset_entries(
                scan,
                dt_now_utc(),
                trigger=const.CHORE_SCAN_TRIGGER_MIDNIGHT,
                persist=True,
            )

        chore_manager._advance_rotation.assert_called_once_with(
            "chore-1", "kid-1", method="auto"
        )
        rotation_calls = [
            call
            for call in chore_manager.emit.call_args_list
            if call.args and call.args[0] == const.SIGNAL_SUFFIX_CHORE_ROTATION_ADVANCED
        ]
        assert len(rotation_calls) == 1
        assert rotation_calls[0].kwargs == {"chore_id": "chore-1", "kid_id": "kid-2"}


class TestApprovalResetExecutorLane:
    """Tests for approval-trigger reset execution path."""

    @pytest.mark.asyncio
    async def test_approval_independent_routes_through_executor(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """Independent UPON_COMPLETION approval uses executor with kid reschedule."""
        mock_coordinator.chores_data["chore-1"][
            const.DATA_CHORE_COMPLETION_CRITERIA
        ] = const.COMPLETION_CRITERIA_INDEPENDENT
        mock_coordinator.chores_data["chore-1"][
            const.DATA_CHORE_APPROVAL_RESET_TYPE
        ] = const.APPROVAL_RESET_UPON_COMPLETION

        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")

        chore_manager._apply_reset_action = MagicMock()

        await chore_manager.approve_chore("Parent", "kid-1", "chore-1")

        chore_manager._apply_reset_action.assert_called_once_with(
            {
                "kid_id": "kid-1",
                "chore_id": "chore-1",
                "decision": const.CHORE_RESET_DECISION_RESET_AND_RESCHEDULE,
                "reschedule_kid_id": "kid-1",
            }
        )

    @pytest.mark.asyncio
    async def test_approval_shared_resets_all_kids_and_reschedules_once(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """Shared UPON_COMPLETION reset applies per-kid reset then one reschedule."""
        mock_coordinator.chores_data["chore-1"][
            const.DATA_CHORE_COMPLETION_CRITERIA
        ] = const.COMPLETION_CRITERIA_SHARED
        mock_coordinator.chores_data["chore-1"][
            const.DATA_CHORE_APPROVAL_RESET_TYPE
        ] = const.APPROVAL_RESET_UPON_COMPLETION

        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")

        chore_manager._all_kids_approved = MagicMock(return_value=True)
        chore_manager._apply_reset_action = MagicMock()
        chore_manager._reschedule_chore_due = MagicMock()

        await chore_manager.approve_chore("Parent", "kid-1", "chore-1")

        assert chore_manager._apply_reset_action.call_count == 2
        chore_manager._reschedule_chore_due.assert_called_once_with("chore-1")

    @pytest.mark.asyncio
    async def test_executor_payload_parity_independent_approval_vs_periodic(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """Independent approval and periodic lanes produce the same reset payload."""
        mock_coordinator.chores_data["chore-1"][
            const.DATA_CHORE_COMPLETION_CRITERIA
        ] = const.COMPLETION_CRITERIA_INDEPENDENT
        mock_coordinator.chores_data["chore-1"][
            const.DATA_CHORE_APPROVAL_RESET_TYPE
        ] = const.APPROVAL_RESET_UPON_COMPLETION

        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")

        chore_manager._apply_reset_action = MagicMock()
        await chore_manager.approve_chore("Parent", "kid-1", "chore-1")
        approval_payload = chore_manager._apply_reset_action.call_args.args[0]

        chore_manager._apply_reset_action.reset_mock()
        chore_manager._get_kid_chore_data = MagicMock(
            return_value={const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING}
        )

        scan: dict[str, list[dict[str, Any]]] = {
            const.CHORE_SCAN_RESULT_APPROVAL_RESET_SHARED: [],
            const.CHORE_SCAN_RESULT_APPROVAL_RESET_INDEPENDENT: [
                {
                    const.CHORE_SCAN_ENTRY_CHORE_ID: "chore-1",
                    const.CHORE_SCAN_ENTRY_CHORE_INFO: {
                        const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION: (
                            const.APPROVAL_RESET_PENDING_CLAIM_CLEAR
                        ),
                        const.DATA_CHORE_APPROVAL_RESET_TYPE: (
                            const.APPROVAL_RESET_AT_DUE_DATE_ONCE
                        ),
                        const.DATA_CHORE_OVERDUE_HANDLING_TYPE: (
                            const.DEFAULT_OVERDUE_HANDLING_TYPE
                        ),
                        const.DATA_CHORE_COMPLETION_CRITERIA: (
                            const.COMPLETION_CRITERIA_INDEPENDENT
                        ),
                    },
                    "kids": [{const.CHORE_SCAN_ENTRY_KID_ID: "kid-1"}],
                }
            ],
        }

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                "custom_components.kidschores.managers.chore_manager.ChoreEngine.get_boundary_category",
                lambda **_kwargs: (
                    const.CHORE_RESET_BOUNDARY_CATEGORY_RESET_AND_RESCHEDULE
                ),
            )
            await chore_manager._process_approval_reset_entries(
                scan,
                dt_now_utc(),
                trigger=const.CHORE_SCAN_TRIGGER_DUE_DATE,
                persist=False,
            )

        periodic_payload = chore_manager._apply_reset_action.call_args.args[0]
        assert periodic_payload == approval_payload

    @pytest.mark.asyncio
    async def test_executor_payload_parity_shared_approval_vs_periodic(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """Shared approval and periodic lanes produce equivalent per-kid reset payloads."""
        mock_coordinator.chores_data["chore-1"][
            const.DATA_CHORE_COMPLETION_CRITERIA
        ] = const.COMPLETION_CRITERIA_SHARED
        mock_coordinator.chores_data["chore-1"][
            const.DATA_CHORE_APPROVAL_RESET_TYPE
        ] = const.APPROVAL_RESET_UPON_COMPLETION

        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")

        chore_manager._all_kids_approved = MagicMock(return_value=True)
        chore_manager._apply_reset_action = MagicMock()
        await chore_manager.approve_chore("Parent", "kid-1", "chore-1")
        approval_payloads = [
            call.args[0] for call in chore_manager._apply_reset_action.call_args_list
        ]

        chore_manager._apply_reset_action.reset_mock()
        chore_manager._get_kid_chore_data = MagicMock(
            return_value={const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_PENDING}
        )

        scan: dict[str, list[dict[str, Any]]] = {
            const.CHORE_SCAN_RESULT_APPROVAL_RESET_SHARED: [
                {
                    const.CHORE_SCAN_ENTRY_CHORE_ID: "chore-1",
                    const.CHORE_SCAN_ENTRY_CHORE_INFO: {
                        const.DATA_CHORE_ASSIGNED_KIDS: ["kid-1", "kid-2"],
                        const.DATA_CHORE_STATE: const.CHORE_STATE_PENDING,
                        const.DATA_CHORE_APPROVAL_RESET_PENDING_CLAIM_ACTION: (
                            const.APPROVAL_RESET_PENDING_CLAIM_CLEAR
                        ),
                        const.DATA_CHORE_APPROVAL_RESET_TYPE: (
                            const.APPROVAL_RESET_AT_DUE_DATE_ONCE
                        ),
                        const.DATA_CHORE_OVERDUE_HANDLING_TYPE: (
                            const.DEFAULT_OVERDUE_HANDLING_TYPE
                        ),
                        const.DATA_CHORE_COMPLETION_CRITERIA: (
                            const.COMPLETION_CRITERIA_SHARED
                        ),
                    },
                }
            ],
            const.CHORE_SCAN_RESULT_APPROVAL_RESET_INDEPENDENT: [],
        }

        with pytest.MonkeyPatch.context() as monkeypatch:
            monkeypatch.setattr(
                "custom_components.kidschores.managers.chore_manager.ChoreEngine.get_boundary_category",
                lambda **_kwargs: (
                    const.CHORE_RESET_BOUNDARY_CATEGORY_RESET_AND_RESCHEDULE
                ),
            )
            await chore_manager._process_approval_reset_entries(
                scan,
                dt_now_utc(),
                trigger=const.CHORE_SCAN_TRIGGER_DUE_DATE,
                persist=False,
            )

        periodic_payloads = [
            call.args[0] for call in chore_manager._apply_reset_action.call_args_list
        ]
        assert periodic_payloads == approval_payloads


# ============================================================================
# Test Class: Claim Workflow
# ============================================================================


class TestClaimWorkflow:
    """Tests for chore claim workflow."""

    @pytest.mark.asyncio
    async def test_claim_chore_success(self, chore_manager: ChoreManager) -> None:
        """Test successful chore claim."""
        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")

        # Verify state changed to claimed
        kid_chore_data = chore_manager._coordinator.kids_data["kid-1"][
            const.DATA_KID_CHORE_DATA
        ]["chore-1"]
        assert (
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] == const.CHORE_STATE_CLAIMED
        )

        # Verify pending count incremented
        assert kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] == 1

        # Verify event emitted
        chore_manager.emit.assert_called()
        call_args = chore_manager.emit.call_args
        assert call_args[0][0] == const.SIGNAL_SUFFIX_CHORE_CLAIMED
        assert call_args[1]["kid_id"] == "kid-1"
        assert call_args[1]["chore_id"] == "chore-1"

        # Verify persist called
        chore_manager._coordinator._persist_and_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_claim_chore_not_assigned(self, chore_manager: ChoreManager) -> None:
        """Test claim fails when kid not assigned to chore."""
        from homeassistant.exceptions import HomeAssistantError

        # Kid-3 is not assigned
        chore_manager._coordinator.kids_data["kid-3"] = {
            const.DATA_KID_NAME: "Charlie",
            const.DATA_KID_CHORE_DATA: {},
        }

        with pytest.raises(HomeAssistantError) as exc_info:
            await chore_manager.claim_chore("kid-3", "chore-1", "Charlie")

        assert exc_info.value.translation_key == const.TRANS_KEY_ERROR_NOT_ASSIGNED

    @pytest.mark.asyncio
    async def test_claim_with_auto_approve(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """Test claim triggers auto-approve when enabled.

        Phase 1: Auto-approve is now atomic/inline (not background task).
        Verify approval happens immediately by checking CHORE_APPROVED signal.
        """
        # Enable auto-approve
        mock_coordinator.chores_data["chore-1"][const.DATA_CHORE_AUTO_APPROVE] = True

        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")

        # Phase 1: Auto-approve happens inline - verify CHORE_APPROVED signal emitted
        chore_manager.emit.assert_called()
        # Find CHORE_APPROVED call (may also have CHORE_COMPLETED signal)
        approved_call = None
        for call in chore_manager.emit.call_args_list:
            if call[0][0] == const.SIGNAL_SUFFIX_CHORE_APPROVED:
                approved_call = call
                break
        assert approved_call is not None, (
            "CHORE_APPROVED signal not emitted (auto-approve failed)"
        )
        assert approved_call[1]["kid_id"] == "kid-1"
        assert approved_call[1]["parent_name"] == "auto_approve"
        assert (
            approved_call[1]["approval_origin"]
            == const.CHORE_APPROVAL_ORIGIN_AUTO_APPROVE
        )
        assert approved_call[1]["notify_kid"] is True


# ============================================================================
# Test Class: Approve Workflow
# ============================================================================


class TestApproveWorkflow:
    """Tests for chore approval workflow."""

    @pytest.mark.asyncio
    async def test_approve_chore_success(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Test successful chore approval."""
        # First claim the chore
        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")
        chore_manager.emit.reset_mock()

        # Now approve
        await chore_manager.approve_chore("Parent", "kid-1", "chore-1")

        # Verify state changed to approved
        kid_chore_data = chore_manager._coordinator.kids_data["kid-1"][
            const.DATA_KID_CHORE_DATA
        ]["chore-1"]
        assert (
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE]
            == const.CHORE_STATE_APPROVED
        )

        # Verify pending count decremented
        assert kid_chore_data[const.DATA_KID_CHORE_DATA_PENDING_CLAIM_COUNT] == 0

        # Verify CHORE_APPROVED signal emitted with correct payload
        # (Signal-First Architecture: EconomyManager deposits points via signal listener)
        chore_manager.emit.assert_called()
        # Find the CHORE_APPROVED call in the list (CHORE_COMPLETED may also be emitted)
        approved_call = None
        for call in chore_manager.emit.call_args_list:
            if call[0][0] == const.SIGNAL_SUFFIX_CHORE_APPROVED:
                approved_call = call
                break
        assert approved_call is not None, "CHORE_APPROVED signal not emitted"
        assert approved_call[1]["kid_id"] == "kid-1"
        assert approved_call[1]["parent_name"] == "Parent"
        # Signal includes base_points for EconomyManager to apply multiplier
        assert "base_points" in approved_call[1]
        assert approved_call[1]["base_points"] == 10.0  # From sample_chore_data
        assert approved_call[1]["approval_origin"] == const.CHORE_APPROVAL_ORIGIN_MANUAL
        assert approved_call[1]["notify_kid"] is True

    @pytest.mark.asyncio
    async def test_approve_race_condition_protection(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Test that race condition is handled gracefully."""
        # Claim first
        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")

        # Mark as already approved in period
        chore_manager._coordinator.chore_is_approved_in_period.return_value = True

        # Should return gracefully without error
        await chore_manager.approve_chore("Parent", "kid-1", "chore-1")

        # No error raised, graceful exit


# ============================================================================
# Test Class: Disapprove Workflow
# ============================================================================


class TestDisapproveWorkflow:
    """Tests for chore disapproval workflow."""

    @pytest.mark.asyncio
    async def test_disapprove_chore_success(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Test successful chore disapproval."""
        # First claim the chore
        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")
        chore_manager.emit.reset_mock()

        # Now disapprove
        await chore_manager.disapprove_chore("Parent", "kid-1", "chore-1", "Try again")

        # Verify state changed back to pending
        kid_chore_data = chore_manager._coordinator.kids_data["kid-1"][
            const.DATA_KID_CHORE_DATA
        ]["chore-1"]
        assert (
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] == const.CHORE_STATE_PENDING
        )

        # Verify event emitted with reason
        chore_manager.emit.assert_called()
        call_args = chore_manager.emit.call_args
        assert call_args[0][0] == const.SIGNAL_SUFFIX_CHORE_DISAPPROVED
        assert call_args[1]["reason"] == "Try again"


# ============================================================================
# Test Class: Reset and Overdue
# ============================================================================


class TestResetAndOverdue:
    """Tests for reset and overdue workflows."""

    @pytest.mark.asyncio
    async def test_reset_chore(self, chore_manager: ChoreManager) -> None:
        """Test chore reset via _transition_chore_state."""
        # Claim and approve first
        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")
        chore_manager.emit.reset_mock()

        # Reset using _transition_chore_state (master method for state changes)
        chore_manager._transition_chore_state(
            "kid-1",
            "chore-1",
            const.CHORE_STATE_PENDING,
            reset_approval_period=True,
            clear_ownership=True,
        )

        # Verify state reset to pending
        kid_chore_data = chore_manager._coordinator.kids_data["kid-1"][
            const.DATA_KID_CHORE_DATA
        ]["chore-1"]
        assert (
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] == const.CHORE_STATE_PENDING
        )

        # Verify event emitted
        chore_manager.emit.assert_called()
        call_args = chore_manager.emit.call_args
        assert call_args[0][0] == const.SIGNAL_SUFFIX_CHORE_STATUS_RESET

    async def test_mark_overdue_via_periodic_update(
        self, chore_manager: ChoreManager
    ) -> None:
        """Test that _on_periodic_update calls process_time_checks and processes overdue.

        Note: This tests the public API interface. Full integration testing
        of overdue state transitions is covered by test_scheduler_delegation.py.
        """
        # Mock process_time_checks to return a known overdue entry
        mock_entry = {
            "chore_id": "chore-1",
            "kid_id": "kid-1",
            "due_dt": dt_now_utc() - timedelta(days=1),
            "time_until_due": timedelta(days=-1),
        }
        chore_manager.process_time_checks = MagicMock(
            return_value={
                "overdue": [mock_entry],
                "in_due_window": [],
                "due_reminder": [],
                "approval_reset_shared": [],
                "approval_reset_independent": [],
            }
        )

        # Mock _process_overdue and _process_approval_reset_entries
        chore_manager._process_overdue = AsyncMock(return_value=None)
        # Phase 1: _process_approval_reset_entries returns (reset_count, reset_pairs) tuple
        chore_manager._process_approval_reset_entries = AsyncMock(
            return_value=(0, set())
        )

        # Process periodic update
        await chore_manager._on_periodic_update(now_utc=dt_now_utc())

        # Verify process_time_checks was called
        chore_manager.process_time_checks.assert_called_once()

        # Verify _process_overdue was called with the overdue entries
        chore_manager._process_overdue.assert_called_once()
        call_args = chore_manager._process_overdue.call_args[0]
        assert len(call_args[0]) == 1  # One overdue entry


class TestDataResetChores:
    """Tests for data_reset_chores scope behavior and side effects."""

    @pytest.mark.asyncio
    async def test_data_reset_chores_global_clears_runtime_and_emits(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """Global reset clears runtime structures across chores and kids."""
        chore_info = mock_coordinator.chores_data["chore-1"]
        chore_info[const.DATA_CHORE_PER_KID_DUE_DATES] = {
            "kid-1": "2026-01-01T00:00:00+00:00",
            "kid-2": "2026-01-02T00:00:00+00:00",
        }
        chore_info[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = {
            "kid-1": [1, 2],
            "kid-2": [3, 4],
        }
        chore_info[const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES] = {
            "kid-1": ["09:00"],
            "kid-2": ["18:00"],
        }
        chore_info[const.DATA_CHORE_LAST_CLAIMED] = "2026-01-01T00:00:00+00:00"
        chore_info[const.DATA_CHORE_LAST_COMPLETED] = "2026-01-01T01:00:00+00:00"

        for field in db._CHORE_PER_KID_RUNTIME_LISTS:
            chore_info[field] = ["kid-1", "kid-2"]

        for kid_id in ("kid-1", "kid-2"):
            kid_dict = mock_coordinator.kids_data[kid_id]
            kid_dict[const.DATA_KID_CHORE_DATA] = {"chore-1": {"state": "claimed"}}
            for field in db._CHORE_KID_RUNTIME_FIELDS:
                if field == const.DATA_KID_CHORE_DATA:
                    continue
                kid_dict[field] = {"marker": 1}

        chore_manager.set_due_date = AsyncMock()

        await chore_manager.data_reset_chores(scope="global")

        chore_manager.set_due_date.assert_awaited_once_with(
            "chore-1", None, kid_id=None
        )

        for field in db._CHORE_PER_KID_RUNTIME_LISTS:
            assert chore_info[field] == []

        assert chore_info[const.DATA_CHORE_LAST_CLAIMED] is None
        assert chore_info[const.DATA_CHORE_LAST_COMPLETED] is None

        for kid_id in ("kid-1", "kid-2"):
            kid_dict = mock_coordinator.kids_data[kid_id]
            assert kid_dict.get(const.DATA_KID_CHORE_DATA) == {}

        mock_coordinator._persist_and_update.assert_called_once()
        chore_manager.emit.assert_any_call(
            const.SIGNAL_SUFFIX_CHORE_DATA_RESET_COMPLETE,
            scope="global",
            kid_id=None,
            item_id=None,
        )

    @pytest.mark.asyncio
    async def test_data_reset_chores_kid_scope_removes_only_target_kid(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """Kid scope reset only touches chores assigned to that kid and kid-scoped config."""
        chore_two = {
            const.DATA_CHORE_NAME: "Second chore",
            const.DATA_CHORE_ASSIGNED_KIDS: ["kid-2"],
            const.DATA_CHORE_COMPLETION_CRITERIA: const.COMPLETION_CRITERIA_INDEPENDENT,
        }
        mock_coordinator.chores_data["chore-2"] = chore_two

        chore_one = mock_coordinator.chores_data["chore-1"]
        chore_one[const.DATA_CHORE_PER_KID_DUE_DATES] = {
            "kid-1": "2026-01-01T00:00:00+00:00",
            "kid-2": "2026-01-02T00:00:00+00:00",
        }
        chore_one[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = {
            "kid-1": [1],
            "kid-2": [2],
        }
        chore_one[const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES] = {
            "kid-1": ["10:00"],
            "kid-2": ["16:00"],
        }

        for field in db._CHORE_PER_KID_RUNTIME_LISTS:
            chore_one[field] = ["kid-1", "kid-2"]

        chore_manager.set_due_date = AsyncMock()

        await chore_manager.data_reset_chores(scope="kid", kid_id="kid-1")

        chore_manager.set_due_date.assert_awaited_once_with(
            "chore-1", None, kid_id="kid-1"
        )

        for field in db._CHORE_PER_KID_RUNTIME_LISTS:
            assert "kid-1" not in chore_one[field]
            assert "kid-2" in chore_one[field]

        assert "kid-1" not in chore_one[const.DATA_CHORE_PER_KID_DUE_DATES]
        assert "kid-2" in chore_one[const.DATA_CHORE_PER_KID_DUE_DATES]
        assert "kid-1" not in chore_one[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS]
        assert "kid-2" in chore_one[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS]
        assert "kid-1" not in chore_one[const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES]
        assert "kid-2" in chore_one[const.DATA_CHORE_PER_KID_DAILY_MULTI_TIMES]

    @pytest.mark.asyncio
    async def test_data_reset_chores_item_scope_clears_single_item(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """Item scope only removes the targeted chore record from kid chore data."""
        for kid_id in ("kid-1", "kid-2"):
            mock_coordinator.kids_data[kid_id][const.DATA_KID_CHORE_DATA] = {
                "chore-1": {"state": "approved"},
                "chore-2": {"state": "pending"},
            }

        chore_manager.set_due_date = AsyncMock()

        await chore_manager.data_reset_chores(scope="item", item_id="chore-1")

        chore_manager.set_due_date.assert_awaited_once_with(
            "chore-1", None, kid_id=None
        )

        for kid_id in ("kid-1", "kid-2"):
            kid_chore_data = mock_coordinator.kids_data[kid_id][
                const.DATA_KID_CHORE_DATA
            ]
            assert "chore-1" not in kid_chore_data
            assert "chore-2" in kid_chore_data


# ============================================================================
# Test Class: Undo Workflow
# ============================================================================


class TestUndoWorkflow:
    """Tests for chore undo workflow."""

    @pytest.mark.asyncio
    async def test_undo_chore(self, chore_manager: ChoreManager) -> None:
        """Test chore undo."""
        # Set up approved state with points
        kid_data = chore_manager._coordinator.kids_data["kid-1"]
        kid_data[const.DATA_KID_CHORE_DATA] = {
            "chore-1": {
                const.DATA_KID_CHORE_DATA_STATE: const.CHORE_STATE_APPROVED,
                const.DATA_KID_CHORE_DATA_TOTAL_POINTS: 10.0,
            }
        }

        await chore_manager.undo_chore("kid-1", "chore-1", "Parent")

        # Verify state reset to pending
        kid_chore_data = kid_data[const.DATA_KID_CHORE_DATA]["chore-1"]
        assert (
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] == const.CHORE_STATE_PENDING
        )


# ============================================================================
# Test Class: Completion Criteria
# ============================================================================


class TestCompletionCriteria:
    """Tests for completion criteria handling."""

    @pytest.mark.asyncio
    async def test_independent_completion(self, chore_manager: ChoreManager) -> None:
        """Test INDEPENDENT completion sets completed_by for actor only."""
        # Claim and complete
        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")

        # Set up for approval
        chore_manager._handle_completion_criteria("chore-1", "kid-1", "Alice")

        # Verify Alice's completed_by is set
        kid1_data = chore_manager._coordinator.kids_data["kid-1"][
            const.DATA_KID_CHORE_DATA
        ]["chore-1"]
        assert kid1_data.get(const.DATA_CHORE_COMPLETED_BY) == "Alice"

        # Verify Bob's completed_by is not affected
        kid2_chores = chore_manager._coordinator.kids_data["kid-2"].get(
            const.DATA_KID_CHORE_DATA, {}
        )
        kid2_chore_data = kid2_chores.get("chore-1", {})
        assert const.DATA_CHORE_COMPLETED_BY not in kid2_chore_data

    def test_shared_first_completion(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """Test SHARED_FIRST completion updates other kids' completed_by."""
        # Change to SHARED_FIRST
        mock_coordinator.chores_data["chore-1"][
            const.DATA_CHORE_COMPLETION_CRITERIA
        ] = const.COMPLETION_CRITERIA_SHARED_FIRST

        # Initialize both kids' chore data
        chore_manager._get_kid_chore_data("kid-1", "chore-1")
        chore_manager._get_kid_chore_data("kid-2", "chore-1")

        # Handle completion
        chore_manager._handle_completion_criteria("chore-1", "kid-1", "Alice")

        # Bob's completed_by should show Alice
        kid2_data = mock_coordinator.kids_data["kid-2"][const.DATA_KID_CHORE_DATA][
            "chore-1"
        ]
        assert kid2_data.get(const.DATA_CHORE_COMPLETED_BY) == "Alice"

    def test_shared_completion_appends_to_list(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """Test SHARED completion appends to completed_by list."""
        # Change to SHARED
        mock_coordinator.chores_data["chore-1"][
            const.DATA_CHORE_COMPLETION_CRITERIA
        ] = const.COMPLETION_CRITERIA_SHARED

        # Initialize both kids' chore data
        chore_manager._get_kid_chore_data("kid-1", "chore-1")
        chore_manager._get_kid_chore_data("kid-2", "chore-1")

        # First completion
        chore_manager._handle_completion_criteria("chore-1", "kid-1", "Alice")

        # Both kids should have Alice in their list
        kid1_data = mock_coordinator.kids_data["kid-1"][const.DATA_KID_CHORE_DATA][
            "chore-1"
        ]
        assert kid1_data.get(const.DATA_CHORE_COMPLETED_BY) == ["Alice"]

        kid2_data = mock_coordinator.kids_data["kid-2"][const.DATA_KID_CHORE_DATA][
            "chore-1"
        ]
        assert kid2_data.get(const.DATA_CHORE_COMPLETED_BY) == ["Alice"]

        # Second completion by Bob
        chore_manager._handle_completion_criteria("chore-1", "kid-2", "Bob")

        # Both should now have both names
        assert "Alice" in kid1_data.get(const.DATA_CHORE_COMPLETED_BY, [])
        assert "Bob" in kid1_data.get(const.DATA_CHORE_COMPLETED_BY, [])


class TestCriteriaTransitions:
    """Tests for manager-side completion criteria transition handling."""

    def test_handle_criteria_transition_applies_changes_and_emits(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """Transition applies engine changes, persists, and emits update signal."""
        mock_coordinator.chores_data["chore-1"][const.DATA_CHORE_ASSIGNED_KIDS] = [
            "kid-1",
            "kid-2",
        ]

        chore_manager._handle_criteria_transition(
            chore_id="chore-1",
            old_criteria=const.COMPLETION_CRITERIA_INDEPENDENT,
            new_criteria=const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
        )

        chore = mock_coordinator.chores_data["chore-1"]
        assert (
            chore[const.DATA_CHORE_COMPLETION_CRITERIA]
            == const.COMPLETION_CRITERIA_ROTATION_SIMPLE
        )
        assert chore[const.DATA_CHORE_ROTATION_CURRENT_KID_ID] == "kid-1"
        assert chore[const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE] is False
        mock_coordinator._persist_and_update.assert_called_once()
        chore_manager.emit.assert_any_call(
            const.SIGNAL_SUFFIX_CHORE_UPDATED,
            chore_id="chore-1",
            updated_fields=[
                const.DATA_CHORE_ROTATION_CURRENT_KID_ID,
                const.DATA_CHORE_ROTATION_CYCLE_OVERRIDE,
                const.DATA_CHORE_COMPLETION_CRITERIA,
            ],
        )

    def test_handle_criteria_transition_rejects_rotation_with_one_kid(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """Rotation criteria requires at least two assigned kids."""
        mock_coordinator.chores_data["chore-1"][const.DATA_CHORE_ASSIGNED_KIDS] = [
            "kid-1"
        ]

        with pytest.raises(ServiceValidationError) as exc:
            chore_manager._handle_criteria_transition(
                chore_id="chore-1",
                old_criteria=const.COMPLETION_CRITERIA_INDEPENDENT,
                new_criteria=const.COMPLETION_CRITERIA_ROTATION_SIMPLE,
            )

        assert exc.value.translation_key == const.TRANS_KEY_ERROR_ROTATION_MIN_KIDS


class TestRotationManagementValidation:
    """Validation/error-path tests for rotation management methods."""

    @pytest.mark.asyncio
    async def test_set_rotation_turn_rejects_missing_chore(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """set_rotation_turn rejects unknown chore id."""
        with pytest.raises(ServiceValidationError) as exc:
            await chore_manager.set_rotation_turn("missing", "kid-1")
        assert exc.value.translation_key == const.TRANS_KEY_ERROR_CHORE_NOT_FOUND

    @pytest.mark.asyncio
    async def test_set_rotation_turn_rejects_non_rotation(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """set_rotation_turn rejects chores that are not rotation mode."""
        mock_coordinator._data[const.DATA_CHORES]["chore-1"][
            const.DATA_CHORE_COMPLETION_CRITERIA
        ] = const.COMPLETION_CRITERIA_INDEPENDENT

        with pytest.raises(ServiceValidationError) as exc:
            await chore_manager.set_rotation_turn("chore-1", "kid-1")
        assert exc.value.translation_key == const.TRANS_KEY_ERROR_NOT_ROTATION

    @pytest.mark.asyncio
    async def test_set_rotation_turn_rejects_unassigned_kid(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """set_rotation_turn rejects kids not assigned to chore."""
        mock_coordinator._data[const.DATA_CHORES]["chore-1"][
            const.DATA_CHORE_COMPLETION_CRITERIA
        ] = const.COMPLETION_CRITERIA_ROTATION_SIMPLE
        mock_coordinator._data[const.DATA_CHORES]["chore-1"][
            const.DATA_CHORE_ASSIGNED_KIDS
        ] = ["kid-1", "kid-2"]

        with pytest.raises(ServiceValidationError) as exc:
            await chore_manager.set_rotation_turn("chore-1", "kid-3")
        assert exc.value.translation_key == const.TRANS_KEY_ERROR_KID_NOT_ASSIGNED

    @pytest.mark.asyncio
    async def test_reset_rotation_rejects_no_assigned_kids(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """reset_rotation rejects rotation chores with no assigned kids."""
        mock_coordinator._data[const.DATA_CHORES]["chore-1"][
            const.DATA_CHORE_COMPLETION_CRITERIA
        ] = const.COMPLETION_CRITERIA_ROTATION_SIMPLE
        mock_coordinator._data[const.DATA_CHORES]["chore-1"][
            const.DATA_CHORE_ASSIGNED_KIDS
        ] = []

        with pytest.raises(ServiceValidationError) as exc:
            await chore_manager.reset_rotation("chore-1")
        assert exc.value.translation_key == const.TRANS_KEY_ERROR_NO_ASSIGNED_KIDS

    @pytest.mark.asyncio
    async def test_open_rotation_cycle_rejects_non_rotation(
        self,
        chore_manager: ChoreManager,
        mock_coordinator: MagicMock,
    ) -> None:
        """open_rotation_cycle rejects non-rotation chores."""
        mock_coordinator._data[const.DATA_CHORES]["chore-1"][
            const.DATA_CHORE_COMPLETION_CRITERIA
        ] = const.COMPLETION_CRITERIA_SHARED

        with pytest.raises(ServiceValidationError) as exc:
            await chore_manager.open_rotation_cycle("chore-1")
        assert exc.value.translation_key == const.TRANS_KEY_ERROR_NOT_ROTATION


# ============================================================================
# Test Class: Event Payloads
# ============================================================================


class TestEventPayloads:
    """Tests for event payload contents."""

    @pytest.mark.asyncio
    async def test_claim_event_has_labels(self, chore_manager: ChoreManager) -> None:
        """Test claim event includes chore labels."""
        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")

        call_args = chore_manager.emit.call_args
        assert call_args[1]["chore_labels"] == ["kitchen", "daily"]

    @pytest.mark.asyncio
    async def test_approve_event_has_rich_payload(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Test approval event includes rich payload for gamification."""
        await chore_manager.claim_chore("kid-1", "chore-1", "Alice")
        chore_manager.emit.reset_mock()

        await chore_manager.approve_chore("Parent", "kid-1", "chore-1")

        # Find the CHORE_APPROVED call in the list (CHORE_COMPLETED may also be emitted)
        approved_call = None
        for call in chore_manager.emit.call_args_list:
            if call[0][0] == const.SIGNAL_SUFFIX_CHORE_APPROVED:
                approved_call = call
                break
        assert approved_call is not None, "CHORE_APPROVED signal not emitted"
        payload = approved_call[1]

        # Verify rich payload fields
        assert "points_awarded" in payload
        assert "is_shared" in payload
        assert "is_multi_claim" in payload
        assert "chore_labels" in payload
        assert "multiplier_applied" in payload
        assert "previous_state" in payload
        assert "update_stats" in payload


# ============================================================================
# Test Class: Lock Management
# ============================================================================


class TestLockManagement:
    """Tests for asyncio lock management."""

    def test_get_lock_creates_new_lock(self, chore_manager: ChoreManager) -> None:
        """Test that get_lock creates a new lock for new key."""
        lock = chore_manager._get_lock("kid-1", "chore-1")
        assert lock is not None

    def test_get_lock_returns_same_lock(self, chore_manager: ChoreManager) -> None:
        """Test that get_lock returns same lock for same key."""
        lock1 = chore_manager._get_lock("kid-1", "chore-1")
        lock2 = chore_manager._get_lock("kid-1", "chore-1")
        assert lock1 is lock2

    def test_different_kids_get_different_locks(
        self, chore_manager: ChoreManager
    ) -> None:
        """Test that different kid+chore pairs get different locks."""
        lock1 = chore_manager._get_lock("kid-1", "chore-1")
        lock2 = chore_manager._get_lock("kid-2", "chore-1")
        assert lock1 is not lock2


class TestStatePersistenceContract:
    """Tests for persisted-vs-derived chore state write contract."""

    def test_apply_effect_normalizes_derived_state_to_pending(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Derived display states must never be persisted in kid_chore_data."""
        effect = TransitionEffect(
            kid_id="kid-1",
            new_state=const.CHORE_STATE_WAITING,
        )

        chore_manager._apply_effect(effect, "chore-1")

        kid_chore_data = chore_manager._coordinator.kids_data["kid-1"][
            const.DATA_KID_CHORE_DATA
        ]["chore-1"]
        assert (
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] == const.CHORE_STATE_PENDING
        )

    def test_apply_effect_persists_missed_checkpoint_state(
        self,
        chore_manager: ChoreManager,
    ) -> None:
        """Missed is a persisted lock/checkpoint state for boundary workflows."""
        effect = TransitionEffect(
            kid_id="kid-1",
            new_state=const.CHORE_STATE_MISSED,
        )

        chore_manager._apply_effect(effect, "chore-1")

        kid_chore_data = chore_manager._coordinator.kids_data["kid-1"][
            const.DATA_KID_CHORE_DATA
        ]["chore-1"]
        assert (
            kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] == const.CHORE_STATE_MISSED
        )
