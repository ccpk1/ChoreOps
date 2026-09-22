"""Unit tests for notification helper functions.

APPROVED EXCEPTION - Direct Function Calls (Rule 2 Approach B):
This test file uses direct function calls instead of service-based testing because
it tests pure helper functions with no Home Assistant dependencies. These functions:
- Have no hass parameter
- Operate on simple string inputs/outputs
- Are internal utilities called by other code (no button/UI equivalents)
- Qualify as "Core business logic not exposed through UI entities"

Approved by: Phase 5 plan in NOTIFICATION_REFACTOR_IN-PROCESS.md
Permission granted: Testing pure helper functions added in Phases 1 and 3

Tests the following functions:
- NotificationManager.build_chore_actions(): Builds 3 action dicts for chore notifications
- NotificationManager.build_reward_actions(): Builds 3 action dicts for reward notifications
- ParsedAction: Dataclass with is_chore/is_reward/is_reminder properties

These tests do NOT duplicate test_workflow_notifications.py which tests the
full notification WORKFLOW (sending notifications, action button presses, etc.).
"""

from types import SimpleNamespace
from typing import Any

import pytest

from custom_components.choreops import const
from custom_components.choreops.data_builders import build_chore, build_user_profile
from custom_components.choreops.helpers import translation_helpers as th
from custom_components.choreops.managers import NotificationManager
from custom_components.choreops.notification_action_handler import (
    ParsedAction,
    parse_notification_action,
)
from tests.helpers import (
    ACTION_APPROVE_CHORE,
    ACTION_APPROVE_REWARD,
    ACTION_DISAPPROVE_CHORE,
    ACTION_DISAPPROVE_REWARD,
    ACTION_REMIND_30,
    DATA_CHORE_ID,
    DATA_REWARD_ID,
    DATA_USER_ID,
    NOTIFY_ACTION,
    NOTIFY_NOTIFICATION_ID,
    NOTIFY_TITLE,
    TRANS_KEY_NOTIF_ACTION_APPROVE,
    TRANS_KEY_NOTIF_ACTION_DISAPPROVE,
    TRANS_KEY_NOTIF_ACTION_REMIND_30,
)

# Convenience aliases for static methods
build_chore_actions = NotificationManager.build_chore_actions
build_reward_actions = NotificationManager.build_reward_actions
build_extra_data = NotificationManager.build_extra_data
build_notification_tag = NotificationManager.build_notification_tag
apply_recipient_notification_options = (
    NotificationManager._apply_recipient_notification_options
)


class TestConvertNotificationKey:
    """Tests for _convert_notification_key()."""

    def test_strips_canonical_notification_prefixes(self) -> None:
        """Canonical notification_* keys should map to JSON notification keys."""
        manager = object.__new__(NotificationManager)

        assert (
            manager._convert_notification_key("notification_title_data_reset")
            == "data_reset"
        )
        assert (
            manager._convert_notification_key("notification_message_data_reset_global")
            == "data_reset_global"
        )


# =============================================================================
# build_chore_actions() Tests
# =============================================================================


class TestBuildChoreActions:
    """Tests for build_chore_actions() function."""

    def test_returns_list_of_three_actions(self) -> None:
        """Test that function returns exactly 3 action dictionaries."""
        actions = build_chore_actions("assignee-123", "chore-456", "entry123")

        assert isinstance(actions, list)
        assert len(actions) == 3

    def test_action_format_structure(self) -> None:
        """Test that each action has required 'action' and 'title' keys."""
        actions = build_chore_actions("assignee-123", "chore-456", "entry123")

        for action_dict in actions:
            assert NOTIFY_ACTION in action_dict
            assert NOTIFY_TITLE in action_dict
            assert isinstance(action_dict[NOTIFY_ACTION], str)
            assert isinstance(action_dict[NOTIFY_TITLE], str)

    def test_approve_action_pipe_format(self) -> None:
        """Test approve action uses pipe-separated format: ACTION|entry_id|assignee_id|chore_id."""
        actions = build_chore_actions("assignee-123", "chore-456", "entry123")
        approve_action = actions[0]

        expected = f"{ACTION_APPROVE_CHORE}|entry123|assignee-123|chore-456"
        assert approve_action[NOTIFY_ACTION] == expected
        assert approve_action[NOTIFY_TITLE] == TRANS_KEY_NOTIF_ACTION_APPROVE

    def test_disapprove_action_pipe_format(self) -> None:
        """Test disapprove action uses pipe-separated format."""
        actions = build_chore_actions("assignee-123", "chore-456", "entry123")
        disapprove_action = actions[1]

        expected = f"{ACTION_DISAPPROVE_CHORE}|entry123|assignee-123|chore-456"
        assert disapprove_action[NOTIFY_ACTION] == expected
        assert disapprove_action[NOTIFY_TITLE] == TRANS_KEY_NOTIF_ACTION_DISAPPROVE

    def test_remind_action_pipe_format(self) -> None:
        """Test remind action uses pipe-separated format."""
        actions = build_chore_actions("assignee-123", "chore-456", "entry123")
        remind_action = actions[2]

        expected = f"{ACTION_REMIND_30}|entry123|assignee-123|chore-456"
        assert remind_action[NOTIFY_ACTION] == expected
        assert remind_action[NOTIFY_TITLE] == TRANS_KEY_NOTIF_ACTION_REMIND_30

    def test_translation_keys_not_raw_strings(self) -> None:
        """Test that translation keys are constants, not hardcoded strings."""
        actions = build_chore_actions("assignee-123", "chore-456", "entry123")

        # All title values should use translation key constants
        for action_dict in actions:
            title = action_dict[NOTIFY_TITLE]
            # Translation keys start with lowercase (notif_action_*)
            assert title.startswith("notif_action_")
            # Should not contain spaces or uppercase (indicates raw text)
            assert " " not in title
            assert title.islower()


