# KidsChores HA Integration - Agent Guide

**Version**: v0.5.0+ (Platinum Quality, Storage-Only Architecture)

**Platinum Quality** = 100% type hints + docstrings on all public methods + 95%+ test coverage + strict typing.

## 📚 Documentation Hierarchy

Read **only** what you need for your task:

- **[ARCHITECTURE.md](../docs/ARCHITECTURE.md)** - Data model, storage, versioning
- **[DEVELOPMENT_STANDARDS.md](../docs/DEVELOPMENT_STANDARDS.md)** - How to code (constants, logging, types, translations)
- **[QUALITY_REFERENCE.md](../docs/QUALITY_REFERENCE.md)** - Details on platinum quality requirements
- **[CODE_REVIEW_GUIDE.md](../docs/CODE_REVIEW_GUIDE.md)** - Phase 0 audit framework for reviewing code
- **[AGENT_TESTING_USAGE_GUIDE.md](../tests/AGENT_TESTING_USAGE_GUIDE.md)** - Test validation & debugging

## � Lexicon Warning (Critical)

**STOP using "Entity" for data records!** This causes catastrophic confusion.

| ❌ NEVER Say   | ✅ ALWAYS Say                 | Example                            |
| -------------- | ----------------------------- | ---------------------------------- |
| "Chore Entity" | "Chore Item" / "Chore Record" | "Update the Chore Item in storage" |
| "Kid Entity"   | "Kid Item" / "Kid Record"     | "Fetch Kid Item by UUID"           |
| "Badge Entity" | "Badge Item" / "Badge Record" | "Create new Badge Item"            |

**Remember**:

- **Item/Record** = JSON data in `.storage/kidschores_data`
- **Entity** = Home Assistant platform object (Sensor, Button, Select)
- **Entity ID** = HA registry string like `sensor.kc_alice_points`

**When in doubt**: If it has a UUID and lives in storage, it's an **Item**. If it has an `entity_id` and lives in HA registry, it's an **Entity**.

## 🦾 Definition of Done (Non-Negotiable)

**Nothing is complete until ALL THREE pass**:

```bash
./utils/quick_lint.sh --fix    # Must pass (includes boundary checks)
mypy custom_components/kidschores/  # Zero errors required
python -m pytest tests/ -v --tb=line  # All tests pass
```

**Integrated Quality Gates** (as of January 2026):

- Ruff check/format (code quality + formatting)
- MyPy (type checking)
- **Boundary checker** (architectural rules) ← NEW

**Error Recovery**: If `mypy` fails more than twice on the same error, STOP and ask for clarification. Do NOT suppress with `# type: ignore`.

## ⚡ Core Principles (Follow These First)

### 1. No Hardcoded Strings

**ALL** user-facing text → `const.py` constants → `translations/en.json`

- Exceptions: `translation_domain=const.DOMAIN, translation_key=const.TRANS_KEY_*`
- Notifications: `TRANS_KEY_NOTIF_TITLE_*` / `TRANS_KEY_NOTIF_MESSAGE_*`
- Config flow errors: `CFOP_ERROR_*` → `TRANS_KEY_CFOF_*`

### 2. Identity = UUID Only

Use `internal_id` (UUID) for logic. **NEVER** use entity names for lookups.

### 3. Storage-Only Model

Entity data → `.storage/kidschores_data` (schema v42+)
Config entry → **9 system settings only** (points theme, intervals, retention)

