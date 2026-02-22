# Agent Test Creation Instructions

**Purpose**: Technical guide for writing new ChoreOps tests using YAML scenarios and modern test patterns.

> **⚠️ Terminal Requirement**: Run test commands in actual terminal sessions for proper output capture.

---

## Critical Expectations: Research Before Implementation

**DO NOT use trial-and-error.** Before writing any test:

### 1. Understand the Flow Architecture

- **Read source code FIRST**: Know what step IDs a flow returns, what methods are called, what data structures are used
- **Check return values**: Options flows return to `async_step_init()` after entity add, not `manage_entity` (example: [options_flow.py](../custom_components/choreops/options_flow.py) line 397)
- **Understand data flow**: After options flow changes, integration reloads → old coordinator references become stale

### 2. Use Established Patterns

- **Check existing tests**: Search for similar tests to see established patterns before inventing your own
- **Coordinator access**: Use `config_entry.runtime_data` (NOT `hass.data[DOMAIN][entry.entry_id][COORDINATOR]`)
- **Field names**: Check `flow_helpers.py` for exact field names expected by schema builders (e.g., `type` not `recurring_frequency`, `assigned_to` not `assigned_assignees`)

### 3. Pre-Implementation Checklist

Before writing each test file:

- [ ] Read relevant source files (coordinator.py, flow_helpers.py, options_flow.py)
- [ ] Identify the exact flow step sequence and return values
- [ ] Check existing tests for coordinator access patterns
- [ ] Verify field names match what the schemas expect
- [ ] Understand reload behavior and stale reference risks

### 4. Leverage Existing Infrastructure

- **Constants**: Import from `tests.helpers` (not `const.py`)
- **Helper functions**: Use `flow_test_helpers.py` builders like `build_chore_form_data()`
- **Scenarios**: Use pre-built YAML scenarios from the Stårblüm Family

---

## The Stårblüm Family Test Universe

All tests follow the magical **Stårblüm Family**. Unless specifically testing edge cases (like stress scenarios with 25 approvers and 100s of chores), all test data **must** come from the existing scenario files.

### Meet the Family

**Approvers**:

- **Môm Astrid Stårblüm** (`@Astrid`) - The family organizer who approves chores and rewards
- **Dad Leo Stårblüm** (`@Leo`) - The fun approver who creates bonus opportunities

**Assignees**:

- **Zoë Stårblüm** (Age 8, avatar: `mdi:star-face`) - The responsible oldest, loves earning badges
- **Max! Stårblüm** (Age 6, avatar: `mdi:rocket`) - The energetic middle child, always claiming chores
- **Lila Stårblüm** (Age 8, avatar: `mdi:flower`) - The creative twin, motivated by rewards

### Why Special Characters?

All names include special characters (`å`, `ï`, `ë`, `ø`, `@`, `!`) to ensure robust Unicode handling. This validates international family support.

### Available Scenarios

| Scenario                      | Description                                      | Use Case                    |
| ----------------------------- | ------------------------------------------------ | --------------------------- |
| `scenario_minimal.yaml`       | Zoë's first week (1 assignee, 5 chores)               | Simple tests, basic flows   |
| `scenario_shared.yaml`        | Multi-assignee coordination (3 assignees, 8 shared chores) | Shared chore testing        |
| `scenario_full.yaml`          | Complete family with all features                | Complex integration tests   |
| `scenario_notifications.yaml` | Notification-focused setup                       | Notification workflow tests |
| `scenario_scheduling.yaml`    | Recurring chore patterns                         | Scheduling tests            |

**Rule**: Find entity names, chore names, and family data from `tests/scenarios/` files. Do NOT invent new names unless testing stress/edge cases.

---

## When to Write New Tests

Write new tests when adding:

- **New features** - Coordinator methods, entity platforms, services
- **New workflows** - User interaction patterns, business logic paths
- **Edge cases** - Error conditions, boundary conditions, validation paths
- **Performance scenarios** - Load testing, stress testing

For **validating existing code changes**, see `AGENT_TEST_VALIDATION_GUIDE.md`.

---

## Test Creation Architecture