# =============================================================================
# build_reward_actions() Tests
# =============================================================================


class TestBuildRewardActions:
    """Tests for build_reward_actions() function."""

    def test_returns_list_of_three_actions(self) -> None:
        """Test that function returns exactly 3 action dictionaries."""
        actions = build_reward_actions("assignee-123", "reward-456", "entry123")

        assert isinstance(actions, list)
        assert len(actions) == 3

    def test_without_notif_id_three_parts(self) -> None:
        """Test action format without notif_id: ACTION|entry_id|assignee_id|reward_id."""
        actions = build_reward_actions(
            "assignee-123", "reward-456", "entry123", notif_id=None
        )

        approve_action = actions[0]
        expected = f"{ACTION_APPROVE_REWARD}|entry123|assignee-123|reward-456"
        assert approve_action[NOTIFY_ACTION] == expected

        disapprove_action = actions[1]
        expected = f"{ACTION_DISAPPROVE_REWARD}|entry123|assignee-123|reward-456"
        assert disapprove_action[NOTIFY_ACTION] == expected

        remind_action = actions[2]
        expected = f"{ACTION_REMIND_30}|entry123|assignee-123|reward-456"
        assert remind_action[NOTIFY_ACTION] == expected

    def test_with_notif_id_four_parts(self) -> None:
        """Test action format with notif_id: ACTION|entry_id|assignee_id|reward_id|notif_id."""
        actions = build_reward_actions(
            "assignee-123", "reward-456", "entry123", notif_id="notif-789"
        )

        approve_action = actions[0]
        expected = f"{ACTION_APPROVE_REWARD}|entry123|assignee-123|reward-456|notif-789"
        assert approve_action[NOTIFY_ACTION] == expected

        disapprove_action = actions[1]
        expected = (
            f"{ACTION_DISAPPROVE_REWARD}|entry123|assignee-123|reward-456|notif-789"
        )
        assert disapprove_action[NOTIFY_ACTION] == expected

        remind_action = actions[2]
        expected = f"{ACTION_REMIND_30}|entry123|assignee-123|reward-456|notif-789"
        assert remind_action[NOTIFY_ACTION] == expected

    def test_reward_uses_correct_translation_keys(self) -> None:
        """Test that reward actions use the same translation keys as chores."""
        actions = build_reward_actions("assignee-123", "reward-456", "entry123")

        assert actions[0][NOTIFY_TITLE] == TRANS_KEY_NOTIF_ACTION_APPROVE
        assert actions[1][NOTIFY_TITLE] == TRANS_KEY_NOTIF_ACTION_DISAPPROVE
        assert actions[2][NOTIFY_TITLE] == TRANS_KEY_NOTIF_ACTION_REMIND_30


# =============================================================================
# build_extra_data() Tests
# =============================================================================


class TestBuildExtraData:
    """Tests for build_extra_data() function."""

    def test_always_includes_assignee_id(self) -> None:
        """Test that assignee_id is always present in returned dict."""
        data = build_extra_data("assignee-123")

        assert DATA_USER_ID in data
        assert data[DATA_USER_ID] == "assignee-123"

    def test_includes_chore_id_when_provided(self) -> None:
        """Test that chore_id is included when not None."""
        data = build_extra_data("assignee-123", chore_id="chore-456")

        assert DATA_USER_ID in data
        assert DATA_CHORE_ID in data
        assert data[DATA_CHORE_ID] == "chore-456"

    def test_includes_reward_id_when_provided(self) -> None:
        """Test that reward_id is included when not None."""
        data = build_extra_data("assignee-123", reward_id="reward-456")

        assert DATA_USER_ID in data
        assert DATA_REWARD_ID in data
        assert data[DATA_REWARD_ID] == "reward-456"

    def test_includes_notif_id_when_provided(self) -> None:
        """Test that notification_id is included when not None."""
        data = build_extra_data("assignee-123", notif_id="notif-789")

        assert DATA_USER_ID in data
        assert NOTIFY_NOTIFICATION_ID in data
        assert data[NOTIFY_NOTIFICATION_ID] == "notif-789"

    def test_omits_none_values(self) -> None:
        """Test that None values are not included in returned dict."""
        data = build_extra_data(
            "assignee-123", chore_id=None, reward_id=None, notif_id=None
        )

        assert len(data) == 1  # Only assignee_id
        assert DATA_USER_ID in data
        assert DATA_CHORE_ID not in data
        assert DATA_REWARD_ID not in data
        assert NOTIFY_NOTIFICATION_ID not in data

    def test_includes_all_provided_values(self) -> None:
        """Test that all non-None values are included."""
        data = build_extra_data(
            "assignee-123",
            chore_id="chore-456",
            reward_id="reward-789",
            notif_id="notif-abc",
        )

        assert len(data) == 4
        assert data[DATA_USER_ID] == "assignee-123"
        assert data[DATA_CHORE_ID] == "chore-456"
        assert data[DATA_REWARD_ID] == "reward-789"
        assert data[NOTIFY_NOTIFICATION_ID] == "notif-abc"


# =============================================================================
# parse_notification_action() Tests
# =============================================================================


