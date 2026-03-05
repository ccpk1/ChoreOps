# Builder handoff: Dashboard UX modernization (Phase 3C single-path template contract)

## Initiative snapshot

- **Name / Code**: Dashboard UX modernization – Phase 3C (`DASHBOARD_UX_MODERNIZATION_PHASE3C`)
- **Target release / milestone**: `release/0.5.0-beta.5-prep` completion hardening
- **Owner / driver(s)**: Builder execution owner + dashboard architecture reviewer
- **Status**: Complete

## Summary & immediate steps

| Phase / Step                                | Description                                                                                                  | % complete | Quick notes                                                                               |
| ------------------------------------------- | ------------------------------------------------------------------------------------------------------------ | ---------: | ----------------------------------------------------------------------------------------- |
| Phase 1 – Contract and source-of-truth lock | Define manifest-based shared-template contract and preserve canonical/shared directory ownership             |        100 | Shared contract fields added with backward-compatible parser defaults and validation      |
| Phase 2 – Single compile pipeline           | Route create/update/release-apply through one compiler path with deterministic compose/validate/overwrite    |        100 | Invariants verified; deterministic managed overwrite path covered by release-apply tests  |
| Phase 3 – Validation and parity gates       | Add/extend tests proving shared-fragment closure, parity, and deterministic behavior across all entry points |        100 | Builder prepared-vs-composed equivalence + unresolved-marker hard-fail parity now covered |
| Phase 4 – Docs and rollout closure          | Update guides/checklists and close 3C with execution evidence                                                |        100 | Docs/tracker reconciled and execution evidence captured                                   |

1. **Key objective** – Make dashboard template handling single-path, reproducible, and release-download safe.
2. **Summary of recent work** – Phase 3A/3B delivered compose parity helpers and row-template recovery; 3C now unifies contract + execution path.
3. **Next steps (short term)** – Phase 3C is complete; proceed to Phase 4 admin modernization and final UX polish.
4. **Risks / blockers**
   - Contract drift risk if shared-fragment requirements are duplicated between template markers and registry metadata.
   - Runtime drift risk if create/update still consume uncomposed prepared assets while release-apply composes first.
   - Backward-compatibility risk if existing registry entries are treated as strict without migration defaults.
5. **References**
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `docs/CODE_REVIEW_GUIDE.md`
   - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
   - `docs/RELEASE_CHECKLIST.md`
   - `docs/DASHBOARD_TEMPLATE_GUIDE.md`
   - `docs/in-process/DASHBOARD_UX_MODERNIZATION_IN-PROCESS.md`
   - `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_BUILDER_HANDOFF_PHASE3B.md`
     - `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_PHASE3C_SCHEMA_APPENDIX.md`
6. **Decisions & completion check**
   - **Decisions captured**:
     - Keep shared template files in `templates/shared/` in both canonical and vendored roots.
     - Add per-template shared contract fields in registry and use them for validation/governance.
     - Enforce one compiler path for create/update/release-apply input processing.
     - Preserve deterministic managed overwrite behavior on write/update.

- **Completion confirmation**: `[x]` All 3C follow-up items complete and evidence attached before owner sign-off.

> **Important:** Keep this summary updated after each 3C milestone (contract, pipeline, tests, docs).

## Tracking expectations

- **Summary upkeep**: Update percentages and blockers after each meaningful 3C commit.
- **Detailed tracking**: Keep line-level implementation details in phase sections below.

## Builder handoff packet (start here)

### Execution intent

Builder should implement Phase 3C exactly as scoped in this document:

- no unrelated dashboard UX refactors,
- no `.storage` schema changes,
- no new feature behavior outside compile/contract path unification.

### First pass scope (single PR target)

1. Phase 1, steps 1-4
2. Phase 2, steps 1-3
3. Phase 3, steps 1 and 3

Defer Phase 2 steps 4-5 and remaining Phase 3/4 steps only if hard blockers appear.

### Mandatory pre-implementation checklist

- [x] Re-read `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_PHASE3C_SCHEMA_APPENDIX.md`
- [x] Confirm parser touchpoints in `dashboard_helpers.py` and `dashboard_builder.py`
- [x] Confirm sync parity behavior in `utils/sync_dashboard_assets.py`
- [x] Confirm current tests to extend in `tests/test_dashboard_release_asset_apply.py` and `tests/test_sync_dashboard_assets.py`

### Required deliverables for first handoff return

1. Updated registry contract parsing with backward-compatible defaults.
2. Single compile-path wiring for prepared assets in create/update.
3. Tests proving new contract parsing + no regression in existing compose behavior.
4. Updated progress checkboxes and Summary % in this file.
5. Short evidence block with exact commands and results.

## Detailed phase tracking

### Phase 1 – Contract and source-of-truth lock

