# Dashboard Template Release Selection - Builder Handoff

---
status: READY_FOR_HANDOFF
owner: Strategist Agent
created: 2026-02-14
parent_plan: DASHBOARD_TEMPLATE_RELEASE_SELECTION_IN-PROCESS.md
handoff_from: KidsChores Strategist
handoff_to: KidsChores Plan Agent
phase_focus: Phase 1 policy lock + Phase 2 resolver MVP
---

## Handoff button

[HANDOFF_TO_BUILDER_RELEASE_SELECTION_MVP](DASHBOARD_TEMPLATE_RELEASE_SELECTION_IN-PROCESS.md)

## Implementation runbook

- [Execution checklist](DASHBOARD_TEMPLATE_RELEASE_SELECTION_SUP_IMPLEMENTATION_CHECKLIST.md)

## Handoff objective

Implement release-aware dashboard template selection that:
1) Defaults to newest compatible dashboard release,
2) Allows user-selected pinning to a specific release, and
3) Enforces a minimum compatible release floor.

## UX allow/restrict contract (must implement exactly)

1. Step 1 is a single CRUD hub with actions: `create`, `update`, `delete`, `exit`.
2. `create` action takes dashboard name only, creates blank dashboard, then routes to Step 2.
3. `delete` action uses same single dashboard selector as `update`, requires confirm, then returns to Step 1.
4. Show `release_mode` only on Step 1 `update` path (advanced collapsed):
  - `latest_compatible` (default)
  - `pin_release`
5. Show `release_tag` selector **only** when `pin_release` is selected.
6. `release_tag` options must come from parsed compatible releases only:
  - allow: tags meeting minimum floor and parser contract
  - restrict: below-floor tags, malformed tags, unknown formats
7. Do not allow free-text release input in MVP.
8. Do not expose minimum-floor override in MVP.
9. On any resolver failure, generation must continue using fallback path (never hard-stop solely due to release lookup).
10. Step 2 must include exactly:
  - Section A kid views: selected kids + kid template profile (no per-kid override controls)
  - Section B admin views: mode (`none`, `global`, `per_kid`, `both`) + required admin template selector(s)
  - Section C display/visibility: show in sidebar, require admin, icon
11. Step 2 validation is mandatory:
  - block when no kids and admin mode `none`
  - block when global mode is selected and global admin template missing
  - block when per-kid mode is selected and per-kid admin template missing
  - block when per-kid mode selected and no kids selected

## Required user messaging states

- Latest path success: “Using latest compatible release: {tag}”
- Pin success: “Using pinned release: {tag}”
- Pin fallback: “Pinned release unavailable; used {fallback_tag}”
- No compatible remote: “No compatible remote release found; used bundled template”
- Resolver outage: “Release service unavailable; used bundled template”

## Confirmed current-state evidence

- Template fetch currently uses a fixed remote pattern targeting integration repo `main`:
  - `custom_components/kidschores/const.py` (`DASHBOARD_TEMPLATE_URL_PATTERN`)
- Fetch entry point and fallback logic:
  - `custom_components/kidschores/helpers/dashboard_builder.py` (`fetch_dashboard_template`, `_fetch_remote_template`, `_fetch_local_template`)
- Dashboard create/update options flow already exists and is stable after recent simplification:
  - `custom_components/kidschores/options_flow.py` (`async_step_dashboard_create`, `async_step_dashboard_update*`, confirm/result)

## Implementation sequence for builder

### Package A - Release policy and parser (must do first)

- [ ] Add dashboard release source constants
  - File: `custom_components/kidschores/const.py`
  - Include owner/repo constants and minimum compatible release constant.

- [ ] Add normalized tag parser utility for dashboard release tags
  - File: `custom_components/kidschores/helpers/dashboard_builder.py`
  - Accept at least `KCD_vX.Y.Z_betaN` and `KCD_vX.Y.Z`.
  - Ignore malformed tags safely.

- [ ] Define and enforce minimum compatible release floor
  - File: `dashboard_builder.py`
  - Any selected/default release below floor is rejected and replaced by nearest compatible fallback.

### Package B - Release discovery + template resolution

- [ ] Add GitHub release discovery helper
  - File: `dashboard_builder.py`
  - Use GitHub releases API (anonymous acceptable; graceful degradation required).

- [ ] Add deterministic newest-compatible selector
  - File: `dashboard_builder.py`
  - Sort compatible tags and select newest.

- [ ] Add release-aware template URL construction
  - Files: `const.py`, `dashboard_builder.py`
  - Use selected tag/ref in raw-content URL.

- [ ] Preserve non-destructive fallback sequence
  - File: `dashboard_builder.py`
  - Resolution order: selected/newest compatible → fallback compatible → local bundled template.

### Package C - Options flow UX wiring

- [ ] Add release mode selector and conditional release tag selector
  - File: `custom_components/kidschores/helpers/dashboard_helpers.py`
  - Default mode: `latest_compatible`.

- [ ] Propagate selected release inputs through create/update/confirm paths
  - File: `custom_components/kidschores/options_flow.py`
  - Maintain existing simple action routing and update preservation behavior.

- [ ] Add new translation keys and selector options
  - Files: `custom_components/kidschores/const.py`, `custom_components/kidschores/translations/en.json`

- [ ] Add user-facing fallback explanation in result/errors
  - File: `options_flow.py`
  - Example: selected release unavailable; fallback used.

## Acceptance criteria (Definition of ready-to-merge)

### AC-1 default behavior

- New dashboard generation uses newest compatible release by default without extra user input.

### AC-2 pin behavior

- User can pin a specific release from discovered options; that release is used when available.

### AC-3 compatibility safety

- Releases below minimum floor are not used.
- If remote release/template fetch fails, generation still succeeds via fallback or bundled local templates.
- Reinstalling integration restores bundled template files; generator can rebuild dashboards from those restored files.

### AC-4 UX clarity

- Create/update/delete flow remains clear and non-redundant.
- New release controls and errors are fully translated in English resources.
- Step 1/Step 2 structure and validation follow locked UX contract exactly.

## Suggested test delivery for builder

- [ ] `tests/test_dashboard_template_release_resolution.py`
  - parser/sort/newest-compatible/floor enforcement
- [ ] `tests/test_dashboard_builder_release_fetch.py`
  - API timeout/missing template/fallback behavior
- [ ] `tests/test_options_flow_dashboard_release_selection.py`
  - selector defaults, pin mode, user-visible fallback messaging

## Validation gates (required before handback)

- `./utils/quick_lint.sh --fix`
- `mypy custom_components/kidschores/`
- `python -m pytest tests/ -v --tb=line`

## Rollback plan

If release discovery introduces regressions:
1. Disable release selector UI and force current style-only behavior.
2. Keep local template fallback path active.
3. Re-enable release selection behind advanced toggle after parser/fetch hardening.

## Out of scope for this handoff

- Multi-source registries beyond GitHub releases (e.g., private mirrors).
- Persistent per-dashboard release pin metadata beyond current flow scope.
- Auto-update scheduler for dashboard templates after initial generation.

## Builder delivery checklist

- [ ] Package A complete and reviewed.
- [ ] Package B complete with robust fallback behavior.
- [ ] Package C complete with translation updates.
- [ ] AC-1 through AC-4 verified with focused tests.
- [ ] Parent plan summary updated with phase percentages and blockers.
