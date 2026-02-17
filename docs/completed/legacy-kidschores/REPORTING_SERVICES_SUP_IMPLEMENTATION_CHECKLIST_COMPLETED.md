# Reporting Services - Implementation Checklist

---

status: READY_FOR_HANDOFF
owner: Strategist Agent
created: 2026-02-14
parent_plan: REPORTING_SERVICES_IN-PROCESS.md
handoff_from: KidsChores Strategist
handoff_to: KidsChores Plan Agent
phase_focus: End-to-end implementation execution order

---

## Handoff button

[HANDOFF_TO_BUILDER_IMPLEMENT_REPORTING_NOW](REPORTING_SERVICES_SUP_BUILDER_HANDOFF.md)

## Purpose

Provide an execution-ready, helper-first implementation sequence for `generate_activity_report` and `export_normalized_data`.

## Execution order (must follow)

1. Constants and response contracts (`const.py`, `type_defs.py`)
2. Reporting helper foundation (`helpers/report_helpers.py`)
3. Service schemas and thin handlers (`services.py`)
4. Service docs (`services.yaml`)
5. Tests (new report/export service tests + diagnostics guard)
6. Quality gates + handback evidence

## File-by-file implementation tasks

### 1) `custom_components/kidschores/const.py`

- Add service constants:
  - `SERVICE_GENERATE_ACTIVITY_REPORT`
  - `SERVICE_EXPORT_NORMALIZED_DATA`
- Add service field constants for report/export APIs:
  - range mode (`last_7_days`, `last_30_days`, `custom`)
  - `start_date`, `end_date`
  - `kid_name`
  - `notify_service`, `report_title`
  - export section toggles (`include_ledger`, `include_periods`, `include_items`, `include_id_map`)
- Add any translation key constants required for new error/result strings.

### 2) `custom_components/kidschores/type_defs.py`

- Add TypedDict contracts for helper/service outputs:
  - `ReportRangeResult`
  - `ReportDailyBlock`
  - `ActivityReportResponse`
  - `NormalizedExportResponse`
- Keep fields additive and explicit for service response stability.

### 3) `custom_components/kidschores/helpers/report_helpers.py` (new)

- Create helper module and keep it read-only.
- Public helper functions to add:
  - `resolve_report_range(...) -> ReportRangeResult`
  - `build_activity_report(...) -> ActivityReportResponse`
  - `build_normalized_export(...) -> NormalizedExportResponse`
- Internal helper functions to add:
  - `_filter_kids(...)`
  - `_iter_ledger_entries_in_range(...)`
  - `_group_ledger_by_day(...)`
  - `_build_id_map(...)`
  - `_resolve_reference_name(...)`
  - `_render_report_markdown(...)`
- Time handling requirements:
  - use project datetime helpers (`utils/dt_utils.py`) and timezone-aware ISO handling
  - deterministic day grouping behavior
- Data source requirements:
  - ledger is primary for activity lines
  - period buckets supplement aggregate context (`point_periods`, `chore_periods`, `reward_periods`)

### 4) `custom_components/kidschores/services.py`

- Add schemas:
  - `GENERATE_ACTIVITY_REPORT_SCHEMA`
  - `EXPORT_NORMALIZED_DATA_SCHEMA`
- Implement thin handlers only:
  - `handle_generate_activity_report`
  - `handle_export_normalized_data`
- Handler responsibilities:
  - entry/coordinator resolution
  - input validation via schema
  - helper delegation
  - optional notify delivery (report handler only)
  - response return
- Register both with `supports_response=SupportsResponse.OPTIONAL`.
- Update `async_unload_services` list with both service names.

### 5) `custom_components/kidschores/services.yaml`

- Add both services with field definitions and examples.
- Document range presets and custom range requirements.
- Document optional `notify_service` behavior for report delivery.
- Document that export is normalized (UUID mapping included) and distinct from diagnostics.

### 6) `custom_components/kidschores/diagnostics.py`

- No behavior changes planned.
- If touched during implementation, ensure raw-export contract remains unchanged.

## Test implementation tasks

### A) `tests/test_report_services.py` (new)

- `test_generate_activity_report_last_7_days_returns_contract`
- `test_generate_activity_report_custom_range_requires_start_end`
- `test_generate_activity_report_filters_by_kid_name`
- `test_generate_activity_report_notify_unavailable_still_returns_response`
- `test_generate_activity_report_daily_grouping_uses_ledger`

### B) `tests/test_export_services.py` (new)

- `test_export_normalized_data_returns_contract`
- `test_export_normalized_data_contains_complete_id_map`
- `test_export_normalized_data_resolves_reference_ids_to_names`
- `test_export_normalized_data_respects_kid_filter`
- `test_export_normalized_data_respects_date_range`

### C) `tests/test_diagnostics.py`

- Keep existing diagnostics tests green.
- Add one focused non-regression check only if implementation touched diagnostics-adjacent behavior.

## Acceptance evidence required in handback

- Diff summary grouped by area:
  - constants/contracts
  - helper module
  - service handlers
  - service docs
  - tests
- Test output snippets for new report/export test files.
- Quality gate outputs:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/kidschores/`
  - `python -m pytest tests/test_report_services.py tests/test_export_services.py tests/test_diagnostics.py -v --tb=line`

## Risk controls during build

- Keep heavy logic out of `services.py`; helper-first is mandatory.
- Preserve diagnostics contract as raw recovery export.
- Ensure deterministic ordering in report/export outputs for stable tests.
- Fail gracefully when optional notify service is missing; return successful response with delivery status.

## Out of scope (do not implement in this handoff)

- Writing export/report files to disk.
- Email attachment transport workflows.
- Dashboard/UI rendering for report consumption.
- Any storage schema or migration changes.

## Builder delivery checklist

- [ ] Constants and type contracts complete
- [ ] `helpers/report_helpers.py` implemented (majority logic)
- [ ] Service schemas/handlers integrated and thin
- [ ] `services.yaml` documented
- [ ] New tests added and passing
- [ ] Quality gates complete
- [ ] Parent plan + handoff docs updated with implementation progress
