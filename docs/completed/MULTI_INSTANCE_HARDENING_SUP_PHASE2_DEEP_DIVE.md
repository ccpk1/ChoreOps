# Phase 2 deep dive: Storage and backup namespacing (MIR-2026Q1)

## Purpose

This document captures concrete action items for Phase 2 and proposes an implementation approach that keeps changes minimal, safe, and entry-isolated.

## Current-state findings

### 1) Storage key is still single-instance in setup paths

- `custom_components/choreops/__init__.py` creates store with `ChoreOpsStore(hass, const.STORAGE_KEY)`.
- `custom_components/choreops/store.py` already supports a `storage_key` parameter, but most call sites still use defaults.

**Impact**: Multiple config entries can still point to a shared active storage payload.

### 2) Backup naming/discovery is tied to one key

- `custom_components/choreops/helpers/backup_helpers.py` creates and scans backups using `const.STORAGE_KEY` prefix.
- Current retention cleanup groups by tag, but not by entry storage key.

**Impact**: Backups can be discovered/cleaned across entries instead of only the current entry.

### 3) Options flow backup/restore logic uses fixed file path assumptions

- `custom_components/choreops/options_flow.py` uses direct paths like `.storage/<const.STORAGE_KEY>` in restore/start-fresh paths.
- Several flows instantiate `ChoreOpsStore(self.hass)` without explicit entry scope.

**Impact**: Restore/start-fresh operations can target the wrong active file when multiple entries exist.

### 4) Remove-entry ownership relies on runtime_data presence

- `custom_components/choreops/__init__.py` `async_remove_entry` exits early if `runtime_data` is missing.
- Storage deletion ownership should not depend on runtime_data.

**Impact**: Removal can miss cleanup or rely on loaded-state assumptions.

### 5) Diagnostics do not expose storage scope metadata

- `custom_components/choreops/diagnostics.py` returns storage data but no explicit storage key/path metadata.

**Impact**: Support and restore workflows have less visibility in multi-entry environments.

## Proposed approach (recommended)

### Guiding decision

Use **entry-scoped storage keys** while keeping the same storage directory.

- Keep directory: `.storage/choreops/`
- New active key pattern: `choreops_data_<entry_id>`
- Keep existing backup suffix/tag pattern but prefix with the scoped key.

This is the smallest change that isolates entries and minimizes migration risk.

## Practical usability contract (restore, reinstall, new instance)

Phase 2 must preserve isolation **without** making recovery harder. The contract below keeps both goals.

### Contract requirements

1. **Routine restore (same entry)**

- Default backup list should show backups for the current entry first.
- One-click restore should continue to work as it does today.

2. **Reinstall restore (new entry_id on same HA)**

- Restore UI must include a way to view all valid ChoreOps backups, not only current-entry backups.
- Selecting an older backup must restore into the **current** entry storage key.

3. **Migration to a new Home Assistant instance**

- Backup files copied from another HA instance must be accepted if JSON is valid.
- Restore process must rehydrate data into the current entry storage key regardless of source key.

4. **Paste JSON path remains universal fallback**

- Paste/import flow remains fully supported and key-agnostic.
- If no matching scoped backup is found, users can still recover via pasted JSON.

### Implementation notes for portability

- Add backup metadata fields (non-breaking) when creating backups:
  - `source_entry_id`
  - `source_storage_key`
  - `source_entry_title` (optional)
- During restore, always write recovered data to the **current** entry storage key.
- In selection UI, label backups clearly:
  - `Current Entry`
  - `Other Entry (importable)`

## Backup selector readability (important UX)

Longer scoped filenames should **not** be the primary thing users read in dropdowns.

### Labeling rule

Use a short, human-first label format:

- `YYYY-MM-DD HH:MM • <tag> • <scope>`
  - Example: `2026-02-25 21:43 • Manual • Current Entry`
  - Example: `2026-02-20 08:11 • Recovery • Other Entry`

Keep raw filename hidden from the main label and expose it only as secondary detail
(description placeholder, debug log, or advanced view text).

### Sorting and grouping

- Default sort: newest first (timestamp desc)
- Group 1: Current Entry
- Group 2: Other Entry (importable)
- Always keep `Cancel`, `Use current active`, and `Paste JSON` at fixed top/bottom positions

