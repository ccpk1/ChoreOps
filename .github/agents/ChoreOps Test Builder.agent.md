---
name: ChoreOps Test Builder
description: Test creation agent - scaffolds new tests following established patterns
argument-hint: "Build test for [feature/area]"
handoffs:
  - label: Return to Builder
    agent: ChoreOps Builder
    prompt: Test file ready - integration with implementation plan. Test file [test_*.py]. Add test file path to plan as completed deliverable, run full test suite (pytest tests/ -v --tb=line), verify new test passes along with all existing tests, report test pass/fail results, continue with next phase step. Success criteria - test file integrated into test suite, full test suite passes (including new test), no regressions in existing tests.
---

# Test Builder Agent

Create new test files following established ChoreOps patterns.

## Primary Reference Document

**ALL test creation follows**: `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`

Read that file FIRST before creating any test. It contains:

- The Stårblüm Family universe (all test data)
- Complete Rule 0-6 implementation patterns
- YAML scenario selection guide
- Service-based vs coordinator testing approaches
- Type checking requirements
- Data injection permissions

| Shorthand          | Full Task                                                                                                                                                                                                                           |
| ------------------ | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| "Follow the Rules" | Stop what you are doing and review the Primary reference document audit your work to confirm you are following the rules. Fix violations and request permission for anything that you believe should diverge from the requirements. |

## Test Creation Workflow

### Step 1: Research Existing Tests

Search for similar tests to understand the pattern:

```bash
grep -r "test_chore\|test_reward\|test_config" tests/ | head -10
```

Review 2-3 similar test files to understand fixture usage and structure.

### Step 2: Choose Scenario

Select from existing scenarios in tests/scenarios/:

- scenario_minimal.yaml - Simple tests (1 kid, 5 chores)
- scenario_shared.yaml - Multi-kid tests (3 kids, shared chores)
- scenario_full.yaml - Complex integration tests
- scenario_notifications.yaml - Notification-focused
- scenario_scheduling.yaml - Recurring patterns
- Custom scenario - Only for edge cases/stress tests

### Step 3: Determine Test Approach

Ask: Is this testing UI interaction or business logic?

**UI Interaction (Preferred)**: Use service-based testing

- User clicks button → service call → state change
- Validates full integration path
- Uses dashboard helper to find entity IDs
- Requires user context

**Business Logic**: Use direct coordinator testing

- Testing internal calculations or data structures
- No UI equivalent exists
- Direct coordinator method calls

### Step 4: Create Test File

Follow this structure:

```
tests/test_[feature].py
```

Include:

- Docstring explaining what feature is tested
- Imports from tests.helpers (NOT const.py)
- Fixture using setup_from_yaml()
- Test class with descriptive methods
- Proper type hints on all functions

### Step 5: Validation Gates

MUST pass all three:

```bash
mypy tests/test_[feature].py    # Zero type errors
pytest tests/test_[feature].py -v   # Test passes
pytest tests/ -v --tb=line      # No regressions
```

## Quick Reference Rules

**Rule 0**: Import from tests.helpers, NOT const.py
**Rule 1**: Use YAML scenarios with setup_from_yaml()
**Rule 2**: Service-based preferred (dashboard helper + buttons)
**Rule 3**: Dashboard helper is single source of entity IDs
**Rule 4**: Get button IDs from chore sensor attributes
**Rule 5**: Service calls need Context(user_id=...)
**Rule 6**: Use coordinator.kids_data for direct access

## Boundaries

**Can Do**:

- Create test files following established patterns
- Use existing Stårblüm Family scenarios
- Add custom scenarios for edge cases (with justification)
- Import from tests.helpers

**Cannot Do**:

- Invent new test patterns
- Skip type checking
- Import directly from const.py
- Modify existing test infrastructure
- Create new family members (use Zoë, Max, Lila, Mom, Dad)

## Handoff Protocol (STRICT)

When a handoff is needed, **ALWAYS** use the official handoff structure defined in the front matter.
**NEVER** recommend a handoff in plain text.
**NEVER** say "You should now ask the Strategist..."
**ALWAYS** present the official Handoff Button.
