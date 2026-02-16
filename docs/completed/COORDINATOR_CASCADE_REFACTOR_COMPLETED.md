# Event-Driven Manager Cascade Refactor

## Initiative snapshot

- **Name / Code**: Coordinator Cascade Refactor (COORD-CASCADE)
- **Target release / milestone**: v0.5.0 (beta3 stabilization)
- **Owner / driver(s)**: KidsChores Development Team
- **Status**: ✅ COMPLETE

## Summary & immediate steps

| Phase / Step             | Description                                          | % complete | Quick notes                                    |
| ------------------------ | ---------------------------------------------------- | ---------- | ---------------------------------------------- |
| Phase 1 – Foundation     | Add lifecycle signals to const.py                    | 100%       | ✅ 6 signals added, cascade documented         |
| Phase 1.5 – Segmentation | Analyze pre-v50 vs ongoing governance code           | 100%       | Clear boundaries for droppable module          |
| Phase 2 – Baton Start    | Coordinator → `await ensure_data_integrity()` → emit | 100%       | ✅ BLOCKING call, migrations in PreV50Migrator |
| Phase 2.5 – Timer Owner  | SystemManager owns all `async_track_time_change`     | 100%       | ✅ 3 timers → 1 signal (MIDNIGHT_ROLLOVER)     |
| Phase 3 – Periodic       | Convert `_async_update_data` to emit-only            | 100%       | ✅ Single PERIODIC_UPDATE signal               |
| Phase 4 – Managers       | Wire managers to listen for lifecycle signals        | 100%       | ✅ DATA_READY cascade wired                    |
| Phase 5 – Validation     | Full test suite, verify cascade ordering             | 100%       | ✅ 1148 passed, cascade test added, docs done  |

1. **Key objective** – Transform coordinator from "orchestrator with domain knowledge" to "dumb infrastructure hub" that only loads data, runs migrations, and emits lifecycle signals. Managers self-organize via signal cascade.

2. **Summary of recent work**
   - Signal-first architecture already implemented for point transactions (EconomyManager listens to CHORE_APPROVED, REWARD_APPROVED)
   - UI flags moved to UIManager with signal listeners
   - Manager injection simplified (no economy_manager passed to ChoreManager/RewardManager)
   - **Phase 1.5**: Migration segmentation analysis complete - clear separation of pre-v50 migration code (droppable) vs ongoing governance (SystemManager)

3. **Next steps (short term)**
   - Add lifecycle signals: `DATA_READY`, `CHORES_READY`, `STATS_READY`, `GAMIFICATION_READY`, `PERIODIC_UPDATE`, `MIDNIGHT_ROLLOVER`
   - Implement `await system_manager.ensure_data_integrity()` (BLOCKING call from Coordinator)
   - Move ALL migration-specific logic to `migration_pre_v50.py` (schema upgrades, meta setup, legacy key cleanup)
   - Move ALL ongoing governance logic to SystemManager (`_ensure_meta_fields()`, safety net)
   - Move ALL timer registrations to SystemManager

4. **Risks / blockers**
   - Signal ordering must be guaranteed (cascade must complete before entities request data)
   - `ensure_data_integrity()` must complete BEFORE `_persist()` is called
   - Test fixtures may need adjustment for new boot sequence

5. **References**
   - [ARCHITECTURE.md](../ARCHITECTURE.md) – Signal-based architecture patterns
   - [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) § 5.3 – Event Architecture

6. **Decisions & completion check**
   - **Decisions captured**:
     - [x] Signal naming: `SIGNAL_SUFFIX_*_READY` for lifecycle, domain-specific for events
     - [x] Cascade order: **DATA_READY → CHORES_READY → STATS_READY → GAMIFICATION_READY** (simplified, no SYSTEM_READY)
     - [x] Timer ownership: **SystemManager owns ALL `async_track_time_change` calls**
     - [x] Periodic: Single PERIODIC_UPDATE signal, managers subscribe as needed
     - [x] Boot pattern: **"Baton Start"** - Coordinator calls `await ensure_data_integrity()` (BLOCKING), SystemManager emits DATA_READY
     - [x] Migration ownership: **Pre-v50 logic in `migration_pre_v50.py` (droppable), ongoing governance in SystemManager**
   - **Completion confirmation**: `[x]` All follow-up items completed (architecture updates, cleanup, documentation, etc.)

---

## Architecture Overview

### Current State (Direct Coupling)

```
┌─────────────────────────────────────────────────────────────────────┐
│                         Coordinator                                  │
│  async_config_entry_first_refresh():                                │
│    1. Load storage                                                  │
│    2. Run migrations                                                │
│    3. gamification_manager.update_chore_badge_references()  ← CALL  │
│    4. for kid: chore_manager.recalculate_stats()           ← CALL  │
│    5. for kid: stats.generate_point_stats()                ← CALL  │
│    6. Register time-based callbacks                                 │
│    7. _persist()                                                    │
└─────────────────────────────────────────────────────────────────────┘
```

**Problems:**

- Coordinator has domain knowledge (knows chores need stats, badges need references)
- Adding new manager requires modifying coordinator
- Circular dependency risk if manager order changes
- Hard to test managers in isolation

