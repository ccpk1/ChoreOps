# Initiative Plan: Dashboard Template Release Selection

## Initiative snapshot

- **Name / Code**: Dashboard Template Release Selection (DASH-REL-SELECT-01)
- **Target release / milestone**: v0.5.0-beta5 (or next patch after beta4)
- **Owner / driver(s)**: KidsChores Team (Integration + Dashboard coordination)
- **Status**: Complete (all planned phases and follow-up hotfix/docs updates finished)

## Summary & immediate steps

| Phase / Step                            | Description                                                                            | % complete | Quick notes                                                                                                       |
| --------------------------------------- | -------------------------------------------------------------------------------------- | ---------- | ----------------------------------------------------------------------------------------------------------------- |
| Phase 1 – Release policy                | Define release-source rules, minimum supported tag, and fallback behavior              | 100%       | Parser contract, compatibility floor constants, prerelease policy, docs complete                                  |
| Phase 2 – Core resolver                 | Add GitHub release discovery + tag resolution + template URL construction              | 100%       | Discovery + compatibility filtering + release URL resolver wired; local fallback preserved                        |
| Phase 3 – Options flow UX               | Show selectable release list, default to newest compatible, allow override             | 100%       | CRUD hub + shared configure step + locked validation + delete-confirm return flow implemented                     |
| Phase 4 – Validation                    | Add focused tests and failure-mode checks                                              | 100%       | Added resolver, fetch-fallback, and options-flow release tests; all passing                                       |
| Phase 4 (Part B) – Update UX refinement | Reorganize update form sections, clarify language, simplify template version selection | 100%       | Update selector/copy polished, dashboard configuration field order updated, and focused section-order tests added |

1. **Key objective** – Allow users to select dashboard template releases from the dashboard repo, default to the newest compatible release, and optionally enforce a minimum release floor.
2. **Summary of recent work**
   - Implemented Phase 1 release policy constants in `const.py` (release source, tag grammar, minimum compatibility floor, prerelease defaults).
   - Implemented Phase 2 resolver flow in `dashboard_builder.py`: GitHub release discovery, compatibility filtering, newest-compatible default selection, pinned fallback handling, and release-aware template URL resolution.
   - Added release-aware URL pattern constant in `const.py` for tag/ref-based template fetching.
   - Implemented Phase 3 options flow UX in `options_flow.py` and `dashboard_helpers.py`: Step 1 CRUD routing, create name-only path, shared Step 2 configure form, update-only release controls, and locked admin/kid validation rules.
   - Updated dashboard translation copy/options for new step fields and validation errors in `translations/en.json`.
   - Added Phase 4 focused tests:
     - `tests/test_dashboard_template_release_resolution.py`
     - `tests/test_dashboard_builder_release_fetch.py`
     - `tests/test_options_flow_dashboard_release_selection.py`
   - Completed dead dashboard code/constants scan and identified stale symbols for follow-up cleanup (see Notes & follow-up).
   - Added user-facing translation key/value for release incompatibility messaging.
   - Documented compatibility matrix source of truth and recovery behavior in `docs/DASHBOARD_TEMPLATE_GUIDE.md`.
   - Template resolution entry point `fetch_dashboard_template()` now resolves compatible release tags first and only falls back to bundled local templates when remote resolution/fetch fails.
   - Dashboard create/update UX already supports explicit action routing in `custom_components/kidschores/options_flow.py` (~lines 3990-4170).
   - Existing translation blocks for dashboard forms are centralized in `custom_components/kidschores/translations/en.json` (~lines 1504-1555).
   - New user-approved direction: fold update-screen usability cleanup into current phase as Phase 4 Part B.

