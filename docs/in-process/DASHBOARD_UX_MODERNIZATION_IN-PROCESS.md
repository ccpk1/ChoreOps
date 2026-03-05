# Initiative plan: Dashboard UX modernization + rapid design iteration

## Initiative snapshot

- **Name / Code**: Dashboard UX modernization + rapid design iteration (`DASHBOARD_UX_MODERNIZATION`)
- **Target release / milestone**: v0.5.x dashboard UX track (multi-PR)
- **Owner / driver(s)**: ChoreOps maintainers + dashboard design/build contributors
- **Status**: In progress

## Summary & immediate steps

| Phase / Step                                | Description                                                                                                          | % complete | Quick notes                                                                                                          |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ---------: | -------------------------------------------------------------------------------------------------------------------- |
| Phase 1 – UX foundation + tooling           | Create UX-focused dashboard builder agent and standardize template naming/version strategy                           |        100 | Completed: agent created, boundaries codified, toolkit linked                                                        |
| Phase 2 – Dev preload workflow              | Make rapid local dashboard testing easy using scenario-based live preload tooling                                    |        100 | Completed: script modernized + docs + targeted tests                                                                 |
| Phase 3 – User template modernization       | Build lightweight inline chore-essentials first, then full-featured chores template from the v2 shared-row reference |        100 | Essentials + chores v1 drafted and composition-ready                                                                 |
| Phase 3A – Template composition parity      | Ensure shared-template composition behaves identically in local sync and remote release apply                        |        100 | Shared contract + sync/release parity + safety tests complete                                                        |
| Phase 3B – Row template parity recovery     | Rebuild `user-chores-v1` around true `button_card_templates` semantics and prove behavior parity                     |        100 | Closed as migration closeout; remaining user-template scope moved to Phase 4A                                        |
| Phase 3C – Single-path contract enforcement | Unify create/update/release template handling under one compile path with registry-backed shared contract validation |        100 | Hard-fork path complete: no hoist, root-template contract, strict canonical↔vendored parity, targeted suites passing |
| Phase 4A – User template UX completion      | Complete remaining user-template behavior parity and modernization follow-up                                         |         40 | Steps 1-2 complete (`user-chore-essentials-v1`, `user-chores-v1` + `user-essential-v1` removal); next Step 3         |
| Phase 4 – Admin modernization + docs/polish | Modernize admin templates and finalize docs/contracts/validation checklist                                           |          0 | Align with template and UI guidelines                                                                                |

1. **Key objective** – Deliver modern, app-like dashboards with strong runtime stability.
2. **Summary of recent work** – Phase 3B now includes true row-template architecture wiring (`button_card_templates` + row template references), no builder hoist behavior, sync parity confirmation, and targeted validation pass.
3. **Next steps (short term)** – Execute Phase 4A Step 3 (young-kids chores template), then Step 4 (gamification modernization), then continue Phase 4A closure evidence and Phase 4 admin modernization.
4. **Risks / blockers**
   - Home Assistant dashboard constraints (no custom card authoring in this initiative) can limit advanced interaction patterns.
   - Dependency drift risk when introducing new custom card usage across templates.
   - Rapid design iteration may create contract drift unless canonical-vendored sync is enforced each cycle.
     - Architecture mismatch risk: include-marker composition alone does not prove true `button_card_templates` behavior parity.
     - Composition drift risk: if shared-template composition runs in sync flow but not remote release-apply flow, local and downloaded dashboards can diverge.
     - Runtime failure risk: unresolved fragment markers in published templates can break generator rendering at runtime.
       - Dual-path risk remains until create/update/release ingestion all consume compiled assets through one helper path.
       - Verification drift risk: existing tests do not currently assert template-definition semantics.
       - Parser-contract drift risk: documented nested shared fragment ids (with `/`) were not explicitly validated in Phase 3B, allowing sync/release parsers to diverge from docs.
