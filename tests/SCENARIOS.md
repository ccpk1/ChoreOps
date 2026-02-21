# Test Scenarios Guide

Quick reference for selecting the right YAML scenario for your test.

## Available Scenarios

### `scenario_minimal.yaml`

**Family**: Mom + Zoë
**Content**: 5 basic chores, simple setup
**Use for**: Quick smoke tests, config flow validation, single-kid workflows

### `scenario_shared.yaml`

**Family**: Both parents + multiple kids
**Content**: Shared chores focus
**Use for**: Multi-kid coordination, shared chore claiming patterns

### `scenario_full.yaml`

**Family**: Complete Stårblüm family
**Content**: All features, complex relationships
**Use for**: Comprehensive integration tests, badge systems, full dashboard

### `scenario_notifications.yaml`

**Family**: Notification-optimized setup
**Content**: Entities configured for notification testing
**Use for**: Notification workflow testing, message validation

### `scenario_scheduling.yaml`

**Family**: Time-focused entities
**Content**: Recurring chores, due dates, overdue handling
**Use for**: Scheduler testing, due date logic, recurring patterns

### Specialized Scenarios

Additional scenarios exist for specific test needs (approval resets, chore services, etc.). Check `tests/scenarios/` directory for complete list.

## Selection Guide

| Your Test Focus      | Recommended Scenario | Why                                |
| -------------------- | -------------------- | ---------------------------------- |
| Basic functionality  | `minimal`            | Fast, simple, focused              |
| Multi-kid features   | `shared`             | Covers coordination patterns       |
| Full integration     | `full`               | Complete feature coverage          |
| Notifications        | `notifications`      | Optimized for notification testing |
| Time-based features  | `scheduling`         | Due dates, recurring, overdue      |
| Config/Options flows | `minimal`            | Simple setup, clear validation     |
| Performance testing  | `full`               | Maximum entity load                |

## Usage Pattern

```python
@pytest.fixture
async def scenario_minimal(hass, mock_hass_users):
    return await setup_from_yaml(hass, mock_hass_users, "tests/scenarios/scenario_minimal.yaml")

async def test_something(hass, scenario_minimal):
    # Use scenario data: scenario_minimal.kid_ids["Zoë"], etc.
```

## Data Consistency

All scenarios use the **Stårblüm family** storyline for consistency:

- Same character names and relationships across scenarios
- Unicode characters (å, ï, ë, ø) for robust testing
- Coherent chore names and themes (magical household)
- Consistent point values and rewards

_See `tests/README.md` for complete family background and testing philosophy._

## Mixed-role authorization matrix

Use these acceptance scenarios for hard-fork capability semantics:

| Scenario      | Capability state                                                | Expected behavior                                                  | Primary tests                                                   |
| ------------- | --------------------------------------------------------------- | ------------------------------------------------------------------ | --------------------------------------------------------------- |
| Assignee-only | `can_be_assigned=true`, `can_approve=false`, `can_manage=false` | Can claim/redeem own items, denied approval and management actions | `tests/test_chore_services.py`, `tests/test_reward_services.py` |
| Approver-only | `can_approve=true`, `can_manage=false`                          | Can approve/disapprove, denied management-only services            | `tests/test_reward_services.py`                                 |
| Manager-only  | `can_manage=true`, `can_approve=false`                          | Can run management-only services, denied approval actions          | `tests/test_reward_services.py`                                 |
| Dual-role     | `can_approve=true`, `can_manage=true`                           | Can execute both approval and management domains                   | `tests/test_reward_services.py`                                 |
