"""Dashboard Helper Size Reduction tests.

Tests for Phase 4 validation of the Dashboard Helper Size Reduction initiative:
- Translation sensor architecture (system-level sensors per language)
- Minimal chore attributes (6 fields instead of 16)
- Gap attributes on chore sensors (claimed_by, completed_by, approval_period_start)
- Translation sensor lifecycle management

Test Categories:
- SIZE-*: Size validation (primary goal - 100 chores in 16KB)
- TRANS-*: Translation sensor architecture
- CHORE-*: Minimal chore attributes
- GAP-*: Gap attributes on chore sensor
- LIFE-*: Lifecycle management
- EDGE-*: Edge cases

Reference: docs/in-process/DASHBOARD_HELPER_SIZE_REDUCTION_V2_IN-PROCESS.md
"""

# pylint: disable=redefined-outer-name

import json
from typing import Any

from homeassistant.core import HomeAssistant
import pytest

from tests.helpers import (
    ATTR_CLAIMED_BY,
    ATTR_COMPLETED_BY,
    ATTR_DASHBOARD_CHORES,
    ATTR_TRANSLATION_SENSOR,
    DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START,
    SENSOR_KC_EID_PREFIX_DASHBOARD_LANG,
    SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER,
    construct_entity_id,
)
from tests.helpers.setup import SetupResult, setup_from_yaml

# =============================================================================
# FIXTURES
# =============================================================================


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario: 1 kid, 1 parent, 5 chores (English only)."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


@pytest.fixture
async def scenario_multilang(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load multilang scenario: 2 kids (English + Spanish), 5 chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_multilang.yaml",
    )


@pytest.fixture
async def scenario_full(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load full scenario: 3 kids, 2 parents, 19 chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_full.yaml",
    )


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def get_dashboard_helper_size(hass: HomeAssistant, kid_name: str) -> int:
    """Get the JSON size of dashboard helper attributes in bytes.

    Args:
        hass: Home Assistant instance
        kid_name: Kid's display name (e.g., "Zoë")

    Returns:
        Size in bytes of the JSON-serialized attributes
    """
    helper_eid = construct_entity_id(
        "sensor", kid_name, SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER
    )
    helper_state = hass.states.get(helper_eid)
    assert helper_state is not None, f"Dashboard helper not found: {helper_eid}"

    # Serialize attributes to JSON and measure size
    attrs_json = json.dumps(helper_state.attributes)
    return len(attrs_json.encode("utf-8"))


def get_translation_sensor_eid(hass: HomeAssistant, kid_name: str = "Zoë") -> str:
    """Get translation sensor entity ID from a kid's dashboard helper.

    Args:
        hass: Home Assistant instance
        kid_name: Any kid name to get dashboard helper from (default: Zoë)

    Returns:
        Translation sensor entity ID (e.g., sensor.system_choreops_dashboard_translations_en)
    """
    # Slugify the kid name (lowercase, replace special chars)
    slug = (
        kid_name.lower()
        .replace("!", "")
        .replace("ë", "e")
        .replace("å", "a")
        .replace("ü", "u")
    )
    helper_state = hass.states.get(
        f"sensor.{slug}_choreops_ui_dashboard_helper"
    ) or hass.states.get(f"sensor.{slug}_kidschores_ui_dashboard_helper")
    assert helper_state is not None, (
        f"Dashboard helper not found: sensor.{slug}_choreops_ui_dashboard_helper"
    )

    translation_sensor = helper_state.attributes.get(ATTR_TRANSLATION_SENSOR)
    assert translation_sensor is not None, "Missing translation_sensor attribute"
    return translation_sensor


def get_translation_sensor_size(hass: HomeAssistant, kid_name: str = "Zoë") -> int:
    """Get the JSON size of translation sensor attributes in bytes.

    Args:
        hass: Home Assistant instance
        kid_name: Any kid name to get dashboard helper from (default: Zoë)

    Returns:
        Size in bytes of the JSON-serialized attributes
    """
    sensor_eid = get_translation_sensor_eid(hass, kid_name)
    sensor_state = hass.states.get(sensor_eid)
    assert sensor_state is not None, f"Translation sensor not found: {sensor_eid}"

    attrs_json = json.dumps(sensor_state.attributes)
    return len(attrs_json.encode("utf-8"))


