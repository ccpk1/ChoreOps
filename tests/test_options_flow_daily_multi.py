"""Options flow tests for DAILY_MULTI frequency feature.

CFE-2026-001 Feature 2: Tests the helper form flow for collecting
pipe-separated times when adding/editing DAILY_MULTI chores.

Test IDs: OF-01 through OF-06
"""

# pyright: reportTypedDictNotRequiredAccess=false

from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest

from tests.helpers import (
    APPROVAL_RESET_UPON_COMPLETION,
    CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE,
    CFOF_CHORES_INPUT_ASSIGNED_ASSIGNEES,
    CFOF_CHORES_INPUT_COMPLETION_CRITERIA,
    CFOF_CHORES_INPUT_DAILY_MULTI_TIMES,
    CFOF_CHORES_INPUT_DEFAULT_POINTS,
    CFOF_CHORES_INPUT_DESCRIPTION,
    CFOF_CHORES_INPUT_DUE_DATE,
    CFOF_CHORES_INPUT_ICON,
    CFOF_CHORES_INPUT_NAME,
    CFOF_CHORES_INPUT_RECURRING_FREQUENCY,
    COMPLETION_CRITERIA_SHARED,
    DATA_CHORE_DAILY_MULTI_TIMES,
    FREQUENCY_DAILY_MULTI,
    OPTIONS_FLOW_ACTIONS_ADD,
    OPTIONS_FLOW_CHORES,
    OPTIONS_FLOW_INPUT_MANAGE_ACTION,
    OPTIONS_FLOW_INPUT_MENU_SELECTION,
    OPTIONS_FLOW_STEP_ADD_CHORE,
    OPTIONS_FLOW_STEP_CHORES_DAILY_MULTI,
    OPTIONS_FLOW_STEP_INIT,
    OPTIONS_FLOW_STEP_MANAGE_ENTITY,
)
from tests.helpers.setup import SetupResult, setup_from_yaml


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario for options flow testing."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


