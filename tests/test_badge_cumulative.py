"""Cumulative badge tests.

Tests for CUMULATIVE badge type functionality:
- Track TOTAL LIFETIME POINTS EARNED (not current balance)
- Points earned = sum of all points ever received (chores, bonuses, etc.)
- NOT reduced by reward purchases or penalties
- Target: threshold_value (e.g., 500 = earn 500+ total points to unlock)
- Rewards: Can award bonus points AND/OR an ongoing points multiplier
- The ONLY badge type that can award a multiplier

Uses scenario_full (Stårblüm family):
- 2 cumulative badges:
  - "Chore Stär Champion" (Zoë): threshold=100 total points earned, awards 50pts
  - "Team Player Badge" (Max!, Lila): threshold=500 total points earned, awards 30pts
- 3 kids: Zoë, Max!, Lila
- 18 chores with various points

Test organization:
- Section 1: Badge Loading & Entity Creation
- Section 2: Cumulative Badge Progress (total points earned tracking)
- Section 3: Multi-Kid Badge Progress
- Section 4: Badge Assignment Filtering
- Section 5: Dashboard Helper Badge Data
"""

from typing import Any

from homeassistant.core import Context, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.kidschores import const
from tests.helpers import (
    ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID,
    ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID,
    ATTR_DASHBOARD_BADGES,
    DATA_KID_CUMULATIVE_BADGE_PROGRESS,
    DATA_KID_POINTS,
)
from tests.helpers.flow_test_helpers import FlowTestHelper
from tests.test_badge_helpers import (
    find_chore_in_dashboard,
    get_badge_by_name,
    get_dashboard_helper_eid,
    get_kid_by_name,
    setup_badges,  # noqa: F401 - pytest fixture
)


