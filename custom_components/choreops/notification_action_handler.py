# File: notification_action_handler.py
"""Handle notification actions from HA companion notifications.

This module processes notification action callbacks from the HA Companion app.
When a user taps an action button on a notification, this handler routes the
action to the appropriate coordinator method.

Separation of concerns (v0.5.0+):
- notification_action_handler.py = "The Router" (INCOMING action button callbacks)
- NotificationManager = "The Voice" (OUTGOING notifications)

ParsedAction dataclass and parse_notification_action() live here because they
are used for INCOMING action parsing, not outgoing notification building.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, cast

from homeassistant.exceptions import HomeAssistantError

from . import const

if TYPE_CHECKING:
    from homeassistant.core import Event, HomeAssistant

    from .coordinator import ChoreOpsDataCoordinator
    from .type_defs import AssigneeData


# =============================================================================
# ParsedAction Dataclass
# =============================================================================


@dataclass
class ParsedAction:
    """Type-safe parsed notification action.

    Represents a notification action string parsed into its components.
    Action strings are pipe-separated: "action_type|entry_id[:8]|assignee_id|entity_id[|notif_id]"

    Attributes:
        action_type: The action constant (e.g., ACTION_APPROVE_CHORE)
        entry_id: The config entry ID (truncated to 8 chars)
        assignee_id: The internal ID of the assignee
        entity_id: The chore_id or reward_id depending on action type
        notif_id: Optional notification tracking ID (rewards only)

    Example:
        # Chore action: "approve_chore|abc12345|assignee-123|chore-456"
        parsed = ParsedAction(
            action_type="approve_chore",
            entry_id="abc12345",
            assignee_id="assignee-123",
            entity_id="chore-456",
        )

        # Reward action: "approve_reward|abc12345|assignee-123|reward-456|notif-789"
        parsed = ParsedAction(
            action_type="approve_reward",
            entry_id="abc12345",
            assignee_id="assignee-123",
            entity_id="reward-456",
            notif_id="notif-789",
        )
    """

    action_type: str
    entry_id: str
    assignee_id: str
    entity_id: str  # chore_id or reward_id
    notif_id: str | None = None

    @property
    def is_chore_action(self) -> bool:
        """Check if this is a chore-related action."""
        return self.action_type in (
            const.ACTION_APPROVE_CHORE,
            const.ACTION_CLAIM_CHORE,
            const.ACTION_COMPLETE_FOR_ASSIGNEE,
            const.ACTION_DISAPPROVE_CHORE,
            const.ACTION_SKIP_CHORE,
        )

    @property
    def is_reward_action(self) -> bool:
        """Check if this is a reward-related action."""
        return self.action_type in (
            const.ACTION_APPROVE_REWARD,
            const.ACTION_DISAPPROVE_REWARD,
        )

    @property
    def is_reminder_action(self) -> bool:
        """Check if this is a reminder action (works for both chores/rewards)."""
        return self.action_type == const.ACTION_REMIND_30

    @property
    def chore_id(self) -> str | None:
        """Get chore_id if this is a chore action, else None."""
        if self.is_chore_action or (self.is_reminder_action and self.notif_id is None):
            return self.entity_id
        return None

    @property
    def reward_id(self) -> str | None:
        """Get reward_id if this is a reward action, else None."""
        if self.is_reward_action or (
            self.is_reminder_action and self.notif_id is not None
        ):
            return self.entity_id
        return None


def parse_notification_action(action_field: str) -> ParsedAction | None:
    """Parse a notification action string into a structured ParsedAction.

    Parses pipe-separated action strings:
    - Format: "CLAIM_CHORE|entry_id[:8]|assignee_id|chore_id"
    - With notification ID: "APPROVE_REWARD|entry_id[:8]|assignee_id|reward_id|notification_id"

    Args:
        action_field: Pipe-separated action string from notification callback

    Returns:
        ParsedAction object if valid, None if invalid/malformed

    Example:
        >>> parsed = parse_notification_action("CLAIM_CHORE|abc12345|def123|ghi456")
        >>> parsed.action_type  # "CLAIM_CHORE"
        >>> parsed.entry_id     # "abc12345"
        >>> parsed.assignee_id  # "def123"
        >>> parsed.entity_id    # "ghi456"
    """
    if not action_field:
        return None

    try:
        parts = action_field.split("|")
        if len(parts) < 3:
            const.LOGGER.warning("Invalid action string format: %s", action_field)
            return None

        action_type = parts[0]

        # Validate action_type is a known constant
        valid_actions = {
            const.ACTION_APPROVE_CHORE,
            const.ACTION_DISAPPROVE_CHORE,
            const.ACTION_CLAIM_CHORE,
            const.ACTION_COMPLETE_FOR_ASSIGNEE,
            const.ACTION_SKIP_CHORE,
            const.ACTION_APPROVE_REWARD,
            const.ACTION_DISAPPROVE_REWARD,
            const.ACTION_REMIND_30,
        }
        if action_type not in valid_actions:
            const.LOGGER.warning("Unknown action type: %s", action_type)
            return None

        # Hard-fork format: ACTION|entry_id|assignee_id|entity_id[|notif_id]
        if len(parts) < 4 or len(parts[1]) != 8:
            const.LOGGER.warning(
                "Invalid hard-fork action string format: %s", action_field
            )
            return None

        entry_id = parts[1]
        assignee_id = parts[2]
        entity_id = parts[3]
        notif_id = parts[4] if len(parts) > 4 else None

        parsed_action = ParsedAction(
            action_type=action_type,
            entry_id=entry_id,
            assignee_id=assignee_id,
            entity_id=entity_id,
            notif_id=notif_id,
        )

        # Validate reward actions require notif_id
        if parsed_action.is_reward_action and notif_id is None:
            const.LOGGER.warning("Reward action %s requires notif_id", action_type)
            return None

        return parsed_action

    except (IndexError, ValueError) as e:
        const.LOGGER.warning("Failed to parse action string '%s': %s", action_field, e)
        return None


# =============================================================================
# Action Handler
# =============================================================================


async def async_handle_notification_action(hass: HomeAssistant, event: Event) -> None:
    """Handle notification actions from HA companion notifications.

    Parses the action string from the event, validates it using ParsedAction,
    and routes to the appropriate coordinator method.

    Args:
        hass: Home Assistant instance
        event: Event containing the notification action data
    """
    action_field = event.data.get(const.NOTIFY_ACTION)
    if not action_field:
        const.LOGGER.error("No action found in event data: %s", event.data)
        return

    # Parse action string into typed ParsedAction object (v0.5.0+)
    parsed = parse_notification_action(action_field)
    if parsed is None:
        # parse_notification_action already logs warnings for invalid formats
        const.LOGGER.error("Failed to parse notification action: %s", action_field)
        return

    # Approver name may be provided in the event data or use a default
    approver_name = event.data.get(
        const.NOTIFY_APPROVER_NAME, const.NOTIFY_DEFAULT_APPROVER_NAME
    )

    # Retrieve the coordinator using modern registry lookup pattern.
    # Hard-fork contract requires entry_id in every action payload.
    target_entry = None
    for entry in hass.config_entries.async_entries(const.DOMAIN):
        if entry.entry_id.startswith(parsed.entry_id):
            target_entry = entry
            break
    if not target_entry:
        const.LOGGER.error(
            "ChoreOps config entry not found for truncated ID: %s",
            parsed.entry_id,
        )
        return

    # Get coordinator from runtime_data
    coordinator: ChoreOpsDataCoordinator = target_entry.runtime_data
    if not coordinator:
        const.LOGGER.error(
            "ChoreOps coordinator not found in runtime_data for entry: %s",
            target_entry.entry_id,
        )
        return

    try:
        if parsed.action_type == const.ACTION_APPROVE_CHORE:
            await coordinator.chore_manager.approve_chore(
                approver_name,
                assignee_id=parsed.assignee_id,
                chore_id=parsed.entity_id,
            )
        elif parsed.action_type == const.ACTION_CLAIM_CHORE:
            # Assignee claiming chore from notification (e.g., overdue reminder)
            assignee_info: AssigneeData = cast(
                "AssigneeData", coordinator.assignees_data.get(parsed.assignee_id, {})
            )
            assignee_name = assignee_info.get(const.DATA_USER_NAME, "Unknown")
            # Async method with lock protection
            await coordinator.chore_manager.claim_chore(
                assignee_id=parsed.assignee_id,
                chore_id=parsed.entity_id,
                user_name=assignee_name,
            )
        elif parsed.action_type == const.ACTION_COMPLETE_FOR_ASSIGNEE:
            # Approver completes chore directly (no claim needed)
            await coordinator.chore_manager.approve_chore(
                approver_name,
                assignee_id=parsed.assignee_id,
                chore_id=parsed.entity_id,
            )
        elif parsed.action_type == const.ACTION_DISAPPROVE_CHORE:
            await coordinator.chore_manager.disapprove_chore(
                approver_name,
                assignee_id=parsed.assignee_id,
                chore_id=parsed.entity_id,
            )
        elif parsed.action_type == const.ACTION_SKIP_CHORE:
            # Reset overdue chore to pending and reschedule
            await coordinator.chore_manager.reset_overdue_chores(
                chore_id=parsed.entity_id,
                assignee_id=parsed.assignee_id,
            )
        elif parsed.action_type == const.ACTION_APPROVE_REWARD:
            await coordinator.reward_manager.approve(
                approver_name,
                assignee_id=parsed.assignee_id,
                reward_id=parsed.entity_id,
                notif_id=parsed.notif_id,
            )
        elif parsed.action_type == const.ACTION_DISAPPROVE_REWARD:
            # Async method with lock protection
            await coordinator.reward_manager.disapprove(
                approver_name,
                assignee_id=parsed.assignee_id,
                reward_id=parsed.entity_id,
            )
        elif parsed.action_type == const.ACTION_REMIND_30:
            # Reminder can be for chore or reward - use computed properties
            await coordinator.notification_manager.remind_in_minutes(
                assignee_id=parsed.assignee_id,
                chore_id=parsed.chore_id,
                reward_id=parsed.reward_id,
                minutes=const.DEFAULT_REMINDER_DELAY,
            )
        else:
            # This shouldn't happen - parse_notification_action validates action types
            const.LOGGER.error(
                "Received unknown notification action: %s", parsed.action_type
            )
    except HomeAssistantError as err:
        const.LOGGER.error(
            "Failed processing notification action %s: %s", parsed.action_type, err
        )