```
tests/
├── conftest.py              # Core fixtures (mock_hass_users, auto_enable_custom_integrations)
├── helpers/
│   ├── __init__.py          # Re-exports everything for convenient imports
│   ├── constants.py         # All ChoreOps constants (from const.py)
│   ├── setup.py             # setup_from_yaml(), SetupResult dataclass
│   ├── workflows.py         # Chore/reward workflow helpers
│   └── validation.py        # Entity state validation helpers
├── scenarios/
│   ├── scenario_minimal.yaml    # 1 assignee, 5 chores
│   ├── scenario_shared.yaml     # 3 assignees, 8 shared chores
│   ├── scenario_full.yaml       # 3 assignees, everything
│   └── scenario_notifications.yaml  # Notification testing
├── test_workflow_chores.py      # Chore workflow tests
├── test_workflow_notifications.py  # Notification workflow tests
├── test_translations_custom.py  # Translation file tests
└── legacy/                      # Old tests (direct coordinator manipulation)
```

---

### Type Checking Tests

**Important**: Test files are excluded from standard `./utils/quick_lint.sh` and `pylint` checks. You must explicitly run type checking on test files:

```bash
# Check test files for type errors (not caught by regular linting)
mypy tests/

# Or check a specific test file
mypy tests/test_datetime_edge_cases.py
```

This catches errors like:

- Passing `None` to functions expecting `str`
- Accessing attributes that don't exist on types
- Type mismatches in function arguments

**Always run `mypy tests/` before submitting test files.**

#### Type: ignore Comments - Placement Matters

When adding `# type: ignore` comments, **placement is critical** because formatters can cause duplication:

**❌ Problematic (inline on continuation lines):**

```python
result = await hass.config_entries.options.async_configure(
    result.get("flow_id"),  # type: ignore[arg-type]  ← Risky: can duplicate if file reformats
    user_input={...},
)
```

**✅ Better (on code line, not continuation):**

```python
flow_id = result.get("flow_id")  # type: ignore[arg-type]
result = await hass.config_entries.options.async_configure(
    flow_id,
    user_input={...},
)
```

**Why**: When formatters run on save, inline comments on continuation lines can duplicate or misalign, causing `# type: ignore` to appear twice on the same line. Refactoring into separate statements prevents this issue entirely.

**For edge case tests** (intentionally passing wrong types), use the refactored pattern above rather than inline comments.

---

## Rule 0: Import from tests.helpers, NOT const.py

✅ **CORRECT** - Import from tests.helpers:

```python
from tests.helpers import (
    # Setup
    setup_from_yaml, SetupResult,

    # Constants - Chore states
    CHORE_STATE_PENDING, CHORE_STATE_CLAIMED, CHORE_STATE_APPROVED,
    CHORE_STATE_COMPLETED_BY_OTHER, CHORE_STATE_OVERDUE,

    # Constants - Sensor attributes
    ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID, ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID,
    ATTR_GLOBAL_STATE, ATTR_CAN_CLAIM, ATTR_CAN_APPROVE, ATTR_DUE_DATE,

    # Constants - Completion criteria
    COMPLETION_CRITERIA_INDEPENDENT, COMPLETION_CRITERIA_SHARED,
    COMPLETION_CRITERIA_SHARED_FIRST,

    # Constants - Data keys
    DATA_KID_CHORE_DATA, DATA_KID_CHORE_DATA_STATE, DATA_KID_POINTS,

    # Workflows
    get_dashboard_helper, find_chore, get_chore_buttons,
)
```

❌ **WRONG** - Direct import from const.py:

```python
from custom_components.choreops.const import CHORE_STATE_PENDING  # Don't do this
```

**Why**: `tests/helpers/constants.py` provides organized imports with quick-reference documentation.

---

## Rule 1: Use YAML Scenarios + setup_from_yaml()

Modern tests load scenarios from YAML files and run through the full config flow:

```python
from tests.helpers.setup import setup_from_yaml, SetupResult

@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario: 1 assignee, 1 approver, 5 chores."""
    return await setup_from_yaml(
        hass,
        mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )
```

### SetupResult provides:

