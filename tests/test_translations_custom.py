"""Custom translation system tests.

Tests the custom translation file loading system used for:
- Notification translations (translations_custom/*_notifications.json)
- Dashboard translations (translations_custom/*_dashboard.json)

These tests verify:
1. Translation files exist and are valid JSON
2. Required translation keys are present
3. Translation constants map to actual file entries
4. Multi-language files load correctly

Note: For notification WORKFLOW tests (sending notifications, action buttons
during chore claims, etc.), see test_workflow_notifications.py.
"""

# pylint: disable=redefined-outer-name

import json
from pathlib import Path
from typing import Any

import pytest

# Import const for tests that verify constant existence in source module
from custom_components.choreops import const
from tests.helpers import (
    TRANS_KEY_NOTIF_ACTION_APPROVE,
    TRANS_KEY_NOTIF_ACTION_DISAPPROVE,
    TRANS_KEY_NOTIF_ACTION_REMIND_30,
)

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_translations_dir() -> Path:
    """Get path to custom translations directory."""
    # Use absolute path based on this file's location
    # tests/test_translations_custom.py -> custom_components/choreops/translations_custom
    tests_dir = Path(__file__).parent
    workspace_root = tests_dir.parent
    return workspace_root / "custom_components" / "choreops" / "translations_custom"


def load_notification_translations(language: str) -> dict[str, Any]:
    """Load notification translations for a language.

    Args:
        language: Language code (e.g., 'en', 'nl', 'sk')

    Returns:
        Full translation dictionary from JSON file

    Raises:
        FileNotFoundError: If translation file doesn't exist
    """
    translations_path = get_translations_dir() / f"{language}_notifications.json"

    if not translations_path.exists():
        raise FileNotFoundError(f"Translation file not found: {translations_path}")

    with open(translations_path, encoding="utf-8") as f:
        return json.load(f)


def load_dashboard_translations(language: str) -> dict[str, Any]:
    """Load dashboard translations for a language.

    Args:
        language: Language code (e.g., 'en', 'nl', 'sk')

    Returns:
        Full translation dictionary from JSON file

    Raises:
        FileNotFoundError: If translation file doesn't exist
    """
    translations_path = get_translations_dir() / f"{language}_dashboard.json"

    if not translations_path.exists():
        raise FileNotFoundError(f"Translation file not found: {translations_path}")

    with open(translations_path, encoding="utf-8") as f:
        return json.load(f)


def load_report_translations(language: str) -> dict[str, Any]:
    """Load report translations for a language.

    Args:
        language: Language code (e.g., 'en')

    Returns:
        Full translation dictionary from JSON file

    Raises:
        FileNotFoundError: If translation file doesn't exist
    """
    translations_path = get_translations_dir() / f"{language}_report.json"

    if not translations_path.exists():
        raise FileNotFoundError(f"Translation file not found: {translations_path}")

    with open(translations_path, encoding="utf-8") as f:
        return json.load(f)


def get_available_notification_languages() -> list[str]:
    """Get list of languages with notification translations.

    Returns:
        List of language codes (e.g., ['en', 'nl', 'sk', ...])
    """
    translations_dir = get_translations_dir()
    languages = []

    for file_path in translations_dir.glob("*_notifications.json"):
        # Extract language code from filename (e.g., 'en' from 'en_notifications.json')
        lang_code = file_path.stem.replace("_notifications", "")
        languages.append(lang_code)

    return sorted(languages)


def get_available_dashboard_languages() -> list[str]:
    """Get list of languages with dashboard translations.

    Returns:
        List of language codes (e.g., ['en', 'nl', 'sk', ...])
    """
    translations_dir = get_translations_dir()
    languages = []

    for file_path in translations_dir.glob("*_dashboard.json"):
        # Extract language code from filename (e.g., 'en' from 'en_dashboard.json')
        lang_code = file_path.stem.replace("_dashboard", "")
        languages.append(lang_code)

    return sorted(languages)


# =============================================================================
# TRANSLATION FILE STRUCTURE TESTS
# =============================================================================