- Hotfix: removed legacy create configure schema path so create/update now share the same sectioned dashboard configure form (single maintained schema path in `dashboard_helpers.py`).
- Added create-path regression coverage verifying sectioned schema use and no release controls on create (`test_dashboard_create_uses_sectioned_configure_schema`).
- Updated admin layout user-facing terminology to `None / Shared / Per Kid / Both` while preserving internal storage values.
- Expanded release-tag parser support to include currently published `v...` and hyphen beta formats (for example `v0.5.6-beta1`) so existing releases are discoverable.
- Clarified dashboard download prerequisites and metadata locations in `docs/DASHBOARD_TEMPLATE_GUIDE.md`.
- Fixed update-flow admin layout application by passing `admin_mode` through to dashboard builder and generating per-kid admin views when `Per Kid`/`Both` is selected.
- Fixed create-flow admin layout application by passing `admin_mode` through to dashboard builder and generating admin views based on `Shared`/`Per Kid`/`Both` selections.
- Fixed update-flow dashboard metadata application so icon, sidebar visibility, and require-admin changes persist on existing dashboards.
- Added admin-mode normalization (`shared`, `per kid`, `both`) in options flow and dashboard builder so label-like values reliably map to internal constants and create per-kid admin views as expected.
- Refreshed dashboard docs/wiki to match current CRUD flow, admin layout modes (`None/Shared/Per Kid/Both`), and release-based template fetch behavior.

3. **Next steps (short term)**
   - [x] Finalize release tag compatibility contract with dashboard repo owner (tag grammar + prerelease handling).
   - [x] Implement resolver abstraction and wire into template fetch path.
   - [x] Add release selector fields in create/update dashboard forms.
   - [x] Add tests for newest-default, pinned selection, and minimum-version rejection.

- [x] Execute Phase 4 Part B update-screen UX refinements (section layout, language, selector simplification, admin view visibility controls).

4. **Risks / blockers**
   - GitHub API availability/rate limits may prevent release list fetch; graceful fallback behavior is mandatory.
   - Release tags may not strictly follow SemVer; parser must support current observed format (`KCD_v0.5.0_beta3`).
   - Integration and dashboard compatibility matrix can drift if minimum-floor rules are not explicit.
5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
   - [docs/DASHBOARD_TEMPLATE_GUIDE.md](../DASHBOARD_TEMPLATE_GUIDE.md)
   - [custom_components/kidschores/helpers/dashboard_builder.py](../../custom_components/kidschores/helpers/dashboard_builder.py)
   - [custom_components/kidschores/helpers/dashboard_helpers.py](../../custom_components/kidschores/helpers/dashboard_helpers.py)
   - [custom_components/kidschores/options_flow.py](../../custom_components/kidschores/options_flow.py)
   - [custom_components/kidschores/const.py](../../custom_components/kidschores/const.py)
   - [custom_components/kidschores/translations/en.json](../../custom_components/kidschores/translations/en.json)
   - [docs/in-process/DASHBOARD_TEMPLATE_RELEASE_SELECTION_SUP_BUILDER_HANDOFF.md](DASHBOARD_TEMPLATE_RELEASE_SELECTION_SUP_BUILDER_HANDOFF.md)
   - [docs/in-process/DASHBOARD_TEMPLATE_RELEASE_SELECTION_SUP_IMPLEMENTATION_CHECKLIST.md](DASHBOARD_TEMPLATE_RELEASE_SELECTION_SUP_IMPLEMENTATION_CHECKLIST.md)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Release source should be dashboard repo releases (not integration repo `main` branch) for deterministic template behavior.
     - Default behavior should auto-select newest compatible release to keep UX simple.
     - Users should have an explicit override to pin a release when needed.
     - A minimum compatible release floor should be enforced to prevent known-broken template generations.

