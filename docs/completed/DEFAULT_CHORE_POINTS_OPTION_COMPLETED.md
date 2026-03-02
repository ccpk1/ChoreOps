# Initiative plan: configurable default chore points

## Initiative snapshot

- **Name / Code**: Configurable default chore points (`CONF_DEFAULT_CHORE_POINTS`)
- **Target release / milestone**: v0.5.x next minor patch
- **Owner / driver(s)**: ChoreOps maintainers
- **Status**: Complete

## Summary & immediate steps

| Phase / Step                    | Description                                                          | % complete | Quick notes                                     |
| ------------------------------- | -------------------------------------------------------------------- | ---------: | ----------------------------------------------- |
| Phase 1 – Contracts & constants | Add system-setting contract for default chore points                 |       100% | Constants/defaults/translations wired           |
| Phase 2 – Flow wiring           | Surface field in config/options flows and persist in options         |       100% | Setup/reconfigure/options paths updated         |
| Phase 3 – Runtime adoption      | Use configured value where chore defaults currently fall back to `5` |       100% | Manager + chore form fallbacks updated          |
| Phase 4 – Tests & docs          | Add/adjust tests + docs for system settings count and behavior       |       100% | Targeted tests + docs updates complete          |

1. **Key objective** – Allow users to set a global default points-per-chore value (instead of fixed `5`) from points/general system settings flows.
2. **Summary of recent work** – Implemented end-to-end default chore points support across constants, flows, runtime fallbacks, migration compatibility, translations, tests, and wiki docs.
3. **Next steps (short term)** – Archived to `docs/completed`.
4. **Risks / blockers** – None open for this plan scope.
5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Global setting applies to **default value prefill/fallback** only; existing chores keep their stored `default_points` unless explicitly edited.
     - Setting lives in `config_entry.options` (system settings), not `.storage/choreops/choreops_data`.
     - Chore runtime fallback order should be: `chore.default_points` → `config_entry.options[default_chore_points]` → hard fallback `const.DEFAULT_POINTS`.
  - **Completion confirmation**: `[x]` All follow-up items completed before owner sign-off.

## Tracking expectations

- **Summary upkeep**: Update summary percentages and quick notes after each merged phase.
- **Detailed tracking**: Keep implementation notes in phase sections below.

## Detailed phase tracking

### Phase 1 – Contracts & constants

- **Goal**: Introduce a first-class system setting for default chore points and ensure it is recognized by shared settings maps.
- **Steps / detailed work items**
  - [x] Add new options key and flow field constants in [custom_components/choreops/const.py](../../custom_components/choreops/const.py) around `CONF_*`/`CFOF_SYSTEM_INPUT_*` groups (near lines ~782-820).
  - [x] Add default constant(s) in [custom_components/choreops/const.py](../../custom_components/choreops/const.py) defaults block (near lines ~1688-1715), and include in `DEFAULT_SYSTEM_SETTINGS`.
  - [x] Add/confirm error key constants (likely `CFOP_ERROR_*` + `TRANS_KEY_CFOF_*`) in [custom_components/choreops/const.py](../../custom_components/choreops/const.py) error/translation section (near lines ~3119-3335).
  - [x] Update English translation labels/descriptions for general/options/reconfigure forms in [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json) under `manage_general_options` and any shared settings sections (near lines ~1614-1642).
  - [x] Verify backup/diagnostics settings contract includes the new key through `DEFAULT_SYSTEM_SETTINGS` consumers in [custom_components/choreops/helpers/backup_helpers.py](../../custom_components/choreops/helpers/backup_helpers.py) (near lines ~35-85) and [custom_components/choreops/diagnostics.py](../../custom_components/choreops/diagnostics.py) (near lines ~34-42).
- **Key issues**
  - Keep naming aligned with existing system-setting pattern (`CONF_*`, `CFOF_SYSTEM_INPUT_*`).
  - Translation key naming must stay consistent with existing `TRANS_KEY_CFOF_*` conventions.

### Phase 2 – Flow wiring (config + options)

- **Goal**: Expose and persist configurable default chore points in all relevant settings UX surfaces.
- **Steps / detailed work items**
  - [x] Add field to general options schema builder in [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py) `build_general_options_schema` (near lines ~3058-3138), with numeric validation (`cv.positive_int` or numeric selector as required).
  - [x] Persist new field in options general step handler in [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py) `async_step_manage_general_options` (near lines ~4788-4899).
  - [x] Include field in consolidated reconfigure schema/data in [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py) for `build_all_system_settings_schema`, `validate_all_system_settings`, and `build_all_system_settings_data` (near lines ~3203-3440).
  - [x] Ensure config flow reconfigure path picks up the new setting via existing helper plumbing in [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py) (near lines ~1583-1638).
  - [x] Decide whether `async_step_points_label` should become a broader points step (label/icon + default chore points) in [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py) (near lines ~575-596) and [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py) `build_points_schema`/`build_points_data` (near lines ~181-216).
