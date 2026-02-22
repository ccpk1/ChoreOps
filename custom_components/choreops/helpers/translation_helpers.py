# File: helpers/translation_helpers.py
"""Translation helper functions for ChoreOps (The Librarian).

Shared logic for loading and caching translation files used by:
- UIManager: Dashboard translations for sensor attributes
- NotificationManager: Notification translations for approver alerts

All functions here require a `hass` object for async file I/O.
"""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING, Any

from .. import const

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant


# ==============================================================================
# Module-Level Cache
# ==============================================================================

# Module-level translation cache for performance (v0.5.0+)
# Key format: f"{language}_{translation_type}" where translation_type is "dashboard" or "notification"
# This avoids repeated file I/O when sending notifications to multiple approvers with same language
_translation_cache: dict[str, dict[str, Any]] = {}


# ==============================================================================
# Internal Helpers
# ==============================================================================


def _read_json_file(file_path: str) -> dict:
    """Read and parse a JSON file. Synchronous helper for executor."""
    with open(file_path, encoding="utf-8") as f:
        return json.load(f)


def _get_translations_path() -> str:
    """Get the absolute path to the translations_custom directory.

    Returns path relative to the component root (helpers/../translations_custom).
    """
    return os.path.join(
        os.path.dirname(os.path.dirname(__file__)), const.CUSTOM_TRANSLATIONS_DIR
    )


# ==============================================================================
# Dashboard Translation Helpers
# ==============================================================================


async def get_available_dashboard_languages(
    hass: HomeAssistant,
) -> list[str]:
    """Get list of available dashboard language codes.

    Scans the translations directory for dashboard translation files and filters
    against Home Assistant's master LANGUAGES set. Only language codes that have
    actual translation files are returned.

    Returns:
        List of language codes (e.g., ["en", "es", "de"]).
        If directory not found or empty, returns ["en"] as fallback.
    """
    from homeassistant.generated.languages import LANGUAGES

    translations_path = _get_translations_path()

    if not await hass.async_add_executor_job(os.path.exists, translations_path):
        const.LOGGER.debug(
            "Dashboard translations directory not found: %s, using English only",
            translations_path,
        )
        return ["en"]

    try:
        filenames = await hass.async_add_executor_job(os.listdir, translations_path)
        available_languages = []

        for filename in filenames:
            # Only process files matching *_dashboard.json pattern
            if not filename.endswith(f"{const.DASHBOARD_TRANSLATIONS_SUFFIX}.json"):
                continue

            # Extract language code from filename (e.g., es_dashboard.json -> es)
            lang_code = filename[
                : -len(".json") - len(const.DASHBOARD_TRANSLATIONS_SUFFIX)
            ]

            # Only include if valid in Home Assistant's LANGUAGES set
            if lang_code in LANGUAGES:
                available_languages.append(lang_code)
            else:
                const.LOGGER.debug(
                    "Ignoring unknown language code: %s (not in LANGUAGES set)",
                    lang_code,
                )

        # Ensure English is always available
        if "en" not in available_languages:
            available_languages.insert(0, "en")
        else:
            # Ensure English is first in the list
            available_languages.remove("en")
            available_languages.insert(0, "en")

        # Sort remaining languages (English stays first)
        if len(available_languages) > 1:
            available_languages = ["en", *sorted(available_languages[1:])]

        const.LOGGER.debug("Available dashboard languages: %s", available_languages)
        return available_languages

    except OSError as err:
        const.LOGGER.error("Error reading dashboard translations directory: %s", err)
        return ["en"]


async def load_dashboard_translation(
    hass: HomeAssistant,
    language: str = "en",
) -> dict[str, str]:
    """Load a specific dashboard translation file with English fallback.

    Args:
        hass: Home Assistant instance
        language: Language code to load (e.g., 'en', 'es', 'de')

    Returns:
        A dict with translation keys and values.
        If the requested language is not found, returns English translations.
    """
    translations_path = _get_translations_path()

    if not await hass.async_add_executor_job(os.path.exists, translations_path):
        const.LOGGER.error(
            "Dashboard translations directory not found: %s", translations_path
        )
        return {}

    # Try to load the requested language (with _dashboard suffix)
    lang_path = os.path.join(
        translations_path, f"{language}{const.DASHBOARD_TRANSLATIONS_SUFFIX}.json"
    )
    if await hass.async_add_executor_job(os.path.exists, lang_path):
        try:
            data = await hass.async_add_executor_job(_read_json_file, lang_path)
            const.LOGGER.debug("Loaded %s dashboard translations", language)
            return data
        except (OSError, json.JSONDecodeError) as err:
            const.LOGGER.error("Error loading %s translations: %s", language, err)

    # Fall back to English if requested language not found or errored
    if language != "en":
        const.LOGGER.warning(
            "Language '%s' not found, falling back to English", language
        )
        en_path = os.path.join(
            translations_path, f"en{const.DASHBOARD_TRANSLATIONS_SUFFIX}.json"
        )
        if await hass.async_add_executor_job(os.path.exists, en_path):
            try:
                data = await hass.async_add_executor_job(_read_json_file, en_path)
                const.LOGGER.debug("Loaded English dashboard translations as fallback")
                return data
            except (OSError, json.JSONDecodeError) as err:
                const.LOGGER.error("Error loading English translations: %s", err)

    return {}


# ==============================================================================
# Notification Translation Helpers
# ==============================================================================