async def _add_cumulative_badge_via_options_flow(
    hass: HomeAssistant,
    config_entry_id: str,
    *,
    name: str,
    kid_id: str,
    threshold: int,
) -> None:
    """Add one cumulative badge through options flow."""
    result = await hass.config_entries.options.async_init(config_entry_id)
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_INIT

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={const.OPTIONS_FLOW_INPUT_MENU_SELECTION: const.OPTIONS_FLOW_BADGES},
    )
    assert result.get("type") == FlowResultType.FORM

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            const.OPTIONS_FLOW_INPUT_MANAGE_ACTION: const.OPTIONS_FLOW_ACTIONS_ADD
        },
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_ADD_BADGE

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={const.CFOF_BADGES_INPUT_TYPE: const.BADGE_TYPE_CUMULATIVE},
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_ADD_BADGE_CUMULATIVE

    form_data = FlowTestHelper.build_badge_form_data(
        {
            "type": const.BADGE_TYPE_CUMULATIVE,
            "name": name,
            "icon": "mdi:medal",
            "assigned_to": [kid_id],
            "award_points": 0,
            "threshold_value": threshold,
            "maintenance_rules": 0,
        }
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=form_data,
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == const.OPTIONS_FLOW_STEP_INIT


# ============================================================================
# SECTION 1: BADGE LOADING & ENTITY CREATION
# ============================================================================


class TestCumulativeBadgeLoading:
    """Test cumulative badge loading via Entity Loading Extension."""

    async def test_cumulative_badges_loaded_from_yaml(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
    ) -> None:
        """Test that cumulative badges are loaded from scenario_full.yaml.

        Validates that Entity Loading Extension correctly processes
        cumulative badge definitions.
        """
        coordinator = setup_badges.coordinator

        # Verify badges_data is populated
        assert coordinator.badges_data, "badges_data should not be empty"
        assert len(coordinator.badges_data) == 2, (
            "scenario_full has 2 cumulative badges"
        )

        # Verify badge names
        badge_names = [b.get("name") for b in coordinator.badges_data.values()]
        assert "Chore Stär Champion" in badge_names
        assert "Team Player Badge" in badge_names

    async def test_cumulative_badge_attributes_loaded_correctly(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
    ) -> None:
        """Test that cumulative badge attributes are correctly loaded from YAML.

        Cumulative badge data structure uses nested format:
        - badge_type: "cumulative"
        - target.threshold_value: Total points needed to earn badge
        - awards.award_points: Points awarded when badge earned
        - awards.points_multiplier: Optional ongoing multiplier (unique to cumulative)
        """
        coordinator = setup_badges.coordinator

        # Get Chore Stär Champion badge
        champion_id = get_badge_by_name(coordinator, "Chore Stär Champion")
        champion_data = coordinator.badges_data[champion_id]

        # Verify cumulative-specific attributes
        assert champion_data.get("badge_type") == "cumulative"
        assert champion_data.get("target", {}).get("threshold_value") == 100.0
        awards = champion_data.get("awards", {})
        assert awards.get("award_points") == 50.0
        assert champion_data.get("icon") == "mdi:medal-outline"

        # Get Team Player Badge
        team_id = get_badge_by_name(coordinator, "Team Player Badge")
        team_data = coordinator.badges_data[team_id]

        # Verify attributes
        assert team_data.get("badge_type") == "cumulative"
        assert team_data.get("target", {}).get("threshold_value") == 500.0
        assert team_data.get("awards", {}).get("award_points") == 30.0

    async def test_cumulative_badge_assigned_to_loaded_correctly(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
    ) -> None:
        """Test that cumulative badge assigned_to lists are resolved to kid IDs."""
        coordinator = setup_badges.coordinator

        # Get kid IDs
        zoe_id = get_kid_by_name(coordinator, "Zoë")
        max_id = get_kid_by_name(coordinator, "Max!")
        lila_id = get_kid_by_name(coordinator, "Lila")

        # Chore Stär Champion should be assigned to Zoë only
        champion_id = get_badge_by_name(coordinator, "Chore Stär Champion")
        champion_data = coordinator.badges_data[champion_id]
        assigned_to = champion_data.get("assigned_to", [])
        assert zoe_id in assigned_to, "Zoë should be assigned to Chore Stär Champion"
        assert max_id not in assigned_to, "Max! should not be assigned"

        # Team Player Badge should be assigned to Max! and Lila
        team_id = get_badge_by_name(coordinator, "Team Player Badge")
        team_data = coordinator.badges_data[team_id]
        team_assigned = team_data.get("assigned_to", [])
        assert max_id in team_assigned, "Max! should be assigned to Team Player Badge"
        assert lila_id in team_assigned, "Lila should be assigned"
        assert zoe_id not in team_assigned, "Zoë should not be assigned"


# ============================================================================
# SECTION 2: CUMULATIVE BADGE PROGRESS (TOTAL POINTS EARNED)
# ============================================================================


class TestCumulativeBadgeProgress:
    """Test cumulative badge progress tracking.

    Cumulative badges track TOTAL LIFETIME POINTS EARNED:
    - Points earned = sum of all points ever received (chores, bonuses, etc.)
    - NOT reduced by reward purchases or penalties
    - Progress toward threshold_value determines badge unlock
    """

    async def test_chore_approval_updates_cumulative_progress(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test that approving a chore updates cumulative badge progress.

        When Zoë completes "Feed the cåts" (10 pts), her total points earned
        increases, progressing toward "Chore Stär Champion" (threshold=100).

        Note: Cumulative badges track total_points_earned, not current balance.
        """
        coordinator = setup_badges.coordinator

        # Get IDs
        zoe_id = get_kid_by_name(coordinator, "Zoë")

        # Get initial cumulative badge progress
        initial_progress = coordinator.kids_data[zoe_id].get(
            DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
        )
        initial_chores_completed = initial_progress.get("cycle_chores_completed", 0)

        # Get dashboard helper to find chore entity
        dashboard_eid = get_dashboard_helper_eid(hass, "Zoë")
        chore_info = find_chore_in_dashboard(hass, dashboard_eid, "Feed the cåts")
        chore_sensor_eid = chore_info["eid"]

        # Get button IDs from chore sensor
        chore_state = hass.states.get(chore_sensor_eid)
        assert chore_state, f"Chore sensor not found: {chore_sensor_eid}"
        claim_button_eid = chore_state.attributes.get(ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID)
        approve_button_eid = chore_state.attributes.get(
            ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID
        )

        # Kid claims chore
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": claim_button_eid},
            blocking=True,
            context=Context(user_id=mock_hass_users["kid1"].id),
        )
        await hass.async_block_till_done()

        # Parent approves chore
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": approve_button_eid},
            blocking=True,
            context=Context(user_id=mock_hass_users["parent1"].id),
        )
        await hass.async_block_till_done()

        # Verify badge progress increased
        updated_progress = coordinator.kids_data[zoe_id].get(
            DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}
        )
        updated_chores_completed = updated_progress.get("cycle_chores_completed", 0)

        # Chore count should have increased
        assert updated_chores_completed >= initial_chores_completed, (
            f"Expected chores completed to increase from {initial_chores_completed}"
        )

        # Verify points were awarded
        zoe_points = coordinator.kids_data[zoe_id].get(DATA_KID_POINTS, 0)
        assert zoe_points == 10, f"Expected 10 points, got {zoe_points}"

    async def test_demoted_current_badge_multiplier_is_applied(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
        monkeypatch,
    ) -> None:
        """Use current badge from computed progress when recalculating multiplier.

        Regression guard for demotion behavior: multiplier must follow the
        demotion-aware current badge (lower badge), not the highest earned badge.
        """
        coordinator = setup_badges.coordinator
        max_id = get_kid_by_name(coordinator, "Max!")

        # Reuse existing badge definitions with test multipliers.
        lower_badge_id = get_badge_by_name(coordinator, "Team Player Badge")
        higher_badge_id = get_badge_by_name(coordinator, "Chore Stär Champion")

        lower_badge_awards = coordinator.badges_data[lower_badge_id].setdefault(
            const.DATA_BADGE_AWARDS, {}
        )
        higher_badge_awards = coordinator.badges_data[higher_badge_id].setdefault(
            const.DATA_BADGE_AWARDS, {}
        )
        lower_badge_awards[const.DATA_BADGE_AWARDS_POINT_MULTIPLIER] = 1.25
        higher_badge_awards[const.DATA_BADGE_AWARDS_POINT_MULTIPLIER] = 2.0

        def _mock_progress(_: str) -> dict[str, Any]:
            return {
                const.CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID: lower_badge_id,
                const.CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_ID: (
                    higher_badge_id
                ),
                const.CUMULATIVE_BADGE_PROGRESS_STATUS: (
                    const.CUMULATIVE_BADGE_STATE_DEMOTED
                ),
            }

        monkeypatch.setattr(
            coordinator.gamification_manager,
            "get_cumulative_badge_progress",
            _mock_progress,
        )

        coordinator.gamification_manager.update_point_multiplier_for_kid(max_id)
        await hass.async_block_till_done()

        multiplier = coordinator.kids_data[max_id].get(const.DATA_KID_POINTS_MULTIPLIER)
        assert multiplier == 1.25, (
            f"Expected multiplier from demotion-aware current badge, got {multiplier}"
        )


# ============================================================================
# SECTION 3: MULTI-KID CUMULATIVE BADGE PROGRESS
# ============================================================================


class TestMultiKidCumulativeBadgeProgress:
    """Test cumulative badge progress for badges assigned to multiple kids.

    "Team Player Badge" is assigned to both Max! and Lila.
    Each kid tracks their own independent progress toward the threshold.
    """

    async def test_chore_approval_updates_multi_kid_badge_progress(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Test that approving a chore updates progress for multi-kid cumulative badges.

        When Max! completes "Pick up Lëgo!" (15 pts), his total points earned
        increases, progressing toward "Team Player Badge" (threshold=500).

        Note: Lila's progress is tracked independently - this test only affects Max!.
        """
        coordinator = setup_badges.coordinator

        # Get IDs
        max_id = get_kid_by_name(coordinator, "Max!")

        # Get initial points
        initial_points = coordinator.kids_data[max_id].get(DATA_KID_POINTS, 0)

        # Get dashboard helper to find chore entity
        dashboard_eid = get_dashboard_helper_eid(hass, "Max!")
        chore_info = find_chore_in_dashboard(hass, dashboard_eid, "Pick up Lëgo!")
        chore_sensor_eid = chore_info["eid"]

        # Get button IDs from chore sensor
        chore_state = hass.states.get(chore_sensor_eid)
        assert chore_state, f"Chore sensor not found: {chore_sensor_eid}"
        claim_button_eid = chore_state.attributes.get(ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID)
        approve_button_eid = chore_state.attributes.get(
            ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID
        )

        # Kid claims chore
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": claim_button_eid},
            blocking=True,
            context=Context(user_id=mock_hass_users["kid2"].id),
        )
        await hass.async_block_till_done()

        # Parent approves chore
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": approve_button_eid},
            blocking=True,
            context=Context(user_id=mock_hass_users["parent1"].id),
        )
        await hass.async_block_till_done()

        # Verify points were awarded (Pick up Lëgo! is 15 points)
        final_points = coordinator.kids_data[max_id].get(DATA_KID_POINTS, 0)
        assert final_points == initial_points + 15, (
            f"Expected {initial_points + 15} points, got {final_points}"
        )