- **Completion confirmation**: `[x]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) and ready for archive.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

## Option presentation and allow/restrict policy

### Locked UX flow (v1)

#### Step 1 – Dashboard actions (CRUD hub)

- Actions shown on one screen: `Create`, `Update`, `Delete`, `Exit`.
- `Create` path:
  - Input: dashboard name only.
  - Behavior: create empty dashboard shell, then route to Step 2 for configuration.
  - No advanced template/release controls used in this path.
- `Update` path:
  - Input: single dashboard selector.
  - Advanced collapsed section available only here for template/release source behavior.
  - Routes to Step 2.
- `Delete` path:
  - Input: same single dashboard selector used by Update (single selection only).
  - Requires explicit confirm step.
  - After delete, return to Step 1 CRUD hub with success/failure status.

#### Step 2 – Configure selected dashboard

- Section A (kid views):
  - selected kids (multi-select)
  - kid template profile (applies to selected kids)
  - no per-kid override/advanced controls in v1
- Section B (admin views):
  - admin mode: `none`, `global`, `per_kid`, `both`
  - global admin template required when mode includes `global`
  - per-kid admin template required when mode includes `per_kid`
- Section C (display/visibility – lightweight):
  - show in sidebar
  - require admin
  - icon

#### Step 2 validation (locked)

1. Block submit when no kids selected and admin mode is `none`.
2. Block submit when admin mode includes `global` and global admin template is missing.
3. Block submit when admin mode includes `per_kid` and per-kid admin template is missing.
4. Block submit when admin mode includes `per_kid` and no kids are selected.

### User-facing controls (MVP)

| Control                    | Visible when                                                | Allowed values                                  | Restricted / blocked values                                 | Default                            | User feedback                                    |
| -------------------------- | ----------------------------------------------------------- | ----------------------------------------------- | ----------------------------------------------------------- | ---------------------------------- | ------------------------------------------------ |
| `release_mode`             | Step 1 Update action only (advanced collapsed)              | `latest_compatible`, `pin_release`              | None                                                        | `latest_compatible`                | Short description under field                    |
| `release_tag`              | Step 1 Update action only when `release_mode = pin_release` | Tags returned by resolver and marked compatible | Any tag below minimum floor, malformed tags, missing assets | Newest compatible tag pre-selected | Inline error if selected tag becomes unavailable |
| `include_prereleases`      | Optional advanced toggle (Phase 3)                          | `true`, `false`                                 | If hidden, user cannot change                               | `true` during beta cycle           | Helper text explains beta-default behavior       |
| `minimum_release_override` | Not shown in MVP (operator-only follow-up)                  | N/A in MVP                                      | All user overrides blocked in MVP                           | Integration constant               | Info text: minimum is enforced automatically     |

### Enforcement rules (authoritative)

1. **Always allow** `latest_compatible` mode, even when release API is down.
2. **Allow pinning only** to compatible tags from discovered list; no free-text tag entry in MVP.
3. **Restrict any release below floor** (example floor tied to beta compatibility), with deterministic fallback to newest compatible.
4. **Restrict malformed tags** from selector population (quietly excluded, debug logged).
5. **Restrict hard failure on remote outages**; system must degrade to local bundled templates.

### Compatibility gate algorithm (prevents incompatible picks)

1. Read installed integration version from [custom_components/kidschores/manifest.json](../../custom_components/kidschores/manifest.json) (`version`, currently `0.5.0b4`).
2. Build compatibility metadata for each dashboard release tag from one of these sources:
   - Primary: release metadata manifest (recommended follow-up in dashboard repo), or
   - MVP fallback: integration-side compatibility map constants keyed by tag pattern/range.
3. For each release candidate, evaluate:
   - `min_integration_version <= installed_integration_version`
   - optional `max_integration_version` if provided.
4. Only include passing releases in selector options.
5. If user has pinned a now-incompatible release, block that selection and auto-fallback to newest compatible.

Example policy for your case:

- Dashboard `KCD_v0.5.4` carries `min_integration_version = 0.5.2`.
- If installed integration is `0.5.1`, `KCD_v0.5.4` is excluded from the selector and cannot be chosen.
- If installed integration is `0.5.2+`, it appears and may be selected (or auto-selected if newest compatible).

### Compatibility metadata shape (proposed)

```text
release_tag: KCD_v0.5.4
min_integration_version: 0.5.2
max_integration_version: null
compatibility_note: Requires integration 0.5.2+
```

MVP implementation note:

- Until dashboard release assets expose metadata, enforce compatibility in integration constants as a temporary gate.
- Promote to release-embedded metadata once dashboard repo adopts compatibility manifests.

### UX response matrix

| Scenario                                 | Behavior                                      | Result copy expectation                                     |
| ---------------------------------------- | --------------------------------------------- | ----------------------------------------------------------- |
| API reachable, compatible releases found | Show selector list; default newest compatible | “Using latest compatible release: {tag}”                    |
| User pins valid compatible release       | Use pinned release                            | “Using pinned release: {tag}”                               |
| User pins tag that later disappears      | Fallback to newest compatible                 | “Pinned release unavailable; used {fallback_tag}”           |
| Only below-floor releases found          | Reject remote set; use bundled local          | “No compatible remote release found; used bundled template” |
| API timeout/rate-limit/network error     | Skip remote selection; use bundled local      | “Release service unavailable; used bundled template”        |

### Recommended MVP decision

- **Choose hardcoded minimum floor (no user override) for v1**.
- **Reason**: prevents support complexity and avoids exposing users to known-bad combinations.
- **Follow-up**: Add advanced operator override only after telemetry/support confirms need.

### Phase 1 – Release policy and compatibility contract

- **Goal**: Define exactly which dashboard releases are selectable and how compatibility is enforced.
- **Steps / detailed work items**
  1. [x] Define canonical tag parser contract and accepted formats
     - Files: `custom_components/kidschores/helpers/dashboard_builder.py` (~template fetching section), `custom_components/kidschores/const.py` (~dashboard constants)
     - Support at minimum:
       - `KCD_vX.Y.Z_betaN`
       - `KCD_vX.Y.Z`
     - Reject malformed tags without crashing flow.
  2. [x] Add minimum compatible dashboard release constant(s)
     - File: `custom_components/kidschores/const.py` (~dashboard constants near lines 100-140)
     - Introduce constants (names TBD by builder) for floor tag and user-facing message key.
  3. [x] Define prerelease policy (include/exclude toggle)
     - Files: `const.py`, `dashboard_builder.py` (selector defaults will be wired in Phase 3)
     - Default recommendation: include prereleases while integration itself is beta.
  4. [x] Document compatibility matrix source of truth
     - Files: `docs/DASHBOARD_TEMPLATE_GUIDE.md`, optional short note in `README.md`
     - Clarify “integration version → minimum dashboard release” mapping.
- **Key issues**
  - Tag semantics are project-specific; strict SemVer parsing alone is insufficient.
  - Future naming changes in dashboard repo can break parsing unless guarded by fallback.

### Phase 2 – Release discovery and template resolution engine

- **Goal**: Resolve selected/default release to template URLs with robust fallback behavior.
- **Steps / detailed work items**
  1.  [x] Add release listing helper using GitHub Releases API
  - File: `custom_components/kidschores/helpers/dashboard_builder.py` (~new helper block near fetch functions)
  - Endpoint target: `ccpk1/kidschores-ha-dashboard` releases list.
  2.  [x] Implement release normalization + sort logic
  - File: `dashboard_builder.py`
  - Build deterministic “newest compatible” selection from fetched releases.
  3.  [x] Build release-aware template URL constructor
  - Files: `const.py` (URL patterns), `dashboard_builder.py`
  - Resolve templates from selected tag/ref instead of fixed `main` path.
  4.  [x] Preserve existing fallback chain
  - File: `dashboard_builder.py` (`fetch_dashboard_template`)
  - New order:
    1.  Selected/newest compatible release template
    2.  Fallback compatible release (if selected missing)
    3.  Local bundled template
  5.  [x] Add structured diagnostics logging for release resolution
  - File: `dashboard_builder.py`
  - Log selected tag, fallback reason, and final source used (without sensitive data).
- **Key issues**
  - Rate limits for anonymous GitHub API calls; include timeout and “best effort” behavior.
  - Must not block dashboard generation when remote API is unavailable.

### Phase 3 – Options flow UX for release selection

- **Goal**: Expose release controls without reintroducing dashboard-flow complexity.
- **Steps / detailed work items**
  1.  [x] Implement Step 1 CRUD hub with single-screen action branching
  - File: `custom_components/kidschores/options_flow.py`
  - Actions: create (blank), update, delete, exit.
  - Delete uses same selector as update (single selection).
  2.  [x] Restrict template/release advanced controls to Update path only
  - Files: `custom_components/kidschores/helpers/dashboard_helpers.py`, `custom_components/kidschores/options_flow.py`
  - Create/Delete paths must not surface release controls.
  3.  [x] Implement Step 2 sections exactly as locked UX
  - Files: `custom_components/kidschores/helpers/dashboard_helpers.py`, `custom_components/kidschores/options_flow.py`
  - Section A kid views (no advanced overrides), Section B admin mode+templates, Section C display/visibility.
  4.  [x] Implement strict Step 2 validation contract
  - Files: `custom_components/kidschores/options_flow.py`, `custom_components/kidschores/translations/en.json`
  - Enforce admin-template requirements based on selected admin mode.
  5.  [x] Add translation keys and fallback/result copy for CRUD + update flows
  - Files: `custom_components/kidschores/const.py`, `custom_components/kidschores/translations/en.json`
  - Include update-only release/fallback messaging.
- **Key issues**
  - Release list fetch can be slow; avoid introducing latency that makes options flow feel stalled.
  - Must keep current create/update/delete intent model simple.

### Phase 4 – Testing and release-readiness validation

- **Goal**: Prevent regressions and guarantee safe fallback behavior under failure modes.
- **Steps / detailed work items**
  1.  [x] Add resolver unit tests
  - File: `tests/test_dashboard_template_release_resolution.py` (new)
  - Cases:
    - Newest compatible selection from mixed tags
    - Pinning exact tag
    - Floor rejection for too-old tags
    - Malformed tag ignore behavior
  2.  [x] Add options flow tests for release fields and defaults
  - File: `tests/test_options_flow_dashboard_release_selection.py` (new)
  - Cases:
    - Default `latest_compatible`
    - Pinned flow with selected release
    - Release fetch failure fallback messaging
  3.  [x] Add integration-level fetch fallback tests
  - File: `tests/test_dashboard_builder_release_fetch.py` (new)
  - Cases:
    - API timeout → local fallback
    - Selected tag missing template file → fallback release/local path
  4.  [x] Validate translation completeness for new keys
  - File: `custom_components/kidschores/translations/en.json`
  - Ensure no orphan keys and correct selector mapping.
  5.  [x] Execute standard quality gates (builder execution)
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/kidschores/`
  - `python -m pytest tests/ -v --tb=line`