class TestTranslationFilesExist:
    """Verify translation files exist and are valid JSON."""

    def test_english_notifications_exists(self) -> None:
        """English notification translations must exist (master file)."""
        translations = load_notification_translations("en")
        assert translations is not None
        assert isinstance(translations, dict)

    def test_english_dashboard_exists(self) -> None:
        """English dashboard translations must exist (master file)."""
        translations = load_dashboard_translations("en")
        assert translations is not None
        assert isinstance(translations, dict)

    def test_english_report_exists(self) -> None:
        """English report translations must exist (master file)."""
        translations = load_report_translations("en")
        assert translations is not None
        assert isinstance(translations, dict)

    def test_at_least_one_other_language_notifications(self) -> None:
        """At least one non-English notification translation should exist."""
        languages = get_available_notification_languages()
        non_english = [lang for lang in languages if lang != "en"]
        assert len(non_english) > 0, (
            "Expected at least one non-English notification translation"
        )

    def test_at_least_one_other_language_dashboard(self) -> None:
        """At least one non-English dashboard translation should exist."""
        languages = get_available_dashboard_languages()
        non_english = [lang for lang in languages if lang != "en"]
        assert len(non_english) > 0, (
            "Expected at least one non-English dashboard translation"
        )


class TestNotificationTranslationStructure:
    """Verify notification translation files have required structure."""

    def test_english_has_actions_section(self) -> None:
        """English notifications must have 'actions' section."""
        translations = load_notification_translations("en")
        assert "actions" in translations, "Missing 'actions' section"

    def test_english_actions_has_required_keys(self) -> None:
        """English actions must have approve, disapprove, remind_30."""
        translations = load_notification_translations("en")
        actions = translations.get("actions", {})

        required_keys = ["approve", "disapprove", "remind_30"]
        for key in required_keys:
            assert key in actions, f"Missing required action key: {key}"
            assert len(actions[key]) > 0, f"Empty translation for action: {key}"

    def test_english_has_chore_notifications(self) -> None:
        """English notifications must have chore-related messages."""
        translations = load_notification_translations("en")

        # v0.5.0+ standardized notification keys by recipient (assignee/approver)
        chore_keys = [
            "chore_approved_assignee",
            "chore_disapproved_assignee",
            "chore_claimed_approver",
        ]
        for key in chore_keys:
            assert key in translations, f"Missing chore notification: {key}"
            assert "title" in translations[key], f"Missing title for {key}"
            assert "message" in translations[key], f"Missing message for {key}"

    def test_english_has_reward_notifications(self) -> None:
        """English notifications must have reward-related messages."""
        translations = load_notification_translations("en")

        # v0.5.0+ standardized notification keys by recipient (assignee/approver)
        reward_keys = [
            "reward_approved_assignee",
            "reward_disapproved_assignee",
            "reward_claimed_approver",
        ]
        for key in reward_keys:
            assert key in translations, f"Missing reward notification: {key}"
            assert "title" in translations[key], f"Missing title for {key}"
            assert "message" in translations[key], f"Missing message for {key}"


class TestNotificationActionConstants:
    """Verify notification action constants map to translation files."""

    def test_approve_constant_maps_to_file(self) -> None:
        """TRANS_KEY_NOTIF_ACTION_APPROVE must map to translation."""
        assert hasattr(const, "TRANS_KEY_NOTIF_ACTION_APPROVE")
        assert TRANS_KEY_NOTIF_ACTION_APPROVE == "notif_action_approve"

        translations = load_notification_translations("en")
        actions = translations.get("actions", {})
        assert "approve" in actions
        assert len(actions["approve"]) > 0

    def test_disapprove_constant_maps_to_file(self) -> None:
        """TRANS_KEY_NOTIF_ACTION_DISAPPROVE must map to translation."""
        assert hasattr(const, "TRANS_KEY_NOTIF_ACTION_DISAPPROVE")
        assert TRANS_KEY_NOTIF_ACTION_DISAPPROVE == "notif_action_disapprove"

        translations = load_notification_translations("en")
        actions = translations.get("actions", {})
        assert "disapprove" in actions
        assert len(actions["disapprove"]) > 0

    def test_remind_constant_maps_to_file(self) -> None:
        """TRANS_KEY_NOTIF_ACTION_REMIND_30 must map to translation."""
        assert hasattr(const, "TRANS_KEY_NOTIF_ACTION_REMIND_30")
        assert TRANS_KEY_NOTIF_ACTION_REMIND_30 == "notif_action_remind_30"

        translations = load_notification_translations("en")
        actions = translations.get("actions", {})
        assert "remind_30" in actions
        assert len(actions["remind_30"]) > 0


