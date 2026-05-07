"""Focused tests for dashboard helper chore sharding."""

from __future__ import annotations

from copy import deepcopy
from typing import TYPE_CHECKING, Any
from uuid import uuid4

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_registry import async_get as async_get_entity_registry
import pytest

from custom_components.choreops import const
from custom_components.choreops.sensor import (
    AssigneeDashboardChoreShardSensor,
    build_chore_shard_plan,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


@pytest.fixture
async def scenario_density_40(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load the 40-chores-per-user density scenario."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_density_starblum_40.yaml",
    )


@pytest.fixture
async def scenario_density_100(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load the 100-chores-per-user density scenario."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_density_starblum_100.yaml",
    )


@pytest.fixture
async def scenario_density_80(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load the 80-chores-per-user density scenario."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_density_starblum_80.yaml",
    )


@pytest.fixture
async def scenario_density_120(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load the 120-chores-per-user density scenario."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_density_starblum_120.yaml",
    )


def _get_dashboard_helper_state(
    hass: HomeAssistant,
    setup_result: SetupResult,
    assignee_name: str,
):
    """Return the dashboard helper state for one assignee slug."""
    assignee_id = setup_result.assignee_ids[assignee_name]
    unique_id = (
        f"{setup_result.config_entry.entry_id}_{assignee_id}"
        f"{const.SENSOR_KC_UID_SUFFIX_UI_DASHBOARD_HELPER}"
    )
    entity_id = async_get_entity_registry(hass).async_get_entity_id(
        "sensor", const.DOMAIN, unique_id
    )
    helper_state = hass.states.get(entity_id) if entity_id is not None else None
    available_dashboard_states = sorted(
        state.entity_id
        for state in hass.states.async_all()
        if state.entity_id.startswith("sensor.") and "dashboard" in state.entity_id
    )
    assert helper_state is not None, available_dashboard_states
    return helper_state


def _get_shard_entity_ids(helper_state) -> list[str]:
    """Return ordered chore shard helper entity IDs from one dashboard helper."""
    dashboard_helpers = helper_state.attributes.get("dashboard_helpers", {})
    return list(dashboard_helpers.get(const.ATTR_CHORE_HELPER_EIDS, []))


def _get_direct_chore_list_state(
    hass: HomeAssistant,
    assignee_slug: str,
    shard_index: int = 1,
):
    """Return one chore list shard state by its direct entity ID."""
    entity_id = f"sensor.{assignee_slug}_choreops_ui_dashboard_chore_list_{shard_index}"
    chore_list_state = hass.states.get(entity_id)
    assert chore_list_state is not None, {
        "missing": entity_id,
        "available_dashboard_states": sorted(
            state.entity_id
            for state in hass.states.async_all()
            if state.entity_id.startswith("sensor.") and "dashboard" in state.entity_id
        ),
    }
    return chore_list_state


def _merge_helper_chores(hass: HomeAssistant, helper_state) -> list[dict[str, Any]]:
    """Return merged chores from one dashboard helper and any shard helpers."""
    merged_chores = list(helper_state.attributes.get("chores", []))
    for shard_eid in _get_shard_entity_ids(helper_state):
        shard_state = hass.states.get(shard_eid)
        assert shard_state is not None, shard_eid
        merged_chores.extend(shard_state.attributes.get("chores", []))
    return merged_chores


def _get_user_plan(setup_result: SetupResult, assignee_name: str):
    """Return the current runtime shard plan for one assignee."""
    assignee_id = setup_result.assignee_ids[assignee_name]
    return setup_result.coordinator.ui_manager.get_helper_shard_plan(
        assignee_id,
        const.HELPER_SHARD_FAMILY_CHORES,
    )


async def _sync_updated_chore(
    setup_result: SetupResult,
    chore_id: str,
    updates: dict[str, Any],
) -> None:
    """Apply one chore update and run the runtime sync path."""
    previous_chore = deepcopy(setup_result.coordinator.chores_data[chore_id])
    current_chore = setup_result.coordinator.chore_manager.update_chore(
        chore_id, updates
    )
    sync_context = setup_result.coordinator.chore_manager.build_entity_sync_context(
        chore_id,
        mutation="updated",
        previous_chore=previous_chore,
        current_chore=current_chore,
    )
    await setup_result.coordinator.async_sync_chore_entities(sync_context)


async def _sync_deleted_chores(
    setup_result: SetupResult,
    chore_ids: list[str],
) -> None:
    """Delete multiple chores and run one final runtime sync pass."""
    last_previous_chore: dict[str, Any] | None = None
    last_chore_id: str | None = None

    for chore_id in chore_ids:
        last_previous_chore = deepcopy(setup_result.coordinator.chores_data[chore_id])
        last_chore_id = chore_id
        setup_result.coordinator.chore_manager.delete_chore(chore_id)

    assert last_previous_chore is not None and last_chore_id is not None
    sync_context = setup_result.coordinator.chore_manager.build_entity_sync_context(
        last_chore_id,
        mutation="deleted",
        previous_chore=last_previous_chore,
        current_chore=None,
    )
    await setup_result.coordinator.async_sync_chore_entities(sync_context)


async def _sync_created_chore(
    setup_result: SetupResult,
    chore_data: dict[str, Any],
) -> str:
    """Create one chore and run the runtime sync path."""
    created_chore = setup_result.coordinator.chore_manager.create_chore(
        chore_data,
        internal_id=str(chore_data[const.DATA_CHORE_INTERNAL_ID]),
        prebuilt=True,
    )
    chore_id = str(created_chore[const.DATA_CHORE_INTERNAL_ID])
    sync_context = setup_result.coordinator.chore_manager.build_entity_sync_context(
        chore_id,
        mutation="created",
        previous_chore=None,
        current_chore=created_chore,
    )
    await setup_result.coordinator.async_sync_chore_entities(sync_context)
    return chore_id


def _build_plan_for_user(setup_result: SetupResult, assignee_name: str, previous_plan):
    """Compute the current chore shard plan directly from coordinator data."""
    assignee_id = setup_result.assignee_ids[assignee_name]
    return build_chore_shard_plan(
        setup_result.coordinator.hass,
        setup_result.coordinator,
        setup_result.config_entry,
        assignee_id,
        assignee_name,
        previous_plan=previous_plan,
    )


async def _trim_user_to_first_inline_plan(
    setup_result: SetupResult,
    assignee_name: str,
) -> list[dict[str, Any]]:
    """Delete chores until the user reaches the first inline plan, returning deleted chores."""
    deleted_chores: list[dict[str, Any]] = []
    user_id = setup_result.assignee_ids[assignee_name]
    plan = _get_user_plan(setup_result, assignee_name)
    assert plan is not None

    while plan.mode != const.HELPER_SHARD_MODE_INLINE:
        chore_id = next(
            current_chore_id
            for current_chore_id, chore_info in setup_result.coordinator.chores_data.items()
            if user_id in chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
        )
        deleted_chore = deepcopy(setup_result.coordinator.chores_data[chore_id])
        deleted_chores.append(deleted_chore)
        await _sync_deleted_chores(setup_result, [chore_id])
        plan = _build_plan_for_user(setup_result, assignee_name, previous_plan=plan)
        setup_result.coordinator.ui_manager.set_helper_shard_plan(
            user_id,
            const.HELPER_SHARD_FAMILY_CHORES,
            plan,
        )

    return deleted_chores


async def _restore_user_to_highest_inline_plan(
    setup_result: SetupResult,
    assignee_name: str,
    deleted_chores: list[dict[str, Any]],
) -> None:
    """Restore chores until one more would switch the user back to sharded mode."""
    user_id = setup_result.assignee_ids[assignee_name]
    plan = _get_user_plan(setup_result, assignee_name)
    assert plan is not None and plan.mode == const.HELPER_SHARD_MODE_INLINE

    while deleted_chores:
        chore_data = deleted_chores.pop()
        setup_result.coordinator.chore_manager.create_chore(
            deepcopy(chore_data),
            internal_id=str(chore_data[const.DATA_CHORE_INTERNAL_ID]),
            prebuilt=True,
        )
        candidate_plan = _build_plan_for_user(
            setup_result,
            assignee_name,
            previous_plan=plan,
        )
        if candidate_plan.mode == const.HELPER_SHARD_MODE_SHARDED:
            setup_result.coordinator.chore_manager.delete_chore(
                str(chore_data[const.DATA_CHORE_INTERNAL_ID])
            )
            break

        plan = candidate_plan
        setup_result.coordinator.ui_manager.set_helper_shard_plan(
            user_id,
            const.HELPER_SHARD_FAMILY_CHORES,
            plan,
        )


class TestDashboardHelperSharding:
    """Validate inline and sharded helper modes around the density threshold."""

    @staticmethod
    def _get_density_setup_result(
        scenario_density_80: SetupResult,
        scenario_density_120: SetupResult,
        chores_per_user: int,
    ) -> SetupResult:
        """Return the setup result for one accepted high-density scenario."""
        scenario_map = {
            80: scenario_density_80,
            120: scenario_density_120,
        }
        return scenario_map[chores_per_user]

    async def test_end_to_end_setup_and_reload_expose_chore_list_1_attributes(
        self,
        hass: HomeAssistant,
        scenario_density_100: SetupResult,
    ) -> None:
        """Normal setup and reload should expose live chore_list_1 shard attributes."""
        await scenario_density_100.coordinator.async_request_refresh()
        await hass.async_block_till_done()

        helper_state = _get_dashboard_helper_state(hass, scenario_density_100, "Zoë")
        chore_helper_eids = _get_shard_entity_ids(helper_state)

        assert chore_helper_eids
        assert chore_helper_eids[0] == "sensor.zoe_choreops_ui_dashboard_chore_list_1"

        chore_list_1_state = _get_direct_chore_list_state(hass, "zoe", 1)
        assert chore_list_1_state.state == "available"
        assert chore_list_1_state.attributes["friendly_name"].endswith(
            "UI Dashboard Chore List 1"
        )
        assert (
            chore_list_1_state.attributes[const.ATTR_PURPOSE]
            == const.TRANS_KEY_PURPOSE_DASHBOARD_CHORE_SHARD_HELPER
        )
        assert chore_list_1_state.attributes[const.ATTR_SHARD_INDEX] == 1
        assert chore_list_1_state.attributes[const.ATTR_SHARD_COUNT] >= 1
        assert (
            chore_list_1_state.attributes[const.ATTR_HELPER_CONTRACT_VERSION]
            == const.HELPER_CONTRACT_VERSION_V1
        )
        assert isinstance(chore_list_1_state.attributes.get("chores", []), list)
        assert chore_list_1_state.attributes.get("chores", [])
        assert all(
            const.DATA_CHORE_NAME in chore
            for chore in chore_list_1_state.attributes["chores"]
        )

        await hass.config_entries.async_reload(
            scenario_density_100.config_entry.entry_id
        )
        await hass.async_block_till_done()
        reloaded_entry = hass.config_entries.async_get_entry(
            scenario_density_100.config_entry.entry_id
        )
        assert reloaded_entry is not None
        reloaded_coordinator = reloaded_entry.runtime_data
        await reloaded_coordinator.async_request_refresh()
        await hass.async_block_till_done()

        helper_state_after_reload = _get_dashboard_helper_state(
            hass, scenario_density_100, "Zoë"
        )
        chore_helper_eids_after_reload = _get_shard_entity_ids(
            helper_state_after_reload
        )
        assert chore_helper_eids_after_reload
        assert (
            chore_helper_eids_after_reload[0]
            == "sensor.zoe_choreops_ui_dashboard_chore_list_1"
        )

        chore_list_1_state_after_reload = _get_direct_chore_list_state(hass, "zoe", 1)
        assert chore_list_1_state_after_reload.state == "available"
        assert chore_list_1_state_after_reload.attributes[const.ATTR_SHARD_INDEX] == 1
        assert isinstance(
            chore_list_1_state_after_reload.attributes.get("chores", []),
            list,
        )
        assert chore_list_1_state_after_reload.attributes.get("chores", [])

    async def test_inline_mode_keeps_chores_on_main_helper(
        self,
        hass: HomeAssistant,
        scenario_density_40: SetupResult,
    ) -> None:
        """40 chores per user should stay inline with no shard pointers."""
        await scenario_density_40.coordinator.async_request_refresh()
        await hass.async_block_till_done()
        helper_state = _get_dashboard_helper_state(hass, scenario_density_40, "Zoë")

        assert const.ATTR_CHORES_BY_LABEL not in helper_state.attributes
        assert (
            helper_state.attributes["dashboard_helpers"][const.ATTR_CHORE_HELPER_EIDS]
            == []
        )
        assert (
            helper_state.attributes[const.ATTR_SHARD_RUNTIME]["mode"]
            == const.HELPER_SHARD_MODE_INLINE
        )
        assert len(helper_state.attributes["chores"]) == 40

    async def test_sharded_mode_moves_chores_to_companion_helpers(
        self,
        hass: HomeAssistant,
        scenario_density_100: SetupResult,
    ) -> None:
        """100 chores per user should expose chore shard helper pointers."""
        await scenario_density_100.coordinator.ui_manager.async_reconcile_chore_shards_for_users(
            [scenario_density_100.assignee_ids["Zoë"]]
        )
        await scenario_density_100.coordinator.async_request_refresh()
        await hass.async_block_till_done()
        helper_state = _get_dashboard_helper_state(hass, scenario_density_100, "Zoë")

        assert const.ATTR_CHORES_BY_LABEL not in helper_state.attributes
        assert helper_state.attributes["chores"] == []

        shard_runtime = helper_state.attributes[const.ATTR_SHARD_RUNTIME]
        assert shard_runtime["mode"] == const.HELPER_SHARD_MODE_SHARDED

        chore_helper_eids = helper_state.attributes["dashboard_helpers"][
            const.ATTR_CHORE_HELPER_EIDS
        ]
        assert chore_helper_eids
        assert len(chore_helper_eids) == shard_runtime["expected_shard_count"]

        merged_chores: list[dict[str, Any]] = []
        for expected_index, shard_eid in enumerate(chore_helper_eids, start=1):
            shard_state = hass.states.get(shard_eid)
            available_shard_states = sorted(
                state.entity_id
                for state in hass.states.async_all()
                if "chore_shard" in state.entity_id
            )
            registry_entries = sorted(
                entry.entity_id
                for entry in er.async_entries_for_config_entry(
                    async_get_entity_registry(hass),
                    scenario_density_100.config_entry.entry_id,
                )
                if "chore_shard" in entry.entity_id
            )
            assert shard_state is not None, {
                "states": available_shard_states,
                "registry": registry_entries,
            }
            assert shard_state.attributes["friendly_name"].endswith(
                f"UI Dashboard Chore List {expected_index}"
            )
            assert "shard" not in shard_state.attributes["friendly_name"].lower()
            assert (
                shard_state.attributes[const.ATTR_PURPOSE]
                == const.TRANS_KEY_PURPOSE_DASHBOARD_CHORE_SHARD_HELPER
            )
            assert shard_state.attributes[const.ATTR_SHARD_INDEX] == expected_index
            assert (
                shard_state.attributes[const.ATTR_SHARD_COUNT]
                == shard_runtime["expected_shard_count"]
            )
            assert (
                shard_state.attributes[const.ATTR_HELPER_CONTRACT_VERSION]
                == const.HELPER_CONTRACT_VERSION_V1
            )
            assert shard_eid.endswith(f"_ui_dashboard_chore_list_{expected_index}")
            merged_chores.extend(shard_state.attributes["chores"])

        assert len(merged_chores) == 100
        assert all("_chore_id" not in chore for chore in merged_chores)

    async def test_dashboard_helper_shared_attributes_resolve_registered_chore_lists(
        self,
        hass: HomeAssistant,
        scenario_density_100: SetupResult,
    ) -> None:
        """Main helper should expose registered chore list helper IDs in dashboard_helpers."""
        await scenario_density_100.coordinator.ui_manager.async_reconcile_chore_shards_for_users(
            [scenario_density_100.assignee_ids["Zoë"]]
        )
        await scenario_density_100.coordinator.async_request_refresh()
        await hass.async_block_till_done()

        helper_state = _get_dashboard_helper_state(hass, scenario_density_100, "Zoë")
        dashboard_helpers = helper_state.attributes.get("dashboard_helpers", {})
        chore_helper_eids = list(
            dashboard_helpers.get(const.ATTR_CHORE_HELPER_EIDS, [])
        )

        assert chore_helper_eids
        assert dashboard_helpers.get("translation_sensor_eid") is not None
        assert dashboard_helpers.get("date_helper_eid") is not None
        assert dashboard_helpers.get("chore_select_eid") is not None

        for expected_index, chore_helper_eid in enumerate(chore_helper_eids, start=1):
            chore_list_state = hass.states.get(chore_helper_eid)
            assert chore_list_state is not None, chore_helper_eid
            assert chore_list_state.attributes["friendly_name"].endswith(
                f"UI Dashboard Chore List {expected_index}"
            )
            assert chore_list_state.attributes[const.ATTR_SHARD_INDEX] == expected_index
            assert chore_list_state.attributes[const.ATTR_SHARD_COUNT] == len(
                chore_helper_eids
            )
            assert isinstance(chore_list_state.attributes.get("chores", []), list)

    @pytest.mark.parametrize("chores_per_user", [80, 120])
    async def test_acceptance_high_density_stays_sharded_and_complete(
        self,
        hass: HomeAssistant,
        scenario_density_80: SetupResult,
        scenario_density_120: SetupResult,
        chores_per_user: int,
    ) -> None:
        """High-density accepted scenarios should stay complete and under the recorder ceiling."""
        setup_result = self._get_density_setup_result(
            scenario_density_80,
            scenario_density_120,
            chores_per_user,
        )

        await (
            setup_result.coordinator.ui_manager.async_reconcile_chore_shards_for_users(
                [setup_result.assignee_ids["Zoë"]]
            )
        )
        await setup_result.coordinator.async_request_refresh()
        await hass.async_block_till_done()

        helper_state = _get_dashboard_helper_state(hass, setup_result, "Zoë")
        shard_runtime = helper_state.attributes[const.ATTR_SHARD_RUNTIME]

        assert shard_runtime["mode"] == const.HELPER_SHARD_MODE_SHARDED
        assert shard_runtime["expected_shard_count"] >= 1
        assert shard_runtime["last_accepted_serialized_size"] < 16 * 1024

        merged_chores = _merge_helper_chores(hass, helper_state)
        assert len(merged_chores) == chores_per_user

    async def test_density_80_claim_path_stays_operational(
        self,
        hass: HomeAssistant,
        scenario_density_80: SetupResult,
    ) -> None:
        """A representative claim path should still work at 80 chores per user."""
        zoe_id = scenario_density_80.assignee_ids["Zoë"]
        first_chore_id = scenario_density_80.chore_ids["Zoë Dense Chore 001"]

        await scenario_density_80.coordinator.ui_manager.async_reconcile_chore_shards_for_users(
            [zoe_id]
        )
        await scenario_density_80.coordinator.async_request_refresh()
        await hass.async_block_till_done()

        await scenario_density_80.coordinator.chore_manager.claim_chore(
            zoe_id,
            first_chore_id,
            "Zoë",
        )
        await scenario_density_80.coordinator.async_request_refresh()
        await hass.async_block_till_done()

        helper_state = _get_dashboard_helper_state(hass, scenario_density_80, "Zoë")
        chores = _merge_helper_chores(hass, helper_state)
        claimed_chore = next(
            chore for chore in chores if chore.get("name") == "Zoë Dense Chore 001"
        )

        assert claimed_chore["state"] in {"claimed", "completed", "waiting"}

    async def test_reload_reconstructs_shard_helpers_without_unavailable_entities(
        self,
        hass: HomeAssistant,
        scenario_density_120: SetupResult,
    ) -> None:
        """Reload should reconstruct shard-backed helpers with stable entity IDs."""
        helper_state_before = _get_dashboard_helper_state(
            hass, scenario_density_120, "Zoë"
        )
        shard_entity_ids_before = _get_shard_entity_ids(helper_state_before)
        assert shard_entity_ids_before

        await hass.config_entries.async_reload(
            scenario_density_120.config_entry.entry_id
        )
        await hass.async_block_till_done()

        helper_state_after = _get_dashboard_helper_state(
            hass, scenario_density_120, "Zoë"
        )
        shard_entity_ids_after = _get_shard_entity_ids(helper_state_after)
        assert shard_entity_ids_after == shard_entity_ids_before, {
            "before": shard_entity_ids_before,
            "after": shard_entity_ids_after,
            "runtime": helper_state_after.attributes.get(const.ATTR_SHARD_RUNTIME),
            "dashboard_helpers": helper_state_after.attributes.get("dashboard_helpers"),
            "registry": [
                entry.entity_id
                for entry in er.async_entries_for_config_entry(
                    async_get_entity_registry(hass),
                    scenario_density_120.config_entry.entry_id,
                )
                if "ui_dashboard_chore_list" in entry.entity_id
            ],
        }
        assert (
            helper_state_after.attributes[const.ATTR_SHARD_RUNTIME]["mode"]
            == const.HELPER_SHARD_MODE_SHARDED
        )
        assert len(_merge_helper_chores(hass, helper_state_after)) == 120

        for shard_entity_id in shard_entity_ids_after:
            shard_state = hass.states.get(shard_entity_id)
            assert shard_state is not None
            assert shard_state.state != "unavailable"

    async def test_reconcile_recreates_missing_live_shards_from_registry_entries(
        self,
        hass: HomeAssistant,
        scenario_density_100: SetupResult,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Reconcile should recreate shard sensors when only registry entries remain."""
        helper_state = _get_dashboard_helper_state(hass, scenario_density_100, "Zoë")
        shard_entity_ids = _get_shard_entity_ids(helper_state)
        assert shard_entity_ids

        for shard_entity_id in shard_entity_ids:
            hass.states.async_remove(shard_entity_id)
        await hass.async_block_till_done()

        captured_sensors: list[AssigneeDashboardChoreShardSensor] = []

        def _capture_entities(
            entities: list[AssigneeDashboardChoreShardSensor],
        ) -> None:
            captured_sensors.extend(entities)

        monkeypatch.setattr(
            scenario_density_100.coordinator.ui_manager,
            "_sensor_add_entities_callback",
            _capture_entities,
        )

        await scenario_density_100.coordinator.ui_manager.async_reconcile_chore_shards_for_users(
            [scenario_density_100.assignee_ids["Zoë"]]
        )

        plan = _get_user_plan(scenario_density_100, "Zoë")
        assert plan is not None
        assert len(captured_sensors) == plan.expected_shard_count
        assert [sensor.unique_id for sensor in captured_sensors] == [
            scenario_density_100.coordinator.ui_manager.get_chore_shard_unique_id(
                scenario_density_100.assignee_ids["Zoë"],
                shard_index,
            )
            for shard_index in range(1, plan.expected_shard_count + 1)
        ]

    async def test_small_edit_keeps_shard_mode_and_inline_transition_cleans_orphans(
        self,
        hass: HomeAssistant,
        scenario_density_100: SetupResult,
    ) -> None:
        """Ordinary edits should not flap shard mode, but shrinking far enough should clean up shard helpers."""
        helper_state_before = _get_dashboard_helper_state(
            hass, scenario_density_100, "Zoë"
        )
        shard_entity_ids_before = _get_shard_entity_ids(helper_state_before)
        assert shard_entity_ids_before

        await _sync_updated_chore(
            scenario_density_100,
            scenario_density_100.chore_ids["Zoë Dense Chore 001"],
            {
                const.DATA_CHORE_NAME: "Zoë Dense Chore 001 Retitled",
                const.DATA_CHORE_ICON: "mdi:star-four-points-outline",
            },
        )
        await hass.async_block_till_done()

        helper_state_after_edit = _get_dashboard_helper_state(
            hass, scenario_density_100, "Zoë"
        )
        shard_entity_ids_after_edit = _get_shard_entity_ids(helper_state_after_edit)
        assert (
            helper_state_after_edit.attributes[const.ATTR_SHARD_RUNTIME]["mode"]
            == const.HELPER_SHARD_MODE_SHARDED
        )
        assert shard_entity_ids_after_edit, {
            "before": shard_entity_ids_before,
            "after": shard_entity_ids_after_edit,
            "runtime": helper_state_after_edit.attributes.get(const.ATTR_SHARD_RUNTIME),
            "dashboard_helpers": helper_state_after_edit.attributes.get(
                "dashboard_helpers"
            ),
            "registry": [
                entry.entity_id
                for entry in er.async_entries_for_config_entry(
                    async_get_entity_registry(hass),
                    scenario_density_100.config_entry.entry_id,
                )
                if "ui_dashboard_chore_list" in entry.entity_id
            ],
        }
        assert set(shard_entity_ids_before).issubset(shard_entity_ids_after_edit), {
            "before": shard_entity_ids_before,
            "after": shard_entity_ids_after_edit,
            "runtime": helper_state_after_edit.attributes.get(const.ATTR_SHARD_RUNTIME),
            "dashboard_helpers": helper_state_after_edit.attributes.get(
                "dashboard_helpers"
            ),
        }
        assert len(_merge_helper_chores(hass, helper_state_after_edit)) == 100

        chores_to_delete = [
            scenario_density_100.chore_ids[f"Zoë Dense Chore {index:03d}"]
            for index in range(41, 101)
        ]
        await _sync_deleted_chores(scenario_density_100, chores_to_delete)
        await hass.async_block_till_done()

        helper_state_inline = _get_dashboard_helper_state(
            hass, scenario_density_100, "Zoë"
        )
        assert (
            helper_state_inline.attributes[const.ATTR_SHARD_RUNTIME]["mode"]
            == const.HELPER_SHARD_MODE_INLINE
        )
        assert _get_shard_entity_ids(helper_state_inline) == []
        assert len(helper_state_inline.attributes["chores"]) == 40

        remaining_registry_entries = [
            entry.entity_id
            for entry in er.async_entries_for_config_entry(
                async_get_entity_registry(hass),
                scenario_density_100.config_entry.entry_id,
            )
            if "zoe_choreops_dashboard_chore_shard" in entry.entity_id
        ]
        assert remaining_registry_entries == []

    async def test_cross_user_transfer_reconciles_both_users_at_threshold_edge(
        self,
        hass: HomeAssistant,
        scenario_density_100: SetupResult,
    ) -> None:
        """One reassignment should reconcile both users when shard pressure moves between them."""
        await scenario_density_100.coordinator.async_request_refresh()
        await hass.async_block_till_done()

        await _trim_user_to_first_inline_plan(
            scenario_density_100,
            "Zoë",
        )
        deleted_max_chores = await _trim_user_to_first_inline_plan(
            scenario_density_100,
            "Max!",
        )
        await _restore_user_to_highest_inline_plan(
            scenario_density_100,
            "Max!",
            deleted_max_chores,
        )
        zoe_plan_before = _get_user_plan(scenario_density_100, "Zoë")
        max_plan_before = _get_user_plan(scenario_density_100, "Max!")
        assert (
            max_plan_before is not None
            and max_plan_before.mode == const.HELPER_SHARD_MODE_INLINE
        )
        assert (
            zoe_plan_before is not None
            and zoe_plan_before.mode == const.HELPER_SHARD_MODE_INLINE
        )

        template_chore = next(
            deepcopy(chore_info)
            for chore_info in scenario_density_100.coordinator.chores_data.values()
            if chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS)
            == [scenario_density_100.assignee_ids["Zoë"]]
        )
        swing_chore_name = f"Zoë Threshold Swing {'X' * 640}"
        swing_chore = deepcopy(template_chore)
        swing_chore[const.DATA_CHORE_INTERNAL_ID] = str(uuid4())
        swing_chore[const.DATA_CHORE_NAME] = swing_chore_name
        swing_chore[const.DATA_CHORE_LABELS] = [
            f"threshold-label-{index}-{'Y' * 192}" for index in range(1, 13)
        ]
        swing_chore[const.DATA_CHORE_ASSIGNED_USER_IDS] = [
            scenario_density_100.assignee_ids["Zoë"]
        ]

        transfer_chore_id = await _sync_created_chore(
            scenario_density_100,
            swing_chore,
        )
        await hass.async_block_till_done()

        zoe_helper_state_before = _get_dashboard_helper_state(
            hass, scenario_density_100, "Zoë"
        )
        assert (
            zoe_helper_state_before.attributes[const.ATTR_SHARD_RUNTIME]["mode"]
            == const.HELPER_SHARD_MODE_SHARDED
        )

        transfer_chore = scenario_density_100.coordinator.chores_data[transfer_chore_id]
        await _sync_updated_chore(
            scenario_density_100,
            transfer_chore_id,
            {
                const.DATA_CHORE_NAME: transfer_chore[const.DATA_CHORE_NAME],
                const.DATA_CHORE_ASSIGNED_USER_IDS: [
                    scenario_density_100.assignee_ids["Max!"]
                ],
            },
        )
        await hass.async_block_till_done()

        zoe_helper_state = _get_dashboard_helper_state(
            hass, scenario_density_100, "Zoë"
        )
        max_helper_state = _get_dashboard_helper_state(
            hass, scenario_density_100, "Max!"
        )

        zoe_runtime_after = zoe_helper_state.attributes[const.ATTR_SHARD_RUNTIME]
        max_runtime_after = max_helper_state.attributes[const.ATTR_SHARD_RUNTIME]

        assert (
            zoe_helper_state.attributes[const.ATTR_SHARD_RUNTIME]["mode"]
            == const.HELPER_SHARD_MODE_INLINE
        )
        assert (
            max_helper_state.attributes[const.ATTR_SHARD_RUNTIME]["mode"]
            == const.HELPER_SHARD_MODE_SHARDED
        )
        assert _get_shard_entity_ids(zoe_helper_state) == []
        assert (
            zoe_runtime_after["last_accepted_serialized_size"]
            <= const.HELPER_SHARD_EXIT_BYTES
        )
        assert (
            len(_get_shard_entity_ids(max_helper_state))
            == max_runtime_after["expected_shard_count"]
        )
        assert max_runtime_after["last_accepted_serialized_size"] < (
            max_plan_before.last_accepted_serialized_size
        )
        assert max_runtime_after["expected_shard_count"] > 0

    async def test_main_and_shard_diagnostics_stay_minimal_and_consistent(
        self,
        hass: HomeAssistant,
        scenario_density_100: SetupResult,
    ) -> None:
        """Diagnostics should stay on the main helper while shard helpers keep the minimal contract."""
        await scenario_density_100.coordinator.ui_manager.async_reconcile_chore_shards_for_users(
            [scenario_density_100.assignee_ids["Zoë"]]
        )
        await scenario_density_100.coordinator.async_request_refresh()
        await hass.async_block_till_done()

        helper_state = _get_dashboard_helper_state(hass, scenario_density_100, "Zoë")
        shard_runtime = helper_state.attributes[const.ATTR_SHARD_RUNTIME]

        assert set(shard_runtime) == {
            "family",
            "mode",
            "expected_shard_count",
            "last_accepted_serialized_size",
            "last_reconciliation_outcome",
        }

        shard_entity_ids = _get_shard_entity_ids(helper_state)
        assert shard_runtime["expected_shard_count"] == len(shard_entity_ids)

        for expected_index, shard_entity_id in enumerate(shard_entity_ids, start=1):
            shard_state = hass.states.get(shard_entity_id)
            assert shard_state is not None
            assert set(shard_state.attributes) == {
                const.ATTR_PURPOSE,
                const.ATTR_SHARD_INDEX,
                const.ATTR_SHARD_COUNT,
                const.ATTR_HELPER_CONTRACT_VERSION,
                "chores",
                "friendly_name",
            }
            assert shard_state.attributes[const.ATTR_SHARD_INDEX] == expected_index