- **Key issues**
  - Existing environment may still show unrelated mypy parse blocker in `core`; isolate dashboard tests first.
  - GitHub API interactions should be mocked to keep tests deterministic.

### Phase 4 (Part B) – Update dashboard UX refinements

- **Goal**: Reduce confusion and friction on the Update Dashboard screen without changing create/delete behavior.
- **Scope lock**:
  - Update screen only (`dashboard_configure` when flow mode is update)
  - Keep existing backend compatibility gates and fallback behavior intact
  - No storage model changes
  - Add optional admin-view-only visibility filtering using linked parent Home Assistant user IDs
- **Steps / detailed work items**
  1. [x] Convert update configure form to explicit section containers (`section()`)
     - Files: `custom_components/kidschores/helpers/dashboard_helpers.py`, `custom_components/kidschores/options_flow.py`
     - Target structure:
       - Section 1 (expanded): Kid views
       - Section 2 (expanded): Admin views
       - Section 3 (collapsed): Access & sidebar
       - Section 4 (collapsed): Template version
  2. [x] Reorder fields for decision-first flow and conditional reveal
     - Files: `custom_components/kidschores/helpers/dashboard_helpers.py`
     - Show admin template selectors only when selected admin layout requires them.
  3. [x] Replace ambiguous labels/descriptions with intent-first copy
     - File: `custom_components/kidschores/translations/en.json`
     - Replace terms like “Admin Mode” with clearer wording (e.g., “Admin layout”).
  4. [x] Unify template selector labels to dynamic human-friendly display names
     - File: `custom_components/kidschores/helpers/dashboard_helpers.py`
     - Label resolution strategy:
       - metadata display title (if present in template header) →
       - filename/key humanization (Propercase) →
       - raw key fallback.
  5. [x] Simplify release controls to one selector in update UX
     - Files: `custom_components/kidschores/helpers/dashboard_helpers.py`, `custom_components/kidschores/options_flow.py`, `custom_components/kidschores/translations/en.json`
     - Replace dual `release_mode` + `release_tag` UX with single “Dashboard template version” selector:
       - default = newest compatible
       - includes relevant compatible tags for explicit selection
       - avoid “pin” terminology in user-facing copy.
  6. [x] Add admin-view visibility policy control for update/create apply step
     - Files: `custom_components/kidschores/helpers/dashboard_helpers.py`, `custom_components/kidschores/options_flow.py`, `custom_components/kidschores/helpers/dashboard_builder.py`, `custom_components/kidschores/translations/en.json`
     - Behavior:
       - Add a simple selector for admin view visibility policy.
       - When policy is parent-linked, write HA `visible` user UUID list only on admin views.
       - Kid views remain unaffected.
       - If no parent HA users are linked, admin view stays unrestricted (no invalid empty user list).
  7. [x] Add/update focused options-flow tests for Part B behavior
     - File: `tests/test_options_flow_dashboard_release_selection.py`
     - Cases:
       - section presence and default collapsed/expanded state
       - conditional field visibility for admin layouts
       - single version selector default and non-default selection behavior
       - admin visibility policy passed through to builder behavior.
     - Progress note:
       - ✅ Added sectioned update payload regression (`test_dashboard_update_accepts_sectioned_configure_payload`)
       - ✅ Added conditional admin-layout reveal regression (`test_dashboard_update_reveals_per_kid_admin_template_on_mode_change`)
       - ✅ Added template label readability regression (`test_dashboard_template_labels_are_human_friendly`)
       - ✅ Existing admin visibility passthrough coverage remains in place
       - ✅ Translation copy updated to intent-first wording (Admin Layout) across dashboard configure + related validation errors
       - ✅ Added single-selector explicit release selection regression (`test_dashboard_update_non_default_release_selection_passes_pinned_tag`)
     - ✅ Added section + dashboard-configuration field order regression (`test_dashboard_update_schema_uses_expected_section_and_access_field_order`)
