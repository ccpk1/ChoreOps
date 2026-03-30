# Initiative plan: Manual points adjustment service

## Initiative snapshot

- **Name / Code**: Manual points adjustment service (`manual_adjust_points`)
- **Target release / milestone**: v0.6.x (minor feature release)
- **Owner / driver(s)**: ChoreOps maintainers
- **Status**: Complete

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
| Phase 1 – Service contract | Define API + constants + translations | 100% | Constants, schema contract, and `services.yaml` entry added |
| Phase 2 – Runtime wiring | Add service schema/handler + manager call path | 100% | Handler wired with signed amount routing and service registration |
| Phase 3 – Validation tests | Add focused service + multi-instance tests | 100% | Added dedicated service tests and multi-instance coverage |
| Phase 4 – Docs & polish | Update service docs, translations, and wiki | 100% | Wiki/README/release checklist synced with final service contract |

1. **Key objective** – Add one config-entry-aware service that manually adds/deducts points like manual points buttons, with ledger classification as manual and required reason persisted via ledger `item_name`.
2. **Summary of recent work**
   - Confirmed config-entry-aware service routing exists in [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L73-L114).
   - Confirmed manual buttons use `POINTS_SOURCE_MANUAL` via `EconomyManager.deposit/withdraw` in [custom_components/choreops/button.py](../../custom_components/choreops/button.py#L1573-L1632).
   - Confirmed ledger entry supports `item_name` payload in [custom_components/choreops/engines/economy_engine.py](../../custom_components/choreops/engines/economy_engine.py#L138-L169).
3. **Next steps (short term)**

- Freeze service schema and validation contract from approved decisions.
- Implement and test against multi-instance routing.
- Hand off to Builder with acceptance criteria and test scope.

4. **Risks / blockers**

- Because `amount` must be positive integer only, add/deduct direction must be explicit in schema (recommended enum field).
- `approver_name` is optional; handler needs a deterministic fallback for logs/ledger context when omitted.
- Historical note: The integer-only `amount` contract documented here was later superseded by the decimal-precision backend work in [docs/in-process/POINTS_DECIMAL_PRECISION_BACKEND_IN-PROCESS.md](../in-process/POINTS_DECIMAL_PRECISION_BACKEND_IN-PROCESS.md).

5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)

- [choreops-wiki/Services:-Reference.md](../../choreops-wiki/Services:-Reference.md)

6. **Decisions & completion check**
   - **Decisions captured**:
     - Preferred service name: `manual_adjust_points` (verb + domain + intent; clearer than `adjust_points`).
     - Reuse current auth gate (`AUTH_ACTION_MANAGEMENT`) used by manual adjustment buttons and bonus/penalty services.
     - Keep ledger source as existing `POINTS_SOURCE_MANUAL` in [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L1259).
    - `amount` was originally defined here as **required positive integer** (`> 0`), decimals disallowed, zero disallowed. That contract was later superseded by decimal support in [docs/in-process/POINTS_DECIMAL_PRECISION_BACKEND_IN-PROCESS.md](../in-process/POINTS_DECIMAL_PRECISION_BACKEND_IN-PROCESS.md).
     - `reason` is **required** and persisted to ledger via existing `item_name`.
     - Support both `user_name` and `user_id` inputs for target user resolution.
     - `approver_name` remains available but **not required**.
   - **Completion confirmation**: `[ ]` All follow-up items completed (implementation, tests, docs, release notes) before owner approval.

## Tracking expectations

- **Summary upkeep**: Update this file after each meaningful change with phase percentages and blockers.
- **Detailed tracking**: Keep detailed implementation notes in phase sections only.

## Detailed phase tracking

### Phase 1 – Service contract and constants

- **Goal**: Lock a stable, user-friendly service API and translations before coding.
- **Steps / detailed work items**
  - [x] Add service constant `SERVICE_MANUAL_ADJUST_POINTS` near existing service names in [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L2633-L2649).
  - [x] Add service fields for amount and reason (`SERVICE_FIELD_POINTS_AMOUNT`, `SERVICE_FIELD_REASON`) near existing field constants in [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L2706-L2795).
  - [x] Add optional `SERVICE_FIELD_USER_ID` path to this service contract while retaining `SERVICE_FIELD_USER_NAME` support.
  - [x] Add/confirm error action key for authorization text if needed (reuse `ERROR_ACTION_ADJUST_POINTS` where possible) in [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L3075-L3077).
  - [x] Define schema contract with constraints: signed non-zero integer amount, `reason` required non-empty string.
  - [x] Add service documentation block in [custom_components/choreops/services.yaml](../../custom_components/choreops/services.yaml#L264-L350) following `apply_bonus` / `apply_penalty` style and target fields.
- **Key issues**
  - Decide default/fallback behavior when both `user_id` and `user_name` are provided but map to different users.

### Phase 2 – Service handler wiring and ledger behavior

- **Goal**: Implement service path that mirrors manual buttons and writes clean ledger entries.
- **Steps / detailed work items**
  - [x] Add `MANUAL_ADJUST_POINTS_SCHEMA` in [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L159-L196) using `_with_service_target_fields`.
  - [x] Add `handle_manual_adjust_points` in [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L2073-L2211) patterning authorization/ID resolution after bonus/penalty handlers.
  - [x] Resolve assignee via `user_id` (preferred when supplied) or fallback `user_name` through `get_item_id_or_raise`, and route by `_resolve_target_entry_id` to remain config-entry aware in [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L73-L114).
  - [x] Call `coordinator.economy_manager.deposit(...)` when `amount > 0` and `.withdraw(...)` when `amount < 0`, with `source=POINTS_SOURCE_MANUAL` in [custom_components/choreops/managers/economy_manager.py](../../custom_components/choreops/managers/economy_manager.py#L482-L680).
  - [x] Map **required** `reason` to ledger `item_name` supported by [custom_components/choreops/engines/economy_engine.py](../../custom_components/choreops/engines/economy_engine.py#L138-L169).
  - [x] If `approver_name` is omitted, use a deterministic fallback label in service logs (for example, "System") without blocking execution.
  - [x] Register and unregister the service in [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L2135-L2211) and [custom_components/choreops/services.py](../../custom_components/choreops/services.py#L2754-L2792).
- **Key issues**
  - Keep `item_name` semantics consistent between manual button path and service path in user-facing history text.

### Phase 3 – Testing coverage

- **Goal**: Prove behavior parity with manual buttons plus multi-instance safety.
- **Steps / detailed work items**
  - [x] Add service behavior tests in [tests/test_reward_services.py](../../tests/test_reward_services.py#L238-L428) style or a new dedicated test file (recommended `tests/test_points_services.py`).
  - [x] Add tests for positive and negative signed integer amounts, verifying balance and ledger source `manual`.
  - [x] Add tests verifying decimals and zero are rejected by schema.
  - [x] Add test asserting required reason is recorded in ledger `item_name`.
  - [x] Add tests for both assignee targeting modes (`user_id` and `user_name`) and conflict handling behavior.
  - [x] Add auth tests: management role required (reuse patterns around apply bonus/penalty).
  - [x] Add tests for optional `approver_name` (present vs omitted) to confirm no validation failure.
  - [x] Add multi-instance routing tests extending [tests/test_multi_instance_services.py](../../tests/test_multi_instance_services.py#L1-L109) for ambiguous/no-target and explicit `config_entry_id` / `config_entry_title` routing.
  - [x] Add service schema validation tests for invalid amounts / empty assignee.
- **Key issues**
  - Keep tests scenario-driven (Stårblüm family fixtures) and avoid direct storage writes.

### Phase 4 – Documentation and release alignment

- **Goal**: Ensure service is discoverable and maintainers can support it.
- **Steps / detailed work items**
  - [x] Add/adjust docs examples for automations in [README.md](../../README.md) and/or docs pages that already reference services.
  - [x] Update user-facing description text in [custom_components/choreops/services.yaml](../../custom_components/choreops/services.yaml).
  - [x] Add translation keys/labels in [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json) for new service fields/messages and auth/validation errors.
  - [x] If notification copy is required for manual service calls, add/update notification translation keys in [custom_components/choreops/translations_custom/en_notifications.json](../../custom_components/choreops/translations_custom/en_notifications.json) and mirrored locale notification files as needed. (No new notification copy required in this phase.)
  - [x] Translation source-of-truth check: this integration currently does not include `strings.json`; Builder must update the active translation source files above and only include `strings.json` updates if/when that file exists in the integration.
  - [x] Update services reference wiki entry with schema + examples in [choreops-wiki/Services:-Reference.md](../../choreops-wiki/Services:-Reference.md).
  - [x] Update release checklist notes in [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md) if this introduces user-visible service API.
- **Key issues**
  - Ensure docs phrase “manual adjustment” consistently across button and service paths.
  - Keep wiki examples aligned with final service schema (signed non-zero integer `amount`, required `reason`, optional `approver_name`, `user_id|user_name`).

## Effort estimate

- **Implementation with approved constraints (positive integer amount, required reason, `item_name` reuse, dual user targeting)**: **Medium** (~1 to 2.5 dev days)
- **Implementation + full role/multi-instance/conflict-path matrix**: **Medium** (~2 to 3 dev days)
- **Migration risk**: none expected with `item_name` reuse

## Naming recommendation

- **Recommended service name**: `manual_adjust_points`
- **Why**: aligns with existing terminology (`manual` source), clearly implies +/- operation, and avoids ambiguity with chore/reward adjustments.
- **Alternative**: `adjust_points` (shorter, but less explicit that this is a manual/admin operation)

## Locked requirements (builder input)

- [x] `amount` must be integer and `> 0`.
- [x] `amount=0` is rejected.
- [x] `reason` is required.
- [x] `reason` is stored in existing ledger `item_name`.
- [x] Service supports both `user_id` and `user_name`.
- [x] `approver_name` is included in schema but optional.

## Remaining implementation assumption to confirm

- [x] Service uses signed non-zero integer `amount`; positive adds points and negative deducts points.

## Schema and migration impact

- **Expected**: No storage schema bump if reason maps to existing ledger `item_name`.
- **Potential**: Schema/type updates only if adding a dedicated ledger reason field (evaluate against data model and migration policy).

## Testing & validation

- Planned validation commands (post-implementation):
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/ -v --tb=line`
  - Targeted: `python -m pytest tests/test_multi_instance_services.py -v`

## Notes & follow-up

- This feature can reuse existing infrastructure cleanly: target routing, authorization helpers, and economy ledger writes are already in place.
- Product decisions are now locked; remaining risk is only contract clarity for operation direction and target conflict behavior.

---

## Builder handoff

- **Handoff target**: ChoreOps Builder
- **Implementation scope**: `custom_components/choreops/{const.py,services.py,services.yaml,translations/en.json,translations_custom/en_notifications.json}` + docs in `choreops-wiki/Services:-Reference.md` + tests under `tests/`.
- **Must-have acceptance criteria**:
  - New service `manual_adjust_points` is config-entry aware (`config_entry_id`/`config_entry_title` behavior matches existing services).
  - Requires positive integer amount and required reason.
  - Supports both `user_id` and `user_name`.
  - Uses `POINTS_SOURCE_MANUAL` and stores reason in ledger `item_name`.
  - Accepts omitted `approver_name` without failure.
  - Includes translation updates for service fields/errors in `translations/en.json` and notification text updates when manual adjustment notifications are required.
  - Services wiki reference page updated with the new service contract and examples.
  - Passes lint, mypy, and targeted service/multi-instance tests.
- **Out of scope**: Any storage schema migration or dedicated new ledger reason field.