class TestDailyMultiOptionsFlow:
    """Tests for DAILY_MULTI options flow helper form."""

    @pytest.mark.asyncio
    async def test_of_01_add_chore_daily_multi_routes_to_helper(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """OF-01: Add chore with DAILY_MULTI routes to chores_daily_multi step."""
        config_entry = scenario_minimal.config_entry
        coordinator = scenario_minimal.coordinator

        # Get existing assignee names
        assignee_names = [k["name"] for k in coordinator.assignees_data.values()]
        assert len(assignee_names) > 0

        # Start options flow
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Navigate to chores menu
        flow_id = result.get("flow_id")
        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_CHORES},
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_MANAGE_ENTITY

        # Select Add action
        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
        )
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_ADD_CHORE

        # Add chore with DAILY_MULTI frequency
        due_date = datetime.now(UTC) + timedelta(hours=1)
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            result = await hass.config_entries.options.async_configure(
                flow_id,  # type: ignore[arg-type]
                user_input={
                    CFOF_CHORES_INPUT_NAME: "Multi Daily Test",
                    CFOF_CHORES_INPUT_DEFAULT_POINTS: 10,
                    CFOF_CHORES_INPUT_ICON: "mdi:check",
                    CFOF_CHORES_INPUT_DESCRIPTION: "",
                    CFOF_CHORES_INPUT_ASSIGNED_ASSIGNEES: assignee_names[:1],
                    CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY_MULTI,
                    CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_SHARED,
                    CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: APPROVAL_RESET_UPON_COMPLETION,
                    CFOF_CHORES_INPUT_DUE_DATE: due_date,
                },
            )

        # Should route to daily_multi helper step
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_CHORES_DAILY_MULTI

    @pytest.mark.asyncio
    async def test_of_03_helper_form_saves_times(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """OF-03: Enter valid times in helper form saves to chore data."""
        config_entry = scenario_minimal.config_entry
        coordinator = scenario_minimal.coordinator

        # Get existing assignee names
        assignee_names = [k["name"] for k in coordinator.assignees_data.values()]

        # Start options flow and navigate to add chore
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result.get("flow_id")

        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_CHORES},
        )
        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
        )

        # Add chore with DAILY_MULTI
        due_date = datetime.now(UTC) + timedelta(hours=1)
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            result = await hass.config_entries.options.async_configure(
                flow_id,  # type: ignore[arg-type]
                user_input={
                    CFOF_CHORES_INPUT_NAME: "Times Save Test",
                    CFOF_CHORES_INPUT_DEFAULT_POINTS: 10,
                    CFOF_CHORES_INPUT_ICON: "mdi:check",
                    CFOF_CHORES_INPUT_DESCRIPTION: "",
                    CFOF_CHORES_INPUT_ASSIGNED_ASSIGNEES: assignee_names[:1],
                    CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY_MULTI,
                    CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_SHARED,
                    CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: APPROVAL_RESET_UPON_COMPLETION,
                    CFOF_CHORES_INPUT_DUE_DATE: due_date,
                },
            )

        # Now at daily_multi helper step
        assert result.get("step_id") == OPTIONS_FLOW_STEP_CHORES_DAILY_MULTI

        # Enter valid times
        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={CFOF_CHORES_INPUT_DAILY_MULTI_TIMES: "08:00|17:00"},
        )

        # Should return to init
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify times were saved
        chore = next(
            (
                c
                for c in coordinator.chores_data.values()
                if c["name"] == "Times Save Test"
            ),
            None,
        )
        assert chore is not None
        assert chore.get(DATA_CHORE_DAILY_MULTI_TIMES) == "08:00|17:00"

    @pytest.mark.asyncio
    async def test_of_04_helper_form_validates_format(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """OF-04: Enter invalid times shows error and redisplays form."""
        config_entry = scenario_minimal.config_entry
        coordinator = scenario_minimal.coordinator

        # Get existing assignee names
        assignee_names = [k["name"] for k in coordinator.assignees_data.values()]

        # Start options flow and navigate to add chore
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result.get("flow_id")

        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_CHORES},
        )
        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
        )

        # Add chore with DAILY_MULTI
        due_date = datetime.now(UTC) + timedelta(hours=1)
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            result = await hass.config_entries.options.async_configure(
                flow_id,  # type: ignore[arg-type]
                user_input={
                    CFOF_CHORES_INPUT_NAME: "Invalid Times Test",
                    CFOF_CHORES_INPUT_DEFAULT_POINTS: 10,
                    CFOF_CHORES_INPUT_ICON: "mdi:check",
                    CFOF_CHORES_INPUT_DESCRIPTION: "",
                    CFOF_CHORES_INPUT_ASSIGNED_ASSIGNEES: assignee_names[:1],
                    CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY_MULTI,
                    CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_SHARED,
                    CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: APPROVAL_RESET_UPON_COMPLETION,
                    CFOF_CHORES_INPUT_DUE_DATE: due_date,
                },
            )

        # Now at daily_multi helper step
        assert result.get("step_id") == OPTIONS_FLOW_STEP_CHORES_DAILY_MULTI

        # Enter invalid times (wrong format)
        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={CFOF_CHORES_INPUT_DAILY_MULTI_TIMES: "8am|5pm"},
        )

        # Should stay on same step with error
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_CHORES_DAILY_MULTI
        errors = result.get("errors")
        assert errors is not None
        assert CFOF_CHORES_INPUT_DAILY_MULTI_TIMES in errors

    @pytest.mark.asyncio
    async def test_of_04b_helper_form_validates_too_few_times(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """OF-04b: Enter only one time shows error (need at least 2)."""
        config_entry = scenario_minimal.config_entry
        coordinator = scenario_minimal.coordinator

        # Get existing assignee names
        assignee_names = [k["name"] for k in coordinator.assignees_data.values()]

        # Start options flow and navigate to add chore
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result.get("flow_id")

        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_CHORES},
        )
        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
        )

        # Add chore with DAILY_MULTI
        due_date = datetime.now(UTC) + timedelta(hours=1)
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            result = await hass.config_entries.options.async_configure(
                flow_id,  # type: ignore[arg-type]
                user_input={
                    CFOF_CHORES_INPUT_NAME: "Too Few Times Test",
                    CFOF_CHORES_INPUT_DEFAULT_POINTS: 10,
                    CFOF_CHORES_INPUT_ICON: "mdi:check",
                    CFOF_CHORES_INPUT_DESCRIPTION: "",
                    CFOF_CHORES_INPUT_ASSIGNED_ASSIGNEES: assignee_names[:1],
                    CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY_MULTI,
                    CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_SHARED,
                    CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: APPROVAL_RESET_UPON_COMPLETION,
                    CFOF_CHORES_INPUT_DUE_DATE: due_date,
                },
            )

        # Now at daily_multi helper step
        assert result.get("step_id") == OPTIONS_FLOW_STEP_CHORES_DAILY_MULTI

        # Enter only one time (need at least 2)
        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={CFOF_CHORES_INPUT_DAILY_MULTI_TIMES: "08:00"},
        )

        # Should stay on same step with error
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_CHORES_DAILY_MULTI
        errors = result.get("errors")
        assert errors is not None
        assert CFOF_CHORES_INPUT_DAILY_MULTI_TIMES in errors

    @pytest.mark.asyncio
    async def test_of_04c_helper_form_validates_too_many_times(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """OF-04c: Enter 7+ times shows error (max 6 allowed)."""
        config_entry = scenario_minimal.config_entry
        coordinator = scenario_minimal.coordinator

        # Get existing assignee names
        assignee_names = [k["name"] for k in coordinator.assignees_data.values()]

        # Start options flow and navigate to add chore
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result.get("flow_id")

        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_CHORES},
        )
        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
        )

        # Add chore with DAILY_MULTI
        due_date = datetime.now(UTC) + timedelta(hours=1)
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            result = await hass.config_entries.options.async_configure(
                flow_id,  # type: ignore[arg-type]
                user_input={
                    CFOF_CHORES_INPUT_NAME: "Too Many Times Test",
                    CFOF_CHORES_INPUT_DEFAULT_POINTS: 10,
                    CFOF_CHORES_INPUT_ICON: "mdi:check",
                    CFOF_CHORES_INPUT_DESCRIPTION: "",
                    CFOF_CHORES_INPUT_ASSIGNED_ASSIGNEES: assignee_names[:1],
                    CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY_MULTI,
                    CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_SHARED,
                    CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: APPROVAL_RESET_UPON_COMPLETION,
                    CFOF_CHORES_INPUT_DUE_DATE: due_date,
                },
            )

        # Now at daily_multi helper step
        assert result.get("step_id") == OPTIONS_FLOW_STEP_CHORES_DAILY_MULTI

        # Enter 7 times (max 6 allowed)
        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={
                CFOF_CHORES_INPUT_DAILY_MULTI_TIMES: "06:00|08:00|10:00|12:00|14:00|16:00|18:00"
            },
        )

        # Should stay on same step with error
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_CHORES_DAILY_MULTI
        errors = result.get("errors")
        assert errors is not None
        assert CFOF_CHORES_INPUT_DAILY_MULTI_TIMES in errors

    @pytest.mark.asyncio
    async def test_of_03b_helper_form_saves_six_times(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """OF-03b: Enter 6 valid times (max allowed) saves correctly."""
        config_entry = scenario_minimal.config_entry
        coordinator = scenario_minimal.coordinator

        # Get existing assignee names
        assignee_names = [k["name"] for k in coordinator.assignees_data.values()]

        # Start options flow and navigate to add chore
        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        flow_id = result.get("flow_id")

        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_CHORES},
        )
        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
        )

        # Add chore with DAILY_MULTI
        due_date = datetime.now(UTC) + timedelta(hours=1)
        with patch.object(
            coordinator.notification_manager, "notify_assignee", new=AsyncMock()
        ):
            result = await hass.config_entries.options.async_configure(
                flow_id,  # type: ignore[arg-type]
                user_input={
                    CFOF_CHORES_INPUT_NAME: "Six Times Test",
                    CFOF_CHORES_INPUT_DEFAULT_POINTS: 10,
                    CFOF_CHORES_INPUT_ICON: "mdi:check",
                    CFOF_CHORES_INPUT_DESCRIPTION: "",
                    CFOF_CHORES_INPUT_ASSIGNED_ASSIGNEES: assignee_names[:1],
                    CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY_MULTI,
                    CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_SHARED,
                    CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: APPROVAL_RESET_UPON_COMPLETION,
                    CFOF_CHORES_INPUT_DUE_DATE: due_date,
                },
            )

        # Now at daily_multi helper step
        assert result.get("step_id") == OPTIONS_FLOW_STEP_CHORES_DAILY_MULTI

        # Enter 6 valid times (max allowed)
        result = await hass.config_entries.options.async_configure(
            flow_id,  # type: ignore[arg-type]
            user_input={
                CFOF_CHORES_INPUT_DAILY_MULTI_TIMES: "06:00|08:00|10:00|12:00|14:00|16:00"
            },
        )

        # Should return to init
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify times were saved
        chore = next(
            (
                c
                for c in coordinator.chores_data.values()
                if c["name"] == "Six Times Test"
            ),
            None,
        )
        assert chore is not None
        assert (
            chore.get(DATA_CHORE_DAILY_MULTI_TIMES)
            == "06:00|08:00|10:00|12:00|14:00|16:00"
        )