### Truncation policy

- Never truncate date/time or tag
- If needed, truncate only the scope tail or title text
- Do not rely on filename length for readability

### Implementation target

In `options_flow.py`, build selector options from structured metadata (timestamp/tag/scope),
not directly from filename strings. Continue to map the selected label back to the true filename internally.

### Why this addresses the concern

- Entry isolation is preserved in steady state.
- Reinstall and new-instance migration remain straightforward.
- Users are not blocked by old entry IDs embedded in backup names.

### Why this approach

- Minimal churn: no new directory topology.
- Existing `ChoreOpsStore` constructor already supports key injection.
- Backup helper logic can remain filename-based with a scoped prefix.
- Easier rollback and testing vs introducing per-entry subdirectories.

## Action plan (implementation order)

### Step 1: Canonical storage-key derivation

Add one helper for deterministic scoped key creation and use it everywhere.

**Changes**

- Add helper in `custom_components/choreops/helpers/storage_helpers.py`:
  - `get_entry_storage_key(entry_id: str) -> str`
- Add optional helper for readability:
  - `get_entry_storage_key_from_entry(config_entry) -> str`

**Notes**

- Keep legacy `const.STORAGE_KEY` as base prefix only.
- No behavior flags; scoped key is the default Phase 2 baseline.

### Step 2: Wire scoped key into setup and removal paths

**Changes**

- `custom_components/choreops/__init__.py`
  - `async_setup_entry`: build store with entry-scoped key.
  - `async_remove_entry`: derive scoped key from entry and delete only owned storage, even if `runtime_data` is unavailable.

### Step 3: Namespace backup helper API by storage key

**Changes**

- `custom_components/choreops/helpers/backup_helpers.py`
  - `create_timestamped_backup(..., storage_key: str | None = None)`
  - `discover_backups(..., storage_key: str | None = None)`
  - `cleanup_old_backups(..., storage_key: str | None = None)`
- If `storage_key` omitted, resolve from `store` when possible.
- Prefix matching must use the scoped storage key.

**Behavior**

- Retention remains per-tag, but now per `(storage_key, tag)` scope.
- No cross-entry cleanup.
- Restore APIs still allow import from non-current storage-key backups.

### Step 4: Scope options-flow backup actions to current entry

**Changes**

- `custom_components/choreops/options_flow.py`
  - Replace direct `.storage/<const.STORAGE_KEY>` paths with entry-scoped storage path resolution.
  - Replace `ChoreOpsStore(self.hass)` with scoped store creation for all backup/restore/start-fresh paths.
  - Pass scoped `storage_key` into `backup_helpers` discover/create/cleanup.
  - Add restore mode that can include `all importable backups` for reinstall/new-instance recovery.

### Step 5: Add diagnostics storage metadata

**Changes**

- `custom_components/choreops/diagnostics.py`
  - Add `storage_context` object:
    - `entry_id`
    - `storage_key`
    - `storage_path`

## Validation plan for Phase 2

### Targeted tests first

1. New test module for backup isolation:
   - two entries with different storage keys
   - discover/cleanup only returns own entry backups
2. Options flow restore/start-fresh tests scoped by entry
3. Remove-entry test verifies only owning storage file is removed
4. Diagnostics test verifies storage_context fields

### Quality gates

- `./utils/quick_lint.sh --fix`
- `mypy custom_components/choreops/`
- `python -m pytest tests/ -v --tb=line` (or targeted modules first, then full)

## Risks and mitigations

- **Risk**: Missing one fixed-path call site in options flow.
  - **Mitigation**: Grep sweep for `const.STORAGE_KEY` + `.storage/` path patterns before finalization.
- **Risk**: Backup compatibility confusion between old and new prefixes.
  - **Mitigation**: Keep parser tolerant, but discovery defaults to current scoped key.
- **Risk**: Runtime-data missing in remove-entry.
  - **Mitigation**: Reconstruct scoped store from config entry directly.

## Recommended execution split

- **Phase 2A**: scoped storage key helper + setup/remove-entry wiring
- **Phase 2B**: backup helper namespacing + options-flow scoping
- **Phase 2C**: diagnostics metadata + isolation tests + gates

This split keeps each PR/review chunk focused and lowers regression risk.
