# 📘 Development Standards & Coding Guidelines

**Purpose**: Prescriptive standards for how we code, organize, and maintain the KidsChores codebase.

**Audience**: All developers writing code for KidsChores.

**Contents**: Git workflows, naming conventions, coding patterns, entity standards, error handling.

**See Also**:

- [QUALITY_REFERENCE.md](QUALITY_REFERENCE.md) – How we measure and track quality compliance
- [CODE_REVIEW_GUIDE.md](CODE_REVIEW_GUIDE.md) – Code review process and Phase 0 audit framework
- [ARCHITECTURE.md](ARCHITECTURE.md) – Data model and integration architecture

---

## 🏛️ KidsChores Repository Standards

### 1. Git & Workflow Standards

To maintain a clean history and stable environment use a **Traffic Controller** workflow.

- **Branching Strategy**: Use feature branches for all development.
- **The L10n-Staging Bridge**: All feature branches must be merged into `l10n-staging` to trigger translation syncs. Note l10n is shorthand for localization / translations.
- **Sync Protocol**: Regularly merge `l10n-staging` back into your active feature branches to receive the latest translations from Crowdin.
- **Commit Style**: Use **Conventional Commits** (e.g., `feat:`, `fix:`, `refactor:`, `chore(l10n):`) to ensure a readable, professional history.

### 1.1 Development environment lock (VS Code)

To keep editor diagnostics stable across contributors, this repository uses a locked interpreter in workspace settings:

- **Locked interpreter**: `/home/vscode/.local/ha-venv/bin/python`
- **Type authority**: MyPy is authoritative; Pylance `typeCheckingMode` remains `off`
- **Noise prevention**: `.venv`, `venv`, and `.tox` paths are excluded/ignored in Pylance analysis

**Why this is required**:

- Prevents accidental local `.venv` creation from becoming the active interpreter
- Avoids large false-positive waves from analyzing vendored site-packages
- Keeps diagnostics aligned with CI validation gates (`ruff` + `mypy` + `pytest`)

**Temporary override policy**:

- Short-lived local overrides for debugging are allowed
- Before commits/PRs, restore the locked interpreter and workspace settings

### 1.2 Quality gate snapshot (concise)

- **Primary local gate**: `./utils/quick_lint.sh --fix` runs Ruff check/format, MyPy, and boundary checks in one pass.
- **Lint/format source**: Ruff config is centralized in `pyproject.toml` (Python 3.13 target, formatter + lint rules + per-file ignores).
- **Type source of truth**: MyPy is authoritative for CI and local validation; Pylance stays low-noise for editor productivity.
- **Architecture enforcement**: `utils/check_boundaries.py` is a required gate, not optional.
- **Test default behavior**: Pytest excludes `performance` and `stress` markers unless explicitly requested.
- **Definition of done**: Lint gate + zero MyPy errors + relevant pytest pass.

---

### 2. Localization & Translation Standards

We strictly separate English "source" files from "localized" output to avoid manual editing conflicts.

- **Master Files**: Only the English master files (`en.json`, `en_notifications.json`, `en_dashboard.json`) are edited in the repository.
- **Crowdin-Managed**: All non-English files are read-only and sourced exclusively via the Crowdin GitHub Action.
- **Standard Integration Translations** (`en.json`): Must strictly nest under Home Assistant-approved keys (e.g., `exceptions`, `issues`, `entity`) for core integration features.
- **Custom Translations** (`translations_custom/`): Flexible files (`en_notifications.json`, `en_dashboard.json`) for dashboards and notifications. These mimic the HA JSON structure but handle features not natively supported by Home Assistant.
- **Template Pattern**: Use the **Template Translation System** for errors to reduce redundant work.
- **Logic**: Use one template (e.g., `not_authorized_action`) and pass the specific action as a placeholder (e.g., `approve_chores`).

---

### 3. Constant Naming Standards

With over 1,000 constants, we follow strict naming patterns to ensure the code remains self-documenting.

#### Primary Prefix Patterns

| Prefix               | Plurality    | Usage                               | Example                           |
| -------------------- | ------------ | ----------------------------------- | --------------------------------- |
| `DATA_*`             | **Singular** | Storage keys for specific entities  | `DATA_KID_NAME`                   |
| `CFOF_*`             | **Plural**   | Config/Options flow input fields    | `CFOF_KIDS_INPUT_NAME`            |
| `CONF_*`             | **N/A**      | Config entry data access only       | `CONF_POINTS_LABEL`               |
| `CFOP_ERROR_*`       | **Singular** | Flow validation error keys          | `CFOP_ERROR_KID_NAME`             |
| `TRANS_KEY_*`        | **N/A**      | Stable identifiers for translations | `TRANS_KEY_CFOF_DUPLICATE_KID`    |
| `CONFIG_FLOW_STEP_*` | **Action**   | Config flow step identifiers        | `CONFIG_FLOW_STEP_COLLECT_CHORES` |
| `OPTIONS_FLOW_*`     | **Action**   | Options flow identifiers            | `OPTIONS_FLOW_STEP_EDIT_CHORE`    |
| `DEFAULT_*`          | **N/A**      | Default configuration values        | `DEFAULT_POINTS_LABEL`            |
| `LABEL_*`            | **N/A**      | Consistent UI text labels           | `LABEL_CHORE`                     |

#### Storage-Only Architecture (v0.5.0+ Data Schema v42+)

**Critical Distinction**: Since moving to storage-only mode, constants have specific usage contexts:

**`DATA_*`** = **Internal Storage Keys**

- **Usage**: Accessing/modifying `.storage/kidschores_data`
- **Context**: `coordinator._data[const.DATA_KIDS][kid_id][const.DATA_KID_NAME]`
- **Rule**: Always singular entity names (`DATA_KID_*`, `DATA_PARENT_*`)

**`CFOF_*`** = **Config/Options Flow Input Fields**

- **Usage**: Form field names in schema definitions during user input
- **Context**: `vol.Required(const.CFOF_KIDS_INPUT_NAME, ...)`
- **Rule**: Always plural entity names with `_INPUT_` (`CFOF_KIDS_INPUT_*`, `CFOF_PARENTS_INPUT_*`)
- **Key Alignment Pattern**: CFOF\** constant *values\* are aligned with DATA\*\_ values where possible (e.g., both use `"name"`). This allows `user_input` to be passed directly to `build\__()`functions without mapping. See`flow_helpers.py` module docstring for details.

**`CONF_*`** = **Configuration Entry Data Access**

- **Usage**: ONLY for accessing the 9 system settings in `config_entry.options`
- **Context**: `config_entry.options[const.CONF_POINTS_LABEL]`
- **Scope**: System-wide settings (points theme, update intervals, retention periods)
- **Rule**: Never use in flow schemas - those should use `CFOF_*`

**Common Anti-Pattern** ❌:

```python
# WRONG: Using CONF_ in flow schema
vol.Required(const.CONF_PARENT_NAME, default=name): str

# CORRECT: Use CFOF_ for flow input fields
vol.Required(const.CFOF_PARENTS_INPUT_NAME, default=name): str
```

#### Entity State & Actions

