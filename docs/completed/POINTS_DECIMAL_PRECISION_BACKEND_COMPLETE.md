# Initiative plan: backend decimal precision for points

## Initiative snapshot

- **Name / Code**: Backend decimal precision for points (`POINTS_DECIMAL_PRECISION_BACKEND`)
- **Target release / milestone**: v0.5.x next patch/minor
- **Owner / driver(s)**: ChoreOps maintainers
- **Status**: In progress

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
| --- | --- | ---: | --- |
| Phase 1 – Contracts & validation | Remove integer-only input restrictions from backend settings and services | 100% | Shared decimal parser added; service and flow contracts now accept 2-decimal values |
| Phase 2 – Runtime read consistency | Eliminate backend truncation paths that cast stored point values to integers | 100% | Reward affordability, legacy point sensors, and approver notification payloads now preserve decimals |
| Phase 3 – Tests & validation | Add end-to-end decimal coverage for services, settings, and read models | 100% | Targeted decimal coverage now spans services, helpers, diagnostics, backups, sensors, and notifications |
| Phase 4 – Docs & deferred frontend handoff | Update backend-facing docs and record dashboard follow-on scope | 100% | Service docs, wiki pages, and historical completed-plan notes now reflect backend decimal support; frontend/dashboard work remains deferred |

1. **Key objective** – Allow 2-digit precision decimal points across the backend contract, runtime behavior, and backend documentation while preserving existing float-safe storage and rounding behavior.
2. **Summary of recent work** – Phase 4 is implemented, and the late follow-up backend sweep is now broader than the original manual repro: chore points, badge awards, reward cost, bonus points, penalty points, achievement reward points, and challenge reward points now all use the shared 2-decimal parser and hundredth-step selectors where users author point amounts. Dashboard/frontend rendering remains explicitly deferred.
3. **Next steps (short term)** – Run the final full validation pass when approved, then close this backend initiative and open the separate frontend/dashboard follow-up.
4. **Risks / blockers** – Full pytest is still intentionally deferred until the final completion pass by instruction because the suite is long-running. No backend behavior work remains open in this plan.
5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
   - [docs/completed/MANUAL_POINTS_ADJUSTMENT_SERVICE_COMPLETED.md](../completed/MANUAL_POINTS_ADJUSTMENT_SERVICE_COMPLETED.md)
   - [docs/completed/DEFAULT_CHORE_POINTS_OPTION_COMPLETED.md](../completed/DEFAULT_CHORE_POINTS_OPTION_COMPLETED.md)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Decimal precision remains capped at 2 fractional digits; this initiative does not expand precision beyond the existing backend rounding contract.
     - `manual_adjust_points` should accept signed non-zero decimal amounts with up to 2 fractional digits.
     - `default_chore_points` should accept positive decimal values with up to 2 fractional digits and continue living in `config_entry.options`.
     - No `.storage/choreops/choreops_data` schema change is expected; this is a contract and consumer-alignment effort, not a storage migration.
     - Dashboard/template rendering changes are out of scope for this document and should be handled in a follow-up frontend initiative after backend validation is complete.
  - **Completion confirmation**: `[ ]` All follow-up items completed (implementation, tests, docs, and deferred frontend handoff notes) before requesting owner approval to mark initiative done. Only the final full-suite validation pass remains deferred.

> **Important:** Keep the entire Summary section current after each meaningful implementation update so backend and later frontend work do not drift apart.

## Tracking expectations

- **Summary upkeep**: Refresh phase percentages, quick notes, and blockers after each meaningful implementation batch or decision change.
- **Detailed tracking**: Keep file-level implementation notes in the phase sections below; keep the summary concise.

## Detailed phase tracking

### Phase 1 – Contracts & validation

