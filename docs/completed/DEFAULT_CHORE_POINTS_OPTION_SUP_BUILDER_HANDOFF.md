# Default chore points option - Builder handoff

---

status: READY_FOR_HANDOFF
owner: Strategist Agent
created: 2026-03-02
parent_plan: DEFAULT_CHORE_POINTS_OPTION_COMPLETED.md
handoff_from: ChoreOps Strategist
handoff_to: ChoreOps Builder
phase_focus: Phase 1-4 end-to-end implementation and validation

---

## Handoff button

[HANDOFF_TO_BUILDER_DEFAULT_CHORE_POINTS_OPTION](DEFAULT_CHORE_POINTS_OPTION_IN-PROCESS.md)

## Handoff objective

Implement configurable default points per chore in system settings so users can override the fixed `5` fallback, while preserving backward compatibility and current storage architecture.

Required behavior:

1. Add a system setting for default chore points in config/options contracts.
2. Surface and persist it in General Options and Reconfigure flows.
3. Use it as fallback/prefill for chore default points where the code currently falls back to `const.DEFAULT_POINTS`.
4. Keep existing chore records unchanged unless the user edits those chores.
5. Ensure backup/restore/diagnostics include the new key through `DEFAULT_SYSTEM_SETTINGS` contract.

## Scope for this handoff

### In scope

- Constants and contract updates:
  - [custom_components/choreops/const.py](../../custom_components/choreops/const.py)
- Flow helper updates:
  - [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py)
- Flow execution updates:
  - [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py)
  - [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py)
- Runtime fallback updates:
  - [custom_components/choreops/managers/chore_manager.py](../../custom_components/choreops/managers/chore_manager.py)
  - [custom_components/choreops/engines/chore_engine.py](../../custom_components/choreops/engines/chore_engine.py)
- Backup/diagnostics/migration settings maps:
  - [custom_components/choreops/helpers/backup_helpers.py](../../custom_components/choreops/helpers/backup_helpers.py)
  - [custom_components/choreops/diagnostics.py](../../custom_components/choreops/diagnostics.py)
  - [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py)
- Tests and docs:
  - [tests/test_points_helpers.py](../../tests/test_points_helpers.py)
  - [tests/test_kiosk_mode_buttons.py](../../tests/test_kiosk_mode_buttons.py)
  - [tests/test_config_flow_fresh_start.py](../../tests/test_config_flow_fresh_start.py)
  - [tests/test_diagnostics.py](../../tests/test_diagnostics.py)
  - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)

### Out of scope

- Bulk migration to rewrite all existing chore records.
- New service actions/UI pages for global points migration.
- Any unrelated refactors in reward/badge/challenge systems.

## Hard constraints

- Follow manager-owned write model and existing storage-only architecture.
- Do not introduce `.storage` schema changes; no schema bump expected.
- Keep translations and constants pattern-compliant (`CONF_*`, `CFOF_SYSTEM_INPUT_*`, `TRANS_KEY_CFOF_*`).
- Avoid compatibility shims unless needed for existing backups/options contracts.

## Execution checklist (builder)

### Package A - Contracts and settings map

- [ ] Add `CONF_DEFAULT_CHORE_POINTS` and matching `CFOF_SYSTEM_INPUT_DEFAULT_CHORE_POINTS` in [custom_components/choreops/const.py](../../custom_components/choreops/const.py).
- [ ] Add default constant (settings-level default value) and include in `DEFAULT_SYSTEM_SETTINGS` in [custom_components/choreops/const.py](../../custom_components/choreops/const.py).
- [ ] Add translation key constants needed for validation errors in [custom_components/choreops/const.py](../../custom_components/choreops/const.py).
- [ ] Add English translation field label/description under `manage_general_options` and any consolidated settings sections in [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json).

### Package B - Config/options flow wiring

- [ ] Add field to `build_general_options_schema` and parse/save path in [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py) and [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py).
- [ ] Add field to consolidated reconfigure helpers (`build_all_system_settings_schema`, `validate_all_system_settings`, `build_all_system_settings_data`) in [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py).
- [ ] Ensure `async_step_reconfigure` in [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py) renders and persists the field through helper contracts.
- [ ] Decide and implement whether the initial points step includes this field (preferred: yes, in existing points step without adding extra steps).

### Package C - Runtime and default-point consumption

- [ ] Update chore add/edit default prefill behavior to consume configured setting where fallback currently uses `const.DEFAULT_POINTS`.
- [ ] Update approval/points calculation fallback chain where missing chore default points currently uses hardcoded constant:
  - [custom_components/choreops/managers/chore_manager.py](../../custom_components/choreops/managers/chore_manager.py)
  - [custom_components/choreops/engines/chore_engine.py](../../custom_components/choreops/engines/chore_engine.py)
- [ ] Keep final fallback to `const.DEFAULT_POINTS` as safety net.

### Package D - Backup/restore/diagnostics and migration compatibility

- [ ] Ensure new setting participates in backup augment/validate via `DEFAULT_SYSTEM_SETTINGS` in [custom_components/choreops/helpers/backup_helpers.py](../../custom_components/choreops/helpers/backup_helpers.py).
- [ ] Ensure diagnostics `config_entry_settings` includes the key in [custom_components/choreops/diagnostics.py](../../custom_components/choreops/diagnostics.py).
- [ ] Ensure migration options-map includes the key default in [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py).

### Package E - Tests and docs

- [ ] Extend points helper tests in [tests/test_points_helpers.py](../../tests/test_points_helpers.py).
- [ ] Update general options flow test payload/assertions in [tests/test_kiosk_mode_buttons.py](../../tests/test_kiosk_mode_buttons.py).
- [ ] Update fresh-start config flow option assertions in [tests/test_config_flow_fresh_start.py](../../tests/test_config_flow_fresh_start.py).
- [ ] Update diagnostics options expectation in [tests/test_diagnostics.py](../../tests/test_diagnostics.py).
- [ ] Update system settings count/wording in [docs/ARCHITECTURE.md](../ARCHITECTURE.md).

## Acceptance criteria

- Users can set default chore points in options/configure flow.
- New and fallback chore defaults use configured value instead of fixed `5`.
- Existing chores preserve existing stored `default_points` values.
- Backup/restore/diagnostics include and round-trip the new setting key.
- All targeted tests pass and no regressions in quality gates.

## Validation gates (required)

- `./utils/quick_lint.sh --fix`
- `mypy custom_components/choreops/`
- `python -m pytest tests/test_points_helpers.py tests/test_kiosk_mode_buttons.py tests/test_config_flow_fresh_start.py tests/test_diagnostics.py -v --tb=line`
- `python -m pytest tests/ -v --tb=line`

## Required handback payload from builder

1. Changed-files list grouped by Package A-E.
2. Short summary of fallback chain implementation locations.
3. Test output summary for targeted tests and full suite.
4. Confirmation that no storage schema version bump was required.
5. Parent plan status update in [docs/in-process/DEFAULT_CHORE_POINTS_OPTION_IN-PROCESS.md](DEFAULT_CHORE_POINTS_OPTION_IN-PROCESS.md).
