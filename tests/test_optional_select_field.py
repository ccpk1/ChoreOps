"""Test optional select field behavior in config flows."""

from unittest.mock import MagicMock, patch

from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_validation as cv
import pytest
import voluptuous_serialize

from custom_components.kidschores import const
from custom_components.kidschores.helpers.flow_helpers import build_parent_schema


class TestOptionalSelectFieldValidation:
    """Test optional SelectSelector field validation with different values."""

    @pytest.fixture
    def mock_users(self):
        """Create mock HA users."""
        user1 = MagicMock()
        user1.id = "user_id_123"
        user1.name = "Test User"
        return [user1]

    @pytest.fixture
    def kids_dict(self):
        """Sample kids dictionary."""
        return {"TestKid": "kid_internal_id_abc"}

    async def test_schema_serialization(
        self,
        hass: HomeAssistant,
        mock_users,
        kids_dict,
    ):
        """Test that the schema can be serialized by HA for the frontend."""
        with patch(
            "custom_components.kidschores.helpers.translation_helpers.get_available_dashboard_languages",
            return_value=["en"],
        ):
            schema = await build_parent_schema(
                hass=hass,
                users=mock_users,
                kids_dict=kids_dict,
            )

        # This is what HA does to send schema to frontend
        try:
            serialized = voluptuous_serialize.convert(
                schema, custom_serializer=cv.custom_serializer
            )
            assert serialized is not None, "Schema should serialize"
            assert len(serialized) > 0, "Schema should have fields"
        except Exception as e:
            pytest.fail(f"Schema serialization failed: {e}")

    @pytest.mark.parametrize(
        ("ha_user_value", "should_pass", "description"),
        [
            # SENTINEL_NO_SELECTION - the "None" option value (non-empty sentinel)
            ("__none__", True, "SENTINEL_NO_SELECTION (None option)"),
            # Empty string - no longer valid (not in SelectSelector options)
            ("", False, "Empty string - not in options"),
            # Valid user ID
            ("user_id_123", True, "Valid user ID"),
            # Python None - SelectSelector requires string, so this should fail
            (None, False, "Python None - rejected by SelectSelector (requires str)"),
            # Missing key entirely - uses default value
            ("__MISSING__", True, "Key not in input at all"),
        ],
    )
    async def test_parent_schema_ha_user_validation(
        self,
        hass: HomeAssistant,
        mock_users,
        kids_dict,
        ha_user_value,
        should_pass,
        description,
    ):
        """Test that parent schema validates different HA user values correctly."""
        # Build the schema
        with patch(
            "custom_components.kidschores.helpers.translation_helpers.get_available_dashboard_languages",
            return_value=["en"],
        ):
            schema = await build_parent_schema(
                hass=hass,
                users=mock_users,
                kids_dict=kids_dict,
            )

        # Build test input
        test_input = {
            const.CFOF_PARENTS_INPUT_NAME: "Test Parent",
        }

        # Add HA user field unless testing missing key
        if ha_user_value != "__MISSING__":
            test_input[const.CFOF_PARENTS_INPUT_HA_USER] = ha_user_value

        # Try to validate
        try:
            validated = schema(test_input)
            passed = True
            # Verify the validated result exists (don't need the value)
            _ = validated.get(const.CFOF_PARENTS_INPUT_HA_USER)
        except Exception:
            passed = False

        assert passed == should_pass, (
            f"{description}: expected pass={should_pass}, got pass={passed}"
        )

    async def test_what_value_ha_sends_for_none_selection(
        self,
        hass: HomeAssistant,
        mock_users,
        kids_dict,
    ):
        """Test that SENTINEL_NO_SELECTION ('__none__') is accepted for None selection.

        The schema uses SENTINEL_NO_SELECTION instead of empty string because
        Home Assistant's SelectSelector has issues tracking empty string selections.
        """
        with patch(
            "custom_components.kidschores.helpers.translation_helpers.get_available_dashboard_languages",
            return_value=["en"],
        ):
            schema = await build_parent_schema(
                hass=hass,
                users=mock_users,
                kids_dict=kids_dict,
            )

        # Test various possible values HA might send
        test_cases = [
            ("sentinel_none", const.SENTINEL_NO_SELECTION),  # Should pass
            ("empty_string", ""),  # Should fail - not in options
            ("python_none", None),  # Should fail - type error
            ("string_none", "none"),  # Should fail - not in options
            ("string_None", "None"),  # Should fail - not in options
        ]

        results = {}
        for name, value in test_cases:
            test_input = {
                const.CFOF_PARENTS_INPUT_NAME: "Test Parent",
                const.CFOF_PARENTS_INPUT_HA_USER: value,
            }
            try:
                validated = schema(test_input)
                results[name] = (
                    f"PASS: {validated.get(const.CFOF_PARENTS_INPUT_HA_USER)!r}"
                )
            except Exception as e:
                results[name] = f"FAIL: {e}"

        # Verify we captured all test cases
        assert len(results) == len(test_cases), "All test cases should be captured"

        # SENTINEL_NO_SELECTION should work - it's the "None" option value
        assert "PASS" in results["sentinel_none"], (
            "SENTINEL_NO_SELECTION MUST pass - it's the 'None' option value"
        )

        # Empty string should NOT work - not in SelectSelector options anymore
        assert "FAIL" in results["empty_string"], (
            "Empty string should fail - not in SelectSelector options"
        )