# ============================================================================
# SECTION 4: CUMULATIVE BADGE ASSIGNMENT FILTERING
# ============================================================================


class TestCumulativeBadgeAssignment:
    """Test cumulative badge assigned_to filtering behavior."""

    async def test_cumulative_badge_only_tracks_assigned_kids(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
    ) -> None:
        """Test that cumulative badges only track progress for assigned kids.

        Chore Stär Champion is assigned to Zoë only.
        Team Player Badge is assigned to Max! and Lila only.
        """
        coordinator = setup_badges.coordinator

        # Get IDs
        zoe_id = get_kid_by_name(coordinator, "Zoë")
        max_id = get_kid_by_name(coordinator, "Max!")
        lila_id = get_kid_by_name(coordinator, "Lila")

        # Get badge IDs
        champion_id = get_badge_by_name(coordinator, "Chore Stär Champion")
        team_id = get_badge_by_name(coordinator, "Team Player Badge")

        # Verify Chore Stär Champion assignment
        champion_assigned = coordinator.badges_data[champion_id].get("assigned_to", [])
        assert zoe_id in champion_assigned
        assert max_id not in champion_assigned
        assert lila_id not in champion_assigned

        # Verify Team Player Badge assignment
        team_assigned = coordinator.badges_data[team_id].get("assigned_to", [])
        assert zoe_id not in team_assigned
        assert max_id in team_assigned
        assert lila_id in team_assigned