- **Goal**: Define a single authoritative shared-template contract without introducing a second composition source.
- **Steps / detailed work items** 1. [x] Add registry fields for per-template shared contract metadata in canonical registry schema and parser validation.
  **Files**: `choreops-dashboards/dashboard_registry.json` (template entries near lines 10-220), `custom_components/choreops/helpers/dashboard_helpers.py` (`DashboardTemplateDefinition` and parser near lines 39-95 and 320-560). 2. [x] Define default behavior for legacy templates with no shared-contract metadata (non-breaking fallback).
  **Files**: `custom_components/choreops/helpers/dashboard_helpers.py` (`_validate_and_normalize_template_definition` near lines 320-560), `tests/test_dashboard_manifest_dependencies_contract.py` (contract fixture patterns near lines ~1-220). 3. [x] Decide and document field naming/version policy (`shared_fragments_required`, `shared_contract_version`, optional fields) and reject invalid ids early.
  **Files**: `docs/DASHBOARD_TEMPLATE_GUIDE.md` (shared fragment contract section near lines ~120-260), `custom_components/choreops/helpers/dashboard_helpers.py` (regex + parser near lines 87-105 and 320-560). 4. [x] Record migration and compatibility note: **no storage schema change required** (this is dashboard asset contract only).
  **Files**: `docs/in-process/DASHBOARD_UX_MODERNIZATION_IN-PROCESS.md` (summary/risk area near lines 12-50), `docs/ARCHITECTURE.md` (storage schema section near lines 1-20 and 140-180).
- **Key issues**
  - Avoid making registry the composition engine; keep file markers + shared directory as the execution source, registry as contract validator.

### Phase 2 – Single compile pipeline

- **Goal**: Remove divergent template-input paths and make create/update/release-apply run one deterministic compile flow.
- **Steps / detailed work items** 1. [x] Extract/centralize one compiler utility to: resolve shared fragments, validate registry contract, and return compiled template assets.
  **Files**: `custom_components/choreops/helpers/dashboard_helpers.py` (`_compose_prepared_template_assets` near lines 109-185), `utils/sync_dashboard_assets.py` (`_compose_template_text` near lines 77-131). 2. [x] Update release prepare flow to fetch shared-fragment closure required by selected templates before handing assets to create/update.
  **Files**: `custom_components/choreops/helpers/dashboard_helpers.py` (`async_prepare_dashboard_release_assets` near lines 884-1065), `custom_components/choreops/dashboards/dashboard_registry.json` (template source path entries near lines 10-220). 3. [x] Ensure create/update paths consume compiled assets only (never raw marker-bearing text when prepared assets are present).
  **Files**: `custom_components/choreops/helpers/dashboard_builder.py` (`create_choreops_dashboard` template cache path near lines 949-986), `custom_components/choreops/helpers/dashboard_builder.py` (`update_choreops_dashboard_views` template cache path near lines 1305-1340). 4. [x] Remove root `button_card_templates` hoist behavior so builder no longer mutates view-local template blocks.
  **Files**: `custom_components/choreops/helpers/dashboard_builder.py` (`build_multi_view_dashboard` near lines 621-656), `custom_components/choreops/helpers/dashboard_builder.py` (`update` rebuild usage near lines 1508-1525). 5. [x] Enforce deterministic write/update behavior: managed template output is checked then overwritten when out-of-contract.
  **Files**: `custom_components/choreops/helpers/dashboard_helpers.py` (`_replace_managed_dashboard_assets_from_release` near lines 224-290), `custom_components/choreops/options_flow.py` (prepare/apply call chain near lines 3890-3940).
- **Key issues**
  - Do not introduce separate local-vs-remote compile logic; both must call the same helper path.

### Phase 3 – Validation and parity gates

- **Goal**: Prove the single-path behavior with tests that fail on any regression to dual-path handling.
- **Steps / detailed work items** 1. [x] Extend release-asset preparation tests to assert shared-fragment closure fetch behavior for marker-bearing templates.
  **Files**: `tests/test_dashboard_release_asset_apply.py` (compose/failure coverage near lines 90-205), `tests/test_options_flow_dashboard_release_selection.py` (prepared-asset flow near lines 60-260). 2. [x] Add/extend builder tests to assert create/update with prepared assets produce identical output to release-applied local assets.
  **Files**: `tests/test_dashboard_template_render_smoke.py` (render baseline near lines 1-90), `tests/test_dashboard_provenance_contract.py` (provenance hooks near lines ~1-120), new `tests/test_dashboard_builder_single_path.py` (if needed). 3. [x] Add contract tests for new registry shared fields, including invalid field shapes and backward-compatible omissions.
  **Files**: `tests/test_dashboard_manifest_dependencies_contract.py` (contract test patterns near lines ~1-220), `custom_components/choreops/dashboards/dashboard_registry.json` (fixtures/expectations near lines 1-240). 4. [x] Re-validate sync parity path against the same shared marker examples used in release tests.
  **Files**: `tests/test_sync_dashboard_assets.py` (nested marker tests near lines 19-106), `utils/sync_dashboard_assets.py` (compose behavior near lines 77-131). 5. [x] Add regression for unresolved-marker hard fail across all ingestion paths.
  **Files**: `tests/test_dashboard_release_asset_apply.py` (missing fragment case near lines 187-205), `tests/test_sync_dashboard_assets.py` (add equivalent missing-fragment case).
