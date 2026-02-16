# KidsChores Testing Suite

Welcome to the KidsChores Home Assistant integration testing suite! This framework validates the integration's functionality through user workflow testing, business logic verification, and dashboard template validation.

## 🌟 The Stårblüm Family

All tests follow the magical **Stårblüm Family**, who use the KidsChores integration to manage their household chores and earn rewards. Unless specifically testing edge cases (like stress scenarios), all test data should come from this consistent storyline.

### Meet the Family

**Parents**:

- **Môm Astrid Stårblüm** (@Astrid) - The family organizer who approves chores and rewards
- **Dad Leo Stårblüm** (@Leo) - The fun parent who creates bonus opportunities

**Kids**:

- **Zoë Stårblüm** (Age 8, avatar: mdi:star-face) - The responsible oldest, loves earning badges
- **Max! Stårblüm** (Age 6, avatar: mdi:rocket) - The energetic middle child, always claiming chores
- **Lila Stårblüm** (Age 8, avatar: mdi:flower) - The creative twin, motivated by rewards

### Why Special Characters?

All names include special characters (å, ï, ë, ø, @, !) to ensure robust Unicode handling throughout the integration. This validates that the system works for international families with diverse naming conventions.

## 🏗️ Testing Architecture

### Modern YAML-Based Scenarios

Tests use pre-built scenarios that tell coherent stories within the Stårblüm family universe:

- **scenario_minimal.yaml**: Zoë's first week with basic chores (simple tests)
- **scenario_shared.yaml**: Multi-kid shared chore coordination
- **scenario_full.yaml**: Complete family with all features
- **scenario_notifications.yaml**: Notification-focused testing
- **scenario_scheduling.yaml**: Recurring chore patterns
- _Plus specialized scenarios for specific test needs_

### Test Resource Documents

- **`AGENT_TEST_CREATION_INSTRUCTIONS.md`** - Complete guide for modern test patterns using YAML scenarios
- **`helpers/`** - Self-documenting setup and validation utilities
- **`scenarios/`** - YAML scenario files with inline documentation
- **Working test files** - Live examples of current patterns (e.g., `test_workflow_chores.py`)

## 📋 Testing Approach

### 1. **User-Centric Workflows**

Tests mirror real-world user journeys:

- Setup integration → Config flow
- Add entities → Options flow
- Interact with system → Services & UI
- View data → Dashboard templates

### 2. **Scenario-Driven Data**

All test data comes from the Stårblüm family storyline to maintain consistency and narrative coherence. Exceptions only for:

- Stress testing (many entities)
- Unicode edge cases
- Error condition simulation

### 3. **Two Testing Patterns**

- **Service calls via entities**: Full end-to-end integration testing
- **Direct coordinator API**: Fast business logic testing. Only use as exception when service calls are not practical for specific test

### 4. **Modern Architecture Focus**

Tests emphasize:

- YAML scenario loading via `setup_from_yaml()`
- Dashboard helper sensor as single source of truth
- Import from `tests.helpers` (not direct const.py)
- Clean separation: setup → test → validate

## 🚀 Quick Start

See `AGENT_TEST_CREATION_INSTRUCTIONS.md` for detailed patterns and examples.

```python
# Basic test pattern
@pytest.fixture
async def scenario_minimal(hass, mock_hass_users):
    return await setup_from_yaml(hass, mock_hass_users, "tests/scenarios/scenario_minimal.yaml")

async def test_something(hass, scenario_minimal):
    # Test implementation using scenario data
```

---

_Note: Legacy test files remain in `tests/legacy/` for reference but use outdated patterns. All new tests should follow the modern YAML scenario approach documented here._
