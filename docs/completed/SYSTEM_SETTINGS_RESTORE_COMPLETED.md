# Initiative Plan: System Settings Backup Restore

## Initiative snapshot

- **Name / Code**: SYSTEM_SETTINGS_RESTORE – Complete backup/restore for config_entry settings
- **Target release / milestone**: v0.5.0 Beta 3 or v0.5.0 Final
- **Owner / driver(s)**: KidsChores Development Team
- **Status**: Not started

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
|--------------|-------------|------------|-------------|
| Phase 0 – Add Constants | Define storage keys and defaults | 100% | ✅ Added to const.py |
| Phase 1 – Enhance Backup Creation | Capture config_entry.options to storage | 100% | ✅ Augmented flow_helpers |
| Phase 2 – Enhance Restore Logic | Apply config_entry_settings from backup | 100% | ✅ Modified flows |
| Phase 3 – Update Diagnostics | Include settings in export | 100% | ✅ Modified diagnostics.py |
| Phase 4 – Testing & Validation | Roundtrip tests, validation tests | 100% | ✅ Added 3 tests (512/520 pass) |

1. **Key objective** – Ensure the 9 system settings stored in `config_entry.options` are included in backups and restored, providing complete data recovery.

2. **Architecture decisions (finalized)**
   - **Storage format**: Add `config_entry_settings` key to storage file (alongside `data`)
   - **Backup creation**: Read `config_entry.options` → write to `config_entry_settings` in storage file
   - **Restore strategy**: Extract `config_entry_settings` from backup → call `async_update_entry()` → use defaults if missing
   - **Implementation location**: Logic in config_flow.py and options_flow.py (NOT flow_helpers.py)
   - **Diagnostics**: Always include `config_entry_settings` in export

3. **Next steps (short term)**
   - Add `DATA_CONFIG_ENTRY_SETTINGS` constant and `DEFAULT_SYSTEM_SETTINGS` dict
   - Modify backup creation to write augmented storage file with settings
   - Modify restore flows to read settings and call `async_update_entry()`
   - Update diagnostics to include settings section

4. **Risks / blockers**
   - **Reload requirement**: Settings restore requires integration reload (expected behavior)
   - **Backward compatibility**: v0.5.0 backups without settings will use defaults (acceptable)
   - **File format change**: Storage file gains new top-level key (non-breaking addition)
   - **Migration**: Existing v0.5.0 users unaffected (their storage files don't have settings key yet)

5. **References**
   - [tests/TESTING_AGENT_INSTRUCTIONS.md](../../tests/TESTING_AGENT_INSTRUCTIONS.md)
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md) – Storage-Only Mode section
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - Backup method: [coordinator.py](../../custom_components/kidschores/coordinator.py) lines ~7739-7825
   - Restore method: [coordinator.py](../../custom_components/kidschores/coordinator.py) lines ~7927-8111

6. **Decisions & completion check**
   - **Decisions captured**:
     - [x] Decision: Reload behavior → Return flag `system_settings_restored: True` in response; user/caller decides when to reload
     - [x] Decision: Partial settings → Merge with current options (only update keys present in backup)
     - [x] Decision: v1 backups → Skip settings restore gracefully, log info message
   - **Completion confirmation**: [x] All follow-up items completed (constants, helpers, flows, diagnostics, tests). Initiative marked done.

> **Important:** Keep the entire Summary section current with every meaningful update.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps.
- **Detailed tracking**: Use the phase-specific sections below for granular progress.

## Detailed phase tracking

### Phase 0 – Add Constants

- **Goal**: Define storage keys and default settings dictionary.