# ============================================================================
# SECTION 5: DASHBOARD HELPER CUMULATIVE BADGE DATA
# ============================================================================


class TestDashboardHelperCumulativeBadges:
    """Test dashboard helper sensor cumulative badge data."""

    async def test_dashboard_helper_includes_assigned_cumulative_badges(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
    ) -> None:
        """Test that dashboard helper includes cumulative badges assigned to each kid.

        Zoë should see "Chore Stär Champion" in her badges list.
        Max! should see "Team Player Badge" in his badges list.
        """
        # Get Zoë's dashboard helper
        zoe_dashboard_eid = get_dashboard_helper_eid(hass, "Zoë")
        zoe_helper = hass.states.get(zoe_dashboard_eid)
        assert zoe_helper, f"Zoë dashboard helper not found: {zoe_dashboard_eid}"

        # Check Zoë's badges
        zoe_badges = zoe_helper.attributes.get(ATTR_DASHBOARD_BADGES, [])
        zoe_badge_names = [b.get("name") for b in zoe_badges]
        assert "Chore Stär Champion" in zoe_badge_names, (
            f"Zoë should see Chore Stär Champion, got {zoe_badge_names}"
        )
        assert "Team Player Badge" not in zoe_badge_names, (
            "Zoë should not see Team Player Badge"
        )

        # Get Max!'s dashboard helper
        max_dashboard_eid = get_dashboard_helper_eid(hass, "Max!")
        max_helper = hass.states.get(max_dashboard_eid)
        assert max_helper, f"Max! dashboard helper not found: {max_dashboard_eid}"

        # Check Max!'s badges
        max_badges = max_helper.attributes.get(ATTR_DASHBOARD_BADGES, [])
        max_badge_names = [b.get("name") for b in max_badges]
        assert "Team Player Badge" in max_badge_names, (
            f"Max! should see Team Player Badge, got {max_badge_names}"
        )
        assert "Chore Stär Champion" not in max_badge_names, (
            "Max! should not see Chore Stär Champion"
        )

    async def test_dashboard_helper_cumulative_badge_attributes(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
    ) -> None:
        """Test that dashboard helper cumulative badge entries have required attributes."""
        # Get Zoë's dashboard helper
        zoe_dashboard_eid = get_dashboard_helper_eid(hass, "Zoë")
        zoe_helper = hass.states.get(zoe_dashboard_eid)
        assert zoe_helper

        badges = zoe_helper.attributes.get(ATTR_DASHBOARD_BADGES, [])
        assert len(badges) > 0, "Zoë should have at least one badge"

        # Check badge entry structure
        badge = badges[0]
        assert "name" in badge, "Badge should have name"
        assert "eid" in badge, "Badge should have entity ID"
        assert "badge_type" in badge, "Badge should have badge_type"
        assert badge.get("badge_type") == "cumulative", (
            "Badge should be cumulative type"
        )


# ============================================================================
# SECTION 6: SIMPLE 3-BADGE SENSOR ATTR VALIDATION (Step 1 of 3)
# ============================================================================


