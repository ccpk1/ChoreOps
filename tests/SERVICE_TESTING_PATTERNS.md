# Service Testing Patterns

**Purpose**: Document proper patterns for testing Home Assistant services to ensure schema validation works correctly.

## The Problem We Had

Our reward CRUD service tests passed but the actual services failed in Developer Tools because:

1. **Tests didn't trigger schema validation** - We used correct constants programmatically
2. **Constants had wrong values** - `SERVICE_FIELD_REWARD_COST = "cost"` should be `"reward_cost"`
3. **services.yaml didn't match schema** - Documentation showed wrong field names

**Result**: Tests passed, but real-world service calls failed with schema validation errors.

## Key Insight: How HA Validates Services

When you call `hass.services.async_call()`, Home Assistant:

1. **Looks up the service** in the registry
2. **Validates data against the schema** registered for that service
3. **Raises `vol.Invalid` or `vol.MultipleInvalid`** if validation fails
4. **Only then calls the handler** if validation passes

**This means**: If your test calls `async_call()` successfully, the schema IS being validated!

## Pattern 1: Test Schema Validation Works (Positive Test)

```python
async def test_create_reward_with_valid_data(hass, scenario_full):
    """Test that create_reward accepts correct field names."""
    coordinator = scenario_full.coordinator

    # This will raise vol.Invalid if schema is wrong
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_REWARD,
        {
            "reward_name": "Test Reward",  # Must match SERVICE_FIELD_REWARD_NAME value
            "reward_cost": 100.0,          # Must match SERVICE_FIELD_REWARD_COST value
            "reward_description": "Test",  # Must match SERVICE_FIELD_REWARD_DESCRIPTION value
        },
        blocking=True,
        return_response=True,
    )

    # Verify service executed (schema validation passed)
    assert response is not None
    assert "reward_id" in response
```

## Pattern 2: Test Schema Rejects Invalid Data (Negative Test)

```python
async def test_create_reward_rejects_wrong_fields(hass, scenario_full):
    """Test that create_reward rejects incorrect field names."""
    import voluptuous as vol

    # Try with old/wrong field name - should raise vol.Invalid
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_REWARD,
            {
                "name": "Test Reward",  # ❌ Wrong - schema expects "reward_name"
                "cost": 100.0,          # ❌ Wrong - schema expects "reward_cost"
            },
            blocking=True,
        )
```

## Pattern 3: Test Missing Required Fields

```python
async def test_create_reward_requires_name(hass, scenario_full):
    """Test that create_reward requires reward_name field."""
    import voluptuous as vol

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_REWARD,
            {
                "reward_cost": 100.0,  # Missing required "reward_name"
            },
            blocking=True,
        )
```

## Pattern 4: Test Extra Keys Rejected

```python
async def test_create_reward_rejects_extra_keys(hass, scenario_full):
    """Test that create_reward rejects unexpected fields."""
    import voluptuous as vol

    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_CREATE_REWARD,
            {
                "reward_name": "Test",
                "reward_cost": 100.0,
                "invalid_field": "should fail",  # ❌ Extra key not in schema
            },
            blocking=True,
        )
```

## Pattern 5: Test Service Response Data

```python
async def test_create_reward_returns_reward_id(hass, scenario_full):
    """Test that create_reward returns the new reward_id."""
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_REWARD,
        {
            "reward_name": "Test Reward",
            "reward_cost": 100.0,
        },
        blocking=True,
        return_response=True,
    )

    # Verify response structure
    assert response is not None
    assert isinstance(response, dict)
    assert "reward_id" in response
    assert isinstance(response["reward_id"], str)

    # Verify reward was actually created
    reward_id = response["reward_id"]
    assert reward_id in scenario_full.coordinator.rewards_data
```

## Pattern 6: E2E Test - Verify Entity State After Service Call

**This is the preferred E2E pattern per AGENT_TEST_CREATION_INSTRUCTIONS.md**:

```python
async def test_create_reward_appears_in_dashboard_helper(
    hass, scenario_full, mock_hass_users
):
    """Test that created reward appears in dashboard helper (E2E)."""

    # Create reward via service
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_REWARD,
        {
            "reward_name": "Dashboard Test Reward",
            "reward_cost": 150.0,
        },
        blocking=True,
        return_response=True,
    )

    reward_id = response["reward_id"]

    # Wait for coordinator update
    await hass.async_block_till_done()

    # Verify appears in dashboard helper for all assignees
    for assignee_name in ["Zoë", "Max!", "Lila"]:
        assignee_slug = assignee_name.lower().replace("!", "").replace("ë", "e")
        helper_eid = f"sensor.kc_{assignee_slug}_ui_dashboard_helper"

        helper_state = hass.states.get(helper_eid)
        assert helper_state is not None

        rewards_list = helper_state.attributes.get("rewards", [])

        # Find our new reward in the list
        found = False
        for reward in rewards_list:
            if reward.get("name") == "Dashboard Test Reward":
                found = True
                assert reward["cost"] == 150.0
                break

        assert found, f"Reward not found in {helper_eid}"
```