### Target State (Event-Driven Cascade with Registry Guard)

```
┌─────────────────────────────────────────────────────────────────────┐
│              Coordinator (Pure Infrastructure Skeleton)              │
│  async_config_entry_first_refresh():                                │
│    1. Load storage (_data holder)                                   │
│    2. Run migrations                                                │
│    3. emit(DATA_READY)  ← Single signal, zero domain knowledge     │
│    4. _persist()                                                    │
│                                                                     │
│  Owns ONLY: _data, _persist(), store wrapper                        │
│  Owns NO: timers, domain logic, manager orchestration              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ DATA_READY
┌─────────────────────────────────────────────────────────────────────┐
│                  SystemManager (The Registry Guard)                  │
│  _on_data_ready():                                                  │
│    - Run startup safety net (orphan removal, registry sync)         │
│    - Validate HA Entity Registry matches Storage Data              │
│    - emit(SYSTEM_READY)                                            │
│                                                                     │
│  async_setup():                                                     │
│    - Register MIDNIGHT_ROLLOVER timer (single timer for all)       │
│    - (Optional) Register PERIODIC_UPDATE timer                      │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ SYSTEM_READY
┌─────────────────────────────────────────────────────────────────────┐
│                    ChoreManager (The Taskmaster)                     │
│  _on_system_ready():                                                │
│    - Process scheduled resets                                       │
│    - Recalculate chore stats for all kids                          │
│    - emit(CHORES_READY)                                            │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ CHORES_READY
┌─────────────────────────────────────────────────────────────────────┐
│                 StatisticsManager (The Accountant)                   │
│  _on_chores_ready():                                                │
│    - Hydrate presentation cache (PRES_* keys)                       │
│    - Generate point stats for all kids                              │
│    - emit(STATS_READY)                                              │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ STATS_READY
┌─────────────────────────────────────────────────────────────────────┐
│               GamificationManager (The Game Master)                  │
│  _on_stats_ready():                                                 │
│    - Update chore badge references                                  │
│    - Evaluate badges/achievements/challenges                        │
│    - emit(GAMIFICATION_READY)                                       │
└─────────────────────────────────────────────────────────────────────┘
                                    │
                                    ▼ GAMIFICATION_READY
┌─────────────────────────────────────────────────────────────────────┐
│                   UIManager (The Interior Decorator)                 │
│  _on_gamification_ready():                                          │
│    - Build dashboard helper data                                    │
│    - System ready for entity state requests                         │
│    - Log "KidsChores initialization cascade complete"              │
└─────────────────────────────────────────────────────────────────────┘
```

**Why SystemManager First?**

- Ensures Entity Registry is clean before domain managers try to update sensors
- Prevents ChoreManager from updating sensors that are about to be deleted as orphans
- Single point of failure isolation: if registry cleanup crashes, Coordinator skeleton survives
  │ - Generate point stats for all kids │
  │ - emit(STATS_READY) │
  └─────────────────────────────────────────────────────────────────────┘
  │
  ▼ STATS_READY
  ┌─────────────────────────────────────────────────────────────────────┐
  │ GamificationManager │
  │ \_on_stats_ready(): │
  │ - Update chore badge references │
  │ - Evaluate badges/achievements/challenges │
  │ - emit(GAMIFICATION_READY) │
  └─────────────────────────────────────────────────────────────────────┘
  │
  ▼ GAMIFICATION_READY
  ┌─────────────────────────────────────────────────────────────────────┐
  │ UIManager │
  │ \_on_gamification_ready(): │
  │ - Build dashboard helper data │
  │ - System ready for entity state requests │
  └─────────────────────────────────────────────────────────────────────┘

````

---

## Detailed phase tracking

### Phase 1 – Foundation (Signals & Constants)

- **Goal**: Add lifecycle signal constants and establish naming convention.

- **Steps / detailed work items**
  1. - [x] Add lifecycle signals to `const.py` (~line 120, after existing signals):
     ```python
     # Lifecycle Events (SystemManager → Domain Managers)
     SIGNAL_SUFFIX_DATA_READY: Final = "data_ready"           # Data migrated, registry clean
     SIGNAL_SUFFIX_CHORES_READY: Final = "chores_ready"       # ChoreManager initialization complete
     SIGNAL_SUFFIX_STATS_READY: Final = "stats_ready"         # StatisticsManager hydration complete
     SIGNAL_SUFFIX_GAMIFICATION_READY: Final = "gamification_ready"  # GamificationManager complete

     # Timer-Triggered Events (SystemManager owns timers)
     SIGNAL_SUFFIX_PERIODIC_UPDATE: Final = "periodic_update" # 5-minute refresh pulse
     SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER: Final = "midnight_rollover"  # Daily reset broadcast
     ```
  2. - [x] Document cascade order in `const.py` comment block:
     ```python
     # Boot Cascade: ensure_data_integrity() → DATA_READY → CHORES_READY → STATS_READY → GAMIFICATION_READY
     ```
  3. - [x] Add to `DEVELOPMENT_STANDARDS.md` § 5.3 signal table