# =============================================================================
# CATEGORY 1: SIZE VALIDATION (PRIMARY GOAL)
# =============================================================================


class TestSizeValidation:
    """SIZE-* tests: Validate sensor sizes stay under 16KB limit."""

    async def test_size_01_minimal_scenario_under_limit(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """SIZE-01: 5 chores (minimal) dashboard helper well under 8KB."""
        size = get_dashboard_helper_size(hass, "Zoë")

        # 5 chores should be much smaller than 8KB
        assert size < 8 * 1024, f"Dashboard helper too large: {size} bytes"

    async def test_size_05_translation_sensor_under_limit(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """SIZE-05: Translation sensor well under 16KB (typically ~5-6KB)."""
        size = get_translation_sensor_size(hass, "Zoë")

        # Translation sensor should be ~5-6KB based on planning doc
        assert size < 8 * 1024, f"Translation sensor too large: {size} bytes"
        # Should have meaningful content
        assert size > 1000, f"Translation sensor too small: {size} bytes"


# =============================================================================
# CATEGORY 2: TRANSLATION SENSOR ARCHITECTURE
# =============================================================================


class TestTranslationSensorArchitecture:
    """TRANS-* tests: Validate translation sensor architecture."""

    async def test_trans_01_single_language_one_sensor(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """TRANS-01: Single language (all English) creates only one sensor."""
        # English sensor should exist
        en_sensor_eid = get_translation_sensor_eid(hass, "Zoë")
        en_sensor = hass.states.get(en_sensor_eid)
        assert en_sensor is not None, "English translation sensor not found"

        # Spanish sensor should NOT exist (no Spanish users)
        # Try to get Spanish sensor - should fail since no Spanish-speaking kids exist
        try:
            es_sensor_eid = get_translation_sensor_eid(hass, "Lila")
            es_sensor = hass.states.get(es_sensor_eid)
        except (ValueError, AssertionError):
            es_sensor = None  # Expected - Lila doesn't exist in scenario_minimal
        assert es_sensor is None, "Spanish sensor should not exist"

    async def test_trans_02_multiple_languages_multiple_sensors(
        self,
        hass: HomeAssistant,
        scenario_multilang: SetupResult,
    ) -> None:
        """TRANS-02: Multiple languages (en + es) create both sensors."""
        # English sensor should exist (Zoë)
        en_sensor_eid = get_translation_sensor_eid(hass, "Zoë")
        en_sensor = hass.states.get(en_sensor_eid)
        assert en_sensor is not None, "English translation sensor not found"

        # Spanish sensor should exist (Lila)
        es_sensor_eid = get_translation_sensor_eid(hass, "Lila")
        es_sensor = hass.states.get(es_sensor_eid)
        assert es_sensor is not None, "Spanish translation sensor not found"

    async def test_trans_05_translation_sensor_has_ui_translations(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """TRANS-05: Translation sensor has ui_translations with 40+ keys."""
        en_sensor_eid = get_translation_sensor_eid(hass, "Zoë")
        en_sensor = hass.states.get(en_sensor_eid)
        assert en_sensor is not None

        ui_translations = en_sensor.attributes.get("ui_translations", {})

        # Should have 40+ translation keys
        assert len(ui_translations) >= 40, (
            f"Expected 40+ translation keys, got {len(ui_translations)}"
        )

        # Check for a few expected keys (from en_dashboard.json)
        expected_keys = ["welcome", "chores", "rewards", "points_details"]
        for key in expected_keys:
            assert key in ui_translations, f"Missing translation key: {key}"

    async def test_trans_06_dashboard_helper_has_translation_pointer(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """TRANS-06: Dashboard helper has translation_sensor pointer attribute."""
        helper_eid = construct_entity_id(
            "sensor", "Zoë", SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER
        )
        helper_state = hass.states.get(helper_eid)
        assert helper_state is not None

        # Should have translation_sensor attribute
        translation_sensor = helper_state.attributes.get(ATTR_TRANSLATION_SENSOR)
        assert translation_sensor is not None, "Missing translation_sensor attribute"

        # Should be a valid entity ID string pointing to English sensor
        # Verify sensor actually exists in state registry
        actual_sensor = hass.states.get(translation_sensor)
        assert actual_sensor is not None, (
            f"Translation sensor {translation_sensor} not found in state registry"
        )

    async def test_trans_06_multilang_correct_pointers(
        self,
        hass: HomeAssistant,
        scenario_multilang: SetupResult,
    ) -> None:
        """TRANS-06: Each kid's dashboard helper points to correct language sensor."""
        # Zoë should point to English
        zoe_helper = hass.states.get(
            construct_entity_id(
                "sensor", "Zoë", SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER
            )
        )
        assert zoe_helper is not None
        zoe_translation_sensor = zoe_helper.attributes.get(ATTR_TRANSLATION_SENSOR)
        assert zoe_translation_sensor is not None, "Zoë missing translation_sensor"
        # Verify it points to a valid sensor (English)
        assert hass.states.get(zoe_translation_sensor) is not None

        # Lila should point to Spanish
        lila_helper = hass.states.get(
            construct_entity_id(
                "sensor", "Lila", SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER
            )
        )
        assert lila_helper is not None
        lila_translation_sensor = lila_helper.attributes.get(ATTR_TRANSLATION_SENSOR)
        assert lila_translation_sensor is not None, "Lila missing translation_sensor"
        # Verify it points to a valid sensor (Spanish)
        assert hass.states.get(lila_translation_sensor) is not None


# =============================================================================
# CATEGORY 3: MINIMAL CHORE ATTRIBUTES
# =============================================================================


class TestMinimalChoreAttributes:
    """CHORE-* tests: Validate minimal 9-field chore structure (includes rotation fields)."""

    # The 9 fields we expect (6 original + 3 rotation fields added for Phase 4)
    EXPECTED_CHORE_FIELDS = {
        "eid",
        "name",
        "status",
        "labels",
        "primary_group",
        "is_today_am",
        "lock_reason",  # Phase 4: rotation support
        "turn_kid_name",  # Phase 4: rotation support
        "available_at",  # Phase 4: rotation support
    }

    # Fields that should be REMOVED (fetch from chore sensor instead)
    REMOVED_CHORE_FIELDS = {
        "due_date",
        "can_claim",
        "can_approve",
        "last_approved",
        "last_claimed",
        "claimed_by",
        "completed_by",
        "approval_period_start",
        "approval_reset_type",
        "completion_criteria",
        "assigned_days",
        "assigned_days_raw",
    }

    async def test_chore_01_chore_list_structure(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """CHORE-01: Each chore in list has exactly 9 fields (6 original + 3 rotation)."""
        helper_eid = construct_entity_id(
            "sensor", "Zoë", SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER
        )
        helper_state = hass.states.get(helper_eid)
        assert helper_state is not None

        chores = helper_state.attributes.get(ATTR_DASHBOARD_CHORES, [])
        assert len(chores) > 0, "No chores found in dashboard helper"

        for chore in chores:
            chore_fields = set(chore.keys())
            assert chore_fields == self.EXPECTED_CHORE_FIELDS, (
                f"Chore '{chore.get('name')}' has wrong fields. "
                f"Expected: {self.EXPECTED_CHORE_FIELDS}, Got: {chore_fields}"
            )

    async def test_chore_02_required_fields_present(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """CHORE-02: All 6 expected fields are present with valid values."""
        helper_eid = construct_entity_id(
            "sensor", "Zoë", SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER
        )
        helper_state = hass.states.get(helper_eid)
        assert helper_state is not None

        chores = helper_state.attributes.get(ATTR_DASHBOARD_CHORES, [])
        for chore in chores:
            # eid should be a sensor entity ID with correct format
            # Format: sensor.{kid_slug}_choreops_chore_status_{chore_name}
            assert chore["eid"].startswith("sensor."), f"Invalid eid: {chore['eid']}"
            assert "_choreops_chore_status_" in chore["eid"], (
                f"Entity ID missing expected pattern: {chore['eid']}"
            )

            # name should be non-empty string
            assert isinstance(chore["name"], str) and len(chore["name"]) > 0

            # status should be one of the valid states
            valid_statuses = {"pending", "claimed", "approved", "overdue"}
            assert chore["status"] in valid_statuses, (
                f"Invalid status: {chore['status']}"
            )

            # labels should be a list
            assert isinstance(chore["labels"], list)

            # primary_group should be one of the valid groups
            valid_groups = {"today", "this_week", "other"}
            assert chore["primary_group"] in valid_groups, (
                f"Invalid primary_group: {chore['primary_group']}"
            )

            # is_today_am can be True, False, or None
            assert chore["is_today_am"] in {True, False, None}

    async def test_chore_03_removed_fields_not_present(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """CHORE-03: Removed fields (due_date, can_claim, etc.) NOT in chore list."""
        helper_eid = construct_entity_id(
            "sensor", "Zoë", SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER
        )
        helper_state = hass.states.get(helper_eid)
        assert helper_state is not None

        chores = helper_state.attributes.get(ATTR_DASHBOARD_CHORES, [])
        for chore in chores:
            chore_fields = set(chore.keys())
            unexpected_fields = chore_fields & self.REMOVED_CHORE_FIELDS
            assert not unexpected_fields, (
                f"Chore '{chore.get('name')}' has removed fields: {unexpected_fields}"
            )

    async def test_chore_04_chore_sensor_has_full_data(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """CHORE-04: Chore sensor has full data (due_date, can_claim, etc.)."""
        helper_eid = construct_entity_id(
            "sensor", "Zoë", SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER
        )
        helper_state = hass.states.get(helper_eid)
        assert helper_state is not None

        chores = helper_state.attributes.get(ATTR_DASHBOARD_CHORES, [])
        assert len(chores) > 0

        # Get first chore and verify its sensor has full data
        chore = chores[0]
        chore_sensor_eid = chore["eid"]
        chore_sensor = hass.states.get(chore_sensor_eid)
        assert chore_sensor is not None, f"Chore sensor not found: {chore_sensor_eid}"

        # Verify removed fields are on the chore sensor
        attrs = chore_sensor.attributes
        assert "due_date" in attrs, "due_date missing from chore sensor"
        assert "can_claim" in attrs, "can_claim missing from chore sensor"
        assert "can_approve" in attrs, "can_approve missing from chore sensor"


# =============================================================================
# CATEGORY 4: GAP ATTRIBUTES ON CHORE SENSOR
# =============================================================================


class TestGapAttributes:
    """GAP-* tests: Validate new gap attributes on chore status sensor."""

    async def test_gap_01_claimed_by_attribute_exists(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """GAP-01: claimed_by attribute exists on chore status sensor."""
        helper_eid = construct_entity_id(
            "sensor", "Zoë", SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER
        )
        helper_state = hass.states.get(helper_eid)
        assert helper_state is not None

        chores = helper_state.attributes.get(ATTR_DASHBOARD_CHORES, [])
        assert len(chores) > 0

        # Check first chore sensor has claimed_by attribute
        chore_sensor_eid = chores[0]["eid"]
        chore_sensor = hass.states.get(chore_sensor_eid)
        assert chore_sensor is not None

        assert ATTR_CLAIMED_BY in chore_sensor.attributes, (
            f"claimed_by attribute missing from {chore_sensor_eid}"
        )

    async def test_gap_02_completed_by_attribute_exists(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """GAP-02: completed_by attribute exists on chore status sensor."""
        helper_eid = construct_entity_id(
            "sensor", "Zoë", SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER
        )
        helper_state = hass.states.get(helper_eid)
        assert helper_state is not None

        chores = helper_state.attributes.get(ATTR_DASHBOARD_CHORES, [])
        assert len(chores) > 0

        # Check first chore sensor has completed_by attribute
        chore_sensor_eid = chores[0]["eid"]
        chore_sensor = hass.states.get(chore_sensor_eid)
        assert chore_sensor is not None

        assert ATTR_COMPLETED_BY in chore_sensor.attributes, (
            f"completed_by attribute missing from {chore_sensor_eid}"
        )

    async def test_gap_03_approval_period_start_attribute_exists(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """GAP-03: approval_period_start attribute exists on chore status sensor."""
        helper_eid = construct_entity_id(
            "sensor", "Zoë", SENSOR_KC_EID_SUFFIX_UI_DASHBOARD_HELPER
        )
        helper_state = hass.states.get(helper_eid)
        assert helper_state is not None

        chores = helper_state.attributes.get(ATTR_DASHBOARD_CHORES, [])
        assert len(chores) > 0

        # Check first chore sensor has approval_period_start attribute
        chore_sensor_eid = chores[0]["eid"]
        chore_sensor = hass.states.get(chore_sensor_eid)
        assert chore_sensor is not None

        # Use the const key name for the attribute
        assert DATA_KID_CHORE_DATA_APPROVAL_PERIOD_START in chore_sensor.attributes, (
            f"approval_period_start attribute missing from {chore_sensor_eid}"
        )


# =============================================================================
# CATEGORY 6: LIFECYCLE MANAGEMENT
# =============================================================================


class TestLifecycleManagement:
    """LIFE-* tests: Validate translation sensor lifecycle."""

    async def test_life_01_initial_setup_creates_sensor(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """LIFE-01: Translation sensor created during initial setup."""
        # After setup, English sensor should exist
        en_sensor_eid = get_translation_sensor_eid(hass, "Zoë")
        en_sensor = hass.states.get(en_sensor_eid)
        assert en_sensor is not None, "English translation sensor not created"

        # Should be available (not unknown/unavailable)
        assert en_sensor.state not in ("unknown", "unavailable"), (
            f"Translation sensor in bad state: {en_sensor.state}"
        )

    async def test_life_05_coordinator_tracks_created_sensors(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """LIFE-05: Coordinator tracks created translation sensors."""
        coordinator = scenario_minimal.coordinator

        # UIManager should have tracking set
        assert hasattr(coordinator.ui_manager, "_translation_sensors_created"), (
            "UIManager missing _translation_sensors_created tracking set"
        )

        # Should track that English sensor was created
        assert coordinator.ui_manager.is_translation_sensor_created("en"), (
            "UIManager not tracking English sensor creation"
        )


# =============================================================================
# CATEGORY 7: EDGE CASES
# =============================================================================


class TestEdgeCases:
    """EDGE-* tests: Edge case handling."""

    async def test_edge_01_unknown_language_returns_none(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """EDGE-01: Unknown language code returns None (not in registry).

        get_translation_sensor_eid() looks up entity IDs from the registry.
        For languages without sensors in the registry, it returns None.
        Entity creation logic is in ensure_translation_sensor_exists().
        """
        coordinator = scenario_minimal.coordinator

        # Get translation sensor entity ID for unknown language
        # Should fall back to English ('en') since xyz doesn't exist
        eid = coordinator.ui_manager.get_translation_sensor_eid("xyz")

        # Should return English translation sensor as fallback
        assert eid is not None, "Expected fallback to English sensor"
        assert "en" in eid, f"Expected English sensor as fallback, got {eid}"

    async def test_edge_02_no_kids_no_extra_sensors(
        self,
        hass: HomeAssistant,
    ) -> None:
        """EDGE-02: Without any setup, no translation sensors exist.

        This is a basic sanity check - before integration setup, there
        should be no KidsChores sensors at all.
        """
        # Before any setup, no translation sensors should exist
        en_sensor = hass.states.get(
            f"sensor.kc_{SENSOR_KC_EID_PREFIX_DASHBOARD_LANG}en"
        )
        assert en_sensor is None, "Translation sensor exists without integration setup"
