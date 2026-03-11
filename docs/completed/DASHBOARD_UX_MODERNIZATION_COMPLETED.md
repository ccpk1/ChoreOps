# Initiative plan: Dashboard UX modernization + rapid design iteration

## Initiative snapshot

- **Name / Code**: Dashboard UX modernization + rapid design iteration (`DASHBOARD_UX_MODERNIZATION`)
- **Target release / milestone**: v0.5.x dashboard UX track (multi-PR)
- **Owner / driver(s)**: ChoreOps maintainers + dashboard design/build contributors
- **Status**: Complete

## Summary & immediate steps

| Phase / Step                                | Description                                                                                                          | % complete | Quick notes                                                                                                          |
| ------------------------------------------- | -------------------------------------------------------------------------------------------------------------------- | ---------: | -------------------------------------------------------------------------------------------------------------------- |
| Phase 1 – UX foundation + tooling           | Create UX-focused dashboard builder agent and standardize template naming/version strategy                           |        100 | Completed: agent created, boundaries codified, toolkit linked                                                        |
| Phase 2 – Dev preload workflow              | Make rapid local dashboard testing easy using scenario-based live preload tooling                                    |        100 | Completed: script modernized + docs + targeted tests                                                                 |
| Phase 3 – User template modernization       | Build lightweight inline chore-essentials first, then full-featured chores template from the v2 shared-row reference |        100 | Essentials + chores v1 drafted and composition-ready                                                                 |
| Phase 3A – Template composition parity      | Ensure shared-template composition behaves identically in local sync and remote release apply                        |        100 | Shared contract + sync/release parity + safety tests complete                                                        |
| Phase 3B – Row template parity recovery     | Rebuild `user-chores-v1` around true `button_card_templates` semantics and prove behavior parity                     |        100 | Closed as migration closeout; remaining user-template scope moved to Phase 4A                                        |
| Phase 3C – Single-path contract enforcement | Unify create/update/release template handling under one compile path with registry-backed shared contract validation |        100 | Hard-fork path complete: no hoist, root-template contract, strict canonical↔vendored parity, targeted suites passing |
| Phase 4A – User template UX completion      | Complete remaining user-template behavior parity and modernization follow-up                                         |        100 | Steps 1-5 complete; Gamification Premier finalized under the approved hard-fork taxonomy                             |
| Phase 4 – Admin modernization + docs/polish | Modernize admin templates and finalize docs/contracts/validation checklist                                           |        100 | Completed for the current v1 admin scope; additive admin v2 work is tracked separately                               |
| Phase 4B – Admin shared state contract      | Define the persistent `ui_control` ownership model and root-key contract for shared admin dashboards                 |        100 | Completed and implemented; shared/per-user ownership split, snippet contract, and release-gate validation landed     |

1. **Key objective** – Deliver modern, app-like dashboards with strong runtime stability.
2. **Summary of recent work** – Phase 4B landed the shared-admin system helper sensor, snippet-provided `ui_root.shared_admin` and `ui_root.selected_user`, canonical and vendored admin template ownership split, per-user admin stabilization, shared fragment extraction for duplicated admin content, renderer support for `template_shared` composition in direct render paths, and focused release-gate validation.
3. **Next steps (short term)** – No remaining implementation work is required for this initiative. Any additive admin v2 template work is a separate follow-up effort and not part of this completed plan.
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

- `docs/completed/DASHBOARD_UX_MODERNIZATION_PHASE4B_SHARED_ADMIN_UI_CONTROL_COMPLETED.md`
- `docs/completed/DASHBOARD_UX_MODERNIZATION_PHASE4B_SHARED_ADMIN_UI_CONTROL_SUP_BUILDER_HANDOFF.md`
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

- **Completion confirmation**: `[x]` All follow-up items completed (agent + preload + templates + docs + parity + validation) before owner sign-off.

> **Important:** Keep this Summary table current after each phase-level implementation milestone.

## Tracking expectations

