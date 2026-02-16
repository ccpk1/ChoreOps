"""Validation helpers for KidsChores integration tests.

Provides assertion helpers and entity counting utilities.

Usage:
    from tests.helpers import (
        assert_entity_exists, assert_state_equals, assert_points_changed,
        count_entities_by_platform, verify_kid_entities,
    )

    # Assert entity exists
    assert_entity_exists(hass, "sensor.zoe_kidschores_star_points")

    # Assert state equals expected value
    assert_state_equals(hass, "sensor.zoe_kidschores_star_points", "100")

    # Assert points changed by expected amount
    assert_points_changed(result, expected_change=10.0)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from homeassistant.core import HomeAssistant

    from tests.helpers.workflows import WorkflowResult

# =============================================================================
# BASIC ENTITY ASSERTIONS
# =============================================================================


def assert_entity_exists(
    hass: HomeAssistant,
    entity_id: str,
    message: str | None = None,
) -> None:
    """Assert that an entity exists in Home Assistant.

    Args:
        hass: Home Assistant instance
        entity_id: Entity ID to check
        message: Optional custom failure message

    Raises:
        AssertionError: If entity doesn't exist
    """
    state = hass.states.get(entity_id)
    if state is None:
        msg = message or f"Entity not found: {entity_id}"
        raise AssertionError(msg)


def assert_entity_not_exists(
    hass: HomeAssistant,
    entity_id: str,
    message: str | None = None,
) -> None:
    """Assert that an entity does NOT exist in Home Assistant.

    Args:
        hass: Home Assistant instance
        entity_id: Entity ID to check
        message: Optional custom failure message

    Raises:
        AssertionError: If entity exists
    """
    state = hass.states.get(entity_id)
    if state is not None:
        msg = message or f"Entity should not exist: {entity_id}"
        raise AssertionError(msg)


def assert_state_equals(
    hass: HomeAssistant,
    entity_id: str,
    expected_state: str,
    message: str | None = None,
) -> None:
    """Assert that an entity's state equals expected value.

    Args:
        hass: Home Assistant instance
        entity_id: Entity ID to check
        expected_state: Expected state value
        message: Optional custom failure message

    Raises:
        AssertionError: If state doesn't match
    """
    state = hass.states.get(entity_id)
    if state is None:
        raise AssertionError(f"Entity not found: {entity_id}")

    if state.state != expected_state:
        msg = message or (
            f"State mismatch for {entity_id}: expected '{expected_state}', got '{state.state}'"
        )
        raise AssertionError(msg)


def assert_state_not_equals(
    hass: HomeAssistant,
    entity_id: str,
    unexpected_state: str,
    message: str | None = None,
) -> None:
    """Assert that an entity's state does NOT equal a value.

    Args:
        hass: Home Assistant instance
        entity_id: Entity ID to check
        unexpected_state: State value that should not be present
        message: Optional custom failure message

    Raises:
        AssertionError: If state matches unexpected value
    """
    state = hass.states.get(entity_id)
    if state is None:
        raise AssertionError(f"Entity not found: {entity_id}")

    if state.state == unexpected_state:
        msg = message or f"State should not be '{unexpected_state}' for {entity_id}"
        raise AssertionError(msg)


def assert_attribute_equals(
    hass: HomeAssistant,
    entity_id: str,
    attribute_name: str,
    expected_value: Any,
    message: str | None = None,
) -> None:
    """Assert that an entity attribute equals expected value.

    Args:
        hass: Home Assistant instance
        entity_id: Entity ID to check
        attribute_name: Name of attribute
        expected_value: Expected attribute value
        message: Optional custom failure message

    Raises:
        AssertionError: If attribute doesn't match
    """
    state = hass.states.get(entity_id)
    if state is None:
        raise AssertionError(f"Entity not found: {entity_id}")

    actual_value = state.attributes.get(attribute_name)
    if actual_value != expected_value:
        msg = message or (
            f"Attribute '{attribute_name}' mismatch for {entity_id}: "
            f"expected '{expected_value}', got '{actual_value}'"
        )
        raise AssertionError(msg)


def assert_state_in(
    hass: HomeAssistant,
    entity_id: str,
    valid_states: list[str],
    message: str | None = None,
) -> None:
    """Assert that an entity's state is one of the valid states.

    Args:
        hass: Home Assistant instance
        entity_id: Entity ID to check
        valid_states: List of acceptable state values
        message: Optional custom failure message

    Raises:
        AssertionError: If state not in valid states
    """
    state = hass.states.get(entity_id)
    if state is None:
        raise AssertionError(f"Entity not found: {entity_id}")

    if state.state not in valid_states:
        msg = message or (
            f"State '{state.state}' for {entity_id} not in valid states: {valid_states}"
        )
        raise AssertionError(msg)


# =============================================================================
# WORKFLOW RESULT ASSERTIONS
# =============================================================================


def assert_workflow_success(
    result: WorkflowResult,
    message: str | None = None,
) -> None:
    """Assert that a workflow completed successfully.

    Args:
        result: WorkflowResult from workflow helper
        message: Optional custom failure message

    Raises:
        AssertionError: If workflow failed
    """
    if not result.success:
        msg = message or f"Workflow failed: {result.error}"
        raise AssertionError(msg)


def assert_workflow_failed(
    result: WorkflowResult,
    expected_error: str | None = None,
    message: str | None = None,
) -> None:
    """Assert that a workflow failed (optionally with specific error).

    Args:
        result: WorkflowResult from workflow helper
        expected_error: Optional substring to check in error message
        message: Optional custom failure message

    Raises:
        AssertionError: If workflow succeeded or wrong error
    """
    if result.success:
        msg = message or "Workflow should have failed but succeeded"
        raise AssertionError(msg)

    if expected_error and expected_error not in (result.error or ""):
        msg = message or (
            f"Expected error containing '{expected_error}', got '{result.error}'"
        )
        raise AssertionError(msg)


def assert_points_changed(
    result: WorkflowResult,
    expected_change: float,
    tolerance: float = 0.01,
    message: str | None = None,
) -> None:
    """Assert that points changed by expected amount.

    Args:
        result: WorkflowResult from workflow helper
        expected_change: Expected points difference (positive = earned, negative = spent)
        tolerance: Acceptable variance (default 0.01 for float comparison)
        message: Optional custom failure message

    Raises:
        AssertionError: If points change doesn't match
    """
    actual_change = result.points_changed

    if abs(actual_change - expected_change) > tolerance:
        msg = message or (
            f"Points change mismatch: expected {expected_change}, "
            f"got {actual_change} (before={result.points_before}, "
            f"after={result.points_after})"
        )
        raise AssertionError(msg)


def assert_points_unchanged(
    result: WorkflowResult,
    tolerance: float = 0.01,
    message: str | None = None,
) -> None:
    """Assert that points did not change.

    Args:
        result: WorkflowResult from workflow helper
        tolerance: Acceptable variance
        message: Optional custom failure message

    Raises:
        AssertionError: If points changed
    """
    if abs(result.points_changed) > tolerance:
        msg = message or (
            f"Points should not have changed but changed by {result.points_changed}"
        )
        raise AssertionError(msg)


def assert_state_transition(
    result: WorkflowResult,
    expected_before: str,
    expected_after: str,
    message: str | None = None,
) -> None:
    """Assert that state transitioned as expected.

    Args:
        result: WorkflowResult from workflow helper
        expected_before: Expected state before action
        expected_after: Expected state after action
        message: Optional custom failure message

    Raises:
        AssertionError: If state transition doesn't match
    """
    if result.state_before != expected_before:
        msg = message or (
            f"State before mismatch: expected '{expected_before}', got '{result.state_before}'"
        )
        raise AssertionError(msg)

    if result.state_after != expected_after:
        msg = message or (
            f"State after mismatch: expected '{expected_after}', got '{result.state_after}'"
        )
        raise AssertionError(msg)


def assert_due_date_advanced(
    result: WorkflowResult,
    message: str | None = None,
) -> None:
    """Assert that due date was advanced.

    Args:
        result: WorkflowResult from workflow helper
        message: Optional custom failure message

    Raises:
        AssertionError: If due date didn't change
    """
    if not result.due_date_advanced:
        msg = message or (
            f"Due date should have advanced but didn't: "
            f"before={result.due_date_before}, after={result.due_date_after}"
        )
        raise AssertionError(msg)


# =============================================================================
# ENTITY COUNTING
# =============================================================================


def count_entities_by_platform(
    hass: HomeAssistant,
    platform: str,
    suffix: str = "_kidschores_",
) -> int:
    """Count KidsChores entities for a specific platform.

    Args:
        hass: Home Assistant instance
        platform: Platform name (sensor, button, etc.)
        suffix: Entity ID suffix to filter (default "_kidschores_")

    Returns:
        Count of matching entities
    """
    count = 0

    for entity_id in hass.states.async_entity_ids(platform):
        if suffix in entity_id:
            count += 1

    return count


def count_entities_by_kid(
    hass: HomeAssistant,
    kid_slug: str,
    platform: str | None = None,
) -> int:
    """Count entities for a specific kid.

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug (e.g., "zoe")
        platform: Optional platform filter

    Returns:
        Count of matching entities
    """
    count = 0
    kid_pattern = f"{kid_slug}_kidschores_"

    platforms = [platform] if platform else ["sensor", "button", "select", "datetime"]

    for p in platforms:
        for entity_id in hass.states.async_entity_ids(p):
            if kid_pattern in entity_id:
                count += 1

    return count


def get_kid_entity_ids(
    hass: HomeAssistant,
    kid_slug: str,
    platform: str | None = None,
) -> list[str]:
    """Get all entity IDs for a specific kid.

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug (e.g., "zoe")
        platform: Optional platform filter

    Returns:
        List of matching entity IDs
    """
    entity_ids = []
    kid_pattern = f"{kid_slug}_kidschores_"

    platforms = [platform] if platform else ["sensor", "button", "select", "datetime"]

    for p in platforms:
        for entity_id in hass.states.async_entity_ids(p):
            if kid_pattern in entity_id:
                entity_ids.append(entity_id)

    return sorted(entity_ids)


# =============================================================================
# ENTITY VERIFICATION (from entity_validation_helpers.py)
# =============================================================================


def verify_kid_entities(
    hass: HomeAssistant,
    kid_slug: str,
    expected_sensors: list[str] | None = None,
    expected_buttons: list[str] | None = None,
    validator: Callable[[str, Any], bool] | None = None,
) -> dict[str, Any]:
    """Verify entities exist for a kid with expected states.

    Args:
        hass: Home Assistant instance
        kid_slug: Kid's slug
        expected_sensors: List of sensor suffixes to verify (e.g., ["points", "chores_completed"])
        expected_buttons: List of button suffixes to verify
        validator: Optional custom validation function (entity_id, state) -> bool

    Returns:
        Dict with verification results: {
            "valid": bool,
            "missing": list of missing entity IDs,
            "invalid": list of entities that failed validation,
            "entities": dict of entity_id -> state
        }
    """
    result: dict[str, Any] = {
        "valid": True,
        "missing": [],
        "invalid": [],
        "entities": {},
    }

    # Check sensors
    if expected_sensors:
        for suffix in expected_sensors:
            entity_id = f"sensor.{kid_slug}_kidschores_{suffix}"
            state = hass.states.get(entity_id)

            if state is None:
                result["missing"].append(entity_id)
                result["valid"] = False
            else:
                result["entities"][entity_id] = state.state
                if validator and not validator(entity_id, state):
                    result["invalid"].append(entity_id)
                    result["valid"] = False

    # Check buttons
    if expected_buttons:
        for suffix in expected_buttons:
            entity_id = f"button.{kid_slug}_kidschores_{suffix}"
            state = hass.states.get(entity_id)

            if state is None:
                result["missing"].append(entity_id)
                result["valid"] = False
            else:
                result["entities"][entity_id] = state.state
                if validator and not validator(entity_id, state):
                    result["invalid"].append(entity_id)
                    result["valid"] = False

    return result


def verify_entity_state(
    hass: HomeAssistant,
    entity_id: str,
    expected_state: str | None = None,
    expected_attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Verify an entity has expected state and attributes.

    Args:
        hass: Home Assistant instance
        entity_id: Entity ID to verify
        expected_state: Expected state value (optional)
        expected_attributes: Expected attribute values (optional)

    Returns:
        Dict with verification results: {
            "valid": bool,
            "exists": bool,
            "state": actual state,
            "state_match": bool,
            "attribute_mismatches": dict of attr -> (expected, actual)
        }
    """
    result: dict[str, Any] = {
        "valid": True,
        "exists": False,
        "state": None,
        "state_match": True,
        "attribute_mismatches": {},
    }

    state = hass.states.get(entity_id)

    if state is None:
        result["valid"] = False
        return result

    result["exists"] = True
    result["state"] = state.state

    # Check state
    if expected_state is not None and state.state != expected_state:
        result["state_match"] = False
        result["valid"] = False

    # Check attributes
    if expected_attributes:
        for attr, expected_value in expected_attributes.items():
            actual_value = state.attributes.get(attr)
            if actual_value != expected_value:
                result["attribute_mismatches"][attr] = (expected_value, actual_value)
                result["valid"] = False

    return result


