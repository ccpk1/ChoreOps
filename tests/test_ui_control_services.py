"""Tests for the `manage_ui_control` service."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.exceptions import HomeAssistantError
import pytest

from custom_components.choreops import const
from tests.helpers import SetupResult, setup_from_yaml

REWARDS_HEADER_COLLAPSE_KEY = "gamification/rewards/header_collapse"
CHORES_HEADER_COLLAPSE_KEY = "gamification/chores/header_collapse"

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture
async def scenario_full(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load full scenario for UI control service testing."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


def _get_helper_ui_control(hass: HomeAssistant, assignee_slug: str) -> dict[str, Any]:
    """Return the dashboard helper `ui_control` payload for one user."""
    helper_state = hass.states.get(
        f"sensor.{assignee_slug}_choreops_ui_dashboard_helper"
    )
    assert helper_state is not None

    ui_control = helper_state.attributes.get(const.ATTR_UI_CONTROL)
    assert isinstance(ui_control, dict)
    return ui_control


def _get_shared_admin_ui_control(scenario_full: SetupResult) -> dict[str, Any]:
    """Return the persisted shared-admin UI control payload."""
    shared_admin_ui_control = scenario_full.coordinator._data[const.DATA_META][
        const.DATA_META_SHARED_ADMIN_UI_CONTROL
    ]
    assert isinstance(shared_admin_ui_control, dict)
    return shared_admin_ui_control


class TestManageUiControlService:
    """Service tests for durable per-user UI controls."""

    @pytest.mark.asyncio
    async def test_create_updates_helper_and_returns_response(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Create should persist the control and refresh the helper payload."""
        user_id = scenario_full.assignee_ids["Zoë"]

        response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_MANAGE_UI_CONTROL,
            {
                const.SERVICE_FIELD_CONFIG_ENTRY_ID: scenario_full.config_entry.entry_id,
                const.SERVICE_FIELD_USER_NAME: "Zoë",
                const.SERVICE_FIELD_UI_CONTROL_ACTION: const.UI_CONTROL_ACTION_CREATE,
                const.SERVICE_FIELD_UI_CONTROL_KEY: REWARDS_HEADER_COLLAPSE_KEY,
                const.SERVICE_FIELD_UI_CONTROL_VALUE: True,
            },
            blocking=True,
            return_response=True,
        )

        await hass.async_block_till_done()

        assert response == {
            const.SERVICE_FIELD_USER_ID: user_id,
            const.SERVICE_FIELD_UI_CONTROL_TARGET: const.UI_CONTROL_TARGET_USER,
            const.SERVICE_FIELD_UI_CONTROL_ACTION: const.UI_CONTROL_ACTION_CREATE,
            const.SERVICE_FIELD_UI_CONTROL_KEY: REWARDS_HEADER_COLLAPSE_KEY,
            "cleared_all": False,
            "user_name": "Zoë",
        }
        assert (
            _get_helper_ui_control(hass, "zoe")["gamification"]["rewards"][
                "header_collapse"
            ]
            is True
        )

    @pytest.mark.asyncio
    async def test_update_overwrites_existing_value(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Update should overwrite an existing persisted value."""
        user_id = scenario_full.assignee_ids["Zoë"]

        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_MANAGE_UI_CONTROL,
            {
                const.SERVICE_FIELD_USER_ID: user_id,
                const.SERVICE_FIELD_UI_CONTROL_ACTION: const.UI_CONTROL_ACTION_CREATE,
                const.SERVICE_FIELD_UI_CONTROL_KEY: REWARDS_HEADER_COLLAPSE_KEY,
                const.SERVICE_FIELD_UI_CONTROL_VALUE: True,
            },
            blocking=True,
            return_response=True,
        )

        response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_MANAGE_UI_CONTROL,
            {
                const.SERVICE_FIELD_USER_ID: user_id,
                const.SERVICE_FIELD_UI_CONTROL_ACTION: const.UI_CONTROL_ACTION_UPDATE,
                const.SERVICE_FIELD_UI_CONTROL_KEY: REWARDS_HEADER_COLLAPSE_KEY,
                const.SERVICE_FIELD_UI_CONTROL_VALUE: False,
            },
            blocking=True,
            return_response=True,
        )

        await hass.async_block_till_done()

        user_record = scenario_full.coordinator.assignees_data[user_id]
        assert response[const.SERVICE_FIELD_UI_CONTROL_ACTION] == (
            const.UI_CONTROL_ACTION_UPDATE
        )
        assert response[const.SERVICE_FIELD_UI_CONTROL_TARGET] == (
            const.UI_CONTROL_TARGET_USER
        )
        assert (
            user_record[const.DATA_USER_UI_PREFERENCES]["gamification"]["rewards"][
                "header_collapse"
            ]
            is False
        )
        assert (
            _get_helper_ui_control(hass, "zoe")["gamification"]["rewards"][
                "header_collapse"
            ]
            is False
        )

    @pytest.mark.asyncio
    async def test_update_creates_missing_value(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Update should create the value when it does not yet exist."""
        user_id = scenario_full.assignee_ids["Zoë"]

        response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_MANAGE_UI_CONTROL,
            {
                const.SERVICE_FIELD_USER_ID: user_id,
                const.SERVICE_FIELD_UI_CONTROL_ACTION: const.UI_CONTROL_ACTION_UPDATE,
                const.SERVICE_FIELD_UI_CONTROL_KEY: CHORES_HEADER_COLLAPSE_KEY,
                const.SERVICE_FIELD_UI_CONTROL_VALUE: True,
            },
            blocking=True,
            return_response=True,
        )

        await hass.async_block_till_done()

        assert response[const.SERVICE_FIELD_UI_CONTROL_ACTION] == (
            const.UI_CONTROL_ACTION_UPDATE
        )
        assert response[const.SERVICE_FIELD_UI_CONTROL_TARGET] == (
            const.UI_CONTROL_TARGET_USER
        )
        assert (
            scenario_full.coordinator.assignees_data[user_id][
                const.DATA_USER_UI_PREFERENCES
            ]["gamification"]["chores"]["header_collapse"]
            is True
        )
        assert (
            _get_helper_ui_control(hass, "zoe")["gamification"]["chores"][
                "header_collapse"
            ]
            is True
        )

    @pytest.mark.asyncio
    async def test_remove_empty_key_clears_all_preferences(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Remove with an empty key should clear the full user preference bucket."""
        user_id = scenario_full.assignee_ids["Zoë"]

        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_MANAGE_UI_CONTROL,
            {
                const.SERVICE_FIELD_USER_ID: user_id,
                const.SERVICE_FIELD_UI_CONTROL_ACTION: const.UI_CONTROL_ACTION_CREATE,
                const.SERVICE_FIELD_UI_CONTROL_KEY: REWARDS_HEADER_COLLAPSE_KEY,
                const.SERVICE_FIELD_UI_CONTROL_VALUE: True,
            },
            blocking=True,
            return_response=True,
        )

        response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_MANAGE_UI_CONTROL,
            {
                const.SERVICE_FIELD_USER_ID: user_id,
                const.SERVICE_FIELD_UI_CONTROL_ACTION: const.UI_CONTROL_ACTION_REMOVE,
            },
            blocking=True,
            return_response=True,
        )

        await hass.async_block_till_done()

        assert response["cleared_all"] is True
        assert response[const.SERVICE_FIELD_UI_CONTROL_TARGET] == (
            const.UI_CONTROL_TARGET_USER
        )
        assert response[const.SERVICE_FIELD_UI_CONTROL_KEY] == ""
        assert (
            scenario_full.coordinator.assignees_data[user_id][
                const.DATA_USER_UI_PREFERENCES
            ]
            == {}
        )
        assert _get_helper_ui_control(hass, "zoe") == {}

    @pytest.mark.asyncio
    async def test_remove_key_clears_targeted_preference(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Remove with a key should clear only the targeted preference path."""
        user_id = scenario_full.assignee_ids["Zoë"]

        await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_MANAGE_UI_CONTROL,
            {
                const.SERVICE_FIELD_USER_ID: user_id,
                const.SERVICE_FIELD_UI_CONTROL_ACTION: const.UI_CONTROL_ACTION_CREATE,
                const.SERVICE_FIELD_UI_CONTROL_KEY: REWARDS_HEADER_COLLAPSE_KEY,
                const.SERVICE_FIELD_UI_CONTROL_VALUE: True,
            },
            blocking=True,
            return_response=True,
        )

        response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_MANAGE_UI_CONTROL,
            {
                const.SERVICE_FIELD_USER_ID: user_id,
                const.SERVICE_FIELD_UI_CONTROL_ACTION: const.UI_CONTROL_ACTION_REMOVE,
                const.SERVICE_FIELD_UI_CONTROL_KEY: REWARDS_HEADER_COLLAPSE_KEY,
            },
            blocking=True,
            return_response=True,
        )

        await hass.async_block_till_done()

        assert response["cleared_all"] is False
        assert response[const.SERVICE_FIELD_UI_CONTROL_TARGET] == (
            const.UI_CONTROL_TARGET_USER
        )
        assert response[const.SERVICE_FIELD_UI_CONTROL_KEY] == (
            REWARDS_HEADER_COLLAPSE_KEY
        )
        assert (
            scenario_full.coordinator.assignees_data[user_id][
                const.DATA_USER_UI_PREFERENCES
            ]
            == {}
        )
        assert _get_helper_ui_control(hass, "zoe") == {}

    @pytest.mark.asyncio
    async def test_requires_user_target(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Service should reject calls without a target user."""
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                const.DOMAIN,
                const.SERVICE_MANAGE_UI_CONTROL,
                {
                    const.SERVICE_FIELD_UI_CONTROL_ACTION: const.UI_CONTROL_ACTION_CREATE,
                    const.SERVICE_FIELD_UI_CONTROL_KEY: REWARDS_HEADER_COLLAPSE_KEY,
                    const.SERVICE_FIELD_UI_CONTROL_VALUE: True,
                },
                blocking=True,
                return_response=True,
            )

    @pytest.mark.asyncio
    async def test_shared_admin_target_writes_meta_bucket(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Shared-admin target should persist outside any individual user record."""
        response = await hass.services.async_call(
            const.DOMAIN,
            const.SERVICE_MANAGE_UI_CONTROL,
            {
                const.SERVICE_FIELD_UI_CONTROL_TARGET: (
                    const.UI_CONTROL_TARGET_SHARED_ADMIN
                ),
                const.SERVICE_FIELD_UI_CONTROL_ACTION: const.UI_CONTROL_ACTION_CREATE,
                const.SERVICE_FIELD_UI_CONTROL_KEY: REWARDS_HEADER_COLLAPSE_KEY,
                const.SERVICE_FIELD_UI_CONTROL_VALUE: True,
            },
            blocking=True,
            return_response=True,
        )

        await hass.async_block_till_done()

        assert response == {
            const.SERVICE_FIELD_UI_CONTROL_TARGET: (
                const.UI_CONTROL_TARGET_SHARED_ADMIN
            ),
            const.SERVICE_FIELD_UI_CONTROL_ACTION: const.UI_CONTROL_ACTION_CREATE,
            const.SERVICE_FIELD_UI_CONTROL_KEY: REWARDS_HEADER_COLLAPSE_KEY,
            "cleared_all": False,
        }
        assert (
            _get_shared_admin_ui_control(scenario_full)["gamification"]["rewards"][
                "header_collapse"
            ]
            is True
        )
        assert (
            scenario_full.coordinator.ui_manager.get_shared_admin_ui_control()[
                "gamification"
            ]["rewards"]["header_collapse"]
            is True
        )

    @pytest.mark.asyncio
    async def test_shared_admin_target_rejects_user_context(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Shared-admin target should reject calls that also include user identity."""
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                const.DOMAIN,
                const.SERVICE_MANAGE_UI_CONTROL,
                {
                    const.SERVICE_FIELD_UI_CONTROL_TARGET: (
                        const.UI_CONTROL_TARGET_SHARED_ADMIN
                    ),
                    const.SERVICE_FIELD_USER_NAME: "Zoë",
                    const.SERVICE_FIELD_UI_CONTROL_ACTION: (
                        const.UI_CONTROL_ACTION_CREATE
                    ),
                    const.SERVICE_FIELD_UI_CONTROL_KEY: REWARDS_HEADER_COLLAPSE_KEY,
                    const.SERVICE_FIELD_UI_CONTROL_VALUE: True,
                },
                blocking=True,
                return_response=True,
            )

    @pytest.mark.asyncio
    async def test_shared_admin_ui_manager_returns_deep_copy(
        self,
        hass: HomeAssistant,
        scenario_full: SetupResult,
    ) -> None:
        """Shared-admin UI manager accessor should not expose mutable internal state."""
        _get_shared_admin_ui_control(scenario_full)["gamification"] = {
            "rewards": {"header_collapse": True}
        }

        shared_admin_ui_control = (
            scenario_full.coordinator.ui_manager.get_shared_admin_ui_control()
        )
        shared_admin_ui_control["gamification"]["rewards"]["header_collapse"] = False

        assert (
            _get_shared_admin_ui_control(scenario_full)["gamification"]["rewards"][
                "header_collapse"
            ]
            is True
        )
