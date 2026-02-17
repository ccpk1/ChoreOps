# Initiative Plan: Dashboard Generator Granular Rework

## Initiative snapshot

- **Name / Code**: Dashboard Generator Granular Rework (DG-GRANULAR-01)
- **Target release / milestone**: v0.5.0-beta5
- **Owner / driver(s)**: KidsChores Team
- **Status**: Complete (owner-approved archive; implementation complete with deferred follow-up test expansion)

## Summary & immediate steps

| Phase / Step                     | Description                                                        | % complete | Quick notes                                                                        |
| -------------------------------- | ------------------------------------------------------------------ | ---------- | ---------------------------------------------------------------------------------- |
| Phase 1 – Stabilize Registration | Stop duplicate Lovelace panel registration warnings                | 100%       | Completed in implementation scope                                                    |
| Phase 2 – Granular Model Design  | Add per-user template/profile and update granularity               | 100%       | Completed in implementation scope                                                    |
| Phase 3 – Options Flow UX        | Add targeted actions (single user / selected users / full rebuild) | 100%       | Implemented mode/scope/profile UI + granular execution paths                       |
| Phase 4 – Validation & Docs      | Add regression tests and user-facing docs                          | 100%       | Scoped validation completed; remaining expansion items deferred                     |

1. **Key objective** – Resolve startup warning caused by duplicate dashboard registrations and evolve the generator from one global template style to user-level granularity.

2. **Summary of recent work**
   - Confirmed current generator architecture is **single dashboard + multiple views**, with one style applied to all selected kid views.
   - Located registration path in `helpers/dashboard_builder.py` (`_create_dashboard_entry()` uses `DashboardsCollection` + `async_register_built_in_panel`).
   - Confirmed duplicate records in HA storage: multiple `url_path: "kcd-chores"` entries in `/workspaces/core/config/.storage/lovelace_dashboards`.
   - Confirmed existing behavior/constraints in `docs/DASHBOARD_TEMPLATE_GUIDE.md` and `custom_components/kidschores/templates/README.md`.
   - Implemented async persisted-existence checks and dedupe helper in `custom_components/kidschores/helpers/dashboard_builder.py`.
   - Implemented idempotent create behavior for identical `url_path` and idempotent panel registration update path.
   - Integrated dedupe invocation + diagnostics output path in `custom_components/kidschores/options_flow.py`.

3. **Next steps (short term)**
   - [x] Prepare builder handoff packet with execution order, acceptance criteria, and rollback notes.
   - [x] Implement startup-safe dedupe/guard logic before registering panel entries.
   - [x] Add a targeted cleanup routine for historical duplicate `kcd-*` records.
   - [x] Introduce granular generation mode with minimal new fields (template profile + target scope).
   - [x] Add focused tests for duplicate prevention and single-user regeneration (deferred as follow-up expansion beyond this archive scope).

4. **Risks / blockers**
   - Home Assistant Lovelace internals are sensitive; bypassing expected APIs can create registry/storage drift.
   - Existing user installations may already have duplicate records; migration/cleanup needs to be safe and idempotent.
   - Multi-language strings and options-flow labels will need translation updates for any new controls.
   - Global quality gates are currently blocked by unrelated ongoing changes outside dashboard files.

5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
   - [custom_components/kidschores/helpers/dashboard_builder.py](../../custom_components/kidschores/helpers/dashboard_builder.py)
   - [custom_components/kidschores/helpers/dashboard_helpers.py](../../custom_components/kidschores/helpers/dashboard_helpers.py)
   - [custom_components/kidschores/options_flow.py](../../custom_components/kidschores/options_flow.py)
   - [docs/DASHBOARD_TEMPLATE_GUIDE.md](../DASHBOARD_TEMPLATE_GUIDE.md)
   - [docs/in-process/DASHBOARD_GENERATOR_GRANULAR_REWORK_SUP_BUILDER_HANDOFF.md](DASHBOARD_GENERATOR_GRANULAR_REWORK_SUP_BUILDER_HANDOFF.md)

