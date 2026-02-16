# Phase 0 Implementation Handoff - Quick Reference

**Status**: ✅ Ready for Implementation
**Estimated Effort**: 2-3 focused sessions (~4-6 hours)
**Primary Guide**: [LAYERED_ARCHITECTURE_VNEXT_SUP_PHASE0_IMPL.md](./LAYERED_ARCHITECTURE_VNEXT_SUP_PHASE0_IMPL.md)

---

## Critical Instructions

### 🚨 Placement is Critical

**DO NOT add constants in the middle of existing groupings.** Follow exact placement instructions:

| File            | Line | Context Marker                                                          |
| --------------- | ---- | ----------------------------------------------------------------------- |
| `const.py`      | 60   | After `STORAGE_VERSION: Final = 1`                                      |
| `kc_helpers.py` | 210  | After Entity Registry section, before `def _get_kidschores_coordinator` |

**Look for these exact context lines in implementation guide before inserting code.**

---

## Implementation Sequence

Follow these steps **in order**:

### Step 1: Add 56 Signal Constants to `const.py`

- **Location**: Line 60 (after Storage section)
- **Section header**: `# Event Infrastructure (Phase 0: Layered Architecture Foundation)`
- **Validation**: `grep "SIGNAL_SUFFIX_" custom_components/kidschores/const.py | wc -l` → should return 56

### Step 2: Add `get_event_signal()` Helper to `kc_helpers.py`

- **Location**: Line 210 (after Entity Registry section)
- **Section header**: `# Event Signal Helpers`
- **Validation**: `python -c "from custom_components.kidschores.kc_helpers import get_event_signal; print(get_event_signal('test123', 'points_changed'))"`
- **Expected output**: `kidschores_test123_points_changed`

### Step 3: Create `managers/base_manager.py`

- **New file**: `custom_components/kidschores/managers/base_manager.py`
- **Contains**: Abstract `BaseManager` class with `emit()` and `listen()` methods
- **Key imports**: `async_dispatcher_send`, `async_dispatcher_connect` from HA
- **Validation**: `mypy custom_components/kidschores/managers/base_manager.py`

### Step 4: Create `managers/__init__.py`

- **New file**: `custom_components/kidschores/managers/__init__.py`
- **Exports**: `BaseManager` only (concrete managers added in later phases)
- **Validation**: `python -c "from custom_components.kidschores.managers import BaseManager; print(BaseManager)"`

### Step 5: Add 15 Event Payload TypedDicts to `type_defs.py`

- **Location**: End of file (~line 800+)
- **Section header**: `# Event Payloads (Phase 0: Layered Architecture Foundation)`
- **Validation**: `grep "Event = TypedDict" custom_components/kidschores/type_defs.py | wc -l` → should return 15

### Step 6: Create `tests/test_event_infrastructure.py`

- **New file**: `tests/test_event_infrastructure.py`
- **Contains**: 5 tests for `get_event_signal()`, multi-instance isolation, BaseManager
- **Validation**: `pytest tests/test_event_infrastructure.py -v` → all 5 tests pass

### Step 7: Run Full Validation Suite

```bash
./utils/quick_lint.sh --fix         # Must score 9.5+/10
mypy custom_components/kidschores/  # Zero errors required
pytest tests/test_event_infrastructure.py -v  # All 5 tests pass
pytest tests/ -v --tb=line          # Full regression (no breakage)
```

---

## Quick Reference

### What Gets Added

| Category         | Count | Examples                                                       |
| ---------------- | ----- | -------------------------------------------------------------- |
| Signal constants | 56    | `SIGNAL_SUFFIX_POINTS_CHANGED`, `SIGNAL_SUFFIX_CHORE_APPROVED` |
| Helper functions | 1     | `get_event_signal(entry_id, suffix)`                           |
| Manager classes  | 1     | `BaseManager` (abstract base class)                            |
| TypedDicts       | 15    | `PointsChangedEvent`, `ChoreApprovedEvent`, `BadgeEarnedEvent` |
| Test cases       | 5     | Signal formatting, multi-instance, emit/listen                 |

### What Does NOT Get Modified

- ✅ Coordinator files (no changes in Phase 0)
- ✅ Entity platform files (no changes in Phase 0)
- ✅ Existing tests (no modifications, only additions)
- ✅ Config flow (no changes in Phase 0)

---

## Success Criteria

- [ ] All 56 constants added in **correct location** (line 60 of `const.py`)
- [ ] `get_event_signal()` helper added in **correct location** (line 210 of `kc_helpers.py`)
- [ ] `BaseManager` abstract class created with emit/listen methods
- [ ] `managers/__init__.py` created with exports
- [ ] 15 event payload TypedDicts added to `type_defs.py`
- [ ] Test file created with 5 passing tests
- [ ] Lint score 9.5+/10 (run `./utils/quick_lint.sh --fix`)
- [ ] MyPy zero errors (run `mypy custom_components/kidschores/`)
- [ ] All tests pass (run `pytest tests/ -v --tb=line`)

---

## Reference Documents

**Primary**:

- [LAYERED_ARCHITECTURE_VNEXT_SUP_PHASE0_IMPL.md](./LAYERED_ARCHITECTURE_VNEXT_SUP_PHASE0_IMPL.md) - Complete implementation guide with code blocks

**Supporting**:

- [LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md](./LAYERED_ARCHITECTURE_VNEXT_IN-PROCESS.md) - Main plan with architectural decisions
- [LAYERED_ARCHITECTURE_VNEXT_SUP_EVENT_PATTERN.md](./LAYERED_ARCHITECTURE_VNEXT_SUP_EVENT_PATTERN.md) - Event pattern analysis
- [../DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Constants, logging, type conventions
- [../ARCHITECTURE.md](../ARCHITECTURE.md) - Data model context

---

## Common Pitfalls to Avoid

❌ **Adding constants at end of file** → Constants should go at line 60 (after Storage section)
❌ **Adding helper at end of file** → Helper should go at line 210 (after Entity Registry section)
❌ **Skipping validation steps** → Run lint/mypy/pytest after each step
❌ **Modifying coordinator** → Phase 0 is infrastructure only; coordinator unchanged
❌ **Implementing all signals immediately** → Define all 56 constants now, implement as needed later

---

**Last Updated**: 2026-01-24
**Next Phase**: Phase 1 - Infrastructure Cleanup (after Phase 0 complete)