- **Key issues**
  - Current architecture/docs say “9 settings,” but active options flow already handles additional settings (`show_legacy_entities`, `kiosk_mode`, backup retention); avoid adding further drift in wording.
  - Keep UX minimal: one numeric field, no extra menu/step proliferation.

### Phase 3 – Runtime adoption in chore defaults

- **Goal**: Make the configured setting actually drive default points behavior where current fallback is fixed to `const.DEFAULT_POINTS`.
- **Steps / detailed work items**
  - [x] Update chore form default prefill in [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py) `build_chore_schema` fallback for `CFOF_CHORES_INPUT_DEFAULT_POINTS` (near lines ~747-749) to use settings-driven default when available.
  - [x] Update options flow chore add/edit schema defaults (call-site feed) in [custom_components/choreops/options_flow.py](../../custom_components/choreops/options_flow.py) where chore forms are built so the new option is passed into default maps.
  - [x] Update config flow chore creation path so first-run created chores inherit configured default when user does not override per chore in [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py) (chore creation loop and `self._data` handoff near lines ~930-1100 and create-entry near ~1550).
  - [x] Update runtime fallback usages that currently use `const.DEFAULT_POINTS` (for missing `default_points`) in [custom_components/choreops/engines/chore_engine.py](../../custom_components/choreops/engines/chore_engine.py) (near line ~1090) and [custom_components/choreops/managers/chore_manager.py](../../custom_components/choreops/managers/chore_manager.py) (near line ~853), sourcing config options through coordinator context where appropriate.
  - [x] Keep migration behavior backward compatible in [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py) options map (near lines ~1462-1490) so restored/migrated entries get the new setting default.
- **Key issues**
  - Engine code may not always have direct config-entry access; if needed, apply settings-driven fallback at manager/flow boundary and keep engine pure.
  - Must avoid retroactively rewriting existing chore records unless explicitly requested.

### Phase 4 – Tests, docs, and quality gates

- **Goal**: Lock behavior with targeted tests, then align architecture/docs wording.
- **Steps / detailed work items**
  - [x] Extend points helper tests in [tests/test_points_helpers.py](../../tests/test_points_helpers.py) for schema/data/validation coverage with default-chore-points field.
  - [x] Update options-flow general settings test payloads in [tests/test_kiosk_mode_buttons.py](../../tests/test_kiosk_mode_buttons.py) (near lines ~150-183) to include/assert the new option persists.
  - [x] Update fresh-start config flow assertions in [tests/test_config_flow_fresh_start.py](../../tests/test_config_flow_fresh_start.py) (e.g., around lines ~162-164 and similar repeated blocks) to validate default option presence.
  - [x] Add diagnostics/backup settings assertions for new key in [tests/test_diagnostics.py](../../tests/test_diagnostics.py) (near lines ~79-93) and relevant backup settings tests.
  - [x] Update architecture docs in [docs/ARCHITECTURE.md](../ARCHITECTURE.md) system settings table/count wording (section “System Settings (config_entry.options)”, near lines ~170-245).
  - [x] Update any user-facing settings docs in [README.md](../../README.md) or wiki references if they list configurable points settings.
- **Key issues**
  - Many tests hardcode settings payloads; broad but mechanical updates likely required.
  - Keep assertions focused on this feature to avoid unrelated churn.

## Testing & validation

- Targeted tests first:
  - `python -m pytest tests/test_points_helpers.py -v --tb=line`
  - `python -m pytest tests/test_kiosk_mode_buttons.py -v --tb=line`
  - `python -m pytest tests/test_config_flow_fresh_start.py -v --tb=line`
  - `python -m pytest tests/test_diagnostics.py -v --tb=line`
- Then integration quality gates:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/ -v --tb=line`

## Notes & follow-up

- **Schema migration note**: No `.storage/choreops/choreops_data` shape change is required, so no `meta.schema_version` increment is expected.
- **Compatibility note**: Backups and diagnostics should automatically carry the new setting once `DEFAULT_SYSTEM_SETTINGS` is updated; confirm with tests.
- **Potential follow-up**: Optional bulk-action to apply new global default to existing chores could be a separate initiative (not in this scope).

## Builder handoff package

- Supporting handoff doc: [DEFAULT_CHORE_POINTS_OPTION_SUP_BUILDER_HANDOFF.md](DEFAULT_CHORE_POINTS_OPTION_SUP_BUILDER_HANDOFF.md)

## Builder handoff checklist

- [x] Scope is locked to configurable default chore points in settings + fallback behavior.
- [x] Decision is locked: existing chores are not bulk-mutated.
- [x] Storage schema impact reviewed: no `.storage` schema change expected.
- [x] Backup/restore/diagnostics settings-contract impact identified.
- [x] Validation gates are specified (`quick_lint`, `mypy`, targeted pytest, full pytest).
- [x] Required handback payload from builder is defined.