5. **References**
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `docs/CODE_REVIEW_GUIDE.md`
   - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
   - `docs/RELEASE_CHECKLIST.md`
   - `docs/DASHBOARD_TEMPLATE_GUIDE.md`
   - `docs/DASHBOARD_UI_DESIGN_GUIDELINE.md`
   - `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_DASHBOARD_BUILDER_AGENT_DRAFT.md`
   - `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_CARD_TOOLKIT.md`
     - `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_BUILDER_HANDOFF_PHASE3A.md`
       - `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_BUILDER_HANDOFF_PHASE3B.md`
       - `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_BUILDER_HANDOFF_PHASE3C.md`
       - `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_PHASE3C_SCHEMA_APPENDIX.md`
6. **Decisions & completion check**
   - **Decisions captured**:
     - Since templates are not yet user-released, prioritize UX clarity over backward compatibility in template naming and structure.
     - Introduce `chore-essentials` as the lightweight inline baseline and a separate full-featured chores template for richer UX.
     - Prioritize reusable card fragments/patterns from minimal-v2 into gamification-v2.
     - Do not build a new custom card in this initiative; rely on existing ecosystem cards only.
   - **Completion confirmation**: `[ ]` All follow-up items completed (agent + preload + templates + docs + parity + validation) before owner sign-off.

> **Important:** Keep this Summary table current after each phase-level implementation milestone.

## Tracking expectations

- **Summary upkeep**: Update percentages, blockers, and quick notes after each phase completion.
- **Detailed tracking**: Keep implementation granularity in phase sections; keep Summary high-level.

## Detailed phase tracking

### Phase 1 – UX foundation + tooling

- **Goal**: Establish execution framework and naming/version contracts for UX-first dashboard work before template changes.
- **Steps / detailed work items** 1. [x] Create new UX-focused implementation agent file using the builder frontmatter/workflow baseline from `.github/agents/builder.agent.md` (lines 1-96), but tuned for dashboard UX iteration and HA Lovelace constraints.
  **Files**: `.github/agents/builder.agent.md` (source pattern), `.github/agents/dashboard-ux-builder.agent.md` (new).
  **Line anchors**: source frontmatter/workflow in `builder.agent.md` lines 1-96. 2. [x] Add explicit UX-agent guardrails for: no custom card development, only template/config-driven UX changes, strict dependency declaration updates in registry when `custom:*` usage changes.
  **Files**: `.github/agents/dashboard-ux-builder.agent.md`, `tests/test_dashboard_manifest_dependencies_contract.py`.
  **Line anchors**: dependency contract test expectations lines 33-152. 3. [x] Define and ratify additive naming strategy for new templates (`*-v2`) while preserving current `*-v1` IDs and regex compatibility.
  **Files**: `docs/DASHBOARD_TEMPLATE_GUIDE.md`, `custom_components/choreops/helpers/dashboard_helpers.py`.
  **Line anchors**: naming pattern in guide (new template section + structure) lines 152-260, template ID regex in `dashboard_helpers.py` line 87. 4. [x] Document UX iteration acceptance criteria (visual quality + usability + HA practicality) and tie them to state-channel requirements from UI guideline.
  **Files**: `docs/DASHBOARD_UI_DESIGN_GUIDELINE.md`, `docs/DASHBOARD_TEMPLATE_GUIDE.md`.
  **Line anchors**: state communication + styling rules in UI guideline lines 13-101. 5. [x] Add official handoff/update path so the new UX agent can pass completed plan phases back to Builder without bypassing existing phase-confirmation workflow.
  **Files**: `.github/agents/dashboard-ux-builder.agent.md`, `.github/agents/strategist.agent.md`.
  **Line anchors**: existing strategist handoff contract lines 1-18.
- **Key issues**
  - Agent instructions must remain precise enough for fast iteration but not conflict with established quality gates.
  - Naming strategy must preserve compatibility with `_VALID_TEMPLATE_ID_RE` and release-selection behavior.

### Phase 2 kickoff handoff packet (ready)

- **Agent**: `.github/agents/dashboard-ux-builder.agent.md`
- **Scope to execute first**: Phase 2, Step 1 only (modernize live preload script path/domain assumptions)
- **Primary files**: - `utils/load_test_scenario_to_live_ha.py` - `utils/README.md`
- **Hard constraints**: - Template source edits only in `choreops-dashboards/templates/*` - Dashboard translation source edits only in `choreops-dashboards/translations/en_dashboard.json` - Sync to vendored runtime when testing requires local runtime visibility
- **Validation for this kickoff step**: - `./utils/quick_lint.sh --fix` - targeted tests as applicable to changed utility logic
- **Expected completion output**: - updated plan checkbox for Phase 2 Step 1 - concise report: files changed, validations, blockers/next step

