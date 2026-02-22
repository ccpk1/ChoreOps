# Agent Test Validation Guide

**Purpose**: Quick reference for validating production code changes using the ChoreOps test suite.

> **⚠️ Terminal Requirement**: Always run commands (tests, lint) inside an actual terminal session so output is captured and visible. Never simulate command execution.

---

## Quick Commands

```bash
# Run all tests
python -m pytest tests/ -v --tb=line

# Run specific file
python -m pytest tests/test_workflow_chores.py -v

# Stop on first failure
python -m pytest tests/ -x
```

---

## Which Tests to Run for Your Changes

| You Changed                 | Run These Tests                             | Why                          |
| --------------------------- | ------------------------------------------- | ---------------------------- |
| **Config/Options flow**     | `test_config_flow*.py`                      | Validate UI setup paths      |
| **Coordinator logic**       | `test_workflow*.py` + `test_coordinator.py` | Validate business logic      |
| **Entity platforms**        | `test_workflow*.py`                         | Validate entity behavior     |
| **Dashboard helper**        | `test_workflow*.py`                         | Validate dashboard data      |
| **Services**                | `test_*_services.py`                        | Validate service endpoints   |
| **Translations**            | `test_translations*.py`                     | Validate translation loading |
| **Storage/Migration**       | All tests                                   | Validate data integrity      |
| **Badge/computation logic** | `test_performance*.py`                      | Validate performance impact  |
| **Any production code**     | **All tests** (mandatory)                   | Prevent regressions          |

### Test Type Decision Matrix

| Need to Validate      | File Pattern                            | Focus                           |
| --------------------- | --------------------------------------- | ------------------------------- |
| UI flows work         | `test_config_flow*.py`                  | Setup and configuration         |
| Business logic intact | `test_workflow*.py`                     | Core functionality              |
| Multi-assignee features    | `test_shared*.py` + `test_workflow*.py` | Coordination patterns           |
| Full integration      | `test_e2e*.py` + all workflow tests     | End-to-end workflows            |
| Performance impact    | `test_performance*.py`                  | Badge computation & entity load |

---

## Performance Test Validation

**Purpose**: Measure badge computation and entity processing performance under realistic load.

### Running Performance Tests

```bash
# Default (uses scenario_stress.yaml - 19 assignees, 510 entities)
python -m pytest tests/test_performance_comprehensive.py -s --tb=short

# Custom scenario via environment variable
PERF_SCENARIO=scenario_full.yaml python -m pytest tests/test_performance_comprehensive.py -s
```

### What the Performance Test Measures

- **Badge computation time** - How long badge calculations take across all assignees
- **Overdue checking** - Time to scan all chores for overdue status
- **Entity persistence** - Storage queue processing time
- **Entity count** - Total entities created for trend tracking

### Available Scenarios

| Scenario                         | Dataset                                      | Use Case                |
| -------------------------------- | -------------------------------------------- | ----------------------- |
| `scenario_stress.yaml` (default) | 19 assignees, 19 chores, 5 badges (~510 entities) | Standard stress test    |
| `scenario_full.yaml`             | 3 assignees, 18 chores, 2 badges (~236 entities)  | Quick integration check |
| `scenario_minimal.yaml`          | 1 assignee, 1 chore                               | Fastest sanity check    |

### Performance Thresholds

Limits scale with entity count:

- **Badge computation**: < 3ms per entity (or 1500ms minimum)
- **Overdue checking**: < 0.6ms per entity (or 300ms minimum)
- **Persist queue**: < 15ms (fixed)

Results are saved to `tests/performance_results.json` for trend analysis.

---

## Mandatory Completion Gates ✅

**Work is NOT complete until BOTH commands pass:**

```bash
# 1. FULL LINT CHECK (must pass)
./utils/quick_lint.sh --fix

# 2. FULL TEST SUITE (all tests must pass)
python -m pytest tests/ -v --tb=line
```

**NEVER declare work complete without running both commands above.**

### What These Commands Validate

**Lint check verifies**:

- ✅ No critical pylint errors (severity 4+)
- ✅ No unused imports or variables
- ✅ Proper module-level suppressions
- ✅ Code formatting compliance
- ✅ No syntax errors

**Test suite verifies**:

- ✅ All business logic works correctly
- ✅ No regressions in existing features
- ✅ Entity states update properly
- ✅ Dashboard helper provides correct data
- ✅ Config/options flows complete successfully

---

## Debugging Test Failures

### Common Test Failure Patterns

**Import Errors**:

```bash
# Problem: Can't import from tests.helpers
# Solution: Use correct import pattern
from tests.helpers import setup_from_yaml, CHORE_STATE_PENDING
```

**Entity Not Found**:

```python
# Problem: Manually constructed entity IDs
entity_id = f"sensor.kc_{assignee_name.lower()}_points"  # ❌ Wrong

# Solution: Get from dashboard helper
helper_state = hass.states.get("sensor.kc_zoe_ui_dashboard_helper")
points_eid = helper_state.attributes["core_sensors"]["points_eid"]  # ✅ Correct
```

**Authorization Failures**:

```python
# Problem: Missing user context
await hass.services.async_call("button", "press", {"entity_id": button_id})  # ❌ Wrong

# Solution: Add user context
context = Context(user_id=mock_hass_users["approver1"].id)
await hass.services.async_call("button", "press", {"entity_id": button_id}, context=context)  # ✅ Correct
```

### Troubleshooting Steps (3-Attempt Rule)

1. **First attempt**: Check the specific error message - often points to exact issue
2. **Second attempt**: Look at similar working test in same file for comparison
3. **Third attempt**: Check scenario YAML data structure for missing entities

After 3 attempts, create a specific question about the failing test.

---

## Module-Level Suppressions (Required for Clean Tests)

**ALWAYS use module-level suppressions** for warnings appearing 3+ times in a test file:

```python
"""Test module docstring."""

# pylint: disable=protected-access  # Accessing _context/_persist for testing
# pylint: disable=redefined-outer-name  # Pytest fixtures redefine names
# pylint: disable=unused-argument  # Fixtures needed for test setup

from typing import Any
import pytest
from homeassistant.core import HomeAssistant
```

**Place immediately after docstring, before imports.**

### Common Suppressions for Test Files

| Suppression            | When to Use                        | Reason                         |
| ---------------------- | ---------------------------------- | ------------------------------ |
| `protected-access`     | Accessing `._context`, `._persist` | Testing internal methods       |
| `redefined-outer-name` | Using pytest fixtures              | Fixtures redefine scope names  |
| `unused-argument`      | Fixtures not used in test body     | Needed for setup               |
| `too-many-locals`      | Complex test setup                 | Many variables for readability |

---

## Quick Validation Checklist

When you finish changing production code:

- [ ] **Lint passes**: `./utils/quick_lint.sh --fix` returns clean
- [ ] **Tests pass**: `python -m pytest tests/ -v --tb=line` all green
- [ ] **No debug code**: No print statements, pdb, or f-strings without interpolation
- [ ] **Module suppressions**: Added for any repeated pylint warnings
- [ ] **Imports clean**: Using `from tests.helpers import ...` pattern

---

## When You Need to Write New Tests

If your changes require new test coverage (new features, new edge cases), see:

- **`AGENT_TEST_CREATION_INSTRUCTIONS.md`** - Complete technical guide for writing tests
- **`SCENARIOS.md`** - Which scenario YAML to use for new tests
- **`README.md`** - Testing philosophy and family background

Most code changes only require **validation** with existing tests. New tests needed only for genuinely new functionality.

---

_This guide focuses on validating existing code. For creating new tests, use the creation guide._