- **Key issues**
  - None encountered

### Phase 1.5 – Migration Segmentation Analysis (Pre-v50 vs Ongoing Governance)

- **Goal**: Clearly identify what code is pre-v50 migration (belongs in `migration_pre_v50.py`) vs. ongoing system governance (belongs in `SystemManager`).

- **Context**: The `migration_pre_v50.py` module is designed to be **droppable** once most users have upgraded past v0.5.0. We must ensure NO ongoing governance logic is mixed in with one-time migrations.

- **Segmentation Analysis (coordinator.py lines 195-330)**

  | Code Block | Description | Classification | Destination |
  |------------|-------------|----------------|-------------|
  | Lines 207-220 | Schema version check + `_run_pre_v50_migrations()` call | **Pre-v50 Migration** | `migration_pre_v50.py` (orchestrator) |
  | Lines 222-248 | Meta section creation after migration | **Pre-v50 Migration** | `migration_pre_v50.py` (part of migrator) |
  | Lines 251-252 | Remove old top-level `schema_version` key | **Pre-v50 Migration** | `migration_pre_v50.py` |
  | Lines 260-264 | Ensure `pending_evaluations` exists in meta | **Ongoing Governance** | `SystemManager._ensure_meta_fields()` |
  | Lines 267-273 | Clean up legacy keys (`migration_performed`, `migration_key_version`) | **Pre-v50 Migration** | `migration_pre_v50.py` (or droppable) |
  | Lines 285-302 | Initialize empty data structure | **Ongoing Governance** | `Coordinator._get_default_structure()` |
  | Lines 306-321 | Timer registrations | **Ongoing Governance** | `SystemManager.async_setup()` |
  | Lines 323-327 | Badge reference init + chore/point stats | **Ongoing Governance** | Domain managers (via cascade) |

- **Guiding Principle**: Ask "Would this code run for a **fresh v0.5.0+ installation**?"
  - **YES** → Ongoing Governance (stays in SystemManager or domain managers)
  - **NO** → Pre-v50 Migration (move to `migration_pre_v50.py`, eventually droppable)

- **Classification Rules**

  | Category | Examples | Location |
  |----------|----------|----------|
  | **Pre-v50 Migration** | Schema transformations, field renames, data restructuring, legacy key cleanup | `migration_pre_v50.py` |
  | **Ongoing Data Governance** | Ensure required fields exist, validate structure, safety net cleanup | `SystemManager` |
  | **Infrastructure** | Load from disk, hold `_data` pointer, `_persist()` | `Coordinator` |
  | **Domain Logic** | Stats calculation, badge evaluation, chore resets | Domain Managers (via signals) |

- **migration_pre_v50.py Structure After Refactor**
````

migration_pre_v50.py
├── migrate_config_to_storage() # Runs BEFORE coordinator init (KC 3.x → 4.x)
│
└── PreV50Migrator # Runs AFTER coordinator loads data
├── run_all_migrations() # Orchestrates all below
├── \_migrate_datetime() # Schema: datetime format changes
├── \_migrate_chore_data() # Schema: chore structure changes
├── \_migrate_badges() # Schema: badge structure changes
├── ... (20+ migration methods) # Schema: various field migrations
├── \_remove_legacy_keys() # Cleanup: beta garbage keys ← MOVED HERE
└── \_update_meta_section() # Sets schema_version=50, migration date ← MOVED HERE

```

- **SystemManager Responsibilities (After Migration Module Cleanup)**
```

SystemManager
├── ensure_data_integrity() # BLOCKING call from Coordinator
│ ├── if schema < 50: run migrations (lazy import)
│ ├── \_ensure_meta_fields() # Ensure required fields exist (ALL installs)
│ ├── run_startup_safety_net() # Registry validation (ALL installs)
│ └── emit(DATA_READY)
│
└── async_setup() # Timer registration
├── register midnight timer → emit(MIDNIGHT_ROLLOVER)
└── listen for \*\_DELETED signals

```

- **Key Decision**: What about `_remove_legacy_keys()`?
- These keys (`migration_performed`, `migration_key_version`) are from KC 4.x beta (schema v41)
- They only exist if user upgraded from v4.x beta → v0.5.0
- **Decision**: Move to `migration_pre_v50.py` because they're legacy cleanup, not ongoing governance
- Future: Can be removed when v4.x beta users have all upgraded

- **Steps / detailed work items**
1. - [x] Analysis complete (documented above)
2. - [x] During Phase 2, ensure migration-specific code goes to `migration_pre_v50.py`
3. - [x] During Phase 2, ensure governance code goes to `SystemManager`
4. - [x] Add comment in `migration_pre_v50.py` header listing all methods for easy removal

- **Key issues**
- None encountered

### Phase 2 – The "Baton Start" Pattern (Coordinator → SystemManager Handoff)

- **Goal**: Coordinator loads data, calls SystemManager for integrity (BLOCKING), then SystemManager emits DATA_READY.

- **Critical Safety Pattern: Why Blocking Call?**
```

