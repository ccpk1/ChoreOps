# Backend decimal precision for points - Builder handoff

---

status: READY_FOR_HANDOFF
owner: Strategist Agent
created: 2026-03-30
parent_plan: POINTS_DECIMAL_PRECISION_BACKEND_IN-PROCESS.md
handoff_from: ChoreOps Strategist
handoff_to: ChoreOps Builder
phase_focus: Backend-only implementation, validation, and doc alignment

---

## Handoff button

[HANDOFF_TO_BUILDER_POINTS_DECIMAL_PRECISION_BACKEND](POINTS_DECIMAL_PRECISION_BACKEND_IN-PROCESS.md)

## Handoff objective

Implement full backend support for 2-digit precision decimal points so the public backend contract, runtime consumers, and backend docs all match the float-safe storage and rounding model already present in ChoreOps.

Required behavior:

1. Accept signed non-zero decimal amounts with up to 2 fractional digits in `manual_adjust_points`.
2. Accept positive decimal values with up to 2 fractional digits for `default_chore_points` in points/general settings flows.
3. Preserve decimal values through backend runtime consumers instead of truncating them to integers where the value represents point currency rather than a count.
4. Keep storage architecture unchanged: no `.storage/choreops/choreops_data` schema migration, no schema version bump.
5. Update backend-facing tests, translations, service docs, and wiki references to reflect the new contract.
6. Leave dashboard/frontend rendering changes out of this handoff and document them as follow-up work only.

## Scope for this handoff

### In scope

- Core backend contracts and defaults:
  - [custom_components/choreops/services.py](../../custom_components/choreops/services.py)
  - [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py)
  - [custom_components/choreops/const.py](../../custom_components/choreops/const.py)
  - [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json)
- Runtime/backend consumers:
  - [custom_components/choreops/sensor.py](../../custom_components/choreops/sensor.py)
  - [custom_components/choreops/sensor_legacy.py](../../custom_components/choreops/sensor_legacy.py)
  - [custom_components/choreops/managers/notification_manager.py](../../custom_components/choreops/managers/notification_manager.py)
  - [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py)
  - [custom_components/choreops/managers/chore_manager.py](../../custom_components/choreops/managers/chore_manager.py)
- Backend docs and service contract text:
  - [custom_components/choreops/services.yaml](../../custom_components/choreops/services.yaml)
  - [choreops-wiki/Configuration:-Points.md](../../../choreops-wiki/Configuration:-Points.md)
  - [choreops-wiki/Services:-Reference.md](../../../choreops-wiki/Services:-Reference.md)
- Validation and regression tests:
  - [tests/test_points_services.py](../../tests/test_points_services.py)
  - [tests/test_points_helpers.py](../../tests/test_points_helpers.py)
  - [tests/test_points_migration_validation.py](../../tests/test_points_migration_validation.py)
  - [tests/test_diagnostics.py](../../tests/test_diagnostics.py)
  - [tests/test_workflow_notifications.py](../../tests/test_workflow_notifications.py)

### Out of scope

- Any dashboard template edits in [choreops-dashboards/templates](../../../choreops-dashboards/templates) or vendored dashboard templates under [custom_components/choreops/dashboards/templates](../../custom_components/choreops/dashboards/templates).
- Any change to the number of supported decimal places beyond 2.
- Any migration that rewrites existing stored point values.
- Unrelated points-system refactors outside the contract and consumer-alignment work.

## Hard constraints

