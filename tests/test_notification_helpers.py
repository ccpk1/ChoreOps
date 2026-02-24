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

from custom_components.choreops import const
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
