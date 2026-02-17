# Quality Remediation - Runtime Data Migration Details

## Supporting Document for QUALITY_SCALE_REMEDIATION_IN-PROCESS.md

This document provides the exact line-by-line changes needed for Phase 1.

---

## Summary: 41 Source File Patterns + 11 Test File Patterns

### Source Files Breakdown

| File              | Patterns | Lines                                                                                                                                    |
| ----------------- | -------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| `__init__.py`     | 8        | 45, 52, 239, 277, 278, 286, 308, 309                                                                                                     |
| `services.py`     | 25       | 391, 549, 670, 838, 887, 947, 1017, 1087, 1226, 1350, 1436, 1553, 1602, 1703, 1777, 1842, 1915, 1979, 2053, 2115, 2189, 2240, 2303, 2331 |
| `options_flow.py` | 2        | 3632, 4428                                                                                                                               |
| `sensor.py`       | 1        | 111                                                                                                                                      |
| `button.py`       | 1        | 118                                                                                                                                      |
| `select.py`       | 1        | 41                                                                                                                                       |
| `calendar.py`     | 1        | 35                                                                                                                                       |
| `datetime.py`     | 1        | 34                                                                                                                                       |
| `diagnostics.py`  | 2        | 35, 58                                                                                                                                   |

**Total Source Patterns: 41**

### Test Files Breakdown

| File                                      | Patterns | Lines              |
| ----------------------------------------- | -------- | ------------------ |
| `tests/helpers/setup.py`                  | 2        | 1153, 1168         |
| `tests/helpers/flow_test_helpers.py`      | 1        | 396                |
| `tests/test_ha_user_id_options_flow.py`   | 4        | 123, 161, 220, 259 |
| `tests/test_performance.py`               | 1        | 38                 |
| `tests/test_performance_comprehensive.py` | 1        | 88                 |
| `tests/test_options_flow_entity_crud.py`  | 2        | 583, 601           |

**Total Test Patterns: 11 (in 6 files)**

---

## Migration Strategy

### Step 1: Define Type Alias

**File**: `custom_components/kidschores/coordinator.py` (near line 25)

```python
# Add after imports, before class definition
from homeassistant.config_entries import ConfigEntry

# Type alias for typed config entry access
type KidsChoresConfigEntry = ConfigEntry["KidsChoresDataCoordinator"]
```

### Step 2: Update `__init__.py`

**Current pattern** (line ~176):

```python
hass.data.setdefault(const.DOMAIN, {})[entry.entry_id] = {
    const.COORDINATOR: coordinator,
    const.STORE: store,
}
```

**New pattern**:

```python
# Store coordinator in runtime_data (modern HA pattern)
entry.runtime_data = coordinator
# Note: Store is accessible via coordinator.store
```

**Session-scoped flags** (keep in `hass.data` - these are NOT entry-specific):

```python
# These track "did X happen this HA session" - NOT entry data
startup_backup_key = f"{const.DOMAIN}_startup_backup_created_{entry.entry_id}"
cleanup_key = f"{const.DOMAIN}_entity_cleanup_done_{entry.entry_id}"
# These remain in hass.data - correct usage
```

### Step 3: Update Platform Files

**Pattern for all platforms**:

Before:

```python
async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities
):
    data = hass.data[const.DOMAIN][entry.entry_id]
    coordinator: KidsChoresDataCoordinator = data[const.DATA_COORDINATOR]
```

After:

```python
from .coordinator import KidsChoresConfigEntry

async def async_setup_entry(
    hass: HomeAssistant, entry: KidsChoresConfigEntry, async_add_entities
):
    coordinator = entry.runtime_data
```

### Step 4: Update Services

Services need special handling because they use `entry_id` string lookups.

**Current pattern** (services.py):

```python
coordinator: KidsChoresDataCoordinator = hass.data[const.DOMAIN][entry_id][const.COORDINATOR]
```

**New pattern** (requires config entry lookup):

```python
# Get config entry by ID, then access runtime_data
entry = hass.config_entries.async_get_entry(entry_id)
if not entry:
    raise HomeAssistantError(f"Config entry {entry_id} not found")
coordinator = entry.runtime_data
```

**Or use helper function**:

```python
# Add to services.py or kc_helpers.py
def get_coordinator_from_entry_id(
    hass: HomeAssistant, entry_id: str
) -> KidsChoresDataCoordinator:
    """Get coordinator from config entry ID."""
    entry = hass.config_entries.async_get_entry(entry_id)
    if not entry or entry.domain != const.DOMAIN:
        raise HomeAssistantError(
            translation_domain=const.DOMAIN,
            translation_key=const.TRANS_KEY_ERROR_ENTRY_NOT_FOUND,
        )
    return entry.runtime_data
```

---

## Store Access Pattern

**Decision**: Store remains accessible via `coordinator.store`

The coordinator already has a store reference:

```python
class KidsChoresDataCoordinator:
    def __init__(self, hass, entry, store):
        self.store = store  # Already exists!
```

So accessing store becomes:

```python
# Old
store = hass.data[const.DOMAIN][entry.entry_id][const.STORE]

# New
coordinator = entry.runtime_data
store = coordinator.store
```

---

## Test File Updates

### `tests/helpers/setup.py`

**Line 1153**:

```python
# Old
coordinator = hass.data[const.DOMAIN][config_entry.entry_id][const.COORDINATOR]

# New
coordinator = config_entry.runtime_data
```

### `tests/conftest.py` (fixture update)

Ensure the mock config entry fixture sets `runtime_data`:

```python
@pytest.fixture
async def init_integration(hass, mock_config_entry, ...):
    """Set up the integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Verify runtime_data is set
    assert mock_config_entry.runtime_data is not None
    return mock_config_entry
```

---

## Validation Checklist

After migration, run these checks:

```bash
# 1. No legacy patterns remain in source
grep -r "hass\.data\[const\.DOMAIN\]\[entry" custom_components/kidschores/
# Expected: 0 results

# 2. No legacy patterns remain in tests (except mocking setup)
grep -r "hass\.data\[.*DOMAIN.*\]\[.*entry" tests/
# Expected: Only in fixture setup, not in test assertions

# 3. All tests pass
python -m pytest tests/ -v --tb=line

# 4. Linting passes
./utils/quick_lint.sh --fix

# 5. Type checking passes
mypy custom_components/kidschores/
```

---

## Rollback Plan

If migration causes issues:

1. Git revert to pre-migration commit
2. Keep `quality_scale.yaml` claim as `todo` until fixed
3. Document specific failure for debugging

---

## References

- [Home Assistant ConfigEntry.runtime_data docs](https://developers.home-assistant.io/docs/config_entries_index/#runtime-data)
- [Example: saunum integration](https://github.com/home-assistant/core/blob/dev/homeassistant/components/saunum/__init__.py)
- [Example: overseerr integration](https://github.com/home-assistant/core/blob/dev/homeassistant/components/overseerr/__init__.py)