```python
result = await setup_from_yaml(hass, mock_hass_users, "tests/scenarios/scenario_minimal.yaml")

# Access coordinator directly
coordinator = result.coordinator

# Get internal IDs by name
assignee_id = result.assignee_ids["Zoë"]           # UUID for Zoë
chore_id = result.chore_ids["Make bed"]  # UUID for Make bed chore
approver_id = result.approver_ids["Mom"]     # UUID for Mom

# Config entry
config_entry = result.config_entry
```

---

## Rule 2: Testing Approaches (Priority Order)

### Testing Method Hierarchy

| Priority                       | Method                                               | User Context        | Use Case                                           |
| ------------------------------ | ---------------------------------------------------- | ------------------- | -------------------------------------------------- |
| **1. REQUIRED**                | Button press with `Context(user_id=...)`             | ✅ Assignee/Approver/Admin | E2E workflow tests with authorization              |
| **2. ACCEPTABLE**              | Service call to `assigneeschores.*` services              | ❌ Always admin     | Service layer tests (no auth testing)              |
| **3. FORBIDDEN for workflows** | Direct coordinator API (`coordinator.claim_chore()`) | N/A                 | Internal logic only - requires explicit permission |

### Why Button Presses Are Required (Not Just Preferred)

**Button presses can mock user privileges**:

```python
# Test as a assignee - can verify assignees CANNOT approve their own chores
assignee_context = Context(user_id=mock_hass_users["assignee1"].id)
await hass.services.async_call("button", "press", {"entity_id": claim_btn}, context=assignee_context)

# Test as a approver - can verify approvers CAN approve chores
approver_context = Context(user_id=mock_hass_users["approver1"].id)
await hass.services.async_call("button", "press", {"entity_id": approve_btn}, context=approver_context)
```

**Service calls ALWAYS run as admin**:

```python
# ⚠️ This ALWAYS runs with admin privileges - cannot test authorization
await hass.services.async_call("assigneeschores", "approve_chore", {...})
```

**Direct coordinator API BYPASSES all security and UI layers**:

```python
# ❌ FORBIDDEN for workflow tests - bypasses everything
coordinator.claim_chore(assignee_id, chore_id, "Zoë")  # No user context, no button, no security
```

### Approach A: Button Press with User Context (REQUIRED for workflow tests)

**This is the primary approach.** It provides true end-to-end testing including authorization:

```python
from homeassistant.core import Context

async def test_claim_via_button(hass, scenario_minimal, mock_hass_users):
    # Get dashboard helper - the single source of truth for entity IDs
    helper_state = hass.states.get("sensor.kc_zoe_ui_dashboard_helper")
    helper_attrs = helper_state.attributes

    # Find chore in helper (use Stårblüm family names from scenarios)
    chore = next(c for c in helper_attrs["chores"] if c["name"] == "Make bed")
    chore_sensor_eid = chore["eid"]

    # Get button ID from chore sensor attributes
    chore_state = hass.states.get(chore_sensor_eid)
    claim_button_eid = chore_state.attributes[ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID]

    # Press button with user context (simulates real user action)
    assignee_context = Context(user_id=mock_hass_users["assignee1"].id)
    await hass.services.async_call(
        "button", "press",
        {"entity_id": claim_button_eid},
        blocking=True, context=assignee_context,
    )
    await hass.async_block_till_done()

    # Verify via sensor state (what the user sees in the UI)
    chore_state = hass.states.get(chore_sensor_eid)
    assert chore_state.state == CHORE_STATE_CLAIMED
```

**Why preferred:**

- Tests the full integration path from UI to coordinator to entity state
- **Tests authorization** - can verify assignees can't approve their own chores, etc.
- Validates that sensors, buttons, and states work together correctly
- Catches integration issues that direct API calls would miss
- Mirrors actual user experience

### Approach A.1: Service Calls to `assigneeschores.*` Services (Acceptable for non-auth tests)

When a button entity doesn't exist for an action, use defined services from `services.py`:

```python
async def test_approve_via_service(hass, scenario_minimal):
    # Service calls always run as admin - cannot test authorization
    await hass.services.async_call(
        "assigneeschores", "approve_chore",
        {
            "config_entry_id": scenario_minimal.entry.entry_id,
            "chore_name": "Make bed",
            "assignee_name": "Zoë",
        },
        blocking=True,
    )
    await hass.async_block_till_done()

    # Verify state changed
    chore_state = hass.states.get("sensor.kc_zoe_chore_make_bed")
    assert chore_state.state == CHORE_STATE_APPROVED
```

**Available services** (see `services.py`):

- `assigneeschores.claim_chore` - Claim a chore for a assignee
- `assigneeschores.approve_chore` - Approve a claimed chore
- `assigneeschores.disapprove_chore` - Disapprove a claimed chore

**When to use:**

- Actions without button entities
- Tests that don't require user authorization verification
- Admin-level operations

**⚠️ LIMITATION**: Service calls cannot mock user privileges - always run as admin.

### Approach B: Direct Coordinator API (Requires explicit permission)

Use **only** when testing:

- Core business logic not exposed through UI entities
- Internal data structures and calculations
- Performance-critical paths where service call overhead matters
- Coordinator-specific edge cases

```python
async def test_internal_calculation(hass, scenario_minimal):
    coordinator = scenario_minimal.coordinator
    assignee_id = scenario_minimal.assignee_ids["Zoë"]
    chore_id = scenario_minimal.chore_ids["Make bed"]

    # ⚠️ REQUIRES PERMISSION - bypasses UI layer
    # Only for internal logic tests, not workflow tests
    result = coordinator._calculate_streak_multiplier(assignee_id, chore_id)

    assert result == 1.5
```

**When to use:**

- Testing internal calculations (point multipliers, badge progress)
- Validating data structures not directly visible in UI
- Testing coordinator methods that have no button/service equivalent

### ❌ FORBIDDEN: Direct Coordinator API for Workflow Tests

**NEVER use direct coordinator calls for workflow tests:**

```python
# ❌ FORBIDDEN - bypasses user context, security, and UI layers
coordinator.claim_chore(assignee_id, chore_id, "Zoë")
coordinator.approve_chore(assignee_id, chore_id, ...)
await coordinator.apply_bonus(...)
await coordinator.claim_reward(...)

# These methods are internal implementation details.
# Tests using them will pass even when the real UI path is broken.
```

**Why this is forbidden:**

1. **No user context**: Cannot verify authorization (who can do what)
2. **Bypasses button entities**: Doesn't test the actual user-facing API
3. **Hidden bugs**: Tests pass but users encounter errors
4. **Timestamp issues**: May not trigger all side effects that buttons trigger

**✅ CORRECT - Use button press with user context:**

```python
# Get button entity ID from dashboard helper or chore sensor
claim_button_eid = chore_state.attributes[ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID]

# Press button WITH user context to test real user flow
assignee_context = Context(user_id=mock_hass_users["assignee1"].id)
await hass.services.async_call(
    "button", "press",
    {"entity_id": claim_button_eid},
    blocking=True, context=assignee_context,
)
```

**✅ ACCEPTABLE - Use service call when button doesn't exist:**

```python
# Service calls are acceptable but cannot test authorization
await hass.services.async_call(
    "assigneeschores", "approve_chore",
    {"config_entry_id": entry.entry_id, "chore_name": "Make bed", "assignee_name": "Zoë"},
    blocking=True,
)
```

---

## Rule 2.1: Data Injection Requires Permission

> **⚠️ CRITICAL**: Direct data injection into coordinator bypassing config/options flow **requires explicit permission**.

**What is data injection?**

Directly modifying coordinator data structures instead of going through the config flow or options flow:

```python
# ❌ DATA INJECTION - Requires permission
chore_info[const.DATA_CHORE_PER_KID_APPLICABLE_DAYS] = {
    zoe_id: ["mon", "wed"],
    max_id: ["tue", "thu"],
}

# ✅ PROPER APPROACH - Goes through flow
result = await hass.config_entries.options.async_configure(
    flow_id, user_input={...}
)
```

**Why this matters:**

Data injection can use **different formats** than real user input, causing tests to pass while production fails:

- UI selector returns `["mon", "tue"]` (strings)
- Code might expect `[0, 1]` (integers)
- Injecting integers makes tests pass, but real users see errors

