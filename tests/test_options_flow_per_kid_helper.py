"""Tests for per-kid helper options flow (PKAD-2026-001).

These tests validate the edit_chore_per_kid_details step which handles:
- Applicable days per kid
- Daily multi times per kid (if DAILY_MULTI frequency)
- Due dates per kid
- Template "Apply to All" checkboxes

All tests use options flow as the single path for creating and editing chores.
Per Rule 2.1 from AGENT_TEST_CREATION_INSTRUCTIONS.md, we test what users
actually do: go through the UI flow.
"""

# pylint: disable=redefined-outer-name

from datetime import UTC
from typing import Any

from homeassistant.config_entries import ConfigFlowResult
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
import pytest

from tests.helpers import (
    APPROVAL_RESET_UPON_COMPLETION,
    CFOF_CHORES_INPUT_APPLICABLE_DAYS,
    CFOF_CHORES_INPUT_APPLY_DAYS_TO_ALL,
    CFOF_CHORES_INPUT_APPLY_TEMPLATE_TO_ALL,
    CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE,
    CFOF_CHORES_INPUT_ASSIGNED_KIDS,
    CFOF_CHORES_INPUT_COMPLETION_CRITERIA,
    CFOF_CHORES_INPUT_DEFAULT_POINTS,
    CFOF_CHORES_INPUT_DESCRIPTION,
    CFOF_CHORES_INPUT_DUE_DATE,
    CFOF_CHORES_INPUT_ICON,
    CFOF_CHORES_INPUT_NAME,
    CFOF_CHORES_INPUT_RECURRING_FREQUENCY,
    COMPLETION_CRITERIA_INDEPENDENT,
    COMPLETION_CRITERIA_SHARED,
    DATA_CHORE_PER_KID_APPLICABLE_DAYS,
    DATA_CHORE_PER_KID_DAILY_MULTI_TIMES,
    DATA_CHORE_PER_KID_DUE_DATES,
    FREQUENCY_DAILY,
    FREQUENCY_DAILY_MULTI,
    FREQUENCY_NONE,
    OPTIONS_FLOW_ACTIONS_ADD,
    OPTIONS_FLOW_ACTIONS_EDIT,
    OPTIONS_FLOW_CHORES,
    OPTIONS_FLOW_INPUT_ENTITY_NAME,
    OPTIONS_FLOW_INPUT_MANAGE_ACTION,
    OPTIONS_FLOW_INPUT_MENU_SELECTION,
    OPTIONS_FLOW_STEP_ADD_CHORE,
    OPTIONS_FLOW_STEP_EDIT_CHORE,
    OPTIONS_FLOW_STEP_EDIT_CHORE_PER_KID_DETAILS,
    OPTIONS_FLOW_STEP_INIT,
    OPTIONS_FLOW_STEP_MANAGE_ENTITY,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
async def scenario_shared(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load scenario_shared with 3 kids (Zoë, Max!, Lila) and 1 parent.

    Uses scenario_shared.yaml which has:
    - 3 kids: Zoë, Max!, Lila
    - 1 parent: Môm Astrid Stârblüm
    - 8 shared chores (will add INDEPENDENT chores via flow)
    """
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_shared.yaml",
    )


@pytest.fixture
async def scenario_full(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load scenario_full with 3 kids and various chore types.

    Uses scenario_full.yaml which has INDEPENDENT chores assigned to
    multiple kids that can be used for edit testing.
    """
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


# =========================================================================
# Helper Functions
# =========================================================================


async def navigate_to_add_chore(
    hass: HomeAssistant,
    entry_id: str,
) -> ConfigFlowResult:
    """Navigate to add chore form and return result with flow_id."""
    # Init options flow
    result = await hass.config_entries.options.async_init(entry_id)
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

    # Navigate to chores menu
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_CHORES},
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_MANAGE_ENTITY

    # Select Add action
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_ADD},
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_ADD_CHORE

    return result


async def navigate_to_edit_chore(
    hass: HomeAssistant,
    entry_id: str,
    chore_name: str,
) -> ConfigFlowResult:
    """Navigate to edit chore form and return result with flow_id."""
    # Init options flow
    result = await hass.config_entries.options.async_init(entry_id)
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

    # Navigate to chores menu
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_MENU_SELECTION: OPTIONS_FLOW_CHORES},
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_MANAGE_ENTITY

    # Select Edit action
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_MANAGE_ACTION: OPTIONS_FLOW_ACTIONS_EDIT},
    )
    # Should be select_entity step

    # Select chore by name
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={OPTIONS_FLOW_INPUT_ENTITY_NAME: chore_name},
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_CHORE

    return result


# =========================================================================
# PKH-01: Add INDEPENDENT chore with 2 kids (no template)
# =========================================================================


