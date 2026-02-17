## Initiative snapshot

- **Name / Code**: Reporting services (`REPORT-SVC-2026`)
- **Target release / milestone**: `v0.5.x` post-beta hardening
- **Owner / driver(s)**: KidsChores integration maintainers (Builder lane)
- **Status**: Completed (archived)

## Summary & immediate steps

| Phase / Step                                     | Description                                                      | % complete | Quick notes                                                                                    |
| ------------------------------------------------ | ---------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------------------------- |
| Phase 1 – Service contract + helper architecture | Define schemas, constants, and a dedicated report helper module  | 100%       | Completed with validation gates passing                                                        |
| Phase 2 – Markdown activity report service       | Add date-range report (ledger-first + period supplementation)    | 100%       | Handler wired with optional notify delivery and helper supplemental rollups                    |
| Phase 3 – Normalized export service              | Add export with UUID-to-name mapping and optional filters        | 100%       | Export handler wired with response-first payload and helper filter toggles                     |
| Phase 4 – Validation + docs                      | Add tests and service docs, run quality gates                    | 100%       | Added report/export tests, diagnostics regression run, docs updated                            |
| Phase 5 – Scope pivot (v0.5.x)                   | Narrow to one 7-day report service + retention-aligned ledger    | 100%       | Export removed, report fixed to 7-day with optional HTML output, stats query boundary enforced |
| Phase 6 – Canonical rollup dedup                 | Remove helper fallback aggregation and centralize manager rollup | 100%       | Report helper now consumes `StatisticsManager.get_report_rollup()` as single source of truth   |

1. **Key objective** – Deliver one high-quality 7-day activity report service (markdown + optional HTML conversion) with manager-owned period rollups.
2. **Summary of recent work**

- Completed Phase 1 contract architecture: new service constants/fields, new report/export schemas, response TypedDict contracts, and helper module scaffold (`helpers/report_helpers.py`).
- Kept `services.py` thin by introducing helper-first structure and exporting helper module from `helpers/__init__.py`.
- Completed Phase 2 implementation: added `handle_generate_activity_report` service handler, response wiring, custom-range validation, and optional notify delivery path.
- Added delivery hotfix to sanitize report message bodies by stripping accidental YAML block wrappers (for example `report: |-`) before kid-facing notify delivery.
- Follow-up correctness fix: weekly summary/highlights now consume in-range rollup metrics (not all-time) for completed chores, bonus points, and reward claimed/spent values.
- Added period-derived supplemental rollup output in `helpers/report_helpers.py` using `point_periods`, `chore_periods`, and `reward_periods` all-time buckets.
- Expanded report supplemental payload with streak and badge summaries (including missed streak and badge award totals).
- Expanded normalized export payload with additive `streaks`/`badges` fields per kid and top-level `gamification` block.
- Added report localization support via `translations_custom/en_report.json`, `report_language` service field, and report translation helper fallback logic.
- Product direction updated: no estimation for partial historical buckets; return best representation by available fidelity (ledger first, then period buckets) with explicit coverage notes.
- Architecture alignment decision: report composition must query period data through `StatisticsManager` APIs (service boundary), not directly via ad hoc store traversal in report helper.
- Scope pivot approved: simplify current rollout to a single 7-day activity report service with markdown output and optional HTML conversion for email workflows.
- Registered/unregistered `generate_activity_report` service in lifecycle lists.
- Validation results: `quick_lint` passed (including mypy), focused regression tests passed (`80 passed`).
- Verified current architecture already supports response-enabled services (`supports_response=SupportsResponse.OPTIONAL`) in `services.py`.
- Confirmed ledger (`kids[*].ledger`) and period buckets (`point_periods`, `chore_periods`, `reward_periods`) are available and retention-governed.
- Confirmed diagnostics currently returns near-raw storage data plus settings, which is excellent for recovery but not ideal as a user report/export API.

3. **Next steps (short term)**

- Add focused report/export service tests in Phase 4 and update service docs.
- Validate export/report contracts with `return_response=True` coverage.
- Keep diagnostics contract unchanged while documenting service-vs-diagnostics distinction.
- Implement Phase 5 pivot plan:
  - ledger retention by age aligned to `retention_daily` (keep a safety cap)
  - remove broad report/export service surface from current attempt
  - keep one report service for 7-day activity report
  - layer ledger + period buckets for all point-source item domains
  - add markdown renderer + optional HTML conversion
  - translation-first report key contract (no user-facing hardcoded text in render paths)
- Implement Phase 6 dedup plan:
  - remove helper-local fallback aggregation over raw period buckets
  - consume canonical manager rollup payload in report helper
  - keep `services.py` orchestration-only and pass manager dependency explicitly