**When data injection IS allowed (with permission):**

- Testing internal coordinator logic not exposed through UI
- Setting up complex state that would require many flow steps
- Testing edge cases impossible to reach through normal flows

**Requirements for data injection:**

1. Add comment: `# DATA INJECTION: [justification] - approved by [person/date]`
2. Use **exact same data formats** as real flow would produce
3. Verify format by checking `flow_helpers.py` or actual selector output

---

## Rule 3: Dashboard Helper Is Single Source of Truth for Entity IDs

The dashboard helper sensor (`sensor.kc_{assignee}_ui_dashboard_helper`) contains ALL entity IDs:

```python
helper_state = hass.states.get("sensor.kc_zoe_ui_dashboard_helper")
helper_attrs = helper_state.attributes

# Chores (sensor entity IDs)
chores_list = helper_attrs.get("chores", [])
for chore in chores_list:
    chore_eid = chore["eid"]        # sensor.kc_zoe_chore_status_make_bed
    chore_name = chore["name"]      # "Make bed"
    chore_status = chore["status"]  # "pending", "claimed", "approved"
    can_claim = chore["can_claim"]  # True/False
    can_approve = chore["can_approve"]

# Rewards (sensor entity IDs)
rewards_list = helper_attrs.get("rewards", [])

# Bonuses & Penalties (BUTTON entity IDs - not sensors!)
bonuses_list = helper_attrs.get("bonuses", [])
penalties_list = helper_attrs.get("penalties", [])

# Core sensors
core_sensors = helper_attrs.get("core_sensors", {})
points_sensor = core_sensors["points_eid"]  # sensor.kc_zoe_points
```

**Never manually construct entity IDs. Always extract from dashboard helper.**

---

## Rule 4: Getting Button IDs from Chore Sensors

Chore-specific buttons are in the chore sensor's attributes:

```python
from tests.helpers import (
    ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID,
    ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID,
    ATTR_CHORE_DISAPPROVE_BUTTON_ENTITY_ID,
)

# Get chore sensor from dashboard helper
chore_info = next(c for c in helper_attrs["chores"] if c["name"] == "Make bed")
chore_sensor_eid = chore_info["eid"]

# Read button IDs from sensor attributes
chore_state = hass.states.get(chore_sensor_eid)
claim_button = chore_state.attributes.get(ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID)
approve_button = chore_state.attributes.get(ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID)
disapprove_button = chore_state.attributes.get(ATTR_CHORE_DISAPPROVE_BUTTON_ENTITY_ID)
```

---

## Rule 5: Service Calls With User Context

Always pass `context=` with the appropriate user for authorization:

```python
from homeassistant.core import Context

# Assignee claims chore
assignee_context = Context(user_id=mock_hass_users["assignee1"].id)
await hass.services.async_call(
    "button", "press",
    {"entity_id": claim_button_eid},
    blocking=True, context=assignee_context,
)

# Approver approves chore
approver_context = Context(user_id=mock_hass_users["approver1"].id)
await hass.services.async_call(
    "button", "press",
    {"entity_id": approve_button_eid},
    blocking=True, context=approver_context,
)
```

### Available mock_hass_users Keys

- `mock_hass_users["assignee1"]` - First assignee (Zoë in most scenarios)
- `mock_hass_users["assignee2"]` - Second assignee (Max)
- `mock_hass_users["assignee3"]` - Third assignee (Lila)
- `mock_hass_users["approver1"]` - First approver (Mom)
- `mock_hass_users["admin"]` - Admin user

---

## Rule 6: Reading Coordinator Data

For direct data access, use coordinator properties:

```python
coordinator = scenario_minimal.coordinator

# Assignee data
assignee_data = coordinator.assignees_data.get(assignee_id, {})
points = assignee_data.get(DATA_KID_POINTS, 0.0)
name = assignee_data.get(DATA_KID_NAME, "")

# Per-assignee chore state
chore_data = assignee_data.get(DATA_KID_CHORE_DATA, {})
per_chore = chore_data.get(chore_id, {})
state = per_chore.get(DATA_KID_CHORE_DATA_STATE, CHORE_STATE_PENDING)
due_date = per_chore.get(DATA_KID_CHORE_DATA_DUE_DATE)

# Global chore data
chore_info = coordinator.chores_data.get(chore_id, {})
completion_criteria = chore_info.get(DATA_CHORE_COMPLETION_CRITERIA)
recurring_frequency = chore_info.get(DATA_CHORE_RECURRING_FREQUENCY)
```