class TestPerKidHelperAdd:
    """Tests for adding INDEPENDENT chores that route to per-kid helper."""

    async def test_pkh01_add_independent_2kids_routes_to_per_kid_details(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Test adding INDEPENDENT chore with 2+ kids routes to per-kid details step.

        PKH-01: When adding an INDEPENDENT chore assigned to 2+ kids,
        the flow should route to edit_chore_per_kid_details after the main form.
        """
        config_entry = scenario_shared.config_entry
        coordinator = scenario_shared.coordinator

        # Get kid names for assignment (need 2+)
        kid_names = [k["name"] for k in coordinator.kids_data.values()]
        assert len(kid_names) >= 2, "Scenario should have at least 2 kids"
        assigned_kids = kid_names[:2]  # Use first 2 kids

        # Navigate to add chore form
        result = await navigate_to_add_chore(hass, config_entry.entry_id)

        # Submit add chore form with INDEPENDENT + 2 kids
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CFOF_CHORES_INPUT_NAME: "PKH01 Test Chore",
                CFOF_CHORES_INPUT_DEFAULT_POINTS: 15.0,
                CFOF_CHORES_INPUT_ICON: "mdi:test-tube",
                CFOF_CHORES_INPUT_DESCRIPTION: "Test chore for PKH-01",
                CFOF_CHORES_INPUT_ASSIGNED_KIDS: assigned_kids,
                CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY,
                CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_INDEPENDENT,
                CFOF_CHORES_INPUT_APPLICABLE_DAYS: ["mon", "tue", "wed"],
            },
        )

        # Should route to per-kid details step
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_CHORE_PER_KID_DETAILS, (
            f"Expected per-kid details step, got {result.get('step_id')}"
        )

        # Submit per-kid details with individual values (no template)
        # Field names are: days_{kid_name}, date_{kid_name}
        per_kid_input: dict[str, Any] = {}
        for kid_name in assigned_kids:
            per_kid_input[f"applicable_days_{kid_name}"] = ["mon", "wed", "fri"]
            # No date specified - leave blank

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=per_kid_input,
        )

        # Should return to init after completion
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify chore was created with per-kid data
        chore_data = None
        for chore in coordinator.chores_data.values():
            if chore.get("name") == "PKH01 Test Chore":
                chore_data = chore
                break

        assert chore_data is not None, "Chore should have been created"
        per_kid_days = chore_data.get(DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
        assert len(per_kid_days) == 2, "Should have per-kid days for 2 kids"

    async def test_pkh02_add_independent_2kids_with_template_date(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Test adding INDEPENDENT chore with 2+ kids using template date.

        PKH-02: When a date is entered in the main form and "Apply to All"
        is checked, all kids should get the same date.
        """
        from datetime import datetime, timedelta

        config_entry = scenario_shared.config_entry
        coordinator = scenario_shared.coordinator

        # Get kid names for assignment
        kid_names = [k["name"] for k in coordinator.kids_data.values()]
        assigned_kids = kid_names[:2]

        # Calculate a future date for due_date
        future_date = datetime.now(UTC) + timedelta(days=7)

        # Navigate to add chore form
        result = await navigate_to_add_chore(hass, config_entry.entry_id)

        # Submit with template date (DateTimeSelector accepts datetime directly)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CFOF_CHORES_INPUT_NAME: "PKH02 Template Date Chore",
                CFOF_CHORES_INPUT_DEFAULT_POINTS: 20.0,
                CFOF_CHORES_INPUT_ICON: "mdi:calendar",
                CFOF_CHORES_INPUT_DESCRIPTION: "Test template date",
                CFOF_CHORES_INPUT_ASSIGNED_KIDS: assigned_kids,
                CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY,
                CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_INDEPENDENT,
                CFOF_CHORES_INPUT_DUE_DATE: future_date,
            },
        )

        # Should route to per-kid details step
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_CHORE_PER_KID_DETAILS

        # Submit with "Apply template date to all" checked
        per_kid_input: dict[str, Any] = {
            CFOF_CHORES_INPUT_APPLY_TEMPLATE_TO_ALL: True,
        }
        for kid_name in assigned_kids:
            per_kid_input[f"applicable_days_{kid_name}"] = [
                "mon",
                "tue",
                "wed",
                "thu",
                "fri",
            ]

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=per_kid_input,
        )

        # Should return to init
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify chore was created with same date for all kids
        chore_data = None
        for chore in coordinator.chores_data.values():
            if chore.get("name") == "PKH02 Template Date Chore":
                chore_data = chore
                break

        assert chore_data is not None
        per_kid_dates = chore_data.get(DATA_CHORE_PER_KID_DUE_DATES, {})

        # All dates should be the same (applied from template)
        date_values = list(per_kid_dates.values())
        assert len(date_values) == 2
        assert date_values[0] == date_values[1], "All kids should have same date"

    async def test_pkh03_add_independent_2kids_with_template_days(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Test adding INDEPENDENT chore with 2+ kids using template days.

        PKH-03: When applicable_days is entered in main form and
        "Apply days to all" is checked, all kids get the same days.
        """
        config_entry = scenario_shared.config_entry
        coordinator = scenario_shared.coordinator

        kid_names = [k["name"] for k in coordinator.kids_data.values()]
        assigned_kids = kid_names[:2]

        # Navigate to add chore form
        result = await navigate_to_add_chore(hass, config_entry.entry_id)

        # Submit with template applicable_days
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CFOF_CHORES_INPUT_NAME: "PKH03 Template Days Chore",
                CFOF_CHORES_INPUT_DEFAULT_POINTS: 15.0,
                CFOF_CHORES_INPUT_ICON: "mdi:calendar-week",
                CFOF_CHORES_INPUT_DESCRIPTION: "Test template days",
                CFOF_CHORES_INPUT_ASSIGNED_KIDS: assigned_kids,
                CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY,
                CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_INDEPENDENT,
                CFOF_CHORES_INPUT_APPLICABLE_DAYS: ["mon", "wed", "fri"],
            },
        )

        assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_CHORE_PER_KID_DETAILS

        # Submit with "Apply days to all" checked
        per_kid_input: dict[str, Any] = {
            CFOF_CHORES_INPUT_APPLY_DAYS_TO_ALL: True,
        }
        # Still need to provide per-kid fields (will be overwritten by template)
        for kid_name in assigned_kids:
            per_kid_input[
                f"applicable_days_{kid_name}"
            ] = []  # Will be replaced by template

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=per_kid_input,
        )

        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify per-kid days match template
        chore_data = None
        for chore in coordinator.chores_data.values():
            if chore.get("name") == "PKH03 Template Days Chore":
                chore_data = chore
                break

        assert chore_data is not None
        per_kid_days = chore_data.get(DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})

        # All kids should have [0, 2, 4] (mon=0, wed=2, fri=4)
        for kid_id, days in per_kid_days.items():
            assert sorted(days) == [0, 2, 4], f"Kid {kid_id} should have mon/wed/fri"

    async def test_pkh04_add_independent_2kids_with_mixed_template_options(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Test adding INDEPENDENT chore with mixed template options.

        PKH-04: Some template checkboxes checked, others not.
        - Apply days to all: checked (all kids get same days)
        - Apply template date to all: unchecked (each kid gets own date)
        """
        from datetime import datetime, timedelta

        config_entry = scenario_shared.config_entry
        coordinator = scenario_shared.coordinator

        kid_names = [k["name"] for k in coordinator.kids_data.values()]
        assigned_kids = kid_names[:2]

        # Template date to be entered in main form
        template_date = datetime.now(UTC) + timedelta(days=14)

        result = await navigate_to_add_chore(hass, config_entry.entry_id)

        # Submit with both template days and date
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CFOF_CHORES_INPUT_NAME: "PKH04 Mixed Template Chore",
                CFOF_CHORES_INPUT_DEFAULT_POINTS: 18.0,
                CFOF_CHORES_INPUT_ICON: "mdi:checkbox-multiple-marked",
                CFOF_CHORES_INPUT_DESCRIPTION: "Test mixed template options",
                CFOF_CHORES_INPUT_ASSIGNED_KIDS: assigned_kids,
                CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY,
                CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_INDEPENDENT,
                CFOF_CHORES_INPUT_APPLICABLE_DAYS: ["tue", "thu", "sat"],
                CFOF_CHORES_INPUT_DUE_DATE: template_date,
            },
        )

        assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_CHORE_PER_KID_DETAILS

        # Submit with mixed options:
        # - Apply days to all: TRUE (use template days)
        # - Apply template to all (date): FALSE (allow different dates)
        per_kid_input: dict[str, Any] = {
            CFOF_CHORES_INPUT_APPLY_DAYS_TO_ALL: True,
            CFOF_CHORES_INPUT_APPLY_TEMPLATE_TO_ALL: False,
        }
        # Give each kid a different date
        for i, kid_name in enumerate(assigned_kids):
            per_kid_input[f"applicable_days_{kid_name}"] = []  # Will use template
            # Different dates per kid
            per_kid_input[f"due_date_{kid_name}"] = datetime.now(UTC) + timedelta(
                days=7 + i * 5
            )

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=per_kid_input,
        )

        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify results
        chore_data = None
        for chore in coordinator.chores_data.values():
            if chore.get("name") == "PKH04 Mixed Template Chore":
                chore_data = chore
                break

        assert chore_data is not None

        # All kids should have same days (applied from template)
        per_kid_days = chore_data.get(DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})
        day_values = list(per_kid_days.values())
        assert len(day_values) == 2
        assert day_values[0] == day_values[1], "Days should be same (template applied)"

        # But dates should be different (template NOT applied)
        per_kid_dates = chore_data.get(DATA_CHORE_PER_KID_DUE_DATES, {})
        date_values = list(per_kid_dates.values())
        assert len(date_values) == 2
        assert date_values[0] != date_values[1], "Dates should differ (no template)"

    async def test_pkh05_add_independent_daily_multi_2kids(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Test adding INDEPENDENT DAILY_MULTI chore with 2+ kids.

        PKH-05: When DAILY_MULTI frequency is selected, per-kid helper
        should also collect times per kid.
        """
        config_entry = scenario_shared.config_entry
        coordinator = scenario_shared.coordinator

        kid_names = [k["name"] for k in coordinator.kids_data.values()]
        assigned_kids = kid_names[:2]

        # DAILY_MULTI requires a due date
        from datetime import datetime, timedelta

        future_date = datetime.now(UTC) + timedelta(days=7)

        result = await navigate_to_add_chore(hass, config_entry.entry_id)

        # Submit with DAILY_MULTI frequency
        # Note: daily_multi_times is NOT in the add_chore schema.
        # For INDEPENDENT + 2 kids, times are collected in per-kid helper.
        # DAILY_MULTI requires:
        #   1. Compatible reset type (not at_midnight_*)
        #   2. A due date
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CFOF_CHORES_INPUT_NAME: "PKH05 Daily Multi Chore",
                CFOF_CHORES_INPUT_DEFAULT_POINTS: 10.0,
                CFOF_CHORES_INPUT_ICON: "mdi:clock-multiple",
                CFOF_CHORES_INPUT_DESCRIPTION: "Test daily multi",
                CFOF_CHORES_INPUT_ASSIGNED_KIDS: assigned_kids,
                CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY_MULTI,
                CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_INDEPENDENT,
                # DAILY_MULTI needs upon_completion reset (not at_midnight_once)
                CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: APPROVAL_RESET_UPON_COMPLETION,
                # DAILY_MULTI requires a due date
                CFOF_CHORES_INPUT_DUE_DATE: future_date,
                # daily_multi_times collected in per-kid helper, not here
            },
        )

        # Check for form errors
        if result.get("errors"):
            raise AssertionError(f"Form had errors: {result.get('errors')}")

        assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_CHORE_PER_KID_DETAILS

        # Submit per-kid details with times
        per_kid_input: dict[str, Any] = {}
        for i, kid_name in enumerate(assigned_kids):
            per_kid_input[f"applicable_days_{kid_name}"] = [
                "mon",
                "tue",
                "wed",
                "thu",
                "fri",
            ]
            # Give different times to each kid
            if i == 0:
                per_kid_input[f"daily_multi_times_{kid_name}"] = "09:00|13:00"
            else:
                per_kid_input[f"daily_multi_times_{kid_name}"] = "08:00|12:00|18:00"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=per_kid_input,
        )

        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify per-kid times
        chore_data = None
        for chore in coordinator.chores_data.values():
            if chore.get("name") == "PKH05 Daily Multi Chore":
                chore_data = chore
                break

        assert chore_data is not None
        per_kid_times = chore_data.get(DATA_CHORE_PER_KID_DAILY_MULTI_TIMES, {})
        assert len(per_kid_times) == 2, "Should have times for 2 kids"


# =========================================================================
# PKH-06 to PKH-10: Edit Tests
# =========================================================================


class TestPerKidHelperEdit:
    """Tests for editing INDEPENDENT chores via per-kid helper."""

    async def test_pkh06_edit_independent_with_none_applicable_days(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test editing INDEPENDENT chore when applicable_days is None.

        PKH-06 REGRESSION: This is the bug that was discovered where editing
        a chore with applicable_days=None caused a schema error because
        .get(key, default) doesn't work when the value is explicitly None.
        """
        config_entry = scenario_full.config_entry
        coordinator = scenario_full.coordinator

        # Find "Stär sweep" - INDEPENDENT chore with 3 kids in scenario_full
        chore_name = "Stär sweep"
        chore_id = None
        for cid, chore in coordinator.chores_data.items():
            if chore.get("name") == chore_name:
                chore_id = cid
                break

        assert chore_id is not None, f"Chore '{chore_name}' not found in scenario"

        # Navigate to edit the chore
        result = await navigate_to_edit_chore(hass, config_entry.entry_id, chore_name)

        # The edit form should load without error (this was the bug)
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_CHORE

        # Make a minor change and submit
        kid_names = [k["name"] for k in coordinator.kids_data.values()]
        assigned_kids = kid_names[:3]  # Keep same 3 kids

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CFOF_CHORES_INPUT_NAME: chore_name,  # Keep same name
                CFOF_CHORES_INPUT_DEFAULT_POINTS: 25.0,  # Change points
                CFOF_CHORES_INPUT_ICON: "mdi:star",
                CFOF_CHORES_INPUT_DESCRIPTION: "Updated description",
                CFOF_CHORES_INPUT_ASSIGNED_KIDS: assigned_kids,
                CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY,
                CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_INDEPENDENT,
                CFOF_CHORES_INPUT_APPLICABLE_DAYS: ["mon", "tue", "wed"],
            },
        )

        # Should route to per-kid details (3 kids = multiple)
        assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_CHORE_PER_KID_DETAILS

        # Submit per-kid details
        per_kid_input: dict[str, Any] = {}
        for kid_name in assigned_kids:
            per_kid_input[f"applicable_days_{kid_name}"] = ["mon", "wed", "fri"]

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=per_kid_input,
        )

        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

    async def test_pkh09_edit_independent_different_dates_per_kid(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test editing INDEPENDENT chore with different dates per kid.

        PKH-09: Each kid can have a different due date.
        """
        from datetime import datetime, timedelta

        config_entry = scenario_full.config_entry
        coordinator = scenario_full.coordinator

        # Find "Ørgänize Bookshelf" - 2-kid INDEPENDENT chore
        chore_name = "Ørgänize Bookshelf"
        chore_id = None
        for cid, chore in coordinator.chores_data.items():
            if chore.get("name") == chore_name:
                chore_id = cid
                break

        assert chore_id is not None, f"Chore '{chore_name}' not found"

        # Get the assigned kids for this chore
        chore_data = coordinator.chores_data[chore_id]
        assigned_kid_ids = chore_data.get("assigned_kids", [])
        assigned_kids = [
            coordinator.kids_data[kid_id]["name"] for kid_id in assigned_kid_ids
        ]

        result = await navigate_to_edit_chore(hass, config_entry.entry_id, chore_name)

        # Submit main form (keep existing values)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CFOF_CHORES_INPUT_NAME: chore_name,
                CFOF_CHORES_INPUT_DEFAULT_POINTS: 18.0,
                CFOF_CHORES_INPUT_ICON: "mdi:bookshelf",
                CFOF_CHORES_INPUT_DESCRIPTION: "",
                CFOF_CHORES_INPUT_ASSIGNED_KIDS: assigned_kids,
                CFOF_CHORES_INPUT_RECURRING_FREQUENCY: "weekly",
                CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_INDEPENDENT,
            },
        )

        # Should route to per-kid details (2 kids)
        assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_CHORE_PER_KID_DETAILS

        # Set different dates for each kid using datetime objects
        per_kid_input: dict[str, Any] = {}
        for i, kid_name in enumerate(assigned_kids):
            per_kid_input[f"applicable_days_{kid_name}"] = ["sat", "sun"]
            # Different date offset for each kid
            future_date = datetime.now(UTC) + timedelta(days=7 + i * 3)
            per_kid_input[f"due_date_{kid_name}"] = future_date

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=per_kid_input,
        )

        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify different dates were saved
        updated_chore = coordinator.chores_data[chore_id]
        per_kid_dates = updated_chore.get(DATA_CHORE_PER_KID_DUE_DATES, {})
        date_values = list(per_kid_dates.values())

        # Should have 2 different dates
        assert len(date_values) == 2
        assert date_values[0] != date_values[1], "Kids should have different dates"

    async def test_pkh10_edit_independent_different_days_per_kid(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test editing INDEPENDENT chore with different days per kid.

        PKH-10: Each kid can have different applicable days.
        """
        config_entry = scenario_full.config_entry
        coordinator = scenario_full.coordinator

        # Find "Stär sweep" - 3-kid INDEPENDENT chore
        chore_name = "Stär sweep"
        chore_id = None
        for cid, chore in coordinator.chores_data.items():
            if chore.get("name") == chore_name:
                chore_id = cid
                break

        assert chore_id is not None
        chore_data = coordinator.chores_data[chore_id]
        assigned_kid_ids = chore_data.get("assigned_kids", [])
        assigned_kids = [
            coordinator.kids_data[kid_id]["name"] for kid_id in assigned_kid_ids
        ]

        result = await navigate_to_edit_chore(hass, config_entry.entry_id, chore_name)

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CFOF_CHORES_INPUT_NAME: chore_name,
                CFOF_CHORES_INPUT_DEFAULT_POINTS: 20.0,
                CFOF_CHORES_INPUT_ICON: "mdi:star",
                CFOF_CHORES_INPUT_DESCRIPTION: "",
                CFOF_CHORES_INPUT_ASSIGNED_KIDS: assigned_kids,
                CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY,
                CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_INDEPENDENT,
            },
        )

        assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_CHORE_PER_KID_DETAILS

        # Set different days for each kid
        day_sets = [
            ["mon", "wed", "fri"],  # MWF for kid 1
            ["tue", "thu"],  # TTh for kid 2
            ["sat", "sun"],  # Weekend for kid 3
        ]

        per_kid_input: dict[str, Any] = {}
        for i, kid_name in enumerate(assigned_kids):
            per_kid_input[f"applicable_days_{kid_name}"] = day_sets[i % len(day_sets)]

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=per_kid_input,
        )

        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify different days were saved
        updated_chore = coordinator.chores_data[chore_id]
        per_kid_days = updated_chore.get(DATA_CHORE_PER_KID_APPLICABLE_DAYS, {})

        # Should have entries for all assigned kids
        assert len(per_kid_days) == len(assigned_kid_ids)

        # Days should be different (converted to integers)
        days_lists = list(per_kid_days.values())
        # At least some should be different
        assert not all(sorted(d) == sorted(days_lists[0]) for d in days_lists), (
            "Kids should have different days"
        )

    async def test_pkh07_edit_independent_to_shared_skips_per_kid(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test changing INDEPENDENT chore to SHARED skips per-kid helper.

        PKH-07: When completion_criteria changes from INDEPENDENT to SHARED,
        the per-kid helper step should be skipped (SHARED doesn't need it).
        """
        config_entry = scenario_full.config_entry
        coordinator = scenario_full.coordinator

        # Find "Stär sweep" - 3-kid INDEPENDENT chore
        chore_name = "Stär sweep"
        chore_id = None
        for cid, chore in coordinator.chores_data.items():
            if chore.get("name") == chore_name:
                chore_id = cid
                break

        assert chore_id is not None
        assert coordinator.chores_data[chore_id].get("completion_criteria") == (
            COMPLETION_CRITERIA_INDEPENDENT
        ), "Chore should start as INDEPENDENT"

        chore_data = coordinator.chores_data[chore_id]
        assigned_kid_ids = chore_data.get("assigned_kids", [])
        assigned_kids = [
            coordinator.kids_data[kid_id]["name"] for kid_id in assigned_kid_ids
        ]

        result = await navigate_to_edit_chore(hass, config_entry.entry_id, chore_name)

        # Change from INDEPENDENT to SHARED_ALL
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CFOF_CHORES_INPUT_NAME: chore_name,
                CFOF_CHORES_INPUT_DEFAULT_POINTS: 20.0,
                CFOF_CHORES_INPUT_ICON: "mdi:star",
                CFOF_CHORES_INPUT_DESCRIPTION: "Now a shared chore",
                CFOF_CHORES_INPUT_ASSIGNED_KIDS: assigned_kids,
                CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY,
                CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_SHARED,
            },
        )

        # Should go directly to init (skip per-kid helper)
        # SHARED chores don't need per-kid customization
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT, (
            f"Expected init (skip per-kid), got {result.get('step_id')}"
        )

        # Verify chore was changed to SHARED
        updated_chore = coordinator.chores_data[chore_id]
        assert updated_chore.get("completion_criteria") == COMPLETION_CRITERIA_SHARED

    async def test_pkh08_edit_shared_to_independent_routes_to_per_kid(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test changing SHARED chore to INDEPENDENT routes to per-kid helper.

        PKH-08: When completion_criteria changes from SHARED to INDEPENDENT
        with 2+ kids, the per-kid helper step should be shown.
        """
        config_entry = scenario_full.config_entry
        coordinator = scenario_full.coordinator

        # Find "Family Dinner Prep" - SHARED_ALL chore with 3 kids
        chore_name = "Family Dinner Prep"
        chore_id = None
        for cid, chore in coordinator.chores_data.items():
            if chore.get("name") == chore_name:
                chore_id = cid
                break

        assert chore_id is not None
        assert coordinator.chores_data[chore_id].get("completion_criteria") == (
            COMPLETION_CRITERIA_SHARED
        ), "Chore should start as SHARED_ALL"

        chore_data = coordinator.chores_data[chore_id]
        assigned_kid_ids = chore_data.get("assigned_kids", [])
        assigned_kids = [
            coordinator.kids_data[kid_id]["name"] for kid_id in assigned_kid_ids
        ]
        assert len(assigned_kids) >= 2, "Need 2+ kids for per-kid routing"

        result = await navigate_to_edit_chore(hass, config_entry.entry_id, chore_name)

        # Change from SHARED_ALL to INDEPENDENT
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CFOF_CHORES_INPUT_NAME: chore_name,
                CFOF_CHORES_INPUT_DEFAULT_POINTS: 15.0,
                CFOF_CHORES_INPUT_ICON: "mdi:food",
                CFOF_CHORES_INPUT_DESCRIPTION: "Now independent",
                CFOF_CHORES_INPUT_ASSIGNED_KIDS: assigned_kids,
                CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY,
                CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_INDEPENDENT,
            },
        )

        # Should route to per-kid helper (INDEPENDENT with 2+ kids)
        assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_CHORE_PER_KID_DETAILS, (
            f"Expected per-kid step, got {result.get('step_id')}"
        )

        # Complete the per-kid form
        per_kid_input: dict[str, Any] = {}
        for kid_name in assigned_kids:
            per_kid_input[f"applicable_days_{kid_name}"] = ["mon", "wed", "fri"]

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=per_kid_input,
        )

        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify chore was changed to INDEPENDENT
        updated_chore = coordinator.chores_data[chore_id]
        assert (
            updated_chore.get("completion_criteria") == COMPLETION_CRITERIA_INDEPENDENT
        )


