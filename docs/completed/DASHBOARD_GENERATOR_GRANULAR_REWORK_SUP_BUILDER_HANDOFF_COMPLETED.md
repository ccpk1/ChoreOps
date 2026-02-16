# Dashboard Generator Granular Rework - Builder Handoff

---
status: READY_FOR_HANDOFF
owner: Strategist Agent
created: 2026-02-14
parent_plan: DASHBOARD_GENERATOR_GRANULAR_REWORK_IN-PROCESS.md
handoff_from: KidsChores Strategist
handoff_to: KidsChores Plan Agent
phase_focus: Phase 1 stabilization first, then Phase 2 MVP option A
---

## Handoff button

[HANDOFF_TO_BUILDER_PHASE1_NOW](DASHBOARD_GENERATOR_GRANULAR_REWORK_IN-PROCESS.md)

## Handoff objective

Prepare implementation to:
1) Eliminate startup Lovelace duplicate panel warnings for KidsChores dashboards.
2) Keep dashboard creation idempotent for repeated create/rebuild cycles.
3) Establish minimal granularity foundation for per-user template/profile and targeted updates.

## Confirmed root-cause evidence

- Duplicate persisted entries exist for the same URL path in Home Assistant storage:
  - `/workspaces/core/config/.storage/lovelace_dashboards`
  - Multiple `items[].url_path == "kcd-chores"` with distinct IDs (`kcd_chores`, `kcd_chores_2`, ...).
- Generator registration path:
  - `custom_components/kidschores/helpers/dashboard_builder.py`
  - `_create_dashboard_entry()` currently creates collection item + registers panel each run.
- Current UX behavior:
  - `options_flow.py` dashboard generator creates a single dashboard with multiple views.
  - One style applies to all selected kid views.

## Implementation sequence for builder

### Package A - Phase 1.1 duplicate prevention (must do first)

- [ ] Add collection-level existence check before create
  - File: `custom_components/kidschores/helpers/dashboard_builder.py`
  - Scope: `_create_dashboard_entry()`
  - Requirement: query `DashboardsCollection.async_items()` for existing matching `url_path`.
  - Behavior: if one entry exists, reuse it; do not create another item.

- [ ] Make panel registration idempotent
  - File: `custom_components/kidschores/helpers/dashboard_builder.py`
  - Scope: `_create_dashboard_entry()`
  - Requirement: if panel/runtime mapping already exists for `url_path`, do not duplicate register path.

- [ ] Harden `check_dashboard_exists`
  - File: `custom_components/kidschores/helpers/dashboard_builder.py`
  - Requirement: include persisted collection items in addition to runtime maps.

### Package B - Phase 1.2 cleanup for existing duplicate data

- [ ] Implement dedupe helper for KidsChores namespace only
  - File: `custom_components/kidschores/helpers/dashboard_builder.py`
  - New helper proposal: `async_dedupe_kidschores_dashboards(hass)`
  - Rule: only operate on `url_path` with `kcd-` prefix.
  - Rule: keep one canonical item per `url_path`, remove extras.

- [ ] Integrate dedupe into dashboard generator workflow
  - File: `custom_components/kidschores/options_flow.py`
  - Suggested point: before create flow execute and before delete list render.

- [ ] Add operator-visible result note
  - File: `custom_components/kidschores/options_flow.py`
  - Requirement: include dedupe summary in result text (e.g., duplicates removed count).

### Package C - Phase 2 scaffolding for granular mode (MVP-ready)

- [ ] Add constants for generation mode/scope
  - File: `custom_components/kidschores/const.py`
  - Keep defaults backward-compatible to current single multi-view behavior.

- [ ] Extend schema builder with minimal mode controls
  - File: `custom_components/kidschores/helpers/dashboard_helpers.py`
  - Add: generation mode and target scope selector.
  - Keep existing fields unchanged for default path.

- [ ] Route options flow by mode without changing current default branch
  - File: `custom_components/kidschores/options_flow.py`
  - If mode absent, current behavior remains.

## Acceptance criteria (Definition of ready-to-merge)

### AC-1 startup stability

- Reproducing startup no longer emits duplicate warning for known KidsChores dashboard URL paths.
- No additional duplicate `kcd-*` entries are written after repeated create/rebuild cycles.

### AC-2 idempotent create behavior

- Running create flow multiple times with same name and force_rebuild settings does not increase entry count for identical `url_path`.

### AC-3 cleanup safety

- Dedupe only affects `kcd-*` dashboards.
- Non-KidsChores dashboards remain unchanged.

### AC-4 backward compatibility

- Existing single-dashboard, multi-view generation path continues working with no extra required inputs.

## Suggested test delivery for builder

- [ ] New: `tests/test_dashboard_builder.py`
  - duplicate prevention test
  - idempotent create test
  - namespace-safe dedupe test
- [ ] New: `tests/test_options_flow_dashboard_generator.py`
  - create flow unchanged default behavior
  - dedupe result messaging path
  - mode branching baseline (if phase 2 scaffolding included)

## Validation gates (required before handback)

- `./utils/quick_lint.sh --fix`
- `mypy custom_components/kidschores/`
- `python -m pytest tests/ -v --tb=line`

## Rollback plan

If regressions occur in Lovelace registration behavior:

1. Disable dedupe invocation path in options flow (keep helper code for diagnostics).
2. Fall back to existing create/delete behavior with strengthened logging only.
3. Preserve manual cleanup path in operator instructions until follow-up patch.

## Out of scope for this handoff

- Full per-kid dashboard architecture switch (Option B).
- Translation rollout for all locales beyond minimum required implementation path.
- Dashboard visual/template redesign.

## Builder delivery checklist

- [ ] Phase 1 packages A + B complete.
- [ ] AC-1 through AC-4 verified by tests/log evidence.
- [ ] Plan summary updated in parent document with percentages.
- [ ] If Phase 2 scaffolding included, mark exact mode flags and defaults in parent plan.
- [ ] Handoff back with changed files list + test output summary.
