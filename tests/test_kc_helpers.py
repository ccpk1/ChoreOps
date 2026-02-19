"""Edge case tests for kc_helpers module.

Tests for:
- Item lookup helpers (get_item_id_by_name, get_item_id_or_raise)
- Authorization helpers (is_user_authorized_for_action)
- Progress calculation helpers
- Datetime boundary handling in dt_add_interval

NOTE: Some functions have been migrated to helpers/ modules:
- entity_helpers: get_integration_entities, parse_entity_reference, build_orphan_detection_regex,
                  get_item_id_by_name, get_item_id_or_raise, get_item_name_or_log_error,
                  get_assignee_name_by_id, get_event_signal
- auth_helpers: is_user_authorized_for_action
"""

from datetime import UTC, datetime
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.choreops import const
from custom_components.choreops.helpers.auth_helpers import (
    AUTH_ACTION_APPROVAL,
    AUTH_ACTION_MANAGEMENT,
    AUTH_ACTION_PARTICIPATION,
    is_kiosk_mode_enabled,
    is_user_authorized_for_action,
)
from custom_components.choreops.helpers.entity_helpers import (
    build_orphan_detection_regex,
    get_integration_entities,
    get_item_id_by_name,
    get_item_id_or_raise,
    parse_entity_reference,
)
from custom_components.choreops.utils.dt_utils import dt_add_interval
from tests.helpers.setup import SetupResult, setup_from_yaml


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario: 1 assignee, 1 approver, 5 chores (all independent)."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


def _set_user_capabilities(
    setup_result: SetupResult,
    ha_user_id: str,
    *,
    can_approve: bool,
    can_manage: bool,
) -> None:
    """Set capability flags for the user record linked to an HA user ID."""

    def _record_ha_user_ref(user_data: dict[str, Any]) -> str | None:
        for key in (
            const.DATA_USER_HA_USER_ID,
            const.DATA_USER_HA_USER_ID,
            const.DATA_USER_HA_USER_ID,
        ):
            value = user_data.get(key)
            if isinstance(value, str) and value:
                return value
        return None

    users = setup_result.coordinator._data.get(const.DATA_USERS, {})
    if not isinstance(users, dict):
        raise TypeError("Users data missing in scenario setup")

    for user_data_raw in users.values():
        if not isinstance(user_data_raw, dict):
            continue
        if _record_ha_user_ref(user_data_raw) == ha_user_id:
            user_data_raw[const.DATA_USER_CAN_APPROVE] = can_approve
            user_data_raw[const.DATA_USER_CAN_MANAGE] = can_manage
            return

    raise AssertionError(f"No user record found for HA user ID: {ha_user_id}")