---

## YAML Scenario Format

Create scenarios in `tests/scenarios/`:

```yaml
# tests/scenarios/scenario_example.yaml

system:
  points_label: "Points"
  points_icon: "mdi:star-outline"

assignees:
  - name: "Zoë"
    ha_user: "assignee1" # Maps to mock_hass_users["assignee1"]
    dashboard_language: "en"
    enable_mobile_notifications: false
    mobile_notify_service: ""

approvers:
  - name: "Mom"
    ha_user: "approver1" # Maps to mock_hass_users["approver1"]
    assignees: ["Zoë"] # Associate with assignees by name
    enable_mobile_notifications: false
    mobile_notify_service: ""

chores:
  - name: "Make bed"
    assigned_to: ["Zoë"] # Assign by assignee name
    points: 5.0
    icon: "mdi:bed"
    completion_criteria: "independent" # or "shared_all", "shared_first"
    recurring_frequency: "daily" # or "weekly", "monthly", "once"
    auto_approve: false
    # Advanced options:
    # approval_reset_type: "at_midnight_once"
    # overdue_handling_type: "at_due_date"
    # due_date: "2026-01-15T08:00:00"
```

---

## Complete Test Example

```python
"""Chore workflow tests."""

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant

from tests.helpers import (
    CHORE_STATE_PENDING, CHORE_STATE_CLAIMED, CHORE_STATE_APPROVED,
    DATA_KID_CHORE_DATA, DATA_KID_CHORE_DATA_STATE, DATA_KID_POINTS,
)
from tests.helpers.setup import setup_from_yaml, SetupResult


@pytest.fixture
async def scenario_minimal(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load minimal scenario."""
    return await setup_from_yaml(
        hass, mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",
    )


def get_assignee_chore_state(coordinator, assignee_id: str, chore_id: str) -> str:
    """Get chore state for a assignee."""
    assignee_data = coordinator.assignees_data.get(assignee_id, {})
    chore_data = assignee_data.get(DATA_KID_CHORE_DATA, {})
    per_chore = chore_data.get(chore_id, {})
    return per_chore.get(DATA_KID_CHORE_DATA_STATE, CHORE_STATE_PENDING)


class TestChoreWorkflow:
    """Chore workflow tests."""

    @pytest.mark.asyncio
    async def test_claim_approve_grants_points(
        self,
        hass: HomeAssistant,
        scenario_minimal: SetupResult,
    ) -> None:
        """Claiming and approving a chore grants points."""
        coordinator = scenario_minimal.coordinator
        assignee_id = scenario_minimal.assignee_ids["Zoë"]
        chore_id = scenario_minimal.chore_ids["Make bed"]  # 5 points

        initial_points = coordinator.assignees_data[assignee_id].get(DATA_KID_POINTS, 0.0)

        with patch.object(coordinator.notification_manager, "notify_assignee", new=AsyncMock()):
            # Claim
            coordinator.claim_chore(assignee_id, chore_id, "Zoë")
            assert get_assignee_chore_state(coordinator, assignee_id, chore_id) == CHORE_STATE_CLAIMED

            # Approve
            coordinator.approve_chore("Mom", assignee_id, chore_id)
            assert get_assignee_chore_state(coordinator, assignee_id, chore_id) == CHORE_STATE_APPROVED

        # Verify points
        final_points = coordinator.assignees_data[assignee_id].get(DATA_KID_POINTS, 0.0)
        assert final_points == initial_points + 5.0
```

---

## Quick Reference: Key Constants

### Chore States

