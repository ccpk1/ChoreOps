# ChoreOps Integration Architecture

**Integration Version**: 0.5.0+
**Storage Schema Version**: 43 (Storage-Only Mode with Meta Section)
**Quality Scale Level**: ⭐ **Platinum** (Meets All Quality Standards)
**Date**: February 2026

---

## 🎯 Platinum Quality Standards

This integration **unofficially** meets **Home Assistant Platinum** quality level requirements. See [quality_scale.yaml](../custom_components/choreops/quality_scale.yaml) for current rule status and [AGENTS.md](../../core/AGENTS.md) and [Home Assistant's Integration Quality Scale](https://developers.home-assistant.io/docs/integration_quality_scale_index/) for ongoing Home Assistant quality standards.

### Home Assistant Quality Standards Reference

For ongoing reference and to maintain Platinum certification, consult:

- **[QUALITY_REFERENCE.md](QUALITY_REFERENCE.md)** - Platinum compliance mapping
  - Maps ChoreOps architecture to Home Assistant Platinum requirements
  - Documents how layered architecture enforces quality standards
  - Provides evidence locations and architectural validation references

- **[DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md)** - Prescriptive coding standards
  - Git workflows, constant naming conventions, data write standards
  - Localization patterns, type hints, logging practices
  - Event-driven communication and manager coupling rules

---

## 🔡 Lexicon Standards (Critical)

**To prevent confusion between Home Assistant's registry and ChoreOps internal data:**

| Term                  | Usage                                             | Example                                |
| --------------------- | ------------------------------------------------- | -------------------------------------- |
| **Item** / **Record** | A data entry in `.storage/choreops/choreops_data` | "A Chore Item", "Kid Record"           |
| **Domain Item**       | Collective term for all stored data types         | Kids, Chores, Badges (as JSON records) |
| **Internal ID**       | UUID identifying a stored record                  | `kid_id`, `chore_id` (always UUIDs)    |
| **Entity**            | ONLY a Home Assistant platform object             | Sensor, Button, Select, Calendar       |
| **Entity ID**         | The Home Assistant registry string                | `sensor.kc_alice_points`               |
| **Entity Data**       | State attributes of an HA entity                  | What appears in `more-info` dialog     |

**Critical Rule**: Never use "Entity" when referring to a Chore, Kid, Badge, etc. These are **Items** stored in JSON, not HA registry objects.

**Storage Contains**: Domain Items (Kids, Chores, Badges, etc.) as JSON records with UUIDs.

**HA Registry Contains**: Entities (Sensors, Buttons) that are ephemeral wrappers representing the state of Domain Items to the user.

---

## Layered Architecture

**Component Responsibilities & Constraints**

| Component        | Stateful? | Hass Objects? | Side Effects? | Responsibility                                                      | File Location      |
| ---------------- | --------- | ------------- | ------------- | ------------------------------------------------------------------- | ------------------ |
| **Engine**       | ❌ No     | ❌ Forbidden  | ❌ Forbidden  | Pure logic: FSM transitions, schedule calculations, recurrence math | `engines/`         |
| **Manager**      | ✅ Yes    | ✅ Yes        | ✅ Yes        | Orchestration: State changes, firing events, calling `_persist()`   | `managers/`        |
| **Util**         | ❌ No     | ❌ Forbidden  | ❌ No         | Pure functions: datetime parsing, point math, validation            | `utils/`           |
| **Helper**       | ❌ No     | ✅ Yes        | ✅ Yes        | HA-specific tools: Registry lookups, auth checks, DeviceInfo        | `helpers/`         |
| **Data Builder** | ❌ No     | ❌ Forbidden  | ❌ No         | Sanitization: Strip strings, validate types, set timestamps         | `data_builders.py` |
| **Coordinator**  | ✅ Yes    | ✅ Yes        | ✅ Yes        | Infrastructure hub: holds `_data`, `_persist()`, Manager routing    | `coordinator.py`   |

### Architectural Rules

**Rule of Purity**: Files in `utils/`, `engines/`, and `data_builders.py` are **prohibited** from importing `homeassistant.*`. They must be testable in a standard Python environment without HA fixtures.

**Single Write Path**: Only Manager methods may call `coordinator._persist()`. UI flows (`options_flow.py`) and services (`services.py`) must delegate to Manager methods.

**Event-Driven Orchestration**: Managers communicate via the Dispatcher (e.g., `SIGNAL_SUFFIX_KID_UPDATED`). Direct cross-manager calls are forbidden to prevent tight coupling.

**Async Listener Contract**: Dispatcher listeners that modify state, persist data, update entities, or call async APIs must be `async def`. Sync listeners are allowed only for read-only or log-only handlers.

**Thread-Safe Scheduling Rule**: In manager listener paths, avoid manual thread marshaling patterns such as `call_soon_threadsafe(...async_create_task...)` when direct awaited async handlers are possible. Use loop-safe scheduling (`hass.add_job`) only for intentional fire-and-forget operations.

**Payload Contract Stability**: Async listener migrations must preserve existing signal payload keys and defaults.

**Automatic Metadata**: All data builders must set `updated_at` timestamps. Managers never manually set timestamps.

### Infrastructure Coordinator Pattern

The Coordinator is a **pure infrastructure hub** with zero domain knowledge:

```
┌─────────────────────────────────────────────────────────────┐
│            Coordinator (Infrastructure Only)                │
│  async_config_entry_first_refresh():                        │
│    1. Load storage (via Store)                              │
│    2. await system_manager.ensure_data_integrity()          │
│    3. _persist()                                            │
│                                                             │
│  Owns: _data holder, _persist(), Store wrapper              │
│  Owns NOT: domain logic, timers, manager orchestration      │
└─────────────────────────────────────────────────────────────┘
```

**Boot Cascade**: Managers self-organize via lifecycle signals:

```
DATA_READY → ChoreManager → CHORES_READY
                              ↓
         StatisticsManager → STATS_READY
                              ↓
       GamificationManager → GAMIFICATION_READY
```

**Timer Ownership**: SystemManager owns ALL `async_track_time_change` calls. Other managers listen to `MIDNIGHT_ROLLOVER` and `PERIODIC_UPDATE` signals.

---

## Data Architecture

```
┌─────────────────────────────────────────────────────────────┐
│ ChoreOps Integration Data Architecture                     │
└─────────────────────────────────────────────────────────────┘

┌────────────────────────┐        ┌──────────────────────────┐
│ config_entry.options   │        │ .storage/choreops/choreops_data │
│ (System Settings Only) │        │ (Domain Items + Runtime) │
├────────────────────────┤        ├──────────────────────────┤
│ • points_label         │        │ • kids                   │
│ • points_icon          │        │ • parents                │
│ • update_interval      │        │ • chores                 │
│ • calendar_show_period │        │ • badges                 │
│ • retention_*          │        │ • rewards                │
│ • points_adjust_values │        │ • penalties              │
│                        │        │ • bonuses                │
│ (9 settings total)     │        │ • achievements           │
│                        │        │ • challenges             │
│ Requires Reload: YES   │        │                          │
│                        │        │ • meta.schema_version:50+│
│                        │        │                          │
│                        │        │ Requires Reload: NO      │
└────────────────────────┘        └──────────────────────────┘
         ↓                                   ↓
    [Reload Flow]                    [Coordinator Refresh]
```

### Storage-Only Mode Advantages

**Before (Legacy)**:

- Config entry size: 50-200KB (limited by Home Assistant)
- Integration reload: Must process all entity data from config
- Options flow: Complex merging logic to avoid data loss
- Startup time: Slow (reads + migrates large config)

**After (v0.5.0)**:

- Config entry size: < 1KB (only 9 settings)
- Integration reload: Only processes system settings (fast)
- Options flow: Direct storage writes (simple)
- Startup time: Fast (reads lightweight config, storage loads once)

#### Reload Performance Comparison

```
┌──────────────────────────────────────────────────┐
│ Integration Reload Time (with 20 kids, 50 chores)│
├──────────────────────────────────────────────────┤
│ Legacy (config-based):     2.5s                  │
│ v0.5.0 (storage-only):     0.3s                  │
│                                                  │
│ Improvement: 8x faster                           │
└──────────────────────────────────────────────────┘
```

### System Settings (config_entry.options)

These settings are stored in `config_entry.options` and require integration reload to take effect:

| Setting                | Type   | Default                 | Used By             | Why Reload Required               |
| ---------------------- | ------ | ----------------------- | ------------------- | --------------------------------- |
| `points_label`         | string | "Points"                | Sensor translations | Entity name changes               |
| `points_icon`          | string | "mdi:star-outline"      | Point sensors       | Entity icon changes               |
| `update_interval`      | int    | 5 (minutes)             | Coordinator         | Polling interval changes          |
| `calendar_show_period` | int    | 90 (days)               | Calendar platform   | Entity config changes             |
| `backups_max_retained` | int    | 5 (count per type)      | backup helper       | Data protection setting           |
| `retention_daily`      | int    | 7 (days)                | Stats cleanup       | Runtime read (no reload needed\*) |
| `retention_weekly`     | int    | 5 (weeks)               | Stats cleanup       | Runtime read (no reload needed\*) |
| `retention_monthly`    | int    | 3 (months)              | Stats cleanup       | Runtime read (no reload needed\*) |
| `retention_yearly`     | int    | 3 (years)               | Stats cleanup       | Runtime read (no reload needed\*) |
| `points_adjust_values` | list   | `[+1,-1,+2,-2,+10,-10]` | Button entities     | Entity creation/removal           |
| `show_legacy_entities` | bool   | `false`                 | Entity setup        | Conditional entity creation       |
| `kiosk_mode`           | bool   | `false`                 | Kid claim buttons   | Authorization behavior toggle     |

**Note**: Retention settings are kept in `config_entry.options` for consistency even though they don't strictly require reload (runtime reads via `self.config_entry.options.get(...)`). This keeps all user-configurable settings in one place.

#### Settings Update Flow

```python
# options_flow.py
async def _update_system_settings_and_reload(self):
    """Update system settings in config entry and reload integration."""
    self.hass.config_entries.async_update_entry(
        self.config_entry,
        options=self._entry_options  # System settings and feature flags
    )
    # Full integration reload triggered automatically
```

---

### Data (Storage)

#### Storage Location

**File**: `.storage/choreops/choreops_data`
**Format**: JSON
**Version**: `STORAGE_VERSION = 1` (Home Assistant Store format), `meta.schema_version = 42` (ChoreOps data structure)

#### Storage Structure

```json
{
    "version": 1,
    "minor_version": 1,
    "key": "choreops_data",
    "data": {
        "meta": {
            "schema_version": 42,
            "last_migration_date": "2025-12-18T10:00:00+00:00",
            "migrations_applied": [
                "datetime_utc",
                "chore_data_structure",
                "kid_data_structure",
                "badge_restructure",
                "cumulative_badge_progress",
                "badges_earned_dict",
                "point_stats",
                "chore_data_and_streaks"
            ]
        },
        "kids": {
            "kid_uuid_1": {
                "internal_id": "kid_uuid_1",
                "name": "Sarah",
                "points": 150,
                "ha_user_id": "user_123",
                "badges_earned": {...},
                "point_stats": {...},
                "chore_data": {...},
                ...
            }
        },
        "parents": {...},
        "chores": {...},
        "badges": {...},
        "rewards": {...},
        "penalties": {...},
        "bonuses": {...},
        "achievements": {...},
        "challenges": {...}
    }
}
```

**Storage Contains**: Domain Items (JSON records with UUIDs), NOT Home Assistant Entities.

**Entities** (Sensors, Buttons) are ephemeral platform objects created at runtime to represent these Items in the HA UI. Entity states reflect Item data but are not persisted—only the underlying Items are stored.

### Coordinator Persistence Pattern

All Domain Item modifications follow this pattern:

```python
# 1. Modify data in memory
self._data[const.DATA_KIDS][kid_id]["points"] = new_points

# 2. Persist to storage
self._persist()  # Writes to .storage/choreops/choreops_data

# 3. Notify entities
self.async_update_listeners()  # Entities refresh from coordinator
```

**Key Method**: `coordinator._persist()` (Lines 8513-8517)

```python
def _persist(self):
    """Save to persistent storage."""
    self.storage_manager.set_data(self._data)
    self.hass.add_job(self.storage_manager.async_save)
```

### Data Persistence Principles

ChoreOps separates **source data** (persisted) from **derived data** (computed at runtime):

| Layer                  | Example                                     | Persisted? | Purpose                             |
| ---------------------- | ------------------------------------------- | ---------- | ----------------------------------- |
| **Period Buckets**     | `daily["2025-01-28"]`, `weekly["2025-W04"]` | ✅ Yes     | Source of truth for historical data |
| **Stats Aggregations** | `approved_today`, `approved_week`           | ❌ No      | Derived views, rebuilt on refresh   |
| **All-Time Totals**    | `approved_all_time`                         | ✅ Yes     | No rollup source, must persist      |

**Historical Queries**: To find "chores completed 6 months ago", query the monthly period bucket directly—`chore_data["periods"]["monthly"]["2024-07"]`. Retention settings (`retention_daily`, etc.) control how long each granularity is kept.

**Implementation**: `StatisticsEngine.record_transaction()` writes to period buckets; `filter_persistent_stats()` strips temporal aggregations before storage; aggregations rebuild from buckets at coordinator refresh.

#### Statistics Period Bucket Key Generation (UTC for Storage, Local for Keys)

**Critical Principle**: Timestamps are stored as UTC ISO strings, but period bucket keys MUST use local timezone dates to reflect user's calendar days.

**Why**: A kid in New York completing a chore at 10 PM Monday should see stats recorded under "Monday", not "Tuesday" (which would occur if using UTC date at 3 AM Tuesday).

**Application**: Affects streak calculations, period statistics, and any logic that needs to query "yesterday's data" or "last week's totals".

---

## Versioning Architecture

ChoreOps uses a **dual versioning system**:

### 1. Home Assistant Store Version (File Format)

```json
{
    "version": 1,          // HA Store format version (always 1)
    "minor_version": 1,    // HA Store minor version
    "key": "choreops_data",
    "data": { ... }        // ChoreOps data with schema_version
}
```

### 2. ChoreOps Schema Version (Data Structure)

The **`meta.schema_version`** field in storage data determines the integration's operational mode. Schema 42 is the current version:

| Schema Version | Mode                  | Behavior                                                        |
| -------------- | --------------------- | --------------------------------------------------------------- |
| < 42           | Legacy (Pre-0.5.0)    | Reads entity data from `config_entry.options` or legacy storage |
| ≥ 42           | Storage-Only (0.5.0+) | Reads entity data exclusively from storage with meta section    |

**Key Files**:

- `custom_components/choreops/const.py`: `SCHEMA_VERSION_STORAGE_ONLY = 42`
- `custom_components/choreops/coordinator.py`: Main coordinator (7,591 lines), uses multiple inheritance
- `custom_components/choreops/coordinator_chore_operations.py`: Chore operations class (3,852 lines), 43 methods in 11 sections
- `custom_components/choreops/__init__.py`: Lines 45-51 (migration detection)

**Code Organization**: Coordinator uses Python's multiple inheritance to organize features:

- ChoreOperations class provides 43 chore lifecycle methods organized into 11 logical sections (§1-§11)
- TYPE_CHECKING pattern provides type hints without runtime imports
- Pattern enables extraction of 3,688 lines (34% reduction) while maintaining single coordinator interface

**Legacy Format (v41 and below)**:

```json
{
    "data": {
        "schema_version": 41,  // Top-level schema version
        "kids": {...}
    }
}
```

**Modern Format (v42+)**:

```json
{
    "data": {
        "meta": {
            "schema_version": 42,                    // Nested in meta section
            "last_migration_date": "2025-12-18...",
            "migrations_applied": ["badge_restructure", ...]
        },
        "kids": {...}
    }
}
```

#### Why Meta Section?

1. **Test Framework Compatibility**: Home Assistant test framework auto-injects `schema_version: 42` at the top level, breaking migration tests. The nested `meta.schema_version` is protected from this interference.

2. **Semantic Separation**: Version metadata is separated from entity data, following database schema versioning patterns.

3. **Migration Tracking**: The `meta` section can track migration history, dates, and applied transformations.

---

## Landlord-Tenant Period Structure Data Ownership

**Pattern**: Managers create empty period containers (Landlord role), StatisticsEngine populates counter data (Tenant role).

### Ownership Division

**Domain Managers (Landlords)** responsible for ownership, creation, and deletion top-level period containers:

**StatisticsEngine (Tenant)** creates and writes all data inside those containers:

### Structure Hierarchy

```
┌──────────────────────────────────────────────────────┐
│ Landlord Layer (Managers)                            │
│ Creates: Empty top-level dicts                       │
├──────────────────────────────────────────────────────┤
│ kid["reward_periods"] = {}                  ← Empty  │
│ reward_data["periods"] = {}                 ← Empty  │
└──────────────────────────────────────────────────────┘
                      ↓
┌──────────────────────────────────────────────────────┐
│ Tenant Layer (StatisticsEngine)                      │
│ Populates: Period buckets, date keys, counter keys   │
├──────────────────────────────────────────────────────┤
│ periods["daily"] = {}                       ← Bucket │
│ periods["daily"]["2025-01-17"] = {}        ← Date   │
│ periods["daily"]["2025-01-17"]["claimed"] = 1        │
│ periods["daily"]["2025-01-17"]["approved"] = 0       │
│ periods["daily"]["2025-01-17"]["disapproved"] = 0    │
│ periods["daily"]["2025-01-17"]["points"] = 0.0       │
└──────────────────────────────────────────────────────┘
```

### Manager Responsibilities

| Manager            | Landlord Containers Created                       | Tenant Counters Tracked                      |
| ------------------ | ------------------------------------------------- | -------------------------------------------- |
| **ChoreManager**   | `kid["chore_periods"]`, `chore_data["periods"]`   | completed, approved, disapproved, points     |
| **RewardManager**  | `kid["reward_periods"]`, `reward_data["periods"]` | claimed, approved, disapproved, points       |
| **EconomyManager** | `kid["point_stats"]["transaction_history"]`       | deposits, withdrawals (via StatisticsEngine) |

**Analogy**: Manager builds the empty apartment building (landlord), StatisticsManager rents it and furnishes every room (tenant). No landlord should be doing interior decorating.

---

## Type System Architecture

**File**: [type_defs.py](../custom_components/choreops/type_defs.py)

ChoreOps uses a **hybrid type approach** balancing type safety with practical code patterns:

### TypedDict for Static Structures

Used for entities and configurations with fixed keys known at design time:

```python
class ParentData(TypedDict):
    """Fixed structure - all keys known."""
    internal_id: str
    name: str
    ha_user_id: str
    associated_kids: list[str]
    enable_notifications: bool
    # ...

class ChoreData(TypedDict):
    """Entity definition with fixed schema."""
    internal_id: str
    name: str
    state: str
    default_points: float
    # ...
```

**Benefits**:

- ✅ Full IDE autocomplete
- ✅ Mypy catches missing/wrong fields
- ✅ Self-documenting structure

### dict[str, Any] for Dynamic Structures

Used for runtime-constructed data accessed with variable keys:

```python
# Type alias with documentation
KidChoreDataEntry = dict[str, Any]
"""Per-chore tracking data accessed dynamically.

Common runtime pattern:
    chore_entry[field_name] = value  # field_name is a variable
"""

KidChoreStats = dict[str, Any]
"""Aggregated stats accessed with dynamic period keys.

Common runtime pattern:
    stats_data[period_key][stat_type] = count  # both are variables
"""
```

**Benefits**:

- ✅ Honest about actual code behavior
- ✅ Minimal type suppressions (1 in dynamic code vs 150+ if forcing TypedDict)
- ✅ Mypy focuses on real issues

**Note**: Variable-based key access (`entry[field_name]`) is efficient, idiomatic Python. Type suppressions are IDE-level hints only—they don't affect runtime performance or indicate code quality issues.

### Why Hybrid Approach?

**TypedDict requires literal string keys** but ChoreOps uses variable-based key access in ~30 locations:

```python
# Variable key access patterns (incompatible with TypedDict):
field_name = "last_approved" if approved else "last_claimed"
kid_chores_data[chore_id][field_name] = kid_name  # field_name is variable

for period_key in ["daily", "weekly", "monthly"]:
    periods_data[period_key][date_str] = stats  # period_key is variable
```

**Solution**: Match type system to actual code patterns. Use TypedDict where keys are static, dict[str, Any] where keys are dynamic. This achieves zero mypy errors without type suppressions.

### Type Safety Guidelines

| Structure Type      | Use TypedDict When             | Use dict[str, Any] When       |
| ------------------- | ------------------------------ | ----------------------------- |
| Entity definitions  | ✅ Keys are fixed in code      | ❌ Keys determined at runtime |
| Config objects      | ✅ Schema is static            | ❌ Schema varies by context   |
| Aggregations        | ❌ (period/stat keys vary)     | ✅ Keys built dynamically     |
| Per-entity tracking | ❌ (field names are variables) | ✅ Accessed with variables    |

See [DEVELOPMENT_STANDARDS.md](DEVELOPMENT_STANDARDS.md#type-system) for implementation details and [type_defs.py](../custom_components/choreops/type_defs.py) header for full rationale.

---

## Schedule Engine Architecture

### Unified Scheduling: Hybrid rrule + relativedelta Approach

The `engines/schedule.py` module provides a unified scheduling system for chores, badges, and challenges:

- **rrule (RFC 5545)**: Standard patterns (DAILY, WEEKLY, BIWEEKLY, MONTHLY, YEARLY) generate RFC 5545 RRULE strings for iCal export
- **relativedelta**: Period-end clamping (Jan 31 + 1 month = Feb 28) and DST-aware calculations
- **Why both?** rrule lacks month-end semantics; relativedelta lacks iCal compliance

### RecurrenceEngine Class

**Location**: `custom_components/choreops/engines/schedule.py`

**Key Methods**:

- `get_occurrences(start, end, limit=100)` → list[datetime]: Calculate recurrence instances in time window
- `to_rrule_string()` → str: Generate RFC 5545 RRULE for iCal export
- `add_interval()` → datetime: DST-safe interval arithmetic
- `snap_to_weekday()` → datetime: Advance to next applicable weekday

**Data Flow**: coordinator → RecurrenceEngine.get_occurrences() → calendar events (with RRULE) → entity_helpers adapters → chore/badge logic

### iCal Compatibility

Calendar events for timed recurring chores now include RFC 5545 RRULE strings, enabling Google Calendar API sync, CalDAV support, Outlook sync, and third-party calendar viewers (future phases). Full-day/multi-day events omit RRULE to preserve correct iCal semantics.

### Edge Case Handling

Covers 9 scenarios (EC-01 through EC-09): monthly clamping, leap year handling, year boundary crossing, applicable_days constraints, period-end calculations, DST transitions, midnight boundaries, custom base dates, and iteration safety limits.

### Runtime optimization notes (v0.5.0 hardening)

- **Daily expansion cap**: Calendar generation for `FREQUENCY_DAILY` and `FREQUENCY_DAILY_MULTI` is intentionally capped to `max(1, floor(calendar_show_period / 3))` days. Non-daily frequencies continue to use full show period.
- **Read-path caching**: `KidScheduleCalendar` caches generated event windows by `(window_start, window_end, revision)` and reuses those results for `async_get_events` and `event` to avoid duplicate expansion work.
- **Signal-first invalidation**: Calendar and recurrence artifacts are invalidated by explicit chore/challenge mutation signals rather than polling, preserving consistency with manager event architecture.
- **Manager scan caching**: `ChoreManager` keeps derived parse caches for due datetimes and reminder/window offsets; these caches are cleared on chore/kid mutation signals.

---

## Statistics Engine Architecture

The `engines/statistics.py` module provides unified time-series tracking for all period-based statistics across ChoreOps. It centralizes period key generation, transaction recording, and data pruning.

### Design Principles

- **Stateless**: No coordinator reference; operates on passed data structures
- **Consistent**: Single source of truth for period key generation (daily, weekly, monthly, yearly, all_time)
- **Efficient**: Batch updates with configurable auto-pruning

### StatisticsEngine Class

**Location**: `custom_components/choreops/engines/statistics.py`

**Key Methods**:

- `get_period_keys(reference_date)` → dict: Generate period identifiers (e.g., `{"daily": "2026-01-20", "weekly": "2026-W04", ...}`)
- `record_transaction(period_data, increments, include_all_time=True)` → None: Update multiple period buckets atomically
- `update_streak(container, streak_key, last_date_key)` → int: Calculate and return current streak
- `prune_history(period_data, retention_config)` → None: Remove old period data based on retention settings

**Data Flow**: coordinator → StatisticsEngine methods → mutated period_data → coordinator.\_persist()

### Uniform Period Structure

All entity types now share an identical 5-bucket period structure:

| Entity Type | daily | weekly | monthly | yearly | all_time |
| ----------- | :---: | :----: | :-----: | :----: | :------: |
| Chores      |  ✅   |   ✅   |   ✅    |   ✅   |    ✅    |
| Points      |  ✅   |   ✅   |   ✅    |   ✅   |    ✅    |
| Rewards     |  ✅   |   ✅   |   ✅    |   ✅   |    ✅    |
| Badges      |  ✅   |   ✅   |   ✅    |   ✅   |    ✅    |

**Benefits**:

- Identical logic paths for all entity types (no conditional code)
- Future achievements (e.g., "Earn 1000 lifetime points") become trivial
- Dashboard analytics get all-time stats for free
- Retention cleanup applies consistently everywhere

### Period Key Formats

```python
# Generated by StatisticsEngine.get_period_keys()
{
    "daily": "2026-01-20",      # PERIOD_FORMAT_DAILY: "%Y-%m-%d"
    "weekly": "2026-W04",       # PERIOD_FORMAT_WEEKLY: "%Y-W%V"
    "monthly": "2026-01",       # PERIOD_FORMAT_MONTHLY: "%Y-%m"
    "yearly": "2026"            # PERIOD_FORMAT_YEARLY: "%Y"
}
```

---

## Translation Architecture

ChoreOps utilizes a multi-tiered translation architecture to manage standard Home Assistant (HA) integration strings alongside specialized custom notifications and dashboard elements.

To support this localization, we use a professional workflow through Crowdin, supported by a granted **Open Source License**. This license enables ongoing collaboration by allowing the team to share direct links with contributors, who can then suggest improvements or provide new translations for the integration. These community-driven updates are then automatically synchronized back into the repository via our automated translation workflow.

### 1. Dual Translation Systems

The integration maintains two distinct systems to balance core HA requirements with specialized functional needs.

#### Standard Integration Translations

- **Location**: `custom_components/choreops/translations/en.json`.
- **Scope**: Governs exception messages, config flow UI, entity names/states, and service descriptions.
- **Implementation**: Utilizes the standard Home Assistant translation system via `hass.localize()` and `translation_key` attributes.
- **Coordinator Notifications**: The Coordinator uses the `async_get_translations()` API to manage 36 dynamic notification keys for chore approvals, reward redemptions, and system reminders.

#### Custom Managed Translations (Notifications & Dashboard)

These systems handle content requiring specific per-kid customization or frontend-accessible strings.

- **Notification System**: Managed via `translations_custom/en_notifications.json` for chore, reward, and challenge updates.
- **Dashboard System**: Managed via `translations_custom/en_dashboard.json` for the Kid Dashboard UI.

### 2. Dashboard Translation Sensor Architecture

The dashboard translation system uses **system-level translation sensors** to efficiently serve localized UI strings to the dashboard frontend.

#### System-Level Translation Sensors

- **Entity Pattern**: `sensor.kc_ui_dashboard_lang_{code}` (e.g., `sensor.kc_ui_dashboard_lang_en`, `sensor.kc_ui_dashboard_lang_es`)
- **One Sensor Per Language**: Created dynamically based on languages used by kids and parents
- **Attributes**: Exposes `ui_translations` dict with 40+ localized UI strings, plus `language` and `purpose` metadata
- **Size**: Each translation sensor is ~5-6KB (well under HA's 16KB attribute limit)

#### Dashboard Helper Pointer Pattern

- **Dashboard Helper Attribute**: Each kid's `sensor.kc_<kid>_ui_dashboard_helper` includes a `translation_sensor` attribute
- **Indirection**: Dashboard helper returns a pointer (e.g., `"sensor.kc_ui_dashboard_lang_en"`) instead of embedding translations
- **Lookup Pattern**: Dashboard YAML fetches translations via `state_attr(translation_sensor, 'ui_translations')`
- **Size Benefit**: Reduces dashboard helper size by ~4.7KB (99% reduction in translation overhead)

#### Lifecycle Management

- **Dynamic Creation**: Translation sensors are created on-demand when a kid or parent selects a new language
- **Automatic Cleanup**: When the last user of a language is deleted, the corresponding translation sensor is removed
- **Coordinator Tracking**: `coordinator._translation_sensors_created` tracks which language sensors exist
- **Callback Pattern**: `sensor.py` registers `async_add_entities` callback for dynamic sensor creation

### 3. Crowdin Management Strategy

All translation files follow a unified, automated synchronization workflow.

- **Master English Files**: Only English master files are maintained and edited directly in the repository.
- **Automated Sync**: A GitHub Action triggers on pushes to the `l10n-staging` branch to upload English sources and download non-English translations from Crowdin.
- **Read-Only Localizations**: All non-English files are considered read-only artifacts sourced exclusively from the Crowdin project.

### 4. Language Selection Architecture

The architecture provides per-kid and per-parent dashboard language selection using standard Home Assistant infrastructure.

- **Dynamic Detection**: The system scans the `translations_custom/` directory, extracting language codes from filenames (e.g., `es_dashboard.json` → `es`).
- **Validation**: Detected codes are filtered against the Home Assistant `LANGUAGES` set to ensure they are valid.
- **Native UI Selection**: The `LanguageSelector` component is used with `native_name=True`, allowing the frontend to automatically display native language names like "Español".
- **Translation Sensor Loading**: When a language is selected, the system calls `coordinator.ensure_translation_sensor_exists()` to create the sensor if needed.
- **Fallback Handling**: Missing translation files fall back to English; missing keys show `err-*` prefixed strings for debugging.

---

## Dashboard Generation System

The Options Flow provides automated dashboard generation, creating fully-functional Lovelace dashboards with pre-configured views for kid management and parent administration.

### Architecture Components

**Dashboard Templates** (`templates/dashboard_*.yaml`):

- Pre-built Jinja2 templates with runtime (`{{ }}`) and build-time (`<< >>`) variables
- Three kid dashboard styles: Minimal (essentials), Compact (dense), Full (all features)
- One admin dashboard template with 7 management cards
- Templates use Mushroom Cards, Auto-Entities, and Mini Graph Card

**Generation Flow** (`options_flow.py` → `dashboard_helpers.py`):

- User selects a dashboard action (`create`, `update`, `delete`, `exit`) in a CRUD hub step
- Create and update use a shared sectioned configure step (kid views, admin views, access/sidebar, template version)
- Admin layout supports `none`, `global` (shared), `per_kid`, and `both`
- Update path applies changes in place to the selected dashboard URL path
- Build-time rendering: Python Jinja2 populates kid names/slugs with `<< >>` delimiters
- Runtime rendering: Home Assistant Jinja2 fetches live data with `{{ }}` delimiters
- Output: Lovelace storage dashboard config persisted through the dashboard builder helpers

**System Dashboard Selector** (`SystemDashboardAdminKidSelect`):

- System-level select entity for admin dashboard kid switching
- Provides `dashboard_helper_eid` attribute for efficient kid data access
- Eliminates hardcoded kid names and expensive `integration_entities()` queries
- Purpose-based filtering (`purpose_system_dashboard_admin_kid`) for entity ID stability

**Custom Card Detection** (`dashboard_helpers.check_custom_cards_installed()`):

- Validates Mushroom Cards, Auto-Entities, Mini Graph Card installation
- Accesses `hass.data["lovelace"].resources` for lovelace resource collection
- Warns users before generation if required frontend cards are missing
- Blocks dashboard creation when cards unavailable to prevent error-filled dashboards

---

## Config and Options Flow Architecture

The ChoreOps integration utilizes a **Direct-to-Storage** architecture that decouples user-defined entities from the Home Assistant configuration entry. This design allows for unlimited entity scaling and optimized system performance.

### Core Design Elements

- **Unified Logic via `flow_helpers.py`**: Both Config and Options flows leverage a shared utility layer to provide consistent validation and schema building. This centralization simplifies ongoing maintenance and ensures a uniform user experience across setup and configuration.
- **Single Source of Truth via `data_builders.py`**: All entity validation and building logic is centralized in `data_builders.py`, which serves **three entry points**: Config Flow, Options Flow, and Services. This architectural decision eliminates duplicate validation code and ensures consistent business rules across UI forms and programmatic CRUD operations.
- **CFOF Key Alignment (v0.5.0)**: Form field keys (`CFOF_*`) align with storage keys (`DATA_*`) where possible, allowing `user_input` to pass directly to `data_builders.build_*()` without mapping. Complex entities (chores, badges) still use transform functions.
- **Direct Storage Writing**: User input is written directly to persistent storage at `.storage/choreops/choreops_data` using **Schema 42**. This approach treats storage as the immediate source of truth, bypassing intermediate configuration entry merging.
- **Lightweight System Settings**: The `config_entry.options` object is reserved exclusively for system-level settings and feature flags, such as `points_label`, `update_interval`, and `kiosk_mode`. This keeps the core configuration entry lightweight and easy to validate.

### Operational Workflows

#### Config Flow (Initial Setup)

The configuration process follows a streamlined four-step path:

1. **Introduction**: A welcome screen providing integration context.
2. **System Settings**: Configuration of global labels, icons, and polling intervals.
3. **Entity Setup**: Direct creation of kids, parents, chores, badges, rewards, and other entities.
4. **Summary**: A final review before the storage data is committed and the entry is created.

#### Options Flow (Management)

The Options Flow manages modifications without unnecessary system overhead:

- **Entity Management**: Operations for adding, editing, or deleting entities are performed directly against storage data. The Coordinator handles persistence via `_persist()` and notifies active entities through `async_update_listeners()`, eliminating the need for a full integration reload.
- **System Settings Update**: When system settings or feature flags are modified, the flow updates the configuration entry via `self.hass.config_entries.async_update_entry()`. This action triggers a standard Home Assistant integration reload to apply global changes.

### Key Benefits

- **Scalability**: Eliminates the size constraints inherent in Home Assistant configuration entries, allowing for an unlimited number of kids and chores.
- **Efficiency**: Provides significantly faster integration reloads (approximately 8x faster) because the system only needs to process a handful of settings rather than the entire entity database.
- **Data Integrity**: Simplifies the codebase by removing complex merging and reconciliation logic, allowing the config flow to focus solely on clean data collection and storage.

---

## Backward Compatibility

The integration maintains backward compatibility for legacy installations:

- **Legacy Support**: Migration system handles v30, v31, v40beta1, v41 → v42 upgrades automatically
- **Dual Version Detection**: Code reads from both `meta.schema_version` (v42+) and top-level `schema_version` (legacy)
- **Safety Net**: If storage is corrupted or deleted, clean install creates v42 meta section
- **Migration Testing**: Comprehensive test suite validates all migration paths (see MIGRATION_TESTING_PLAN.md)
