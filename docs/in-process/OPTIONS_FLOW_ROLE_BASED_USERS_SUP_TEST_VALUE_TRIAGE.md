# Supporting doc: Test value triage for hard-fork transition

## Purpose

Define a **value-first** strategy for the 95 failing tests after the user-role hard fork.
This document prevents low-value test patching and drives intentional keep/rewrite/remove decisions.

## Inputs

- Full suite run summary: `1361 passed / 95 failed`
- Failure inventory source: full test log artifact from latest run
- Contract source of truth:
  - `custom_components/choreops/const.py`
  - `custom_components/choreops/options_flow.py`
  - `custom_components/choreops/config_flow.py`
  - `custom_components/choreops/migration_pre_v50.py`

## Rubric (applied per failing test)

Each test gets a 0-2 score on five dimensions.

1. **Business value**: catches user-visible breakage
2. **Contract coverage**: validates current hard-fork behavior (not legacy internals)
3. **Uniqueness**: non-duplicative with existing test coverage
4. **Determinism**: stable, low-flake
5. **Maintenance cost**: clear setup, low fragility

### Decision bands

- **8-10**: Keep (possibly minor rewrite)
- **5-7**: Rewrite/Merge
- **0-4**: Remove (only if replaced by stronger coverage)

## Failure distribution (top files)

- `tests/test_workflow_chores.py`: 24
- `tests/test_workflow_gaps.py`: 16
- `tests/test_workflow_notifications.py`: 10
- `tests/test_parent_shadow_kid.py`: 8
- `tests/test_points_migration_validation.py`: 8
- `tests/test_daily_multi_approval_reset.py`: 4
- `tests/test_badge_cumulative.py`: 3
- `tests/test_optional_select_field.py`: 3
- `tests/test_setup_helper.py`: 3
- `tests/test_shared_chore_features.py`: 3
- Remaining files: 16 total failures

## Triage decisions by cluster

### A) Legacy storage/internal coupling (`parents` key, direct `_data` writes)

**Examples**

- `test_workflow_notifications.py` uses `coordinator._data[DATA_PARENTS]`
- setup/yaml tests expecting `parent_ids` from legacy bucket

**Decision**

- **Rewrite** to black-box role/user setup via flow/service APIs.
- **Remove** only those internals assertions that duplicate black-box scenarios.

**Why**

- High business value remains (notifications, setup correctness), but legacy implementation coupling is invalid.

---

### B) Removed menu/step compatibility assumptions (`manage_kid` in options menu)

**Examples**

- options-flow tests expecting old menu route values

**Decision**

- **Rewrite** to assert current contract explicitly:
  - allowed menu options
  - disallowed legacy route validation

**Why**

- Contract verification is high value, old assumptions are not.

---

### C) Core workflow regressions (points/approval/state transitions)

**Examples**

- `test_workflow_chores.py` point awards not occurring
- `test_badge_cumulative.py` expected points/progress not updating

**Decision**

- **Keep + rewrite setup harness** where needed.
- No removals in this cluster.

**Why**

- These are top business-value behaviors.

---

### D) Shadow user/profile behavior

**Examples**

- `test_parent_shadow_kid.py`

**Decision**

- **Merge + rewrite** into fewer scenario-driven tests that assert:
  - creation toggle behavior
  - linked profile markers
  - count/reporting semantics

**Why**

- Some duplication likely; preserve behavior checks while reducing overlap.

---

### E) Migration validation and optional select edge cases

**Examples**

- `test_points_migration_validation.py`
- `test_optional_select_field.py`

**Decision**

- **Keep**, but rewrite assertions to target post-migration/user schema contract.

**Why**

- Migration correctness is release-critical, and input validation protects UX reliability.

## Proposed execution batches

### Batch 1 (highest value, highest risk)

- `test_workflow_chores.py`
- `test_workflow_gaps.py`
- `test_badge_cumulative.py`

Goal: restore behavioral confidence for points/approval/recurrence logic.

### Batch 2 (contract + notifications)

- `test_workflow_notifications.py`
- `test_shared_chore_features.py`

Goal: user-role notification recipients and shared-chore semantics.

### Batch 3 (shadow + setup/migration harness)

- `test_parent_shadow_kid.py`
- `test_setup_helper.py`
- `test_yaml_setup.py`
- `test_points_migration_validation.py`

Goal: complete harness migration away from legacy `parents` internals.

### Batch 4 (tail cleanup)

- remaining low-count files
- dedupe/removal passes with replacement tests where needed

## Removal policy (strict)

A test can be removed only if all are true:

1. It asserts legacy/internal implementation detail no longer in contract.
2. Its user-visible behavior is covered by another stronger test.
3. The replacement test is merged and passing first.
4. Removal rationale is documented in PR notes.

## Exit criteria

- 0 failing tests in targeted files per batch
- No direct runtime assertions on `DATA_PARENTS`
- Contract-focused assertions only (API/flow/service outcomes)
- `./utils/quick_lint.sh --fix` + full pytest passing