class TestEntityLookupHelpers:
    """Test entity lookup functions with edge cases."""

    async def test_lookup_existing_entity(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should find existing entity by name."""
        coordinator = scenario_minimal.coordinator

        assignee_id = scenario_minimal.assignee_ids["Zoë"]
        assignee_info = coordinator.assignees_data.get(assignee_id, {})
        assignee_name = assignee_info.get(const.DATA_USER_NAME)

        result = get_item_id_by_name(
            coordinator,
            const.ITEM_TYPE_USER,
            str(assignee_name),
            role=const.ROLE_ASSIGNEE,
        )

        assert result == assignee_id

    async def test_lookup_missing_entity_returns_none(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should return None for missing entity."""
        coordinator = scenario_minimal.coordinator

        result = get_item_id_by_name(
            coordinator,
            const.ITEM_TYPE_USER,
            "NonexistentAssignee",
            role=const.ROLE_ASSIGNEE,
        )

        assert result is None

    async def test_lookup_or_raise_raises_on_missing(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should raise HomeAssistantError on missing entity."""
        from custom_components.choreops import const

        coordinator = scenario_minimal.coordinator

        with pytest.raises(HomeAssistantError):
            get_item_id_or_raise(
                coordinator,
                const.ITEM_TYPE_USER,
                "NonexistentAssignee",
                role=const.ROLE_ASSIGNEE,
            )


class TestEntityRegistryUtilities:
    """Test entity registry query and parsing utilities."""

    async def test_get_integration_entities_all_platforms(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should retrieve all integration entities when no platform filter."""
        entry = scenario_minimal.config_entry

        entities = get_integration_entities(hass, entry.entry_id)

        # Should have sensors, buttons, etc. for minimal scenario
        assert len(entities) > 0
        # All entities should belong to this config entry
        assert all(e.config_entry_id == entry.entry_id for e in entities)

    async def test_get_integration_entities_filtered_by_platform(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should filter entities by platform when specified."""
        entry = scenario_minimal.config_entry

        sensors = get_integration_entities(hass, entry.entry_id, "sensor")
        buttons = get_integration_entities(hass, entry.entry_id, "button")

        # Should have both sensors and buttons
        assert len(sensors) > 0
        assert len(buttons) > 0
        # All should be correct platform
        assert all(e.domain == "sensor" for e in sensors)
        assert all(e.domain == "button" for e in buttons)

    async def test_parse_entity_reference_valid(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should parse valid entity unique_id correctly."""
        unique_id = "entry_123_assignee_456_chore_789"
        prefix = "entry_123_"

        result = parse_entity_reference(unique_id, prefix)

        assert result == ("assignee", "456", "chore", "789")

    async def test_parse_entity_reference_invalid_prefix(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should return None when prefix doesn't match."""
        unique_id = "entry_999_assignee_456"
        prefix = "entry_123_"

        result = parse_entity_reference(unique_id, prefix)

        assert result is None

    async def test_parse_entity_reference_empty_remainder(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should return None when nothing after prefix."""
        unique_id = "entry_123_"
        prefix = "entry_123_"

        result = parse_entity_reference(unique_id, prefix)

        assert result is None

    async def test_build_orphan_detection_regex_matches_valid(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should match entities belonging to valid IDs."""
        valid_ids = ["assignee_1", "assignee_2", "assignee_3"]
        pattern = build_orphan_detection_regex(valid_ids)

        # Should match using search() - pattern matches valid IDs anywhere in string
        assert pattern.search("kc_assignee_1_chore_123") is not None
        assert pattern.search("kc_assignee_2_reward_456") is not None
        assert pattern.search("entry_assignee_3_points") is not None

    async def test_build_orphan_detection_regex_rejects_invalid(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should not match entities from deleted IDs."""
        valid_ids = ["assignee_1", "assignee_2"]
        pattern = build_orphan_detection_regex(valid_ids)

        # assignee_3 not in valid list - should not match
        assert pattern.search("kc_assignee_3_chore_999") is None

    async def test_build_orphan_detection_regex_empty_list(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should return pattern that never matches when no valid IDs."""
        pattern = build_orphan_detection_regex([])

        # Should not match anything
        assert pattern.search("kc_assignee_1_chore_123") is None
        assert pattern.search("kc_anything") is None

    async def test_build_orphan_detection_regex_performance(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should handle large ID lists efficiently (performance test)."""
        # Simulate 100 assignees (large installation)
        valid_ids = [f"assignee_{i}" for i in range(100)]
        pattern = build_orphan_detection_regex(valid_ids)

        # Should still match efficiently using search()
        assert pattern.search("kc_assignee_0_chore_123") is not None
        assert pattern.search("kc_assignee_50_reward_456") is not None
        assert pattern.search("entry_assignee_99_points") is not None
        assert pattern.search("kc_assignee_100_chore_789") is None  # Not in valid list


class TestAuthorizationHelpers:
    """Test authorization check functions."""

    async def test_admin_user_global_authorization(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Admin user should be authorized for global actions."""
        admin_user = mock_hass_users["admin"]

        is_authorized = await is_user_authorized_for_action(
            hass,
            admin_user.id,
            AUTH_ACTION_MANAGEMENT,
        )

        assert is_authorized is True

    async def test_non_admin_user_global_authorization(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Registered approver user should be authorized for global actions."""
        approver_user = mock_hass_users["approver1"]
        _set_user_capabilities(
            scenario_minimal,
            approver_user.id,
            can_approve=True,
            can_manage=True,
        )

        is_authorized = await is_user_authorized_for_action(
            hass,
            approver_user.id,
            AUTH_ACTION_MANAGEMENT,
        )

        # Approver users ARE authorized when registered in coordinator.approvers_data
        assert is_authorized is True

    async def test_non_approver_non_admin_global_denied(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Assignee user should be denied for global actions without approver capability."""
        assignee_user = mock_hass_users["assignee1"]

        is_authorized = await is_user_authorized_for_action(
            hass,
            assignee_user.id,
            AUTH_ACTION_MANAGEMENT,
        )

        assert is_authorized is False

    async def test_admin_user_assignee_authorization_override(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Admin user should be authorized for assignee-scoped actions."""
        admin_user = mock_hass_users["admin"]
        assignee_id = scenario_minimal.assignee_ids["Zoë"]

        is_authorized = await is_user_authorized_for_action(
            hass,
            admin_user.id,
            AUTH_ACTION_APPROVAL,
            target_user_id=assignee_id,
        )

        assert is_authorized is True

    async def test_assignee_self_authorization_allows_assignee_scope(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Assignee linked to the target assignee_id should be authorized for assignee scope."""
        assignee_user = mock_hass_users["assignee1"]
        assignee_id = scenario_minimal.assignee_ids["Zoë"]

        is_authorized = await is_user_authorized_for_action(
            hass,
            assignee_user.id,
            AUTH_ACTION_PARTICIPATION,
            target_user_id=assignee_id,
        )

        assert is_authorized is True

    async def test_unrelated_assignee_denied_assignee_scope(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Unrelated assignee should be denied when not admin and not approver."""
        unrelated_assignee_user = mock_hass_users["assignee2"]
        assignee_id = scenario_minimal.assignee_ids["Zoë"]

        is_authorized = await is_user_authorized_for_action(
            hass,
            unrelated_assignee_user.id,
            AUTH_ACTION_APPROVAL,
            target_user_id=assignee_id,
        )

        assert is_authorized is False

    async def test_kiosk_mode_defaults_to_disabled(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Kiosk mode should default to disabled when option is not set."""
        assert is_kiosk_mode_enabled(hass) is False

    async def test_kiosk_mode_enabled_when_option_set(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Kiosk mode helper should read enabled state from config entry options."""
        config_entry = scenario_minimal.config_entry

        hass.config_entries.async_update_entry(
            config_entry,
            options={
                **config_entry.options,
                const.CONF_KIOSK_MODE: True,
            },
        )
        await hass.async_block_till_done()

        assert is_kiosk_mode_enabled(hass) is True


class TestDatetimeBoundaryHandling:
    """Test datetime handling in dt_add_interval."""

    async def test_month_end_transition(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should handle month-end boundary correctly."""
        jan_31 = datetime(2025, 1, 31, 12, 0, 0, tzinfo=UTC)

        result = dt_add_interval(jan_31, const.TIME_UNIT_MONTHS, 1)

        # Adding 1 month from Jan 31 should give Feb 28 (or 29 in leap year)
        assert result is not None
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC

    async def test_year_transition(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should handle year boundary correctly."""
        dec_31 = datetime(2024, 12, 31, 23, 59, 59, tzinfo=UTC)

        result = dt_add_interval(dec_31, const.TIME_UNIT_YEARS, 1)

        assert result is not None
        assert isinstance(result, datetime)
        assert result.tzinfo == UTC