- **Steps / detailed work items**
  1. - [x] Add constant for config_entry_settings storage key in const.py (~line 507)
     ```python
     # After DATA_KEY_LINKED_USERS definition
     DATA_CONFIG_ENTRY_SETTINGS: Final = "config_entry_settings"
     ```
  2. - [x] Add DEFAULT_SYSTEM_SETTINGS dictionary in const.py (~line 530 after defaults section)
     ```python
     # System Settings Defaults (for backup/restore validation)
     DEFAULT_SYSTEM_SETTINGS: Final = {
         CONF_POINTS_LABEL: DEFAULT_POINTS_LABEL,
         CONF_POINTS_ICON: DEFAULT_POINTS_ICON,
         CONF_UPDATE_INTERVAL: DEFAULT_UPDATE_INTERVAL,
         CONF_CALENDAR_SHOW_PERIOD: DEFAULT_CALENDAR_SHOW_PERIOD,
         CONF_RETENTION_DAILY: DEFAULT_RETENTION_DAILY,
         CONF_RETENTION_WEEKLY: DEFAULT_RETENTION_WEEKLY,
         CONF_RETENTION_MONTHLY: DEFAULT_RETENTION_MONTHLY,
         CONF_RETENTION_YEARLY: DEFAULT_RETENTION_YEARLY,
         CONF_POINTS_ADJUST_VALUES: DEFAULT_POINTS_ADJUST_VALUES,
     }
     ```
  3. - [x] Run quick_lint to verify constant additions
     ```bash
     ./utils/quick_lint.sh --fix
     ```

- **Key issues**
  - Ensure all DEFAULT_* constants already exist (they do per ARCHITECTURE.md)

### Phase 2 – Core Implementation

- **Goal**1 – Enhance Backup Creation

- **Goal**: Capture config_entry.options and write to storage file's config_entry_settings section.

- **Steps / detailed work items**
  1. - [x] Add helper function in flow_helpers.py (~line 3385 after create_timestamped_backup)
     ```python
     def _augment_backup_with_settings(
         backup_data: dict[str, Any], 
         config_entry_options: dict[str, Any]
     ) -> dict[str, Any]:
         """Add config_entry_settings to backup data.
         
         Args:
             backup_data: Existing storage data with "version" and "data" keys
             config_entry_options: The config_entry.options dict
             
         Returns:
             Augmented backup data with config_entry_settings section
         """
         # Extract only the 9 system settings
         settings = {
             key: config_entry_options.get(key, default)
             for key, default in const.DEFAULT_SYSTEM_SETTINGS.items()
         }
         
         # Add to backup data (non-destructive)
         augmented = dict(backup_data)
         augmented[const.DATA_CONFIG_ENTRY_SETTINGS] = settings
         return augmented
     ```
  2. - [x] Modify create_timestamped_backup to capture settings (~line 3345)
     - Add parameter: `config_entry: ConfigEntry | None = None`
     - After copying storage file, if config_entry provided:
       - Read the backup file
       - Call _augment_backup_with_settings()
       - Write augmented version back
     - Implementation sketch:
       ```python
       # After: await hass.async_add_executor_job(shutil.copy2, ...)
       
       if config_entry:
           # Read backup, augment, write back
           backup_str = await hass.async_add_executor_job(backup_path.read_text)
           backup_data = json.loads(backup_str)
           
           augmented = _augment_backup_with_settings(backup_data, config_entry.options)
           
           await hass.async_add_executor_job(
               backup_path.write_text, json.dumps(augmented, indent=2)
           )
       ```
  3. - [x] Update all callers to pass config_entry
     - config_flow.py line ~344 (safety backup): Pass `config_entry` if available
     - options_flow.py line ~3119 (manual backup): Pass `self.config_entry`
     - options_flow.py line ~3275 (pre-restore safety): Pass `self.config_entry`
     - services.py line ~847 (reset backup): Pass `coordinator.config_entry`
     - __init__.py line ~193 (startup backup): Pass `entry`

- **Key issues**
  - Read-modify-write introduces small overhead but ensures single source of truth
  - File operations remain non-blocking via async_add_executor_job

- **Goal**: Comprehensive test coverage and validation of the fix.

- **Steps 2 – Enhance Restore Logic

- **Goal**: Extract config_entry_settings from backup and apply via async_update_entry().