### Local sandbox auth (development only)

- **Dev instance token (sandbox)**:
  `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJkMTg1MzVmMWRkOTg0OGUyOTNiNmI5OWY4ODc2NTc1MyIsImlhdCI6MTc3MjU1OTc0NywiZXhwIjoyMDg3OTE5NzQ3fQ.Bk0f4R062GzJifL_It2ybOd7Eu5iGRrOhZPoQHIAJEM`

### Phase 2 – Dev preload workflow

- **Goal**: Enable one-command(ish) local data preloading for dashboard UX testing using existing scenario logic.
- **Steps / detailed work items**
  1. [x] Modernize live preload script to current repository/domain conventions (`choreops` vs legacy `kidschores`) and scenario file locations.
         **Files**: `utils/load_test_scenario_to_live_ha.py`, `utils/README.md`.
         **Line anchors**: legacy paths/domain usage in script lines 1-48 and 81-112; README references lines 7-33.
  2. [x] Add CLI arguments for scenario selection (`tests/scenarios/scenario_minimal.yaml`, `scenario_full.yaml`, etc.), HA URL, and non-interactive token input via env var for repeatable local cycles.
         **Files**: `utils/load_test_scenario_to_live_ha.py`, `tests/scenarios/` YAML files.
         **Line anchors**: parser currently only supports `--reset` in script lines 266-279.
  3. [x] Align payload mapping to current options-flow field names/menu selections using reusable constants/flow contracts where feasible.
         **Files**: `utils/load_test_scenario_to_live_ha.py`, `custom_components/choreops/options_flow.py`.
         **Line anchors**: dashboard/options flow structure around lines 3818-4717; script entity-add flow lines 114-257.
  4. [x] Add dry-run/validation mode to verify scenario structure and intended operations before mutating live instance.
         **Files**: `utils/load_test_scenario_to_live_ha.py`, `tests/helpers/setup.py`.
         **Line anchors**: canonical scenario loader model in `setup.py` lines 1-220 and schema helpers lines 82-162.
  5. [x] Add usage documentation for UX iteration loops (reset/load/switch template/reload dashboard) including known limitations and safety notes.
         **Files**: `utils/README.md`, `docs/DASHBOARD_TEMPLATE_GUIDE.md`.
         **Line anchors**: utils usage block lines 7-33; guide workflow lines 67-85.
  6. [x] Add targeted tests for any new parser/helper logic extracted from live preload script (pure helper functions only; no live-HA calls in unit tests).
         **Files**: `tests/test_dashboard_*` (new/updated), optional `tests/helpers/*` helper test module.
         **Line anchors**: dashboard smoke/contract patterns in `tests/test_dashboard_template_render_smoke.py` lines 1-47.
- **Key issues**
  - Existing script is a dev utility with legacy assumptions; modernization should avoid introducing runtime coupling to test-only helpers.
  - Need safe defaults to avoid destructive resets in unintended instances.

### Phase 3 – User template modernization

- **Goal**: Deliver a modern lightweight inline chores template first (`chore-essentials`), then deliver a full-featured chores template based on the v2 shared-row reference patterns.
- **Critical template integrity gate (mandatory for every new template completion)**
  - Preserve template header format, snippet contracts, and metadata stamp placement exactly as defined in the guides.
  - Preserve translation and graceful error-handling patterns (no regressions in fallback behavior, helper validation, or missing-entity handling).
  - Keep structure easy to follow/maintain: do not collapse or obscure existing logical sections.
  - Default implementation strategy: start from existing template baseline, then focus changes in render sections first.
  - **Completion gate question (must be explicitly answered for each new template):**
    - "Did this template keep headers, translation wiring, graceful error handling, and logical sectioning intact while limiting scope mainly to render changes?"
