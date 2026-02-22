"""Tests for reset_transactional_data service (Unified Data Reset V2).

This module tests:
- Safety mechanism (confirm_destructive required)
- Global scope reset (all domains)
- Per-assignee scope reset (single assignee)
- Item type filtering (single domain)
- Validation errors (invalid inputs)

Testing approach:
- Uses scenario_full fixture for comprehensive data
- Verifies state changes via coordinator data and entity states
- Tests both positive paths and error conditions

See docs/in-process/DATA_RESET_SERVICE_V2_IN-PROCESS.md for full specification.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.exceptions import HomeAssistantError
import pytest
import voluptuous as vol

from tests.helpers import DOMAIN, SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# ============================================================================
# CONSTANTS
# ============================================================================

SERVICE_RESET_TRANSACTIONAL_DATA = "reset_transactional_data"

# Service field names (literal strings as documented in services.yaml)
FIELD_CONFIRM_DESTRUCTIVE = "confirm_destructive"
FIELD_SCOPE = "scope"
FIELD_ASSIGNEE_NAME = "assignee_name"
FIELD_ITEM_TYPE = "item_type"
FIELD_ITEM_NAME = "item_name"

# Scope values
SCOPE_GLOBAL = "global"
SCOPE_ASSIGNEE = "assignee"

# Item types
ITEM_TYPE_POINTS = "points"
ITEM_TYPE_CHORES = "chores"
ITEM_TYPE_REWARDS = "rewards"
ITEM_TYPE_BADGES = "badges"


# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
async def scenario_full(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load full scenario: 3 assignees, 2 approvers, 19 chores, rewards."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def get_assignee_points(result: SetupResult, assignee_name: str) -> float:
    """Get current points for a assignee by name."""
    for assignee_data in result.coordinator.assignees_data.values():
        if assignee_data.get("name") == assignee_name:
            return assignee_data.get("points", 0)
    return 0


def get_assignee_multiplier(result: SetupResult, assignee_name: str) -> float:
    """Get current points multiplier for a assignee by name."""
    for assignee_data in result.coordinator.assignees_data.values():
        if assignee_data.get("name") == assignee_name:
            return assignee_data.get("points_multiplier", 1.0)
    return 1.0


def get_assignee_chore_data(result: SetupResult, assignee_name: str) -> dict[str, Any]:
    """Get chore_data dict for a assignee by name."""
    for assignee_data in result.coordinator.assignees_data.values():
        if assignee_data.get("name") == assignee_name:
            return assignee_data.get("chore_data", {})
    return {}


def get_assignee_ledger(result: SetupResult, assignee_name: str) -> list[Any]:
    """Get ledger for a assignee by name."""
    for assignee_data in result.coordinator.assignees_data.values():
        if assignee_data.get("name") == assignee_name:
            return assignee_data.get("ledger", [])
    return []


def set_assignee_points(result: SetupResult, assignee_name: str, points: float) -> None:
    """Set points for a assignee (for test setup)."""
    for assignee_data in result.coordinator.assignees_data.values():
        if assignee_data.get("name") == assignee_name:
            assignee_data["points"] = points
            assignee_data["ledger"] = [{"type": "test", "points": points}]
            return


# ============================================================================
# SAFETY MECHANISM TESTS
# ============================================================================


class TestDataResetSafetyMechanism:
    """Test that confirm_destructive is required for safety."""

    @pytest.mark.asyncio
    async def test_fails_without_confirm_destructive(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test service fails when confirm_destructive is missing (schema validation)."""
        # Schema validation should fail since confirm_destructive is required
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RESET_TRANSACTIONAL_DATA,
                {
                    # confirm_destructive missing!
                    FIELD_SCOPE: SCOPE_GLOBAL,
                },
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_fails_with_false_confirm_destructive(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test service fails when confirm_destructive is False."""
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RESET_TRANSACTIONAL_DATA,
                {
                    FIELD_CONFIRM_DESTRUCTIVE: False,
                    FIELD_SCOPE: SCOPE_GLOBAL,
                },
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_succeeds_with_true_confirm_destructive(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test service succeeds when confirm_destructive is True."""
        # Give a assignee some points to verify reset works
        set_assignee_points(scenario_full, "Zoë", 100)

        # Mock _persist to avoid actual storage writes
        with (
            patch.object(scenario_full.coordinator, "_persist", new=MagicMock()),
            patch.object(
                scenario_full.coordinator.notification_manager,
                "broadcast_to_all_approvers",
                new=AsyncMock(),
            ),
        ):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RESET_TRANSACTIONAL_DATA,
                {
                    FIELD_CONFIRM_DESTRUCTIVE: True,
                    FIELD_SCOPE: SCOPE_GLOBAL,
                },
                blocking=True,
            )

        # Service completed without error - that's the success condition
        # Points should be reset to 0
        assert get_assignee_points(scenario_full, "Zoë") == 0


