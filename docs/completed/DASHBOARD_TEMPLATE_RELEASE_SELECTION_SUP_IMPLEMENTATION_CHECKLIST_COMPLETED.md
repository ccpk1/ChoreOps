# Dashboard Template Release Selection - Implementation Checklist

---
status: READY_FOR_HANDOFF
owner: Strategist Agent
created: 2026-02-14
parent_plan: DASHBOARD_TEMPLATE_RELEASE_SELECTION_IN-PROCESS.md
handoff_from: KidsChores Strategist
handoff_to: KidsChores Plan Agent
phase_focus: End-to-end implementation execution order
---

## Handoff button

[HANDOFF_TO_BUILDER_IMPLEMENT_NOW](DASHBOARD_TEMPLATE_RELEASE_SELECTION_SUP_BUILDER_HANDOFF.md)

## Purpose

Provide an execution-ready, file-by-file implementation sequence for the locked UX and compatibility gate behavior.

## Execution order (must follow)

1. Constants and contracts (`const.py`)
2. Resolver and compatibility logic (`dashboard_builder.py`)
3. Form schema changes (`dashboard_helpers.py`)
4. Options flow orchestration (`options_flow.py`)
5. Translation keys/copy (`translations/en.json`)
6. Tests (new test files)
7. Quality gates + handback evidence

## File-by-file implementation tasks

### 1) `custom_components/kidschores/const.py`

- Add release source constants:
  - dashboard repo owner/name
  - release API endpoint and raw template URL pattern by ref/tag
- Add release-mode constants:
  - `latest_compatible`
  - `pin_release`
- Add compatibility-floor constants:
  - minimum compatible dashboard release tag/range
  - optional compatibility map structure for MVP fallback
- Add options-flow field constants for locked UX:
  - Step 1 action, dashboard selector, create name
  - Update-only release controls
  - Step 2 kid/admin/display controls
- Add translation key constants for new field labels/errors and result messages.

### 2) `custom_components/kidschores/helpers/dashboard_builder.py`

- Add release parser/normalizer for tags:
  - support `KCD_vX.Y.Z_betaN` and `KCD_vX.Y.Z`
  - reject malformed tags safely
- Add compatibility evaluator:
  - compare installed integration version against min/max compatibility metadata
- Add release discovery helper:
  - call GitHub releases API
  - parse + sort + filter compatible candidates
- Add selection resolver:
  - `latest_compatible` default path
  - pinned tag path with fallback to latest compatible
- Keep fallback chain non-destructive:
  1. selected release template
  2. fallback compatible release template
  3. local bundled template
- Ensure create path can create blank dashboard shell for Step 1 `Create` before Step 2 customization.

### 3) `custom_components/kidschores/helpers/dashboard_helpers.py`

- Implement Step 1 schemas:
  - CRUD action selector
  - create name input (create path only)
  - dashboard selector (update/delete, single-select)
  - update-only advanced release controls
- Implement Step 2 schema sections:
  - Section A: kid selection + kid template profile (no per-kid override)
  - Section B: admin mode + conditional admin template selectors
  - Section C: display/visibility (sidebar/admin/icon)
- Keep selectors simple and deterministic (no hidden secondary branches beyond locked spec).

### 4) `custom_components/kidschores/options_flow.py`

- Implement Step 1 CRUD hub routing:
  - Create: name -> create empty dashboard -> Step 2
  - Update: select existing -> Step 2
  - Delete: select existing -> confirm -> execute -> return Step 1
  - Exit: return to previous menu
- Enforce release controls only for Update path.
- Implement Step 2 validation contract exactly:
  - block if no kids and admin mode `none`
  - block global admin mode missing global template
  - block per-kid mode missing per-kid template
  - block per-kid mode with zero kids selected
- Apply Step 2 configuration updates and return user to Step 1 with result summary.
- Ensure fallback/result messaging includes compatibility and source-resolution outcomes.

### 5) `custom_components/kidschores/translations/en.json`

- Add/adjust step titles and descriptions for:
  - Step 1 CRUD hub
  - Delete confirmation
  - Step 2 sections and fields
- Add labels/descriptions for update-only release controls.
- Add validation error strings for missing template requirements by admin mode.
- Add result-state strings for release fallback outcomes.

## Tests to add

### A) `tests/test_dashboard_template_release_resolution.py`

- newest compatible selection from mixed tags
- pinned tag success
- pinned incompatible tag rejection/fallback
- malformed tags ignored
- floor enforcement using integration version

### B) `tests/test_dashboard_builder_release_fetch.py`

- API timeout/rate-limit/network failure -> bundled fallback
- selected tag missing template -> fallback release/local
- local bundled fallback available after simulated remote failure

### C) `tests/test_options_flow_dashboard_release_selection.py`

- Step 1 CRUD routing: create/update/delete/exit
- update-only visibility of release controls
- delete confirm -> return to CRUD hub
- Step 2 validation contract cases
- result copy for fallback and compatibility decisions

## Acceptance evidence required in handback

- Diff list grouped by file area (const/resolver/forms/flow/translations/tests)
- Test output snippets for each new test file
- Quality gate outputs:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/kidschores/`
  - focused `pytest` files above
- Manual UX walkthrough summary:
  - create blank -> configure -> apply
  - update existing with release controls
  - delete confirm and return

## Risk controls during build

- Keep existing dashboard dedupe/safe-update behavior intact.
- Do not introduce per-kid template override controls in this iteration.
- Do not expose user override for minimum compatibility floor.
- Preserve bundled template recovery path as hard safety net.

## Out of scope (do not implement in this handoff)

- persistent per-dashboard release pin storage model redesign
- scheduled template auto-updates
- admin role/permission matrix changes
- multi-repo template source support
