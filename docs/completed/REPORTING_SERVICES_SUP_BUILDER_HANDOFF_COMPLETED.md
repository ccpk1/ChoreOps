# Reporting Services - Builder Handoff

---

status: READY_FOR_HANDOFF
owner: Strategist Agent
created: 2026-02-14
parent_plan: REPORTING_SERVICES_IN-PROCESS.md
handoff_from: KidsChores Strategist
handoff_to: KidsChores Plan Agent
phase_focus: Phase 1 contract lock + Phase 2/3 MVP services

---

## Handoff button

[HANDOFF_TO_BUILDER_REPORTING_SERVICES_MVP](REPORTING_SERVICES_IN-PROCESS.md)

## Implementation runbook

- [Execution checklist](REPORTING_SERVICES_SUP_IMPLEMENTATION_CHECKLIST.md)

## Handoff objective

Implement two new custom services in `kidschores`:

1. markdown activity reporting (ledger-first + period-supplemented), and
2. normalized export (UUID-to-name mapped data package for users/automations).

Architectural directive: keep `services.py` thin. Place the majority of reporting/export logic in a dedicated helper module.

## Diligence findings (confirmed current-state)

- Services already use `supports_response=SupportsResponse.OPTIONAL` patterns and return dict payloads in CRUD flows.
  - File: `custom_components/kidschores/services.py`
- Ledger exists as kid-level transaction history (`ledger`) with stable fields:
  - `timestamp`, `amount`, `balance_after`, `source`, `reference_id`, `item_name`
  - File: `custom_components/kidschores/const.py`
- Period summaries already exist in storage and are maintained by `StatisticsManager`:
  - `point_periods`, `chore_periods`, `reward_periods`
  - File: `custom_components/kidschores/managers/statistics_manager.py`
- Diagnostics is intentionally raw-storage oriented (+ `config_entry_settings`) and must stay stable for restore workflows.
  - Files: `custom_components/kidschores/diagnostics.py`, `tests/test_diagnostics.py`
- Notification delivery path is available and testable via module-level helper + service existence checks.
  - File: `custom_components/kidschores/managers/notification_manager.py`

## UX/behavior contract (must implement exactly)

1. Add exactly two services:
   - `generate_activity_report`
   - `export_normalized_data`
2. Both services are response-first APIs:
   - if called with `return_response=True`, return structured output dicts.
3. Markdown report uses ledger as source-of-truth for day-by-day activity.
4. Report may include period-summary supplements (daily/weekly/monthly/all-time) when ledger coverage is sparse.
5. Report supports date range modes:
   - `last_7_days`
   - `last_30_days`
   - `custom` (`start_date` + `end_date` required)
6. Optional report delivery via `notify_service` is allowed, but response payload remains canonical output.
7. Normalized export must include UUID-to-name mapping tables and relation-friendly sections.
8. Diagnostics behavior is unchanged (no replacement, no contract drift).
9. No storage schema changes in MVP (read-only projection).
10. No file attachment/email-transport orchestration in MVP (service response + optional notify only).
11. Core transformation/render logic must live in helper module:

- `custom_components/kidschores/helpers/report_helpers.py`

12. Service handlers must only perform: schema validation, coordinator lookup, delegation to helper, optional notify dispatch, and response return.

## Required response contracts

### A) `generate_activity_report` response

- `range`: `{mode, start_iso, end_iso, timezone}`
- `scope`: `{kid_filter_applied, kid_ids}`
- `summary`: `{total_earned, total_spent, net, transactions_count}`
- `daily`: list of day blocks ordered newest/oldest (pick one and document)
  - each block: `{date, earned, spent, net, transactions, markdown_section}`
- `markdown`: full render string
- `supplemental`: optional period-derived rollup block
- `delivery`: `{notify_attempted, notify_service, delivered}`

### B) `export_normalized_data` response

- `meta`: `{export_version, generated_at, range, filters}`
- `id_map`: `{kids, parents, chores, rewards, bonuses, penalties}` where each map is `{uuid: name}`
- `kids`: normalized kid records (selective, not full raw blob)
- `ledger_entries`: flattened entries with resolved names where possible
- `period_summaries`: normalized point/chore/reward period snapshots
- `raw_refs`: optional minimal UUID refs for traceability

## Implementation sequence for builder

### Package A – Contracts and schemas (first)

- [ ] Add service constants and service fields
  - File: `custom_components/kidschores/const.py`
  - Add `SERVICE_GENERATE_ACTIVITY_REPORT`, `SERVICE_EXPORT_NORMALIZED_DATA`
  - Add service field constants: range mode, start/end, kid name, notify service, include sections

- [ ] Add service schemas
  - File: `custom_components/kidschores/services.py`
  - Keep validation strict (reject undocumented fields), aligned to existing service schema style

- [ ] Add/extend response typed definitions
  - File: `custom_components/kidschores/type_defs.py`

- [ ] Create dedicated reporting helper module
  - File: `custom_components/kidschores/helpers/report_helpers.py` (new)
  - Include public helper API:
    - `resolve_report_range(...)`
    - `build_activity_report(...)`
    - `build_normalized_export(...)`
  - Keep module read-only (no `_persist()`, no manager writes)