async def load_notification_translation(
    hass: HomeAssistant,
    language: str = "en",
) -> dict[str, dict[str, str]]:
    """Load notification translations for a specific language with English fallback.

    Uses module-level caching to avoid repeated file I/O when sending
    notifications to multiple approvers with the same language preference (v0.5.0+).

    Args:
        hass: Home Assistant instance
        language: Language code to load (e.g., 'en', 'es', 'de')

    Returns:
        A dict with notification keys mapping to {title, message} dicts.
        If the requested language is not found, returns English translations.
    """
    # Normalize language: default to English if empty/None
    if not language:
        language = "en"

    # Check cache first (v0.5.0+ performance improvement)
    cache_key = f"{language}_notification"
    if cache_key in _translation_cache:
        const.LOGGER.debug(
            "Notification translations for '%s' loaded from cache", language
        )
        return _translation_cache[cache_key]

    translations_path = _get_translations_path()

    if not await hass.async_add_executor_job(os.path.exists, translations_path):
        const.LOGGER.error(
            "Custom translations directory not found: %s", translations_path
        )
        return {}

    # Try to load the requested language (with _notifications suffix)
    lang_path = os.path.join(
        translations_path, f"{language}{const.NOTIFICATION_TRANSLATIONS_SUFFIX}.json"
    )
    if await hass.async_add_executor_job(os.path.exists, lang_path):
        try:
            data = await hass.async_add_executor_job(_read_json_file, lang_path)
            const.LOGGER.debug("Loaded %s notification translations", language)
            # Cache the loaded translations
            _translation_cache[cache_key] = data
            return data
        except (OSError, json.JSONDecodeError) as err:
            const.LOGGER.error(
                "Error loading %s notification translations: %s", language, err
            )

    # Fall back to English if requested language not found or errored
    if language != "en":
        const.LOGGER.warning(
            "Notification language '%s' not found, falling back to English", language
        )
        # Check if English is already cached
        en_cache_key = "en_notification"
        if en_cache_key in _translation_cache:
            const.LOGGER.debug("English notification translations loaded from cache")
            return _translation_cache[en_cache_key]

        en_path = os.path.join(
            translations_path, f"en{const.NOTIFICATION_TRANSLATIONS_SUFFIX}.json"
        )
        if await hass.async_add_executor_job(os.path.exists, en_path):
            try:
                data = await hass.async_add_executor_job(_read_json_file, en_path)
                const.LOGGER.debug(
                    "Loaded English notification translations as fallback"
                )
                # Cache English translations
                _translation_cache[en_cache_key] = data
                return data
            except (OSError, json.JSONDecodeError) as err:
                const.LOGGER.error(
                    "Error loading English notification translations: %s", err
                )
    else:
        # If we get here, English was requested but file not found
        const.LOGGER.error(
            "English notification translations not found at: %s",
            os.path.join(
                translations_path,
                f"en{const.NOTIFICATION_TRANSLATIONS_SUFFIX}.json",
            ),
        )

    return {}


# ==============================================================================
# Report Translation Helpers
# ==============================================================================


async def load_report_translation(
    hass: HomeAssistant,
    language: str = "en",
) -> dict[str, str]:
    """Load report translations for a specific language with English fallback.

    Uses module-level caching to avoid repeated file I/O for report rendering.

    Args:
        hass: Home Assistant instance
        language: Language code to load (e.g., 'en', 'es', 'de')

    Returns:
        A dict with report translation keys and string values.
    """
    if not language:
        language = const.DEFAULT_REPORT_LANGUAGE

    cache_key = f"{language}_report"
    if cache_key in _translation_cache:
        const.LOGGER.debug("Report translations for '%s' loaded from cache", language)
        return {k: str(v) for k, v in _translation_cache[cache_key].items()}

    translations_path = _get_translations_path()
    if not await hass.async_add_executor_job(os.path.exists, translations_path):
        const.LOGGER.error(
            "Custom translations directory not found: %s", translations_path
        )
        return {}

    lang_path = os.path.join(
        translations_path,
        f"{language}{const.REPORT_TRANSLATIONS_SUFFIX}.json",
    )
    if await hass.async_add_executor_job(os.path.exists, lang_path):
        try:
            data = await hass.async_add_executor_job(_read_json_file, lang_path)
            if isinstance(data, dict):
                _translation_cache[cache_key] = data
                const.LOGGER.debug("Loaded %s report translations", language)
                return {k: str(v) for k, v in data.items()}
        except (OSError, json.JSONDecodeError) as err:
            const.LOGGER.error(
                "Error loading %s report translations: %s", language, err
            )

    if language != "en":
        const.LOGGER.warning(
            "Report language '%s' not found, falling back to English", language
        )
        en_cache_key = "en_report"
        if en_cache_key in _translation_cache:
            return {k: str(v) for k, v in _translation_cache[en_cache_key].items()}

        en_path = os.path.join(
            translations_path,
            f"en{const.REPORT_TRANSLATIONS_SUFFIX}.json",
        )
        if await hass.async_add_executor_job(os.path.exists, en_path):
            try:
                data = await hass.async_add_executor_job(_read_json_file, en_path)
                if isinstance(data, dict):
                    _translation_cache[en_cache_key] = data
                    const.LOGGER.debug("Loaded English report translations as fallback")
                    return {k: str(v) for k, v in data.items()}
            except (OSError, json.JSONDecodeError) as err:
                const.LOGGER.error("Error loading English report translations: %s", err)
    else:
        const.LOGGER.error(
            "English report translations not found at: %s",
            os.path.join(
                translations_path,
                f"en{const.REPORT_TRANSLATIONS_SUFFIX}.json",
            ),
        )

    return {}


# ==============================================================================
# Cache Management
# ==============================================================================


def clear_translation_cache() -> None:
    """Clear the translation cache.

    Useful for testing or when translation files are updated.
    Call this when reloading the integration or during test teardown.
    """
    _translation_cache.clear()
    const.LOGGER.debug("Translation cache cleared")