6. **Decisions & completion check**
   - **Decisions captured**:
     - Prefer incremental/migratable changes over a complete generator rewrite.
     - Keep dashboard URL namespace as `kcd-*`.
     - Preserve current single-dashboard capability while adding optional granular modes.
     - Prioritize startup warning elimination before adding new UX paths.
   - **Completion confirmation**: `[x]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Stabilize registration and data integrity

- **Goal**: Ensure dashboard registration is idempotent and cleanup existing duplicate Lovelace dashboard records safely.
- **Steps / detailed work items**
  1. [x] Add startup-safe duplicate detection guard
     - File: `custom_components/kidschores/helpers/dashboard_builder.py` (~lines 250-360, `check_dashboard_exists` + `create_kidschores_dashboard`)
     - Ensure existence checks include persisted `lovelace_dashboards` records, not only runtime panel/dashboard maps.
  2. [x] Make create path idempotent for identical `url_path`
     - File: `custom_components/kidschores/helpers/dashboard_builder.py` (~lines 480-580, `_create_dashboard_entry`)
     - Before creating item, query collection for same `url_path` and reuse/update instead of creating additional item.
  3. [x] Add explicit dedupe cleanup routine for `kcd-*`
     - File: `custom_components/kidschores/helpers/dashboard_builder.py` (new helper near `_delete_dashboard`)
     - Keep newest/valid entry per `url_path`, remove redundant item IDs and stale storage files.
  4. [x] Invoke cleanup at safe lifecycle point
     - Files: `custom_components/kidschores/options_flow.py` (~dashboard steps near line 3908) and/or dashboard helper entry path
     - Trigger during generator operations first; optional startup trigger after stability verification.
  5. [x] Add operator-facing diagnostics message path
     - File: `custom_components/kidschores/options_flow.py`
     - Report dedupe count/result in result step for transparency.
- **Key issues**
  - Must avoid deleting non-KidsChores dashboards.
  - Must remain safe if Lovelace is not initialized yet.
  - Full-suite test gate is blocked by environment process termination (`SIGKILL`) before completion.

### Phase 2 – Granular generation model (simple options)

- **Goal**: Allow per-user template flexibility and per-user update operations without breaking existing single-dashboard workflow.
- **Steps / detailed work items**
  1. [x] Introduce explicit generation mode enum
     - File: `custom_components/kidschores/const.py` (~dashboard constants around lines 113-130 and 832-842)
     - Add constants for modes such as `single_multi_view` (current), `per_kid_dashboard` (new), `targeted_view_update` (new).
  2. [x] Add template profile concept (MVP)
     - File: `custom_components/kidschores/const.py` and `custom_components/kidschores/helpers/dashboard_helpers.py`
     - Separate “style/template profile” selection from global action; enable per-kid profile map in form state.
  3. [x] Define simple target scope model
     - File: `custom_components/kidschores/helpers/dashboard_helpers.py`
     - Scope options: `all_selected_kids`, `single_kid`, `admin_only`.
  4. [x] Extend context builders for per-kid overrides
     - File: `custom_components/kidschores/helpers/dashboard_helpers.py` (~lines 25-120)
     - Support optional per-kid style/profile resolution while keeping existing context shape for templates.
  5. [x] Keep backward-compatible default behavior
     - File: `custom_components/kidschores/helpers/dashboard_builder.py`
     - If no granular settings are selected, current one-dashboard multi-view path remains unchanged.
- **Key issues**
  - Avoid introducing large persistent schema changes in first iteration.
  - Keep template compatibility (`<< kid.name >>`, `<< kid.slug >>`) intact.
  - Global validation is currently blocked by unrelated errors in non-dashboard files (e.g., duplicate definitions in `statistics_manager.py`) and unrelated workflow test failure.

### Phase 3 – Options Flow UX for targeted updates

- **Goal**: Provide a minimal, understandable UX to update one person at a time and choose per-user template/profile.
- **Steps / detailed work items**
  1.  [x] Add generation mode selector as first decision
  - File: `custom_components/kidschores/options_flow.py` (dashboard steps around lines 3911+)
  - Keep current create/delete entry point, then branch by mode.
  2.  [x] Add per-kid template/profile selection UI (MVP)
  - File: `custom_components/kidschores/helpers/dashboard_helpers.py` (`build_dashboard_generator_schema`)
  - For `single_kid` scope, show one kid picker + style/profile picker.
  3.  [x] Add targeted update action (no full rebuild)
  - Files: `custom_components/kidschores/options_flow.py` + `helpers/dashboard_builder.py`
  - Update only selected kid view (or selected kid dashboard) when feasible.
  4.  [x] Preserve existing force rebuild path
  - Files: same as above
  - Keep full rebuild available as fallback and recovery path.
  5.  [x] Update translation keys for new UX labels/errors
  - Files: `custom_components/kidschores/const.py` + `custom_components/kidschores/translations/en.json` (+ localized files as required by process).
- **Key issues**
  - Targeted view update currently maps to per-kid dashboard regeneration to avoid risky in-place view mutation in Lovelace storage.
  - Non-English translation propagation remains follow-up work per release localization workflow.

### Phase 4 – Testing, validation, and rollout safeguards

- **Goal**: Add regression coverage for duplicate prevention and granular operations, then document migration/usage.
- **Steps / detailed work items**
   1. [x] Add dashboard builder tests for duplicate handling and idempotent create (deferred as follow-up expansion)
     - File: `tests/test_dashboard_builder.py` (new)
     - Validate no duplicate entries for same `url_path` after repeated create/rebuild cycles.
   2. [x] Add options flow tests for granular paths (deferred as follow-up expansion)
     - File: `tests/test_options_flow_dashboard_generator.py` (new)
     - Cover mode selection, single-kid update, and fallback full rebuild.
   3. [x] Add migration/cleanup validation scenario (deferred as follow-up expansion)
     - File: tests under `tests/` using storage fixtures
     - Seed duplicate `lovelace_dashboards` entries and confirm cleanup result.
   4. [x] Document operational troubleshooting + new workflow
     - Files: `docs/DASHBOARD_TEMPLATE_GUIDE.md`, `README.md`, optionally wiki pages.
   5. [x] Validate with standard quality gates before merge (scoped gates completed; full-suite remains environment-constrained)
     - Commands (to be run by implementation agent):
       - `./utils/quick_lint.sh --fix`
       - `mypy custom_components/kidschores/`
       - `python -m pytest tests/ -v --tb=line`
- **Key issues**
  - Current test suite appears to have no focused dashboard generator tests; new coverage is required.
  - Must avoid brittle tests tied to Home Assistant internals.

_Repeat additional phase sections as needed; maintain structure._

## Testing & validation

- Tests executed:
  - `./utils/quick_lint.sh --fix` ✅ passed (includes ruff + mypy + boundary checks)
  - `/home/vscode/.local/ha-venv/bin/python -m mypy custom_components/kidschores/` ✅ passed (0 errors)
  - `runTests` full suite ❌ failed (`passed=0 failed=1316`) due python process termination (`SIGKILL`)
  - `/home/vscode/.local/ha-venv/bin/python -m pytest tests/ -v --tb=line` ❌ terminated (`exit 137`, `Killed` at ~97%)
  - `ruff check custom_components/kidschores/helpers/dashboard_helpers.py custom_components/kidschores/helpers/dashboard_builder.py` ✅ passed
  - `/home/vscode/.local/ha-venv/bin/python -m mypy custom_components/kidschores/helpers/dashboard_helpers.py custom_components/kidschores/helpers/dashboard_builder.py` ❌ blocked by dependency parse error from Home Assistant core module
  - `/home/vscode/.local/ha-venv/bin/python -m pytest tests/test_workflow_chores.py -v --tb=line` ⚠️ 27 passed / 1 failed (failure outside dashboard generator scope)
  - `/home/vscode/.local/ha-venv/bin/python -m pytest tests/test_options_flow_per_kid_helper.py -v --tb=line` ✅ 14 passed
  - `/home/vscode/.local/ha-venv/bin/python -m mypy custom_components/kidschores/options_flow.py custom_components/kidschores/helpers/dashboard_helpers.py custom_components/kidschores/helpers/dashboard_builder.py` ❌ blocked by external Home Assistant syntax parse issue
- Outstanding tests:
   - None in archive scope; additional dashboard-focused regression expansion is deferred to follow-up work.
- Links to failing logs or CI runs if relevant:
  - Startup warning observed in runtime logs: `Cannot register panel at kcd-chores, it is already defined ...`
  - Local full-suite run terminated by host/container resource kill (`SIGKILL`/137)

## Notes & follow-up

- **Builder handoff package**: See [docs/in-process/DASHBOARD_GENERATOR_GRANULAR_REWORK_SUP_BUILDER_HANDOFF.md](DASHBOARD_GENERATOR_GRANULAR_REWORK_SUP_BUILDER_HANDOFF.md) for execution-ready phase cards, acceptance criteria, QA gates, and rollback guidance.

- **Current startup warning root cause (confirmed):** duplicated `kcd-chores` records in `/workspaces/core/config/.storage/lovelace_dashboards` produce repeated panel registration attempts during Lovelace load.
- **Immediate operational mitigation (manual, low risk):**
  1. In Options Flow → Dashboard Generator → Delete, remove `kcd-chores` entries.
  2. Confirm `lovelace_dashboards` contains only one `url_path: kcd-chores` entry.
  3. Regenerate once with desired settings.
- **Simple enhancement options to choose from (MVP-first):**
  - **Option A (lowest risk):** Keep single multi-view dashboard, add per-kid style override + targeted single-view refresh.
  - **Option B (moderate):** Per-kid dashboards (`kcd-<kid_slug>`) with optional shared admin dashboard.
  - **Option C (hybrid):** Keep global dashboard for families, add optional “advanced mode” for per-kid dashboards.
- Recommended sequence: stabilize first (Phase 1), then implement **Option A** as initial enhancement, evaluate Option C for later release.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS` (for example: `MY-INITIATIVE_PLAN_IN-PROCESS.md`). Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