class TestParseNotificationAction:
    """Tests for parse_notification_action() function."""

    def test_parse_valid_chore_action_three_parts(self) -> None:
        """Test parsing valid chore action: ACTION|entry_id|user_id|chore_id."""
        action_string = f"{ACTION_APPROVE_CHORE}|entry123|assignee-123|chore-456"
        parsed = parse_notification_action(action_string)

        assert parsed is not None
        assert isinstance(parsed, ParsedAction)
        assert parsed.action_type == ACTION_APPROVE_CHORE
        assert parsed.entry_id == "entry123"
        assert parsed.user_id == "assignee-123"
        assert parsed.entity_id == "chore-456"
        assert parsed.notif_id is None

    def test_parse_valid_reward_action_four_parts(self) -> None:
        """Test parsing valid reward action: ACTION|entry_id|user_id|reward_id|notif_id."""
        action_string = (
            f"{ACTION_APPROVE_REWARD}|entry123|assignee-123|reward-456|notif-789"
        )
        parsed = parse_notification_action(action_string)

        assert parsed is not None
        assert isinstance(parsed, ParsedAction)
        assert parsed.action_type == ACTION_APPROVE_REWARD
        assert parsed.entry_id == "entry123"
        assert parsed.user_id == "assignee-123"
        assert parsed.entity_id == "reward-456"
        assert parsed.notif_id == "notif-789"

    def test_parse_empty_string_returns_none(self) -> None:
        """Test that empty string returns None."""
        parsed = parse_notification_action("")

        assert parsed is None

    def test_parse_too_few_parts_returns_none(self) -> None:
        """Test that malformed string with <3 parts returns None."""
        action_string = "approve_chore|entry123"  # Missing user_id/chore_id
        parsed = parse_notification_action(action_string)

        assert parsed is None

    def test_parse_unknown_action_type_returns_none(self) -> None:
        """Test that unrecognized action type returns None."""
        action_string = "unknown_action|entry123|assignee-123|chore-456"
        parsed = parse_notification_action(action_string)

        assert parsed is None

    def test_parse_reward_without_notif_id_returns_none(self) -> None:
        """Test that reward action without notif_id returns None (invalid)."""
        # Reward actions require 4 parts (with notif_id)
        action_string = f"{ACTION_APPROVE_REWARD}|entry123|assignee-123|reward-456"
        parsed = parse_notification_action(action_string)

        assert parsed is None

    def test_parse_disapprove_chore_action(self) -> None:
        """Test parsing disapprove chore action."""
        action_string = f"{ACTION_DISAPPROVE_CHORE}|entry123|assignee-123|chore-456"
        parsed = parse_notification_action(action_string)

        assert parsed is not None
        assert parsed.action_type == ACTION_DISAPPROVE_CHORE
        assert parsed.entry_id == "entry123"
        assert parsed.user_id == "assignee-123"
        assert parsed.entity_id == "chore-456"

    def test_parse_remind_action_chore_three_parts(self) -> None:
        """Test parsing remind action for chore (4 parts)."""
        action_string = f"{ACTION_REMIND_30}|entry123|assignee-123|chore-456"
        parsed = parse_notification_action(action_string)

        assert parsed is not None
        assert parsed.action_type == ACTION_REMIND_30
        assert parsed.entry_id == "entry123"
        assert parsed.user_id == "assignee-123"
        assert parsed.entity_id == "chore-456"
        assert parsed.notif_id is None

    def test_parse_remind_action_reward_four_parts(self) -> None:
        """Test parsing remind action for reward (5 parts)."""
        action_string = f"{ACTION_REMIND_30}|entry123|assignee-123|reward-456|notif-789"
        parsed = parse_notification_action(action_string)

        assert parsed is not None
        assert parsed.action_type == ACTION_REMIND_30
        assert parsed.entry_id == "entry123"
        assert parsed.user_id == "assignee-123"
        assert parsed.entity_id == "reward-456"
        assert parsed.notif_id == "notif-789"


# =============================================================================
# ParsedAction Properties Tests
# =============================================================================


class TestParsedActionProperties:
    """Tests for ParsedAction dataclass properties."""

    def test_is_chore_action_approve(self) -> None:
        """Test is_chore_action returns True for APPROVE_CHORE."""
        parsed = ParsedAction(
            action_type=ACTION_APPROVE_CHORE,
            entry_id="entry123",
            user_id="assignee-123",
            entity_id="chore-456",
        )

        assert parsed.is_chore_action is True
        assert parsed.is_reward_action is False
        assert parsed.is_reminder_action is False

    def test_is_chore_action_disapprove(self) -> None:
        """Test is_chore_action returns True for DISAPPROVE_CHORE."""
        parsed = ParsedAction(
            action_type=ACTION_DISAPPROVE_CHORE,
            entry_id="entry123",
            user_id="assignee-123",
            entity_id="chore-456",
        )

        assert parsed.is_chore_action is True
        assert parsed.is_reward_action is False
        assert parsed.is_reminder_action is False

    def test_is_reward_action_approve(self) -> None:
        """Test is_reward_action returns True for APPROVE_REWARD."""
        parsed = ParsedAction(
            action_type=ACTION_APPROVE_REWARD,
            entry_id="entry123",
            user_id="assignee-123",
            entity_id="reward-456",
            notif_id="notif-789",
        )

        assert parsed.is_chore_action is False
        assert parsed.is_reward_action is True
        assert parsed.is_reminder_action is False

    def test_is_reward_action_disapprove(self) -> None:
        """Test is_reward_action returns True for DISAPPROVE_REWARD."""
        parsed = ParsedAction(
            action_type=ACTION_DISAPPROVE_REWARD,
            entry_id="entry123",
            user_id="assignee-123",
            entity_id="reward-456",
            notif_id="notif-789",
        )

        assert parsed.is_chore_action is False
        assert parsed.is_reward_action is True
        assert parsed.is_reminder_action is False

    def test_is_reminder_action(self) -> None:
        """Test is_reminder_action returns True for REMIND_30."""
        parsed = ParsedAction(
            action_type=ACTION_REMIND_30,
            entry_id="entry123",
            user_id="assignee-123",
            entity_id="chore-456",
        )

        assert parsed.is_chore_action is False
        assert parsed.is_reward_action is False
        assert parsed.is_reminder_action is True

    def test_chore_id_property_for_chore_action(self) -> None:
        """Test chore_id property returns entity_id for chore actions."""
        parsed = ParsedAction(
            action_type=ACTION_APPROVE_CHORE,
            entry_id="entry123",
            user_id="assignee-123",
            entity_id="chore-456",
        )

        assert parsed.chore_id == "chore-456"
        assert parsed.reward_id is None

    def test_chore_id_property_for_chore_reminder(self) -> None:
        """Test chore_id property for reminder without notif_id (chore reminder)."""
        parsed = ParsedAction(
            action_type=ACTION_REMIND_30,
            entry_id="entry123",
            user_id="assignee-123",
            entity_id="chore-456",
            notif_id=None,
        )

        assert parsed.chore_id == "chore-456"
        assert parsed.reward_id is None

    def test_reward_id_property_for_reward_action(self) -> None:
        """Test reward_id property returns entity_id for reward actions."""
        parsed = ParsedAction(
            action_type=ACTION_APPROVE_REWARD,
            entry_id="entry123",
            user_id="assignee-123",
            entity_id="reward-456",
            notif_id="notif-789",
        )

        assert parsed.reward_id == "reward-456"
        assert parsed.chore_id is None

    def test_reward_id_property_for_reward_reminder(self) -> None:
        """Test reward_id property for reminder with notif_id (reward reminder)."""
        parsed = ParsedAction(
            action_type=ACTION_REMIND_30,
            entry_id="entry123",
            user_id="assignee-123",
            entity_id="reward-456",
            notif_id="notif-789",
        )

        assert parsed.reward_id == "reward-456"
        assert parsed.chore_id is None

    def test_chore_id_none_for_reward_action(self) -> None:
        """Test chore_id returns None for reward actions."""
        parsed = ParsedAction(
            action_type=ACTION_APPROVE_REWARD,
            entry_id="entry123",
            user_id="assignee-123",
            entity_id="reward-456",
            notif_id="notif-789",
        )

        assert parsed.chore_id is None

    def test_reward_id_none_for_chore_action(self) -> None:
        """Test reward_id returns None for chore actions."""
        parsed = ParsedAction(
            action_type=ACTION_APPROVE_CHORE,
            entry_id="entry123",
            user_id="assignee-123",
            entity_id="chore-456",
        )

        assert parsed.reward_id is None