- **Steps / detailed work items**
  1. [x] Establish baseline from current essential/minimal user template structure for modern chores-card iteration.
         **Files**: `choreops-dashboards/templates/user-minimal-v1.yaml`, `choreops-dashboards/templates/user-essential-v1.yaml`.
         **Line anchors**: existing user template header/card structure lines 1-50. 2. [x] Build `chore-essentials` lightweight inline chores template using production state/claim/color semantics with minimal presentation layers.
         **Files**: `choreops-dashboards/templates/user-chore-essentials-v1.yaml` (new), `docs/DASHBOARD_UI_DESIGN_GUIDELINE.md`.
         **Scope constraints**: no progress bar, reduced secondary context, no heavy decorative effects, keep optional chore description preference.
  2. [x] Register `user-chore-essentials-v1` in canonical registry with accurate dependency declarations (required/recommended) and preference doc linkage.
         **Files**: `choreops-dashboards/dashboard_registry.json`, `choreops-dashboards/preferences/user-chore-essentials-v1.md` (new).
         **Line anchors**: existing template registry contract lines 1-125. 3. [x] Build full-featured chores template from v2 shared-row reference patterns (welcome/header + richer shared context + full chore UX semantics).
         **Files**: `choreops-dashboards/templates/user-chores-v1.yaml` (new), `docs/DASHBOARD_UI_DESIGN_GUIDELINE.md`.
         **Line anchors**: row reference `choreops-dashboards/docs/shared_button_card_dashboard_reference_v2.yaml` and guideline state channels.
  3. [x] Register full-featured chores template + preferences and ensure dependency declarations cover all `custom:*` usage.
         **Files**: `choreops-dashboards/dashboard_registry.json`, `choreops-dashboards/preferences/user-chores-v1.md` (new).
         **Line anchors**: dependency contract expectations in test file lines 33-152.
  4. [x] Sync canonical assets into vendored runtime mirror and verify parity before any integration-side flow/testing updates.
         **Files**: `utils/sync_dashboard_assets.py` (execution), `custom_components/choreops/dashboards/*` (synced outputs).
         **Line anchors**: required sync/parity workflow in template guide lines 67-85.
- **Key issues** - Must keep all templates as single-view outputs and preserve dual Jinja delimiter rules. - Headers, translations, graceful error handling, and clear template organization are non-negotiable quality gates for every new template. - Lightweight template should prioritize readability and fast render path (minimal visual layers). - Full template should preserve shared-row reference behavior while avoiding drift from canonical state/claim semantics.

### Phase 3A – Template composition parity (sync + release apply)

- **Goal**: Ensure modular/shared template authoring composes into identical final runtime assets in both local sync and remote release-download apply paths.
- **Why this sub-phase exists**: Current user-chores draft carries full row UX semantics, but architecture alignment is required so builder/runtime behavior is deterministic regardless of asset source.
- **Steps / detailed work items** 1. [x] Define shared-template source contract (`templates/shared/*`) and include-marker syntax, plus naming/version conventions.
  **Files**: `choreops-dashboards/templates/shared/*` (new), `docs/DASHBOARD_TEMPLATE_GUIDE.md`.
  **Acceptance**: contract is explicit about source vs published assets. 2. [x] Add composition to canonical→vendored sync flow with fail-fast handling for unresolved markers.
  **Files**: `utils/sync_dashboard_assets.py` (+ helper module if needed).
  **Acceptance**: parity check validates composed canonical output against vendored runtime output. 3. [x] Add equivalent composition behavior to remote release-asset apply path.
  **Files**: `custom_components/choreops/helpers/dashboard_helpers.py` (`_replace_managed_dashboard_assets_from_release`, `async_apply_prepared_dashboard_release_assets`).
  **Acceptance**: composed runtime files are produced before dashboard generation reads templates. 4. [x] Add tests proving composition parity and safety for both paths.
  **Files**: `tests/test_dashboard_release_asset_apply.py`, composition-focused tests, and any required contract tests.
  **Acceptance**: same source inputs produce byte-identical composed outputs in both flows. 5. [x] Finalize `user-chores-v1` against the shared-template architecture and re-run dashboard quality gates.
  **Files**: `choreops-dashboards/templates/user-chores-v1.yaml`, `choreops-dashboards/preferences/user-chores-v1.md`, `choreops-dashboards/dashboard_registry.json`.
  **Acceptance**: full-featured chores template passes render/contract/dependency/size gates on final architecture.