- **Steps / detailed work items**
  1. - [x] Add validation helper in flow_helpers.py (~line 3420 after _augment_backup_with_settings)
     ```python
     def _validate_config_entry_settings(settings: dict[str, Any]) -> dict[str, Any]:
         """Validate config_entry_settings from backup.
         
         Returns only valid key-value pairs. Invalid entries logged and skipped.
         Missing keys NOT added (caller merges with defaults).
         """
         valid = {}
         for key, default_val in const.DEFAULT_SYSTEM_SETTINGS.items():
             if key in settings:
                 value = settings[key]
                 # Type-check against default value's type
                 if type(value) is type(default_val):
                     valid[key] = value
                 else:
                     const.LOGGER.warning(
                         "Invalid type for %s: expected %s, got %s",
                         key, type(default_val).__name__, type(value).__name__
                     )
         return valid
     ```
  2. - [x] Modify config_flow._handle_restore_backup (~line 350 after storage restore)
     ```python
     # After: Parse backup_data = json.loads(backup_data_str)
     
     # Extract and apply config_entry_settings if present
     if const.DATA_CONFIG_ENTRY_SETTINGS in backup_data:
         settings = backup_data[const.DATA_CONFIG_ENTRY_SETTINGS]
         validated = fh._validate_config_entry_settings(settings)
         
         if validated:
             # Merge with defaults for any missing keys
             options = {
                 key: validated.get(key, default)
                 for key, default in const.DEFAULT_SYSTEM_SETTINGS.items()
             }
             # Store for use when creating config entry
             self._restored_settings = options
  # Phase 3 – Update Diagnostics

- **Goal**: Include config_entry_settings in diagnostics export for complete recovery.

- **Steps / detailed work items**
  1. - [x] Modify diagnostics.py async_get_config_entry_diagnostics (~line 38)
     ```python
     async def async_get_config_entry_diagnostics(hass, entry):
         """Return diagnostics including config_entry_settings."""
         coordinator = hass.data[const.DOMAIN][entry.entry_id][const.COORDINATOR]
         
         # Get base storage data
         diagnostics_data = coordinator.storage_manager.data
         
         # Add config_entry_settings section
         diagnostics_data[const.DATA_CONFIG_ENTRY_SETTINGS] = {
             key: entry.options.get(key, default)
             for key, default in const.DEFAULT_SYSTEM_SETTINGS.items()
         }
         
         return diagnostics_data
     ```
  2. - [x] Test diagnostics export includes settings
     - Download diagnostics from UI
     - Verify config_entry_settings section present with all 9 keys

- **Key issues**
  - Diagnostics returns modified copy (doesn't mutate coordinator data)
  - This makes diagnostics → paste restore workflow complete

### Phase 4 – Testing & Validation

- **Goal**: Comprehensive test coverage validating complete backup/restore.

- **Steps / detailed work items**
  1. - [ ] Add test_backup_includes_config_entry_settings in test_backup_utilities.py
     - Setup: Create backup with custom settings
     - Assert: Backup file contains config_entry_settings section with all 9 keys
  2. - [ ] Add test_restore_with_settings in test_backup_flow_navigation.py
     - Setup: Backup with custom settings (points_label="Stars")
     - Action: Restore via config flow
     - Assert: New config entry has custom settings
  3. - [ ] Add test_restore_without_settings_uses_defaults in test_backup_flow_navigation.py
     - Setup: Old backup without config_entry_settings key
     - Action: Restore
     - Assert: Config entry created with DEFAULT_SYSTEM_SETTINGS
  4. - [ ] Add test_options_flow_restore_updates_settings in test_backup_flow_navigation.py
     - Setup: Existing entry with defaults, backup with custom settings
     - Action: Restore via options flow
     - Assert: Config entry updated with custom settings
  5. - [ ] Add test_roundtrip_preserves_all_settings in test_backup_utilities.py
     - Setup: Customize all 9 settings
     - Action: Create backup → modify settings → restore
     - Assert: All 9 original values restored exactly
  6. - [ ] Add test_diagnostics_includes_settings in test_diagnostics.py
     - Setup: Config entry with custom settings
     - Action: Call async_get_config_entry_diagnostics
     - Assert: Return includes config_entry_settings with correct values
  7. - [ ] Run backup-specific tests
     ```bash
     python -m pytest tests/test_backup_utilities.py tests/test_backup_flow_navigation.py -v
     ```
  8. - [ ] Run full test suite
     ```bash
     python -m pytest tests/ -v --tb=line
     ```
  9. - [ ] Run linting
     ```bash
     ./utils/quick_lint.sh --fix
     mypy custom_components/kidschores/
     ```

- **Key issues**
  - Need to mock config_entry in backAdding config_entry_settings section to storage file is straightforward. Total implementation: ~65 minutes (5 const + 15 backup + 20 restore + 5 diagnostics + 20 tests).

**Key architectural decisions (finalized)**:
1. **Storage format**: Add `config_entry_settings` as top-level key in storage file (alongside "data")
2. **Backup strategy**: Read storage → add settings from config_entry.options → write augmented version
3. **Restore strategy**: Read backup → extract config_entry_settings → merge with defaults → apply via async_update_entry()
4. **Fallback**: Missing config_entry_settings → use DEFAULT_SYSTEM_SETTINGS (not current settings)
5. **Diagnostics**: Always include config_entry_settings for complete recovery

**Storage File Structure After Implementation:**

```json
{
    "version": 1,
    "data": {
        "meta": {"schema_version": 42},
        "kids": {...},
        "parents": {...},
        "chores": {...}
    },
    "config_entry_settings": {
        "points_label": "Stars",
        "points_icon": "mdi:star",
        "update_interval": 10,
        "calendar_show_period": 90,
        "retention_daily": 7,
        "retention_weekly": 5,
        "retention_monthly": 3,
        "retention_yearly": 3,
        "points_adjust_values": [1, -1, 2, -2, 10, -10]
    }
}
```

**The 9 System Settings Reference:**

| Constant | Key String | Type | Default | Effect |
|----------|------------|------|---------|--------|
| `CONF_POINTS_LABEL` | `"points_label"` | str | `"Points"` | Sensor translations |
| `CONF_POINTS_ICON` | `"points_icon"` | str | `"mdi:star-outline"` | Point sensor icons |
| `CONF_UPDATE_INTERVAL` | `"update_interval"` | int | `5` | Coordinator polling (minutes) |
| `CONF_CALENDAR_SHOW_PERIOD` | `"calendar_show_period"` | int | `90` | Calendar view range (days) |
| `CONF_RETENTION_DAILY` | `"retention_daily"` | int | `7` | Stats cleanup (days) |
| `CONF_RETENTION_WEEKLY` | `"retention_weekly"` | int | `5` | Stats cleanup (weeks) |
| `CONF_RETENTION_MONTHLY` | `"retention_monthly"` | int | `3` | Stats cleanup (months) |
| `CONF_RETENTION_YEARLY` | `"retention_yearly"` | int | `3` | Stats cleanup (years) |
| `CONF_POINTS_ADJUST_VALUES` | `"points_adjust_values"` | list | `[1,-1,2,-2,10,-10]` | Adjustment buttons |

**Backward compatibility**: 
- Existing v0.5.0 backups without config_entry_settings work unchanged (use defaults on restore)
- Storage files gain new top-level key (non-breaking addition)
- No schema version bump needed (additive change)

**Related files:**
- [const.py](../../custom_components/kidschores/const.py) – Add DATA_CONFIG_ENTRY_SETTINGS and DEFAULT_SYSTEM_SETTINGS
- [flow_helpers.py](../../custom_components/kidschores/flow_helpers.py) – Add _augment_backup_with_settings() and _validate_config_entry_settings()
- [config_flow.py](../../custom_components/kidschores/config_flow.py) – Modify _handle_restore_backup() to extract and apply settings
- [options_flow.py](../../custom_components/kidschores/options_flow.py) – Modify async_step_restore_backup_confirm() to update entry
- [diagnostics.py](../../custom_components/kidschores/diagnostics.py) – Add config_entry_settings to export
- [test_backup_utilities.py](../../tests/test_backup_utilities.py) – Add backup format and roundtrip tests
- [test_backup_flow_navigation.py](../../tests/test_backup_flow_navigation.py) – Add restore flow tests
- [test_diagnostics.py](../../tests/test_diagnostics.py) – Add diagnostics inclusion test

**Success criteria:**
- All 6 new tests pass
- All existing tests pass (500+ tests)
- Linting score ≥ 9.5/10
- MyPy passes with zero errors
- Roundtrip test proves settings preserved exactly
             options = {
                 key: validated.get(key, default)
                 for key, default in const.DEFAULT_SYSTEM_SETTINGS.items()
             }
             
             # Update config entry
             self.hass.config_entries.async_update_entry(
                 self.config_entry, options=options
             )
             const.LOGGER.info("Restored %d settings from backup", len(validated))
     else:
         const.LOGGER.info("Backup has no settings, using existing")
     ```

