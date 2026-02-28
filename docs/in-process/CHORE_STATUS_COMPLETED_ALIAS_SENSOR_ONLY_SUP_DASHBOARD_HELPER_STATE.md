# Dashboard-helper chore-state analysis

## Purpose

Provide a focused decision analysis for dashboard-helper chore `state` behavior under the hard-fork display initiative (`approved` → `completed` on chore status sensor output), while dashboard template rework is deferred.

## Scope of this analysis

- In scope:
  - Dashboard helper `chores[*].state` contract
  - Current dashboard template consumers of helper status and sensor state
  - Associated test surface impacted by helper/sensor state divergence
- Out of scope:
  - Template implementation changes
  - Backend FSM, storage schema, or manager signal contract changes

## Current contract map

### 1) Source-of-truth and projection layers

1. **Manager context state** is produced by `get_chore_status_context()` and returned as `CHORE_CTX_STATE`.
   - File: `custom_components/choreops/managers/chore_manager.py` (~`get_chore_status_context`)
2. **Assignee chore sensor state** currently returns `ctx[CHORE_CTX_STATE]` directly.
   - File: `custom_components/choreops/sensor.py` (`AssigneeChoreStatusSensor.native_value`)
3. **Dashboard helper chore status** also currently copies `ctx[CHORE_CTX_STATE]` directly.
   - File: `custom_components/choreops/sensor.py` (`AssigneeDashboardHelperSensor._calculate_chore_attributes`)

This means helper and sensor are currently coupled by design through the same context state source.

### 1.1 Existing single state-calculation function (confirmed)

- `get_chore_status_context()` is the existing single manager-level state provider for assignee chore state projection.
- It calls `ChoreEngine.resolve_assignee_chore_state()` for core resolution and then applies manager-level display context rules.
- This initiative should reuse this path and avoid introducing a second state calculator.

### 2) Dashboard template usage split (critical)

Current templates consume **both** helper status and sensor state, but for different behavior:

- **Grouping/filtering path** (from helper list):
  - `chore_status = chore.status` (current template key)
  - `pref_exclude_approved` checks `chore_status == 'approved'`
  - overdue grouping checks `chore_status == 'overdue'`
  - Files:
    - `custom_components/choreops/dashboards/templates/user-minimal-v1.yaml`
    - `custom_components/choreops/dashboards/templates/user-gamification-v1.yaml`

- **Card styling/labels path** (from sensor entity state):
  - `chore_state = states(chore_sensor_id)`
  - state maps include `approved` but not `completed`
  - icon/badge color logic explicitly keys on `chore_state == 'approved'`
  - Files:
    - `custom_components/choreops/dashboards/templates/user-minimal-v1.yaml`
    - `custom_components/choreops/dashboards/templates/user-gamification-v1.yaml`

- **Admin detail display path**:
  - detail card uses helper-provided selected chore status (`current_status`) + template state map
  - state maps include `approved` but not `completed`
  - File:
    - `custom_components/choreops/dashboards/templates/admin-shared-v1.yaml`

### 3) Existing helper contract declaration

Dashboard helper docstring currently describes `status` as:
- `pending/claimed/approved/overdue` (narrow set)
- File: `custom_components/choreops/sensor.py` (`_calculate_chore_attributes` docstring)

### 4) Existing test assumptions

- Hard status allowlist in helper-size tests:
  - `{"pending", "claimed", "approved", "overdue"}`
  - File: `tests/test_dashboard_helper_size_reduction.py`
- Rotation and workflow tests assert helper chore status `approved` in several places.
  - File: `tests/test_rotation_fsm_states.py`

## Hard-fork decision matrix

| Decision | Helper key | Helper value | Sensor state | Compatibility layer | Risk profile |
| --- | --- | --- | --- | --- | --- |
| H1 | `state` only | `completed` alias applied | `completed` alias applied | None | Correct long-term contract; template consumers must be updated in rework |
| H2 | `state` + `status` | mirrored | `completed` alias applied | Yes | Rejected (violates hard-fork/no-compat rule) |
| H3 | `status` only | `completed` alias applied | `completed` alias applied | N/A | Rejected (keeps ambiguous naming) |

## Key findings

1. **There is a real UI-layer miss risk today** if sensor state is aliased before template rework:
   - even if helper remains `approved`, card visuals use sensor state and will fall through `approved`-specific color/icon logic.
2. Helper-only decisions do **not** neutralize template impact because templates read both helper status and sensor state.
3. Test updates must explicitly separate:
   - backend/context assertions (`approved` remains lifecycle state)
   - sensor display assertions (`completed` alias)
  - helper state assertions (`state` key only)

## Signal consistency check (approved vs completed events)

- Current dual-signal design is intentional:
  - `SIGNAL_SUFFIX_CHORE_APPROVED` drives economy/notification/gamification listeners
  - `SIGNAL_SUFFIX_CHORE_COMPLETED` is emitted for completion-credit semantics by criteria
- Files:
  - `custom_components/choreops/const.py` (signal constants)
  - `custom_components/choreops/managers/chore_manager.py` (emit order and payloads)
  - `custom_components/choreops/managers/economy_manager.py`
  - `custom_components/choreops/managers/notification_manager.py`

**Conclusion**: dashboard-helper/sensor display alias work must not modify these signal contracts.

## Recommendation for this initiative (hard-fork)

### Accepted strategy: **H1 (`state` only, no compatibility alias key)**

Reasoning:
- Aligns with long-term contract clarity (`state` is explicit and unambiguous).
- Enforces no-compatibility technical debt policy in this hard-fork initiative.
- Prevents future drift by requiring one canonical helper field and one canonical sensor state projection.

### Required guardrails for H1

1. Helper emits `state` only (no `status` key).
2. Helper `state` and sensor state must be assigned from the same projected variable in one path.
3. Add regression test that fails if helper and sensor diverge.
4. Do not modify manager context contracts or signal semantics.

## Test planning deltas from this analysis

### Must update

- Sensor state assertions currently expecting `approved` where alias should apply.
- Translation assertions for sensor state map to include `completed`.

### Must update

- Helper key assertions in:
  - `tests/test_dashboard_helper_size_reduction.py`
  - `tests/test_rotation_fsm_states.py`
- Migrate helper reads from `chore["status"]` to `chore["state"]`.

### Add one contract test

Assert in same scenario that:
  - manager context state is `approved`
  - helper `chores[*].state` is `completed`
  - helper has no `status` key
  - sensor `state` is `completed`

This prevents accidental future coupling regressions.

## Builder handoff notes

1. Treat this as a hard-fork contract change: helper key is `state` only.
2. Keep changes limited to display projection + helper key migration + tests + translations.
3. Capture a follow-up item in template rework to reconcile all `approved`-specific state-map/filter/color branches.

## Decision checkpoint (to be marked during execution)

- [x] H1 accepted (`helper.state=completed`, `sensor=completed`, no `status` field)
- [ ] Signal-path assertions added for no-divergence guarantee