❌ WRONG: emit(DATA_LOADED) from Coordinator - Race: ChoreManager and SystemManager receive signal simultaneously - Crash: ChoreManager tries reset logic on v41 schema data - Result: Code crashes looking for keys that haven't been migrated yet

✅ CORRECT: await system_manager.ensure_data_integrity() then emit - Blocking: Migrations complete BEFORE any domain manager sees data - Safe: All managers receive clean, migrated data - Linear: No race conditions, predictable boot sequence

````

- **Separation of Concerns (Stay vs Move)**
| Feature | Stay in Coordinator (Infra) | Move to SystemManager (Governance) | Rationale |
|---------|----------------------------|-----------------------------------|-----------|
| Storage Access | `self.store.data` | | Only Hub touches raw disk |
| Memory Pointer | `self._data = ...` | | Hub holds central dict |
| Version Detection | Read `schema_version` | | Hub identifies "Package" version |
| Migrations | | `_run_pre_v50_migrations()` | Hub doesn't care HOW data transforms |
| Meta-Data Setup | | `_init_modern_meta_section()` | Metadata is Governance |
| Legacy Key Cleanup | | `_remove_legacy_keys()` | Hub shouldn't know about v41 bugs |
| Timers (Midnight) | | `register_timers()` | Time-cycles are System task |
| Domain Init | | `emit(SIGNAL_DATA_READY)` | Hub shouldn't know stats/badges exist |

- **Steps / detailed work items**

**Step 2.1 – Slim Down Coordinator to Pure Infrastructure**

1. - [x] Create `_get_default_structure()` helper method:
   ```python
   def _get_default_structure(self) -> dict[str, Any]:
       """Return empty data structure for new installations."""
       return {
           const.DATA_KIDS: {},
           const.DATA_CHORES: {},
           const.DATA_BADGES: {},
           const.DATA_REWARDS: {},
           const.DATA_PARENTS: {},
           const.DATA_PENALTIES: {},
           const.DATA_BONUSES: {},
           const.DATA_ACHIEVEMENTS: {},
           const.DATA_CHALLENGES: {},
           const.DATA_META: {
               const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_STORAGE_ONLY,
               const.DATA_META_PENDING_EVALUATIONS: [],
           },
       }
   ```

2. - [x] Refactor `async_config_entry_first_refresh` to "Baton Start":
   ```python
   async def async_config_entry_first_refresh(self):
       """Load from storage and hand off to SystemManager for integrity."""
       const.LOGGER.debug("Coordinator: Loading data from storage")

       # 1. Physical Load (Infrastructure responsibility)
       stored_data = self.store.data
       self._data = stored_data or self._get_default_structure()

       # 2. Version Check (Read-only, for passing to SystemManager)
       meta = self._data.get(const.DATA_META, {})
       current_version = meta.get(
           const.DATA_META_SCHEMA_VERSION,
           self._data.get(const.DATA_SCHEMA_VERSION, const.DEFAULT_ZERO),
       )

       # 3. BLOCKING Integrity Gate (The "Baton Pass")
       # Coordinator: "I have data, but don't know if it's correct for v50.
       # SystemManager, please fix it and don't return until it's safe."
       await self.system_manager.ensure_data_integrity(current_version=current_version)

       # 4. Finalize Infrastructure (cascade is complete, persist result)
       self._persist(immediate=True)
       await super().async_config_entry_first_refresh()
   ```

3. - [x] Remove ALL migration logic from coordinator:
   - Delete: `if storage_schema_version < const.SCHEMA_VERSION_STORAGE_ONLY:` block
   - Delete: `self._run_pre_v50_migrations()` call
   - Delete: `self._data[const.DATA_META] = {...}` assignment
   - Delete: Legacy key cleanup (`MIGRATION_PERFORMED`, `MIGRATION_KEY_VERSION`)
   - Delete: `_run_pre_v50_migrations()` method (moves to SystemManager)

4. - [ ] Remove ALL timer registrations (DEFERRED to Phase 2.5):
   - Note: Timers remain in Coordinator with TODO comment for Phase 2.5

5. - [ ] Remove ALL domain initialization (DEFERRED to Phase 4):
   - Note: Badge refs + stats init remain until managers listen to DATA_READY

**Step 2.2 – SystemManager becomes Data Governance**

1. - [ ] Add `ensure_data_integrity()` method to SystemManager:
   ```python
   async def ensure_data_integrity(self, current_version: int) -> None:
       """Ensure data is migrated and clean before domain managers start.

       This is a BLOCKING call from Coordinator. No domain manager should
       see data until this method returns.

       Args:
           current_version: Schema version detected by Coordinator
       """
       const.LOGGER.debug(
           "SystemManager: Ensuring data integrity (schema version: %s)",
           current_version,
       )

       # 1. Execute Migrations if needed (v41 → v50)
       # NOTE: The migrator handles ALL pre-v50 logic including meta section setup
       # and legacy key cleanup. This keeps migration logic in one droppable module.
       if current_version < const.SCHEMA_VERSION_STORAGE_ONLY:
           self._run_pre_v50_migrations()
           const.LOGGER.info(
               "SystemManager: Migrated from schema %s to %s",
               current_version,
               const.SCHEMA_VERSION_STORAGE_ONLY,
           )

       # 2. Ensure meta section has all required fields (ALL installations)
       # This runs for both fresh installs and upgrades
       self._ensure_meta_fields()

       # 3. Startup Safety Net (Registry validation)
       await self.run_startup_safety_net()
       const.LOGGER.info("SystemManager: Data integrity verified")

       # 4. THE BATON PASS: Data is now clean and safe
       # Signal domain managers to begin their initialization
       self.emit(const.SIGNAL_SUFFIX_DATA_READY)
   ```

