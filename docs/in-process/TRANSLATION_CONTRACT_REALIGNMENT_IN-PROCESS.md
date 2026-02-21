# Initiative Plan: Translation contract realignment (runtime-safe)

## Initiative snapshot

- **Name / Code**: Translation Contract Realignment (`CHOREOPS-I18N-CONTRACT-001`)
- **Target release / milestone**: v0.5.0-beta5 hardening (pre-release gate)
- **Owner / driver(s)**: Integration maintainers + architecture owner
- **Status**: Phase 1-3 complete for active wave; Phase 4 gate hardening pending

## Why this plan exists

A compatibility audit found that translation/runtime contract safety must be handled as a lockstep program gate (not isolated text replacement):

- Runtime constants and flow step IDs include transitional legacy key references for many surfaces.
- `en.json` policy and key IDs must stay explicitly synchronized with runtime references until a deliberate terminal cutover wave is approved.
- This gate prevents runtime fallback/missing translation regressions during rebrand work.

> Note: Current baseline and sequencing authority are tracked in `REBRAND_ROLEMODEL_CLOSEOUT_IN-PROCESS.md`.
> Terminology boundaries are defined in `REBRAND_ROLEMODEL_CLOSEOUT_SUP_TERMINOLOGY_POLICY.md`.

## Summary table

| Phase                              | Description                                     | %   | Quick notes                               |
| ---------------------------------- | ----------------------------------------------- | --- | ----------------------------------------- |
| Phase 1 – Contract inventory       | Build authoritative runtime→translation key map | 100%  | Inventory published with evidence artifact |
| Phase 2 – Key parity verification  | Verify runtime-consumed keys are retained in `en.json` | 100%  | Priority runtime keys verified present     |
| Phase 3 – Canonical migration path | Introduce canonical key path safely             | 100%  | Policy-A deferral recorded; no unsynced key-ID migration |
| Phase 4 – Gate hardening           | Add automated parity checks to CI/local gates   | 0%  | Block recurrence                          |

## Phase details

### Phase 1 – Contract inventory

**Goal**: Produce one canonical map of all translation keys currently consumed by runtime.

- [x] Generate runtime key inventory from constants and flow step IDs
  - Files: `custom_components/choreops/const.py`, `config_flow.py`, `options_flow.py`, `services.py`, `button.py`, `sensor.py`, `notification_action_handler.py`
  - Include: `config.step.*`, `options.step.*`, `selector.*`, `services.*`, `exceptions.*`, notification custom keys.
- [x] Build current `en.json` flattened key inventory and diff against runtime inventory
  - File: `custom_components/choreops/translations/en.json`
- [x] Publish mismatch artifact
  - File: `docs/in-process/TRANSLATION_CONTRACT_REALIGNMENT_SUP_MISMATCH_INVENTORY.md`

**Key issues**:

- Missing runtime keys are release-blocking.
- Renamed-only keys without runtime references are potential future contract keys, not immediate replacements.

### Phase 2 – Key parity verification

**Goal**: Confirm current runtime remains fully translatable before further naming migrations.

- [x] Verify all runtime-required legacy key IDs consumed by current runtime are present in `en.json`
  - File: `custom_components/choreops/translations/en.json`
  - Priority keys include: `kid_count`, `kids`, `add_kid`, `edit_kid`, `delete_kid`, `invalid_kid`, `invalid_parent`, `kid_not_found_by_name`, `parent_not_found_by_name`, `notif_message_data_reset_kid`, `dashboard_kid_selection`, `per_kid`.
- [x] Keep canonical wording in values where acceptable, but **do not** remove runtime key IDs in this phase.
- [x] Validate with runtime key parity script and focused flow/service smoke checks.

**Key issues**:

- This is contract stabilization, not vocabulary completion.
- Do not do broad key renaming in this phase.

### Phase 3 – Canonical migration path (planned, same-wave only)

**Goal**: Move to canonical assignee/approver key IDs only when runtime is changed in lockstep.

- [x] Record active-wave lockstep decision for Policy A
  - Keep legacy key IDs authoritative in this wave; do not perform translation-key-only migration.
- [x] Verify no unsynced key-ID migration was introduced in this wave
  - Evidence: `TRANSLATION_CONTRACT_REALIGNMENT_SUP_MISMATCH_INVENTORY.md`
- [x] Defer canonical key-ID cutover to a dedicated lockstep runtime+translation batch
  - Scope remains explicitly gated by this plan before compatibility key removal.

**Key issues**:

- No translation-key-only migrations.
- Requires deterministic test and translation parity evidence in the same batch.

### Phase 4 – Gate hardening

**Goal**: Prevent any future find/replace drift.

- [ ] Add translation contract parity check to boundary/quality gate
  - File: `utils/check_boundaries.py` (or dedicated script under `utils/`)
- [ ] Fail on runtime key missing in `en.json`.
- [ ] Add optional warning/fail mode for orphan key growth beyond approved baseline.
- [ ] Document the gate and operator workflow
  - Files: `docs/DEVELOPMENT_STANDARDS.md`, `docs/RELEASE_CHECKLIST.md`

**Key issues**:

- Gate should be strict for missing runtime keys, configurable for orphan cleanups.

## Validation commands (execution phase)

- `./utils/quick_lint.sh --fix`
- `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
- `python -m pytest tests/test_config_flow_fresh_start.py tests/test_options_flow_entity_crud.py tests/test_ha_user_id_options_flow.py -v --tb=line`
- `python -m pytest tests/test_chore_services.py tests/test_reward_services.py -v --tb=line`

## Relationship to active plans

- **CHOREOPS-ARCH-UNIFY-003** (`CHOREOPS_DATA_MODEL_UNIFICATION_IN-PROCESS.md`):
  - Re-open translation hygiene gate as **not complete** until runtime key parity is proven.
- **CHOREOPS-UX-ROLEFLOW-001** (`OPTIONS_FLOW_ROLE_BASED_USERS_IN-PROCESS.md`):
  - Keep functional flow phases complete, but add release-hardening dependency: translation contract realignment gate.

## Decisions & completion check

- **Decision**: Runtime translation key IDs are authoritative until runtime constants and handlers are changed in lockstep.
- **Decision**: Approved terminal terminology policy: `KidsChores` is restricted to migration/legacy/credit references and the explicit fun label `KidsChores Mode`; `kid` and `parent` are disallowed in runtime symbols/translations/core docs outside documented migration-only compatibility and intentional README/wiki exceptions.
- **Completion**: `[x]` Runtime key parity report shows zero missing keys and focused regression gates pass.