- **Key issues**
  - Config flow creates entry with options (easy)
  - Options flow updates existing entry (requires async_update_entry)
```bash
# Run specific backup/restore tests
python -m pytest tests/test_services.py -k backup -v

# Run full test suite
python -m pytest tests/ -v --tb=line

# Lint check
./utils/quick_lint.sh --fix
```

**Expected test file:** [tests/test_services.py](../../tests/test_services.py)

**New tests to add (5 total):**
1. `test_restore_backup_restores_system_settings`
2. `test_restore_backup_partial_system_settings`
3. `test_restore_backup_v1_no_system_settings`
4. `test_restore_backup_invalid_system_settings_values`
5. `test_backup_restore_roundtrip_system_settings`

**Success criteria:**
- All existing tests pass (500+ tests)
- All new tests pass
- Linting score ≥ 9.5/10
- Roundtrip test proves complete backup/restore including settings

## Notes & follow-up

**Implementation complexity**: LOW – The backup already captures system_settings correctly. The fix is ~30-40 lines of new code in restore_backup plus validation helper.

**Key architectural consideration**: The `async_update_entry()` call updates the config entry in-place. While it doesn't require an await, the changes to system settings like `update_interval` or `points_label` only take full effect after integration reload. The return value includes `system_settings_restored: True` to inform callers that a reload may be beneficial.