2. - [x] Move `_run_pre_v50_migrations()` to SystemManager (thin wrapper):
   ```python
   def _run_pre_v50_migrations(self) -> None:
       """Run pre-v50 schema migrations.

       Lazy-loads the migration module to avoid any cost for v50+ users.
       The PreV50Migrator handles ALL migration logic including:
       - Schema transformations
       - Meta section initialization (schema_version, migration_date)
       - Legacy key cleanup (migration_performed, migration_key_version)
       """
       from .migration_pre_v50 import PreV50Migrator

       migrator = PreV50Migrator(self.coordinator)
       migrator.run_all_migrations()
   ```

3. - [x] Add meta field ensurer (ONGOING GOVERNANCE - runs for ALL installs):
   ```python
   def _ensure_meta_fields(self) -> None:
       """Ensure all required meta fields exist.

       This runs for BOTH fresh installs and upgrades.
       Fresh installs get meta section from _get_default_structure().
       Upgrades get meta section from PreV50Migrator.
       This method ensures any NEW required fields exist for both cases.
       """
       if const.DATA_META not in self._data:
           self._data[const.DATA_META] = {}
       meta = self._data[const.DATA_META]

       # Required fields for all installations
       if const.DATA_META_PENDING_EVALUATIONS not in meta:
           meta[const.DATA_META_PENDING_EVALUATIONS] = []

       # Ensure schema version exists (should always be set, but safety net)
       if const.DATA_META_SCHEMA_VERSION not in meta:
           meta[const.DATA_META_SCHEMA_VERSION] = const.SCHEMA_VERSION_STORAGE_ONLY
   ```

4. - [x] **Update PreV50Migrator.run_all_migrations()** to include meta setup and legacy cleanup:
   ```python
   # migration_pre_v50.py - END of run_all_migrations()

   def run_all_migrations(self) -> None:
       """Execute all pre-v50 migrations in the correct order."""
       # ... existing Phase 1-10 migrations ...

       # Phase 11: Finalize migration metadata (MUST be last)
       self._finalize_migration_meta()

       const.LOGGER.info("All pre-v50 migrations completed successfully")

   def _finalize_migration_meta(self) -> None:
       """Set up v50+ meta section and clean legacy keys.

       This MUST run at the end of all migrations because:
       1. Schema version should only be updated after ALL migrations succeed
       2. Legacy keys might be needed during migration (not anymore, but safety)

       This method will be REMOVED when migration_pre_v50.py is dropped.
       """
       from homeassistant.util import dt as dt_util
       from datetime import datetime

       # Set modern meta section
       self.coordinator._data[const.DATA_META] = {
           const.DATA_META_SCHEMA_VERSION: const.SCHEMA_VERSION_STORAGE_ONLY,
           const.DATA_META_LAST_MIGRATION_DATE: datetime.now(dt_util.UTC).isoformat(),
           const.DATA_META_MIGRATIONS_APPLIED: const.DEFAULT_MIGRATIONS_APPLIED,
           const.DATA_META_PENDING_EVALUATIONS: [],
       }

       # Remove old top-level schema_version if present (v42 → v50)
       self.coordinator._data.pop(const.DATA_SCHEMA_VERSION, None)

       # Clean up legacy beta keys (KC 4.x beta, schema v41)
       if const.MIGRATION_PERFORMED in self.coordinator._data:
           const.LOGGER.debug("Cleaning up legacy key: migration_performed")
           del self.coordinator._data[const.MIGRATION_PERFORMED]
       if const.MIGRATION_KEY_VERSION in self.coordinator._data:
           const.LOGGER.debug("Cleaning up legacy key: migration_key_version")
           del self.coordinator._data[const.MIGRATION_KEY_VERSION]
   ```

- **Key issues / Traps to Avoid**

| Trap | Issue | Fix |
|------|-------|-----|
| "Uninitialized Data" Race | StatisticsManager generates stats before ChoreManager resets | Strict cascade: SYSTEM_READY → CHORES_READY → STATS_READY |
| "Migration Ghost" | Coordinator properties return legacy-formatted data | `ensure_data_integrity()` must be BLOCKING (`await`) |
| "Double Persistence" | `_persist()` called before cascade completes | Keep in Coordinator, but AFTER `await ensure_data_integrity()` |
| "Migration in Governance" | Pre-v50 logic mixed into SystemManager | Keep ALL migration logic in `migration_pre_v50.py` for clean removal |

### Phase 2.5 – SystemManager Timer Registration (The Heartbeat Owner)