### Package B – Markdown report handler

- [ ] Implement `handle_generate_activity_report`
  - File: `custom_components/kidschores/services.py`
  - Register with `supports_response=SupportsResponse.OPTIONAL`
  - Delegate all heavy logic to `helpers/report_helpers.py`

- [ ] Implement date range resolver with timezone-safe boundaries
  - File: `custom_components/kidschores/helpers/report_helpers.py`
  - Reuse existing datetime helpers from `utils/dt_utils.py` when practical

- [ ] Implement ledger grouping + markdown builder
  - File: `custom_components/kidschores/helpers/report_helpers.py`
  - Prefer deterministic sort order for test stability

- [ ] Add optional notify delivery integration
  - File: `custom_components/kidschores/services.py`
  - Use safe send path and do not fail service if notify target unavailable; report delivery outcome in response

### Package C – Normalized export handler

- [ ] Implement `handle_export_normalized_data`
  - File: `custom_components/kidschores/services.py`
  - Register with `supports_response=SupportsResponse.OPTIONAL`
  - Delegate all heavy logic to `helpers/report_helpers.py`

- [ ] Build `id_map` and normalized sections
  - File: `custom_components/kidschores/helpers/report_helpers.py`
  - Ensure mapping covers all referenced IDs in ledger/export body

- [ ] Add filter support
  - File: `custom_components/kidschores/helpers/report_helpers.py`
  - Filter by kid and date range without mutating coordinator data

- [ ] Keep diagnostics untouched
  - Files: `custom_components/kidschores/diagnostics.py`, `tests/test_diagnostics.py`
  - Only add tests if needed to prove no regressions

### Package D – Service docs + tests + validation

- [ ] Document services in `services.yaml`
  - File: `custom_components/kidschores/services.yaml`
  - Include field definitions, presets, and example responses

- [ ] Add focused service tests
  - Files:
    - `tests/test_report_services.py` (new)
    - `tests/test_export_services.py` (new)
  - Follow existing service testing patterns with `return_response=True`

- [ ] Add diagnostics non-regression assertion (if needed)
  - File: `tests/test_diagnostics.py`

- [ ] Run required gates
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/kidschores/`
  - `python -m pytest tests/test_report_services.py tests/test_export_services.py tests/test_diagnostics.py -v --tb=line`

## Acceptance criteria

### AC-1 report service

- Returns markdown and structured summary for `last_7_days`, `last_30_days`, and valid custom ranges.
- Groups activity by day using ledger entries as primary source.
- Optional notify delivery does not break response path.

### AC-2 export service

- Returns normalized export object with complete UUID-to-name mapping for included sections.
- Supports kid/date filters deterministically.
- Includes metadata with export version and generation timestamp.

### AC-3 diagnostics safety

- Existing diagnostics contract (raw storage + settings) remains unchanged.

### AC-4 architecture compliance

- No storage writes, no `_persist()`, no schema version bump.
- Services remain thin orchestration; transformation/render logic is helper-owned.

## Known pitfalls to avoid

1. **Do not treat diagnostics as export replacement**
   - Keep diagnostics for backup/restore intent.
2. **Do not hardcode labels/user-facing strings**
   - Use constants/translations where applicable.
3. **Do not rely on non-deterministic ordering**
   - Sort dates and entries explicitly for test consistency.
4. **Do not emit partial UUID-only export without mapping**
   - This is the specific gap this service must solve.
5. **Do not fail whole report on missing notify service**
   - Return response + delivery status.
6. **Do not accumulate major logic in `services.py`**

- Move composition/render/mapping logic into `helpers/report_helpers.py`.

## Suggested test cases (minimum)

### `tests/test_report_services.py`

- `test_report_last_7_days_returns_markdown_and_summary`
- `test_report_custom_range_requires_start_end`
- `test_report_filters_single_kid`
- `test_report_notify_service_unavailable_still_returns_response`
- `test_report_daily_grouping_matches_ledger_entries`

### `tests/test_export_services.py`

- `test_export_contains_id_map_for_all_sections`
- `test_export_resolves_reference_ids_to_names`
- `test_export_respects_kid_filter`
- `test_export_respects_date_range_filter`
- `test_export_response_contract_stable`

### `tests/test_diagnostics.py`

- Existing assertions remain green; add targeted non-regression only if builder touches related code.

## Rollback plan

If service rollout causes regressions:

1. Keep constants/schemas but temporarily unregister new services in `async_setup_services`.
2. Preserve diagnostics unchanged.
3. Re-enable services behind follow-up patch after response contract/test stabilization.

## Out of scope for this handoff

- Writing report/export data to files in `/config/www`.
- Email attachments generation lifecycle.
- UI cards/dashboard changes for report rendering.
- Any migration or storage schema restructuring.

## Builder delivery checklist

- [ ] Package A complete (constants, fields, schemas, type defs)
- [ ] Package B complete (report service + optional notify)
- [ ] Package C complete (normalized export service)
- [ ] Package D complete (tests/docs/validation)
- [ ] Parent plan summary updated with implementation progress and blockers