- **Traps (analysis)**
  - Composition implemented in only one path (sync or release-apply) causes local-vs-remote drift.
  - Unresolved include markers reaching runtime templates can cause generator render failures.
  - Composition logic that bypasses existing release-apply path guards may reintroduce path traversal or stale-asset issues.
  - Ambiguous ownership of generated files can lead to manual edits in vendored runtime outputs.
- **Opportunities (analysis)**
  - Centralize complex row logic once, reducing duplicate maintenance across templates.
  - Increase iteration speed by editing shared building blocks while preserving deterministic published artifacts.
  - Strengthen confidence with parity tests that enforce identical outcomes across both ingestion paths.
- **Guiding design decisions (to ratify before Builder execution)**
  - Runtime generator must consume fully composed templates only (no runtime fragment merge in render path).
  - Composition is a pre-runtime asset concern and must be applied uniformly in sync and release-apply flows.
  - Unresolved marker tokens are hard failures, not warnings.
  - Rollout should be incremental: migrate one shared row block first (`user-chores-v1`), then expand.

### Phase 3B – Button-card-template parity recovery

**Phase status update**: Closed as a migration closeout. Remaining user-template parity and behavior work is moved to **Phase 4A** to avoid reopening pre-3C sequencing.

- **Goal**: Rebuild `user-chores-v1` so its row behavior follows true `button_card_templates` semantics and prove parity with objective tests/evidence.
- **Gap analysis update (added)**
  - Phase 3B originally concentrated on row behavior and template semantics, but did not include an explicit parser-compatibility gate for shared-fragment marker ids.
  - As a result, the documented nested-fragment contract (`template_shared.<path/segment>`) was not covered by regression tests.
  - The same parser pattern exists in both local sync and online release-download apply paths, so this is a dual-path risk.
- **Steps / detailed work items** 1. [x] Build a parity matrix of the v2 row contract vs current `user-chores-v1` behavior (states, icons, actions, fields, translation labels).
  **Files**: `choreops-dashboards/docs/shared_button_card_dashboard_reference_v2.yaml` (anchors: `button_card_templates` lines 2-3), `choreops-dashboards/templates/user-chores-v1.yaml` (anchors: chores card section line 150, render section line 439).
  **Acceptance**: every row behavior is mapped to one explicit implementation target or justified deviation. 2. [x] Rename and wire shared row helper for production naming.
  **Files**: `choreops-dashboards/templates/shared/chore_row_user_chores_v1.yaml`, `choreops-dashboards/templates/user-chores-v1.yaml`, `choreops-dashboards/preferences/user-chores-v1.md`.
  **Acceptance**: `user-chores-v1` references `template_shared.chore_row_user_chores_v1` and production helper names use release-ready terminology. 3. [x] Introduce template-level `button_card_templates` block in `user-chores-v1` and move row logic there (instead of inline row object assembly).
  **Files**: `choreops-dashboards/templates/user-chores-v1.yaml` (row include anchor line 522), optional shared helper source in `choreops-dashboards/templates/shared/`.
  **Acceptance**: chore row instances reference the template (`template: ...`) and pass variables for translation/prefs instead of duplicating row logic inline. 4. [x] Align claim/undo/action behavior exactly with row-reference semantics and block-state fallbacks. **Moved to Phase 4A**
  **Files**: `choreops-dashboards/templates/user-chores-v1.yaml` (row action wiring region), `choreops-dashboards/docs/shared_button_card_dashboard_reference_v2.yaml` (action block near row definition).
  **Acceptance**: claimed, completed, blocked, steal-window, and in-part states produce equivalent action/icon/tap outcomes. 5. [x] Expand template contract tests to assert template-definition semantics (not only snippet markers).
  **Files**: `tests/test_dashboard_template_contract.py` (existing marker test anchor line 57), `tests/test_dashboard_template_render_smoke.py` (user render test anchor line 20).
  **Acceptance**: tests verify presence/use of button-card templates and ensure render output remains parse-valid. 6. [x] Add behavior regression tests for row-state mapping and action routing parity. **Moved to Phase 4A**
  **Files**: new focused test module under `tests/test_dashboard_*`, plus `tests/test_dashboard_manifest_dependencies_contract.py` (dependency coverage anchor line 115) as needed.
  **Acceptance**: test cases cover all row-reference-relevant states (`claimed`, `completed`, `completed_in_part`, `overdue`, blocked claim modes, `steal_available`). 7. [x] Re-sync canonical to vendored outputs and verify parity remains deterministic in local sync + release-apply paths.
  **Files**: `utils/sync_dashboard_assets.py` (compose anchors lines 71 and 110), `custom_components/choreops/helpers/dashboard_helpers.py` (release apply anchors lines 103 and 201).
  **Acceptance**: no unresolved markers in runtime templates; same source yields deterministic vendored outputs. 8. [x] Run targeted validation suite and capture parity evidence before re-closing Phase 3.
  **Files**: `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_BUILDER_HANDOFF_PHASE3B.md` (execution evidence log), this plan file.
  **Acceptance**: all Phase 3B commands pass; parity matrix has zero unresolved `partial/missing` rows; summary table updated with evidence references.