- **Goal**: Replace integer-only backend input contracts with decimal-safe validation that matches the existing 2-decimal storage and math model.
- **Steps / detailed work items**
  - [x] Replace `_validate_non_zero_integer_amount` in [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L198) with a shared decimal-safe validator/parser that accepts signed non-zero values and rejects more than 2 fractional digits.
  - [x] Update `MANUAL_ADJUST_POINTS_SCHEMA` in [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L367-L376) so the service contract accepts decimal amounts instead of whole numbers only.
  - [x] Update `handle_manual_adjust_points` in [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L2462-L2528) to stop coercing the service amount through `int(...)` before deposit/withdraw routing.
  - [x] Update points settings schema builders in [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L185-L224) and [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L3223-L3260) so `default_chore_points` accepts a positive decimal value rather than `cv.positive_int`.
  - [x] Update points settings validation in [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L246-L253) and [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L3516-L3531) to enforce `> 0` and a 2-decimal maximum without `int(...)` parsing.
  - [x] Review related constants and defaults in [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L794-L823) and [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L1731-L1746) to confirm type hints/default maps stay coherent once `default_chore_points` becomes decimal-capable.
  - [x] Update backend translation error/help text in [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json#L502) and [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json#L550-L553) so they describe decimal support accurately.
- **Key issues**
  - Completed plans explicitly documented integer-only behavior, so this phase must treat the contract reversal as deliberate and fully update validation, translations, and service descriptions together.
  - Prefer a shared point-value parser/validator over separate ad hoc service and flow conversions to avoid reintroducing backend drift.

### Phase 2 – Runtime read consistency

- **Goal**: Make backend entities, summaries, and notifications reflect stored decimal values consistently instead of truncating them.
- **Steps / detailed work items**
  - [x] Review reward affordability logic in [custom_components/choreops/sensor.py](../../custom_components/choreops/sensor.py#L2733) and remove `int(...)` coercion where cost comparison should remain decimal-accurate.
  - [x] Review achievement/progress aggregation in [custom_components/choreops/sensor.py](../../custom_components/choreops/sensor.py#L3031) and nearby percentage/summary calculations so point totals are not truncated before presentation or attribute generation.
  - [x] Update legacy point sensor paths in [custom_components/choreops/sensor_legacy.py](../../custom_components/choreops/sensor_legacy.py#L610), [custom_components/choreops/sensor_legacy.py](../../custom_components/choreops/sensor_legacy.py#L688), and [custom_components/choreops/sensor_legacy.py](../../custom_components/choreops/sensor_legacy.py#L766) to preserve decimal point values or explicitly round to the shared 2-decimal policy instead of casting to `int`.
  - [x] Update notification payload generation in [custom_components/choreops/managers/notification_manager.py](../../custom_components/choreops/managers/notification_manager.py#L2109) so point values sent into translated notification text do not truncate decimal chore rewards.
  - [x] Audit adjacent backend consumers that compare, summarize, or serialize points for integer assumptions, starting with points defaults in [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py#L605-L605) and [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py#L1629-L1630), to ensure newly accepted decimal settings are carried through the runtime path intact.
  - [x] Confirm manager/runtime fallback behavior still follows the documented order in [custom_components/choreops/managers/chore_manager.py](../../custom_components/choreops/managers/chore_manager.py#L873-L880) when `default_chore_points` is decimal.
- **Key issues**
  - Some attributes are counts and must remain integers; this phase needs to distinguish “point amounts” from “event counts” so only true currency-like values change behavior.
  - Legacy sensors may expose long-standing integer expectations; any compatibility impact should be called out in release notes and docs rather than hidden.

### Phase 3 – Tests & validation

- **Goal**: Add focused test coverage that proves decimal support works end to end across service input, settings validation, and backend read models.
- **Steps / detailed work items**
  - [x] Replace the integer-only expectation in [tests/test_points_services.py](../../tests/test_points_services.py#L206) with decimal acceptance coverage for `manual_adjust_points`, while retaining rejection tests for `0`, malformed values, and values beyond 2 decimal places.
  - [x] Add service behavior assertions in [tests/test_points_services.py](../../tests/test_points_services.py) that verify positive and negative decimal manual adjustments update balances and ledger entries correctly.
  - [x] Extend helper/flow validation coverage around [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L246-L253) and [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L3516-L3531), using the appropriate points helper tests to prove `default_chore_points` accepts values like `2.5` and rejects values with more than 2 fractional digits.
  - [x] Add or update diagnostics/backup assertions, using existing settings coverage such as [tests/test_diagnostics.py](../../tests/test_diagnostics.py#L286), to confirm decimal `default_chore_points` and decimal `points_adjust_values` survive serialization unchanged.
  - [x] Add targeted sensor and notification tests for decimal presentation/attributes so backend read models do not silently regress to integer truncation.
  - [x] Run targeted validation first (`tests/test_economy_engine.py`, `tests/test_points_services.py`, points helper tests, diagnostics tests), then run the required quality gates from this repo (`./utils/quick_lint.sh --fix`, `mypy custom_components/choreops/`, `python -m pytest tests/ -v --tb=line`).
- **Key issues**
  - Current tests already prove the float math layer works, so new coverage should concentrate on contract edges and consumer behavior rather than duplicating engine tests.
  - Snapshot-like attribute tests should check both raw numeric values and any translated/message payloads that currently lose precision.

### Phase 4 – Docs & deferred frontend handoff

- **Goal**: Align backend-facing documentation with the new decimal contract and leave a clean handoff for the later dashboard/frontend initiative.
- **Steps / detailed work items**
  - [x] Update service documentation in [custom_components/choreops/services.yaml](../../custom_components/choreops/services.yaml#L344-L385) so `manual_adjust_points` describes signed decimal amounts with up to 2 fractional digits instead of whole numbers only.
  - [x] Update completed-plan assumptions referenced by this change, especially [docs/completed/MANUAL_POINTS_ADJUSTMENT_SERVICE_COMPLETED.md](../completed/MANUAL_POINTS_ADJUSTMENT_SERVICE_COMPLETED.md) and [docs/completed/DEFAULT_CHORE_POINTS_OPTION_COMPLETED.md](../completed/DEFAULT_CHORE_POINTS_OPTION_COMPLETED.md), with a short note or follow-up cross-reference if needed so future archaeology does not misread the old integer-only decisions as still active policy.
  - [x] Update user-facing backend docs in [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json#L550-L553), [choreops-wiki/Configuration:-Points.md](../../../choreops-wiki/Configuration:-Points.md#L26), and [choreops-wiki/Services:-Reference.md](../../../choreops-wiki/Services:-Reference.md#L92-L106) to describe decimal support consistently.
  - [x] Record the deferred frontend/dashboard follow-on scope in this plan, starting with known truncation anchors in [choreops-dashboards/templates/user-gamification-premier-v1.yaml](../../../choreops-dashboards/templates/user-gamification-premier-v1.yaml#L90-L90) and vendored templates such as [custom_components/choreops/dashboards/templates/user-chores-standard-v1.yaml](../../custom_components/choreops/dashboards/templates/user-chores-standard-v1.yaml#L88-L95).
  - [x] Confirm release-note wording calls out that backend decimal support is now consistent, while dashboard rendering improvements will land in a separate follow-up.
- **Key issues**
  - The dashboard repo and vendored dashboard templates must remain synchronized, so frontend changes should not be mixed into this backend initiative.
  - Old wiki/service examples currently reinforce whole-number behavior; leaving them unchanged would create immediate support confusion after backend changes ship.

## Testing & validation

- Baseline analysis already completed:
  - `python -m pytest tests/test_economy_engine.py tests/test_points_services.py -q`
  - Result: passed during investigation, confirming the existing float math layer is stable and the current manual-adjust integer restriction is covered.
- Phase 1 build-pass validation completed:
  - `./utils/quick_lint.sh --fix`
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
  - `python -m pytest tests/test_economy_engine.py tests/test_points_services.py tests/test_points_helpers.py tests/test_diagnostics.py -v --tb=line`
  - Result: passed
- Phase 2 build-pass validation completed:
  - `./utils/quick_lint.sh --fix`
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
  - `python -m pytest tests/test_points_migration_validation.py tests/test_workflow_notifications.py -v --tb=line`
  - Result: passed
- Phase 3 build-pass validation completed:
  - `./utils/quick_lint.sh --fix`
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
  - `python -m pytest tests/test_economy_engine.py tests/test_points_services.py tests/test_points_helpers.py tests/test_diagnostics.py tests/test_backup_utilities.py tests/test_points_migration_validation.py tests/test_workflow_notifications.py -v --tb=line`
  - Result: passed
- Phase 4 build-pass validation completed:
  - `./utils/quick_lint.sh --fix`
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
  - `python -m pytest tests/test_points_services.py tests/test_points_helpers.py tests/test_diagnostics.py -v --tb=line`
  - Result: passed
- Required implementation validation for this initiative:
  - `./utils/quick_lint.sh --fix`
  - `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
  - `python -m pytest tests/ -v --tb=line`
- Outstanding tests:
  - Full pytest is intentionally deferred until the later completion pass by instruction.
  - Frontend/dashboard template validation is intentionally deferred to the follow-up initiative.

## Notes & follow-up

- **Schema migration note**: No `.storage/choreops/choreops_data` schema version increment is expected because the stored point model already supports floats; only validation and consumer behavior are being aligned.
- **Root-cause note**: The backend drift came from selective integer-only UX/service contracts and read-side casts, not from the core math or storage layers.
- **Frontend follow-up note**: Known dashboard truncation remains in [choreops-dashboards/templates/user-gamification-premier-v1.yaml](../../../choreops-dashboards/templates/user-gamification-premier-v1.yaml#L90-L90) and multiple vendored dashboard templates under [custom_components/choreops/dashboards/templates](../../custom_components/choreops/dashboards/templates). Start the frontend plan from those anchors after backend behavior is merged and validated.
- **Late-gap note**: Manual verification after the initial backend completion pass exposed remaining authoring-surface drift beyond the first repro. The follow-up sweep now routes chore points, badge awards, reward cost, bonus points, penalty points, achievement reward points, and challenge reward points through the shared decimal parser as well.
- **Compatibility note**: If any legacy entities intentionally exposed integer-only points for compatibility, document that decision explicitly during implementation rather than preserving silent truncation.

## Builder handoff package

- Supporting handoff doc: [POINTS_DECIMAL_PRECISION_BACKEND_SUP_BUILDER_HANDOFF.md](POINTS_DECIMAL_PRECISION_BACKEND_SUP_BUILDER_HANDOFF.md)

## Builder handoff checklist

- [x] Backend-only scope is locked; dashboard/frontend implementation is deferred.
- [x] Storage schema impact reviewed: no `.storage` schema change or schema bump expected.
- [x] Primary contract reversals identified: `manual_adjust_points` and `default_chore_points` move from integer-only to decimal-capable.
- [x] Read-side truncation anchors identified in sensors, legacy sensors, and notifications.
- [x] Validation gates are specified (`quick_lint`, `mypy`, targeted pytest, full pytest).
- [x] Required handback payload from builder is defined in the supporting handoff doc.