- **Goal**: SystemManager owns ALL timer registrations in `async_setup()`. Emits time-cycle signals.

- **Note**: Data integrity and DATA_READY emission are handled in `ensure_data_integrity()` (Phase 2).
Timer registration happens in `async_setup()` which runs during manager initialization.

- **Rationale (Platinum Standard)**
| Role | Responsibility | Benefit |
|------|----------------|---------|
| Data Governance | `ensure_data_integrity()` - migrations, cleanup, safety net | Blocking call ensures clean data |
| Timer Owner | `async_setup()` - registers ALL `async_track_time_change` | Coordinator becomes pure skeleton |
| Signal Emitter | Emits DATA_READY, MIDNIGHT_ROLLOVER, PERIODIC_UPDATE | Single source of lifecycle signals |
| Failure Isolation | If cleanup crashes, Coordinator skeleton survives | Integration stays alive |

- **SystemManager Responsibilities Summary**
| Method | Trigger | Action | Signal Emitted |
|--------|---------|--------|----------------|
| `ensure_data_integrity()` | Coordinator calls (blocking) | Migrations, cleanup, safety net | SIGNAL_DATA_READY |
| `async_setup()` | Manager initialization | Register timers, listen for *_DELETED | (timers emit later) |
| Timer callback | Midnight | - | SIGNAL_MIDNIGHT_ROLLOVER |
| Timer callback | 5-min interval (optional) | - | SIGNAL_PERIODIC_UPDATE |

- **Steps / detailed work items**
1. - [x] Register timers in `async_setup()`:
   - SystemManager registers single `async_track_time_change` at midnight
   - Callback `_on_midnight_tick()` emits `SIGNAL_SUFFIX_MIDNIGHT_ROLLOVER`
   - Removed 3 direct timer registrations from Coordinator

2. - [x] Domain managers subscribe to MIDNIGHT_ROLLOVER:
   - ChoreManager: `_on_midnight_rollover()` calls `process_recurring_chore_resets()` + `check_overdue_chores()`
   - UIManager: `_on_midnight_rollover()` calls `bump_past_datetime_helpers()`
   - Both use broad `except Exception:` with logging (valid for background tasks per AGENTS.md)

3. - [x] Updated boundary checker allowlist:
   - Added `chore_manager.py` and `ui_manager.py` for background task exceptions

- **Key issues**
- None - emit() works synchronously as expected (uses async_dispatcher_send)

- **Key issues**
- Lambda in `async_track_time_change` must be sync; `emit()` must be callable synchronously
- Verify `emit()` works as sync (dispatcher_send is sync, should work)
- Future-proof: Adding a `BackupManager` that creates safety backups nightly only requires adding a listener there

### Phase 3 – Periodic Pulse (Update Refactor)

- **Goal**: Replace direct manager calls in `_async_update_data` with single `PERIODIC_UPDATE` signal.

- **Steps / detailed work items**
1. - [x] Refactor `_async_update_data`:
   - Removed direct calls to `check_overdue_chores()`, `check_chore_due_window_transitions()`, `check_chore_due_reminders()`
   - Added `async_dispatcher_send()` to emit `SIGNAL_SUFFIX_PERIODIC_UPDATE`
   - Uses `get_event_signal()` helper for instance-scoped signal key

2. - [x] Wire ChoreManager to listen for PERIODIC_UPDATE:
   - Added `self.listen(const.SIGNAL_SUFFIX_PERIODIC_UPDATE, self._on_periodic_update)` in `async_setup()`
   - Added `_on_periodic_update()` handler that calls maintenance methods
   - Uses broad exception catch with logging (valid for background tasks)

- **Key issues**
- None - coordinator now only emits signal, ChoreManager reacts autonomously

### Phase 4 – Manager Wiring

- **Goal**: Wire each manager to listen for appropriate lifecycle signals.

#### 4.1 ChoreManager

- **Steps**
1. - [x] Add listeners in `async_setup()`:
   - Added `self.listen(const.SIGNAL_SUFFIX_DATA_READY, self._on_data_ready)`

2. - [x] Implement `_on_data_ready`:
   - Recalculates chore stats for all kids
   - Emits `SIGNAL_SUFFIX_CHORES_READY` to continue cascade

3. - [x] `_on_periodic_update` already wired in Phase 3

4. - [x] `_on_midnight` already wired in Phase 2.5

#### 4.2 StatisticsManager

- **Steps**
1. - [x] Add listener: `self.listen(const.SIGNAL_SUFFIX_CHORES_READY, self._on_chores_ready)`

2. - [x] Implement `_on_chores_ready`:
   - Calls `_hydrate_cache_all_kids()` to populate presentation stats
   - Emits `SIGNAL_SUFFIX_STATS_READY` to continue cascade

#### 4.3 GamificationManager

- **Steps**
1. - [x] Add listener: `self.listen(const.SIGNAL_SUFFIX_STATS_READY, self._on_stats_ready)`

2. - [x] Implement `_on_stats_ready`:
   - Calls `update_chore_badge_references_for_kid()` to init badge refs
   - Emits `SIGNAL_SUFFIX_GAMIFICATION_READY` to complete cascade
   - Logs "KidsChores initialization cascade complete"