| Constant                         | Value                | Meaning                           |
| -------------------------------- | -------------------- | --------------------------------- |
| `CHORE_STATE_PENDING`            | "pending"            | Not yet claimed                   |
| `CHORE_STATE_CLAIMED`            | "claimed"            | Claimed, awaiting approval        |
| `CHORE_STATE_APPROVED`           | "approved"           | Completed and approved            |
| `CHORE_STATE_OVERDUE`            | "overdue"            | Past due date                     |
| `CHORE_STATE_COMPLETED_BY_OTHER` | "completed_by_other" | Another assignee did it (shared_first) |
| `CHORE_STATE_CLAIMED_IN_PART`    | "claimed_in_part"    | Some assignees claimed (shared_all)    |
| `CHORE_STATE_APPROVED_IN_PART`   | "approved_in_part"   | Some assignees approved (shared_all)   |

### Completion Criteria

| Constant                           | Behavior                              |
| ---------------------------------- | ------------------------------------- |
| `COMPLETION_CRITERIA_INDEPENDENT`  | Each assignee has their own chore instance |
| `COMPLETION_CRITERIA_SHARED_FIRST` | First to claim wins, others blocked   |
| `COMPLETION_CRITERIA_SHARED`       | All assigned assignees must complete       |

---

## Test File Structure Template

```python
"""Test module for [feature description]."""

# pylint: disable=protected-access  # Testing internal methods
# pylint: disable=redefined-outer-name  # Pytest fixtures
# pylint: disable=unused-argument  # Fixtures needed for setup

from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant

from tests.helpers import (
    # Import needed constants and helpers
    CHORE_STATE_PENDING, CHORE_STATE_CLAIMED,
    setup_from_yaml, SetupResult,
)


@pytest.fixture
async def scenario_for_feature(
    hass: HomeAssistant,
    mock_hass_users: dict[str, Any],
) -> SetupResult:
    """Load scenario optimized for this feature."""
    return await setup_from_yaml(
        hass, mock_hass_users,
        "tests/scenarios/scenario_minimal.yaml",  # Choose appropriate scenario
    )


class TestFeatureName:
    """Test class for [feature description]."""

    async def test_specific_behavior(
        self,
        hass: HomeAssistant,
        scenario_for_feature: SetupResult,
    ) -> None:
        """Test that [specific behavior] works correctly."""
        # Setup
        coordinator = scenario_for_feature.coordinator

        # Test implementation
        # ...

        # Assertions
        assert expected == actual
```

---

_For test validation after code changes, see `AGENT_TEST_VALIDATION_GUIDE.md`._
_For scenario selection, see `SCENARIOS.md`._
_For family background, see `README.md`._

### Sensor Attributes

| Constant                                 | Description                      |
| ---------------------------------------- | -------------------------------- |
| `ATTR_CHORE_CLAIM_BUTTON_ENTITY_ID`      | Button to claim chore            |
| `ATTR_CHORE_APPROVE_BUTTON_ENTITY_ID`    | Button to approve chore          |
| `ATTR_CHORE_DISAPPROVE_BUTTON_ENTITY_ID` | Button to disapprove chore       |
| `ATTR_GLOBAL_STATE`                      | Aggregated state across all assignees |
| `ATTR_CAN_CLAIM`                         | Whether chore can be claimed     |
| `ATTR_CAN_APPROVE`                       | Whether chore can be approved    |
| `ATTR_DUE_DATE`                          | Chore due date                   |
| `ATTR_DEFAULT_POINTS`                    | Points awarded on approval       |

---

## Golden Rules

1. **Research before implementation** - read source code, check existing tests, understand flow architecture
2. **Prefer service calls over direct API** - end-to-end tests via dashboard helper and buttons
3. **Import from `tests.helpers`** - never from `const.py` directly
4. **Use Stårblüm Family scenarios** - reusable test data via `setup_from_yaml()`, don't invent new names
5. **Get entity IDs from dashboard helper** - never construct them manually
6. **Use SetupResult** - access `coordinator`, `assignee_ids`, `chore_ids` by name
7. **Mock notifications** - `patch.object(coordinator.notification_manager, "notify_assignee", new=AsyncMock())`
8. **Pass user context** - service calls need `context=Context(user_id=...)`
9. **Get fresh coordinator after reload** - use `config_entry.runtime_data` pattern