# =============================================================================
# build_notification_tag() Tests
# =============================================================================


class TestBuildNotificationTag:
    """Tests for build_notification_tag() function - v0.5.0+ unique tag system."""

    def test_single_identifier(self) -> None:
        """Test tag generation with single identifier (backwards compatible)."""
        tag = build_notification_tag("status", "assignee-123")
        # Identifiers truncated to 8 chars for Apple's 64-byte limit
        assert tag == f"{const.DOMAIN}-status-assignee-123"

    def test_multiple_identifiers(self) -> None:
        """Test tag generation with chore_id + assignee_id for uniqueness."""
        tag = build_notification_tag("status", "chore-456", "assignee-123")
        # Identifiers truncated to 8 chars: "chore-456" -> "chore-45", "assignee-123" -> "assignee-123"
        assert tag == f"{const.DOMAIN}-status-chore-45-assignee-123"

    def test_reward_identifiers(self) -> None:
        """Test tag generation for reward notifications."""
        tag = build_notification_tag("status", "reward-789", "assignee-123")
        # Identifiers truncated: "reward-789" -> "reward-7", "assignee-123" -> "assignee-123"
        assert tag == f"{const.DOMAIN}-status-reward-7-assignee-123"

    def test_no_identifiers(self) -> None:
        """Test tag generation with just tag_type (fallback behavior)."""
        tag = build_notification_tag("pending")
        assert tag == f"{const.DOMAIN}-pending"

    def test_empty_string_identifier_included(self) -> None:
        """Test that empty string identifiers are included (no filtering)."""
        # Note: Production code should not pass empty strings, but if it does
        # they are included in the tag (not filtered out)
        tag = build_notification_tag("status", "chore-456", "", "assignee-123")
        # Identifiers truncated: "chore-456" -> "chore-45", "" -> "", "assignee-123" -> "assignee-123"
        assert tag == f"{const.DOMAIN}-status-chore-45--assignee-123"

    def test_tag_type_preserved(self) -> None:
        """Test different tag types produce different prefixes."""
        # Identifiers truncated to 8 chars
        status_tag = build_notification_tag("status", "entity-1", "assignee-1")
        pending_tag = build_notification_tag("pending", "entity-1", "assignee-1")
        rewards_tag = build_notification_tag("rewards", "entity-1", "assignee-1")

        assert "status" in status_tag
        assert "pending" in pending_tag
        assert "rewards" in rewards_tag
        assert status_tag != pending_tag != rewards_tag

    def test_same_assignee_different_chores_unique(self) -> None:
        """Test same assignee with different chores produces unique tags.

        NOTE: Truncation to 8 chars can cause collisions with short test IDs!
        Production uses UUIDs where first 8 chars provide sufficient uniqueness.
        Test uses realistic UUID prefixes to demonstrate expected behavior.
        """
        # Use realistic UUID-like identifiers (production format)
        tag1 = build_notification_tag(
            "status", "abc12345-6789-abcd-ef01-234567890abc", "assignee-123"
        )
        tag2 = build_notification_tag(
            "status", "def67890-1234-5678-9abc-def012345678", "assignee-123"
        )

        assert tag1 != tag2
        # Truncated: first 8 chars are different
        assert "abc12345" in tag1
        assert "def67890" in tag2

    def test_same_chore_different_assignees_unique(self) -> None:
        """Test shared chore with different assignees produces unique tags."""
        tag1 = build_notification_tag("status", "shared-chore", "assignee-alice")
        tag2 = build_notification_tag("status", "shared-chore", "assignee-bob")

        assert tag1 != tag2
        # Truncated: "shared-chore" -> "shared-c", "assignee-alice" -> "assignee-alic", "assignee-bob" -> "assignee-bob"
        assert "shared-c" in tag1  # First 8 chars of "shared-chore"
        assert "assignee-alic" in tag1  # First 8 chars of "assignee-alice"
        assert "assignee-bob" in tag2


