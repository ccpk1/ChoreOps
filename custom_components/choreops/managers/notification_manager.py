# File: notification_manager.py
"""Notification Manager for ChoreOps integration.

This manager handles all outgoing notification logic:
- Sending notifications to assignees and approvers
- Translation and localization
- Action button building
- Notification tag management for smart replacement
- Event-driven notifications (listens to domain events and sends appropriate notifications)

Separation of concerns (v0.5.0+):
- NotificationManager = "The Voice" (OUTGOING notifications)
- notification_action_handler.py = "The Router" (INCOMING action button callbacks)

Event-driven architecture (v0.5.0+):
- Subscribes to domain events (badge_earned, reward_claimed, etc.)
- Sends notifications in response to events
- Managers emit events, NotificationManager reacts
"""

from __future__ import annotations

import asyncio
import time
from typing import TYPE_CHECKING, Any, cast

from .. import const
from ..engines.chore_engine import ChoreEngine
from ..helpers import translation_helpers as th
from ..utils.dt_utils import dt_format_short, dt_now_iso, dt_to_utc
from .base_manager import BaseManager

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

    from ..coordinator import ChoreOpsDataCoordinator
    from ..type_defs import AssigneeData, ChoreData, RewardData


# =============================================================================
# Module-level helper for testability
# =============================================================================


async def async_send_notification(
    hass: HomeAssistant,
    service: str,
    title: str,
    message: str,
    actions: list[dict[str, Any]] | None = None,
    extra_data: dict[str, Any] | None = None,
) -> None:
    """Send a notification via Home Assistant service call.

    This is a module-level function that can be easily mocked in tests.
    It wraps the raw hass.services.async_call for notification services.

    Args:
        hass: Home Assistant instance
        service: Notification service in format "notify.service_name" or just service name
        title: Notification title
        message: Notification message
        actions: Optional list of action button dictionaries
        extra_data: Optional extra data (e.g., tag, notification_id)
    """
    # Parse domain/service
    if "." in service:
        domain, svc = service.split(".", 1)
    else:
        domain = const.NOTIFY_DOMAIN
        svc = service

    # Build payload
    payload: dict[str, Any] = {
        const.NOTIFY_TITLE: title,
        const.NOTIFY_MESSAGE: message,
    }

    if actions:
        data = payload.setdefault(const.NOTIFY_DATA, {})
        data[const.NOTIFY_ACTIONS] = actions

    if extra_data:
        data = payload.setdefault(const.NOTIFY_DATA, {})
        data.update(extra_data)

    const.LOGGER.debug(
        "async_send_notification: %s.%s - title='%s', message='%s'",
        domain,
        svc,
        title,
        message,
    )

    await hass.services.async_call(domain, svc, payload, blocking=True)