**Details**: See [ARCHITECTURE.md § Data Architecture](../docs/ARCHITECTURE.md#data-architecture) for storage structure, system settings breakdown, and reload performance comparisons.

### 4. Type Hints Mandatory

100% coverage enforced by MyPy in CI/CD. Modern syntax: `str | None` not `Optional[str]`

**Type System Strategy** (See [ARCHITECTURE.md § Type System Architecture](../docs/ARCHITECTURE.md#type-system-architecture)):

- **TypedDict**: Static structures with fixed keys (entity definitions, config objects)
- **dict[str, Any]**: Dynamic structures accessed with variable keys (runtime-built data)
- **Goal**: Achieve zero mypy errors without type suppressions by matching types to actual code patterns

### 5. Lazy Logging Only

```python
const.LOGGER.debug("Value: %s", var)  # ✅ Correct
const.LOGGER.debug(f"Value: {var}")   # ❌ NEVER f-strings in logs
```

## 🧠 Logic Placement Cheat-Sheet

**Before writing ANY code, ask these questions:**

### 1. Does it need `hass`?

- **YES** → `helpers/` (if it's a tool) or `managers/` (if it's a workflow)
- **NO** → `utils/` (if it's a tool) or `engines/` (if it's logic)

### 2. Does it change state (write to storage)?

- **YES** → **MUST** be in `managers/` (only Managers can write)
- **NO** → `engines/` (read-only logic) or `utils/` (formatting)

### 3. Is it pure calculation?

- **YES** → `engines/` (schedule math, FSM transitions, point calculations)
- **NO** → Check if it needs HA objects (sensors, buttons)

### 4. Decision Tree Summary

```
                    Does it write to _data?
                           /        \
                         YES         NO
                          |           |
                    MANAGERS/    Does it need hass?
                                    /        \
                                  YES        NO
                                   |          |
                               HELPERS/   Is it pure?
                              or           /      \
                              MANAGERS/  YES      NO
                                          |        |
                                      ENGINES/  UTILS/
```

### 5. Examples

| Task                          | Location                      | Reason                     |
| ----------------------------- | ----------------------------- | -------------------------- |
| Calculate next chore due date | `engines/schedule_engine.py`  | Pure math, no HA, no state |
| Update kid points             | `managers/economy_manager.py` | Writes to storage          |
| Format points display         | `utils/math_utils.py`         | Pure function, no HA       |
| Get kid by user_id            | `helpers/entity_helpers.py`   | Needs HA registry access   |
| Parse datetime string         | `utils/dt_utils.py`           | Pure datetime parsing      |
| Build chore data dict         | `data_builders.py`            | Sanitization, no HA        |

### 6. CRUD Ownership Rules

**Non-Negotiable**: Only Manager methods can call `coordinator._persist()`.

**Forbidden**:

- ❌ `options_flow.py` writing to storage
- ❌ `services.py` calling `_persist()` directly
- ❌ Any file outside `managers/` modifying `_data`

**Correct Pattern**:

```python
# services.py - Service delegates to manager
async def handle_claim_chore(call: ServiceCall) -> None:
    chore_id = call.data[SERVICE_FIELD_CHORE_ID]
    await coordinator.chore_manager.claim_chore(chore_id)  # ✅ Manager handles write

# managers/chore_manager.py - Manager owns the write
async def claim_chore(self, chore_id: str) -> None:
    self._data[DATA_CHORES][chore_id]["state"] = CHORE_STATE_CLAIMED
    self.coordinator._persist()  # ✅ Only Managers do this
    async_dispatcher_send(self.hass, SIGNAL_SUFFIX_CHORE_UPDATED)
```

### 7. Signal-First Communication Rules

**Non-Negotiable**: Managers NEVER call other Managers' write methods directly. All cross-domain logic uses the Event Bus (Dispatcher).

**Why This Matters**:

- **Prevents circular dependencies** between managers
- **Enables testability** - each manager can be tested in isolation
- **Maintains data consistency** - listeners only react to confirmed state changes
- **Avoids "phantom state"** - no signals for operations that failed

**Pattern**:

```python
# ❌ WRONG: Direct manager coupling
await self.coordinator.economy_manager.deposit(kid_id, 50)

# ✅ CORRECT: Signal-based communication
self.emit(const.SIGNAL_SUFFIX_BADGE_EARNED, kid_id=kid_id, points=50)
# EconomyManager listens for BADGE_EARNED and deposits automatically
```

**Transactional Integrity (Critical)**:

```python
async def create_chore(self, user_input: dict[str, Any]) -> dict[str, Any]:
    # 1. Build the entity dict
    chore_dict = db.build_chore(user_input)
    internal_id = chore_dict[const.DATA_CHORE_INTERNAL_ID]

    # 2. Write to in-memory storage (atomic operation)
    self._data[DATA_CHORES][internal_id] = dict(chore_dict)

    # 3. Persist
    self.coordinator._persist()

    # 4. ONLY emit signal after successful write ⚠️
    self.emit(const.SIGNAL_SUFFIX_CHORE_CREATED, chore_id=internal_id)

    return chore_dict
```

**Rule**: Emit signals ONLY after `_persist()` succeeds. Never emit in a `try` block before persistence.

**Reference**: [DEVELOPMENT_STANDARDS.md § 5.3](../docs/DEVELOPMENT_STANDARDS.md#53-event-architecture-manager-communication)

## 🎯 Fast Implementation Strategy

### Before Writing Code

1. Check if helper exists: `helpers/entity_helpers.py` (entity lookups), `helpers/flow_helpers.py` (flow validation)
2. Find constant: `grep TRANS_KEY custom_components/kidschores/const.py`
3. Use test scenario: `scenario_medium` (most common), `scenario_full` (complex)

### While Writing Code

- Copy patterns from existing files (don't invent new patterns)
- **Consolidate duplicates**: If code appears 2+ times, extract to helper function
- **Verify coordinator methods**: When editing `coordinator.py`, search file FIRST to verify method exists. Never assume methods exist by name.
- Use `conftest.py` helpers: `get_kid_by_name()`, `construct_entity_id()`
- Mock notifications: `patch.object(coordinator, "_notify_kid", new=AsyncMock())`

### After Writing Code

Run quality gates (**in this order**):

1. `./utils/quick_lint.sh --fix` (catches most issues fast)
2. `mypy custom_components/kidschores/` (type errors)
3. `python -m pytest tests/ -v` (validates behavior)

## 🚫 Common Mistakes (Avoid These)

❌ Calling "Chore" an "Entity" → ✅ Use "Chore Item" or "Chore Record"
❌ Hardcoded strings → ✅ Use `const.TRANS_KEY_*`
❌ `Optional[str]` → ✅ Use `str | None`
❌ F-strings in logs → ✅ Use lazy logging `%s`
❌ Entity names for lookups → ✅ Use `internal_id` (UUID)
❌ Touching `config_entry.data` → ✅ Use `.storage/kidschores_data`
❌ Direct storage writes → ✅ Use Manager method that calls `coordinator._persist()`
❌ Importing `homeassistant` in `utils/` → ✅ Keep utils pure (no HA imports)
❌ Writing to `_data` outside Managers → ✅ Delegate to Manager methods

## 📦 Quick Reference

**Key Files**:

- `const.py` - All constants (TRANS_KEY_*, DATA_*, CFOF_*, SERVICE_*, etc.)
- `coordinator.py` - Infrastructure hub (routing, persistence, manager lifecycle)
- `managers/` - Stateful workflows (ChoreManager, EconomyManager, UIManager, StatisticsManager, etc.)
- `helpers/` - HA-aware utilities (entity, flow, device, auth, backup, translation helpers)
- `utils/` - Pure Python utilities (datetime, math, validation, formatting)
- `translations/en.json` - Master translation file

**Constant Naming Patterns** (See [DEVELOPMENT_STANDARDS.md § 3. Constant Naming Standards](../docs/DEVELOPMENT_STANDARDS.md#3-constant-naming-standards)):

- `DATA_*` = Storage keys for Domain Items (singular names: `DATA_KID_*`, `DATA_CHORE_*`)
- `CFOF_*` = Config/Options flow input fields (plural with `_INPUT_`)
- `CONF_*` = System settings in config_entry.options (9 settings only)
- `TRANS_KEY_*` = Translation identifiers
- `ATTR_*` = Entity state attributes (for HA Entities, not Items)
- `SERVICE_*` / `SERVICE_FIELD_*` = Service actions and parameters

**DateTime Functions** (See [DEVELOPMENT_STANDARDS.md § 6. DateTime & Scheduling Standards](../docs/DEVELOPMENT_STANDARDS.md#6-datetime--scheduling-standards)):

- ALWAYS use `dt_*` helpers from `utils/dt_utils.py` (never raw `datetime` module)
- Examples: `dt_now_iso()`, `dt_parse()`, `dt_add_interval()`, `dt_next_schedule()`

**Common Test Scenarios** (run after making changes):

```bash
pytest tests/test_workflow_*.py -v  # Entity state validation
pytest tests/test_config_flow.py -v  # UI flow changes
pytest tests/ -x  # Stop on first failure (debugging)
```

**Datetime**: Always UTC-aware ISO strings. Use `utils/dt_utils.py` helper functions (dt_now(), dt_parse(), dt_to_utc())

---

**Agent Tip**: When stuck, run `./utils/quick_lint.sh --fix` first. It catches 80% of issues instantly.