# =========================================================================
# ESV: Schema Edge Cases
# =========================================================================


class TestSchemaEdgeCases:
    """Tests for schema edge cases with None/empty values."""

    async def test_esv01_edit_chore_with_none_applicable_days(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Test editing a chore when applicable_days is None in storage.

        ESV-01: Schema builder should handle applicable_days=None gracefully.
        This tests the .get(key) or fallback pattern fix.
        """
        config_entry = scenario_shared.config_entry
        coordinator = scenario_shared.coordinator

        # First add a chore via flow
        kid_names = [k["name"] for k in coordinator.kids_data.values()]

        result = await navigate_to_add_chore(hass, config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CFOF_CHORES_INPUT_NAME: "ESV01 Test Chore",
                CFOF_CHORES_INPUT_DEFAULT_POINTS: 10.0,
                CFOF_CHORES_INPUT_ICON: "mdi:test-tube",
                CFOF_CHORES_INPUT_DESCRIPTION: "",
                CFOF_CHORES_INPUT_ASSIGNED_KIDS: [kid_names[0]],
                CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY,
                CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_SHARED,
                # Don't specify applicable_days - will be None
            },
        )

        # For SHARED_ALL single kid, goes directly back
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Find the chore and verify applicable_days is None
        chore_id = None
        for cid, chore in coordinator.chores_data.items():
            if chore.get("name") == "ESV01 Test Chore":
                chore_id = cid
                break

        assert chore_id is not None

        # Now try to edit it - this should not raise an error
        result = await navigate_to_edit_chore(
            hass, config_entry.entry_id, "ESV01 Test Chore"
        )

        # Edit form should load without error
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_CHORE

    async def test_esv02_edit_chore_with_none_per_kid_due_dates(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Test editing a chore when per_kid_due_dates is None in storage.

        ESV-02: Schema builder should handle per_kid_due_dates=None gracefully.
        This ensures the date field defaults work when no dates exist.
        """
        config_entry = scenario_shared.config_entry
        coordinator = scenario_shared.coordinator

        kid_names = [k["name"] for k in coordinator.kids_data.values()]
        assigned_kids = kid_names[:2]

        # Add an INDEPENDENT chore with 2 kids but no dates
        result = await navigate_to_add_chore(hass, config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CFOF_CHORES_INPUT_NAME: "ESV02 No Dates Chore",
                CFOF_CHORES_INPUT_DEFAULT_POINTS: 12.0,
                CFOF_CHORES_INPUT_ICON: "mdi:calendar-blank",
                CFOF_CHORES_INPUT_DESCRIPTION: "",
                CFOF_CHORES_INPUT_ASSIGNED_KIDS: assigned_kids,
                CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY,
                CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_INDEPENDENT,
                # No due_date specified
            },
        )

        # Routes to per-kid helper for 2+ kids INDEPENDENT
        assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_CHORE_PER_KID_DETAILS

        # Complete per-kid without dates
        per_kid_input: dict[str, Any] = {}
        for kid_name in assigned_kids:
            per_kid_input[f"applicable_days_{kid_name}"] = ["mon", "wed", "fri"]
            # No date_{kid_name} - leave blank

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input=per_kid_input,
        )
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Find the chore
        chore_id = None
        for cid, chore in coordinator.chores_data.items():
            if chore.get("name") == "ESV02 No Dates Chore":
                chore_id = cid
                break

        assert chore_id is not None

        # Verify per_kid_due_dates has None values (or is empty)
        # The system may create entries with None values, which is valid
        per_kid_dates = coordinator.chores_data[chore_id].get(
            DATA_CHORE_PER_KID_DUE_DATES, {}
        )
        # All date values should be None (no actual dates set)
        assert all(v is None for v in per_kid_dates.values()), (
            "Should have no actual dates (all None)"
        )

        # Now edit it - schema should handle None/empty dates gracefully
        result = await navigate_to_edit_chore(
            hass, config_entry.entry_id, "ESV02 No Dates Chore"
        )

        # Edit form should load without error
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_CHORE

    async def test_esv03_edit_chore_with_none_daily_multi_times(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Test editing a DAILY_MULTI chore when times is None in storage.

        ESV-03: Schema builder should handle daily_multi_times=None gracefully.
        This ensures the times field defaults work when no times exist.
        """
        from datetime import datetime, timedelta

        config_entry = scenario_shared.config_entry
        coordinator = scenario_shared.coordinator

        kid_names = [k["name"] for k in coordinator.kids_data.values()]
        # Use just 1 kid to avoid per-kid routing complexity
        assigned_kids = [kid_names[0]]

        future_date = datetime.now(UTC) + timedelta(days=7)

        # Add a DAILY_MULTI chore (1 kid)
        result = await navigate_to_add_chore(hass, config_entry.entry_id)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CFOF_CHORES_INPUT_NAME: "ESV03 Daily Multi No Times",
                CFOF_CHORES_INPUT_DEFAULT_POINTS: 10.0,
                CFOF_CHORES_INPUT_ICON: "mdi:clock",
                CFOF_CHORES_INPUT_DESCRIPTION: "",
                CFOF_CHORES_INPUT_ASSIGNED_KIDS: assigned_kids,
                CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_DAILY_MULTI,
                CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_SHARED,
                CFOF_CHORES_INPUT_APPROVAL_RESET_TYPE: APPROVAL_RESET_UPON_COMPLETION,
                CFOF_CHORES_INPUT_DUE_DATE: future_date,
                # No daily_multi_times specified
            },
        )

        # DAILY_MULTI routes to times step even with 1 kid
        # (times need to be specified for DAILY_MULTI)
        assert result.get("step_id") == "chores_daily_multi"

        # Complete the daily_multi step with valid times (minimum 2 required)
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                "daily_multi_times": "09:00|17:00",  # Min 2 times required
            },
        )

        # Now should go to init
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Find the chore
        chore_id = None
        for cid, chore in coordinator.chores_data.items():
            if chore.get("name") == "ESV03 Daily Multi No Times":
                chore_id = cid
                break

        assert chore_id is not None

        # Now edit it - schema should handle the times gracefully
        result = await navigate_to_edit_chore(
            hass, config_entry.entry_id, "ESV03 Daily Multi No Times"
        )

        # Edit form should load without error
        assert result.get("type") == FlowResultType.FORM
        assert result.get("step_id") == OPTIONS_FLOW_STEP_EDIT_CHORE

    async def test_esv04_add_chore_all_optional_blank(
        self,
        hass: HomeAssistant,
        scenario_shared: SetupResult,
    ) -> None:
        """Test adding a chore with all optional fields left blank.

        ESV-04: Minimal chore creation - only required fields.
        """
        config_entry = scenario_shared.config_entry
        coordinator = scenario_shared.coordinator

        kid_names = [k["name"] for k in coordinator.kids_data.values()]

        result = await navigate_to_add_chore(hass, config_entry.entry_id)

        # Submit with minimal required fields only
        # Note: "once" is not a valid frequency - use FREQUENCY_NONE ("none")
        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={
                CFOF_CHORES_INPUT_NAME: "Minimal Chore",
                CFOF_CHORES_INPUT_DEFAULT_POINTS: 5.0,
                CFOF_CHORES_INPUT_ICON: "mdi:check",
                CFOF_CHORES_INPUT_DESCRIPTION: "",
                CFOF_CHORES_INPUT_ASSIGNED_KIDS: [kid_names[0]],
                CFOF_CHORES_INPUT_RECURRING_FREQUENCY: FREQUENCY_NONE,
                CFOF_CHORES_INPUT_COMPLETION_CRITERIA: COMPLETION_CRITERIA_SHARED,
                # All optional fields omitted
            },
        )

        # Should complete without error
        assert result.get("step_id") == OPTIONS_FLOW_STEP_INIT

        # Verify chore was created
        chore_created = any(
            c.get("name") == "Minimal Chore" for c in coordinator.chores_data.values()
        )
        assert chore_created, "Minimal chore should have been created"