- **Summary upkeep**: Update percentages, blockers, and quick notes after each phase completion.
- **Detailed tracking**: Keep implementation granularity in phase sections; keep Summary high-level.
- **Validation execution policy**: Run lint and tests only in an actual terminal session. For pytest, the only acceptable invocation pattern going forward is `python -m pytest ...`.
- **Mid-phase validation policy**: Use targeted terminal pytest commands while implementation is still in progress.
- **Completion-gate validation policy**: Reserve `python -m pytest tests/ -v --tb=line` for the point where the phase or code change set is believed complete.

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

- **Verified local reload workflow**:

```bash
cd /workspaces/choreops && TOKEN="$(python - <<'PY'
from pathlib import Path
import re

text = Path('docs/completed/DASHBOARD_UX_MODERNIZATION_COMPLETED.md').read_text(
  encoding='utf-8'
)
match = re.search(
  r"Dev instance token \(sandbox\)\*\*:\s*\n\s*`([^`]+)`",
  text,
)
if not match:
  raise SystemExit('Sandbox token block not found')
print(match.group(1))
PY
)" && /workspaces/choreops/.venv/bin/python utils/load_test_scenario_to_live_ha.py --scenario tests/scenarios/scenario_ux_states.yaml --ha-url http://localhost:8123 --reset --seed-states --token "$TOKEN"
```

This avoids prompt handling and reuses the documented sandbox token without hardcoding a line number.

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
  **Finalization gate (required for this step)**: parity tests, translation coverage, and post-change sync/contract validation. 3. [x] Finalize the kid-focused chores presentation path (pre-release consolidation folded the larger/friendlier kids row variant into `user-chores-v1` instead of shipping a separate template, while keeping baseline color/state/action semantics aligned to `user-chores-v1`).
  **Files**: `choreops-dashboards/templates/user-chores-v1.yaml`, `choreops-dashboards/preferences/user-chores-v1.md`, `choreops-dashboards/dashboard_registry.json`, related docs in `docs/DASHBOARD_TEMPLATE_GUIDE.md`.
  **Finalization gate (required for this step)**: parity tests, translation coverage, and post-change sync/contract validation. 4. [x] Create and finalize the modern gamification user template under the approved hard-fork taxonomy as `user-gamification-premier-v1`.
  **Files**: `choreops-dashboards/templates/user-gamification-premier-v1.yaml`, `choreops-dashboards/preferences/user-gamification-premier-v1.md`, `choreops-dashboards/dashboard_registry.json`, related docs in `docs/DASHBOARD_TEMPLATE_GUIDE.md`.
  **Finalization gate (required for this step)**: parity tests, translation coverage, and post-change sync/contract validation. 5. [x] Capture 4A closure evidence and release readiness notes.
  **Files**: `docs/completed/DASHBOARD_UX_MODERNIZATION_COMPLETED.md`, `docs/RELEASE_CHECKLIST.md`.
- **Key issues**
  - Preserve strict template contract and dependency declarations as user templates evolve.
  - Avoid introducing custom-card development scope beyond existing ecosystem cards.
  - Keep single-path compile/parity guarantees intact during UX iteration.

#### Phase 4A closure decisions ratified

- [x] Confirm the dashboard state layering standard: `pref_*` remains the template-authored default layer, reviewed `ui_control` keys remain durable per-user overrides, and any future temporary header/filter interactions stay separate from durable persisted state until a dedicated transient pattern is approved.
- [x] Confirm the long-term top-level `ui_control` namespace strategy for dashboard keys: the current approved pattern remains feature/surface namespaces under `gamification/*`, with template-level defaults still authored through `pref_*`.

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
- **Scope closeout note**: This initiative completed the intended admin modernization scope using the current admin template family. Additive `admin-shared-v2` and `admin-peruser-v2` work was intentionally split into a separate follow-up effort and is not an open item for this plan.
- **Steps / detailed work items** 0. [x] Complete Phase 4B and ratify the shared-admin `ui_control` ownership contract before continuing admin template refinement.
  **Files**: `docs/completed/DASHBOARD_UX_MODERNIZATION_COMPLETED.md`, `docs/DASHBOARD_TEMPLATE_GUIDE.md`.
  **Line anchors**: Phase 4B section in this plan; dashboard state-layering guidance in the template guide.
  1. [x] Modernize the current shared and per-user admin templates under the approved shared-admin ownership contract while preserving selector/helper validation flows.
         **Files**: `choreops-dashboards/templates/admin-shared-v1.yaml`, `choreops-dashboards/templates/admin-peruser-v1.yaml`, synced vendored runtime outputs.
         **Line anchors**: current admin baselines and finalized v1 implementation.
  2. [x] Update canonical registry/contracts and supporting admin assets for the finalized admin template scope.
         **Files**: `choreops-dashboards/dashboard_registry.json`, canonical/vendored dashboard assets, supporting preference and contract updates made during admin stabilization.
         **Line anchors**: admin template registry entries and shared fragment contract metadata.
  3. [x] Validate template-select behavior and admin render compatibility in integration helper logic for the finalized admin scope.
         **Files**: `custom_components/choreops/helpers/dashboard_helpers.py`, `custom_components/choreops/helpers/dashboard_builder.py`, `custom_components/choreops/options_flow.py`.
         **Line anchors**: admin render context, local/shared fragment composition, and admin template normalization paths.
  4. [x] Expand/adjust dashboard tests for render smoke, contract coverage, and admin behavior stabilization.
         **Files**: `tests/test_dashboard_template_render_smoke.py`, `tests/test_dashboard_template_contract.py`, related focused dashboard validation.
         **Line anchors**: admin render smoke and contract assertions for shared/per-user templates.
  5. [x] Update dashboard docs and plan records for the finalized admin scope and closed ownership contract.
         **Files**: `docs/DASHBOARD_TEMPLATE_GUIDE.md`, `docs/DASHBOARD_UI_DESIGN_GUIDELINE.md`, `docs/completed/DASHBOARD_UX_MODERNIZATION_COMPLETED.md`, supporting completed-phase records.
         **Line anchors**: guide authority/workflow sections and Phase 4B closeout records.
  6. [x] Perform final parity + quality gate checklist and capture release readiness notes for this initiative scope.
         **Files**: `docs/RELEASE_CHECKLIST.md`, `docs/completed/DASHBOARD_UX_MODERNIZATION_COMPLETED.md`, validation/test evidence recorded in completed and in-process support docs.
         **Line anchors**: summary table, closeout note, and focused validation references.
- **Key issues**
  - Any future additive admin v2 template family should remain clearly separated from this completed v1-scope initiative.
  - Admin dashboards must continue to keep actionable clarity for high-density operational tasks.

### Phase 4B – Admin shared state contract

- **Goal**: Resolve shared-admin `ui_control` ownership before implementation so every top-level admin card writes to one intentional state owner and one stable root-key taxonomy.
- **Archive summary**: `docs/completed/DASHBOARD_UX_MODERNIZATION_PHASE4B_SHARED_ADMIN_UI_CONTROL_COMPLETED.md`
- **Supporting archive**: `docs/completed/DASHBOARD_UX_MODERNIZATION_PHASE4B_SHARED_ADMIN_UI_CONTROL_SUP_BUILDER_HANDOFF.md`
- **Pre-builder prerequisite**: complete dashboard sync/test/doc cleanup and commit it before any Phase 4B integration changes, so rollback to pre-Builder integration state is always safe and explicit.
- **Issue statement**
  - The current shared-admin direction risks conflating three different concerns: page-owned chrome state, selected-user workflow state, and bootstrap/fallback helper usage.
  - `admin-shared-v1` currently reads and writes some section state through a changing helper context, which makes header persistence, visibility gating, and background treatments harder to reason about when the managed user changes.
  - Admin modernization needs one approved ownership model before `admin-shared-v2` is built, otherwise the v2 work will encode inconsistent persistence rules into the new baseline.
- **Phase 4B decisions ratified (pre-implementation lock)**
  - Shared-admin persisted state will be stored at `data/meta/shared_admin_ui_control`.
  - A dedicated system dashboard helper sensor will be introduced for shared-admin page state.
  - System helper `purpose` will be `purpose_system_dashboard_helper`.
  - System helper language strategy:
    - derive language from user languages in the config entry
    - majority language wins
    - tie-breaker is the first user with approver role
    - fallback language is English (`en`) if an unexpected gap occurs
  - System helper minimum attributes:
    - `purpose`
    - `language`
    - `integration_entry_id`
    - `ui_control`
    - `user_dashboard_helpers` (initially minimal, to enable direct helper targeting and reduce repeated broad lookups)
      - this field is pointer-focused (helper identity lookup), not a second full helper payload mirror
  - Shared-admin template direction remains a single-template strategy:
    - shared mode must be designed so user selection can later be stripped and bound to one fixed target user without creating a separate maintenance-heavy admin template family.
- **Steps / detailed work items**
  1. [x] Document the approved ownership boundary for shared-admin state: which controls are page-owned, which controls are selected-user-owned, and which controls should remain non-persistent.
         **Files**: `docs/completed/DASHBOARD_UX_MODERNIZATION_COMPLETED.md`, `docs/DASHBOARD_TEMPLATE_GUIDE.md`.
         **Line anchors**: this Phase 4B section; dashboard state-layering guidance added under admin template conventions.
  2. [x] Decide the storage owner for page-level shared-admin state and record the rationale.
         **Files**: `docs/completed/DASHBOARD_UX_MODERNIZATION_COMPLETED.md`.
         **Decision options**: dedicated system dashboard helper sensor, selected-user helper, or another explicit page-scoped helper model.
  3. [x] Ratify the root-key contract for shared-admin surfaces under one namespace pattern.
         **Files**: `docs/completed/DASHBOARD_UX_MODERNIZATION_COMPLETED.md`, `docs/DASHBOARD_TEMPLATE_GUIDE.md`.
         **Proposed shape**: `admin-shared/<section>/<value>` for page-owned state, with any approved per-user workflow keys explicitly separated and documented.
  4. [x] Define the shared-admin helper entity contract before template changes begin.
         **Files**: `docs/completed/DASHBOARD_UX_MODERNIZATION_COMPLETED.md`, `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT_STANDARDS.md`.
         **Contract scope**: purpose value, entity type, minimum attributes, translation/purpose metadata, `ui_control` exposure, and whether the helper exposes only page state or also lightweight lookup metadata.
  5. [x] Lock dynamic helper-resolution rules in reusable snippets so shared-admin templates never construct helper entity ids manually.
         **Files**: `docs/completed/DASHBOARD_UX_MODERNIZATION_COMPLETED.md`, `docs/DASHBOARD_TEMPLATE_GUIDE.md`.
         **Snippet scope**: extend the existing shared-admin setup snippet by default (only split into a dedicated snippet if required by maintainability constraints), and resolve the system helper by `purpose` + `integration_entry_id`, mirroring the existing selector-resolution contract.
  6. [x] Define the render/gating contract for top-level shared-admin cards so empty-selection states show intentional guidance cards rather than disappearing sections.
         **Files**: `docs/completed/DASHBOARD_UX_MODERNIZATION_COMPLETED.md`, `docs/DASHBOARD_UI_DESIGN_GUIDELINE.md`.
         **Examples**: selector not chosen, selected helper unavailable, selected helper missing expected helper entities.
  7. [x] Define service/write-path expectations for the shared-admin helper so `manage_ui_control` mutations remain entry-scoped, owner-consistent, and testable.
         **Files**: `docs/completed/DASHBOARD_UX_MODERNIZATION_COMPLETED.md`, `docs/DEVELOPMENT_STANDARDS.md`.
         **Scope**: owner resolution, one-owner-per-card rule, and prohibition on mixed-owner reads/writes inside a single render block.
         **Implementation note**: update the service contract as needed to support system-helper-backed state writes without forcing pseudo-user identifiers.
  8. [x] Define helper-target resolution optimization using identity pointers instead of repeated broad domain scans.
         **Files**: `docs/completed/DASHBOARD_UX_MODERNIZATION_COMPLETED.md`, `docs/ARCHITECTURE.md`, `docs/DEVELOPMENT_STANDARDS.md`.
         **Scope**: use user identity linkage (unique-id driven mapping) to resolve each user's dashboard helper entity id directly from `user_dashboard_helpers`, with domain query reserved for resolving the single system helper sensor.
  9. [x] Lock ui-root ownership rules for template reuse scenarios.
         **Files**: `docs/completed/DASHBOARD_UX_MODERNIZATION_COMPLETED.md`, `docs/DASHBOARD_TEMPLATE_GUIDE.md`.
         **Rule**: each card attaches `ui_root` to exactly one owner (`system helper` for page chrome or `user helper` for per-user workflow), never both in one render path.
  10. [x] Lock the implementation checklist for Builder before template edits start.
          **Files**: `docs/completed/DASHBOARD_UX_MODERNIZATION_COMPLETED.md`.
          **Checklist scope**: owner entity, purpose naming, attribute contract, translation coverage, snippet resolution, root-key naming, default-collapse semantics, gating rules, background/tint behavior, and test expectations.
- **Key issues**
  - A shared admin page needs stable page chrome even while the managed user changes; page-level header collapse state should not drift between user helper contexts unless that is an explicit, approved requirement.
  - If a dedicated system dashboard helper sensor is introduced, keep it minimal and clearly scoped so it does not become a second user-helper model with overlapping responsibilities.
  - Root-key design must stay simple enough to reason about during rapid UX iteration: one namespace per surface, one owner per card, no mixed-owner reads/writes inside the same render block.
  - Helper discovery must be entirely metadata-driven (`purpose` + `integration_entry_id` and other stable attributes when needed), not entity-id-string-driven.
  - Platinum-quality expectations apply here too: clean naming, centralized snippet logic, explicit contracts, and targeted validation coverage for creation, lookup, and render behavior.
  - `user_dashboard_helpers` must remain intentionally small and deterministic to avoid replacing one expensive broad lookup with a second large dynamic payload.
  - Identity-pointer resolution must be deterministic and covered by tests so helper eid targeting is stable across reloads and ordering changes.
  - Language derivation behavior must be deterministic and covered by tests, including tie and missing-language scenarios.
  - Cleanup churn from dashboard sync is expected during this phase, but must be isolated into a standalone cleanup commit before Builder begins integration-side work.

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

- **Storage schema change required**: **Yes** (add `data/meta/shared_admin_ui_control`).
- **`meta.schema_version` increment required**: **Yes** (`45`, because this work is pre-release for users and still in build phase).
- **Compatibility note**: This remains a hard-fork UX track, but migration logic is still required for existing local storage instances when introducing the new `meta` branch.
- **Template compatibility note**: Template IDs must still satisfy regex compatibility (`^[a-z0-9]+-[a-z0-9-]+-v[0-9]+$`).

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
- [x] Shared and per-user admin templates modernized and stabilized for the finalized v1 admin scope
- [x] Registry/preferences/translations/contracts updated in the canonical dashboard repo for the finalized scope
- [x] Vendored assets synced + parity verified
- [x] Dashboard tests updated and passing
- [x] Dashboard docs updated (template guide + UI guideline + release notes) — foundational boundary/contract updates completed in Phase 1
- [x] User-template modernization/parity closure completed under Phase 4A

## Open items outside this completed plan

- Additive `admin-shared-v2` and `admin-peruser-v2` template work, if pursued later, belongs to a separate follow-up initiative and is intentionally not tracked as open work here.