class TestApplyRecipientNotificationOptions:
    """Tests for per-user notification delivery options.

    These keys are read by the mobile app from the payload's ``data`` block.
    The defaults matter more than the features: an existing user who has set
    nothing must produce byte-identical payloads to before.
    """

    def test_unset_adds_nothing(self) -> None:
        """A profile with no notification settings changes the payload not at all."""
        extra: dict[str, object] = {}
        apply_recipient_notification_options(extra, {}, const.DATA_USER_NOTIF_CLICK_URL)

        assert extra == {}

    def test_click_url_still_sets_both_platform_keys(self) -> None:
        """clickAction is Android, url is iOS - the pre-existing behaviour."""
        extra: dict[str, object] = {}
        apply_recipient_notification_options(
            extra,
            {const.DATA_USER_NOTIF_CLICK_URL: "/lovelace/chores"},
            const.DATA_USER_NOTIF_CLICK_URL,
        )

        assert extra["clickAction"] == "/lovelace/chores"
        assert extra["url"] == "/lovelace/chores"

    def test_approver_key_is_honoured(self) -> None:
        """Approvers store their own click URL, so the key is a parameter."""
        extra: dict[str, object] = {}
        profile = {
            const.DATA_USER_NOTIF_CLICK_URL: "/assignee",
            const.DATA_USER_NOTIF_APPROVE_CLICK_URL: "/approver",
        }
        apply_recipient_notification_options(
            extra, profile, const.DATA_USER_NOTIF_APPROVE_CLICK_URL
        )

        assert extra["clickAction"] == "/approver"

    def test_high_priority_is_passed_through(self) -> None:
        """The setting that lets a push wake a sleeping device."""
        extra: dict[str, object] = {}
        apply_recipient_notification_options(
            extra,
            {const.DATA_USER_NOTIFICATION_PRIORITY: const.NOTIFY_PRIORITY_HIGH},
            const.DATA_USER_NOTIF_CLICK_URL,
        )

        assert extra[const.NOTIFY_PRIORITY] == const.NOTIFY_PRIORITY_HIGH