## Why Tests Didn't Catch Our Bug

### What We Did Wrong

```python
# In deleted test_reward_crud_services.py
response = await hass.services.async_call(
    DOMAIN,
    SERVICE_CREATE_REWARD,
    {
        SERVICE_FIELD_REWARD_NAME: "Test",  # ✅ Used constant
        SERVICE_FIELD_REWARD_COST: 100.0,   # ✅ Used constant
    },
    blocking=True,
    return_response=True,
)
```

**Why it passed**:

- Constants resolved to correct VALUES at test time
- Schema validation used same constants
- Everything matched programmatically

**Why it failed in Developer Tools**:

- User typed `reward_cost` (from services.yaml documentation)
- Schema expected `cost` (from constant VALUE)
- Mismatch → validation error

### How to Prevent This

**✅ Always include literal string tests**:

```python
async def test_create_reward_literal_field_names(hass, scenario_full):
    """Test create_reward with field names as documented in services.yaml.

    This catches schema/documentation mismatches that constant-based
    tests would miss.
    """
    # Use exact strings a user would type from services.yaml
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_CREATE_REWARD,
        {
            "reward_name": "Literal Test",    # From services.yaml docs
            "reward_cost": 100.0,             # From services.yaml docs
            "reward_description": "Testing",  # From services.yaml docs
        },
        blocking=True,
        return_response=True,
    )

    assert response["reward_id"] is not None
```

## Complete Test Suite Template

```python
"""Tests for reward CRUD services.

Tests both schema validation AND end-to-end functionality.
"""

import pytest
import voluptuous as vol

from homeassistant.core import HomeAssistant
from tests.helpers import SetupResult, setup_from_yaml


@pytest.fixture
async def scenario_full(
    hass: HomeAssistant,
    mock_hass_users: dict,
) -> SetupResult:
    """Load full scenario."""
    return await setup_from_yaml(
        hass, mock_hass_users, "tests/scenarios/scenario_full.yaml"
    )


class TestCreateRewardSchemaValidation:
    """Test create_reward schema validation."""

    async def test_accepts_correct_fields(self, hass, scenario_full):
        """Test service accepts documented field names."""
        # Use literal strings from services.yaml
        response = await hass.services.async_call(
            "assigneeschores",
            "create_reward",
            {
                "reward_name": "Schema Test",
                "reward_cost": 75.0,
            },
            blocking=True,
            return_response=True,
        )
        assert response["reward_id"] is not None

    async def test_rejects_old_field_names(self, hass, scenario_full):
        """Test service rejects undocumented field names."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                "assigneeschores",
                "create_reward",
                {
                    "name": "Test",  # Old field name
                    "cost": 75.0,    # Old field name
                },
                blocking=True,
            )

    async def test_requires_name_field(self, hass, scenario_full):
        """Test service requires reward_name."""
        with pytest.raises(vol.Invalid):
            await hass.services.async_call(
                "assigneeschores",
                "create_reward",
                {"reward_cost": 75.0},  # Missing reward_name
                blocking=True,
            )


class TestCreateRewardEndToEnd:
    """Test create_reward end-to-end functionality."""

    async def test_creates_reward_in_storage(self, hass, scenario_full):
        """Test reward is created in coordinator storage."""
        # Test implementation here
        pass

    async def test_reward_appears_in_dashboard(self, hass, scenario_full):
        """Test reward appears in dashboard helper."""
        # E2E test implementation here
        pass
```

## Key Takeaways

1. **`async_call()` validates automatically** - If your test doesn't raise `vol.Invalid`, schema is correct
2. **Test with literal strings** - Not just constants, to catch docs/schema mismatches
3. **Test negative cases** - Verify wrong field names ARE rejected
4. **Follow E2E pattern** - Check entity states after service calls (per AGENT_TEST_CREATION_INSTRUCTIONS.md)
5. **Match services.yaml exactly** - Test with the exact field names users will type

## Validation Checklist

Before committing service changes:

- [ ] Test with literal field names from services.yaml
- [ ] Test that wrong field names raise `vol.Invalid`
- [ ] Test missing required fields raise `vol.Invalid`
- [ ] Test in actual Developer Tools (not just automated tests)
- [ ] Verify constant VALUES match services.yaml field names
- [ ] Check E2E: entity states update after service call