- **`ATTR_*`**: Entity state attributes. e.g., `ATTR_KID_NAME`, `ATTR_CHORE_POINTS`.
- **`SERVICE_*`**: Service action names. e.g., `SERVICE_CLAIM_CHORE`.
- **`SERVICE_FIELD_*`**: Service input field names. e.g., `SERVICE_FIELD_REWARD_NAME`.

#### Specialized Logic Patterns

- **`CHORE_STATE_*`**: Lifecycle states for chores (e.g., `CHORE_STATE_CLAIMED`, `CHORE_STATE_OVERDUE`).
- **`BADGE_*`**: Constants for badge logic, including `BADGE_TYPE_*`, `BADGE_STATE_*`, and `BADGE_RESET_SCHEDULE_*`.
- **`FREQUENCY_*`**: Recurrence options (e.g., `FREQUENCY_DAILY`, `FREQUENCY_CUSTOM`).
- **`PERIOD_*`**: Time period definitions (e.g., `PERIOD_DAY_END`, `PERIOD_ALL_TIME`).
- **`POINTS_SOURCE_*`**: Tracks point origins (e.g., `POINTS_SOURCE_CHORES`, `POINTS_SOURCE_BADGES`).
- **`ACTION_*`**: Notification action button titles.
- **`AWARD_ITEMS_*`**: Badge award composition (e.g., `AWARD_ITEMS_KEY_POINTS`).

#### Internal Scanner API Patterns

**`<ITEM_TYPE>_SCAN_<STRUCTURE>_<FIELD>`** = **Internal method signatures and return structures**

- **Pattern**: Item-type-scoped scanner constants for type-safe dictionary access
- **Usage**: Internal API contracts for scanner methods that categorize items by status
- **Context**:
  - `process_time_checks(trigger=const.CHORE_SCAN_TRIGGER_MIDNIGHT)`
  - `scan[const.CHORE_SCAN_RESULT_OVERDUE]`
  - `entry[const.CHORE_SCAN_ENTRY_KID_ID]`
- **Structure Types**:
  - `*_TRIGGER_*`: Scanner trigger parameter values (e.g., `CHORE_SCAN_TRIGGER_MIDNIGHT`)
  - `*_RESULT_*`: Scanner return dict category keys (e.g., `CHORE_SCAN_RESULT_OVERDUE`)
  - `*_ENTRY_*`: Scanner entry structure field keys (e.g., `CHORE_SCAN_ENTRY_KID_ID`)
- **Scalability**: Future item types follow same pattern:
  - Badges: `BADGE_SCAN_RESULT_*`, `BADGE_SCAN_ENTRY_*`
  - Rewards: `REWARD_SCAN_RESULT_*`, `REWARD_SCAN_ENTRY_*`
- **Rule**: Always use for dict access in type-unsafe contexts (vs TypedDict with literal keys)

#### Entity ID Generation (Dual-Variant System)

All entity platforms MUST provide both human-readable (`*_EID_*`) and machine-readable (`*_UID_*`) variants:

- **Sensors**: `SENSOR_KC_EID_*` / `SENSOR_KC_UID_*` (e.g., `kc_sarah_points` vs `kc_{uuid}_points`)
- **Buttons**: `BUTTON_KC_EID_*` / `BUTTON_KC_UID_*` (e.g., `kc_sarah_claim_chore` vs `kc_{uuid}_claim`)
- **Selects**: `SELECT_KC_EID_*` / `SELECT_KC_UID_*` (e.g., `kc_sarah_chore_list` vs `kc_{uuid}_chore_select`)
- **Calendars**: `CALENDAR_KC_*` (Standardized prefixes/suffixes)

#### Lifecycle Suffixes (Constant Management)

**`_DEPRECATED`** = **Active Production Code Pending Refactor**

- **Usage**: Constants actively used in production but planned for replacement in future versions
- **Code Impact**: Removing these WOULD break existing installations without migration
- **Organization**: Defined in dedicated section at bottom of `const.py`
- **Deletion**: Only after feature is refactored AND migration path implemented
- **Current Status**: None in use (all previous deprecations completed)

**`_LEGACY`** = **Migration Support Only**

- **Usage**: One-time data conversion during version upgrades (e.g., KC 3.x→4.x config migration)
- **Code Impact**: After migration completes, these keys NO LONGER EXIST in active storage
- **Organization**: Defined in dedicated section at bottom of `const.py` after `_DEPRECATED` section
- **Deletion**: Remove when migration support dropped (typically 2+ major versions, <1% users)

---

### 4. Data Write Standards (CRUD Ownership)

**Single Write Path**: All modifications to `coordinator._data` MUST happen inside a Manager method. Direct writes are **prohibited**.

#### The CRUD Contract

Every data modification must follow this atomic pattern:

```python
# Inside a Manager method only (e.g., managers/kid_manager.py)
async def update_kid_points(self, kid_id: str, points: int) -> None:
    """Update kid points - atomic operation."""
    # 1. Update memory
    self._data[const.DATA_KIDS][kid_id][const.DATA_KID_POINTS] = points

    # 2. Persist to storage AND update entity listeners
    self.coordinator._persist_and_update()

    # 3. Emit signal for listeners
    async_dispatcher_send(self.hass, SIGNAL_SUFFIX_KID_UPDATED)
```

**Two Persist Methods**:

| Method                                 | When to Use                                                                                                       | Entity Update?                            |
| -------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| `_persist_and_update(immediate=False)` | **Default** - All workflow operations that change user-visible state (claim, approve, timer-triggered, rotations) | ✅ YES - Calls `async_update_listeners()` |
| `_persist(immediate=False)`            | Internal bookkeeping only (notification metadata, system config cleanup, statistics flushes)                      | ❌ NO - Data not read by entities         |

````

#### Forbidden Patterns

**UI/Service Purity**: `options_flow.py` and `services.py` are **strictly forbidden** from:

- Calling `coordinator._persist()` directly
- Writing to `coordinator._data` directly
- Setting `updated_at` timestamps manually

**Correct Pattern**: Always delegate to Manager methods:

```python
# services.py - CORRECT
async def handle_claim_chore(call: ServiceCall) -> None:
    """Service handler delegates to manager."""
    chore_id = call.data[SERVICE_FIELD_CHORE_ID]
    await coordinator.chore_manager.claim_chore(chore_id)  # ✅ Manager handles everything
````

#### Automatic Metadata

All data builders (in `data_builders.py`) MUST set `updated_at` timestamps automatically:

```python
# data_builders.py
def build_kid_data(...) -> KidData:
    """Build kid data with automatic timestamp."""
    return {
        "name": name.strip(),
        "points": points,
        "updated_at": dt_now_iso(),  # ✅ Builder sets timestamp
        ...
    }
```

**Rule**: Managers never manually set `updated_at`—builders handle all metadata.

---

### 4b. Cross-Manager Communication Rules

| Rule                         | Description                                                                                                        |
| ---------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| **Reads OK**                 | Manager A can call Manager B's read methods (counts, names, statuses)                                              |
| **Writes FORBIDDEN**         | Manager A must emit a Signal; Manager B listens and handles its own write                                          |
| **Workflows = Event-Chains** | `CHORE_APPROVED` → Economy deposits → `POINTS_CHANGED` → Gamification checks → `BADGE_EARNED` → Notification sends |

```python
# ✅ CORRECT: Read data from another manager's domain via coordinator
period_start = self.coordinator.chore_manager.get_approval_period_start(kid_id, chore_id)
# NotificationManager queries ChoreManager data for Schedule-Lock comparison