- **Key issues**
  - Test coverage must assert behavior equivalence, not only parser success.

### Phase 4 – Docs and rollout closure

- **Goal**: Close 3C with clear operator guidance, release readiness notes, and phase status updates.
- **Steps / detailed work items**
  1. [ ] Update dashboard template guide with final 3C contract model (shared directory + registry contract + single compiler path).
         **Files**: `docs/DASHBOARD_TEMPLATE_GUIDE.md` (shared template section near lines ~120-280), `docs/RELEASE_CHECKLIST.md` (dashboard registry sync gates near lines 120-175).
  2. [ ] Update main initiative tracker to mark 3C status and move 3B/3C dependencies accurately.
         **Files**: `docs/in-process/DASHBOARD_UX_MODERNIZATION_IN-PROCESS.md` (summary table near lines 12-20, next-steps/risk section near lines 21-45).
  3. [ ] Add handoff completion evidence (commands/results) and close this 3C document.
         **Files**: this file (`docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_BUILDER_HANDOFF_PHASE3C.md`), optional linked CI logs.
- **Key issues**
  - Documentation must explicitly state that this phase does not change `.storage` schema/version.

## Testing & validation

- Tests to execute after implementation:
  1. `python utils/sync_dashboard_assets.py`
  2. `python utils/sync_dashboard_assets.py --check`
  3. `python -m pytest tests/test_sync_dashboard_assets.py -v --tb=line`
  4. `python -m pytest tests/test_dashboard_release_asset_apply.py -v --tb=line`
  5. `python -m pytest tests/test_dashboard_manifest_dependencies_contract.py -v --tb=line`
  6. `python -m pytest tests/test_dashboard_template_render_smoke.py -v --tb=line`
  7. `python -m pytest tests/test_options_flow_dashboard_release_selection.py -v --tb=line`
  8. `./utils/quick_lint.sh --fix`
  9. `mypy custom_components/choreops/`

- Outstanding tests (until implementation lands):
  - None for Phase 2/3 deferred scope.

## Builder execution evidence (first pass)

- `python utils/sync_dashboard_assets.py` → pass (`Dashboard asset sync completed and parity check passed`)
- `python utils/sync_dashboard_assets.py --check` → pass (`Dashboard asset parity check passed`)
- `python -m pytest tests/test_dashboard_manifest_dependencies_contract.py -v --tb=line` → pass (`6 passed`)
- `python -m pytest tests/test_dashboard_release_asset_apply.py -v --tb=line` → pass (`8 passed`)
- `python -m pytest tests/test_sync_dashboard_assets.py -v --tb=line` → pass (`2 passed`)
- `python -m pytest tests/test_options_flow_dashboard_release_selection.py -v --tb=line` → pass (`30 passed`)
- `python -m pytest tests/test_dashboard_*.py tests/test_options_flow_dashboard_release_selection.py tests/test_sync_dashboard_assets.py -v --tb=line` → pass (`89 passed`)
- `./utils/quick_lint.sh --fix` → pass (ruff + mypy + boundary checks)

## Builder execution evidence (second pass - deferred scope)

- `python -m pytest tests/test_dashboard_builder_single_path.py tests/test_dashboard_release_asset_apply.py tests/test_sync_dashboard_assets.py -v --tb=line` → pass (`14 passed`)
- `./utils/quick_lint.sh --fix` → pass (ruff + mypy + boundary checks)

## Builder execution evidence (final hard-fork closeout)

- `python utils/sync_dashboard_assets.py` → pass (`Dashboard asset sync completed and parity check passed`)
- `python utils/sync_dashboard_assets.py --check` → pass (`Dashboard asset parity check passed`)
- `python -m pytest tests/test_sync_dashboard_assets.py tests/test_dashboard_release_asset_apply.py tests/test_dashboard_provenance_contract.py tests/test_dashboard_builder_single_path.py tests/test_dashboard_template_render_smoke.py tests/test_dashboard_template_contract.py tests/test_dashboard_manifest_dependencies_contract.py -v --tb=line` → pass (`31 passed`)

## Completion report template (Builder fills)

1. **Scope executed**
   - Which phase steps were completed and which were deferred.
2. **Files changed**
   - List of touched files grouped by `helpers/`, `tests/`, and `docs/`.
3. **Validation evidence**
   - Exact commands run and pass/fail counts.
4. **Open blockers**
   - Any blockers with minimal reproduction notes.
5. **Recommendation**
   - Continue 3C next pass / mark 3C complete.

## Notes & follow-up

- **Schema/migration note**: No `.storage/choreops/choreops_data` schema increment is expected for Phase 3C.
- **Translation key note**: No new user-facing translation key is required by default; if new explicit shared-contract failure surfaces are added, route through existing dashboard flow error keys or introduce `TRANS_KEY_*` constants before merge.
- **Execution boundary note**: This 3C plan concerns dashboard asset contracts and compile flow only; it must not expand into unrelated options-flow UX changes.