- **Key issues**
  - Form framework has limited dynamic controls; use simplest consistent conditional rendering supported by HA section forms.
  - Dynamic template labels must remain deterministic when metadata is missing.

### Dead dashboard code/constants scan (requested)

- **Scan status**: complete
- **Focused cleanup completed**:
  - Removed dead helper functions in `custom_components/kidschores/helpers/dashboard_helpers.py`:
    - `build_dashboard_style_options()`
    - `format_dashboard_confirm_summary()`
    - `format_dashboard_results()`
    - `build_dashboard_update_schema()`
    - `build_dashboard_delete_schema()`
  - Removed legacy options-flow paths in `custom_components/kidschores/options_flow.py`:
    - `async_step_dashboard_generator_confirm()`
    - `async_step_dashboard_generator_result()`
    - `async_step_dashboard_update()` wrapper
  - Removed stale constants in `custom_components/kidschores/const.py` (unused old dashboard flow/input/translation keys and old template path mode constants).
  - Removed orphan translation blocks in `custom_components/kidschores/translations/en.json`:
    - `step.dashboard_update`
    - `step.dashboard_generator_confirm`
    - `step.dashboard_generator_result`
    - selector entries `dashboard_style` and `dashboard_delete_selection`

## Testing & validation

- Tests executed:
  - `./utils/quick_lint.sh --fix` ✅ passed (ruff + format + mypy_quick + boundary checks)
  - `python -m pytest tests/test_setup_helper.py -q` ✅ 5/5 passed
  - `python -m pytest tests/test_dashboard_template_release_resolution.py tests/test_dashboard_builder_release_fetch.py tests/test_options_flow_dashboard_release_selection.py -q` ✅ 8/8 passed
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/kidschores` ✅ 0 errors
  - `./utils/quick_lint.sh --fix` ✅ passed after focused cleanup
  - `runTests` on dashboard release test set ✅ 8/8 passed after focused cleanup
- Additional gate note:
  - `mypy custom_components/kidschores/` ❌ blocked by unrelated external syntax issue in `/workspaces/core/homeassistant/helpers/device_registry.py:407`
- Outstanding tests (not run and why): None for this initiative scope; focused release/options-flow coverage and quality gates were executed.

## Notes & follow-up

- **Recommended product behavior (MVP)**:
  - Default to newest compatible release.
  - Expose a single explicit “Dashboard template version” selector for update mode.
  - Enforce one integration-defined minimum release floor.
  - Keep local templates as final safety net.
- **No storage schema migration expected** for MVP if release preference remains flow-scoped or stored in existing options fields.
- If long-term persistence per-dashboard is desired, create a follow-up initiative for persistent release pinning metadata.

### Worst-case recovery guarantee

- If remote release resolution fails, dashboard generation must still work from bundled templates shipped inside the integration package (`custom_components/kidschores/templates/`).
- If a user reinstalls/redownloads the integration, those bundled templates are restored to the versions included with that integration build.
- Operational caveat: existing already-generated Lovelace dashboards are stored configs; they are not automatically rewritten on reinstall.
- Recovery action for operators: rerun Dashboard Create/Update flow after reinstall to regenerate views from restored bundled templates.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS` (for example: `MY-INITIATIVE_PLAN_IN-PROCESS.md`). Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