# ✅ CORRECT: Emit signal with payload (for writes)
self.emit(SIGNAL_SUFFIX_BADGE_EARNED, kid_id=kid_id, bonus_ids=bonus_ids)
# EconomyManager._on_badge_earned() handles point deposit + bonus application

# ❌ WRONG: Direct cross-manager write
await self.coordinator.economy_manager.apply_bonus(kid_id, bonus_id)
```

---

### 4c. Landlord-Tenant Structure Ownership

**Pattern**: Manager that owns a data structure creates empty containers (Landlord), specialized managers populate data inside those containers (Tenant).

**Why This Matters**:

- **Prevents ownership conflicts**: Clear boundary between structure creation and data population
- **Enables clean separation**: Domain logic separated from specialized operations (statistics, caching, aggregations)
- **Simplifies testing**: Landlords test container creation, Tenants test data operations independently
- **Reduces coupling**: Tenants don't need to know about structure lifecycle, Landlords don't need statistical logic

**Ownership Hierarchy**:

```
KidManager (Landlord)
  └─ Creates: kid structure, top-level fields
      ├─ ChoreManager (Tenant → Landlord)
      │   └─ Creates: kid["chore_data"], kid["chore_periods"] (empty containers)
      │       └─ StatisticsManager (Tenant) populates: period buckets, date keys, counters
      ├─ RewardManager (Tenant → Landlord)
      │   └─ Creates: kid["reward_data"], kid["reward_periods"] (empty containers)
      │       └─ StatisticsManager (Tenant) populates: period buckets, date keys, counters
      └─ EconomyManager (Tenant → Landlord)
          └─ Creates: kid["point_stats"]["transaction_history"] (empty)
              └─ StatisticsManager (Tenant) populates: transaction records
```

**Example - Period Structures**:

```python
# ✅ Domain Manager (Landlord): Create empty container only
class RewardManager(BaseManager):
    def _ensure_kid_structures(self, kid_id: str, reward_id: str) -> None:
        """Create empty period container."""
        if const.DATA_KID_REWARD_PERIODS not in kid:
            kid[const.DATA_KID_REWARD_PERIODS] = {}  # Empty - Tenant populates

# ✅ StatisticsManager (Tenant): Populate data via signal listener
class StatisticsManager(BaseManager):
    async def _on_reward_approved(self, event: RewardApprovedEvent) -> None:
        """Record approval to period counters."""
        periods = kid[const.DATA_KID_REWARD_PERIODS]
        self.stats_engine.record_transaction(
            periods, {"approved": 1}, transaction_type="reward_approval"
        )

# ❌ WRONG: Domain manager directly populating data (Landlord acting as Tenant)
class RewardManager(BaseManager):
    def _increment_counter(self, reward_entry: dict) -> None:
        periods = reward_entry[const.DATA_KID_REWARD_DATA_PERIODS]
        self.coordinator.stats.record_transaction(periods, {"approved": 1})  # ❌ Violates boundary
```

---

### 5. Utils vs Helpers Boundary

**Rule of Purity**: Files in `utils/` and `engines/` are prohibited from importing `homeassistant.*`. They must be testable in a standard Python environment without HA fixtures.

| Component    | Location    | HA Imports?  | Purpose               | Example                                                     |
| ------------ | ----------- | ------------ | --------------------- | ----------------------------------------------------------- |
| **Utils**    | `utils/`    | ❌ Forbidden | Pure Python functions | `format_points()`, `validate_uuid()`                        |
| **Engines**  | `engines/`  | ❌ Forbidden | Pure business logic   | `RecurrenceEngine`, `ChoreStateEngine`                      |
| **Helpers**  | `helpers/`  | ✅ Required  | HA-specific tools     | `entity_helpers.py`, `auth_helpers.py`, `device_helpers.py` |
| **Managers** | `managers/` | ✅ Required  | Orchestration         | `ChoreManager`, `EconomyManager`, `NotificationManager`     |

**Why This Matters**:

- **Testability**: Utils/Engines run in pure pytest without mocking HA
- **Portability**: Logic can be extracted to standalone libraries
- **Performance**: Pure functions are faster to test and debug

**Example - WRONG**:

```python
# utils/point_utils.py
from homeassistant.core import HomeAssistant  # ❌ FORBIDDEN

def calculate_points(hass: HomeAssistant, chore_id: str) -> int:
    """Utils cannot depend on HA."""
    ...
```

**Example - CORRECT**:

```python
# utils/point_utils.py
def calculate_points(base_points: int, multiplier: float) -> int:  # ✅ Pure function
    """Calculate points with multiplier."""
    return round(base_points * multiplier)

# helpers/entity_helpers.py
from homeassistant.core import HomeAssistant

def get_chore_points(hass: HomeAssistant, chore_id: str) -> int:  # ✅ HA-aware helper
    """Fetch chore from registry and calculate points."""
    coordinator = hass.data[DOMAIN]
    chore = coordinator._data[DATA_CHORES][chore_id]
    return calculate_points(chore["base_points"], chore.get("multiplier", 1.0))
```

#### Data & Statistics Helpers

**Rule**: Helper functions that extract data like `_periods` structures MUST live in StatisticsManager, not domain managers or sensors.

**Rationale**: StatisticsManager is the "Accountant" - it owns all historical tallies and period data structures. Domain managers (the "Judges") own current state and rules, but delegate historical queries to Statistics.

---

### 6. DateTime & Scheduling Standards

#### Always Use dt\_\* Helper Functions

**Required**: All date/time operations MUST use the `dt_*` helper functions from `utils/dt_utils.py`. Direct use of Python's `datetime` module is forbidden.

**Why**: Ensures consistent timezone handling (UTC-aware, local-aware), DST safety, and testability across the codebase.

**Available DateTime Functions (dt\_\* prefix)**:

| Function                        | Purpose                                           |
| ------------------------------- | ------------------------------------------------- |
| `dt_today_local()`              | Today's date in local timezone                    |
| `dt_today_iso()`                | Today's date as ISO string                        |
| `dt_now_local()`                | Current time in local timezone                    |
| `dt_now_iso()`                  | Current time as ISO string                        |
| `dt_to_utc(dt)`                 | Convert to UTC-aware datetime                     |
| `dt_parse(value)`               | Parse ISO datetime string                         |
| `dt_add_interval(dt, interval)` | DST-safe interval arithmetic                      |
| `dt_next_schedule(config)`      | Calculate next recurrence (uses RecurrenceEngine) |
| `dt_parse_date(value)`          | Parse date string                                 |
| `dt_format_short(dt)`           | Format for display                                |
| `dt_format(dt, fmt)`            | Custom format                                     |

**Anti-Pattern** ❌:

```python
today = datetime.now().date()
next_time = datetime.now() + timedelta(days=1)
```

**Correct Pattern** ✅:

```python
from custom_components.choreops.utils.dt_utils import dt_today_local, dt_add_interval
today = dt_today_local()
next_time = dt_add_interval(dt_now_local(), {"interval": 1, "interval_unit": "day"})
```

#### UTC for Storage, Local for Keys (Period Statistics)

**Mandatory Pattern**: When generating period bucket keys (daily, weekly, monthly), ALWAYS convert UTC timestamps to local timezone dates.

**Rule**:

- Storage: Keep timestamps as UTC ISO strings (`DATA_KID_CHORE_DATA_LAST_COMPLETED`)
- Bucket Keys: Convert to local date before extracting key (`dt_parse(..., HELPER_RETURN_DATETIME_LOCAL)`)

**Implementation**:

```python
# ✅ CORRECT: Convert UTC → local → extract date
previous_completed = chore_data[DATA_KID_CHORE_DATA_LAST_COMPLETED]  # UTC timestamp
local_dt = dt_parse(previous_completed, return_type=HELPER_RETURN_DATETIME_LOCAL)
bucket_key = local_dt.date().isoformat()  # Local date string
period_data = daily_periods.get(bucket_key, {})

