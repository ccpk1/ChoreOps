"""Edge case tests for kc_helpers module.

Tests for:
- Item lookup helpers (get_item_id_by_name, get_item_id_or_raise)
- Authorization helpers (is_user_authorized_for_action)
- Progress calculation helpers
- Datetime boundary handling in dt_add_interval

NOTE: Some functions have been migrated to helpers/ modules:
- entity_helpers: get_integration_entities, parse_entity_reference, build_orphan_detection_regex,
                  get_item_id_by_name, get_item_id_or_raise, get_item_name_or_log_error,
                  get_kid_name_by_id, get_event_signal
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
    """Load minimal scenario: 1 kid, 1 parent, 5 chores (all independent)."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


class TestEntityLookupHelpers:
    """Test entity lookup functions with edge cases."""

    async def test_lookup_existing_entity(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should find existing entity by name."""
        coordinator = scenario_minimal.coordinator

        kid_id = scenario_minimal.kid_ids["Zoë"]
        kid_info = coordinator.kids_data.get(kid_id, {})
        kid_name = kid_info.get(const.DATA_KID_NAME)

        result = get_item_id_by_name(coordinator, const.ENTITY_TYPE_KID, str(kid_name))

        assert result == kid_id

    async def test_lookup_missing_entity_returns_none(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should return None for missing entity."""
        coordinator = scenario_minimal.coordinator

        result = get_item_id_by_name(
            coordinator, const.ENTITY_TYPE_KID, "NonexistentKid"
        )

        assert result is None

    async def test_lookup_or_raise_raises_on_missing(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should raise HomeAssistantError on missing entity."""
        from custom_components.choreops import const

        coordinator = scenario_minimal.coordinator

        with pytest.raises(HomeAssistantError):
            get_item_id_or_raise(coordinator, const.ENTITY_TYPE_KID, "NonexistentKid")


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
        unique_id = "entry_123_kid_456_chore_789"
        prefix = "entry_123_"

        result = parse_entity_reference(unique_id, prefix)

        assert result == ("kid", "456", "chore", "789")

    async def test_parse_entity_reference_invalid_prefix(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should return None when prefix doesn't match."""
        unique_id = "entry_999_kid_456"
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
        valid_ids = ["kid_1", "kid_2", "kid_3"]
        pattern = build_orphan_detection_regex(valid_ids)

        # Should match using search() - pattern matches valid IDs anywhere in string
        assert pattern.search("kc_kid_1_chore_123") is not None
        assert pattern.search("kc_kid_2_reward_456") is not None
        assert pattern.search("entry_kid_3_points") is not None

    async def test_build_orphan_detection_regex_rejects_invalid(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should not match entities from deleted IDs."""
        valid_ids = ["kid_1", "kid_2"]
        pattern = build_orphan_detection_regex(valid_ids)

        # kid_3 not in valid list - should not match
        assert pattern.search("kc_kid_3_chore_999") is None

    async def test_build_orphan_detection_regex_empty_list(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should return pattern that never matches when no valid IDs."""
        pattern = build_orphan_detection_regex([])

        # Should not match anything
        assert pattern.search("kc_kid_1_chore_123") is None
        assert pattern.search("kc_anything") is None

    async def test_build_orphan_detection_regex_performance(
        self, hass: HomeAssistant, scenario_minimal: SetupResult
    ) -> None:
        """Should handle large ID lists efficiently (performance test)."""
        # Simulate 100 kids (large installation)
        valid_ids = [f"kid_{i}" for i in range(100)]
        pattern = build_orphan_detection_regex(valid_ids)

        # Should still match efficiently using search()
        assert pattern.search("kc_kid_0_chore_123") is not None
        assert pattern.search("kc_kid_50_reward_456") is not None
        assert pattern.search("entry_kid_99_points") is not None
        assert pattern.search("kc_kid_100_chore_789") is None  # Not in valid list


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
        """Registered parent user should be authorized for global actions."""
        parent_user = mock_hass_users["parent1"]

        is_authorized = await is_user_authorized_for_action(
            hass,
            parent_user.id,
            AUTH_ACTION_MANAGEMENT,
        )

        # Parent users ARE authorized when registered in coordinator.parents_data
        assert is_authorized is True

    async def test_non_parent_non_admin_global_denied(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Kid user should be denied for global actions without parent capability."""
        kid_user = mock_hass_users["kid1"]

        is_authorized = await is_user_authorized_for_action(
            hass,
            kid_user.id,
            AUTH_ACTION_MANAGEMENT,
        )

        assert is_authorized is False

    async def test_admin_user_kid_authorization_override(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Admin user should be authorized for kid-scoped actions."""
        admin_user = mock_hass_users["admin"]
        kid_id = scenario_minimal.kid_ids["Zoë"]

        is_authorized = await is_user_authorized_for_action(
            hass,
            admin_user.id,
            AUTH_ACTION_APPROVAL,
            target_user_id=kid_id,
        )

        assert is_authorized is True

    async def test_kid_self_authorization_allows_kid_scope(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Kid linked to the target kid_id should be authorized for kid scope."""
        kid_user = mock_hass_users["kid1"]
        kid_id = scenario_minimal.kid_ids["Zoë"]

        is_authorized = await is_user_authorized_for_action(
            hass,
            kid_user.id,
            AUTH_ACTION_APPROVAL,
            target_user_id=kid_id,
        )

        assert is_authorized is True

    async def test_unrelated_kid_denied_kid_scope(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Unrelated kid should be denied when not admin and not parent."""
        unrelated_kid_user = mock_hass_users["kid2"]
        kid_id = scenario_minimal.kid_ids["Zoë"]

        is_authorized = await is_user_authorized_for_action(
            hass,
            unrelated_kid_user.id,
            AUTH_ACTION_APPROVAL,
            target_user_id=kid_id,
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