class TestCumulativeThreeBadgeSensorAttributes:
    """Simple baseline: create 3 cumulative badges and verify kid badges sensor attrs."""

    async def test_three_cumulative_badges_update_kid_badges_sensor_attrs(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
    ) -> None:
        """Use 3 cumulative badges (2 existing + 1 new) and verify sensor attrs."""
        coordinator = setup_badges.coordinator
        config_entry = setup_badges.config_entry
        zoe_id = get_kid_by_name(coordinator, "Zoë")

        await _add_cumulative_badge_via_options_flow(
            hass,
            config_entry.entry_id,
            name="Bronze Tier",
            kid_id=zoe_id,
            threshold=5,
        )
        await hass.async_block_till_done()

        dashboard_eid = get_dashboard_helper_eid(hass, "Zoë")
        dashboard_state = hass.states.get(dashboard_eid)
        assert dashboard_state is not None

        core_sensors = dashboard_state.attributes.get("core_sensors", {})
        badges_eid = core_sensors.get("badges_eid")
        assert badges_eid, "Expected badges_eid in dashboard helper core_sensors"

        badges_sensor_state = hass.states.get(badges_eid)
        assert badges_sensor_state is not None, (
            f"Expected kid badges sensor state for entity_id={badges_eid}"
        )

        attrs = badges_sensor_state.attributes
        assert const.ATTR_CURRENT_BADGE_NAME in attrs
        assert const.ATTR_HIGHEST_EARNED_BADGE_NAME in attrs
        assert const.ATTR_NEXT_HIGHER_BADGE_NAME in attrs
        assert const.ATTR_NEXT_LOWER_BADGE_NAME in attrs
        assert const.ATTR_CURRENT_BADGE_EID in attrs
        assert const.ATTR_HIGHEST_EARNED_BADGE_EID in attrs
        assert const.ATTR_NEXT_HIGHER_BADGE_EID in attrs
        assert const.ATTR_NEXT_LOWER_BADGE_EID in attrs

        badge_name_to_assigned = {
            badge_data.get(const.DATA_BADGE_NAME, ""): badge_data.get(
                const.DATA_BADGE_ASSIGNED_TO, []
            )
            for badge_data in coordinator.badges_data.values()
        }
        assert len(coordinator.badges_data) == 3
        for badge_name in (
            "Chore Stär Champion",
            "Team Player Badge",
            "Bronze Tier",
        ):
            assert badge_name in badge_name_to_assigned, (
                f"Expected badge '{badge_name}'. Existing badges: "
                f"{sorted(badge_name_to_assigned.keys())}"
            )

        assert zoe_id in badge_name_to_assigned["Bronze Tier"]


# ============================================================================
# SECTION 7: PROMOTION VALUE VALIDATION (Step 2 of 3)
# ============================================================================


class TestCumulativeBadgePromotionValues:
    """Validate cumulative promotion updates concrete kid badges sensor values."""

    async def test_cumulative_promotion_sets_current_and_highest_badge_attrs(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
        mock_hass_users: dict[str, Any],
    ) -> None:
        """Promote Zoë to Bronze tier and verify concrete badges sensor attrs."""
        coordinator = setup_badges.coordinator
        config_entry = setup_badges.config_entry
        zoe_id = get_kid_by_name(coordinator, "Zoë")

        await _add_cumulative_badge_via_options_flow(
            hass,
            config_entry.entry_id,
            name="Bronze Tier",
            kid_id=zoe_id,
            threshold=5,
        )
        await hass.async_block_till_done()

        _ = get_badge_by_name(coordinator, "Bronze Tier")

        dashboard_eid = get_dashboard_helper_eid(hass, "Zoë")
        dashboard_state = hass.states.get(dashboard_eid)
        assert dashboard_state is not None
        core_sensors = dashboard_state.attributes.get("core_sensors", {})
        badges_eid = core_sensors.get("badges_eid")
        assert badges_eid, "Expected badges_eid in dashboard helper core_sensors"

        before_state = hass.states.get(badges_eid)
        assert before_state is not None
        before_attrs = before_state.attributes
        assert before_attrs.get(const.ATTR_CURRENT_BADGE_NAME) != "Bronze Tier"

        chore_info = find_chore_in_dashboard(hass, dashboard_eid, "Feed the cåts")
        chore_state = hass.states.get(chore_info["eid"])
        assert chore_state is not None

        claim_button_eid = chore_state.attributes.get(ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID)
        approve_button_eid = chore_state.attributes.get(
            ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID
        )
        assert claim_button_eid
        assert approve_button_eid

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": claim_button_eid},
            blocking=True,
            context=Context(user_id=mock_hass_users["kid1"].id),
        )
        await hass.async_block_till_done()

        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": approve_button_eid},
            blocking=True,
            context=Context(user_id=mock_hass_users["parent1"].id),
        )
        await hass.async_block_till_done()

        after_state = hass.states.get(badges_eid)
        assert after_state is not None
        after_attrs = after_state.attributes

        assert after_attrs.get(const.ATTR_CURRENT_BADGE_NAME) == "Bronze Tier"
        assert after_attrs.get(const.ATTR_HIGHEST_EARNED_BADGE_NAME) == "Bronze Tier"
        assert after_attrs.get(const.ATTR_CURRENT_BADGE_EID) == after_attrs.get(
            const.ATTR_HIGHEST_EARNED_BADGE_EID
        )


