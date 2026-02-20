"""Workflow helpers for KidsChores integration tests.

All helpers use the dashboard helper sensor as the single source of truth.
NEVER construct entity IDs manually - get them from the dashboard helper.

Usage:
    from tests.helpers import (
        claim_chore, approve_chore, WorkflowResult,
        get_dashboard_helper, find_chore,
    )

    # Get dashboard helper for a kid
    dashboard = get_dashboard_helper(hass, "zoe")

    # Find chore by display name
    chore = find_chore(dashboard, "Feed the cats")

    # Claim and approve via service calls
    result = await claim_chore(hass, "zoe", "Feed the cats", kid_context)
    result = await approve_chore(hass, "zoe", "Feed the cats", parent_context)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from tests.helpers.constants import (
    ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID,
    ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID,
    ATTR_CHORE_DISAPPROVE_BUTTON_ENTITY_ID,
    ATTR_DASHBOARD_BONUSES,
    ATTR_DASHBOARD_CHORES,
    ATTR_DASHBOARD_PENALTIES,
    ATTR_DASHBOARD_REWARDS,
    ATTR_REWARD_APPROVE_BUTTON_ENTITY_ID,
    ATTR_REWARD_CLAIM_BUTTON_ENTITY_ID,
)

if TYPE_CHECKING:
    from homeassistant.core import Context, HomeAssistant

# =============================================================================
# RESULT DATACLASS
# =============================================================================


@dataclass
class WorkflowResult:
    """Result from any workflow action (claim, approve, redeem, etc.).

    Captures before/after state for flexible assertions.
    """

    success: bool = True
    error: str | None = None

    # State tracking
    state_before: str = ""
    state_after: str = ""
    global_state_before: str = ""
    global_state_after: str = ""

    # Points tracking
    points_before: float = 0.0
    points_after: float = 0.0

    # Due date tracking
    due_date_before: str | None = None
    due_date_after: str | None = None

    # Multi-kid scenarios
    other_kids_states: dict[str, str] = field(default_factory=dict)

    @property
    def points_changed(self) -> float:
        """Points difference (positive = earned, negative = spent)."""
        return self.points_after - self.points_before

    @property
    def due_date_advanced(self) -> bool:
        """Whether due date changed."""
        return (
            self.due_date_before != self.due_date_after
            and self.due_date_after is not None
        )


# =============================================================================
# DASHBOARD HELPER ACCESS
# =============================================================================


def get_dashboard_helper(hass: HomeAssistant, kid_slug: str) -> dict[str, Any]:
    """Get dashboard helper attributes for a kid.

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug (e.g., "zoe", "max") - the slugified name

    Returns:
        Dashboard helper attributes dict with: chores, rewards, bonuses,
        penalties, core_sensors, pending_approvals, ui_translations

    Raises:
        ValueError: If dashboard helper doesn't exist
    """
    helper_ids = [
        f"sensor.{kid_slug}_choreops_ui_dashboard_helper",
        f"sensor.{kid_slug}_kidschores_ui_dashboard_helper",
    ]

    for helper_id in helper_ids:
        state = hass.states.get(helper_id)
        if state is not None:
            return dict(state.attributes)

    raise ValueError(f"Dashboard helper not found: {helper_ids[0]}")


def get_kid_points(hass: HomeAssistant, kid_slug: str) -> float:
    """Get current points for a kid via dashboard helper.

    Uses the dashboard helper's core_sensors.points_eid to find the actual
    points sensor entity ID (which may vary based on points_label config).

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug (e.g., "zoe")

    Returns:
        Current point balance
    """
    # Get points entity ID from dashboard helper (single source of truth)
    helper = get_dashboard_helper(hass, kid_slug)
    core_sensors = helper.get("core_sensors", {})
    points_eid = core_sensors.get("points_eid")

    if not points_eid:
        return 0.0

    state = hass.states.get(points_eid)

    if state is None or state.state in ("unknown", "unavailable"):
        return 0.0

    try:
        return float(state.state)
    except (ValueError, TypeError):
        return 0.0


# =============================================================================
# ENTITY FINDER FUNCTIONS
# =============================================================================


def find_chore(
    dashboard_attrs: dict[str, Any], chore_name: str
) -> dict[str, Any] | None:
    """Find chore by display name in dashboard helper's chores list.

    Args:
        dashboard_attrs: Attributes from get_dashboard_helper()
        chore_name: Display name of chore (e.g., "Feed the cats")

    Returns:
        Chore dict with keys: eid, name, status, can_claim, can_approve, etc.
        Or None if not found.
    """
    chores = dashboard_attrs.get(ATTR_DASHBOARD_CHORES, [])
    for chore in chores:
        if chore.get("name") == chore_name:
            return chore
    return None


def find_reward(
    dashboard_attrs: dict[str, Any], reward_name: str
) -> dict[str, Any] | None:
    """Find reward by display name in dashboard helper's rewards list.

    Args:
        dashboard_attrs: Attributes from get_dashboard_helper()
        reward_name: Display name of reward (e.g., "Ice Cream")

    Returns:
        Reward dict with keys: eid, name, cost, status, claims, etc.
        Or None if not found.
    """
    rewards = dashboard_attrs.get(ATTR_DASHBOARD_REWARDS, [])
    for reward in rewards:
        if reward.get("name") == reward_name:
            return reward
    return None


def find_bonus(
    dashboard_attrs: dict[str, Any], bonus_name: str
) -> dict[str, Any] | None:
    """Find bonus by display name in dashboard helper's bonuses list.

    NOTE: The eid returned is a BUTTON entity, not a sensor.

    Args:
        dashboard_attrs: Attributes from get_dashboard_helper()
        bonus_name: Display name of bonus (e.g., "Helper Bonus")

    Returns:
        Bonus dict with keys: eid (button!), name, points
        Or None if not found.
    """
    bonuses = dashboard_attrs.get(ATTR_DASHBOARD_BONUSES, [])
    for bonus in bonuses:
        if bonus.get("name") == bonus_name:
            return bonus
    return None


def find_penalty(
    dashboard_attrs: dict[str, Any], penalty_name: str
) -> dict[str, Any] | None:
    """Find penalty by display name in dashboard helper's penalties list.

    NOTE: The eid returned is a BUTTON entity, not a sensor.

    Args:
        dashboard_attrs: Attributes from get_dashboard_helper()
        penalty_name: Display name of penalty (e.g., "Bad Behavior")

    Returns:
        Penalty dict with keys: eid (button!), name, points
        Or None if not found.
    """
    penalties = dashboard_attrs.get(ATTR_DASHBOARD_PENALTIES, [])
    for penalty in penalties:
        if penalty.get("name") == penalty_name:
            return penalty
    return None


# =============================================================================
# BUTTON LOOKUP FUNCTIONS
# =============================================================================


def get_chore_buttons(hass: HomeAssistant, chore_sensor_eid: str) -> dict[str, str]:
    """Get claim/approve/disapprove button eids from chore sensor attributes.

    Args:
        hass: Home Assistant instance
        chore_sensor_eid: Chore status sensor entity ID (from dashboard helper)

    Returns:
        Dict with keys: claim, approve, disapprove (values are button entity IDs)

    Raises:
        ValueError: If sensor doesn't exist or missing button attributes
    """
    state = hass.states.get(chore_sensor_eid)
    if state is None:
        raise ValueError(f"Chore sensor not found: {chore_sensor_eid}")

    attrs = state.attributes
    return {
        "claim": attrs.get(ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID, ""),
        "approve": attrs.get(ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID, ""),
        "disapprove": attrs.get(ATTR_CHORE_DISAPPROVE_BUTTON_ENTITY_ID, ""),
    }


def get_reward_buttons(hass: HomeAssistant, reward_sensor_eid: str) -> dict[str, str]:
    """Get claim/approve button eids from reward sensor attributes.

    Args:
        hass: Home Assistant instance
        reward_sensor_eid: Reward status sensor entity ID (from dashboard helper)

    Returns:
        Dict with keys: claim, approve (values are button entity IDs)

    Raises:
        ValueError: If sensor doesn't exist
    """
    state = hass.states.get(reward_sensor_eid)
    if state is None:
        raise ValueError(f"Reward sensor not found: {reward_sensor_eid}")

    attrs = state.attributes
    return {
        "claim": attrs.get(ATTR_REWARD_CLAIM_BUTTON_ENTITY_ID, ""),
        "approve": attrs.get(ATTR_REWARD_APPROVE_BUTTON_ENTITY_ID, ""),
    }


# =============================================================================
# BUTTON PRESS HELPER
# =============================================================================


async def press_button(
    hass: HomeAssistant,
    button_eid: str,
    context: Context | None = None,
) -> bool:
    """Press a button entity via service call.

    Args:
        hass: Home Assistant instance
        button_eid: Button entity ID to press
        context: User context for authorization

    Returns:
        True if successful, False otherwise
    """
    try:
        await hass.services.async_call(
            "button",
            "press",
            {"entity_id": button_eid},
            blocking=True,
            context=context,
        )
        await hass.async_block_till_done()
        return True
    except Exception:
        return False


# =============================================================================
# CHORE WORKFLOWS
# =============================================================================


async def claim_chore(
    hass: HomeAssistant,
    kid_slug: str,
    chore_name: str,
    context: Context | None = None,
) -> WorkflowResult:
    """Claim a chore for a kid via button press.

    1. Gets dashboard helper for kid
    2. Finds chore by name
    3. Gets claim button from chore sensor
    4. Captures before state
    5. Presses claim button
    6. Captures after state

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug (e.g., "zoe")
        chore_name: Display name of chore
        context: User context (should be kid's context)

    Returns:
        WorkflowResult with before/after state
    """
    result = WorkflowResult()

    try:
        # Get dashboard helper and find chore
        dashboard = get_dashboard_helper(hass, kid_slug)
        chore = find_chore(dashboard, chore_name)

        if chore is None:
            result.success = False
            result.error = f"Chore not found: {chore_name}"
            return result

        chore_sensor_eid = chore["eid"]

        # Get chore sensor state for before values
        chore_state = hass.states.get(chore_sensor_eid)
        if chore_state:
            result.state_before = chore_state.state
            result.global_state_before = chore_state.attributes.get("global_state", "")
            result.due_date_before = chore_state.attributes.get("due_date")

        # Get points before
        result.points_before = get_kid_points(hass, kid_slug)

        # Get claim button and press it
        buttons = get_chore_buttons(hass, chore_sensor_eid)
        claim_button = buttons["claim"]

        if not claim_button:
            result.success = False
            result.error = "Claim button not found"
            return result

        success = await press_button(hass, claim_button, context)
        if not success:
            result.success = False
            result.error = "Failed to press claim button"
            return result

        # Capture after state
        chore_state = hass.states.get(chore_sensor_eid)
        if chore_state:
            result.state_after = chore_state.state
            result.global_state_after = chore_state.attributes.get("global_state", "")
            result.due_date_after = chore_state.attributes.get("due_date")

        result.points_after = get_kid_points(hass, kid_slug)

    except Exception as ex:
        result.success = False
        result.error = str(ex)

    return result


async def approve_chore(
    hass: HomeAssistant,
    kid_slug: str,
    chore_name: str,
    context: Context | None = None,
) -> WorkflowResult:
    """Approve a chore for a kid via button press.

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug (e.g., "zoe")
        chore_name: Display name of chore
        context: User context (should be parent's context)

    Returns:
        WorkflowResult with before/after state
    """
    result = WorkflowResult()

    try:
        dashboard = get_dashboard_helper(hass, kid_slug)
        chore = find_chore(dashboard, chore_name)

        if chore is None:
            result.success = False
            result.error = f"Chore not found: {chore_name}"
            return result

        chore_sensor_eid = chore["eid"]

        # Capture before state
        chore_state = hass.states.get(chore_sensor_eid)
        if chore_state:
            result.state_before = chore_state.state
            result.global_state_before = chore_state.attributes.get("global_state", "")
            result.due_date_before = chore_state.attributes.get("due_date")

        result.points_before = get_kid_points(hass, kid_slug)

        # Get approve button and press it
        buttons = get_chore_buttons(hass, chore_sensor_eid)
        approve_button = buttons["approve"]

        if not approve_button:
            result.success = False
            result.error = "Approve button not found"
            return result

        success = await press_button(hass, approve_button, context)
        if not success:
            result.success = False
            result.error = "Failed to press approve button"
            return result

        # Capture after state
        chore_state = hass.states.get(chore_sensor_eid)
        if chore_state:
            result.state_after = chore_state.state
            result.global_state_after = chore_state.attributes.get("global_state", "")
            result.due_date_after = chore_state.attributes.get("due_date")

        result.points_after = get_kid_points(hass, kid_slug)

    except Exception as ex:
        result.success = False
        result.error = str(ex)

    return result


async def disapprove_chore(
    hass: HomeAssistant,
    kid_slug: str,
    chore_name: str,
    context: Context | None = None,
) -> WorkflowResult:
    """Disapprove a chore for a kid via button press.

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug (e.g., "zoe")
        chore_name: Display name of chore
        context: User context (should be parent's context)

    Returns:
        WorkflowResult with before/after state
    """
    result = WorkflowResult()

    try:
        dashboard = get_dashboard_helper(hass, kid_slug)
        chore = find_chore(dashboard, chore_name)

        if chore is None:
            result.success = False
            result.error = f"Chore not found: {chore_name}"
            return result

        chore_sensor_eid = chore["eid"]

        # Capture before state
        chore_state = hass.states.get(chore_sensor_eid)
        if chore_state:
            result.state_before = chore_state.state
            result.global_state_before = chore_state.attributes.get("global_state", "")
            result.due_date_before = chore_state.attributes.get("due_date")

        result.points_before = get_kid_points(hass, kid_slug)

        # Get disapprove button and press it
        buttons = get_chore_buttons(hass, chore_sensor_eid)
        disapprove_button = buttons["disapprove"]

        if not disapprove_button:
            result.success = False
            result.error = "Disapprove button not found"
            return result

        success = await press_button(hass, disapprove_button, context)
        if not success:
            result.success = False
            result.error = "Failed to press disapprove button"
            return result

        # Capture after state
        chore_state = hass.states.get(chore_sensor_eid)
        if chore_state:
            result.state_after = chore_state.state
            result.global_state_after = chore_state.attributes.get("global_state", "")
            result.due_date_after = chore_state.attributes.get("due_date")

        result.points_after = get_kid_points(hass, kid_slug)

    except Exception as ex:
        result.success = False
        result.error = str(ex)

    return result


# =============================================================================
# REWARD WORKFLOWS
# =============================================================================


async def claim_reward(
    hass: HomeAssistant,
    kid_slug: str,
    reward_name: str,
    context: Context | None = None,
) -> WorkflowResult:
    """Claim a reward for a kid via button press.

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug
        reward_name: Display name of reward
        context: User context (should be kid's context)

    Returns:
        WorkflowResult with before/after state
    """
    result = WorkflowResult()

    try:
        dashboard = get_dashboard_helper(hass, kid_slug)
        reward = find_reward(dashboard, reward_name)

        if reward is None:
            result.success = False
            result.error = f"Reward not found: {reward_name}"
            return result

        reward_sensor_eid = reward["eid"]

        # Capture before state
        reward_state = hass.states.get(reward_sensor_eid)
        if reward_state:
            result.state_before = reward_state.state

        result.points_before = get_kid_points(hass, kid_slug)

        # Get claim button and press it
        buttons = get_reward_buttons(hass, reward_sensor_eid)
        claim_button = buttons["claim"]

        if not claim_button:
            result.success = False
            result.error = "Reward claim button not found"
            return result

        success = await press_button(hass, claim_button, context)
        if not success:
            result.success = False
            result.error = "Failed to press reward claim button"
            return result

        # Capture after state
        reward_state = hass.states.get(reward_sensor_eid)
        if reward_state:
            result.state_after = reward_state.state

        result.points_after = get_kid_points(hass, kid_slug)

    except Exception as ex:
        result.success = False
        result.error = str(ex)

    return result


async def approve_reward(
    hass: HomeAssistant,
    kid_slug: str,
    reward_name: str,
    context: Context | None = None,
) -> WorkflowResult:
    """Approve a reward claim via button press.

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug
        reward_name: Display name of reward
        context: User context (should be parent's context)

    Returns:
        WorkflowResult with before/after state
    """
    result = WorkflowResult()

    try:
        dashboard = get_dashboard_helper(hass, kid_slug)
        reward = find_reward(dashboard, reward_name)

        if reward is None:
            result.success = False
            result.error = f"Reward not found: {reward_name}"
            return result

        reward_sensor_eid = reward["eid"]

        # Capture before state
        reward_state = hass.states.get(reward_sensor_eid)
        if reward_state:
            result.state_before = reward_state.state

        result.points_before = get_kid_points(hass, kid_slug)

        # Get approve button and press it
        buttons = get_reward_buttons(hass, reward_sensor_eid)
        approve_button = buttons["approve"]

        if not approve_button:
            result.success = False
            result.error = "Reward approve button not found"
            return result

        success = await press_button(hass, approve_button, context)
        if not success:
            result.success = False
            result.error = "Failed to press reward approve button"
            return result

        # Capture after state
        reward_state = hass.states.get(reward_sensor_eid)
        if reward_state:
            result.state_after = reward_state.state

        result.points_after = get_kid_points(hass, kid_slug)

    except Exception as ex:
        result.success = False
        result.error = str(ex)

    return result


# =============================================================================
# BONUS/PENALTY WORKFLOWS
# =============================================================================


async def apply_bonus(
    hass: HomeAssistant,
    kid_slug: str,
    bonus_name: str,
    context: Context | None = None,
) -> WorkflowResult:
    """Apply a bonus to a kid via button press.

    NOTE: Bonus eid from dashboard helper is already a button entity.

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug
        bonus_name: Display name of bonus
        context: User context (should be parent's context)

    Returns:
        WorkflowResult with points before/after
    """
    result = WorkflowResult()

    try:
        dashboard = get_dashboard_helper(hass, kid_slug)
        bonus = find_bonus(dashboard, bonus_name)

        if bonus is None:
            result.success = False
            result.error = f"Bonus not found: {bonus_name}"
            return result

        # Bonus eid is already a button entity
        bonus_button_eid = bonus["eid"]

        result.points_before = get_kid_points(hass, kid_slug)

        success = await press_button(hass, bonus_button_eid, context)
        if not success:
            result.success = False
            result.error = "Failed to press bonus button"
            return result

        result.points_after = get_kid_points(hass, kid_slug)

    except Exception as ex:
        result.success = False
        result.error = str(ex)

    return result


async def apply_penalty(
    hass: HomeAssistant,
    kid_slug: str,
    penalty_name: str,
    context: Context | None = None,
) -> WorkflowResult:
    """Apply a penalty to a kid via button press.

    NOTE: Penalty eid from dashboard helper is already a button entity.

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug
        penalty_name: Display name of penalty
        context: User context (should be parent's context)

    Returns:
        WorkflowResult with points before/after
    """
    result = WorkflowResult()

    try:
        dashboard = get_dashboard_helper(hass, kid_slug)
        penalty = find_penalty(dashboard, penalty_name)

        if penalty is None:
            result.success = False
            result.error = f"Penalty not found: {penalty_name}"
            return result

        # Penalty eid is already a button entity
        penalty_button_eid = penalty["eid"]

        result.points_before = get_kid_points(hass, kid_slug)

        success = await press_button(hass, penalty_button_eid, context)
        if not success:
            result.success = False
            result.error = "Failed to press penalty button"
            return result

        result.points_after = get_kid_points(hass, kid_slug)

    except Exception as ex:
        result.success = False
        result.error = str(ex)

    return result


# =============================================================================
# MULTI-KID HELPERS
# =============================================================================


async def get_chore_states_all_kids(
    hass: HomeAssistant,
    kid_slugs: list[str],
    chore_name: str,
) -> dict[str, str]:
    """Get chore state for multiple kids.

    Args:
        hass: Home Assistant instance
        kid_slugs: List of kid slugs (e.g., ["zoe", "max", "lila"])
        chore_name: Display name of chore

    Returns:
        Dict mapping kid_slug -> chore state (e.g., {"zoe": "pending", "max": "claimed"})
    """
    states = {}

    for kid_slug in kid_slugs:
        try:
            dashboard = get_dashboard_helper(hass, kid_slug)
            chore = find_chore(dashboard, chore_name)

            if chore:
                chore_state = hass.states.get(chore["eid"])
                states[kid_slug] = chore_state.state if chore_state else "unknown"
            else:
                states[kid_slug] = "not_assigned"
        except ValueError:
            states[kid_slug] = "error"

    return states