9. [x] Add parser-contract remediation in **local sync** so nested shared fragment ids (`/`) are accepted per guide contract.
       **Files**: `utils/sync_dashboard_assets.py`, `tests/test_sync_dashboard_assets.py` (new/updated).
       **Acceptance**: sync compose + `--check` pass with nested fragment-id fixture inputs.
10. [x] Add parser-contract remediation in **online release-download apply** with matching nested-fragment-id behavior.
        **Files**: `custom_components/choreops/helpers/dashboard_helpers.py`, `tests/test_dashboard_release_asset_apply.py`.
        **Acceptance**: release-apply compose path passes nested fragment-id fixture inputs before write.
11. [x] Add dual-path parser parity tests and closure evidence in 3B handoff.
        **Files**: `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_BUILDER_HANDOFF_PHASE3B.md`, targeted test modules above.
        **Acceptance**: explicit evidence shows both local sync and online release-download apply paths pass the same nested-fragment-id cases.

- **Key issues** - Existing “composition complete” status does not guarantee button-card template parity.
  - Current tests are strong on syntax/contracts but weak on row template semantics and state-to-action parity assertions.
  - Current 3B closeout must also prove parser-contract parity across both ingestion paths (local sync + online release download), not row behavior alone.
  - Remaining user-template parity scope is now tracked and executed in Phase 4A.

### Phase 4A – User template UX completion

- **Goal**: Consolidate and complete all remaining user-template UX/parity work without reopening pre-3C phase ordering.
- **Steps / detailed work items** 1. [x] Finalize design of `user-chore-essentials-v1`.
  **Files**: `choreops-dashboards/templates/user-chore-essentials-v1.yaml`, `choreops-dashboards/preferences/user-chore-essentials-v1.md`, `choreops-dashboards/dashboard_registry.json`.
  **Finalization gate (required for this step)**: parity tests, translation coverage, and post-change sync/contract validation. 2. [x] Finalize design of `user-chores-v1`, then remove `user-essential-v1.yaml`.
  **Files**: `choreops-dashboards/templates/user-chores-v1.yaml`, `choreops-dashboards/templates/user-essential-v1.yaml` (remove), `choreops-dashboards/preferences/user-chores-v1.md`, `choreops-dashboards/preferences/user-essential-v1.md` (deprecate/remove), `choreops-dashboards/dashboard_registry.json`.
  **Finalization gate (required for this step)**: parity tests, translation coverage, and post-change sync/contract validation. 3. [ ] Create and finalize a kid-focused chores template version (stripped-down `user-chores` variant with larger/friendlier button-card tiles, while keeping baseline color/state/action semantics aligned to `user-chores-v1`).
  **Files**: `choreops-dashboards/templates/user-kids-chores-v1.yaml` (new), `choreops-dashboards/preferences/user-kids-chores-v1.md` (new), `choreops-dashboards/dashboard_registry.json`, related docs in `docs/DASHBOARD_TEMPLATE_GUIDE.md`.
  **Finalization gate (required for this step)**: parity tests, translation coverage, and post-change sync/contract validation. 4. [ ] Create and finalize a modern gamification template version.
  **Files**: `choreops-dashboards/templates/user-gamification-v2.yaml` (new), `choreops-dashboards/preferences/user-gamification-v2.md` (new), `choreops-dashboards/dashboard_registry.json`, related docs in `docs/DASHBOARD_TEMPLATE_GUIDE.md`.
  **Finalization gate (required for this step)**: parity tests, translation coverage, and post-change sync/contract validation. 5. [ ] Capture 4A closure evidence and release readiness notes.
  **Files**: `docs/in-process/DASHBOARD_UX_MODERNIZATION_IN-PROCESS.md`, `docs/RELEASE_CHECKLIST.md`.