# ============================================================================
# GLOBAL SCOPE TESTS
# ============================================================================


class TestDataResetGlobalScope:
    """Test global scope resets all data for all assignees."""

    @pytest.mark.asyncio
    async def test_global_resets_all_assignees_points(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test global scope resets points for all assignees."""
        # Setup: Give all assignees different point balances
        set_assignee_points(scenario_full, "Zoë", 100)
        set_assignee_points(scenario_full, "Max!", 200)
        set_assignee_points(scenario_full, "Lila", 300)

        with (
            patch.object(scenario_full.coordinator, "_persist", new=MagicMock()),
            patch.object(
                scenario_full.coordinator.notification_manager,
                "broadcast_to_all_approvers",
                new=AsyncMock(),
            ),
        ):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RESET_TRANSACTIONAL_DATA,
                {
                    FIELD_CONFIRM_DESTRUCTIVE: True,
                    FIELD_SCOPE: SCOPE_GLOBAL,
                },
                blocking=True,
            )

        # Verify all assignees' points are reset to 0
        assert get_assignee_points(scenario_full, "Zoë") == 0
        assert get_assignee_points(scenario_full, "Max!") == 0
        assert get_assignee_points(scenario_full, "Lila") == 0

    @pytest.mark.asyncio
    async def test_global_resets_all_assignees_multipliers(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test global scope resets multipliers for all assignees."""
        with (
            patch.object(scenario_full.coordinator, "_persist", new=MagicMock()),
            patch.object(
                scenario_full.coordinator.notification_manager,
                "broadcast_to_all_approvers",
                new=AsyncMock(),
            ),
        ):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RESET_TRANSACTIONAL_DATA,
                {
                    FIELD_CONFIRM_DESTRUCTIVE: True,
                    FIELD_SCOPE: SCOPE_GLOBAL,
                },
                blocking=True,
            )

        # Verify all assignees' multipliers are reset to 1.0
        assert get_assignee_multiplier(scenario_full, "Zoë") == 1.0
        assert get_assignee_multiplier(scenario_full, "Max!") == 1.0
        assert get_assignee_multiplier(scenario_full, "Lila") == 1.0

    @pytest.mark.asyncio
    async def test_global_clears_all_assignees_ledgers(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test global scope clears ledgers for all assignees."""
        # Setup: Give assignees ledger entries via points
        set_assignee_points(scenario_full, "Zoë", 50)
        assert len(get_assignee_ledger(scenario_full, "Zoë")) > 0

        with (
            patch.object(scenario_full.coordinator, "_persist", new=MagicMock()),
            patch.object(
                scenario_full.coordinator.notification_manager,
                "broadcast_to_all_approvers",
                new=AsyncMock(),
            ),
        ):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RESET_TRANSACTIONAL_DATA,
                {
                    FIELD_CONFIRM_DESTRUCTIVE: True,
                    FIELD_SCOPE: SCOPE_GLOBAL,
                },
                blocking=True,
            )

        # Verify ledgers are cleared
        assert get_assignee_ledger(scenario_full, "Zoë") == []


# ============================================================================
# PER-KID SCOPE TESTS
# ============================================================================


class TestDataResetAssigneeScope:
    """Test assignee scope resets data only for target assignee."""

    @pytest.mark.asyncio
    async def test_assignee_scope_resets_only_target_assignee(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test assignee scope resets only the specified assignee, others untouched."""
        # Setup: Give all assignees different point balances
        set_assignee_points(scenario_full, "Zoë", 100)
        set_assignee_points(scenario_full, "Max!", 200)
        set_assignee_points(scenario_full, "Lila", 300)

        with (
            patch.object(scenario_full.coordinator, "_persist", new=MagicMock()),
            patch.object(
                scenario_full.coordinator.notification_manager,
                "broadcast_to_all_approvers",
                new=AsyncMock(),
            ),
        ):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RESET_TRANSACTIONAL_DATA,
                {
                    FIELD_CONFIRM_DESTRUCTIVE: True,
                    FIELD_SCOPE: SCOPE_ASSIGNEE,
                    FIELD_ASSIGNEE_NAME: "Zoë",
                },
                blocking=True,
            )

        # Verify only Zoë's points are reset
        assert get_assignee_points(scenario_full, "Zoë") == 0
        # Other assignees should be untouched
        assert get_assignee_points(scenario_full, "Max!") == 200
        assert get_assignee_points(scenario_full, "Lila") == 300

    @pytest.mark.asyncio
    async def test_assignee_scope_requires_assignee_name(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test assignee scope fails without assignee_name."""
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RESET_TRANSACTIONAL_DATA,
                {
                    FIELD_CONFIRM_DESTRUCTIVE: True,
                    FIELD_SCOPE: SCOPE_ASSIGNEE,
                    # assignee_name missing!
                },
                blocking=True,
            )


# ============================================================================
# ITEM TYPE FILTER TESTS
# ============================================================================


class TestDataResetItemTypeFilter:
    """Test item_type filtering resets only specific domains."""

    @pytest.mark.asyncio
    async def test_item_type_points_only(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test item_type: points resets only economy data."""
        # Setup: Give assignee points
        set_assignee_points(scenario_full, "Zoë", 100)

        with (
            patch.object(scenario_full.coordinator, "_persist", new=MagicMock()),
            patch.object(
                scenario_full.coordinator.notification_manager,
                "broadcast_to_all_approvers",
                new=AsyncMock(),
            ),
        ):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RESET_TRANSACTIONAL_DATA,
                {
                    FIELD_CONFIRM_DESTRUCTIVE: True,
                    FIELD_ITEM_TYPE: ITEM_TYPE_POINTS,
                },
                blocking=True,
            )

        # Verify points are reset
        assert get_assignee_points(scenario_full, "Zoë") == 0


