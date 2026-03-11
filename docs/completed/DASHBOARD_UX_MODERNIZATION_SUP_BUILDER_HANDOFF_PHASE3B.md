# Builder handoff: Dashboard UX modernization (Phase 3B row-template parity recovery)

## Initiative snapshot

- **Name / Code**: Dashboard UX modernization – Phase 3B (`DASHBOARD_UX_MODERNIZATION_PHASE3B`)
- **Target release / milestone**: `release/0.5.0-beta.5-prep` hardening track
- **Owner / driver(s)**: Builder execution owner + dashboard maintainer reviewer
- **Status**: In progress

## Purpose

Phase 3B exists to correct a critical architecture/behavior gap: `user-chores-v1` must implement **true `button_card_templates` semantics**, not only shared include-style composition.

This handoff is complete only when parity is proven with targeted tests and an explicit parity matrix.

## Why Phase 3B did not catch this earlier

Root-cause analysis for the missed issue (shared-fragment ids containing `/`):

1. B1/B3 parity focus was scoped primarily to row UX semantics (`button_card_templates`, state/action parity), not marker-parser contract parity.
2. Phase 3A marked composition as complete, but the parser regex accepted `.` and `-` ids while missing `/` support documented in the template guide.
3. Existing composition tests emphasized compose/fail behavior for simple fragment ids and did not assert nested fragment-id examples (`rows/chore/action_v1`).
4. Because release-apply used a mirrored parser pattern, the same blind spot existed for online release download as well.

Planning correction:

- Phase 3B now treats marker-parser compatibility as a blocking parity gate, not an implicit Phase 3A assumption.

## Non-negotiable definition of “100% row-template functionality parity”

Treat parity as **measured equivalence**, not a visual estimate:

1. Row template contract matches the v2 shared-row reference structure (`button_card_templates` + row template reference usage)
2. State/icon/action routing matches row-reference behavior for all supported states/modes
3. Shared/chore progress and badge semantics match row-reference behavior
4. Description/history/progress visibility logic matches row-reference behavior
5. Translation-driven labels remain functional and complete
6. Sync and release-apply outputs remain deterministic and safe

## Source references (must drive implementation)

- Shared-row reference contract: `choreops-dashboards/docs/shared_button_card_dashboard_reference_v2.yaml`
  - `button_card_templates` block: lines 2-3
  - Reference view anchor: line 415
- Current implementation target: `choreops-dashboards/templates/user-chores-v1.yaml`
  - Chores card anchor: line 150
  - Render section anchor: line 439
  - Current row include anchor: line 522
- Runtime composition paths:
  - `utils/sync_dashboard_assets.py` (compose anchors lines 71, 110)
  - `custom_components/choreops/helpers/dashboard_helpers.py` (compose/release apply anchors lines 103, 201)

## Execution phases

### Phase B1 – Parity audit foundation

- **Goal**: Build a line-by-line parity matrix between the v2 row contract and `user-chores-v1` behavior.
- **Steps**
  1. [x] Create parity matrix table in this document covering row contract categories:
         `name/icon`, `styles`, `custom_fields`, `btn_undo`, `btn_action`, state mapping, claim-mode mapping.
  2. [x] For each matrix row, mark status: `match`, `partial`, `missing`, or `intentional deviation`.
  3. [x] For every `partial/missing`, record exact implementation file and target section.
  4. [x] Obtain maintainer sign-off on any intentional deviations before code edits.
- **Files**: this file, `choreops-dashboards/docs/shared_button_card_dashboard_reference_v2.yaml`, `choreops-dashboards/templates/user-chores-v1.yaml`

### Phase B1 output – Row-template parity matrix