# =============================================================================
# BATCH OPERATIONS
# =============================================================================


def get_all_entity_states(
    hass: HomeAssistant,
    entity_ids: list[str],
) -> dict[str, str | None]:
    """Get states for multiple entities.

    Args:
        hass: Home Assistant instance
        entity_ids: List of entity IDs

    Returns:
        Dict mapping entity_id -> state (None if not found)
    """
    return {
        eid: (state.state if (state := hass.states.get(eid)) else None)
        for eid in entity_ids
    }


def assert_all_entities_exist(
    hass: HomeAssistant,
    entity_ids: list[str],
    message: str | None = None,
) -> None:
    """Assert that all entities in list exist.

    Args:
        hass: Home Assistant instance
        entity_ids: List of entity IDs to check
        message: Optional custom failure message

    Raises:
        AssertionError: If any entity doesn't exist
    """
    missing = [eid for eid in entity_ids if hass.states.get(eid) is None]

    if missing:
        msg = message or f"Missing entities: {missing}"
        raise AssertionError(msg)


def assert_all_states_equal(
    hass: HomeAssistant,
    entity_ids: list[str],
    expected_state: str,
    message: str | None = None,
) -> None:
    """Assert that all entities have the same expected state.

    Args:
        hass: Home Assistant instance
        entity_ids: List of entity IDs to check
        expected_state: Expected state for all entities
        message: Optional custom failure message

    Raises:
        AssertionError: If any entity has wrong state
    """
    mismatches = {}

    for eid in entity_ids:
        state = hass.states.get(eid)
        if state is None:
            mismatches[eid] = "NOT_FOUND"
        elif state.state != expected_state:
            mismatches[eid] = state.state

    if mismatches:
        msg = message or (
            f"State mismatches (expected '{expected_state}'): {mismatches}"
        )
        raise AssertionError(msg)