# ============================================================================
# VALIDATION ERROR TESTS
# ============================================================================


class TestDataResetValidationErrors:
    """Test validation errors for invalid inputs."""

    @pytest.mark.asyncio
    async def test_invalid_scope_rejected(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test invalid scope value is rejected by schema."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RESET_TRANSACTIONAL_DATA,
                {
                    FIELD_CONFIRM_DESTRUCTIVE: True,
                    FIELD_SCOPE: "invalid_scope",
                },
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_invalid_item_type_rejected(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test invalid item_type value is rejected by schema."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RESET_TRANSACTIONAL_DATA,
                {
                    FIELD_CONFIRM_DESTRUCTIVE: True,
                    FIELD_ITEM_TYPE: "invalid_item_type",
                },
                blocking=True,
            )

    @pytest.mark.asyncio
    async def test_unknown_assignee_name_raises_error(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test unknown assignee_name raises translated error."""
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RESET_TRANSACTIONAL_DATA,
                {
                    FIELD_CONFIRM_DESTRUCTIVE: True,
                    FIELD_SCOPE: SCOPE_ASSIGNEE,
                    FIELD_ASSIGNEE_NAME: "NonexistentAssignee",
                },
                blocking=True,
            )


# ============================================================================
# BACKUP CREATION TESTS
# ============================================================================


class TestDataResetBackupCreation:
    """Test that backup is created before reset."""

    @pytest.mark.asyncio
    async def test_backup_created_before_reset(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test backup is created before data is reset."""
        backup_created = False

        async def mock_create_backup(*args, **kwargs):
            nonlocal backup_created
            backup_created = True
            return "choreops_data_test_backup"

        with (
            patch(
                "custom_components.choreops.helpers.backup_helpers.create_timestamped_backup",
                new=mock_create_backup,
            ),
            patch.object(scenario_full.coordinator, "_persist", new=MagicMock()),
            patch.object(
                scenario_full.coordinator.notification_manager,
                "broadcast_to_all_approvers",
                new=AsyncMock(),
            ),
        ):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RESET_TRANSACTIONAL_DATA,
                {
                    FIELD_CONFIRM_DESTRUCTIVE: True,
                    FIELD_SCOPE: SCOPE_GLOBAL,
                },
                blocking=True,
            )

        assert backup_created, "Backup should be created before reset"


# ============================================================================
# NOTIFICATION TESTS
# ============================================================================


class TestDataResetNotification:
    """Test that notifications are sent after reset."""

    @pytest.mark.asyncio
    async def test_notification_sent_after_global_reset(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Test notification is sent to approvers after global reset."""
        notification_sent = False

        async def mock_broadcast(*args, **kwargs):
            nonlocal notification_sent
            notification_sent = True

        with (
            patch.object(scenario_full.coordinator, "_persist", new=MagicMock()),
            patch.object(
                scenario_full.coordinator.notification_manager,
                "broadcast_to_all_approvers",
                new=mock_broadcast,
            ),
        ):
            await hass.services.async_call(
                DOMAIN,
                SERVICE_RESET_TRANSACTIONAL_DATA,
                {
                    FIELD_CONFIRM_DESTRUCTIVE: True,
                    FIELD_SCOPE: SCOPE_GLOBAL,
                },
                blocking=True,
            )

        assert notification_sent, "Notification should be sent after reset"