class TestSettingsSurviveTheDataBuilders:
    """Round-trip coverage for the canonical data builders.

    CLOSED DICT LITERALS: build_user_profile() and build_chore() return an
    explicit field list, so any key they do not name is dropped on write. A
    setting can therefore be read correctly everywhere and still never persist.

    The other tests in this module call the notification helpers against
    hand-built dicts, which cannot detect that. These assert all four settings
    survive a build, and survive an unrelated edit - update replaces the stored
    record wholesale rather than merging into it.
    """

    def test_user_priority_and_ttl_survive_build(self) -> None:
        """Both must appear in the built profile, like notif_click_url does."""
        built = build_user_profile(
            user_input={
                const.CFOF_USERS_INPUT_NAME: "Test",
                const.CFOF_USERS_INPUT_NOTIFICATION_PRIORITY: const.NOTIFY_PRIORITY_HIGH,
                const.CFOF_USERS_INPUT_NOTIFICATION_TTL: "3600",
            },
            existing=None,
        )

        assert (
            built[const.DATA_USER_NOTIFICATION_PRIORITY] == const.NOTIFY_PRIORITY_HIGH
        )
        assert built[const.DATA_USER_NOTIFICATION_TTL] == "3600"

    def test_user_settings_survive_an_unrelated_edit(self) -> None:
        """user_manager replaces the record wholesale, so an omitted key is lost."""
        first = build_user_profile(
            user_input={
                const.CFOF_USERS_INPUT_NAME: "Test",
                const.CFOF_USERS_INPUT_NOTIFICATION_PRIORITY: const.NOTIFY_PRIORITY_HIGH,
            },
            existing=None,
        )
        second = build_user_profile(
            user_input={const.CFOF_USERS_INPUT_NAME: "Renamed"},
            existing=first,
        )

        assert (
            second[const.DATA_USER_NOTIFICATION_PRIORITY] == const.NOTIFY_PRIORITY_HIGH
        )

    def test_chore_channel_survives_build(self) -> None:
        built = build_chore(
            user_input={
                const.DATA_CHORE_NAME: "Medicine",
                const.DATA_CHORE_NOTIFICATION_CHANNEL: "Medicine",
            },
            existing=None,
        )

        assert built[const.DATA_CHORE_NOTIFICATION_CHANNEL] == "Medicine"

    def test_chore_importance_survives_build(self) -> None:
        """Fourth setting, same closed-dict-literal trap as the other three."""
        built = build_chore(
            user_input={
                const.DATA_CHORE_NAME: "Medicine",
                const.DATA_CHORE_NOTIFICATION_CHANNEL: "Medicine",
                const.DATA_CHORE_NOTIFICATION_IMPORTANCE: "high",
            },
            existing=None,
        )

        assert built[const.DATA_CHORE_NOTIFICATION_IMPORTANCE] == "high"

    @pytest.mark.parametrize("stored", ["min", "low", "default", "high", "max", ""])
    def test_every_importance_member_round_trips(self, stored: str) -> None:
        """Each member of the closed set survives the builder unchanged.

        The narrowing is a ladder of explicit comparisons, so a member with no
        branch of its own would silently become something else. Only a sweep of
        the whole set catches that; testing one value hits one branch.
        """
        built = build_chore(
            user_input={
                const.DATA_CHORE_NAME: "Medicine",
                const.DATA_CHORE_NOTIFICATION_CHANNEL: "Medicine",
                const.DATA_CHORE_NOTIFICATION_IMPORTANCE: stored,
            },
            existing=None,
        )

        assert built[const.DATA_CHORE_NOTIFICATION_IMPORTANCE] == stored

    @pytest.mark.parametrize("stored", ["urgent", "HIGH", "1", "none", "maximum"])
    def test_unrecognised_importance_becomes_unset_not_verbatim(
        self, stored: str
    ) -> None:
        """A value from a hand-edited backup is dropped, never written back.

        🔑 `"maximum"` is the case that matters: an earlier version gated on
        membership in NOTIFY_IMPORTANCE_OPTIONS and fell through to `return
        "max"`, so a near-miss - or any option added to that tuple without a
        branch - became the LOUDEST setting rather than unset.
        """
        built = build_chore(
            user_input={
                const.DATA_CHORE_NAME: "Medicine",
                const.DATA_CHORE_NOTIFICATION_CHANNEL: "Medicine",
                const.DATA_CHORE_NOTIFICATION_IMPORTANCE: stored,
            },
            existing=None,
        )

        assert built[const.DATA_CHORE_NOTIFICATION_IMPORTANCE] == ""

    def test_every_importance_option_has_its_own_branch(self) -> None:
        """Pins the const tuple to the narrowing ladder.

        Four places have to agree: NOTIFY_IMPORTANCE_OPTIONS, the Literal in
        type_defs, the builder's ladder, and the manager's guard. Nothing else
        holds them together, so adding an option to the tuple without a branch
        fails here rather than silently unsetting it in production.
        """
        for option in const.NOTIFY_IMPORTANCE_OPTIONS:
            built = build_chore(
                user_input={
                    const.DATA_CHORE_NAME: "Medicine",
                    const.DATA_CHORE_NOTIFICATION_CHANNEL: "Medicine",
                    const.DATA_CHORE_NOTIFICATION_IMPORTANCE: option,
                },
                existing=None,
            )
            assert built[const.DATA_CHORE_NOTIFICATION_IMPORTANCE] == option, (
                f"{option!r} is in NOTIFY_IMPORTANCE_OPTIONS but has no branch "
                "in _narrow_notification_importance"
            )

    def test_chore_channel_survives_an_unrelated_edit(self) -> None:
        first = build_chore(
            user_input={
                const.DATA_CHORE_NAME: "Medicine",
                const.DATA_CHORE_NOTIFICATION_CHANNEL: "Medicine",
            },
            existing=None,
        )
        second = build_chore(
            user_input={
                const.DATA_CHORE_NAME: "Medicine",
                const.DATA_CHORE_DEFAULT_POINTS: 2,
            },
            existing=first,
        )

        assert second[const.DATA_CHORE_NOTIFICATION_CHANNEL] == "Medicine"

    def test_unknown_priority_is_ignored(self) -> None:
        """Only the documented values are forwarded - never arbitrary strings."""
        extra: dict[str, object] = {}
        apply_recipient_notification_options(
            extra,
            {const.DATA_USER_NOTIFICATION_PRIORITY: "URGENT!!"},
            const.DATA_USER_NOTIF_CLICK_URL,
        )

        assert const.NOTIFY_PRIORITY not in extra

    def test_normal_priority_emits_nothing(self) -> None:
        """'normal' is the platform default, so it must not touch the payload.

        The form's default is "normal", so emitting it would mean every user who
        opens and saves a profile silently starts sending a priority key forever.
        """
        extra: dict[str, object] = {}
        apply_recipient_notification_options(
            extra,
            {const.DATA_USER_NOTIFICATION_PRIORITY: const.NOTIFY_PRIORITY_NORMAL},
            const.DATA_USER_NOTIF_CLICK_URL,
        )

        assert extra == {}

    def test_none_ttl_does_not_warn_or_emit(self) -> None:
        """A stored None must not stringify to "None" and warn on every send."""
        extra: dict[str, object] = {}
        apply_recipient_notification_options(
            extra,
            {const.DATA_USER_NOTIFICATION_TTL: None},
            const.DATA_USER_NOTIF_CLICK_URL,
        )

        assert const.NOTIFY_TTL not in extra

    def test_negative_ttl_is_rejected(self) -> None:
        """A negative lifetime is meaningless and must not reach the payload."""
        extra: dict[str, object] = {}
        apply_recipient_notification_options(
            extra,
            {const.DATA_USER_NOTIFICATION_TTL: "-5"},
            const.DATA_USER_NOTIF_CLICK_URL,
        )

        assert const.NOTIFY_TTL not in extra

    def test_ttl_is_sent_as_an_integer(self) -> None:
        """Stored as text by the form; the payload wants a number."""
        extra: dict[str, object] = {}
        apply_recipient_notification_options(
            extra,
            {const.DATA_USER_NOTIFICATION_TTL: "3600"},
            const.DATA_USER_NOTIF_CLICK_URL,
        )

        assert extra[const.NOTIFY_TTL] == 3600
        assert isinstance(extra[const.NOTIFY_TTL], int)

    def test_ttl_zero_is_preserved(self) -> None:
        """0 means 'discard if undeliverable now' - a real setting, not 'unset'.

        The obvious falsy check would silently drop it.
        """
        extra: dict[str, object] = {}
        apply_recipient_notification_options(
            extra,
            {const.DATA_USER_NOTIFICATION_TTL: "0"},
            const.DATA_USER_NOTIF_CLICK_URL,
        )

        assert extra[const.NOTIFY_TTL] == 0

    def test_non_numeric_ttl_is_dropped_not_raised(self) -> None:
        """A typo must not break every notification for that user."""
        extra: dict[str, object] = {}
        apply_recipient_notification_options(
            extra,
            {const.DATA_USER_NOTIFICATION_TTL: "soon"},
            const.DATA_USER_NOTIF_CLICK_URL,
        )

        assert const.NOTIFY_TTL not in extra

    @pytest.mark.parametrize("raw", ["1e400", "inf", "-inf", "Infinity"])
    def test_infinite_ttl_is_dropped_not_raised(self, raw: str) -> None:
        """An unbounded literal must not silence the user's notifications.

        ``float()`` does NOT raise on any of these - it returns ``inf``, and the
        ``OverflowError`` comes from ``int(inf)``. Since the parse catches only
        ``ValueError``, that escapes the dispatcher callback and the send never
        happens. Every recipient path calls this helper, so one bad profile field
        silently stops all of that user's pushes.

        ``"nan"`` is deliberately absent: it raises ``ValueError``, which the
        existing handler already catches. Pinning it would suggest the guard is
        doing work it is not.
        """
        extra: dict[str, object] = {}
        apply_recipient_notification_options(
            extra,
            {const.DATA_USER_NOTIFICATION_TTL: raw},
            const.DATA_USER_NOTIF_CLICK_URL,
        )

        assert const.NOTIFY_TTL not in extra

    @pytest.mark.parametrize("raw", ["1e308", "2419201", "99999999999"])
    def test_ttl_beyond_the_fcm_ceiling_is_dropped(self, raw: str) -> None:
        """Out-of-range is as fatal as a crash, and it raises nothing at all.

        🔑 THIS IS THE CASE A ``ValueError, OverflowError`` CATCH DOES NOT FIX.
        ``1e308`` parses cleanly, clears the ``parsed < 0`` guard, and puts a
        309-digit integer in the payload. FCM accepts 0..2,419,200 seconds and
        answers anything else with ``InvalidTtl`` - the message is not sent. Same
        user-visible outcome as the escaping exception above, reached without any
        exception to catch, so the fix has to be a BOUND and not a wider except.
        """
        extra: dict[str, object] = {}
        apply_recipient_notification_options(
            extra,
            {const.DATA_USER_NOTIFICATION_TTL: raw},
            const.DATA_USER_NOTIF_CLICK_URL,
        )

        assert const.NOTIFY_TTL not in extra

    def test_ttl_at_the_fcm_ceiling_is_kept(self) -> None:
        """The boundary itself is valid - 28 days is FCM's documented maximum.

        Guards the off-by-one in the other direction: a bound written ``<`` would
        drop a legitimate setting.
        """
        extra: dict[str, object] = {}
        apply_recipient_notification_options(
            extra,
            {const.DATA_USER_NOTIFICATION_TTL: "2419200"},
            const.DATA_USER_NOTIF_CLICK_URL,
        )

        assert extra[const.NOTIFY_TTL] == 2419200

    def test_existing_payload_keys_are_preserved(self) -> None:
        """The helper merges into a payload that already carries tags/actions."""
        extra: dict[str, object] = {const.NOTIFY_TAG: "choreops_status_x"}
        apply_recipient_notification_options(
            extra,
            {const.DATA_USER_NOTIFICATION_PRIORITY: const.NOTIFY_PRIORITY_HIGH},
            const.DATA_USER_NOTIF_CLICK_URL,
        )

        assert extra[const.NOTIFY_TAG] == "choreops_status_x"
        assert extra[const.NOTIFY_PRIORITY] == const.NOTIFY_PRIORITY_HIGH