4. **Risks / blockers**
   - Ledger retention cap means long ranges may be partially represented if entries were pruned.

- Pivot risk: stale constants/docs/tests from broad export implementation can remain if cleanup is incomplete.
- Translation risk: renderer text drift if translation keys are not fully enumerated and validated.
- Timezone/day-boundary grouping must consistently use existing datetime helpers to avoid off-by-one-day errors.
- Notify/email delivery must remain optional to keep service behavior deterministic and testable.

5. **References**
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `docs/CODE_REVIEW_GUIDE.md`
   - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
   - `docs/RELEASE_CHECKLIST.md`
6. **Decisions & completion check**
   - **Decisions captured**:
   - Build two services (report + export), not diagnostics-only substitution.
   - Put majority of report/export logic in a dedicated helper module, not in `services.py`.
   - MVP returns service response payloads first; notify/email delivery is optional in same API.
   - No schema migration required for MVP (read-only composition from existing storage).

- **Completion confirmation**: `[x]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) and owner approval received to close this initiative.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update.

## Tracking expectations

- **Summary upkeep**: Update percentages and blockers after each phase lands.
- **Detailed tracking**: Keep implementation specifics in phase sections; summary remains high level.

## Detailed phase tracking

### Phase 1 – Service contract + helper architecture

- **Goal**: Define stable service contracts and create a dedicated report helper module for read-only composition logic.
- **Steps / detailed work items**
  - [x] Add service constants and service field constants for both APIs.
    - File: `custom_components/kidschores/const.py`
    - Line hints: service constants block around `SERVICE_*` (`~2882+`) and service fields (`~2928+`)
    - Add: `SERVICE_GENERATE_ACTIVITY_REPORT`, `SERVICE_EXPORT_NORMALIZED_DATA`, date/filter/output field constants
  - [x] Add service schemas for report and export payload validation.
    - File: `custom_components/kidschores/services.py`
    - Line hints: schema section near existing reset/CRUD schemas (`~50-420`)
    - Include presets (`last_7_days`, `last_30_days`, `custom`), optional `kid_name`, and output mode selector
  - [x] Create dedicated helper module for reporting/export composition.
    - File: `custom_components/kidschores/helpers/report_helpers.py` (new)
    - Responsibilities: date range resolution, ledger grouping, markdown rendering, normalized export projection, UUID-to-name mapping
    - Constraint: read-only only (no manager mutations, no `_persist()`)
  - [x] Add lightweight helper API surface designed for service delegation.
    - File: `custom_components/kidschores/helpers/report_helpers.py`
    - Suggested functions: `build_activity_report(...)`, `build_normalized_export(...)`, `resolve_report_range(...)`
  - [x] Define response payload contracts (typed dicts) for report and export.
    - File: `custom_components/kidschores/type_defs.py`
    - Add explicit response structures for predictable automations/tests
- **Key issues**
  - Keep naming/translation constants aligned with project patterns (no hardcoded user-facing strings).
  - Avoid introducing data duplication into storage for reporting convenience.

### Phase 2 – Markdown activity report service

- **Goal**: Implement a daily activity markdown report that is ledger-first and period-supplemented.
- **Steps / detailed work items**
  - [x] Add `handle_generate_activity_report` service handler with `supports_response=SupportsResponse.OPTIONAL`.
    - File: `custom_components/kidschores/services.py`
    - Line hints: follow existing response-enabled patterns around CRUD handlers (`~758`, `~1531`, `~1646`)
  - [x] Implement ledger-driven daily grouping and totals in helper layer.
    - File: `custom_components/kidschores/helpers/report_helpers.py`
    - Read from `kids_data[kid_id][ledger]` using `DATA_LEDGER_*` constants
  - [x] Supplement with period-derived context where ledger is thin/pruned in helper layer.
    - Files: `custom_components/kidschores/helpers/report_helpers.py`, `custom_components/kidschores/managers/statistics_manager.py` (read pattern only)
    - Use existing `point_periods` / `chore_periods` / `reward_periods` buckets for summary blocks
  - [x] Add optional delivery path via notify target while keeping response as canonical output.
    - File: `custom_components/kidschores/services.py`
    - Service handler delegates report body generation to helper and handles notify integration
    - Inputs: optional `notify_service` (e.g., `notify.family_email`) and optional `title`
  - [x] Register/unregister service in service lifecycle.
    - File: `custom_components/kidschores/services.py`
    - Line hints: registration near tail (`~2258+`) and unload list (`~2384+`)
- **Key issues**
  - Markdown output must remain deterministic for tests.
  - Date boundaries must use timezone-aware helpers and inclusive/exclusive semantics documented in `services.yaml`.

### Phase 3 – Normalized export service

- **Goal**: Provide export data for users that includes UUID-to-name mapping and readable relations.
- **Steps / detailed work items**
  - [x] Add `handle_export_normalized_data` service handler (response-first).
    - File: `custom_components/kidschores/services.py`
    - Service delegates export build to helper and returns structured dict
  - [x] Build normalized sections with explicit mapping dictionaries in helper layer.
    - File: `custom_components/kidschores/helpers/report_helpers.py`
    - Sections: `meta`, `kids`, `parents`, `chores`, `rewards`, `ledger_entries`, `period_summaries`, `id_map`
  - [x] Add optional export filters (`kid_name`, date range, include/exclude sections) in helper layer.
    - File: `custom_components/kidschores/helpers/report_helpers.py`
    - Keep defaults simple: all kids, last 30 days, all sections
  - [x] Keep diagnostics unchanged and document distinction.
    - Files: `custom_components/kidschores/diagnostics.py`, `custom_components/kidschores/services.yaml`
    - Diagnostics = raw recovery snapshot; export service = human/automation-friendly normalized projection
  - [x] Register/unregister service in lifecycle lists.
    - File: `custom_components/kidschores/services.py`
- **Key issues**
  - Large response payloads may need optional section toggles to avoid automation payload bloat.
  - Export contract must be versioned in payload metadata to permit future additive fields.

### Phase 4 – Validation + docs

- **Goal**: Add focused test coverage and service documentation for maintainable rollout.
- **Steps / detailed work items**
  - [x] Add service tests for markdown report behavior.
    - File: `tests/test_report_services.py` (new)
    - Cover: preset/custom ranges, per-day grouping, no-data output, notify optional path
  - [x] Add service tests for normalized export behavior.
    - File: `tests/test_export_services.py` (new)
    - Cover: UUID-name mapping completeness, filters, section toggles, response shape
  - [x] Add regression tests confirming diagnostics behavior is unchanged.
    - File: `tests/test_diagnostics.py`
    - Confirm raw storage + `config_entry_settings` contract remains intact
  - [x] Document both services in Home Assistant service docs.
    - File: `custom_components/kidschores/services.yaml`
    - Add fields, examples, and response/delivery semantics
  - [x] Run targeted quality gates.
    - Commands:
      - `./utils/quick_lint.sh --fix`
      - `mypy custom_components/kidschores/`
      - `python -m pytest tests/test_report_services.py tests/test_export_services.py tests/test_diagnostics.py -v --tb=line`
- **Key issues**
  - Keep tests scenario-based per guide (Stårblüm fixtures/scenarios) and avoid direct storage mutation unless necessary.

## Testing & validation

- **Service tests**: Add dedicated tests for both new services using `hass.services.async_call(..., return_response=True)` patterns.
- **Diagnostics regression**: Preserve current diagnostics intent (raw recovery snapshot).
- **Validation gates**:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/kidschores/`
  - `python -m pytest tests/test_report_services.py tests/test_export_services.py tests/test_diagnostics.py -v --tb=line`