class TestMultiLanguageNotifications:
    """Verify non-English notification translations are valid."""

    @pytest.mark.parametrize("language", get_available_notification_languages())
    def test_notification_file_is_valid_json(self, language: str) -> None:
        """Each notification file must be valid JSON."""
        translations = load_notification_translations(language)
        assert isinstance(translations, dict)

    @pytest.mark.parametrize("language", get_available_notification_languages())
    def test_notification_file_has_actions(self, language: str) -> None:
        """Each notification file must have actions section."""
        translations = load_notification_translations(language)
        assert "actions" in translations, f"{language}: Missing 'actions' section"

    @pytest.mark.parametrize("language", get_available_notification_languages())
    def test_action_titles_not_empty(self, language: str) -> None:
        """Action titles must not be empty strings."""
        translations = load_notification_translations(language)
        actions = translations.get("actions", {})

        for key in ["approve", "disapprove", "remind_30"]:
            if key in actions:
                assert len(actions[key]) > 0, (
                    f"{language}: Empty translation for '{key}'"
                )


class TestMultiLanguageDashboard:
    """Verify non-English dashboard translations are valid."""

    @pytest.mark.parametrize("language", get_available_dashboard_languages())
    def test_dashboard_file_is_valid_json(self, language: str) -> None:
        """Each dashboard file must be valid JSON."""
        translations = load_dashboard_translations(language)
        assert isinstance(translations, dict)

    @pytest.mark.parametrize("language", get_available_dashboard_languages())
    def test_dashboard_has_welcome_section(self, language: str) -> None:
        """Each dashboard file should have welcome translations."""
        translations = load_dashboard_translations(language)
        # Check for common dashboard keys
        assert len(translations) > 0, f"{language}: Dashboard file is empty"


# =============================================================================
# TRANSLATION CONTENT QUALITY TESTS
# =============================================================================


class TestTranslationQuality:
    """Verify translation content quality."""

    def test_action_translations_differ_from_keys(self) -> None:
        """Action translations should be user-friendly, not raw keys."""
        translations = load_notification_translations("en")
        actions = translations.get("actions", {})

        # Translations should NOT just be the key itself
        assert actions.get("approve") != "approve"
        assert actions.get("disapprove") != "disapprove"
        assert actions.get("remind_30") != "remind_30"

    def test_action_translations_are_readable(self) -> None:
        """Action translations should be human-readable text."""
        translations = load_notification_translations("en")
        actions = translations.get("actions", {})

        # Should contain spaces or be properly capitalized words
        approve = actions.get("approve", "")
        assert approve[0].isupper() or " " in approve, (
            f"Expected readable text, got: {approve}"
        )

    @pytest.mark.parametrize("language", get_available_notification_languages())
    def test_no_untranslated_placeholders(self, language: str) -> None:
        """Translations should not contain untranslated placeholder text."""
        translations = load_notification_translations(language)
        actions = translations.get("actions", {})

        for key, value in actions.items():
            # Check for common placeholder patterns that indicate missing translation
            # Note: Skip "TODO" check for Spanish where "todo" is a valid word meaning "all"
            if language != "es":
                assert "TODO" not in value.upper(), f"{language}.{key}: Contains TODO"
            assert "FIXME" not in value.upper(), f"{language}.{key}: Contains FIXME"
            assert "err-" not in value.lower(), f"{language}.{key}: Contains err-"