class TestApplySubjectNotificationOptions:
    """Tests for the per-chore notification channel.

    This axis is the SUBJECT of a notification rather than its recipient, which
    is why it is resolved from an explicit chore_id and not from the profile.
    """

    @staticmethod
    def _manager(chores: dict[str, dict[str, object]]) -> NotificationManager:
        """A NotificationManager with nothing but the chore lookup wired."""
        manager = object.__new__(NotificationManager)
        manager.coordinator = SimpleNamespace(chores_data=chores)  # type: ignore[assignment]
        return manager

    def test_channel_is_applied(self) -> None:
        """The whole point: one chore's notifications get their own channel."""
        manager = self._manager(
            {"chore-1": {const.DATA_CHORE_NOTIFICATION_CHANNEL: "Medicine"}}
        )
        extra: dict[str, object] = {}
        manager._apply_subject_notification_options(extra, "chore-1")

        assert extra[const.NOTIFY_CHANNEL] == "Medicine"

    def test_no_chore_id_adds_nothing(self) -> None:
        """Notifications that are not about a chore are untouched."""
        manager = self._manager({})
        extra: dict[str, object] = {}
        manager._apply_subject_notification_options(extra, None)

        assert extra == {}

    def test_unknown_chore_id_adds_nothing(self) -> None:
        """A deleted chore must not raise while its notification drains."""
        manager = self._manager({})
        extra: dict[str, object] = {}
        manager._apply_subject_notification_options(extra, "gone")

        assert extra == {}

    def test_unset_channel_adds_nothing(self) -> None:
        """Default state for every existing chore - payload unchanged."""
        manager = self._manager({"chore-1": {}})
        extra: dict[str, object] = {}
        manager._apply_subject_notification_options(extra, "chore-1")

        assert const.NOTIFY_CHANNEL not in extra

    def test_whitespace_only_channel_is_ignored(self) -> None:
        """The integration cannot alter a channel once a device has it; blanks must not create one."""
        manager = self._manager(
            {"chore-1": {const.DATA_CHORE_NOTIFICATION_CHANNEL: "   "}}
        )
        extra: dict[str, object] = {}
        manager._apply_subject_notification_options(extra, "chore-1")

        assert const.NOTIFY_CHANNEL not in extra

    def test_reward_id_does_not_resolve_a_channel(self) -> None:
        """A reward id must not resolve a chore channel.

        Two call sites pass ``tag_identifiers=(reward_id, assignee_id)``, so
        inferring the subject from that tuple's first element would look up a
        reward id in the chore table. Resolving from an explicit chore_id means a
        reward notification simply carries no channel.
        """
        manager = self._manager(
            {"chore-1": {const.DATA_CHORE_NOTIFICATION_CHANNEL: "Medicine"}}
        )
        extra: dict[str, object] = {}
        manager._apply_subject_notification_options(extra, "reward-1")

        assert const.NOTIFY_CHANNEL not in extra

    def test_importance_accompanies_the_channel(self) -> None:
        """Importance decides whether the alert pops on screen or arrives quietly.

        A channel created without it is born at "default" - makes a sound, does
        not intrude - so a high-priority push into that channel is delivered
        promptly and then alerts quietly.
        """
        manager = self._manager(
            {
                "chore-1": {
                    const.DATA_CHORE_NOTIFICATION_CHANNEL: "Medicine",
                    const.DATA_CHORE_NOTIFICATION_IMPORTANCE: "high",
                }
            }
        )
        extra: dict[str, object] = {}
        manager._apply_subject_notification_options(extra, "chore-1")

        assert extra[const.NOTIFY_CHANNEL] == "Medicine"
        assert extra[const.NOTIFY_IMPORTANCE] == "high"

    def test_importance_without_a_channel_is_not_sent(self) -> None:
        """Android attaches importance to a channel, so it is meaningless alone."""
        manager = self._manager(
            {"chore-1": {const.DATA_CHORE_NOTIFICATION_IMPORTANCE: "high"}}
        )
        extra: dict[str, object] = {}
        manager._apply_subject_notification_options(extra, "chore-1")

        assert extra == {}

    def test_unknown_importance_is_ignored(self) -> None:
        """Only the documented levels reach the payload."""
        manager = self._manager(
            {
                "chore-1": {
                    const.DATA_CHORE_NOTIFICATION_CHANNEL: "Medicine",
                    const.DATA_CHORE_NOTIFICATION_IMPORTANCE: "URGENT!!",
                }
            }
        )
        extra: dict[str, object] = {}
        manager._apply_subject_notification_options(extra, "chore-1")

        assert extra[const.NOTIFY_CHANNEL] == "Medicine"
        assert const.NOTIFY_IMPORTANCE not in extra

    def test_channel_without_importance_still_works(self) -> None:
        """The pre-importance shape stays valid - channel alone is legitimate."""
        manager = self._manager(
            {"chore-1": {const.DATA_CHORE_NOTIFICATION_CHANNEL: "Medicine"}}
        )
        extra: dict[str, object] = {}
        manager._apply_subject_notification_options(extra, "chore-1")

        assert extra[const.NOTIFY_CHANNEL] == "Medicine"
        assert const.NOTIFY_IMPORTANCE not in extra