- **Phase 1 executed evidence**:
  - `./utils/quick_lint.sh --fix` ✅ passed (ruff + format + mypy + boundary checks)
  - `python -m pytest tests/test_rotation_fsm_states.py tests/test_workflow_chores.py tests/test_shared_chore_features.py -q` ✅ `80 passed`
- **Phase 2 executed evidence**:
  - `./utils/quick_lint.sh --fix` ✅ passed (ruff + format + mypy + boundary checks)
  - `python -m pytest tests/test_rotation_fsm_states.py tests/test_workflow_chores.py tests/test_shared_chore_features.py -q` ✅ `80 passed`
- **Phase 3 executed evidence**:
  - `./utils/quick_lint.sh --fix` ✅ passed (ruff + format + mypy + boundary checks)
  - `python -m pytest tests/test_rotation_fsm_states.py tests/test_workflow_chores.py tests/test_shared_chore_features.py -q` ✅ `80 passed`
- **Phase 4 executed evidence**:
  - `./utils/quick_lint.sh --fix` ✅ passed (ruff + format + mypy + boundary checks)
  - `python -m pytest tests/test_report_services.py tests/test_export_services.py tests/test_translations_custom.py -q` ✅ `94 passed`
  - `python -m pytest tests/test_diagnostics.py -q` ✅ `8 passed`

## Notes & follow-up