#### 4.4 Coordinator Cleanup

- **Steps**
1. - [x] Remove direct manager calls from `async_config_entry_first_refresh`:
   - Removed `self.gamification_manager.update_chore_badge_references_for_kid()`
   - Removed `for kid: chore_manager.recalculate_chore_stats_for_kid()` loop
   - Updated comments to document cascade-driven initialization

- **Key issues**
- None - cascade self-organizes via signals

### Phase 5 – Validation

- **Goal**: Verify cascade ordering, ensure all tests pass, document behavior.

- **Steps / detailed work items**
1. - [x] Run full test suite: `python -m pytest tests/ -v --tb=line`
   - Result: 1148 passed, 2 skipped ✅
   - Fixed: `test_storage_manager.py` updated for modern `DATA_META` structure

2. - [x] Run lint/type check: `./utils/quick_lint.sh --fix`
   - Result: mypy 0 errors, all 10 architectural boundaries ✅

3. - [x] Add cascade integration test:
   - Added `TestStartupCascade` class to `test_event_infrastructure.py`
   - Tests: signal constants defined, signal values match convention, managers have handlers

4. - [x] Update `docs/ARCHITECTURE.md` with cascade diagram
   - Added "Infrastructure Coordinator Pattern" section with cascade diagram
   - Documents "Timer Ownership" pattern

5. - [x] Update `docs/DEVELOPMENT_STANDARDS.md` with "Don't call, just listen" rule
   - Added anti-pattern: direct manager calls from Coordinator
   - Added Golden Rule: "Don't call, just listen"

- **Key issues**
- None encountered

---

## Testing & validation

- **Tests to run**:
- `python -m pytest tests/ -v --tb=line -q` (full suite)
- `python -m pytest tests/test_chore_manager.py tests/test_gamification_engine.py -v` (cascade-affected)
- `./utils/quick_lint.sh --fix` (lint/type/architectural boundaries)

- **New tests to add**:
- `test_startup_cascade_order` – Verify signal sequence
- `test_periodic_update_signal` – Verify managers respond to pulse
- `test_cascade_failure_isolation` – Verify one manager failure doesn't crash cascade

---

## Notes & follow-up

### Implementation Rule (Platinum Standard)

> **"Don't call, just listen."**
>
> No Manager method should ever be called directly inside the Coordinator's `_async_update_data` or `async_config_entry_first_refresh`. If a Manager needs to do work, it must subscribe to the appropriate lifecycle signal.

### Benefits Summary

| Benefit | Description |
|---------|-------------|
| **Absolute Coordinator Purity** | Coordinator = `_data` holder + `_persist()` caller + `store` wrapper + ONE blocking call to SystemManager |
| **Data Governance via Baton Start** | Coordinator loads → calls `await system_manager.ensure_data_integrity()` (BLOCKING) → SystemManager emits DATA_READY |
| **No "Dirty Data" Race** | Migrations complete BEFORE any domain manager sees data |
| **Single Point of Timer Ownership** | All `async_track_time_change` calls in SystemManager, not scattered across files |
| **Elimination of Circular Imports** | Managers no longer call each other's init methods |
| **Manager Autonomy** | New managers hook into signal chain without touching coordinator |
| **Linear Debugging** | Startup issues traced by watching signal flow: DATA_READY → CHORES_READY → STATS_READY → GAMIFICATION_READY |
| **Performance** | Load (Coordinator) separated from Validate/Migrate (SystemManager) separated from Recalculate (Domain Managers) |
| **Testability** | Mock signal, verify manager response in isolation |
| **Timer Consolidation** | 3 midnight timers → 1 single broadcast (HA resource efficiency) |
| **Error Isolation** | Each manager's handlers have try/except; failures don't cascade |
| **Future-Proof** | Adding BackupManager nightly task = add MIDNIGHT_ROLLOVER listener, no other changes |

### The Holy Grail: Coordinator as "Reliable Switchboard"

After this refactor, `coordinator.py` becomes:
1. **A `_data` holder** - reads from storage, holds in memory
2. **A `_persist()` caller** - writes back to storage
3. **A `store` wrapper** - interface to KidsChoresStore
4. **ONE blocking call** - `await self.system_manager.ensure_data_integrity()`

**It owns NO:**
- Migrations (→ SystemManager)
- Meta section setup (→ SystemManager)
- Legacy key cleanup (→ SystemManager)
- Timers (→ SystemManager)
- Domain logic (→ Domain Managers)
- Manager orchestration (→ Signal cascade)
- Entity registry knowledge (→ SystemManager)

### Future Considerations

- **v0.6.0+**: Consider adding `SIGNAL_SUFFIX_SHUTDOWN` for graceful cleanup
- **Multi-instance**: Signals are already entry_id-scoped, cascade is instance-safe
- **Async cascade**: Current design is synchronous-ish (signal handlers run in order), may need async barrier for true parallelism

---

## Appendix: Signal Reference

### Lifecycle Cascade (Startup)