# ❌ WRONG: Using UTC date directly
utc_dt = dt_parse(previous_completed)  # Returns UTC datetime
bucket_key = utc_dt.date().isoformat()  # UTC date (WRONG!)
```

**Why**: Ensures user's calendar days match statistics. NY kid completing chore at 10 PM Monday shows "Monday" stats, not "Tuesday" (UTC would be 3 AM Tuesday).

**Affected Areas**: Streak calculations, period statistics queries, historical data lookups, aggregation logic.

#### RecurrenceEngine for Schedule Calculations

For chore/badge recurrence calculations, use `RecurrenceEngine` class instead of manual date arithmetic:

```python
from custom_components.choreops.engines.schedule import RecurrenceEngine
from custom_components.choreops.type_defs import ScheduleConfig

config: ScheduleConfig = {
    "frequency": "WEEKLY",
    "interval": 2,
    "interval_unit": "week",
    "base_date": "2026-01-19T00:00:00+00:00",
    "applicable_days": [0, 1, 2, 3, 4],
}
engine = RecurrenceEngine(config)
occurrences = engine.get_occurrences(start, end, limit=100)
rrule_str = engine.to_rrule_string()  # For iCal export
```

**Benefits**: Unified logic, RFC 5545 RRULE generation, edge case handling (monthly clamping, leap years, DST).

**Implementation Notes (Scheduling Cache Rules)**:

- Keep recurrence semantics in `RecurrenceEngine` unchanged; optimize call patterns around it (cache/reuse), not recurrence math itself.
- Any new schedule/calendar cache MUST have explicit signal-driven invalidation on relevant mutations (chore/challenge/kid updates and deletions).
- Calendar optimizations must preserve non-daily behavior: only DAILY and DAILY_MULTI use the 1/3 horizon cap.
- Tests asserting period buckets must use `StatisticsEngine.get_period_keys()` (local-period source of truth), not ad hoc UTC date strings.

---

### 5. Code Quality & Performance Standards

These standards ensure we maintain Platinum quality compliance. See [QUALITY_REFERENCE.md](QUALITY_REFERENCE.md) for compliance tracking and Home Assistant alignment.

- **No Hardcoded Strings**: All user-facing text (errors, logs, UI) **must** use constants and translation keys.
- **Lazy Logging**: Never use f-strings in logging. Use lazy formatting (`_LOGGER.info("Message: %s", variable)`) for performance.
- **Type Hinting**: 100% type hint coverage for all function arguments and return types.
  - **TypedDict for static structures**: Entity definitions, config objects with fixed schemas
  - **dict[str, Any] for dynamic structures**: Runtime-built aggregations, variable key access patterns
  - See Section 5.1 (Type System) below for details
- **Docstrings**: All public functions, methods, and classes MUST have docstrings.
  - Module docstrings: Describe purpose and list entity types/count by scope.
  - Class docstrings: Explain entity purpose and when it updates.
  - Method docstrings: Brief description of what it does (especially for complex logic).
- **Entity Lookup Pattern**: Always use the `get_*_id_or_raise()` helper functions in `helpers/entity_helpers.py` for service handlers to eliminate code duplication.
- **Coordinator Persistence**: All entity modifications must follow the **Modify → Persist (`_persist()`) → Notify (`async_update_listeners()`)** pattern.
- **Header Documentation**: Every entity file MUST include a header listing total count, categorized list (Kid-Specific vs System-Level), and legacy imports with clear numbering.
- **Test Coverage**: All new code must maintain 95%+ test coverage. See Section 7 for validation commands.
- **Entity Lifecycle**: Follow the cleanup architecture in Section 6 for proper entity removal and registry management.

#### 5.1 Type System

**File**: [type_defs.py](../custom_components/choreops/type_defs.py)

KidsChores uses a **hybrid typing strategy** that matches types to actual code patterns:

**Use TypedDict When**:

- ✅ Structure has fixed keys known at design time
- ✅ Keys are always accessed with literal strings
- ✅ IDE autocomplete and type safety are valuable

```python
class ChoreData(TypedDict):
    """Entity with fixed schema."""
    internal_id: str
    name: str
    state: str
    default_points: float
```

**Use dict[str, Any] When**:

- ✅ Keys are determined at runtime
- ✅ Code accesses structure with variable keys
- ✅ Structure is built dynamically from aggregations
- ✅ Enables smart, efficient code patterns that type checkers can't fully understand

```python
# ❌ WRONG: TypedDict with dynamic access
class StatsEntry(TypedDict):
    approved: int
    claimed: int

# Later in code:
field_name = "approved" if cond else "claimed"
stats[field_name] += 1  # ❌ mypy error: variable key not allowed

# ✅ CORRECT: dict[str, Any] for dynamic access
StatsEntry = dict[str, Any]
"""Aggregated stats with dynamic keys."""

# Later in code:
field_name = "approved" if cond else "claimed"
stats[field_name] += 1  # ✅ Works as intended
```

**Why This Matters**:

- Using TypedDict for dynamic structures requires 100+ `# type: ignore` suppressions
- Those suppressions disable type checking where it's most needed
- Being honest about structure type enables mypy to catch real bugs
- **Variable-based key access is idiomatic, efficient Python**—type checkers flag it because they can't infer runtime key values, not because the code is wrong
- Type suppressions are **IDE-level hints only**: they don't affect runtime performance or indicate code quality issues

**Acceptable Suppressions** (when TypedDict storage contracts differ from intermediate values):

```python
# Hybrid types: date objects converted to ISO strings before storage
progress.update({
    "maintenance_end_date": next_end  # next_end: str | date | None
})  # pyright: ignore[reportArgumentType]

# Dynamic field resets in loops
for field, default in reset_fields:
    progress[field] = default  # type: ignore[literal-required]
```

**Current Type Breakdown** (`type_defs.py`):

- **TypedDict**: 18 entity/config classes (ParentData, ChoreData, BadgeData, etc.)
- **dict[str, Any]**: 6 dynamic structures (KidChoreDataEntry, KidChoreStats, etc.)
- **Total**: 24 type definitions + 9 collection aliases