| Contract area                                                         | Source reference                                                                                     | Current `user-chores-v1` state                                                                                  | Status  | Implementation target                                                                                                    |
| --------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- | ------- | ------------------------------------------------------------------------------------------------------------------------ |
| `button_card_templates` root contract                                 | `shared_button_card_dashboard_reference_v2.yaml` lines 2-3                                           | Template-level `button_card_templates` is now defined in `user-chores-v1` and synced to runtime output          | match   | Keep root template definition and guard it with render/contract tests                                                    |
| Row template indirection (`template:` usage)                          | Row instances under `views` block (line 415+)                                                        | Row cards now reference `choreops_chore_row_v1` through shared row-instance helper                              | match   | Keep row template indirection and harden behavior parity in B3                                                           |
| Row `name` + badge behavior (`shared_all`, `shared_first`, rotation)  | `choreops_chore_row_v2.name` block                                                                   | Equivalent logic exists in current row object (composed/inlined)                                                | partial | Move logic into real button-card template definition and preserve behavior                                               |
| Row visual styles (`card/grid/name/icon`)                             | `styles` block                                                                                       | Equivalent structure and values exist, but are not housed in template contract                                  | partial | Relocate styles into template definition without behavior change                                                         |
| `custom_fields.due` mapping + date formatting                         | `custom_fields.due`                                                                                  | Equivalent semantics exist with translation-backed labels; state normalization is close but not contract-tested | partial | Keep translation model, add explicit parity tests for state/date output contract                                         |
| `custom_fields.description` visibility                                | `variables.pref_show_chore_description` usage                                                        | Works through Jinja-injected boolean and current row config; not template-variable driven                       | partial | Bind pref through template variables or documented equivalent in template block                                          |
| `custom_fields.history` contextual messaging                          | History block                                                                                        | Equivalent high-level behavior exists; requires explicit parity assertions for blocked/steal/shared cases       | partial | Add behavior tests for each decision branch                                                                              |
| `custom_fields.progress` shared_all bar logic                         | Progress block                                                                                       | Equivalent behavior exists in current row object                                                                | partial | Move into template definition and test numeric output cases                                                              |
| `btn_undo` action routing                                             | `btn_undo.card.tap_action`                                                                           | Equivalent service call exists                                                                                  | match   | Keep behavior unchanged during template migration                                                                        |
| `btn_action` icon selection and tap routing                           | `btn_action` block                                                                                   | Equivalent logic exists, including blocked/steal handling; no parity test matrix yet                            | partial | Add explicit state/mode action routing tests and preserve current outputs                                                |
| Dashboard-level compatibility with single-view generator              | `dashboard_builder.render_dashboard_template` view contract                                          | Multi-view builder now hoists view-level `button_card_templates` into dashboard root                            | match   | Maintain hoist behavior with dedicated provenance/contract regression coverage                                           |
| Sync + release-apply deterministic composition                        | `utils/sync_dashboard_assets.py`, `dashboard_helpers._replace_managed_dashboard_assets_from_release` | Composition parity implemented and tested                                                                       | match   | Re-run parity tests after template architecture migration                                                                |
| Marker parser compatibility with documented nested fragment ids (`/`) | `docs/DASHBOARD_TEMPLATE_GUIDE.md` shared-template contract section                                  | Parser regex in sync and release-apply paths currently omits `/` in fragment-id token class                     | missing | Update parser contract in both paths and add nested-id regression tests for local sync and online release-download apply |

Intentional deviations sign-off record:

- None accepted in Phase B1. All `missing/partial` rows are implementation requirements for Phase B2/B3.

### Phase B2 – True button-card-template architecture

- **Goal**: Implement row rendering through actual `button_card_templates` semantics in `user-chores-v1`.
- **Steps**
  1. [x] Rename shared row helper to production naming and wire `user-chores-v1` include usage.
  2. [x] Introduce template-level `button_card_templates` block in `user-chores-v1` that defines the row template contract.
  3. [x] Convert chore row instantiation to template references (`template: <row-template-id>`) and pass required variables for translations/preferences.
  4. [x] Remove duplicate inline row object assembly once template reference path is validated.
  5. [x] Keep metadata stamp, snippet contracts, and section structure intact.
- **Files**: `choreops-dashboards/templates/user-chores-v1.yaml` (primary), optional helper fragment file under `choreops-dashboards/templates/shared/`

### Phase B3 – Behavioral parity hardening