````

Coordinator.async_config_entry_first_refresh()
│
├── 1. Load storage (self.\_data = self.store.data)
│
├── 2. await system_manager.ensure_data_integrity(version) ← BLOCKING
│ │
│ ├── Migrations (if needed)
│ ├── Meta section setup
│ ├── Legacy key cleanup
│ ├── run_startup_safety_net()
│ │
│ └── emit(DATA_READY) ← SystemManager emits this
│ │
│ ▼
│ ChoreManager.\_on_data_ready()
│ │ └── recalculate_chore_stats_for_kid()
│ │
│ └── emit(CHORES_READY)
│ │
│ ▼
│ StatisticsManager.\_on_chores_ready()
│ │ └── generate_point_stats()
│ │
│ └── emit(STATS_READY)
│ │
│ ▼
│ GamificationManager.\_on_stats_ready()
│ │ └── update_chore_badge_references()
│ │
│ └── emit(GAMIFICATION_READY)
│ │
│ ▼
│ UIManager.\_on_gamification_ready()
│ └── Log "Cascade complete"
│
├── 3. self.\_persist(immediate=True)
│
└── 4. await super().async_config_entry_first_refresh()

````

| Signal | Emitter | Listeners | Payload |
|--------|---------|-----------|---------|
| `DATA_READY` | SystemManager (in `ensure_data_integrity`) | ChoreManager | `{}` |
| `CHORES_READY` | ChoreManager | StatisticsManager | `{}` |
| `STATS_READY` | StatisticsManager | GamificationManager | `{}` |
| `GAMIFICATION_READY` | GamificationManager | UIManager | `{}` |

### Timer-Triggered Events (Owned by SystemManager)

| Signal | Trigger | Listeners | Payload |
|--------|---------|-----------|---------|
| `MIDNIGHT_ROLLOVER` | SystemManager (async_track_time_change) | ChoreManager, UIManager, StatisticsManager | `{}` |
| `PERIODIC_UPDATE` | SystemManager (async_track_time_interval) | ChoreManager, NotificationManager, StatisticsManager | `{}` |

### The "Baton Start" Pattern Summary

**Before (Coordinator as Database Administrator + Product Manager):**
```python
# coordinator.py - Knows migrations, knows stats, knows badges, owns timers
if storage_schema_version < SCHEMA_VERSION_STORAGE_ONLY:
    self._run_pre_v50_migrations()
    self._data[DATA_META] = {...}
async_track_time_change(hass, chore_manager.process_recurring_chore_resets, ...)
async_track_time_change(hass, chore_manager.check_overdue_chores, ...)
async_track_time_change(hass, ui_manager.bump_past_datetime_helpers, ...)
gamification_manager.update_chore_badge_references_for_kid()
for kid_id in kids_data: chore_manager.recalculate_chore_stats_for_kid(kid_id)
````

**After (Coordinator as "Reliable Switchboard"):**

```python
# coordinator.py - Loads, hands baton to SystemManager, persists
async def async_config_entry_first_refresh(self):
    self._data = self.store.data or self._get_default_structure()
    version = self._data.get(DATA_META, {}).get(DATA_META_SCHEMA_VERSION, 0)

    await self.system_manager.ensure_data_integrity(current_version=version)  # BLOCKING

    self._persist(immediate=True)
    await super().async_config_entry_first_refresh()
```

async_track_time_change(hass, ui_manager.bump_past_datetime_helpers, ...)
gamification_manager.update_chore_badge_references_for_kid()
for kid_id in kids_data: chore_manager.recalculate_chore_stats_for_kid(kid_id)

````

**After (Coordinator as Pure Skeleton):**
```python
# coordinator.py - Owns ONLY: _data, _persist(), store wrapper
async def async_config_entry_first_refresh(self):
    stored_data = self.store.data
    if stored_data:
        self._data = stored_data
        # migrations...
    self.emit(const.SIGNAL_SUFFIX_DATA_READY)  # THE ONLY DOMAIN-AWARE ACTION
    self._persist(immediate=True)
    await super().async_config_entry_first_refresh()

# SystemManager handles ALL timers and cascades SYSTEM_READY
# ChoreManager handles chore logic on SYSTEM_READY
# UIManager handles UI logic on GAMIFICATION_READY
# Each manager isolated with try/except, failures don't cascade
````

### Manager Responsibilities Summary

| Manager                 | Startup Role                    | Midnight Role                   | Periodic Role                 |
| ----------------------- | ------------------------------- | ------------------------------- | ----------------------------- |
| **SystemManager**       | Registry Guard → SYSTEM_READY   | Timer Owner → MIDNIGHT_ROLLOVER | Timer Owner → PERIODIC_UPDATE |
| **ChoreManager**        | Recalc stats → CHORES_READY     | Resets + Overdue checks         | Due windows + Reminders       |
| **StatisticsManager**   | Hydrate cache → STATS_READY     | Invalidate cache                | -                             |
| **GamificationManager** | Badge refs → GAMIFICATION_READY | -                               | -                             |
| **UIManager**           | Log completion                  | Bump datetime helpers           | -                             |