## Phase 5 – Scope pivot (approved)

- **Goal**: Reduce current scope to one high-quality, extensible report service while aligning with architecture standards and translation-first rendering.

### Decisions captured (Phase 5)

- Keep reporting simple for now:
  - one service that produces a **7-day activity report**
  - markdown output as canonical content
  - optional HTML conversion for email delivery
- Do **not** implement estimation/proration for partial historical buckets.
- Best-representation policy over time:
  - use ledger for exact event timeline
  - use period buckets via `StatisticsManager` query methods for aggregate representation
  - expose coverage/source notes in response
- Retention policy update:
  - ledger pruning should respect time retention threshold (`retention_daily`) instead of count-only pruning
  - keep a high safety cap to prevent unbounded growth

### Architecture enforcement updates

- `services.py` remains orchestration-only (input validation, manager/helper delegation, optional notify delivery).
- `report_helpers.py` remains renderer/composition layer, but period data access must come through `StatisticsManager` methods.
- Any new period/range query logic required by reports should be added to `StatisticsManager` as reusable APIs.

### Translation setup requirements (explicit)

- Maintain translation-first renderer contract:
  - all report section labels/titles/phrasing sourced from report translation file(s)
  - no hardcoded user-facing strings in markdown/html render paths
- Keep `translations_custom/en_report.json` as source of truth for report copy.
- Add test guardrails to ensure required report translation keys exist and fallback behavior remains stable.
- Ensure markdown and html renderers consume the same translation key set for consistency.

### Cleanup / no-remnants checklist

- Remove deprecated service surfaces introduced in broad attempt (export and extra report modes/fields not in pivot scope).
- Remove unused constants/schema fields/docs for removed surfaces.
- Remove or rewrite tests that validate removed behavior.
- Re-run focused and quality gates after cleanup to confirm no dead paths remain.
- Update `services.yaml` and `translations/en.json` to match final pivoted API only.

### Phase 5 implementation checklist

- [x] Add ledger age-based prune path using `retention_daily` + safety cap.
- [x] Add reusable `StatisticsManager` query methods for report aggregation windows.
- [x] Refactor report composition to use manager query methods for period aggregates.
- [x] Remove export service registration/schema/docs/tests for current release scope.
- [x] Restrict report service contract to 7-day output (+ optional html conversion option).
- [x] Ensure translation key completeness for markdown/html rendering.
- [x] Run quality gates + focused report tests; update executed evidence.

### Phase 5 executed evidence

- `./utils/quick_lint.sh --fix` ✅ passed (ruff + format + mypy + boundary checks)
- `python -m pytest tests/test_report_services.py tests/test_diagnostics.py -q` ✅ `14 passed`

## Phase 6 – Canonical rollup dedup (approved)

- **Goal**: Eliminate duplicate report aggregation paths and make `StatisticsManager` rollup APIs the only source for supplemental report totals.

### Phase 6 implementation checklist

- [x] Refactor `StatisticsManager.get_report_rollup()` internals to use shared helper methods for metric and collection rollups.
- [x] Add canonical empty rollup structure and shared streak rollup helper in manager layer.
- [x] Normalize manager rollup contract naming for rewards (`in_range_points_spent` / `all_time_points_spent`).
- [x] Remove helper fallback/all-time recomputation path in `report_helpers.py` (manager dependency required).
- [x] Update report helper callers/tests to use manager-only rollup dependency.
- [x] Add focused manager rollup contract tests.
- [x] Re-run validation gates and focused report tests.

### Phase 6 executed evidence

- `./utils/quick_lint.sh --fix` ✅ passed (ruff + format + mypy + boundary checks)
- `python -m pytest tests/test_report_services.py tests/test_statistics_manager_report_rollup.py -v --tb=line` ✅ `10 passed`

- **Feasibility assessment**
  - This is **highly reasonable** with current architecture.
  - Markdown report service is straightforward because ledger and period buckets already exist and services already support response payloads.
  - A diagnostics-only workaround is acceptable for recovery workflows, but insufficient for family-readable exports due to UUID-heavy structure and missing normalized relation views.

- **MVP recommendation**
  1. Ship report + export services with response payloads.
  2. Add optional `notify_service` delivery for report markdown.
  3. Defer file-writing/email attachment mechanics to a later increment.

- **Schema impact**
  - No `SCHEMA_VERSION` increment planned for MVP (read-only reporting/export projection).

- **Layering enforcement**
  - `services.py` should validate inputs, resolve coordinator, delegate to helper, and manage optional notify delivery only.
  - Majority of transformation/render logic belongs in `helpers/report_helpers.py`.