- **Goal**: Match row-reference behavior for row state/action logic and visibility semantics.
- **Steps (remaining, executable order)**
  1. [ ] Align icon normalization and state routing to the row reference for `approved_in_part` -> `completed_in_part` and `already_approved` -> `completed`.
         **Files**: `choreops-dashboards/templates/shared/button_card_template_user_chores_row_v1.yaml` (state/icon mapping block near lines 1-120), `choreops-dashboards/docs/shared_button_card_dashboard_reference_v2.yaml` (state/icon mapping near lines 70-170).
  2. [ ] Align `btn_action` icon and tap routing for blocked claim modes (`blocked_*`) and `steal_available`, including disabled no-op behavior for terminal states.
         **Files**: `choreops-dashboards/templates/shared/button_card_template_user_chores_row_v1.yaml` (`btn_action` block near lines 180-330), `choreops-dashboards/docs/shared_button_card_dashboard_reference_v2.yaml` (`btn_action` block near lines 200-360).
  3. [ ] Align `btn_undo` visibility and action semantics to the same claimed-state rule used by the v2 reference.
         **Files**: `choreops-dashboards/templates/shared/button_card_template_user_chores_row_v1.yaml` (`btn_undo` styles/tap-action near lines 220-290), `choreops-dashboards/docs/shared_button_card_dashboard_reference_v2.yaml` (`btn_undo` near lines 180-240).
  4. [ ] Align shared badge/progress/history semantics for `shared_all`, `shared_first`, and rotation, including partial-vs-complete color boundaries and context labels.
         **Files**: `choreops-dashboards/templates/shared/button_card_template_user_chores_row_v1.yaml` (`name`, `history`, `progress` blocks near lines 1-260), `choreops-dashboards/docs/shared_button_card_dashboard_reference_v2.yaml` (`name`, `history`, `progress` near lines 7-280).
  5. [ ] Validate translation-key coverage for all row-rendered labels (`steal_window_open`, `current_turn`, `available_in`, `overdue_in`, blocked labels) and add only missing keys.
         **Files**: `custom_components/choreops/dashboards/translations/en_dashboard.json` (status labels near lines 55-95), `choreops-dashboards/translations/en_dashboard.json` (canonical source mirror for same keys).
  6. [ ] Re-sync canonical assets and confirm the composed vendored output still carries the exact row template contract (no unresolved markers, no inline regression).
         **Files**: `choreops-dashboards/templates/user-chores-v1.yaml` (template include near lines 20-30), `custom_components/choreops/dashboards/templates/user-chores-v1.yaml` (composed output verification near lines 20-40).
  7. [x] Remediate marker parser compatibility in local sync path so fragment ids support documented nested syntax (`rows/chore/action_v1`).
         **Files**: `utils/sync_dashboard_assets.py`, `docs/DASHBOARD_TEMPLATE_GUIDE.md` (contract reference only).
         **Acceptance**: `template_shared.<nested/path>` markers compose successfully in sync and `--check` parity.
  8. [x] Remediate marker parser compatibility in online release-download apply path using the same fragment-id contract as local sync.
         **Files**: `custom_components/choreops/helpers/dashboard_helpers.py` (`_compose_prepared_template_assets` path).
         **Acceptance**: prepared release assets containing nested fragment ids compose successfully before disk apply.

### Phase B3 test matrix (required before B4 close)

1. [ ] Add row-behavior parity tests for icon/action routing across: `claimed`, `claimed_in_part`, `completed`, `completed_in_part`, `overdue`, `waiting`, `blocked_*`, `steal_available`.
       **Files**: `tests/test_dashboard_row_behavior_parity.py` (new), `tests/test_dashboard_template_render_smoke.py` (extend row-template assertions near lines 54-77).
2. [ ] Add contract assertions that rendered `button_card_templates.choreops_chore_row_v1` contains required sub-blocks (`custom_fields.due/history/progress`, `btn_undo`, `btn_action`).
       **Files**: `tests/test_dashboard_template_contract.py` (existing row contract test near lines 70-82), `tests/test_dashboard_template_render_smoke.py` (rendered dict assertions near lines 54-77).
3. [ ] Add deterministic parity checks proving canonical shared row fragment and vendored composed row template remain semantically aligned after sync.
       **Files**: `tests/test_dashboard_template_contract.py`, `tests/test_dashboard_release_asset_apply.py` (composition parity patterns near lines 90-150).
4. [x] Add nested fragment-id regression tests for local sync (`template_shared.rows/chore/action_v1`) and assert compose succeeds.
       **Files**: `tests/test_sync_dashboard_assets.py` (new or extend existing sync tests).
5. [x] Add nested fragment-id regression tests for online release-download apply path and assert compose succeeds before write.
       **Files**: `tests/test_dashboard_release_asset_apply.py`.

### Phase B4 – Verification and closure evidence