See [ARCHITECTURE.md](ARCHITECTURE.md#type-system-architecture) for architectural rationale.

#### 5.2 Data Entry Architecture

**Purpose**: Define how user input flows through validation layers into entity storage from **all three entry points**: Config Flow, Options Flow, and Services.

**Key Modules**:

- `flow_helpers.py` - UI layer (schema building, field validation for flows)
- `data_builders.py` - Core layer (entity validation, entity building - **shared by flows AND services**)

##### The 4-Layer Architecture

All entity types (kids, chores, rewards, badges, etc.) follow a consistent pattern across **three entry points**:

- **Config Flow**: Initial integration setup
- **Options Flow**: UI-based entity management
- **Services** (`services.py`): Programmatic CRUD operations via service calls

The same validation and building functions serve all three entry points, ensuring a true single source of truth:

**Layer 1: Schema Building** (`flow_helpers.py`)

- **Function**: `build_<entity>_schema()` → Returns `vol.Schema`
- **Purpose**: Construct voluptuous schemas for Home Assistant UI forms
- **Keys**: Uses `CFOF_*` constants (Config Flow / Options Flow form field names)
- **Example**: `build_chore_schema(default_values, kids_dict, coordinator)`

**Layer 2: Field-Level Validation** (`flow_helpers.py` + `services.py`)

- **Function**: `validate_<entity>_inputs()` → Returns `dict[str, str]` (errors)
- **Purpose**: Transform `CFOF_*` keys to `DATA_*` keys and delegate to core validation
- **Pattern**: Calls Layer 3 validation after key transformation
- **Field Validators**: Individual field validators (e.g., `validate_duration_string()`) used in `vol.All()` chains
- **Usage**: Options flows call `validate_<entity>_inputs()`; services call Layer 3 directly with `DATA_*` keys

**Layer 3: Entity-Level Validation** (`data_builders.py`)

- **Function**: `validate_<entity>_data()` → Returns `dict[str, str]` (errors)
- **Purpose**: **SINGLE SOURCE OF TRUTH** for business rule validation
- **Keys**: Uses `DATA_*` constants (storage format)
- **Rules**: Cross-field validation, uniqueness checks, business constraints
- **Consumers**: Config Flow, Options Flow, **AND Services** - all use the same validation

**Layer 4: Entity Building** (`data_builders.py`)

- **Function**: `build_<entity>()` → Returns complete entity dict
- **Purpose**: Build normalized entity with UUIDs, timestamps, defaults
- **Output**: Ready-to-store entity dict with all required fields
- **Consumers**: Config Flow, Options Flow, **AND Services** - all use the same builder

##### Two Types of Validators

**Field-Level Validators** (Layer 2 - `flow_helpers.py`):

- **Usage**: Individual field validation in `vol.All()` chains
- **Pattern**: `vol.All(cv.string, validate_duration_string)`
- **Returns**: Raise `vol.Invalid` on error (Voluptuous pattern)
- **Examples**: `validate_duration_string()`, `validate_time_format()`
- **Used In**: Service schemas (`services.py`), form schemas (`flow_helpers.py`)

**Entity-Level Validators** (Layer 3 - `data_builders.py`):

- **Usage**: Post-submission validation of complete entity data
- **Pattern**: Called by `validate_<entity>_inputs()` wrapper
- **Returns**: Error dict (`{"field_name": "translation_key"}`)
- **Examples**: `validate_chore_data()`, `validate_badge_data()`
- **Rules**: Uniqueness, cross-field validation, business logic

##### Standard Call Patterns

**From Options Flow** (Simple Entities - Aligned Keys):

```python
# Step 1: UI validation (transforms CFOF_* → DATA_* internally)
errors = flow_helpers.validate_reward_inputs(user_input, existing_rewards)

if not errors:
    # Step 2: Build entity directly from user_input (keys aligned!)
    reward = data_builders.build_reward(user_input)
    internal_id = reward[const.DATA_REWARD_INTERNAL_ID]

    # Step 3: Store
    coordinator._data[const.DATA_REWARDS][internal_id] = dict(reward)
    coordinator._persist()
    coordinator.async_update_listeners()
```

**From Services** (Direct to Core Layer):

```python
# Step 1: Validate with DATA_* keys (services receive DATA_* format)
errors = data_builders.validate_reward_data(service_data, existing_rewards)

if not errors:
    # Step 2: Build entity (same function as flows!)
    reward = data_builders.build_reward(service_data)
    internal_id = reward[const.DATA_REWARD_INTERNAL_ID]

    # Step 3: Store (same pattern as flows!)
    coordinator._data[const.DATA_REWARDS][internal_id] = dict(reward)
    coordinator._persist()
    coordinator.async_update_listeners()
```

**Complex Entities** (Require Mapping):

```python
# Step 1: UI validation
errors = flow_helpers.validate_chore_inputs(user_input, existing_chores, kids)

if not errors:
    # Step 2: Map complex fields (daily_multi_times string → list)
    data_input = data_builders.map_cfof_to_chore_data(user_input)

    # Step 3: Build entity
    chore = data_builders.build_chore(data_input)
    internal_id = chore[const.DATA_CHORE_INTERNAL_ID]

    # Step 4: Store
    coordinator._data[const.DATA_CHORES][internal_id] = dict(chore)
    coordinator._persist()
    coordinator.async_update_listeners()
```

##### Key Alignment (Phase 6)

Most `CFOF_*` constant **values** are now aligned with `DATA_*` values to eliminate mapping:

- `CFOF_KIDS_INPUT_NAME = "name"` matches `DATA_KID_NAME = "name"`
- `CFOF_REWARDS_INPUT_NAME = "name"` matches `DATA_REWARD_NAME = "name"`
- `CFOF_CHORES_INPUT_NAME = "name"` matches `DATA_CHORE_NAME = "name"`

**Entities with aligned keys** (pass `user_input` directly to `build_*()` after validation):

- Kids, Parents, Rewards, Bonuses, Penalties, Achievements, Challenges

**Entities requiring mapping** (complex transformations):

- **Chores**: `map_cfof_to_chore_data()` - Handles `daily_multi_times` string→list parsing
- **Badges**: Mapping embedded in `build_badge()` - Fields vary by `badge_type`

##### Benefits

1. **Single Source of Truth**: All validation logic in `data_builders` - **serves Config Flow, Options Flow, AND Services**
2. **DRY**: No duplicate validation across three entry points (flows + services)
3. **Testable**: Core validation isolated and unit testable
4. **Consistent**: Same pattern for all entity types across all entry points
5. **Type Safe**: Clear key transformation at well-defined boundaries
6. **Simplified**: Key alignment eliminates most mapping functions
7. **Service Integration**: Services use the same `validate_*_data()` and `build_*()` functions as flows - true code reuse

**Detailed Documentation**: See module docstrings in `flow_helpers.py` and `data_builders.py` for complete architecture details.

#### 5.3 Event Architecture (Manager Communication)

**Purpose**: Define how Managers communicate state changes via Home Assistant's Dispatcher system without tight coupling.

**Key Files**:

- `const.py` - Signal suffix constants (`SIGNAL_SUFFIX_*`)
- `helpers/entity_helpers.py` - `get_event_signal()` helper function
- `managers/base_manager.py` - `BaseManager` abstract class with emit/listen methods
- `type_defs.py` - Event payload TypedDicts (`*Event` types)

##### Signal Naming Convention

All signals use the **past-tense naming** pattern to indicate completed actions:

**Lifecycle Events (Boot Cascade)**:

| Category  | Signal Suffix                      | Emitter             | Description                      |
| --------- | ---------------------------------- | ------------------- | -------------------------------- |
| Lifecycle | `SIGNAL_SUFFIX_DATA_READY`         | SystemManager       | Data migrated, registry clean    |
| Lifecycle | `SIGNAL_SUFFIX_CHORES_READY`       | ChoreManager        | Chore initialization complete    |
| Lifecycle | `SIGNAL_SUFFIX_STATS_READY`        | StatisticsManager   | Stats hydration complete         |
| Lifecycle | `SIGNAL_SUFFIX_GAMIFICATION_READY` | GamificationManager | Gamification evaluation complete |
| Timer     | `SIGNAL_SUFFIX_PERIODIC_UPDATE`    | SystemManager       | 5-minute refresh pulse           |
| Timer     | `SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER`  | SystemManager       | Daily reset broadcast            |

**Boot Cascade Order**: `DATA_READY` → `CHORES_READY` → `STATS_READY` → `GAMIFICATION_READY`

**Domain Events**:

| Category     | Signal Suffix                        | Payload Type               |
| ------------ | ------------------------------------ | -------------------------- |
| Economy      | `SIGNAL_SUFFIX_POINTS_CHANGED`       | `PointsChangedEvent`       |
| Economy      | `SIGNAL_SUFFIX_TRANSACTION_FAILED`   | `TransactionFailedEvent`   |
| Chore        | `SIGNAL_SUFFIX_CHORE_CLAIMED`        | `ChoreClaimedEvent`        |
| Chore        | `SIGNAL_SUFFIX_CHORE_APPROVED`       | `ChoreApprovedEvent`       |
| Chore        | `SIGNAL_SUFFIX_CHORE_DISAPPROVED`    | `ChoreDisapprovedEvent`    |
| Reward       | `SIGNAL_SUFFIX_REWARD_APPROVED`      | `RewardApprovedEvent`      |
| Badge        | `SIGNAL_SUFFIX_BADGE_EARNED`         | `BadgeEarnedEvent`         |
| Gamification | `SIGNAL_SUFFIX_ACHIEVEMENT_UNLOCKED` | `AchievementUnlockedEvent` |
| CRUD         | `SIGNAL_SUFFIX_ENTITY_CREATED`       | `EntityCreatedEvent`       |

##### Multi-Instance Isolation

Every signal is scoped to a specific config entry using `get_event_signal()`:

```python
from custom_components.choreops import const
from custom_components.choreops.helpers import entity_helpers

# Build instance-scoped signal
signal = entity_helpers.get_event_signal(entry_id, const.SIGNAL_SUFFIX_POINTS_CHANGED)
# Result: "kidschores_{entry_id}_points_changed"

# Two instances never interfere:
# Instance A: "kidschores_abc123_points_changed"
# Instance B: "kidschores_xyz789_points_changed"
```

##### BaseManager Pattern

All Managers extend `BaseManager` which provides standardized emit/listen methods:

```python
from custom_components.choreops.managers import BaseManager
from custom_components.choreops import const

class NotificationManager(BaseManager):
    """Handles all notification dispatch."""

    async def async_setup(self) -> None:
        """Set up listeners for notification triggers."""
        # Listen for chore approvals to send congratulations
        self.listen(const.SIGNAL_SUFFIX_CHORE_APPROVED, self._on_chore_approved)

    async def _on_chore_approved(self, event: ChoreApprovedEvent) -> None:
        """Handle chore approval - send notification to kid."""
        await self.send_kid_notification(
            event["kid_id"],
            title_key="chore_approved_title",
            message_key="chore_approved_message",
        )
```

##### Async Listener Standards (Dispatcher Callbacks)

These rules apply to signal listener callbacks (`self.listen(...)`) and complement §5.4 method-level async guidance.

- State-modifying listeners must be `async def`.
- Read-only/log-only listeners may remain sync.
- Remove obsolete manual thread marshaling during async migration.
- Preserve signal payload keys/defaults while changing callback type.
- Keep migrations scoped to async/thread-safety behavior (no opportunistic feature refactors).

❌ **WRONG**: Sync listener manually scheduling async work

```python
def _on_badge_earned(self, payload: BadgeEarnedEvent) -> None:
    self.hass.loop.call_soon_threadsafe(
        self.hass.async_create_task,
        self._apply_award(payload),
    )
```

✅ **CORRECT**: Async listener with direct await

```python
async def _on_badge_earned(self, payload: BadgeEarnedEvent) -> None:
    await self._apply_award(payload)
```

**Validation for listener migrations**: `./utils/quick_lint.sh --fix`, `mypy custom_components/choreops/`, targeted workflow tests, and runtime log audit for thread-misuse warnings.

##### Event Payload TypedDicts

All event payloads are defined as TypedDicts in `type_defs.py` for type safety:

```python
class PointsChangedEvent(TypedDict):
    """Payload for points change events."""
    kid_id: str
    old_balance: float
    new_balance: float
    delta: float
    reason: str
    source: str  # POINTS_SOURCE_* constant
```

**Required Fields**: All events MUST include `kid_id` (or equivalent identifier) for routing.

##### Anti-Patterns

❌ **WRONG**: Direct method calls between managers

```python
# Tight coupling - don't do this
self.economy_manager.update_points(kid_id, points)
```

✅ **CORRECT**: Emit events, let managers listen

```python
# Loose coupling - managers react to events
self.emit(const.SIGNAL_SUFFIX_CHORE_APPROVED, {
    "kid_id": kid_id,
    "chore_id": chore_id,
    "points": points,
})
# EconomyManager listens and handles point update
# NotificationManager listens and sends congratulations
```

❌ **WRONG**: Direct manager calls from Coordinator

```python
# Coordinator should NOT have domain knowledge
async def _async_update_data(self):
    self.chore_manager.recalculate_stats()  # ❌ Don't call
    self.stats_manager.rebuild_cache()       # ❌ Don't call
```

✅ **CORRECT**: Coordinator emits, managers listen

```python
# Coordinator is pure infrastructure - just emit
async def _async_update_data(self):
    self.emit(const.SIGNAL_SUFFIX_PERIODIC_UPDATE)  # ✅ Managers subscribe
```

**Golden Rule: "Don't call, just listen."** The Coordinator emits lifecycle signals; managers subscribe and self-organize.

##### Persist → Emit Pattern (Non-Negotiable)

**Order MUST be: Persist → Emit.** Reversing creates "Ghost Fact" risk (listeners act on data that crashes before save).

```python
async def _approve_chore_locked(self, kid_id: str, chore_id: str, ...) -> None:
    # 1. Validate
    if not self._can_approve(kid_id, chore_id):
        raise ServiceValidationError(...)

    # 2. Transform in-memory state
    kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] = const.CHORE_STATE_APPROVED

    # 3. Commit (point of no return)
    self._coordinator._persist()

    # 4. Signal (safe - data is durable)
    self.emit(const.SIGNAL_SUFFIX_CHORE_APPROVED, kid_id=kid_id, ...)

    # 5. Refresh UI
    self._coordinator.async_update_listeners()
```

**Review Rule**: Reject PRs where `self.emit()` appears before `_persist()` for state-changing operations.

**Exception**: Non-data-changing signals (e.g., reminders) have nothing to persist.

#### 5.4 Async/Await Standards (Manager Methods)

**Purpose**: Define when methods must be `async def` vs `def` to ensure future-proofing and Home Assistant best practices.

##### Golden Rule

**Public Manager methods that mutate state must be `async def`.**

Even if a method only modifies in-memory dictionaries today, it should be async to support future database operations, API calls, or transaction logging without breaking callers.

##### Method Categories

| Category                   | Pattern     | Rationale                              |
| -------------------------- | ----------- | -------------------------------------- |
| **State-changing methods** | `async def` | May need I/O in future (database, API) |
| **Getter methods**         | `def`       | Pure in-memory lookups, no I/O needed  |
| **Engine methods**         | `def`       | Pure computation, stateless logic      |

##### Examples by Category

**State-Changing Methods** (MUST be `async def`):

```python
# ✅ Correct: State changes use async
async def reset_chore(self, kid_id: str, chore_id: str) -> None:
    """Reset chore state to pending."""
    kid_chore_data[const.DATA_KID_CHORE_DATA_STATE] = const.CHORE_STATE_PENDING
    self._coordinator._persist()

async def deposit(self, kid_id: str, amount: float, reason: str) -> None:
    """Add points to kid's balance."""
    kid_info[const.DATA_KID_POINTS] += amount
    self._coordinator._persist()
```

**Getter Methods** (can be `def`):

```python
# ✅ Correct: Pure lookups stay sync
def get_chore_state(self, kid_id: str, chore_id: str) -> str:
    """Return current chore state."""
    return kid_chore_data.get(const.DATA_KID_CHORE_DATA_STATE, const.CHORE_STATE_PENDING)

def chore_is_overdue(self, kid_id: str, chore_id: str) -> bool:
    """Check if chore is overdue."""
    return state == const.CHORE_STATE_OVERDUE
```

**Engine Methods** (MUST be `def`):

```python
# ✅ Correct: Pure computation, no state
def calculate_next_due_date(self, config: ScheduleConfig) -> datetime:
    """Calculate next occurrence from schedule config."""
    return RecurrenceEngine(config).get_next_occurrence()
```

##### Caller Requirements

All callers **MUST** await async methods:

```python
# ✅ Correct
await coordinator.chore_manager.reset_chore(kid_id, chore_id)
await coordinator.economy_manager.deposit(kid_id, points, reason)

# ❌ Wrong - missing await causes RuntimeWarning
coordinator.chore_manager.reset_chore(kid_id, chore_id)  # Coroutine never awaited!
```

##### Why This Matters

1. **Future-proofing**: Today's `dict.pop()` might become `await db.delete()` in v1.0
2. **Consistency**: Callers don't need to know implementation details
3. **Home Assistant alignment**: HA best practices require async for all I/O operations
4. **Test safety**: Async tests catch missing awaits via RuntimeWarnings

---

### 6. Entity Standards

We enforce strict naming patterns for both **Entity IDs** (runtime identifiers) and **Class Names** (codebase structure) to ensure persistence, readability, and immediate scope identification.

#### Entity ID Construction (Dual-Variant System)

Entities must support two identifiers to balance human readability with registry persistence:

1.  **UNIQUE_ID** (`unique_id`): Internal, stable registry identifier.
    - **Format**: `{entry_id}[_{kid_id}][_{item_id}]{_SUFFIX}` (e.g., `abc123_kid456_chore789_kid_chore_claim_button`)
    - **SUFFIX Pattern**: Class name lowercased with underscores (e.g., `_kid_points_sensor`, `_parent_chore_approve_button`)
    - **Why Required**: Ensures history and settings persist even if users rename kids or chores.
    - ⚠️ **NEVER use MIDFIX or PREFIX patterns in UIDs** – suffix-only ensures consistent registry lookups
2.  **ENTITY_ID** (`entity_id`): User-visible UI identifier.
    - **Format**: `domain.kc_[name][_MIDFIX_][name2][_SUFFIX]` (e.g., `sensor.kc_sarah_points`)
    - **Why Required**: Provides descriptive, readable IDs for automations and dashboards.
    - MIDFIX patterns are acceptable in EIDs for readability (e.g., `_chore_claim_`)

**Pattern Components**:

- **SUFFIX** (`_kid_points_sensor`): Appended to end. **Required for UID**, optional for EID. Class-aligned naming.
- **MIDFIX** (`_chore_claim_`): Embedded between names. **EID only** – provides semantic clarity in multi-part entities.

#### Entity Class Naming

All classes must follow the `[Scope][Entity][Property]EntityType` pattern (e.g., `KidPointsSensor`, `ParentChoreApproveButton`).

**1. Scope (Required)**
Indicates data ownership and initiation source. **Rule**: No blank scopes allowed.

- **`Kid`**: Per-kid data/actions initiated by the kid (e.g., `KidChoreClaimButton`).
- **`Parent`**: Per-kid actions initiated by a parent (e.g., `ParentChoreApproveButton`).
- **`System`**: Global aggregates shared across all kids (e.g., `SystemChoresPendingApprovalSensor`).

**2. Entity & Property**

- **Entity**: The subject (`Chore`, `Badge`, `Points`). Use **Plural** for collections (`SystemChores...`), **Singular** for items (`KidChore...`).
- **Property**: The aspect (`Status`, `Approvals`, `Claim`). **Rule**: Property must follow Entity (`KidBadgeHighest`, never `KidHighestBadge`).

**3. Platform Consistency**
This pattern applies to **all** platforms.

- **Sensor**: `KidPointsSensor` (State: Balance)
- **Button**: `KidChoreClaimButton` (Action: Claim)
- **Select**: `SystemRewardsSelect` (List: All Shared Rewards)
- **Calendar**: `KidScheduleCalendar` (View: Kid's timeline)

#### Feature Flag Implementation Checklist

When adding new feature flags that control entity creation:

1. **Define Constants** (const.py):
   - [ ] Add `CONF_*` constant for the option key
   - [ ] Add `DEFAULT_*` constant for default value
   - [ ] Add to `DEFAULT_OPTIONS` dictionary

2. **Update Entity Logic** (coordinator.py + platform files):
   - [ ] Add flag check in `should_create_entity()` method
   - [ ] Add flag check in platform's `async_setup_entry()` or entity `__init__`
   - [ ] Verify cleanup in `remove_conditional_entities()` handles the flag

3. **Update Config Flow** (options_flow.py):
   - [ ] Add form field in `async_step_system_settings()` using `CFOF_*` constant
   - [ ] Add user input handling with proper validation

4. **Add Translations** (translations/en.json):
   - [ ] Add option title and description under `config.step.system_settings.data`
   - [ ] Add any new error messages under `config.error`

5. **Update Cleanup** (See Entity Cleanup Architecture above):
   - [ ] Verify flag-driven cleanup works in BOTH reload paths:
     - Path 1: System settings → `async_update_options()` (\_\_init\_\_.py)
     - Path 2: Entity changes → `_reload_entry_after_entity_change()` (options_flow.py)
   - [ ] Test flag toggle: on → off → on (entities removed/recreated)

6. **Add Tests**:
   - [ ] Test entity creation when flag enabled
   - [ ] Test entity removal when flag disabled
   - [ ] Test toggle cycle doesn't leave orphaned entities
   - [ ] Test both reload paths trigger cleanup correctly

7. **Documentation**:
   - [ ] Update Section 6 (Entity Cleanup Architecture) if new cleanup pattern introduced
   - [ ] Update wiki documentation for user-facing feature

**Common Pitfall**: Adding cleanup to only ONE reload path. Always update BOTH paths to stay synchronized.

#### Entity Cleanup Architecture

KidsChores uses a **dual-path reload system** where both paths must run synchronized cleanup to prevent orphaned entities.

**The Two Reload Paths:**

1. **System Settings Path** (`__init__.py: async_update_options`)
   - **Trigger**: User changes points theme, update intervals, retention settings
   - **Flow**: `async_update_entry()` → Update listener fires → Cleanup → Reload
   - **Cleanup**: Flag-driven + Validation safety net
   - **Use**: `_update_system_settings_and_reload()` method

2. **Entity Changes Path** (`options_flow.py: _reload_entry_after_entity_change`)
   - **Trigger**: User adds/edits/deletes kids, chores, badges, parents
   - **Flow**: `_mark_reload_needed()` flag → User returns to menu → Cleanup → `async_reload()` directly
   - **Cleanup**: Flag-driven + Data-driven orphaned entities
   - **Use**: Call `self._mark_reload_needed()` in entity edit handlers
   - **Why Direct Reload?** Bypasses update listener to avoid interrupting multi-step flows
   - **Pattern**: Always call after persisting entity changes:
     ```python
     # In your async_step_edit_* handler:
     coordinator._data[const.DATA_CHORES][chore_id] = updated_chore
     coordinator._persist()
     coordinator.async_update_listeners()
     self._mark_reload_needed()  # ← Triggers cleanup on menu return
     return await self.async_step_init()  # Return to menu
     ```

**The Three Cleanup Types:**

1. **FLAG-DRIVEN** (`remove_conditional_entities()`)
   - Removes entities disabled by feature flags (show_legacy_entities, enable_chore_workflow, enable_gamification)
   - Runs in BOTH paths (system settings + entity changes)

2. **DATA-DRIVEN** (`_remove_orphaned_kid_chore_entities()`, `_remove_orphaned_badge_entities()`)
   - Removes entities with broken relationships (kid unassigned from chore/badge)
   - Only kid-chore and kid-badge create per-relationship entities requiring registry cleanup
   - Runs ONLY in entity changes path (system settings don't affect data relationships)

3. **VALIDATION** (`remove_all_orphaned_entities()`)
   - Safety net at startup and system settings changes
   - Catches any entities that slipped through other cleanup

**Critical Rule**: Update listener and deferred reload must call the same flag-driven cleanup. Missing cleanup in either path causes entities to remain after flag toggles.

---

### 7. Error Handling Standards

We strictly enforce Home Assistant's exception handling patterns to ensure errors are translatable, actionable, and properly categorized.

- **Translation Keys Required**: All exceptions MUST use `translation_key` and `translation_placeholders`. **Never** raise exceptions with hardcoded strings.
- **Specific Exception Types**:
  - `ServiceValidationError`: For invalid user input (e.g., entity not found, invalid date).
  - `HomeAssistantError`: For system/runtime failures (e.g., API error, calculation failure).
  - `UpdateFailed`: Exclusive to Coordinator update failures.
  - `ConfigEntryAuthFailed`: For authentication expiration/invalid credentials.
- **Exception Chaining**: Always use `from err` when re-raising to preserve stack traces.
- **Input Validation**: Validate inputs _before_ processing action logic. Use `get_*_or_raise` helpers.

#### Correct Pattern (Gold Standard)

```python
try:
    kid_id = kh.get_kid_id_or_raise(coordinator, kid_name, "Approve Chore")
except ValueError as err:
    # ✅ Specific exception, translation key, and chaining
    raise ServiceValidationError(
        translation_domain=const.DOMAIN,
        translation_key=const.TRANS_KEY_ERROR_INVALID_INPUT,
        translation_placeholders={"details": str(err)}
    ) from err
```

#### Wrong Pattern (Do Not Use)

```python
# ❌ Hardcoded string, undefined exception type, no chaining
if not kid_id:
    raise Exception(f"Kid {kid_name} not found!")
```

---

### 8. Development Workflow & Quality Validation

Before committing code changes, validate they meet quality standards using these mandatory commands:

#### Linting Check (9.5+/10 Required)

```bash
./utils/quick_lint.sh --fix  # Auto-fix formatting, verify no critical errors
```

- Catches unused imports, format violations, and code quality issues
- Must pass before marking work complete

#### Type Checking (100% Coverage) - ENFORCED IN CI/CD

MyPy type checking is now **mandatory** and runs automatically in `quick_lint.sh`.

```bash
mypy custom_components/choreops/  # Verify all type hints are correct
```

**Current Strictness**: Platinum-level compliance (as of January 2026)

- `strict_optional = true` - No implicit None types
- `check_untyped_defs = true` - All function signatures must be typed
- `python_version = 3.12` - Modern Python syntax required

**Requirements**:

- All functions MUST have complete type hints (args + return)
- Zero mypy errors required for code to pass CI/CD
- Use Python 3.10+ syntax (`str | None` not `Optional[str]`)
- Use modern collections (`dict[str, Any]` not `Dict[str, Any]`)

**Common Type Fixes**:

- Import from `collections.abc`: Use `Callable`, `Mapping`, `Sequence`
- Use `from __future__ import annotations` for forward references
- Replace `Optional[X]` with `X | None`
- Use `Any` sparingly (only when truly dynamic)

**Configuration**: See `pyproject.toml` for complete MyPy settings

#### Full Test Suite (All Tests Must Pass)

```bash
python -m pytest tests/ -v --tb=line  # Run complete test suite
```

- Validates all business logic, platforms, and integrations
- Detects regressions in existing features
- Must pass before work is considered complete

#### Comprehensive Validation (Do Not Skip)

**Work is NOT complete until ALL THREE pass**:

1. Linting passes (`./utils/quick_lint.sh --fix`)
2. Tests pass (`python -m pytest tests/ -v --tb=line`)
3. All errors fixed (lint errors, test failures)

**For Detailed Guidance**:

- **Test Validation & Debugging**: See [AGENT_TESTING_USAGE_GUIDE.md](../tests/AGENT_TESTING_USAGE_GUIDE.md)
  - Which tests to run for specific changes
  - Debugging failing tests
  - Module-level suppressions for test files

- **Creating New Tests**: See [AGENT_TEST_CREATION_INSTRUCTIONS.md](../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
  - Only needed for genuinely new functionality
  - Modern testing patterns and fixtures
  - Scenario-based test setup

### 9. Lexicon Standards (Non-Negotiable)

To prevent confusion between Home Assistant's registry and our internal data:

| Term                  | Usage                                     | Example                                |
| --------------------- | ----------------------------------------- | -------------------------------------- |
| **Item** / **Record** | A data entry in our JSON storage          | "A Chore Item", "Kid Record"           |
| **Domain Item**       | Collective term for all stored data types | Kids, Chores, Badges (as JSON records) |
| **Internal ID**       | The UUID for a record                     | `kid_id`, `chore_id`                   |
| **Entity**            | ONLY a Home Assistant object              | Sensor, Button, Select                 |
| **Entity ID**         | The HA string                             | `sensor.kc_alice_points`               |

**Critical Rule**: Never use "Entity" when referring to a Chore, Kid, Badge, etc. These are **Items** in storage, not HA registry objects.

---