- **Key issues**
  - Preserve strict template contract and dependency declarations as user templates evolve.
  - Avoid introducing custom-card development scope beyond existing ecosystem cards.
  - Keep single-path compile/parity guarantees intact during UX iteration.

### Phase 3C – Single-path contract enforcement

- **Goal**: Remove remaining template ingestion divergence by enforcing one compile pipeline across create/update/release paths with registry-backed shared-contract validation.
- **Steps / detailed work items**
  1. [x] Execute Phase 3C Phase 1 (contract and source-of-truth lock) from `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_BUILDER_HANDOFF_PHASE3C.md`.
         **Files**: `choreops-dashboards/dashboard_registry.json`, `custom_components/choreops/helpers/dashboard_helpers.py`, `docs/DASHBOARD_TEMPLATE_GUIDE.md`.
  2. [x] Execute Phase 3C Phase 2 (single compile pipeline) from `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_BUILDER_HANDOFF_PHASE3C.md`.
         **Files**: `custom_components/choreops/helpers/dashboard_helpers.py`, `custom_components/choreops/helpers/dashboard_builder.py`, `utils/sync_dashboard_assets.py`.
  3. [x] Execute Phase 3C Phase 3 (validation and parity gates) from `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_BUILDER_HANDOFF_PHASE3C.md`.
         **Files**: `tests/test_dashboard_release_asset_apply.py`, `tests/test_sync_dashboard_assets.py`, `tests/test_dashboard_manifest_dependencies_contract.py`, `tests/test_options_flow_dashboard_release_selection.py`.
  4. [x] Execute Phase 3C Phase 4 (docs and rollout closure) and capture evidence.
         **Files**: `docs/DASHBOARD_TEMPLATE_GUIDE.md`, `docs/RELEASE_CHECKLIST.md`, `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_BUILDER_HANDOFF_PHASE3C.md`.
- **Key issues**
  - Registry contract fields must be validator metadata, not a second composition source.
  - No `.storage` schema changes are expected for 3C; avoid mixing dashboard contract work with data model migrations.

### Phase 4 – Admin modernization + docs/polish

- **Goal**: Modernize admin templates with the same UX language and finalize docs/tests/options-flow readiness for production use.
- **Steps / detailed work items**
  1. [ ] Add additive admin variants (`admin-shared-v2.yaml`, `admin-peruser-v2.yaml`) with modernized header/action cards and preserved selector/helper validation flows.
         **Files**: `choreops-dashboards/templates/admin-shared-v2.yaml` (new), `choreops-dashboards/templates/admin-peruser-v2.yaml` (new).
         **Line anchors**: current admin baselines lines 1-50 in both v1 templates.
  2. [ ] Register admin v2 templates in canonical registry with dependency declarations and preference docs; ensure admin mode routing remains compatible.
         **Files**: `choreops-dashboards/dashboard_registry.json`, `choreops-dashboards/preferences/admin-shared-v2.md` + `admin-peruser-v2.md` (new).
         **Line anchors**: admin template IDs and contracts in registry lines 69-125.
  3. [ ] Validate template-select behavior and defaults in integration helper logic (especially default admin template selection and template normalization) for mixed v1/v2 availability.
         **Files**: `custom_components/choreops/helpers/dashboard_helpers.py`, `custom_components/choreops/options_flow.py`.
         **Line anchors**: default admin template selectors at `dashboard_helpers.py` lines 985-1008; configure step in `options_flow.py` lines 4081-4636.
  4. [ ] Expand/adjust dashboard tests for render smoke, registry/dependency contracts, and flow selection behavior with new template IDs.
         **Files**: `tests/test_dashboard_template_render_smoke.py`, `tests/test_dashboard_manifest_dependencies_contract.py`, `tests/test_options_flow_dashboard_release_selection.py` (and related dashboard flow tests).
         **Line anchors**: smoke render tests lines 1-47; dependency contract lines 33-152.
  5. [ ] Update dashboard docs with v2 naming, migration guidance, and UX design constraints (including HA practical limitations and “no custom card development” scope).
         **Files**: `docs/DASHBOARD_TEMPLATE_GUIDE.md`, `docs/DASHBOARD_UI_DESIGN_GUIDELINE.md`, optional wiki pages in `choreops-wiki/` for user-facing rollout notes.
         **Line anchors**: guide authority/workflow sections lines 9-85; UI guideline scope/state sections lines 6-101.
  6. [ ] Perform final parity + quality gate checklist and capture release readiness notes.
         **Files**: `docs/RELEASE_CHECKLIST.md`, `docs/in-process/DASHBOARD_UX_MODERNIZATION_IN-PROCESS.md` (this file updates).
         **Line anchors**: update Summary table and phase statuses in this plan after each completed gate.