class TestBroadcastAppliesRecipientOptions:
    """Coverage for the system-announcement delivery path.

    Every test of the data-reset service patches ``broadcast_to_all_approvers``
    out, so its body is the one delivery path the suite never executes. The
    options are applied synchronously before the send coroutine is built, and
    the gather that follows uses ``return_exceptions=True`` - so a failure here
    would abort the whole broadcast rather than being logged per-approver.
    """

    @staticmethod
    def _manager(approvers: dict[str, dict[str, object]]) -> NotificationManager:
        """A NotificationManager with only what the broadcast loop reads."""
        manager = object.__new__(NotificationManager)
        manager.hass = SimpleNamespace(  # type: ignore[assignment]
            config=SimpleNamespace(language="en")
        )
        manager.coordinator = SimpleNamespace(  # type: ignore[assignment]
            approvers_data=approvers,
            config_entry=SimpleNamespace(options={}),
        )
        return manager

    async def test_broadcast_carries_user_delivery_options(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An approver's priority and TTL reach a system announcement too."""
        manager = self._manager(
            {
                "approver-1": {
                    const.DATA_USER_MOBILE_NOTIFY_SERVICE: "notify.mobile_app_x",
                    const.DATA_USER_NOTIFICATION_PRIORITY: const.NOTIFY_PRIORITY_HIGH,
                    const.DATA_USER_NOTIFICATION_TTL: "72000",
                }
            }
        )
        sent: list[dict[str, Any]] = []

        async def _capture(
            service: str,
            title: str,
            message: str,
            extra_data: dict[str, Any] | None = None,
        ) -> None:
            sent.append({"service": service, "extra_data": extra_data})

        async def _no_translations(*_args: object, **_kwargs: object) -> dict[str, Any]:
            return {}

        monkeypatch.setattr(manager, "_send_notification", _capture)
        monkeypatch.setattr(th, "load_notification_translation", _no_translations)

        await manager.broadcast_to_all_approvers("title_key", "message_key")

        assert len(sent) == 1
        extra = sent[0]["extra_data"]
        assert extra[const.NOTIFY_PRIORITY] == const.NOTIFY_PRIORITY_HIGH
        assert extra[const.NOTIFY_TTL] == 72000

    async def test_broadcast_without_options_sends_no_extra_data(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """An approver who set nothing gets the payload they got before."""
        manager = self._manager(
            {
                "approver-1": {
                    const.DATA_USER_MOBILE_NOTIFY_SERVICE: "notify.mobile_app_x",
                }
            }
        )
        sent: list[dict[str, Any]] = []

        async def _capture(
            service: str,
            title: str,
            message: str,
            extra_data: dict[str, Any] | None = None,
        ) -> None:
            sent.append({"service": service, "extra_data": extra_data})

        async def _no_translations(*_args: object, **_kwargs: object) -> dict[str, Any]:
            return {}

        monkeypatch.setattr(manager, "_send_notification", _capture)
        monkeypatch.setattr(th, "load_notification_translation", _no_translations)

        await manager.broadcast_to_all_approvers("title_key", "message_key")

        assert sent[0]["extra_data"] is None
