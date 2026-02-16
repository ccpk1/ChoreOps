# Initiative Plan: Atomic Migration Hardening

## Initiative snapshot

- **Name / Code**: ATOMIC-MIGRATION-HARDENING (Issue #243)
- **Target release / milestone**: v0.5.0-rc1
- **Owner / driver(s)**: @ccpk1
- **Status**: Complete — all 6 phases implemented, 24 tests passing, 1234 full suite tests passing

## Summary & immediate steps

| Phase / Step               | Description                                         | % complete | Quick notes                                         |
| -------------------------- | --------------------------------------------------- | ---------- | --------------------------------------------------- |
| Phase 1 – Schema Stamp Fix | Stop premature schema=43 stamp in config→storage    | 100%       | ✅ Transitional v42, frozen v43, beta4 v44          |
| Phase 2 – Atomic Rollback  | deepcopy + try/except around `run_all_migrations`   | 100%       | ✅ Snapshot + rollback + re-raise on failure        |
| Phase 3 – Nuclear Rebuild  | Rebuild items through `build_*()` on rollback       | 100%       | ✅ Empty user_input, existing= pattern, entity wipe |
| Phase 4 – Auto-Restore     | Auto-restore pre-migration backup as last resort    | 100%       | ✅ discover_backups + validate + restore            |
| Phase 5 – Tests            | Validate all layers with targeted test cases        | 100%       | ✅ 24 tests, all passing                            |
| Phase 6 – Schema 44 Gate   | Version-gated slot for beta 4 tweaks (runs post-43) | 100%       | ✅ Placeholder body, stamps v44                     |

1. **Key objective** – Eliminate the "malformed data after failed migration" problem reported in Issue #243. Users who upgrade should either get a clean migration OR an automatic recovery — never a half-migrated, unrecoverable state.

2. **Summary of recent work** –
   - Root cause identified: `migrate_config_to_storage()` stamps schema_version=43 **before** `run_all_migrations()` runs its 20+ structural phases. If any phase fails, the data claims "migrated" but has legacy structures. On restart, the version check skips re-migration.
   - The manual "restore from pre-migration backup" (Options → General → Restore) works reliably because it replaces malformed data with the clean pre-v50 snapshot.
   - `data_builders.build_*()` functions with `existing=` parameter already handle "reshape old data into correct schema" — this is the same code path as "delete + re-add with existing data."

3. **Next steps (short term)** –
   - Implement Phase 1 (schema stamp fix) — smallest, highest-impact change
   - Implement Phase 2 (atomic rollback) — prevents data corruption on failure
   - Implement Phase 3 (nuclear rebuild) — automated recovery using existing builders
   - Implement Phase 4 (auto-restore) — last-resort fallback using proven manual path
   - Write tests for each layer

4. **Risks / blockers** –
   - **RISK (Low)**: Phase 1 introduces a transitional schema version (42). Existing installs already at 43 are unaffected (version check gates out). Only applies to users mid-upgrade.
   - **RISK (Medium)**: Phase 3 rebuild through `build_*()` may lose some runtime state (streak data, period aggregations). Acceptable trade-off vs. completely broken integration — user would lose this data anyway with manual "Option 2" restore.
   - **RISK (Low)**: Phase 4 auto-restore relies on pre-migration backup file existing on disk. Already created by current code before any migration starts (two redundant backup creation points). If backup doesn't exist, falls through to ConfigEntryNotReady with clear user message.
   - **CONSERVATIVE DECISION**: Phase 4 preserves the proven pre-migration backup restore as the ultimate fallback. We are NOT replacing it — we are automating what the user currently does manually in Options → General → Restore.

5. **References** –
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md) – Data model, storage schema, migration section
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) – Constant naming, logging, type standards
   - [tests/AGENT_TESTING_USAGE_GUIDE.md](../../tests/AGENT_TESTING_USAGE_GUIDE.md) – Test patterns
   - GitHub Issue: [#243 — All entities showing as 'Unavailable' after upgrade](https://github.com/ad-ha/kidschores-ha/issues/243)

6. **Decisions & completion check**
   - **Decisions captured**:
     - **D1**: Use transitional schema version (42) between config→storage and full migration — only `_finalize_migration_meta()` stamps 43.
     - **D2**: Nuclear rebuild uses existing `build_*()` with `existing=` parameter — no new validation framework needed.
     - **D3**: `_*_DATA_RESET_PRESERVE_FIELDS` frozensets define what survives rebuild (user config) vs. what gets regenerated (runtime state).
     - **D4**: Pre-migration backup auto-restore is the LAST resort, preserving the proven manual recovery path. We automate it, not replace it.
     - **D5**: Entity registry wipe during nuclear rebuild is acceptable — it mirrors what already happens when user does "delete + re-add." Platforms recreate all entities on next startup.
     - **D6**: Existing pre-v50 migrations are **frozen at schema 43**. The 20+ migration phases in `run_all_migrations()` are hardcoded to produce schema 43 — no further modifications. Future changes target schema 44+.
     - **D7**: Schema 44 (beta 4) tweaks live in a **separate version-gated section** in `ensure_data_integrity()`. They ONLY run when `current_version == 43` — confirming schema 43 migration succeeded first.
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

---

## Detailed phase tracking

### Phase 1 – Schema Stamp Fix (Root Cause)

- **Goal**: Prevent `migrate_config_to_storage()` from stamping schema_version=43 before structural migrations run. Only `_finalize_migration_meta()` at the end of `run_all_migrations()` should set the final version.

- **Why this is the real bug**: Currently, `migrate_config_to_storage()` (line ~228 of `migration_pre_v50.py`) sets `DATA_META_SCHEMA_VERSION: SCHEMA_VERSION_STORAGE_ONLY` (43) and persists. Then `ensure_data_integrity()` checks `current_version < 43` → false → skips `run_all_migrations()`. But the data still has legacy structure. On restart, same version check → same skip → permanently stuck with malformed data.

- **Steps / detailed work items**:
  1. - [x] **Introduce `SCHEMA_VERSION_TRANSITIONAL` constant** in `const.py` (~line 245)
     - Value: `42` — signals "data is in storage but not yet structurally migrated"
     - Add comment: "Set by migrate_config_to_storage(), upgraded to SCHEMA_VERSION_STORAGE_ONLY by \_finalize_migration_meta()"

  2. - [x] **Change `migrate_config_to_storage()` to stamp transitional version** in `migration_pre_v50.py` (~line 228-230)
     - Change: `DATA_META_SCHEMA_VERSION: SCHEMA_VERSION_STORAGE_ONLY` → `DATA_META_SCHEMA_VERSION: SCHEMA_VERSION_TRANSITIONAL`
     - This means: "data is in storage, but structural migration has not run yet"

  3. - [x] **Update version gate in `ensure_data_integrity()`** in `managers/system_manager.py` (~line 153)
     - Current: `if current_version < const.SCHEMA_VERSION_STORAGE_ONLY` (< 43)
     - Change to: `if current_version < const.SCHEMA_VERSION_STORAGE_ONLY` — **no change needed!**
     - Why: Transitional version 42 IS < 43, so `run_all_migrations()` will now correctly trigger
     - `_finalize_migration_meta()` already stamps 43 at the end of `run_all_migrations()`

  4. - [x] **Update version gate in `__init__.py`** (~line 127)
     - Current: `if schema_version < 43:` triggers `async_migrate_uid_suffixes_v0_5_0()`
     - This already works correctly with transitional version 42 (42 < 43 → runs)
     - No code change needed, just verify behavior

  5. - [x] **Validate**: Run `./utils/quick_lint.sh --fix` + `mypy custom_components/kidschores/`

- **Key issues**:
  - Users already at schema 43 (clean migration) are completely unaffected — version check gates them out
  - Users currently stuck with malformed schema-43 data need manual restore first (this fix prevents NEW occurrences, doesn't retroactively fix existing ones — Phase 4 handles that)

---

### Phase 2 – Atomic Rollback (Safety Net)

- **Goal**: Wrap `run_all_migrations()` in a deepcopy + try/except so that if ANY migration phase fails, the in-memory data reverts to its pre-migration state instead of being left half-transformed.

- **Steps / detailed work items**:
  1. - [x] **Add `copy` import** to `migration_pre_v50.py` (top of file, ~line 3)
     - `import copy` (for `copy.deepcopy`)

  2. - [x] **Wrap migration phases in `run_all_migrations()`** in `migration_pre_v50.py` (~line 347-460)
     - Before Phase 1 starts (after backup creation, ~line 346): `snapshot = copy.deepcopy(self.coordinator._data)`
     - Wrap all Phase 1-13 calls in `try:` block
     - In `except Exception:` block:
       - Log error at WARNING level (lazy logging)
       - Restore: `self.coordinator._data = snapshot`
       - Re-raise with a custom migration error (or let caller handle)
     - Keep `_finalize_migration_meta()` INSIDE the try block (schema stamp only on full success)

  3. - [x] **Handle rollback in `ensure_data_integrity()`** in `managers/system_manager.py` (~line 150-157)
     - Wrap `await self._run_pre_v50_migrations()` in try/except
     - On failure: log error, set a flag `self._migration_failed = True`
     - Pass control to Phase 3 (nuclear rebuild) or Phase 4 (auto-restore)

  4. - [x] **Validate**: `./utils/quick_lint.sh --fix` + `mypy` + `pytest tests/` (existing tests should still pass)

- **Key issues**:
  - `deepcopy` on the full data dict may be memory-intensive for very large datasets (hundreds of kids/chores). Acceptable trade-off for migration safety — this runs exactly once per upgrade.
  - The rollback restores data to pre-migration state (schema < 43). This means Phase 3/4 can attempt recovery on clean data.

---

### Phase 3 – Nuclear Rebuild (Automated "Option 2")

- **Goal**: When Phase 2 rollback fires, attempt an automated rebuild that preserves user definitions (kids, chores, rewards, badges with names/UUIDs/points/assignments) but regenerates all runtime structure through `build_*()` functions. Also wipe all KC entities from the registry so platforms recreate them fresh.

- **This is exactly what "delete integration + re-add with existing data" does**, but automated.

- **Steps / detailed work items**:
  1. - [x] **Create `_attempt_nuclear_rebuild()` method** in `managers/system_manager.py`
     - Signature: `async def _attempt_nuclear_rebuild(self) -> bool` (returns True on success)
     - Logic flow:
       ```
       For each entity bucket (kids, chores, rewards, badges, penalties, bonuses, achievements, challenges):
           For each item in self.coordinator._data[bucket]:
               1. Extract item data as dict
               2. Pass through build_*() with existing=item_data
               3. Replace item in _data with rebuilt version
       ```
     - For kids specifically: preserve `points` value (critical user data)
     - For chores: preserve `assigned_kids`, `per_kid_due_dates` (relational data)
     - For badges: preserve `assigned_to`, `earned_by` (relational data)
     - Set meta section with `SCHEMA_VERSION_STORAGE_ONLY` (43) — rebuilt data IS valid v50 structure
     - Persist immediately

  2. - [x] **Add entity registry wipe helper** in `managers/system_manager.py`
     - Method: `async def _wipe_all_kc_entities(self) -> int`
     - Uses `er.async_entries_for_config_entry()` to get all KC entities
     - Calls `entity_registry.async_remove()` for each
     - Returns count of removed entities
     - Platforms will recreate all entities on next startup after reload

  3. - [x] **Wire into `ensure_data_integrity()` fallback chain** in `managers/system_manager.py`
     - After Phase 2 rollback: call `_attempt_nuclear_rebuild()`
     - If rebuild succeeds → log success, call `_wipe_all_kc_entities()`, continue boot
     - If rebuild fails → fall through to Phase 4 (auto-restore)

  4. - [x] **Map entity types to builders** — Reference table for implementer:

     | Bucket              | Builder function              | PRESERVE_FIELDS frozenset                 | Key preserve fields                 |
     | ------------------- | ----------------------------- | ----------------------------------------- | ----------------------------------- |
     | `DATA_KIDS`         | `build_kid(existing=item)`    | `_KID_DATA_RESET_PRESERVE_FIELDS`         | name, UUID, ha_user_id, language    |
     | `DATA_CHORES`       | `build_chore(existing=item)`  | `_CHORE_DATA_RESET_PRESERVE_FIELDS`       | name, UUID, assigned_kids, points   |
     | `DATA_REWARDS`      | `build_reward(existing=item)` | `_REWARD_DATA_RESET_PRESERVE_FIELDS`      | name, UUID, cost                    |
     | `DATA_BADGES`       | `build_badge(existing=item)`  | `_BADGE_DATA_RESET_PRESERVE_FIELDS`       | name, UUID, assigned_to, target     |
     | `DATA_PENALTIES`    | `build_bonus_or_penalty()`    | `_PENALTY_DATA_RESET_PRESERVE_FIELDS`     | name, UUID, points                  |
     | `DATA_BONUSES`      | `build_bonus_or_penalty()`    | `_BONUS_DATA_RESET_PRESERVE_FIELDS`       | name, UUID, points                  |
     | `DATA_ACHIEVEMENTS` | `build_achievement()`         | `_ACHIEVEMENT_DATA_RESET_PRESERVE_FIELDS` | name, UUID, criteria, assigned_kids |
     | `DATA_CHALLENGES`   | `build_challenge()`           | `_CHALLENGE_DATA_RESET_PRESERVE_FIELDS`   | name, UUID, criteria, assigned_kids |
     | `DATA_PARENTS`      | `build_parent(existing=item)` | (no frozenset — all fields config)        | name, UUID, associated_kids         |

  5. - [x] **Handle kid points preservation explicitly**
     - `build_kid()` with `existing=` already preserves `DATA_KID_POINTS` (line ~786 of `data_builders.py`)
     - Verify this works for negative balances (Issue #243 user had negative points — valid)

  6. - [x] **Validate**: `./utils/quick_lint.sh --fix` + `mypy` + `pytest tests/`

- **Key issues**:
  - **Data loss**: Runtime state (streaks, period aggregations, chore_data per-kid tracking) will be reset to defaults. This is the same data loss as manual "Option 2" — acceptable trade-off vs. completely broken integration.
  - **Kid points**: MUST be preserved — `build_kid()` handles this via `existing=` parameter.
  - **Relational integrity**: `assigned_kids` lists, `associated_kids` lists, badge `earned_by` lists all contain UUIDs. These survive rebuild because they're in PRESERVE_FIELDS.
  - **`build_*()` may raise `EntityValidationError`**: Wrap each item rebuild in try/except. If a single item fails, skip it and log warning (don't abort entire rebuild for one bad item).

---

### Phase 4 – Auto-Restore from Pre-Migration Backup (Last Resort)

- **Goal**: If Phase 3 nuclear rebuild also fails, automatically restore the pre-migration backup file from disk — the same proven path that works when users do it manually via Options → General → Restore.

- **CONSERVATIVE APPROACH**: This does NOT change the backup/restore logic. It just automates the manual step that already works.

- **Steps / detailed work items**:
  1. - [x] **Create `_attempt_auto_restore()` method** in `managers/system_manager.py`
     - Signature: `async def _attempt_auto_restore(self) -> bool`
     - Logic:
       1. Call `bh.discover_backups(hass, store)` to find backups
       2. Filter for `tag == "pre-migration"` (most recent first — list is pre-sorted)
       3. If found: read backup file, parse JSON, validate with `bh.validate_backup_json()`
       4. If valid: `store.set_data(backup_data)` + `await store.async_save()`
       5. Return True on success, False if no backup found or restore failed
     - This is essentially the same logic as `_handle_restore_backup_from_options()` in options_flow.py (~line 4444)

  2. - [x] **Wire into `ensure_data_integrity()` as final fallback** in `managers/system_manager.py`
     - After Phase 3 fails: call `_attempt_auto_restore()`
     - If restore succeeds → log info "Auto-restored from pre-migration backup, migration will retry on next restart"
     - Schema version in restored data will be < 43 → migration retries next boot (Phase 1 fix ensures this works)
     - If restore fails → raise `ConfigEntryNotReady` with clear message: "Migration failed and no pre-migration backup available. Please restore manually via Configure → General Options → Restore from backup."

  3. - [x] **Add TRANS_KEY constants** for user-facing messages in `const.py`
     - `TRANS_KEY_MIGRATION_FAILED_AUTO_RESTORED` — "Migration encountered an error. Your data has been automatically restored from the pre-upgrade backup. The migration will retry on next restart."
     - `TRANS_KEY_MIGRATION_FAILED_NO_BACKUP` — "Migration failed and automatic recovery was not possible. Please go to Configure → General Options → Restore from backup."

  4. - [x] **Add translation strings** in `translations/en.json` for the above keys

  5. - [x] **Validate**: `./utils/quick_lint.sh --fix` + `mypy` + `pytest tests/`

- **Key issues**:
  - Pre-migration backup is already created at two points in the code (lines ~139-148 in `migrate_config_to_storage()` and lines ~328-337 in `run_all_migrations()`). Very unlikely to be missing.
  - After auto-restore, the integration will restart with clean pre-migration data. Phase 1 fix ensures migration retries correctly.
  - If the migration fails AGAIN on retry, the cycle repeats — but the pre-migration backup is preserved (it's not deleted). User can still do manual restore.

---

### Phase 5 – Tests

- **Goal**: Validate all four defensive layers with targeted test cases simulating migration failures.

- **Steps / detailed work items**:
  1. - [x] **Test: Schema stamp fix (Phase 1)**
     - Test `migrate_config_to_storage()` stamps transitional version (42), not 43
     - Test `_finalize_migration_meta()` stamps 43
     - Test `ensure_data_integrity()` triggers `run_all_migrations()` for version 42

  2. - [x] **Test: Atomic rollback (Phase 2)**
     - Mock one migration phase to raise an exception
     - Verify `coordinator._data` is restored to pre-migration snapshot
     - Verify schema version is NOT updated to 43

  3. - [x] **Test: Nuclear rebuild (Phase 3)**
     - Provide intentionally malformed kid/chore data
     - Verify `_attempt_nuclear_rebuild()` produces valid structure via `build_*()` pass
     - Verify kid points are preserved
     - Verify relational fields (assigned_kids, associated_kids) survive

  4. - [x] **Test: Auto-restore (Phase 4)**
     - Create a mock pre-migration backup file on disk
     - Simulate all-layers-failed scenario
     - Verify auto-restore reads and applies the backup
     - Verify restored data has schema < 43 (will trigger re-migration)

  5. - [x] **Test: Full cascade (integration test)**
     - Simulate upgrade from legacy data with a failing migration step
     - Verify the fallback cascade: rollback → rebuild → auto-restore → ConfigEntryNotReady
     - Use `scenario_medium` fixture data as the pre-migration dataset

  6. - [x] **Validate**: `pytest tests/ -v --tb=line` — all tests pass

- **Key issues**:
  - Mocking individual migration phases requires patching methods on `PreV50Migrator`
  - Test file location: `tests/test_migration_hardening.py` (new file)

---

### Phase 6 – Schema 44 Gate (Beta 4 Follow-On)

- **Goal**: Provide a clean, version-gated slot for any minor tweaks needed in beta 4 (schema 44). This section ONLY runs when `current_version == 43`, confirming all pre-v50 migrations completed successfully.

- **FROZEN BOUNDARY**: The 20+ migration phases in `run_all_migrations()` are **hardcoded to produce schema 43**. They will NOT be modified. Schema 44 is a new gate entirely.

- **Steps / detailed work items**:
  1. - [x] **Add `SCHEMA_VERSION_BETA4` constant** in `const.py`
     - Value: `44` — signals "v0.5.0-beta4 schema"
     - Comment: "Post-migration tweaks for beta 4, only runs after schema 43 confirmed"

  2. - [x] **Add version-gated section in `ensure_data_integrity()`** in `managers/system_manager.py`
     - Position: AFTER the pre-v50 migration block, BEFORE `run_startup_safety_net()`
     - Guard: `if current_version == 43:` (exactly 43, not < 44)
     - This ensures: schema 43 migration succeeded → safe to apply beta 4 tweaks
     - On success: update meta schema_version to 44
     - Placeholder: `self._migrate_to_schema_44()` method with comment "Add beta 4 tweaks here"

  3. - [x] **Create `_migrate_to_schema_44()` method** in `managers/system_manager.py`
     - Placeholder method with docstring explaining its purpose
     - Currently empty (no tweaks needed yet) — will be populated as beta 4 requirements emerge
     - Stamps `SCHEMA_VERSION_BETA4` (44) in meta section on success

  4. - [x] **Update `SCHEMA_VERSION_STORAGE_ONLY` usage**
     - `SCHEMA_VERSION_STORAGE_ONLY` (43) remains as-is — it's the target of pre-v50 migrations
     - `SCHEMA_VERSION_BETA4` (44) is the NEW current version for beta 4 installs
     - Fresh installs should use the highest version (44) in `migrate_config_to_storage()` clean-install path and `_finalize_migration_meta()`

  5. - [x] **Validate**: `./utils/quick_lint.sh --fix` + `mypy` + `pytest tests/`

- **Key issues**:
  - Schema 44 tweaks are intentionally EMPTY right now. The gate infrastructure is what matters — it provides a safe place to add beta 4 changes without touching frozen schema 43 code.
  - Users who were stuck at malformed schema 43 data will benefit from Phases 1-4 first, then schema 44 runs on next restart if applicable.
  - The `if current_version == 43:` guard means: "schema 43 succeeded, now apply 44." If schema 43 failed → Phase 2/3/4 cascade handles it → data stays at < 43 → schema 44 never triggers (correct behavior).

---

## Fallback Cascade Summary

```
ensure_data_integrity(current_version)
│
├─ current_version >= 43 → SKIP pre-v50 (already migrated)
│  │
│  └─ current_version == 43 → [Phase 6] _migrate_to_schema_44()
│     │                         (beta 4 tweaks, stamps 44)
│     └─ current_version >= 44 → DONE ✅ (fully current)
│
├─ current_version < 43 → RUN MIGRATIONS
│  │
│  ├─ [Phase 2] run_all_migrations() with deepcopy snapshot
│  │  │
│  │  ├─ SUCCESS → _finalize_migration_meta() stamps 43 → [Phase 6] → DONE ✅
│  │  │
│  │  └─ FAILURE → restore snapshot (data reverts to pre-migration)
│  │     │
│  │     ├─ [Phase 3] _attempt_nuclear_rebuild()
│  │     │  │
│  │     │  ├─ SUCCESS → stamps 43, wipes entity registry → [Phase 6] → DONE ✅
│  │     │  │  (entities recreated by platform setup)
│  │     │  │
│  │     │  └─ FAILURE → fall through
│  │     │     │
│  │     │     ├─ [Phase 4] _attempt_auto_restore()
│  │     │     │  │
│  │     │     │  ├─ SUCCESS → restores backup (schema < 43)
│  │     │     │  │  → retries migration on next restart → RECOVERED ✅
│  │     │     │  │
│  │     │     │  └─ FAILURE → no backup found
│  │     │     │     │
│  │     │     │     └─ raise ConfigEntryNotReady
│  │     │     │        "Please restore manually via Options"
│  │     │     │        → USER ACTION REQUIRED ⚠️
```

## Testing & validation

- **Primary validation command**: `pytest tests/test_migration_hardening.py -v`
- **Full regression**: `pytest tests/ -v --tb=line`
- **Lint**: `./utils/quick_lint.sh --fix`
- **Type check**: `mypy custom_components/kidschores/`
- Outstanding: Test scenarios will be designed in Phase 5 implementation

## Notes & follow-up

- **Files modified** (estimated):
  - `custom_components/kidschores/const.py` — Add `SCHEMA_VERSION_TRANSITIONAL`, `SCHEMA_VERSION_BETA4`, TRANS_KEY constants
  - `custom_components/kidschores/migration_pre_v50.py` — Phase 1 stamp fix, Phase 2 deepcopy/rollback
  - `custom_components/kidschores/managers/system_manager.py` — Phase 2-4 fallback chain, Phase 6 schema 44 gate
  - `custom_components/kidschores/translations/en.json` — Migration error/recovery translation strings
  - `tests/test_migration_hardening.py` — New test file for all phases

- **Not modified** (conservative choice):
  - `__init__.py` — No changes needed (version gate at line 127 works with transitional version)
  - `store.py` — No changes needed (Store.get_default_structure() already correct)
  - `data_builders.py` — No changes needed (build\_\*() already handles existing= parameter)
  - `helpers/backup_helpers.py` — No changes needed (discover_backups() already works)
  - `options_flow.py` — No changes needed (manual restore path preserved as-is)

- **Future consideration**: Once the vast majority of users are past v0.5.0, the entire `migration_pre_v50.py` module can be removed (it already has a deprecation notice in its header). At that point, Phases 2-4 of this initiative become dead code and can also be removed.