- **Key issues**
  - Introducing multiple v2 templates may require clear UX labeling to avoid user confusion in template selectors.
  - Admin modernization must keep actionable clarity for high-density operational tasks.

## Validation commands (execution phase requirements)

Run during implementation phases (Builder/UX Builder):

1. `python utils/sync_dashboard_assets.py`
2. `python utils/sync_dashboard_assets.py --check`
3. `./utils/quick_lint.sh --fix`
4. `mypy custom_components/choreops/`
5. `python -m pytest tests/ -v --tb=line`
6. Focused dashboard regression pass (recommended):
   `python -m pytest tests/test_dashboard_template_render_smoke.py tests/test_dashboard_manifest_dependencies_contract.py tests/test_dashboard_template_contract.py -v --tb=line`

## Migration and schema impact

- **Storage schema change required**: **No**.
- **`meta.schema_version` increment required**: **No** (dashboard/templates/docs/utilities only; no `.storage/choreops/choreops_data` schema changes).
- **Compatibility note**: Template IDs must still satisfy regex compatibility (`^[a-z0-9]+-[a-z0-9-]+-v[0-9]+$`); backward compatibility with prior user-facing template naming is not required yet because this UX feature set is not released.

## Translation keys (planned usage)

Re-use existing dashboard translation constants in `custom_components/choreops/const.py` where applicable:

- `TRANS_KEY_CFOF_DASHBOARD_TEMPLATE_PROFILE` (line 3370)
- `TRANS_KEY_CFOF_DASHBOARD_ADMIN_MODE` (line 3383)
- `TRANS_KEY_CFOF_DASHBOARD_ADMIN_TEMPLATE_GLOBAL` (line 3384)
- `TRANS_KEY_CFOF_DASHBOARD_ADMIN_TEMPLATE_PER_ASSIGNEE` (line 3387)
- `TRANS_KEY_CFOF_DASHBOARD_RELEASE_SELECTION` (line 3393)
- `TRANS_KEY_EXC_DASHBOARD_STATUS_UPDATED` (line 3420)
- `TRANS_KEY_EXC_DASHBOARD_STATUS_CREATED` (line 3421)
- `TRANS_KEY_EXC_DASHBOARD_STATUS_RECOMMENDED_DEPS_MISSING` (line 3428)

If new user-facing options/status text is introduced for UX iteration workflow, add new `TRANS_KEY_*` constants + `translations/en.json` entries in the same PR.

## Deliverables checklist

- [x] New agent spec created for dashboard UX implementation (`.github/agents/dashboard-ux-builder.agent.md`)
- [x] Live preload utility modernized for scenario-based local testing
- [x] New user templates: user-chore-essentials-v1 + user-chores-v1
- [x] Shared-template composition parity implemented for sync + release-apply flows
- [ ] New additive admin templates: shared-v2 + peruser-v2
- [ ] Registry/preferences/translations updated in canonical dashboard repo
- [x] Vendored assets synced + parity verified
- [x] Dashboard tests updated and passing
- [x] Dashboard docs updated (template guide + UI guideline + release notes) — foundational boundary/contract updates completed in Phase 1
- [ ] User-template modernization/parity closure completed under Phase 4A