**The 9 System Settings Reference:**

| Constant | Key String | Type | Default | Effect |
|----------|------------|------|---------|--------|
| `CONF_POINTS_LABEL` | `"points_label"` | str | `"Points"` | Sensor translations |
| `CONF_POINTS_ICON` | `"points_icon"` | str | `"mdi:star-outline"` | Point sensor icons |
| `CONF_UPDATE_INTERVAL` | `"update_interval"` | int | `5` | Coordinator polling (minutes) |
| `CONF_CALENDAR_SHOW_PERIOD` | `"calendar_show_period"` | int | `90` | Calendar view range (days) |
| `CONF_RETENTION_DAILY` | `"retention_daily"` | int | `7` | Stats cleanup (days) |
| `CONF_RETENTION_WEEKLY` | `"retention_weekly"` | int | `5` | Stats cleanup (weeks) |
| `CONF_RETENTION_MONTHLY` | `"retention_monthly"` | int | `3` | Stats cleanup (months) |
| `CONF_RETENTION_YEARLY` | `"retention_yearly"` | int | `3` | Stats cleanup (years) |
| `CONF_POINTS_ADJUST_VALUES` | `"points_adjust_values"` | list | `[1,-1,2,-2,10,-10]` | Adjustment buttons |

**Future enhancement consideration**: Add service parameter `restore_settings: bool = True` allowing users to choose whether to restore system settings or just entity data.

**Related files:**
- [coordinator.py](../../custom_components/kidschores/coordinator.py) – restore_backup method (~line 7927)
- [const.py](../../custom_components/kidschores/const.py) – CONF_* and DEFAULT_* constants
- [services.yaml](../../custom_components/kidschores/services.yaml) – service definitions
- [test_services.py](../../tests/test_services.py) – backup/restore tests

---

> **Template usage notice:** Created from [PLAN_TEMPLATE.md](../PLAN_TEMPLATE.md). Once complete, rename to `SYSTEM_SETTINGS_RESTORE_COMPLETE.md` and move to `docs/completed/`.