- **Goal**: Prove parity and runtime safety with targeted tests and deterministic output checks.
- **Steps**
  1. [x] Complete the B3 test matrix additions and commit parity evidence links in this file.
  2. [ ] Run canonical sync + parity checks and confirm no marker leakage.
  3. [ ] Run targeted test suite listed below and record pass counts.
  4. [ ] Update main plan (`DASHBOARD_UX_MODERNIZATION_IN-PROCESS.md`) to move Phase 3B from in-progress to complete.
  5. [x] Record explicit evidence that both ingestion paths (local sync and online release-download apply) pass nested fragment-id tests.
- **Files**: `tests/test_dashboard_template_contract.py`, `tests/test_dashboard_template_render_smoke.py`, `tests/test_dashboard_row_behavior_parity.py` (new), `docs/in-process/DASHBOARD_UX_MODERNIZATION_IN-PROCESS.md`

## Required targeted validation commands

Run in `choreops` only, and capture pass/fail outputs in this file.

1. `python utils/sync_dashboard_assets.py`
2. `python utils/sync_dashboard_assets.py --check`
3. `python -m pytest tests/test_dashboard_template_render_smoke.py -v --tb=line`
4. `python -m pytest tests/test_dashboard_template_contract.py -v --tb=line`
5. `python -m pytest tests/test_dashboard_manifest_dependencies_contract.py -v --tb=line`
6. `python -m pytest tests/test_dashboard_release_asset_apply.py -v --tb=line`
7. `python -m pytest tests/test_dashboard_helper_size_reduction.py -v --tb=line`
8. `python -m pytest tests/test_dashboard_release_asset_apply.py tests/test_sync_dashboard_assets.py -v --tb=line`

Execution evidence (current checkpoint):

- `python utils/sync_dashboard_assets.py` ✅
- `python utils/sync_dashboard_assets.py --check` ✅
- `./utils/quick_lint.sh --fix` ✅
- `python -m pytest tests/test_dashboard_template_render_smoke.py tests/test_dashboard_template_contract.py tests/test_dashboard_manifest_dependencies_contract.py tests/test_dashboard_release_asset_apply.py tests/test_dashboard_helper_size_reduction.py tests/test_dashboard_provenance_contract.py -v --tb=line` ✅ (38 passed)
- `python -m pytest tests/test_dashboard_release_asset_apply.py tests/test_sync_dashboard_assets.py -v --tb=line` ✅ (7 passed)
- `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` ✅

If new parity tests are added, append them to this targeted list and run them in the same pass.

## Immediate execution order (next builder pass)

1. Complete Phase B3 steps 1-4 in canonical shared row template.
2. Complete Phase B3 step 5 translation coverage check.
3. Run `python utils/sync_dashboard_assets.py` and `python utils/sync_dashboard_assets.py --check`.
4. Implement and run Phase B3 test matrix.
5. Re-run B4 validation suite and update checkboxes in this handoff + main initiative plan.

## Acceptance checklist (must all be checked)

- [ ] Parity matrix completed with no unresolved `partial/missing` items
- [x] `user-chores-v1` uses true `button_card_templates` row semantics
- [ ] State/action parity proven against the reference contract for all supported modes
- [ ] Translation behavior remains correct for all user-visible row strings
- [ ] Sync/release-apply parity and safety tests pass
- [ ] Targeted regression suite passes with recorded outputs
- [ ] Main initiative plan updated to reflect verified completion

## Risks and guardrails

- Risk: introducing `button_card_templates` at wrong YAML level can invalidate template render
  - Guardrail: add render smoke coverage for `user-chores-v1` specifically
- Risk: action routing regression in blocked/steal states
  - Guardrail: explicit state/mode test matrix
- Risk: dependency drift (custom cards)
  - Guardrail: dependency contract test remains mandatory
- Risk: parser contract drift between docs and implementation (for nested fragment ids)
  - Guardrail: enforce shared fragment-id regex/contract parity in both sync and online release-download apply tests

## Decisions required before implementation starts

1. Whether to keep shared include markers for helper snippets in addition to button-card templates
2. Whether any reference-contract behavior is intentionally excluded for MVP scope (must be documented in parity matrix)
3. Whether to add a dedicated `user-chores-v2` for clean cutover or complete `v1` parity in place

## Completion report template (Builder must fill)

1. **What changed** (files)
2. **Parity matrix outcome** (all rows status)
3. **Validation outputs** (commands + pass counts)
4. **Known residual gaps** (must be `none` for Phase 3B close)
5. **Recommendation** (close Phase 3B / continue)