class NotificationManager(BaseManager):
    """Manager for sending notifications to assignees and approvers.

    Responsibilities:
    - Send translated notifications to assignees
    - Send translated notifications to approvers
    - Build notification action buttons
    - Handle notification tag generation for smart replacement
    - Clear notifications via tag

    Uses coordinator for:
    - assignees_data, approvers_data, chores_data, rewards_data lookups
    - Test mode detection (_test_mode flag)
    """

    # =========================================================================
    # Initialization
    # =========================================================================

    def __init__(
        self, hass: HomeAssistant, coordinator: ChoreOpsDataCoordinator
    ) -> None:
        """Initialize notification manager.

        Args:
            hass: Home Assistant instance
            coordinator: Approver coordinator for data access
        """
        super().__init__(hass, coordinator)
        # No additional state needed - manager delegates to coordinator data

    async def async_setup(self) -> None:
        """Set up the notification manager with event subscriptions.

        Subscribes to domain events that require notifications:
        - Badge earned → notify assignee and approvers
        - Achievement unlocked → notify assignee and approvers
        - Challenge completed → notify assignee and approvers
        - Reward claimed → notify approvers (approval needed)
        - Reward approved → notify assignee
        - Reward disapproved → notify assignee
        - Bonus applied → notify assignee
        - Penalty applied → notify assignee

        Also subscribes to DELETED events to clear ghost notifications:
        - Chore deleted → clear pending approval notifications
        - Reward deleted → clear pending claim notifications
        - Assignee deleted → clear all notifications for that assignee
        """
        # Badge events
        self.listen(const.SIGNAL_SUFFIX_BADGE_EARNED, self._handle_badge_earned)

        # Achievement/Challenge events
        self.listen(
            const.SIGNAL_SUFFIX_ACHIEVEMENT_EARNED, self._handle_achievement_earned
        )
        self.listen(
            const.SIGNAL_SUFFIX_CHALLENGE_COMPLETED, self._handle_challenge_completed
        )

        # Chore events
        self.listen(const.SIGNAL_SUFFIX_CHORE_CLAIMED, self._handle_chore_claimed)
        self.listen(
            const.SIGNAL_SUFFIX_CHORE_CLAIM_UNDONE, self._handle_chore_claim_undone
        )
        self.listen(const.SIGNAL_SUFFIX_CHORE_APPROVED, self._handle_chore_approved)
        self.listen(
            const.SIGNAL_SUFFIX_CHORE_DISAPPROVED, self._handle_chore_disapproved
        )

        # Reward events
        self.listen(const.SIGNAL_SUFFIX_REWARD_CLAIMED, self._handle_reward_claimed)
        self.listen(
            const.SIGNAL_SUFFIX_REWARD_CLAIM_UNDONE, self._handle_reward_claim_undone
        )
        self.listen(const.SIGNAL_SUFFIX_REWARD_APPROVED, self._handle_reward_approved)
        self.listen(
            const.SIGNAL_SUFFIX_REWARD_DISAPPROVED, self._handle_reward_disapproved
        )

        # Bonus/Penalty events
        self.listen(const.SIGNAL_SUFFIX_BONUS_APPLIED, self._handle_bonus_applied)
        self.listen(const.SIGNAL_SUFFIX_PENALTY_APPLIED, self._handle_penalty_applied)
        self.listen(
            const.SIGNAL_SUFFIX_POINTS_MULTIPLIER_CHANGE_REQUESTED,
            self._handle_multiplier_changed,
        )

        # Chore due date notification events (v0.6.0+: dual notification types)
        self.listen(const.SIGNAL_SUFFIX_CHORE_DUE_WINDOW, self._handle_chore_due_window)
        self.listen(
            const.SIGNAL_SUFFIX_CHORE_DUE_REMINDER, self._handle_chore_due_reminder
        )
        self.listen(const.SIGNAL_SUFFIX_CHORE_OVERDUE, self._handle_chore_overdue)
        # Phase 3 Step 9: Missed lock notification (v0.5.0)
        self.listen(const.SIGNAL_SUFFIX_CHORE_MISSED, self._handle_chore_missed)

        # DELETED events - clear ghost notifications (Phase 7.3.7)
        self.listen(const.SIGNAL_SUFFIX_CHORE_DELETED, self._handle_chore_deleted)
        self.listen(const.SIGNAL_SUFFIX_REWARD_DELETED, self._handle_reward_deleted)
        self.listen(const.SIGNAL_SUFFIX_USER_DELETED, self._handle_assignee_deleted)

        const.LOGGER.debug(
            "NotificationManager initialized with 17 event subscriptions for entry %s",
            self.entry_id,
        )

    # =========================================================================
    # Notification Tag Helper
    # =========================================================================

    @staticmethod
    def build_notification_tag(tag_type: str, *identifiers: str) -> str:
        """Build a notification tag string for smart replacement.

        Tags allow subsequent notifications with the same tag to replace previous ones
        instead of stacking, reducing notification spam.

        CRITICAL: Apple's apns-collapse-id header has a 64-byte limit. Since identifiers
        are typically UUIDs (36 chars each), we truncate them to 8 chars to stay within
        the limit while maintaining sufficient uniqueness for tag matching.

        Args:
            tag_type: Type of notification (pending, rewards, system, status).
                      Use const.NOTIFY_TAG_TYPE_* constants.
            *identifiers: One or more identifiers to make tag unique.
                         For per-item tags: (item_id, assignee_id)
                         For per-assignee tags: (assignee_id,)
                         Identifiers are truncated to first 8 characters.

        Returns:
            Tag string in format: assigneeschores-{tag_type}-{id1[:8]}-{id2[:8]}-...
            or assigneeschores-{tag_type} if no identifiers provided.
            Maximum length: ~40 bytes (well under Apple's 64-byte limit).

        Examples:
            build_notification_tag(const.NOTIFY_TAG_TYPE_STATUS, chore_id, assignee_id)
            -> "assigneeschores-status-abc12345-def67890"

            build_notification_tag(const.NOTIFY_TAG_TYPE_SYSTEM, assignee_id)
            -> "assigneeschores-system-abc12345"
        """
        if identifiers:
            normalized_ids: list[str] = []
            for identifier in identifiers:
                if identifier.startswith(("assignee-", "user-")):
                    normalized_ids.append(identifier)
                    continue

                # Keep item identifiers short to stay under Apple's 64-byte limit
                normalized_ids.append(identifier[:8])

            return f"{const.NOTIFY_TAG_PREFIX}-{tag_type}-{'-'.join(normalized_ids)}"
        return f"{const.NOTIFY_TAG_PREFIX}-{tag_type}"

    # =========================================================================
    # Chore Notification Schedule-Lock Helpers (Platinum Pattern v0.5.0+)
    # =========================================================================
    #
    # These helpers implement the "Schedule-Lock" pattern for persistent
    # chore notification deduplication. Key architectural points:
    #
    # 1. SEPARATE BUCKET: NotificationManager owns DATA_NOTIFICATIONS bucket.
    #    We do NOT write to ChoreManager's chore_data (domain separation).
    #
    # 2. READ-ONLY QUERY: We read approval_period_start from ChoreManager's
    #    data for the Schedule-Lock comparison (query, not mutation).
    #
    # 3. AUTOMATIC INVALIDATION: When chore resets, approval_period_start
    #    advances. Any old notification timestamps become obsolete because
    #    last_notified < new_period_start.
    #
    # 4. CLEANUP VIA SIGNALS: CHORE_DELETED and KID_DELETED signals trigger
    #    cleanup in our notifications bucket (choreographed janitor pattern).
    #
    # Structure: notifications[assignee_id][chore_id] = {
    #     "last_due_start": ISO timestamp,
    #     "last_due_reminder": ISO timestamp,
    #     "last_overdue": ISO timestamp,
    # }
    # =========================================================================

    def _get_chore_notifications_bucket(self) -> dict[str, Any]:
        """Get or create the chore notifications top-level bucket.

        Returns:
            Mutable dict reference to notifications bucket
        """
        return self.coordinator._data.setdefault(const.DATA_NOTIFICATIONS, {})

    def _get_chore_notification_record(
        self, assignee_id: str, chore_id: str
    ) -> dict[str, Any]:
        """Get or create chore notification record for a assignee+chore combination.

        Args:
            assignee_id: The assignee's internal ID (UUID)
            chore_id: The chore's internal ID (UUID)

        Returns:
            Mutable dict reference to notification record
        """
        notifications = self._get_chore_notifications_bucket()
        assignee_notifs = notifications.setdefault(assignee_id, {})
        return assignee_notifs.setdefault(chore_id, {})

    def _get_chore_approval_period_start(
        self, assignee_id: str, chore_id: str
    ) -> str | None:
        """Query the approval_period_start from ChoreManager (read-only).

        Uses ChoreManager's public read method for cross-manager queries.
        This follows the "Reads OK" pattern from DEVELOPMENT_STANDARDS.md § 4b.

        Args:
            assignee_id: The assignee's internal ID (UUID)
            chore_id: The chore's internal ID (UUID)

        Returns:
            ISO datetime string of approval_period_start, or None if not found
        """
        return self.coordinator.chore_manager.get_approval_period_start(
            assignee_id, chore_id
        )

    def _get_chore_notif_key(self, notif_type: str) -> str:
        """Map chore notification type to storage key.

        Args:
            notif_type: "due_start", "due_reminder", or "overdue"

        Returns:
            Storage key constant
        """
        key_map = {
            "due_start": const.DATA_NOTIF_LAST_DUE_START,
            "due_reminder": const.DATA_NOTIF_LAST_DUE_REMINDER,
            "overdue": const.DATA_NOTIF_LAST_OVERDUE,
        }
        return key_map.get(notif_type, const.DATA_NOTIF_LAST_DUE_START)

    def _should_send_chore_notification(
        self, assignee_id: str, chore_id: str, notif_type: str
    ) -> bool:
        """Check if chore notification should be sent using Schedule-Lock pattern.

        The Schedule-Lock pattern compares the last notification timestamp
        (from our notifications bucket) against the approval_period_start
        (queried from ChoreManager's chore_data).

        A notification is only suppressed if it was already sent WITHIN
        the current period. When a chore resets, approval_period_start
        advances, making old timestamps obsolete (automatic invalidation).

        Args:
            assignee_id: The assignee's internal ID (UUID)
            chore_id: The chore's internal ID (UUID)
            notif_type: "due_start", "due_reminder", or "overdue"

        Returns:
            True if notification should be sent, False if should be suppressed
        """
        notif_key = self._get_chore_notif_key(notif_type)

        # Get our notification record (from our bucket)
        notif_record = self._get_chore_notification_record(assignee_id, chore_id)
        last_notified_str = notif_record.get(notif_key)
        if not last_notified_str:
            return True  # Never notified - send it

        # Query approval_period_start from ChoreManager (read-only)
        period_start_str = self._get_chore_approval_period_start(assignee_id, chore_id)
        if not period_start_str:
            return True  # No period defined - send it

        last_notified = dt_to_utc(last_notified_str)
        period_start = dt_to_utc(period_start_str)

        if last_notified is None or period_start is None:
            return True  # Parse error - send to be safe

        # Schedule-Lock: Suppress only if notified WITHIN current period
        return last_notified < period_start

    def _record_chore_notification_sent(
        self, assignee_id: str, chore_id: str, notif_type: str
    ) -> None:
        """Record chore notification timestamp in our bucket and persist.

        Updates the notification timestamp in our DATA_NOTIFICATIONS bucket
        to "lock" this occurrence. Subsequent calls within the same period
        will be suppressed by _should_send_chore_notification().

        Args:
            assignee_id: The assignee's internal ID (UUID)
            chore_id: The chore's internal ID (UUID)
            notif_type: "due_start", "due_reminder", or "overdue"
        """
        notif_key = self._get_chore_notif_key(notif_type)

        notif_record = self._get_chore_notification_record(assignee_id, chore_id)
        notif_record[notif_key] = dt_now_iso()
        self.coordinator._persist()  # Debounced persist

        const.LOGGER.debug(
            "Recorded chore notification timestamp for assignee=%s chore=%s type=%s",
            assignee_id[:8],
            chore_id[:8],
            notif_type,
        )

    def _cleanup_chore_notifications(self, chore_id: str) -> None:
        """Remove all notification records for a deleted chore.

        Called when CHORE_DELETED signal is received. Prevents ghost records
        in our bucket after chore deletion.

        Args:
            chore_id: The deleted chore's internal ID (UUID)
        """
        notifications = self._get_chore_notifications_bucket()
        cleaned = 0
        for assignee_id in list(notifications.keys()):
            if chore_id in notifications.get(assignee_id, {}):
                del notifications[assignee_id][chore_id]
                cleaned += 1
                # Clean up empty assignee dict
                if not notifications[assignee_id]:
                    del notifications[assignee_id]

        if cleaned > 0:
            self.coordinator._persist()
            const.LOGGER.debug(
                "Cleaned %d notification records for deleted chore=%s",
                cleaned,
                chore_id[:8],
            )

    def _cleanup_assignee_chore_notifications(self, assignee_id: str) -> None:
        """Remove all chore notification records for a deleted assignee.

        Called when KID_DELETED signal is received. Prevents ghost records
        in our bucket after assignee deletion.

        Args:
            assignee_id: The deleted assignee's internal ID (UUID)
        """
        notifications = self._get_chore_notifications_bucket()
        if assignee_id in notifications:
            del notifications[assignee_id]
            self.coordinator._persist()
            const.LOGGER.debug(
                "Cleaned notification records for deleted assignee=%s",
                assignee_id[:8],
            )

    # =========================================================================
    # Action Button Builders
    # =========================================================================

    @staticmethod
    def build_claim_action(
        assignee_id: str, chore_id: str, entry_id: str
    ) -> list[dict[str, str]]:
        """Build a claim action button for assignee notifications.

        Returns a single action button for assignees to claim a chore directly from
        a notification (e.g., overdue or due-soon reminders).

        Args:
            assignee_id: The internal ID of the assignee
            chore_id: The internal ID of the chore
            entry_id: The config entry ID (will be truncated to 8 chars)

        Returns:
            List containing one action dictionary with 'action' and 'title' keys.
        """
        truncated_entry_id = entry_id[:8]
        return [
            {
                const.NOTIFY_ACTION: f"{const.ACTION_CLAIM_CHORE}|{truncated_entry_id}|{assignee_id}|{chore_id}",
                const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_CLAIM,
            },
        ]

    @staticmethod
    def build_skip_action(
        assignee_id: str, chore_id: str, entry_id: str
    ) -> list[dict[str, str]]:
        """Build skip action button for overdue chores.

        Skip action resets the chore to PENDING state and reschedules it to the
        next due date.

        Args:
            assignee_id: The internal ID of the assignee
            chore_id: The internal ID of the chore

        Returns:
            List with single action dict for Skip button
        """
        truncated_entry_id = entry_id[:8]
        return [
            {
                const.NOTIFY_ACTION: f"{const.ACTION_SKIP_CHORE}|{truncated_entry_id}|{assignee_id}|{chore_id}",
                const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_SKIP,
            },
        ]

    @staticmethod
    def build_complete_action(
        assignee_id: str, chore_id: str, entry_id: str
    ) -> list[dict[str, str]]:
        """Build complete action button for overdue chores.

        Complete action directly approves the chore for the assignee without requiring
        a claim step first.

        Args:
            assignee_id: The internal ID of the assignee
            chore_id: The internal ID of the chore

        Returns:
            List with single action dict for Complete button
        """
        truncated_entry_id = entry_id[:8]
        return [
            {
                const.NOTIFY_ACTION: f"{const.ACTION_COMPLETE_FOR_ASSIGNEE}|{truncated_entry_id}|{assignee_id}|{chore_id}",
                const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_COMPLETE,
            },
        ]

    @staticmethod
    def build_remind_action(
        assignee_id: str, chore_id: str, entry_id: str
    ) -> list[dict[str, str]]:
        """Build remind action button for chore notifications.

        Remind action schedules a follow-up reminder notification in 30 minutes.

        Args:
            assignee_id: The internal ID of the assignee
            chore_id: The internal ID of the chore

        Returns:
            List with single action dict for Remind button
        """
        truncated_entry_id = entry_id[:8]
        return [
            {
                const.NOTIFY_ACTION: f"{const.ACTION_REMIND_30}|{truncated_entry_id}|{assignee_id}|{chore_id}",
                const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_REMIND_30,
            },
        ]

    @staticmethod
    def build_chore_actions(
        assignee_id: str, chore_id: str, entry_id: str
    ) -> list[dict[str, str]]:
        """Build standard notification actions for chore workflows.

        Returns the three standard action buttons for chore notifications:
        - Approve: Marks the chore as approved and awards points
        - Disapprove: Rejects the chore claim, resetting to pending
        - Remind in 30: Schedules a follow-up reminder notification

        Args:
            assignee_id: The internal ID of the assignee
            chore_id: The internal ID of the chore
            entry_id: The config entry ID (will be truncated to 8 chars)

        Returns:
            List of action dictionaries with 'action' and 'title' keys.
        """
        truncated_entry_id = entry_id[:8]
        return [
            {
                const.NOTIFY_ACTION: f"{const.ACTION_APPROVE_CHORE}|{truncated_entry_id}|{assignee_id}|{chore_id}",
                const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_APPROVE,
            },
            {
                const.NOTIFY_ACTION: f"{const.ACTION_DISAPPROVE_CHORE}|{truncated_entry_id}|{assignee_id}|{chore_id}",
                const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_DISAPPROVE,
            },
            {
                const.NOTIFY_ACTION: f"{const.ACTION_REMIND_30}|{truncated_entry_id}|{assignee_id}|{chore_id}",
                const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_REMIND_30,
            },
        ]

    @staticmethod
    def build_reward_actions(
        assignee_id: str,
        reward_id: str,
        entry_id: str,
        notif_id: str | None = None,
    ) -> list[dict[str, str]]:
        """Build standard notification actions for reward workflows.

        Returns the three standard action buttons for reward notifications:
        - Approve: Confirms the reward claim and deducts points
        - Disapprove: Rejects the reward claim, refunding any held points
        - Remind in 30: Schedules a follow-up reminder notification

        Args:
            assignee_id: The internal ID of the assignee
            reward_id: The internal ID of the reward
            entry_id: The config entry ID (will be truncated to 8 chars)
            notif_id: Optional notification tracking ID for deduplication.

        Returns:
            List of action dictionaries with 'action' and 'title' keys.
        """
        truncated_entry_id = entry_id[:8]
        suffix = f"|{notif_id}" if notif_id else ""

        return [
            {
                const.NOTIFY_ACTION: f"{const.ACTION_APPROVE_REWARD}|{truncated_entry_id}|{assignee_id}|{reward_id}{suffix}",
                const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_APPROVE,
            },
            {
                const.NOTIFY_ACTION: f"{const.ACTION_DISAPPROVE_REWARD}|{truncated_entry_id}|{assignee_id}|{reward_id}{suffix}",
                const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_DISAPPROVE,
            },
            {
                const.NOTIFY_ACTION: f"{const.ACTION_REMIND_30}|{truncated_entry_id}|{assignee_id}|{reward_id}{suffix}",
                const.NOTIFY_TITLE: const.TRANS_KEY_NOTIF_ACTION_REMIND_30,
            },
        ]

    @staticmethod
    def build_extra_data(
        assignee_id: str,
        chore_id: str | None = None,
        reward_id: str | None = None,
        notif_id: str | None = None,
    ) -> dict[str, str]:
        """Build consistent extra_data dictionary for notification context.

        Extra data is included in the notification payload for deep-linking
        and context retrieval when processing action callbacks.

        Args:
            assignee_id: The internal ID of the assignee (always required)
            chore_id: Optional chore internal ID (for chore notifications)
            reward_id: Optional reward internal ID (for reward notifications)
            notif_id: Optional notification tracking ID

        Returns:
            Dictionary with relevant context keys. Only includes non-None values.
        """
        data: dict[str, str] = {const.DATA_USER_ID: assignee_id}

        if chore_id:
            data[const.DATA_CHORE_ID] = chore_id
        if reward_id:
            data[const.DATA_REWARD_ID] = reward_id
        if notif_id:
            data[const.NOTIFY_NOTIFICATION_ID] = notif_id

        return data

    # =========================================================================
    # Translation Helpers
    # =========================================================================

    def _convert_notification_key(self, const_key: str) -> str:
        """Convert const translation key to JSON key.

        Removes notification prefix from const keys:
        - "notification_title_chore_assigned" -> "chore_assigned"
        - "notification_message_reward_claimed" -> "reward_claimed"
        """
        return const_key.replace("notification_title_", "").replace(
            "notification_message_", ""
        )

    def _format_notification_text(
        self,
        template: str,
        data: dict[str, Any] | None,
        json_key: str,
        text_type: str = "message",
    ) -> str | None:
        """Format notification text with placeholders, blocking on missing data.

        Args:
            template: Template string with {placeholder} syntax
            data: Dictionary of placeholder values
            json_key: Notification key for logging
            text_type: "title" or "message" for error logging

        Returns:
            Formatted string if successful, None if placeholders missing (blocks notification)
        """
        try:
            return template.format(**(data or {}))
        except KeyError as err:
            const.LOGGER.error(
                "Blocking notification '%s' due to missing placeholder %s in %s. "
                "This indicates a system bug that needs fixing.",
                json_key,
                err,
                text_type,
            )
            return None

    def _translate_action_buttons(
        self, actions: list[dict[str, str]] | None, translations: dict[str, Any]
    ) -> list[dict[str, str]] | None:
        """Translate action button titles using loaded translations.

        Converts action keys like "notif_action_approve" to translation keys
        like "approve", then looks up translated text from the "actions" section
        of notification translations.

        Args:
            actions: List of action dicts with 'action' and 'title' keys
            translations: Loaded notification translations dict

        Returns:
            New list with translated action titles, or None if no actions
        """
        if not actions:
            return None

        action_translations = translations.get("actions", {})
        translated_actions = []

        for action in actions:
            translated_action = action.copy()
            action_title_key = action.get(const.NOTIFY_TITLE, "")
            # Convert "notif_action_approve" -> "approve"
            action_key = action_title_key.replace("notif_action_", "")
            # Look up translation, fallback to original key
            translated_title = action_translations.get(action_key, action_title_key)
            translated_action[const.NOTIFY_TITLE] = translated_title
            translated_actions.append(translated_action)

        const.LOGGER.debug(
            "Translated action buttons: %s -> %s",
            [a.get(const.NOTIFY_TITLE) for a in actions],
            [a.get(const.NOTIFY_TITLE) for a in translated_actions],
        )

        return translated_actions

    # =========================================================================
    # Core Notification Send Method
    # =========================================================================

    async def _send_notification(
        self,
        notify_service: str,
        title: str,
        message: str,
        actions: list[dict[str, str]] | None = None,
        extra_data: dict[str, str] | None = None,
    ) -> None:
        """Send a notification using the specified notify service.

        Gracefully handles missing notification services (common in fresh installs,
        migrations, or when mobile app isn't configured yet).

        Uses the module-level async_send_notification function which can be
        easily mocked in tests.
        """
        # Parse service name into domain and service components
        if const.DISPLAY_DOT not in notify_service:
            domain = const.NOTIFY_DOMAIN
            service = notify_service
        else:
            domain, service = notify_service.split(".", 1)

        # Validate service exists before attempting to send
        if not self.hass.services.has_service(domain, service):
            const.LOGGER.warning(
                "Notification service '%s.%s' not available - skipping notification. "
                "This is normal during migration or if the mobile app/notification "
                "integration isn't configured yet",
                domain,
                service,
            )
            return

        const.LOGGER.debug(
            "Sending notification via '%s.%s': title='%s', message='%s', actions=%s",
            domain,
            service,
            title,
            message,
            actions,
        )

        try:
            # Use module-level function for testability
            await async_send_notification(
                self.hass,
                notify_service,
                title,
                message,
                actions,
                extra_data,
            )
            const.LOGGER.debug("Notification sent via '%s.%s'", domain, service)

        except Exception as err:
            # Broad exception allowed: This runs in fire-and-forget background tasks
            # per AGENTS.md guidelines. We must catch all exceptions to prevent
            # "Task exception was never retrieved" errors in logs.
            const.LOGGER.error(
                "Unexpected error sending notification via '%s.%s': %s",
                domain,
                service,
                err,
            )

    # =========================================================================
    # Persistent Notification (System)
    # =========================================================================

    async def send_persistent_notification(
        self,
        user_id: str | None,
        title: str,
        message: str,
        notification_id: str,
    ) -> None:
        """Send a persistent notification to a user if possible.

        Fallback to a general persistent notification if the user is not found.
        """
        if not user_id:
            const.LOGGER.debug(
                "No User ID provided. Sending a general persistent notification"
            )
            await self.hass.services.async_call(
                const.NOTIFY_PERSISTENT_NOTIFICATION,
                const.NOTIFY_CREATE,
                {
                    const.NOTIFY_TITLE: title,
                    const.NOTIFY_MESSAGE: message,
                    const.NOTIFY_NOTIFICATION_ID: notification_id,
                },
                blocking=True,
            )
            return

        try:
            user_obj = await self.hass.auth.async_get_user(user_id)
            if not user_obj:
                const.LOGGER.warning(
                    "User ID '%s' not found. Sending fallback persistent notification",
                    user_id,
                )
                await self.hass.services.async_call(
                    const.NOTIFY_PERSISTENT_NOTIFICATION,
                    const.NOTIFY_CREATE,
                    {
                        const.NOTIFY_TITLE: title,
                        const.NOTIFY_MESSAGE: message,
                        const.NOTIFY_NOTIFICATION_ID: notification_id,
                    },
                    blocking=True,
                )
                return

            await self.hass.services.async_call(
                const.NOTIFY_PERSISTENT_NOTIFICATION,
                const.NOTIFY_CREATE,
                {
                    const.NOTIFY_TITLE: title,
                    const.NOTIFY_MESSAGE: message,
                    const.NOTIFY_NOTIFICATION_ID: notification_id,
                },
                blocking=True,
            )
        except Exception as err:
            # Broad exception allowed: Background task
            const.LOGGER.warning(
                "Failed to send notification to '%s': %s. Fallback to persistent notification",
                user_id,
                err,
            )
            await self.hass.services.async_call(
                const.NOTIFY_PERSISTENT_NOTIFICATION,
                const.NOTIFY_CREATE,
                {
                    const.NOTIFY_TITLE: title,
                    const.NOTIFY_MESSAGE: message,
                    const.NOTIFY_NOTIFICATION_ID: notification_id,
                },
                blocking=True,
            )

    # =========================================================================
    # Assignee Notifications
    # =========================================================================

    async def notify_assignee(
        self,
        assignee_id: str,
        title: str,
        message: str,
        actions: list[dict[str, str]] | None = None,
        extra_data: dict[str, str] | None = None,
        tag_type: str | None = None,
        tag_identifiers: tuple[str, ...] | None = None,
    ) -> None:
        """Notify a assignee using their configured notification settings."""
        assignee_info: AssigneeData | None = self.coordinator.assignees_data.get(
            assignee_id
        )
        if not assignee_info:
            return

        # Build notification tag if tag_type provided
        notification_tag = None
        if tag_type:
            # Multi-instance support: always include entry_id as first identifier
            base_identifiers = (self.entry_id,)
            if tag_identifiers:
                identifiers = (*base_identifiers, *tag_identifiers)
            else:
                identifiers = (*base_identifiers, assignee_id)
            notification_tag = self.build_notification_tag(tag_type, *identifiers)
            const.LOGGER.debug(
                "Using notification tag '%s' for assignee %s",
                notification_tag,
                assignee_id,
            )

        mobile_notify_service = assignee_info.get(
            const.DATA_USER_MOBILE_NOTIFY_SERVICE, const.SENTINEL_EMPTY
        )
        persistent_enabled = assignee_info.get(
            const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS, True
        )

        if mobile_notify_service:
            # Build final extra_data with tag if provided
            final_extra_data = dict(extra_data) if extra_data else {}
            if notification_tag:
                final_extra_data[const.NOTIFY_TAG] = notification_tag

            await self._send_notification(
                mobile_notify_service,
                title,
                message,
                actions=actions,
                extra_data=final_extra_data or None,
            )
        elif persistent_enabled:
            # Use tag for notification_id when available for smart replacement
            notification_id = notification_tag or f"assignee_{assignee_id}"
            await self.hass.services.async_call(
                const.NOTIFY_PERSISTENT_NOTIFICATION,
                const.NOTIFY_CREATE,
                {
                    const.NOTIFY_TITLE: title,
                    const.NOTIFY_MESSAGE: message,
                    const.NOTIFY_NOTIFICATION_ID: notification_id,
                },
                blocking=True,
            )
        else:
            const.LOGGER.debug(
                "No notification method configured for Assignee ID '%s'",
                assignee_id,
            )

    async def notify_assignee_translated(
        self,
        assignee_id: str,
        title_key: str,
        message_key: str,
        message_data: dict[str, Any] | None = None,
        actions: list[dict[str, str]] | None = None,
        extra_data: dict[str, str] | None = None,
        tag_type: str | None = None,
        tag_identifiers: tuple[str, ...] | None = None,
    ) -> None:
        """Notify a assignee using translated title and message.

        Args:
            assignee_id: The internal ID of the assignee
            title_key: Translation key for the notification title
            message_key: Translation key for the notification message
            message_data: Dictionary of placeholder values for message formatting
            actions: Optional list of notification actions
            extra_data: Optional extra data for mobile notifications
        """
        # Get assignee's preferred language (or fall back to system language)
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(assignee_id, {})
        )
        language = assignee_info.get(
            const.DATA_USER_DASHBOARD_LANGUAGE,
            self.hass.config.language,
        )
        const.LOGGER.debug(
            "Notification: assignee_id=%s, language=%s, title_key=%s",
            assignee_id,
            language,
            title_key,
        )

        # Load notification translations from custom translations directory
        translations = await th.load_notification_translation(self.hass, language)
        const.LOGGER.debug(
            "Notification translations loaded: %d keys, language=%s",
            len(translations),
            language,
        )

        # Convert const keys to JSON keys and look up translations
        title_json_key = self._convert_notification_key(title_key)
        message_json_key = self._convert_notification_key(message_key)
        title_notification = translations.get(title_json_key, {})
        message_notification = translations.get(message_json_key, {})

        # Format title and message with placeholders
        title = self._format_notification_text(
            title_notification.get("title", title_key),
            message_data,
            title_json_key,
            "title",
        )
        message = self._format_notification_text(
            message_notification.get("message", message_key),
            message_data,
            message_json_key,
            "message",
        )

        # Skip notification if placeholders missing
        if title is None or message is None:
            const.LOGGER.error(
                "Skipping notification to assignee_id=%s due to missing placeholders",
                assignee_id,
            )
            return

        # Translate action button titles
        translated_actions = self._translate_action_buttons(actions, translations)

        # Call notification method
        await self.notify_assignee(
            assignee_id,
            title,
            message,
            translated_actions,
            extra_data,
            tag_type=tag_type,
            tag_identifiers=tag_identifiers,
        )

    # =========================================================================
    # Approver Notifications
    # =========================================================================

    async def notify_approvers(
        self,
        assignee_id: str,
        title: str,
        message: str,
        actions: list[dict[str, str]] | None = None,
        extra_data: dict[str, str] | None = None,
    ) -> None:
        """Notify all approvers associated with a assignee using their settings."""
        perf_start = time.perf_counter()
        approver_count = 0

        for approver_id, approver_info in self.coordinator.approvers_data.items():
            associated_user_ids = approver_info.get(
                const.DATA_USER_ASSOCIATED_USER_IDS, []
            )
            if not isinstance(associated_user_ids, list):
                continue
            if assignee_id not in associated_user_ids:
                continue

            mobile_notify_service = approver_info.get(
                const.DATA_USER_MOBILE_NOTIFY_SERVICE, const.SENTINEL_EMPTY
            )
            persistent_enabled = approver_info.get(
                const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS,
                True,
            )

            if mobile_notify_service:
                approver_count += 1
                await self._send_notification(
                    mobile_notify_service,
                    title,
                    message,
                    actions=actions,
                    extra_data=extra_data,
                )
            elif persistent_enabled:
                approver_count += 1
                await self.hass.services.async_call(
                    const.NOTIFY_PERSISTENT_NOTIFICATION,
                    const.NOTIFY_CREATE,
                    {
                        const.NOTIFY_TITLE: title,
                        const.NOTIFY_MESSAGE: message,
                        const.NOTIFY_NOTIFICATION_ID: f"approver_{approver_id}",
                    },
                    blocking=True,
                )
            else:
                const.LOGGER.debug(
                    "No notification method configured for Approver ID '%s'",
                    approver_id,
                )

        # PERF: Log approver notification latency
        perf_duration = time.perf_counter() - perf_start
        const.LOGGER.debug(
            "PERF: notify_approvers() sent %d notifications in %.3fs (sequential)",
            approver_count,
            perf_duration,
        )

    async def notify_approvers_translated(
        self,
        assignee_id: str,
        title_key: str,
        message_key: str,
        message_data: dict[str, Any] | None = None,
        actions: list[dict[str, str]] | None = None,
        extra_data: dict[str, str] | None = None,
        tag_type: str | None = None,
        tag_identifiers: tuple[str, ...] | None = None,
    ) -> None:
        """Notify approvers using translated title and message.

        Each approver receives notifications in their own preferred language.
        Supports tag-based notification replacement (v0.5.0+).
        Uses concurrent notification sending for ~3x performance improvement.

        Args:
            assignee_id: The internal ID of the assignee (to find associated approvers)
            title_key: Translation key for the notification title
            message_key: Translation key for the notification message
            message_data: Dictionary of placeholder values for message formatting
            actions: Optional list of notification actions
            extra_data: Optional extra data for mobile notifications
            tag_type: Optional tag type for smart notification replacement.
            tag_identifiers: Optional tuple of identifiers for tag uniqueness.
        """
        perf_start = time.perf_counter()

        # Build notification tag if tag_type provided
        notification_tag = None
        if tag_type:
            # Multi-instance support: always include entry_id as first identifier
            base_identifiers = (self.entry_id,)
            if tag_identifiers:
                identifiers = (*base_identifiers, *tag_identifiers)
            else:
                identifiers = (*base_identifiers, assignee_id)
            notification_tag = self.build_notification_tag(tag_type, *identifiers)
            const.LOGGER.debug(
                "Using notification tag '%s' for identifiers %s",
                notification_tag,
                identifiers,
            )

        # Phase 1: Prepare all approver notifications (translations, formatting)
        notification_tasks: list[tuple[str, Any]] = []

        for approver_id, approver_info in self.coordinator.approvers_data.items():
            associated_user_ids = approver_info.get(
                const.DATA_USER_ASSOCIATED_USER_IDS, []
            )
            if not isinstance(associated_user_ids, list):
                continue
            if assignee_id not in associated_user_ids:
                continue

            # Use approver's language preference
            approver_language = (
                approver_info.get(const.DATA_USER_DASHBOARD_LANGUAGE)
                or cast(
                    "AssigneeData", self.coordinator.assignees_data.get(assignee_id, {})
                ).get(const.DATA_USER_DASHBOARD_LANGUAGE)
                or self.hass.config.language
            )

            const.LOGGER.debug(
                "Approver notification: assignee_id=%s, approver_id=%s, language=%s, title_key=%s",
                assignee_id,
                approver_id,
                approver_language,
                title_key,
            )

            # Load notification translations for this approver's language
            translations = await th.load_notification_translation(
                self.hass, approver_language
            )

            # Convert const keys to JSON keys and look up translations
            title_json_key = self._convert_notification_key(title_key)
            message_json_key = self._convert_notification_key(message_key)
            title_notification = translations.get(title_json_key, {})
            message_notification = translations.get(message_json_key, {})

            # Format both title and message with placeholders
            title = self._format_notification_text(
                title_notification.get("title", title_key),
                message_data,
                title_json_key,
                "title",
            )
            message = self._format_notification_text(
                message_notification.get("message", message_key),
                message_data,
                message_json_key,
                "message",
            )

            # Skip notification if placeholders missing
            if title is None or message is None:
                const.LOGGER.error(
                    "Skipping notification to approver_id=%s (assignee_id=%s) due to missing placeholders",
                    approver_id,
                    assignee_id,
                )
                continue

            # Translate action button titles
            translated_actions = self._translate_action_buttons(actions, translations)

            # Build final extra_data with tag if provided
            final_extra_data = dict(extra_data) if extra_data else {}
            if notification_tag:
                final_extra_data[const.NOTIFY_TAG] = notification_tag

            # Determine notification method and prepare coroutine
            persistent_enabled = approver_info.get(
                const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS,
                True,
            )
            mobile_notify_service = approver_info.get(
                const.DATA_USER_MOBILE_NOTIFY_SERVICE, const.SENTINEL_EMPTY
            )

            if mobile_notify_service:
                notification_tasks.append(
                    (
                        approver_id,
                        self._send_notification(
                            mobile_notify_service,
                            title,
                            message,
                            actions=translated_actions,
                            extra_data=final_extra_data or None,
                        ),
                    )
                )
            elif persistent_enabled:
                notification_tasks.append(
                    (
                        approver_id,
                        self.hass.services.async_call(
                            const.NOTIFY_PERSISTENT_NOTIFICATION,
                            const.NOTIFY_CREATE,
                            {
                                const.NOTIFY_TITLE: title,
                                const.NOTIFY_MESSAGE: message,
                                const.NOTIFY_NOTIFICATION_ID: f"approver_{approver_id}",
                            },
                            blocking=True,
                        ),
                    )
                )
            else:
                const.LOGGER.debug(
                    "No notification method configured for Approver ID '%s'",
                    approver_id,
                )

        # Phase 2: Send all notifications concurrently
        approver_count = len(notification_tasks)
        if notification_tasks:
            results = await asyncio.gather(
                *[coro for _, coro in notification_tasks],
                return_exceptions=True,
            )

            # Log any errors
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    approver_id = notification_tasks[idx][0]
                    const.LOGGER.warning(
                        "Failed to send notification to approver '%s': %s",
                        approver_id,
                        result,
                    )

        # PERF: Log approver notification latency
        perf_duration = time.perf_counter() - perf_start
        const.LOGGER.debug(
            "PERF: notify_approvers_translated() sent %d notifications in %.3fs (concurrent)",
            approver_count,
            perf_duration,
        )

    async def broadcast_to_all_approvers(
        self,
        title_key: str,
        message_key: str,
        placeholders: dict[str, str] | None = None,
    ) -> None:
        """Broadcast a notification to ALL approvers (system-level announcements).

        Unlike notify_approvers_translated(), this sends to every approver regardless
        of assignee association. Used for system-wide notifications like data resets.

        Each approver receives the notification in their preferred language.

        Args:
            title_key: Translation key for the notification title
            message_key: Translation key for the notification message
            placeholders: Optional placeholder values for message formatting
        """
        perf_start = time.perf_counter()
        notification_tasks: list[tuple[str, Any]] = []
        message_data = placeholders or {}

        for approver_id, approver_info in self.coordinator.approvers_data.items():
            # Use approver's language preference, fall back to system language
            approver_language = (
                approver_info.get(const.DATA_USER_DASHBOARD_LANGUAGE)
                or self.hass.config.language
            )

            # Load notification translations for this approver's language
            translations = await th.load_notification_translation(
                self.hass, approver_language
            )

            # Convert const key to JSON key and look up translations
            json_key = self._convert_notification_key(title_key)
            notification = translations.get(json_key, {})

            # Format both title and message with placeholders
            title = self._format_notification_text(
                notification.get("title", title_key), message_data, json_key, "title"
            )
            message = self._format_notification_text(
                notification.get("message", message_key),
                message_data,
                json_key,
                "message",
            )

            # Skip notification if placeholders missing
            if title is None or message is None:
                const.LOGGER.error(
                    "Skipping notification to approver_id=%s due to missing placeholders",
                    approver_id,
                )
                continue

            mobile_notify_service = approver_info.get(
                const.DATA_USER_MOBILE_NOTIFY_SERVICE, const.SENTINEL_EMPTY
            )
            persistent_enabled = approver_info.get(
                const.DATA_USER_USE_PERSISTENT_NOTIFICATIONS,
                True,
            )

            if mobile_notify_service:
                notification_tasks.append(
                    (
                        approver_id,
                        self._send_notification(
                            mobile_notify_service,
                            title,
                            message,
                        ),
                    )
                )
            elif persistent_enabled:
                notification_tasks.append(
                    (
                        approver_id,
                        self.hass.services.async_call(
                            const.NOTIFY_PERSISTENT_NOTIFICATION,
                            const.NOTIFY_CREATE,
                            {
                                const.NOTIFY_TITLE: title,
                                const.NOTIFY_MESSAGE: message,
                                const.NOTIFY_NOTIFICATION_ID: f"kc_system_{approver_id}",
                            },
                            blocking=True,
                        ),
                    )
                )
            else:
                const.LOGGER.debug(
                    "No notification method configured for Approver ID '%s'",
                    approver_id,
                )

        # Send all notifications concurrently
        approver_count = len(notification_tasks)
        if notification_tasks:
            results = await asyncio.gather(
                *[coro for _, coro in notification_tasks],
                return_exceptions=True,
            )

            # Log any errors
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    approver_id = notification_tasks[idx][0]
                    const.LOGGER.warning(
                        "Failed to send broadcast notification to approver '%s': %s",
                        approver_id,
                        result,
                    )

        perf_duration = time.perf_counter() - perf_start
        const.LOGGER.debug(
            "PERF: broadcast_to_all_approvers() sent %d notifications in %.3fs",
            approver_count,
            perf_duration,
        )

    # =========================================================================
    # Notification Management
    # =========================================================================

    async def clear_notification_for_approvers(
        self,
        assignee_id: str,
        tag_type: str,
        item_id: str,
    ) -> None:
        """Clear a notification for all approvers of a assignee.

        Sends "clear_notification" message to each approver's notification service
        with the appropriate tag.

        Args:
            assignee_id: The internal ID of the Assignee Item (to find associated approvers)
            tag_type: Tag type constant (e.g., NOTIFY_TAG_TYPE_STATUS)
            item_id: The Chore/Reward Item ID (UUID) to include in the tag
        """
        # Build the tag for this item (multi-instance support: entry_id, item_id, assignee_id)
        notification_tag = self.build_notification_tag(
            tag_type, self.entry_id, item_id, assignee_id
        )

        const.LOGGER.debug(
            "Clearing notification with tag '%s' for assignee '%s'",
            notification_tag,
            assignee_id,
        )

        # Build clear tasks for all approvers associated with this assignee
        clear_tasks: list[tuple[str, Any]] = []

        for approver_id, approver_info in self.coordinator.approvers_data.items():
            associated_user_ids = approver_info.get(
                const.DATA_USER_ASSOCIATED_USER_IDS, []
            )
            if not isinstance(associated_user_ids, list):
                continue
            if assignee_id not in associated_user_ids:
                continue

            notify_service = approver_info.get(const.DATA_USER_MOBILE_NOTIFY_SERVICE)
            if not notify_service:
                continue

            # Strip "notify." prefix if present
            service_name = notify_service.removeprefix("notify.")

            service_data = {
                "message": "clear_notification",
                "data": {"tag": notification_tag},
            }
            coro = self.hass.services.async_call(
                "notify",
                service_name,
                service_data,
            )
            clear_tasks.append((approver_id, coro))

        # Execute all clears concurrently
        if clear_tasks:
            results = await asyncio.gather(
                *[coro for _, coro in clear_tasks],
                return_exceptions=True,
            )
            for idx, result in enumerate(results):
                if isinstance(result, Exception):
                    approver_id = clear_tasks[idx][0]
                    const.LOGGER.warning(
                        "Failed to clear notification for approver '%s': %s",
                        approver_id,
                        result,
                    )
        else:
            const.LOGGER.debug(
                "No approvers with notification service found for assignee '%s'",
                assignee_id,
            )

    async def clear_notification_for_assignee(
        self,
        assignee_id: str,
        tag: str | None = None,
    ) -> None:
        """Clear notifications for a specific assignee.

        Args:
            assignee_id: ID of the assignee to clear notifications for
            tag: Optional tag to clear specific notifications
        """
        assignee_info: AssigneeData | None = self.coordinator.assignees_data.get(
            assignee_id
        )
        if not assignee_info:
            const.LOGGER.debug(
                "Assignee '%s' not found, cannot clear notifications", assignee_id
            )
            return

        if not assignee_info.get(const.DATA_USER_MOBILE_NOTIFY_SERVICE):
            const.LOGGER.debug(
                "No notification service configured for assignee '%s'", assignee_id
            )
            return

        service_name = assignee_info[
            const.DATA_USER_MOBILE_NOTIFY_SERVICE
        ].removeprefix("notify.")

        service_data: dict[str, Any] = {
            "message": "clear_notification",
        }

        if tag:
            service_data["data"] = {"tag": tag}
            const.LOGGER.debug(
                "Clearing notification with tag '%s' for assignee '%s'",
                tag,
                assignee_id,
            )
        else:
            const.LOGGER.debug(
                "Clearing all notifications for assignee '%s'", assignee_id
            )

        try:
            await self.hass.services.async_call(
                "notify",
                service_name,
                service_data,
            )
        except Exception as ex:
            const.LOGGER.warning(
                "Failed to clear notification for assignee '%s': %s",
                assignee_id,
                ex,
            )

    async def remind_in_minutes(
        self,
        assignee_id: str,
        minutes: int,
        *,
        chore_id: str | None = None,
        reward_id: str | None = None,
    ) -> None:
        """Schedule a reminder notification after specified minutes.

        If a chore_id is provided, checks the chore's state before sending.
        If a reward_id is provided, checks whether that reward is still pending.
        """
        const.LOGGER.debug(
            "Scheduling reminder for Assignee ID '%s', Chore ID '%s', Reward ID '%s' in %d minutes",
            assignee_id,
            chore_id,
            reward_id,
            minutes,
        )
        # Use 5 seconds in test mode, convert minutes to seconds in production
        delay_seconds = 5 if self.coordinator._test_mode else (minutes * 60)
        await asyncio.sleep(delay_seconds)

        assignee_info: AssigneeData | None = self.coordinator.assignees_data.get(
            assignee_id
        )
        if not assignee_info:
            const.LOGGER.warning(
                "Assignee ID '%s' not found during reminder check",
                assignee_id,
            )
            return

        if chore_id:
            chore_info: ChoreData | None = self.coordinator.chores_data.get(chore_id)
            if not chore_info:
                const.LOGGER.warning(
                    "Chore ID '%s' not found during reminder check",
                    chore_id,
                )
                return

            # Check if reminders are enabled for this chore
            if not chore_info.get(
                const.DATA_CHORE_NOTIFY_DUE_REMINDER,
                const.DEFAULT_NOTIFY_DUE_REMINDER,
            ):
                const.LOGGER.debug(
                    "Reminders disabled for Chore ID '%s'. Skipping",
                    chore_id,
                )
                return

            # Get the per-assignee chore state
            assignee_info = self.coordinator.assignees_data.get(assignee_id)
            if not assignee_info:
                const.LOGGER.debug(
                    "Assignee ID '%s' not found in data. Skipping reminder",
                    assignee_id,
                )
                return
            assignee_chore_data = ChoreEngine.get_chore_data_for_assignee(
                assignee_info, chore_id
            )
            current_state = assignee_chore_data.get(const.DATA_USER_CHORE_DATA_STATE)

            # Only resend if still pending/overdue
            if current_state not in [
                const.CHORE_STATE_PENDING,
                const.CHORE_STATE_OVERDUE,
            ]:
                const.LOGGER.info(
                    "Chore ID '%s' for Assignee ID '%s' is in state '%s'. No reminder sent",
                    chore_id,
                    assignee_id,
                    current_state,
                )
                return

            # Build actions and send reminder
            actions = self.build_chore_actions(assignee_id, chore_id, self.entry_id)
            extra_data = self.build_extra_data(assignee_id, chore_id=chore_id)
            await self.notify_approvers_translated(
                assignee_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_REMINDER_APPROVER,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_REMINDER_APPROVER,
                message_data={
                    "chore_name": chore_info.get(
                        const.DATA_CHORE_NAME, const.DISPLAY_UNNAMED_CHORE
                    ),
                    "assignee_name": assignee_info.get(
                        const.DATA_USER_NAME, const.DISPLAY_UNNAMED_USER
                    ),
                },
                actions=actions,
                extra_data=extra_data,
                tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                tag_identifiers=(chore_id, assignee_id),
            )
            const.LOGGER.info(
                "Resent reminder for Chore ID '%s' for Assignee ID '%s'",
                chore_id,
                assignee_id,
            )

        elif reward_id:
            # Check if the reward is still pending
            reward_data = assignee_info.get(const.DATA_USER_REWARD_DATA, {}).get(
                reward_id, {}
            )
            pending_count = reward_data.get(
                const.DATA_USER_REWARD_DATA_PENDING_COUNT, 0
            )
            if pending_count <= 0:
                const.LOGGER.info(
                    "Reward ID '%s' is no longer pending for Assignee ID '%s'. No reminder sent",
                    reward_id,
                    assignee_id,
                )
                return

            # Build actions and send reminder
            actions = self.build_reward_actions(assignee_id, reward_id, self.entry_id)
            extra_data = self.build_extra_data(assignee_id, reward_id=reward_id)
            reward_info: RewardData = cast(
                "RewardData", self.coordinator.rewards_data.get(reward_id, {})
            )
            reward_name = reward_info.get(const.DATA_REWARD_NAME, "the reward")
            await self.notify_approvers_translated(
                assignee_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_REWARD_REMINDER_APPROVER,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_REWARD_REMINDER_APPROVER,
                message_data={
                    "reward_name": reward_name,
                    "assignee_name": assignee_info.get(
                        const.DATA_USER_NAME, "A assignee"
                    ),
                },
                actions=actions,
                extra_data=extra_data,
                tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                tag_identifiers=(reward_id, assignee_id),
            )
            const.LOGGER.info(
                "Resent reminder for Reward ID '%s' for Assignee ID '%s'",
                reward_id,
                assignee_id,
            )
        else:
            const.LOGGER.warning(
                "No Chore ID or Reward ID provided for reminder action"
            )

    # =========================================================================
    # Event Handlers (Event-Driven Notifications)
    # =========================================================================

    async def _handle_badge_earned(self, payload: dict[str, Any]) -> None:
        """Handle BADGE_EARNED event - send notifications to assignee and approvers.

        Args:
            payload: Event data containing assignee_id, badge_id, badge_name
        """
        assignee_id = payload.get("user_id", "")
        badge_id = payload.get("badge_id", "")
        badge_name = payload.get("badge_name", "Unknown Badge")
        assignee_name = payload.get("user_name", "")

        if not assignee_id:
            return

        if not assignee_name:
            const.LOGGER.warning(
                "BADGE_EARNED notification missing assignee_name in payload for assignee_id=%s",
                assignee_id,
            )
            # Fallback to lookup
            assignee_info = self.coordinator.assignees_data.get(assignee_id)
            if assignee_info:
                assignee_name = assignee_info.get(const.DATA_USER_NAME, "")
            if not assignee_name:
                return
        extra_data = {
            const.DATA_USER_ID: assignee_id,
            const.DATA_BADGE_ID: badge_id,
        }

        # Notify assignee
        await self.notify_assignee_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_BADGE_EARNED_ASSIGNEE,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_BADGE_EARNED_ASSIGNEE,
            message_data={"badge_name": badge_name},
            extra_data=extra_data,
        )

        # Notify approvers
        await self.notify_approvers_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_BADGE_EARNED_APPROVER,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_BADGE_EARNED_APPROVER,
            message_data={"assignee_name": assignee_name, "badge_name": badge_name},
            extra_data=extra_data,
        )

        const.LOGGER.debug(
            "NotificationManager: Sent badge earned notifications for assignee=%s, badge=%s",
            assignee_id,
            badge_name,
        )

    async def _handle_achievement_earned(self, payload: dict[str, Any]) -> None:
        """Handle ACHIEVEMENT_EARNED event - send notifications to assignee and approvers.

        Args:
            payload: Event data containing assignee_id, achievement_id, achievement_name
        """
        assignee_id = payload.get("user_id", "")
        achievement_id = payload.get("achievement_id", "")
        achievement_name = payload.get("achievement_name", "Unknown Achievement")
        assignee_name = payload.get("user_name", "")

        if not assignee_id:
            return

        if not assignee_name:
            const.LOGGER.warning(
                "ACHIEVEMENT_EARNED notification missing assignee_name in payload for assignee_id=%s",
                assignee_id,
            )
            # Fallback to lookup
            assignee_info = self.coordinator.assignees_data.get(assignee_id)
            if assignee_info:
                assignee_name = assignee_info.get(const.DATA_USER_NAME, "")
            if not assignee_name:
                return
        extra_data = {
            const.DATA_USER_ID: assignee_id,
            const.DATA_ACHIEVEMENT_ID: achievement_id,
        }

        # Notify assignee
        await self.notify_assignee_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_ACHIEVEMENT_EARNED_ASSIGNEE,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_ACHIEVEMENT_EARNED_ASSIGNEE,
            message_data={"achievement_name": achievement_name},
            extra_data=extra_data,
        )

        # Notify approvers
        await self.notify_approvers_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_ACHIEVEMENT_EARNED_APPROVER,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_ACHIEVEMENT_EARNED_APPROVER,
            message_data={
                "assignee_name": assignee_name,
                "achievement_name": achievement_name,
            },
            extra_data=extra_data,
        )

        const.LOGGER.debug(
            "NotificationManager: Sent achievement notifications for assignee=%s, achievement=%s",
            assignee_id,
            achievement_name,
        )

    async def _handle_challenge_completed(self, payload: dict[str, Any]) -> None:
        """Handle CHALLENGE_COMPLETED event - send notifications to assignee and approvers.

        Args:
            payload: Event data containing assignee_id, challenge_id, challenge_name
        """
        assignee_id = payload.get("user_id", "")
        challenge_id = payload.get("challenge_id", "")
        challenge_name = payload.get("challenge_name", "Unknown Challenge")
        assignee_name = payload.get("user_name", "")

        if not assignee_id:
            return

        if not assignee_name:
            const.LOGGER.warning(
                "CHALLENGE_COMPLETED notification missing assignee_name in payload for assignee_id=%s",
                assignee_id,
            )
            # Fallback to lookup
            assignee_info = self.coordinator.assignees_data.get(assignee_id)
            if assignee_info:
                assignee_name = assignee_info.get(const.DATA_USER_NAME, "")
            if not assignee_name:
                return
        extra_data = {
            const.DATA_USER_ID: assignee_id,
            const.DATA_CHALLENGE_ID: challenge_id,
        }

        # Notify assignee
        await self.notify_assignee_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_CHALLENGE_COMPLETED_ASSIGNEE,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHALLENGE_COMPLETED_ASSIGNEE,
            message_data={"challenge_name": challenge_name},
            extra_data=extra_data,
        )

        # Notify approvers
        await self.notify_approvers_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_CHALLENGE_COMPLETED_APPROVER,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHALLENGE_COMPLETED_APPROVER,
            message_data={
                "assignee_name": assignee_name,
                "challenge_name": challenge_name,
            },
            extra_data=extra_data,
        )

        const.LOGGER.debug(
            "NotificationManager: Sent challenge notifications for assignee=%s, challenge=%s",
            assignee_id,
            challenge_name,
        )

    async def _handle_chore_claimed(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_CLAIMED event - send notification to approvers for approval.

        This bridges ChoreManager events to the notification system.
        Notifications are NOT sent if auto_approve is enabled or notify_on_claim is disabled.

        Args:
            payload: Event data containing assignee_id, chore_id, and optional chore_name
        """
        assignee_id = payload.get("user_id", "")
        chore_id = payload.get("chore_id", "")

        if not assignee_id or not chore_id:
            const.LOGGER.warning(
                "CHORE_CLAIMED notification skipped: missing assignee_id or chore_id"
            )
            return

        chore_info = self.coordinator.chores_data.get(chore_id)
        if not chore_info:
            return

        # Skip notification if auto_approve is enabled
        if chore_info.get(
            const.DATA_CHORE_AUTO_APPROVE, const.DEFAULT_CHORE_AUTO_APPROVE
        ):
            return

        # Skip if notify_on_claim is disabled
        if not chore_info.get(
            const.DATA_CHORE_NOTIFY_ON_CLAIM, const.DEFAULT_NOTIFY_ON_CLAIM
        ):
            return

        chore_name = payload.get("chore_name") or chore_info.get(
            const.DATA_CHORE_NAME, ""
        )
        assignee_name = payload.get("user_name", "")
        if not assignee_name:
            const.LOGGER.warning(
                "CHORE_CLAIMED notification missing assignee_name in payload for assignee_id=%s",
                assignee_id,
            )
            # Fallback to lookup
            assignee_info = self.coordinator.assignees_data.get(assignee_id)
            if assignee_info:
                assignee_name = assignee_info.get(const.DATA_USER_NAME, "")
            if not assignee_name:
                return
        chore_points = chore_info.get(
            const.DATA_CHORE_DEFAULT_POINTS, const.DEFAULT_ZERO
        )

        # Count pending chores for aggregation
        pending_count = (
            self.coordinator.chore_manager.get_pending_chore_count_for_assignee(
                assignee_id
            )
        )

        # Build action buttons
        actions = self.build_chore_actions(assignee_id, chore_id, self.entry_id)
        extra_data = self.build_extra_data(assignee_id, chore_id=chore_id)

        if pending_count > 1:
            # Aggregated notification
            await self.notify_approvers_translated(
                assignee_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_PENDING_CHORES_APPROVER,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_PENDING_CHORES_APPROVER,
                message_data={
                    "assignee_name": assignee_name,
                    "count": pending_count,
                    "latest_chore": chore_name,
                    "points": int(chore_points),
                },
                actions=actions,
                extra_data=extra_data,
                tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                tag_identifiers=(chore_id, assignee_id),
            )
        else:
            # Single chore notification
            await self.notify_approvers_translated(
                assignee_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_CLAIMED_APPROVER,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_CLAIMED_APPROVER,
                message_data={
                    "assignee_name": assignee_name,
                    "chore_name": chore_name,
                },
                actions=actions,
                extra_data=extra_data,
                tag_type=const.NOTIFY_TAG_TYPE_STATUS,
                tag_identifiers=(chore_id, assignee_id),
            )

        # Note: Due-soon reminder tracking is already cleared by ChoreManager.claim_chore()
        # per Cross-Manager Directive 2 (Direct Writes are FORBIDDEN)

        # Auto-clear: Remove overdue and due window notifications for assignee
        # when they claim the chore (v0.5.0+ auto-clearing functionality)
        overdue_tag = self.build_notification_tag(
            const.NOTIFY_TAG_TYPE_OVERDUE, self.entry_id, chore_id, assignee_id
        )
        due_window_tag = self.build_notification_tag(
            const.NOTIFY_TAG_TYPE_DUE_WINDOW, self.entry_id, chore_id, assignee_id
        )

        await self.clear_notification_for_assignee(assignee_id, overdue_tag)
        await self.clear_notification_for_assignee(assignee_id, due_window_tag)

        const.LOGGER.debug(
            "NotificationManager: Sent chore claimed notification for assignee=%s, chore=%s",
            assignee_id,
            chore_name,
        )

    async def _handle_reward_claimed(self, payload: dict[str, Any]) -> None:
        """Handle REWARD_CLAIMED event - send notification to approvers for approval.

        Args:
            payload: Event data containing assignee_id, reward_id, reward_name, points, notif_id
        """
        assignee_id = payload.get("user_id", "")
        reward_id = payload.get("reward_id", "")
        reward_name = payload.get("reward_name", "Unknown Reward")
        points = payload.get("points", 0)
        notif_id = payload.get("notif_id", "")
        assignee_name = payload.get("user_name", "")

        if not assignee_id:
            return

        if not assignee_name:
            const.LOGGER.warning(
                "REWARD_CLAIMED notification missing assignee_name in payload for assignee_id=%s",
                assignee_id,
            )
            # Fallback to lookup
            assignee_info = self.coordinator.assignees_data.get(assignee_id)
            if assignee_info:
                assignee_name = assignee_info.get(const.DATA_USER_NAME, "")
            if not assignee_name:
                return

        # Build actions for approvers
        actions = self.build_reward_actions(
            assignee_id, reward_id, self.entry_id, notif_id
        )
        extra_data = self.build_extra_data(
            assignee_id, reward_id=reward_id, notif_id=notif_id
        )

        # Notify approvers
        await self.notify_approvers_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_REWARD_CLAIMED_APPROVER,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_REWARD_CLAIMED_APPROVER,
            message_data={
                "assignee_name": assignee_name,
                "reward_name": reward_name,
                "points": points,
            },
            actions=actions,
            extra_data=extra_data,
            tag_type=const.NOTIFY_TAG_TYPE_STATUS,
            tag_identifiers=(reward_id, assignee_id),
        )

        const.LOGGER.debug(
            "NotificationManager: Sent reward claimed notification for assignee=%s, reward=%s",
            assignee_id,
            reward_name,
        )

    async def _handle_chore_claim_undone(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_CLAIM_UNDONE event - clear approver claim notifications.

        Args:
            payload: Event data containing assignee_id and chore_id
        """
        assignee_id = payload.get("user_id", "")
        chore_id = payload.get("chore_id", "")

        if not assignee_id or not chore_id:
            return

        await self.clear_notification_for_approvers(
            assignee_id,
            const.NOTIFY_TAG_TYPE_STATUS,
            chore_id,
        )

        const.LOGGER.debug(
            "NotificationManager: Cleared chore claim notifications for assignee=%s, chore=%s",
            assignee_id,
            chore_id,
        )

    async def _handle_reward_claim_undone(self, payload: dict[str, Any]) -> None:
        """Handle REWARD_CLAIM_UNDONE event - clear approver claim notifications.

        Args:
            payload: Event data containing assignee_id and reward_id
        """
        assignee_id = payload.get("user_id", "")
        reward_id = payload.get("reward_id", "")

        if not assignee_id or not reward_id:
            return

        await self.clear_notification_for_approvers(
            assignee_id,
            const.NOTIFY_TAG_TYPE_STATUS,
            reward_id,
        )

        const.LOGGER.debug(
            "NotificationManager: Cleared reward claim notifications for assignee=%s, reward=%s",
            assignee_id,
            reward_id,
        )

    async def _handle_reward_approved(self, payload: dict[str, Any]) -> None:
        """Handle REWARD_APPROVED event - send notification to assignee.

        Args:
            payload: Event data containing assignee_id, reward_id, reward_name
        """
        assignee_id = payload.get("user_id", "")
        reward_id = payload.get("reward_id", "")
        reward_name = payload.get("reward_name", "Unknown Reward")

        if not assignee_id:
            return

        extra_data = {
            const.DATA_USER_ID: assignee_id,
            const.DATA_REWARD_ID: reward_id,
        }

        # Notify assignee
        await self.notify_assignee_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_REWARD_APPROVED_ASSIGNEE,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_REWARD_APPROVED_ASSIGNEE,
            message_data={"reward_name": reward_name},
            extra_data=extra_data,
        )

        # Clear the original claim notification from approvers' devices
        await self.clear_notification_for_approvers(
            assignee_id,
            const.NOTIFY_TAG_TYPE_STATUS,
            reward_id,
        )

        const.LOGGER.debug(
            "NotificationManager: Sent reward approved notification for assignee=%s, reward=%s",
            assignee_id,
            reward_name,
        )

    async def _handle_reward_disapproved(self, payload: dict[str, Any]) -> None:
        """Handle REWARD_DISAPPROVED event - send notification to assignee.

        Args:
            payload: Event data containing assignee_id, reward_id, reward_name
        """
        assignee_id = payload.get("user_id", "")
        reward_id = payload.get("reward_id", "")
        reward_name = payload.get("reward_name", "Unknown Reward")

        if not assignee_id:
            return

        extra_data = {
            const.DATA_USER_ID: assignee_id,
            const.DATA_REWARD_ID: reward_id,
        }

        # Notify assignee
        await self.notify_assignee_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_REWARD_DISAPPROVED_ASSIGNEE,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_REWARD_DISAPPROVED_ASSIGNEE,
            message_data={"reward_name": reward_name},
            extra_data=extra_data,
        )

        # Clear the original claim notification from approvers' devices
        await self.clear_notification_for_approvers(
            assignee_id,
            const.NOTIFY_TAG_TYPE_STATUS,
            reward_id,
        )

        const.LOGGER.debug(
            "NotificationManager: Sent reward disapproved notification for assignee=%s, reward=%s",
            assignee_id,
            reward_name,
        )

    async def _handle_chore_disapproved(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_DISAPPROVED event - send notification to assignee.

        Args:
            payload: Event data containing assignee_id, chore_id, chore_name
        """
        assignee_id = payload.get("user_id", "")
        chore_id = payload.get("chore_id", "")
        chore_name = payload.get("chore_name", "Unknown Chore")

        if not assignee_id:
            return

        extra_data = {
            const.DATA_USER_ID: assignee_id,
            const.DATA_CHORE_ID: chore_id,
        }

        # Notify assignee
        await self.notify_assignee_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_DISAPPROVED_ASSIGNEE,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_DISAPPROVED_ASSIGNEE,
            message_data={"chore_name": chore_name},
            extra_data=extra_data,
        )

        # Clear the original claim notification from approvers' devices
        await self.clear_notification_for_approvers(
            assignee_id,
            const.NOTIFY_TAG_TYPE_STATUS,
            chore_id,
        )

        const.LOGGER.debug(
            "NotificationManager: Sent chore disapproved notification for assignee=%s, chore=%s",
            assignee_id,
            chore_name,
        )

    async def _handle_chore_approved(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_APPROVED event - notify assignee and clear pending notifications.

        Sends approval notification to assignee if notify_on_approval is enabled.
        Clears both approver claim notifications and assignee overdue notifications.

        Args:
            payload: Event data containing assignee_id, chore_id, chore_name, points_awarded
        """
        assignee_id = payload.get("user_id", "")
        chore_id = payload.get("chore_id", "")
        chore_name = payload.get("chore_name", "Unknown Chore")
        points = payload.get(
            "points_awarded", 0
        )  # Use points_awarded from ChoreManager
        notify_assignee = bool(payload.get("notify_assignee", True))

        if not assignee_id or not chore_id:
            return

        # Check if approval notifications are enabled for this chore
        chore_info: ChoreData | None = self.coordinator.chores_data.get(chore_id)
        if (
            notify_assignee
            and chore_info
            and chore_info.get(
                const.DATA_CHORE_NOTIFY_ON_APPROVAL,
                const.DEFAULT_NOTIFY_ON_APPROVAL,
            )
        ):
            # Notify assignee of approval
            await self.notify_assignee_translated(
                assignee_id,
                title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_APPROVED_ASSIGNEE,
                message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_APPROVED_ASSIGNEE,
                message_data={
                    "chore_name": chore_name,
                    "points": points,
                },
            )

        # Clear claim notification for approvers
        await self.clear_notification_for_approvers(
            assignee_id,
            const.NOTIFY_TAG_TYPE_STATUS,
            chore_id,
        )

        # Clear overdue/due window notifications for assignee
        overdue_tag = self.build_notification_tag(
            const.NOTIFY_TAG_TYPE_OVERDUE, self.entry_id, chore_id, assignee_id
        )
        due_window_tag = self.build_notification_tag(
            const.NOTIFY_TAG_TYPE_DUE_WINDOW, self.entry_id, chore_id, assignee_id
        )

        await self.clear_notification_for_assignee(assignee_id, overdue_tag)
        await self.clear_notification_for_assignee(assignee_id, due_window_tag)

        const.LOGGER.debug(
            "NotificationManager: Cleared notifications for approved chore=%s, assignee=%s",
            chore_name,
            assignee_id,
        )

    async def _handle_bonus_applied(self, payload: dict[str, Any]) -> None:
        """Handle BONUS_APPLIED event - send notification to assignee.

        Args:
            payload: Event data containing assignee_id, bonus_id, bonus_name, points
        """
        assignee_id = payload.get("user_id", "")
        bonus_id = payload.get("bonus_id", "")
        bonus_name = payload.get("bonus_name", "Unknown Bonus")
        points = payload.get("points", 0)

        if not assignee_id:
            return

        extra_data = {
            const.DATA_USER_ID: assignee_id,
            const.DATA_BONUS_ID: bonus_id,
        }

        # Notify assignee
        await self.notify_assignee_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_BONUS_APPLIED_ASSIGNEE,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_BONUS_APPLIED_ASSIGNEE,
            message_data={"bonus_name": bonus_name, "points": points},
            extra_data=extra_data,
        )

        const.LOGGER.debug(
            "NotificationManager: Sent bonus applied notification for assignee=%s, bonus=%s",
            assignee_id,
            bonus_name,
        )

    async def _handle_penalty_applied(self, payload: dict[str, Any]) -> None:
        """Handle PENALTY_APPLIED event - send notification to assignee.

        Args:
            payload: Event data containing assignee_id, penalty_id, penalty_name, points
        """
        assignee_id = payload.get("user_id", "")
        penalty_id = payload.get("penalty_id", "")
        penalty_name = payload.get("penalty_name", "Unknown Penalty")
        points = payload.get("points", 0)

        if not assignee_id:
            return

        extra_data = {
            const.DATA_USER_ID: assignee_id,
            const.DATA_PENALTY_ID: penalty_id,
        }

        # Notify assignee
        await self.notify_assignee_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_PENALTY_APPLIED_ASSIGNEE,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_PENALTY_APPLIED_ASSIGNEE,
            message_data={"penalty_name": penalty_name, "points": points},
            extra_data=extra_data,
        )

        const.LOGGER.debug(
            "NotificationManager: Sent penalty applied notification for assignee=%s, penalty=%s",
            assignee_id,
            penalty_name,
        )

    async def _handle_multiplier_changed(self, payload: dict[str, Any]) -> None:
        """Handle points multiplier changes - notify assignee and approvers.

        Args:
            payload: Event data containing assignee_id, old_multiplier, and new_multiplier
        """
        assignee_id = payload.get("user_id", "")
        old_multiplier = payload.get("old_multiplier")
        new_multiplier = payload.get("new_multiplier", payload.get("multiplier"))

        if not assignee_id or old_multiplier is None or new_multiplier is None:
            return

        old_value = float(old_multiplier)
        new_value = float(new_multiplier)

        if old_value == new_value:
            const.LOGGER.debug(
                "NotificationManager: Skipping multiplier notification (unchanged) for assignee=%s",
                assignee_id,
            )
            return

        assignee_name = ""
        assignee_info = self.coordinator.assignees_data.get(assignee_id)
        if assignee_info:
            assignee_name = assignee_info.get(const.DATA_USER_NAME, "")
        if not assignee_name:
            return

        message_data = {
            "old_multiplier": old_value,
            "new_multiplier": new_value,
        }

        await self.notify_assignee_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_MULTIPLIER_CHANGED_ASSIGNEE,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_MULTIPLIER_CHANGED_ASSIGNEE,
            message_data=message_data,
        )

        await self.notify_approvers_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_MULTIPLIER_CHANGED_APPROVER,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_MULTIPLIER_CHANGED_APPROVER,
            message_data={
                "assignee_name": assignee_name,
                **message_data,
            },
        )

        const.LOGGER.debug(
            "NotificationManager: Sent multiplier change notifications for assignee=%s (%s -> %s)",
            assignee_id,
            old_value,
            new_value,
        )

    async def _handle_chore_due_window(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_DUE_WINDOW event - notify assignee when chore enters due window (v0.6.0+).

        Triggered when chore transitions from PENDING → DUE state.
        Uses Schedule-Lock pattern to prevent duplicate notifications within same period.

        Args:
            payload: Event data containing assignee_id, chore_id, chore_name,
                     hours (remaining), points, due_date
        """
        assignee_id = payload.get("user_id", "")
        chore_id = payload.get("chore_id", "")
        chore_name = payload.get("chore_name", "Unknown Chore")
        hours = payload.get("hours", 0)
        points = payload.get("points", 0)

        if not assignee_id or not chore_id:
            return

        # Phase 3 Step 9: Filter rotation chores - only notify turn-holder
        chore_info: ChoreData | None = self.coordinator.chores_data.get(chore_id)
        if chore_info and ChoreEngine.is_rotation_mode(chore_info):
            current_turn_assignee = chore_info.get(
                const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID
            )
            if current_turn_assignee != assignee_id:
                const.LOGGER.debug(
                    "NotificationManager: Skipping due window notification for rotation chore=%s "
                    "(not_my_turn: current turn is assignee=%s, not %s)",
                    chore_name,
                    current_turn_assignee,
                    assignee_id,
                )
                return

        # Schedule-Lock: Check if already notified this period
        if not self._should_send_chore_notification(assignee_id, chore_id, "due_start"):
            const.LOGGER.debug(
                "NotificationManager: Suppressing due start notification (Schedule-Lock) "
                "for chore=%s to assignee=%s",
                chore_name,
                assignee_id,
            )
            return

        # Notify assignee with claim action (using tag for smart replacement)
        await self.notify_assignee_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_DUE_WINDOW_ASSIGNEE,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_WINDOW_ASSIGNEE,
            message_data={
                "chore_name": chore_name,
                "hours": hours,
                "points": points,
            },
            actions=self.build_claim_action(assignee_id, chore_id, self.entry_id),
            tag_type=const.NOTIFY_TAG_TYPE_STATUS,
            tag_identifiers=(chore_id, assignee_id),
        )

        # Record notification sent (persists to storage)
        self._record_chore_notification_sent(assignee_id, chore_id, "due_start")

        const.LOGGER.debug(
            "NotificationManager: Sent due start notification for chore=%s to assignee=%s (%d hrs)",
            chore_name,
            assignee_id,
            hours,
        )

    async def _handle_chore_due_reminder(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_DUE_REMINDER event - send reminder to assignee with claim button (v0.6.0+).

        Renamed from _handle_chore_due_soon to clarify purpose.
        Uses configurable per-chore `due_reminder_offset` timing.
        Uses Schedule-Lock pattern to prevent duplicate notifications within same period.

        Args:
            payload: Event data containing assignee_id, chore_id, chore_name, minutes, points, due_date
        """
        assignee_id = payload.get("user_id", "")
        chore_id = payload.get("chore_id", "")
        chore_name = payload.get("chore_name", "Unknown Chore")
        minutes = payload.get("minutes", 0)
        points = payload.get("points", 0)

        if not assignee_id or not chore_id:
            return

        # Phase 3 Step 9: Filter rotation chores - only notify turn-holder
        chore_info: ChoreData | None = self.coordinator.chores_data.get(chore_id)
        if chore_info and ChoreEngine.is_rotation_mode(chore_info):
            current_turn_assignee = chore_info.get(
                const.DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID
            )
            if current_turn_assignee != assignee_id:
                const.LOGGER.debug(
                    "NotificationManager: Skipping due reminder notification for rotation chore=%s "
                    "(not_my_turn: current turn is assignee=%s, not %s)",
                    chore_name,
                    current_turn_assignee,
                    assignee_id,
                )
                return

        # Schedule-Lock: Check if already notified this period
        if not self._should_send_chore_notification(
            assignee_id, chore_id, "due_reminder"
        ):
            const.LOGGER.debug(
                "NotificationManager: Suppressing due-reminder notification (Schedule-Lock) "
                "for chore=%s to assignee=%s",
                chore_name,
                assignee_id,
            )
            return

        # Notify assignee with claim action
        await self.notify_assignee_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_DUE_REMINDER_ASSIGNEE,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_DUE_REMINDER_ASSIGNEE,
            message_data={
                "chore_name": chore_name,
                "minutes": minutes,
                "points": points,
            },
            actions=self.build_claim_action(assignee_id, chore_id, self.entry_id),
        )

        # Record notification sent (persists to storage)
        self._record_chore_notification_sent(assignee_id, chore_id, "due_reminder")

        const.LOGGER.debug(
            "NotificationManager: Sent due-reminder notification for chore=%s to assignee=%s (%d min)",
            chore_name,
            assignee_id,
            minutes,
        )

    async def _handle_chore_overdue(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_OVERDUE event - notify assignee and approvers with actions.

        For rotation chores, notifies ALL assigned assignees (steal mechanic).
        For regular chores, notifies only the target assignee.
        Uses Schedule-Lock pattern to prevent duplicate notifications within same period.

        Args:
            payload: Event data containing assignee_id, chore_id, chore_name, due_date
        """
        assignee_id = payload.get("user_id", "")
        chore_id = payload.get("chore_id", "")
        chore_name = payload.get("chore_name", "Unknown Chore")
        due_date = payload.get("due_date", "")

        if not assignee_id or not chore_id:
            return

        # Check if overdue notifications are enabled for this chore
        chore_info: ChoreData | None = self.coordinator.chores_data.get(chore_id)
        if not chore_info:
            const.LOGGER.warning(
                "Chore ID '%s' not found during overdue notification check",
                chore_id,
            )
            return

        if not chore_info.get(
            const.DATA_CHORE_NOTIFY_ON_OVERDUE,
            const.DEFAULT_NOTIFY_ON_OVERDUE,
        ):
            const.LOGGER.debug(
                "Overdue notifications disabled for Chore ID '%s'. Skipping",
                chore_id,
            )
            return

        # For rotation chores, notify ALL assigned assignees (steal mechanic)
        # For regular chores, notify only the original assignee
        if chore_info and ChoreEngine.is_rotation_mode(chore_info):
            assigned_assignees = chore_info.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])
            const.LOGGER.debug(
                "NotificationManager: Rotation chore overdue - notifying all %d assigned assignees",
                len(assigned_assignees),
            )

            # Send to all assigned assignees
            for target_assignee_id in assigned_assignees:
                await self._send_overdue_notification_to_assignee(
                    target_assignee_id, chore_id, chore_name, due_date, payload
                )
        else:
            # Regular chore - send to original assignee only
            await self._send_overdue_notification_to_assignee(
                assignee_id, chore_id, chore_name, due_date, payload
            )

    async def _send_overdue_notification_to_assignee(
        self,
        target_assignee_id: str,
        chore_id: str,
        chore_name: str,
        due_date: str,
        payload: dict[str, Any],
    ) -> None:
        """Send overdue notification to a specific assignee with Schedule-Lock protection."""
        # Schedule-Lock: Check if already notified this period
        if not self._should_send_chore_notification(
            target_assignee_id, chore_id, "overdue"
        ):
            const.LOGGER.debug(
                "NotificationManager: Suppressing overdue notification (Schedule-Lock) "
                "for chore=%s to assignee=%s",
                chore_name,
                target_assignee_id,
            )
            return

        # Get assignee's language for datetime formatting
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(target_assignee_id, {})
        )
        assignee_language = assignee_info.get(
            const.DATA_USER_DASHBOARD_LANGUAGE, self.hass.config.language
        )

        # Convert UTC ISO string to local datetime for display
        due_dt = dt_to_utc(due_date) if due_date else None
        formatted_due_date = dt_format_short(due_dt, language=assignee_language)

        # Get assignee's name for notification message
        assignee_name = assignee_info.get(const.DATA_USER_NAME, "Unknown Assignee")

        # Get chore points for message
        chore_info: ChoreData | None = self.coordinator.chores_data.get(chore_id)
        chore_points = (
            chore_info.get(const.DATA_CHORE_DEFAULT_POINTS, 0) if chore_info else 0
        )

        # Notify assignee with claim action (using tag for smart replacement)
        await self.notify_assignee_translated(
            target_assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_OVERDUE_ASSIGNEE,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_OVERDUE_ASSIGNEE,
            message_data={
                "assignee_name": assignee_name,
                "chore_name": chore_name,
                "due_date": formatted_due_date,
                "points": chore_points,
            },
            actions=self.build_claim_action(
                target_assignee_id, chore_id, self.entry_id
            ),
            tag_type=const.NOTIFY_TAG_TYPE_STATUS,
            tag_identifiers=(chore_id, target_assignee_id),
        )

        # Build approver actions
        approver_actions: list[dict[str, str]] = []
        approver_actions.extend(
            self.build_complete_action(target_assignee_id, chore_id, self.entry_id)
        )
        approver_actions.extend(
            self.build_skip_action(target_assignee_id, chore_id, self.entry_id)
        )
        approver_actions.extend(
            self.build_remind_action(target_assignee_id, chore_id, self.entry_id)
        )

        # Get assignee name from payload (ChoreManager always provides it)
        original_assignee_name = payload.get("user_name", "")
        if not original_assignee_name:
            const.LOGGER.error(
                "CHORE_OVERDUE notification missing assignee_name in payload for target_assignee=%s, chore_id=%s",
                target_assignee_id,
                chore_id,
            )
            return

        # Get approver's language for datetime formatting
        # Note: notify_approvers_translated handles per-approver language internally,
        # but we format with system default here since the message_data is shared
        approver_language = self.hass.config.language
        formatted_due_date_approver = dt_format_short(
            due_dt, language=approver_language
        )

        await self.notify_approvers_translated(
            target_assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_OVERDUE_APPROVER,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_OVERDUE_APPROVER,
            message_data={
                "assignee_name": original_assignee_name,  # Use original assignee name from payload
                "chore_name": chore_name,
                "due_date": formatted_due_date_approver,
            },
            actions=approver_actions,
            tag_type=const.NOTIFY_TAG_TYPE_STATUS,
            tag_identifiers=(chore_id, target_assignee_id),
        )

        # Record notification sent (persists to storage)
        self._record_chore_notification_sent(target_assignee_id, chore_id, "overdue")

        const.LOGGER.debug(
            "NotificationManager: Sent overdue notification for chore=%s to assignee=%s and approvers",
            chore_name,
            target_assignee_id,
        )

    async def _handle_chore_missed(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_MISSED event - notify assignee and approvers when chore locked due to missed.

        Phase 3 Step 9 (v0.5.0): Missed lock notifications
        Triggered when rotation chore with at_due_date_mark_missed_and_lock reaches due date.
        Uses overdue notification flag (notify_on_overdue) to gate both overdue and missed.

        Args:
            payload: Event data containing assignee_id, chore_id, chore_name, due_date
        """
        assignee_id = payload.get("user_id", "")
        chore_id = payload.get("chore_id", "")
        chore_name = payload.get("chore_name", "Unknown Chore")
        due_date = payload.get("due_date", "")

        if not assignee_id or not chore_id:
            return

        # Check if overdue notifications are enabled (gates both overdue and missed)
        chore_info: ChoreData | None = self.coordinator.chores_data.get(chore_id)
        if not chore_info:
            const.LOGGER.warning(
                "Chore ID '%s' not found during missed notification check",
                chore_id,
            )
            return

        if not chore_info.get(
            const.DATA_CHORE_NOTIFY_ON_OVERDUE,
            const.DEFAULT_NOTIFY_ON_OVERDUE,
        ):
            const.LOGGER.debug(
                "Missed notifications disabled for Chore ID '%s' (notify_on_overdue=False). Skipping",
                chore_id,
            )
            return

        # Schedule-Lock: Check if already notified this period
        if not self._should_send_chore_notification(assignee_id, chore_id, "missed"):
            const.LOGGER.debug(
                "NotificationManager: Suppressing missed notification (Schedule-Lock) "
                "for chore=%s to assignee=%s",
                chore_name,
                assignee_id,
            )
            return

        # Get assignee's language for datetime formatting
        assignee_info: AssigneeData = cast(
            "AssigneeData", self.coordinator.assignees_data.get(assignee_id, {})
        )
        assignee_language = assignee_info.get(
            const.DATA_USER_DASHBOARD_LANGUAGE, self.hass.config.language
        )

        # Convert UTC ISO string to local datetime for display
        due_dt = dt_to_utc(due_date) if due_date else None
        formatted_due_date = dt_format_short(due_dt, language=assignee_language)

        # Get assignee's name for notification message
        assignee_name = assignee_info.get(const.DATA_USER_NAME, "Unknown Assignee")

        # Notify assignee (NO claim action - chore is locked)
        await self.notify_assignee_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_MISSED_ASSIGNEE,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_MISSED_ASSIGNEE,
            message_data={
                "assignee_name": assignee_name,
                "chore_name": chore_name,
                "due_date": formatted_due_date,
            },
            actions=None,  # No actions - chore is locked
            tag_type=const.NOTIFY_TAG_TYPE_STATUS,
            tag_identifiers=(chore_id, assignee_id),
        )

        # Build approver actions (complete/skip still available for approvers)
        approver_actions: list[dict[str, str]] = []
        approver_actions.extend(
            self.build_complete_action(assignee_id, chore_id, self.entry_id)
        )
        approver_actions.extend(
            self.build_skip_action(assignee_id, chore_id, self.entry_id)
        )

        # Get assignee name from payload (ChoreManager always provides it)
        assignee_name_payload = payload.get("user_name", "")
        if not assignee_name_payload:
            const.LOGGER.error(
                "CHORE_MISSED notification missing assignee_name in payload for assignee_id=%s, chore_id=%s",
                assignee_id,
                chore_id,
            )
            return

        # Format due date for approvers
        approver_language = self.hass.config.language
        formatted_due_date_approver = dt_format_short(
            due_dt, language=approver_language
        )

        await self.notify_approvers_translated(
            assignee_id,
            title_key=const.TRANS_KEY_NOTIF_TITLE_CHORE_MISSED_ASSIGNEE,
            message_key=const.TRANS_KEY_NOTIF_MESSAGE_CHORE_MISSED_ASSIGNEE,
            message_data={
                "assignee_name": assignee_name_payload,
                "chore_name": chore_name,
                "due_date": formatted_due_date_approver,
            },
            actions=approver_actions,
            tag_type=const.NOTIFY_TAG_TYPE_STATUS,
            tag_identifiers=(chore_id, assignee_id),
        )

        # Record notification sent (persists to storage)
        self._record_chore_notification_sent(assignee_id, chore_id, "missed")

        const.LOGGER.debug(
            "NotificationManager: Sent missed notification for chore=%s to assignee=%s and approvers",
            chore_name,
            assignee_id,
        )

    # =========================================================================
    # DELETED Event Handlers - Clear Ghost Notifications (Phase 7.3.7)
    # =========================================================================

    async def _handle_chore_deleted(self, payload: dict[str, Any]) -> None:
        """Handle CHORE_DELETED event - clear any pending notifications for deleted chore.

        When a chore is deleted, we need to clear notifications that reference it:
        - Pending approval notifications sent to approvers
        - Due soon / overdue reminders
        - Notification records in our DATA_NOTIFICATIONS bucket (Schedule-Lock janitor)

        Args:
            payload: Event data containing chore_id, chore_name, and optionally
                     assigned_user_ids (list of user IDs that had this chore assigned)
        """
        chore_id = payload.get("chore_id", "")
        chore_name = payload.get("chore_name", "Unknown")
        assigned_assignees = payload.get(const.DATA_CHORE_ASSIGNED_USER_IDS, [])

        if not chore_id:
            const.LOGGER.warning(
                "CHORE_DELETED notification cleanup skipped: missing chore_id"
            )
            return

        const.LOGGER.debug(
            "Clearing notifications for deleted chore '%s' (id=%s), assigned_user_ids=%s",
            chore_name,
            chore_id,
            assigned_assignees,
        )

        # Clean up notification records in our bucket (Schedule-Lock janitor)
        self._cleanup_chore_notifications(chore_id)

        # Clear notifications for each assignee that had this chore assigned
        for assignee_id in assigned_assignees:
            # Clear STATUS tag notifications (pending approvals, due/overdue)
            await self.clear_notification_for_approvers(
                assignee_id,
                const.NOTIFY_TAG_TYPE_STATUS,
                chore_id,
            )

    async def _handle_reward_deleted(self, payload: dict[str, Any]) -> None:
        """Handle REWARD_DELETED event - clear any pending notifications for deleted reward.

        When a reward is deleted, we need to clear notifications that reference it:
        - Pending reward claim notifications sent to approvers
        - Reward approval/disapproval notifications

        Args:
            payload: Event data containing reward_id, reward_name
        """
        reward_id = payload.get("reward_id", "")
        reward_name = payload.get("reward_name", "Unknown")

        if not reward_id:
            const.LOGGER.warning(
                "REWARD_DELETED notification cleanup skipped: missing reward_id"
            )
            return

        const.LOGGER.debug(
            "Clearing notifications for deleted reward '%s' (id=%s)",
            reward_name,
            reward_id,
        )

        # Clear REWARDS tag notifications for all assignees
        # Rewards can be claimed by any assignee, so we iterate through all assignees
        for assignee_id in self.coordinator.assignees_data:
            await self.clear_notification_for_approvers(
                assignee_id,
                const.NOTIFY_TAG_TYPE_REWARDS,
                reward_id,
            )

    async def _handle_assignee_deleted(self, payload: dict[str, Any]) -> None:
        """Handle KID_DELETED event - clear all notifications involving deleted assignee.

        When a assignee is deleted, we need to clear all notifications that reference them:
        - All pending approval notifications for this assignee's chores
        - All reward claim notifications involving this assignee
        - Any status/system notifications for this assignee
        - Notification records in our DATA_NOTIFICATIONS bucket (Schedule-Lock janitor)

        Note: This is a best-effort cleanup. Some notifications may have already
        been dismissed or may not have used tags. The system is designed to be
        resilient to orphaned notifications.

        Args:
            payload: Event data containing user_id and capability snapshot flags
        """
        if not payload.get(const.DATA_USER_CAN_BE_ASSIGNED, False):
            return

        assignee_id = payload.get(const.DATA_USER_ID, "")
        assignee_name = payload.get(const.DATA_USER_NAME, "Unknown")

        if not assignee_id:
            const.LOGGER.warning(
                "KID_DELETED notification cleanup skipped: missing assignee_id"
            )
            return

        # Clean up notification records in our bucket (Schedule-Lock janitor)
        self._cleanup_assignee_chore_notifications(assignee_id)

        const.LOGGER.debug(
            "Clearing all notifications for deleted assignee '%s' (id=%s)",
            assignee_name,
            assignee_id,
        )

        # Clear all notification tag types for this assignee
        # We use assignee_id as the item_id since we want to clear all notifications
        # that have this assignee_id in their tag
        for tag_type in (
            const.NOTIFY_TAG_TYPE_STATUS,
            const.NOTIFY_TAG_TYPE_REWARDS,
            const.NOTIFY_TAG_TYPE_PENDING,
            const.NOTIFY_TAG_TYPE_SYSTEM,
        ):
            await self.clear_notification_for_approvers(
                assignee_id,
                tag_type,
                assignee_id,  # Use assignee_id as item_id to match tags like "status-assigneeid-assigneeid"
            )