# ============================================================================
# SECTION 8: DEMOTION VALUE VALIDATION (Step 3 of 3)
# ============================================================================


class TestCumulativeBadgeDemotionValues:
    """Validate demotion-aware cumulative progress in kid badges sensor attrs."""

    async def test_demoted_progress_surfaces_current_vs_highest_badges(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
        monkeypatch,
    ) -> None:
        """Show demoted state where current badge is lower than highest earned."""
        coordinator = setup_badges.coordinator
        zoe_id = get_kid_by_name(coordinator, "Zoë")

        lower_badge_id = get_badge_by_name(coordinator, "Team Player Badge")
        higher_badge_id = get_badge_by_name(coordinator, "Chore Stär Champion")

        lower_badge_name = coordinator.badges_data[lower_badge_id].get(
            const.DATA_BADGE_NAME, ""
        )
        higher_badge_name = coordinator.badges_data[higher_badge_id].get(
            const.DATA_BADGE_NAME, ""
        )

        original_get_progress = (
            coordinator.gamification_manager.get_cumulative_badge_progress
        )

        def _mock_progress(kid_id: str) -> dict[str, Any]:
            if kid_id != zoe_id:
                return original_get_progress(kid_id)

            return {
                const.CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID: lower_badge_id,
                const.CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_NAME: lower_badge_name,
                const.CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_ID: (
                    higher_badge_id
                ),
                const.CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_NAME: (
                    higher_badge_name
                ),
                const.CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_BADGE_ID: higher_badge_id,
                const.CUMULATIVE_BADGE_PROGRESS_NEXT_HIGHER_BADGE_NAME: (
                    higher_badge_name
                ),
                const.CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_BADGE_ID: (
                    const.SENTINEL_NONE_TEXT
                ),
                const.CUMULATIVE_BADGE_PROGRESS_NEXT_LOWER_BADGE_NAME: (
                    const.SENTINEL_NONE_TEXT
                ),
                const.CUMULATIVE_BADGE_PROGRESS_STATUS: (
                    const.CUMULATIVE_BADGE_STATE_DEMOTED
                ),
            }

        monkeypatch.setattr(
            coordinator.gamification_manager,
            "get_cumulative_badge_progress",
            _mock_progress,
        )

        coordinator.async_update_listeners()
        await hass.async_block_till_done()

        dashboard_eid = get_dashboard_helper_eid(hass, "Zoë")
        dashboard_state = hass.states.get(dashboard_eid)
        assert dashboard_state is not None
        badges_eid = dashboard_state.attributes.get("core_sensors", {}).get(
            "badges_eid"
        )
        assert badges_eid, "Expected badges_eid in dashboard helper core_sensors"

        badges_sensor_state = hass.states.get(badges_eid)
        assert badges_sensor_state is not None
        attrs = badges_sensor_state.attributes

        assert (
            attrs.get(const.ATTR_BADGE_STATUS) == const.CUMULATIVE_BADGE_STATE_DEMOTED
        )
        assert attrs.get(const.ATTR_CURRENT_BADGE_NAME) == lower_badge_name
        assert attrs.get(const.ATTR_HIGHEST_EARNED_BADGE_NAME) == higher_badge_name
        assert attrs.get(const.ATTR_CURRENT_BADGE_NAME) != attrs.get(
            const.ATTR_HIGHEST_EARNED_BADGE_NAME
        )
        assert attrs.get(const.ATTR_NEXT_HIGHER_BADGE_NAME) == higher_badge_name
        assert attrs.get(const.ATTR_CURRENT_BADGE_EID)
        assert attrs.get(const.ATTR_HIGHEST_EARNED_BADGE_EID)
        assert attrs.get(const.ATTR_CURRENT_BADGE_EID) != attrs.get(
            const.ATTR_HIGHEST_EARNED_BADGE_EID
        )