- Follow the current storage-only architecture and manager-owned write model.
- Reuse the existing 2-decimal precision contract defined by [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L357) and the existing rounding helpers in [custom_components/choreops/utils/math_utils.py](../../custom_components/choreops/utils/math_utils.py#L37-L133) and [custom_components/choreops/engines/economy_engine.py](../../custom_components/choreops/engines/economy_engine.py#L88-L183).
- Do not add `# type: ignore` or validation suppressions to force the change through.
- Keep count semantics as integers where the value is an actual count rather than a point amount.
- Update docs/translations in the same implementation pass as the code contract changes to avoid temporary user-facing drift.

## Recommended execution order

1. Finish Package A before any read-side cleanup so input contracts are defined first.
2. Finish Package B next so accepted decimal values can propagate end to end.
3. Add Package C tests while making Package B code changes to catch precision regressions early.
4. Finish Package D docs and service text in the same branch before merge.
5. Run targeted validation before full-suite validation.

## Execution checklist (builder)

### Package A - Shared contract and validation changes

- [ ] Replace `_validate_non_zero_integer_amount` in [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L198) with a decimal-safe validator/parser that:
  - accepts signed numeric input
  - rejects `0`
  - rejects more than 2 fractional digits
  - returns a float-like value appropriate for downstream `deposit` / `withdraw`
- [ ] Decide whether the new validator lives directly in [custom_components/choreops/services.py](../../custom_components/choreops/services.py) or is extracted to a shared helper next to other points parsing utilities. Preferred direction: shared helper if both flows and services need identical precision enforcement.
- [ ] Update `MANUAL_ADJUST_POINTS_SCHEMA` in [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L367-L376) to use the new validator.
- [ ] Update `handle_manual_adjust_points` in [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L2462-L2528) to stop truncating `amount` via `int(...)`.
- [ ] Update points settings schema builders in [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L185-L224) and [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L3223-L3260) so `default_chore_points` accepts decimal values.
- [ ] Update validation in [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L246-L253) and [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L3516-L3531) to enforce `> 0` with max 2 decimals instead of integer parsing.
- [ ] Review type/default implications in [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L794-L823) and [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L1731-L1746), then update translations in [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json#L502-L553) to describe decimal support.

### Package B - Runtime consumer alignment

- [ ] Remove reward-cost truncation in [custom_components/choreops/sensor.py](../../custom_components/choreops/sensor.py#L2733) so affordability checks use decimal values accurately.
- [ ] Review the achievement/progress accumulation around [custom_components/choreops/sensor.py](../../custom_components/choreops/sensor.py#L3031) and only preserve integers for true counts, not points.
- [ ] Update legacy point entity paths in [custom_components/choreops/sensor_legacy.py](../../custom_components/choreops/sensor_legacy.py#L610), [custom_components/choreops/sensor_legacy.py](../../custom_components/choreops/sensor_legacy.py#L688), and [custom_components/choreops/sensor_legacy.py](../../custom_components/choreops/sensor_legacy.py#L766) so point-valued sensors no longer cast to `int`.
- [ ] Update point payload generation in [custom_components/choreops/managers/notification_manager.py](../../custom_components/choreops/managers/notification_manager.py#L2109) so translated notification data keeps decimal values.
- [ ] Verify decimal `default_chore_points` continues through config flow defaults in [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py#L605) and [custom_components/choreops/config_flow.py](../../custom_components/choreops/config_flow.py#L1629-L1630).
- [ ] Confirm runtime fallback behavior in [custom_components/choreops/managers/chore_manager.py](../../custom_components/choreops/managers/chore_manager.py#L873-L880) remains correct when the option is decimal.
- [ ] Do a final grep pass for `int(` on point-value paths before closing the package.

### Package C - Test coverage and validation

- [ ] Update [tests/test_points_services.py](../../tests/test_points_services.py#L116-L316) so manual adjustment tests cover:
  - positive decimal deposit
  - negative decimal withdrawal
  - decimal rejection when precision exceeds 2 places
  - zero rejection
  - multi-instance routing still working with decimal values
- [ ] Extend [tests/test_points_helpers.py](../../tests/test_points_helpers.py#L1-L88) to cover decimal `default_chore_points` schema defaults, parsing, and validation failures.
- [ ] Extend diagnostics/settings coverage using [tests/test_diagnostics.py](../../tests/test_diagnostics.py#L286) so decimal defaults round-trip correctly.
- [ ] Extend points-sensor regression coverage in [tests/test_points_migration_validation.py](../../tests/test_points_migration_validation.py#L640-L710) so a decimal manual adjustment updates the points sensor and earned/spent/net attributes without truncation.
- [ ] Update or add notification assertions in [tests/test_workflow_notifications.py](../../tests/test_workflow_notifications.py#L969-L1139) so point payloads/messages can carry decimals where relevant.
- [ ] Retain the existing engine math coverage; do not duplicate float-rounding engine tests unless a true backend contract gap appears.

### Package D - Docs and release-facing alignment

- [ ] Update the service definition in [custom_components/choreops/services.yaml](../../custom_components/choreops/services.yaml#L344-L390) so `manual_adjust_points` describes signed decimal amounts with up to 2 fractional digits.
- [ ] Update [choreops-wiki/Configuration:-Points.md](../../../choreops-wiki/Configuration:-Points.md#L26) and [choreops-wiki/Services:-Reference.md](../../../choreops-wiki/Services:-Reference.md#L92-L106) so they no longer describe whole-number-only behavior.
- [ ] Add a brief historical note or cross-reference in [docs/completed/MANUAL_POINTS_ADJUSTMENT_SERVICE_COMPLETED.md](../completed/MANUAL_POINTS_ADJUSTMENT_SERVICE_COMPLETED.md) and [docs/completed/DEFAULT_CHORE_POINTS_OPTION_COMPLETED.md](../completed/DEFAULT_CHORE_POINTS_OPTION_COMPLETED.md) if needed to show those earlier integer-only decisions were superseded.
- [ ] Update the parent plan status in [docs/in-process/POINTS_DECIMAL_PRECISION_BACKEND_IN-PROCESS.md](POINTS_DECIMAL_PRECISION_BACKEND_IN-PROCESS.md) as each package lands.

## Acceptance criteria

- `manual_adjust_points` accepts values like `1.5` and `-2.25`, rejects `0`, and rejects values with more than 2 decimal places.
- `default_chore_points` accepts values like `2.5` anywhere that points settings are configured.
- Stored point values and backend-calculated point attributes are preserved at 2-decimal precision without integer truncation on modern sensors, legacy sensors that expose point amounts, or notification payloads.
- Diagnostics and related settings serialization preserve decimal point values unchanged.
- Backend docs and service descriptions match the shipped behavior.
- No storage schema version bump is introduced.

## Validation gates (required)

- `python -m pytest tests/test_economy_engine.py tests/test_points_services.py -v --tb=line`
- `python -m pytest tests/test_points_helpers.py tests/test_diagnostics.py -v --tb=line`
- `python -m pytest tests/test_points_migration_validation.py tests/test_workflow_notifications.py -v --tb=line`
- `./utils/quick_lint.sh --fix`
- `mypy custom_components/choreops/`
- `python -m pytest tests/ -v --tb=line`

## Required handback payload from builder

1. Changed-files list grouped by Package A-D.
2. Short explanation of where the shared decimal validation logic ended up and why.
3. Summary of any legacy entity compatibility decisions that were kept intentionally.
4. Test output summary for targeted tests and the full suite.
5. Confirmation that no `.storage` schema migration or schema version bump was needed.
6. Parent plan status update in [docs/in-process/POINTS_DECIMAL_PRECISION_BACKEND_IN-PROCESS.md](POINTS_DECIMAL_PRECISION_BACKEND_IN-PROCESS.md).