# ============================================================================
# SECTION 9: MULTIPLIER TRANSITION VALIDATION
# ============================================================================


class TestCumulativeBadgeMultiplierTransitions:
    """Validate multiplier changes across promotion, demotion, and reactivation."""

    async def test_multiplier_changes_correctly_on_promotion(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
        monkeypatch,
    ) -> None:
        """Promotion should move multiplier from base to higher badge value."""
        coordinator = setup_badges.coordinator
        gamification_manager = coordinator.gamification_manager
        zoe_id = get_kid_by_name(coordinator, "Zoë")

        higher_badge_id = get_badge_by_name(coordinator, "Chore Stär Champion")
        higher_badge_awards = coordinator.badges_data[higher_badge_id].setdefault(
            const.DATA_BADGE_AWARDS, {}
        )
        higher_badge_awards[const.DATA_BADGE_AWARDS_POINT_MULTIPLIER] = 2.0

        coordinator.kids_data[zoe_id][const.DATA_KID_POINTS_MULTIPLIER] = 1.0

        def _mock_progress(_: str) -> dict[str, Any]:
            return {
                const.CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID: higher_badge_id,
                const.CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_ID: (
                    higher_badge_id
                ),
                const.CUMULATIVE_BADGE_PROGRESS_STATUS: (
                    const.CUMULATIVE_BADGE_STATE_ACTIVE
                ),
            }

        monkeypatch.setattr(
            gamification_manager,
            "get_cumulative_badge_progress",
            _mock_progress,
        )

        gamification_manager.update_point_multiplier_for_kid(zoe_id)
        await hass.async_block_till_done()

        assert coordinator.kids_data[zoe_id][const.DATA_KID_POINTS_MULTIPLIER] == 2.0

    async def test_multiplier_changes_correctly_on_demotion(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
        monkeypatch,
    ) -> None:
        """Demotion should move multiplier from higher to lower badge value."""
        coordinator = setup_badges.coordinator
        gamification_manager = coordinator.gamification_manager
        max_id = get_kid_by_name(coordinator, "Max!")

        lower_badge_id = get_badge_by_name(coordinator, "Team Player Badge")
        higher_badge_id = get_badge_by_name(coordinator, "Chore Stär Champion")

        lower_badge_awards = coordinator.badges_data[lower_badge_id].setdefault(
            const.DATA_BADGE_AWARDS, {}
        )
        higher_badge_awards = coordinator.badges_data[higher_badge_id].setdefault(
            const.DATA_BADGE_AWARDS, {}
        )
        lower_badge_awards[const.DATA_BADGE_AWARDS_POINT_MULTIPLIER] = 1.25
        higher_badge_awards[const.DATA_BADGE_AWARDS_POINT_MULTIPLIER] = 2.0

        coordinator.kids_data[max_id][const.DATA_KID_POINTS_MULTIPLIER] = 2.0

        def _mock_progress(_: str) -> dict[str, Any]:
            return {
                const.CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID: lower_badge_id,
                const.CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_ID: (
                    higher_badge_id
                ),
                const.CUMULATIVE_BADGE_PROGRESS_STATUS: (
                    const.CUMULATIVE_BADGE_STATE_DEMOTED
                ),
            }

        monkeypatch.setattr(
            gamification_manager,
            "get_cumulative_badge_progress",
            _mock_progress,
        )

        gamification_manager.update_point_multiplier_for_kid(max_id)
        await hass.async_block_till_done()

        assert coordinator.kids_data[max_id][const.DATA_KID_POINTS_MULTIPLIER] == 1.25

    async def test_demoted_state_reactivates_and_restores_higher_multiplier(
        self,
        hass: HomeAssistant,
        setup_badges,  # noqa: F811
        monkeypatch,
    ) -> None:
        """DEMOTED should reactivate immediately when maintenance threshold is met."""
        coordinator = setup_badges.coordinator
        gamification_manager = coordinator.gamification_manager
        zoe_id = get_kid_by_name(coordinator, "Zoë")

        lower_badge_id = get_badge_by_name(coordinator, "Team Player Badge")
        higher_badge_id = get_badge_by_name(coordinator, "Chore Stär Champion")

        lower_badge_awards = coordinator.badges_data[lower_badge_id].setdefault(
            const.DATA_BADGE_AWARDS, {}
        )
        higher_badge_awards = coordinator.badges_data[higher_badge_id].setdefault(
            const.DATA_BADGE_AWARDS, {}
        )
        lower_badge_awards[const.DATA_BADGE_AWARDS_POINT_MULTIPLIER] = 1.25
        higher_badge_awards[const.DATA_BADGE_AWARDS_POINT_MULTIPLIER] = 2.0

        higher_badge_target = coordinator.badges_data[higher_badge_id].setdefault(
            const.DATA_BADGE_TARGET, {}
        )
        higher_badge_target[const.DATA_BADGE_MAINTENANCE_RULES] = 5.0
        higher_badge_reset = coordinator.badges_data[higher_badge_id].setdefault(
            const.DATA_BADGE_RESET_SCHEDULE, {}
        )
        higher_badge_reset[const.DATA_BADGE_RESET_SCHEDULE_RECURRING_FREQUENCY] = (
            const.FREQUENCY_WEEKLY
        )

        kid_data = coordinator.kids_data[zoe_id]
        kid_data[const.DATA_KID_POINTS_MULTIPLIER] = 1.25
        initial_points = float(kid_data.get(const.DATA_KID_POINTS, 0.0))
        kid_badges_earned = kid_data.setdefault(const.DATA_KID_BADGES_EARNED, {})
        kid_badges_earned[higher_badge_id] = {
            const.DATA_KID_BADGES_EARNED_NAME: coordinator.badges_data[higher_badge_id][
                const.DATA_BADGE_NAME
            ],
            const.DATA_KID_BADGES_EARNED_LAST_AWARDED: "2026-02-01",
            const.DATA_KID_BADGES_EARNED_PERIODS: {},
        }

        kid_progress = kid_data.setdefault(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {})
        kid_progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS] = (
            const.CUMULATIVE_BADGE_STATE_DEMOTED
        )
        kid_progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS] = 6.0
        kid_progress[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_END_DATE] = (
            "2099-01-01"
        )
        kid_progress[
            const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_MAINTENANCE_GRACE_END_DATE
        ] = None

        original_get_progress = gamification_manager.get_cumulative_badge_progress

        def _mock_progress(kid_id: str) -> dict[str, Any]:
            if kid_id != zoe_id:
                return original_get_progress(kid_id)

            status = kid_data.get(const.DATA_KID_CUMULATIVE_BADGE_PROGRESS, {}).get(
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS,
                const.CUMULATIVE_BADGE_STATE_ACTIVE,
            )
            current_badge_id = (
                higher_badge_id
                if status == const.CUMULATIVE_BADGE_STATE_ACTIVE
                else lower_badge_id
            )
            highest_badge_id = higher_badge_id

            return {
                const.CUMULATIVE_BADGE_PROGRESS_CURRENT_BADGE_ID: current_badge_id,
                const.CUMULATIVE_BADGE_PROGRESS_HIGHEST_EARNED_BADGE_ID: (
                    highest_badge_id
                ),
                const.CUMULATIVE_BADGE_PROGRESS_STATUS: status,
            }

        monkeypatch.setattr(
            gamification_manager,
            "get_cumulative_badge_progress",
            _mock_progress,
        )
        monkeypatch.setattr(
            gamification_manager,
            "get_cumulative_badge_levels",
            lambda _: (
                coordinator.badges_data[higher_badge_id],
                None,
                None,
                0.0,
                6.0,
            ),
        )

        context = gamification_manager._build_evaluation_context(zoe_id)
        assert context is not None

        await gamification_manager._evaluate_cumulative_badge(
            zoe_id,
            higher_badge_id,
            coordinator.badges_data[higher_badge_id],
            context,
        )
        await hass.async_block_till_done()

        assert (
            kid_data[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS][
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_STATUS
            ]
            == const.CUMULATIVE_BADGE_STATE_ACTIVE
        )
        assert (
            kid_data[const.DATA_KID_CUMULATIVE_BADGE_PROGRESS][
                const.DATA_KID_CUMULATIVE_BADGE_PROGRESS_CYCLE_POINTS
            ]
            == 0.0
        )
        assert kid_data[const.DATA_KID_POINTS_MULTIPLIER] == 2.0
        assert float(kid_data.get(const.DATA_KID_POINTS, 0.0)) == initial_points
        assert (
            kid_data[const.DATA_KID_BADGES_EARNED][higher_badge_id][
                const.DATA_KID_BADGES_EARNED_LAST_AWARDED
            ]
            == "2026-02-01"
        )
