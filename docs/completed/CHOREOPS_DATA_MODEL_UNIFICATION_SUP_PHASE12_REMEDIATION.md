# Supporting Doc: Phase 1/2 remediation tracker (users capability pivot)

## Purpose

Track every required remediation item introduced by the unified `users` capability pivot, so interim wrappers and legacy terms are removed before Phase 3 continuation.

## Scope lock

- Applies to Phase 1 (contract/foundation) and Phase 2 (migration) only.
- Builder must complete this remediation batch before proceeding to Phase 3 feature work.

## TODO registry (authoritative)

### Auth helper naming and wrapper cleanup

- [x] TODO-AUTH-001: Replace wrapper name `is_user_authorized_for_kid`
  - File: [custom_components/choreops/helpers/auth_helpers.py](../../custom_components/choreops/helpers/auth_helpers.py)
  - Replace with action/capability-oriented naming (for example approval or assignment scope authorization).
  - Remove role-bucket language from docstrings and logs.

- [x] TODO-AUTH-002: Replace wrapper name `is_user_authorized_for_global_action`
  - File: [custom_components/choreops/helpers/auth_helpers.py](../../custom_components/choreops/helpers/auth_helpers.py)
  - Use explicit capability-intent naming (for example management authorization).

- [x] TODO-AUTH-003: Remove generic `permission_type="kid"|"global"` API shape
  - File: [custom_components/choreops/helpers/auth_helpers.py](../../custom_components/choreops/helpers/auth_helpers.py)
  - Replace with explicit capability checks (`can_approve`, `can_manage`) and optional assignment participation checks.

- [x] TODO-AUTH-004: Update tests to validate new helper API names
  - File: [tests/test_kc_helpers.py](../../tests/test_kc_helpers.py)
  - Remove assertions tied to legacy wrapper function names.

### Canonical storage/runtimes

- [x] TODO-DATA-001: Remove canonical split-bucket dependency (`kids`/`parents`)
  - Files:
    - [custom_components/choreops/coordinator.py](../../custom_components/choreops/coordinator.py)
    - [custom_components/choreops/store.py](../../custom_components/choreops/store.py)
    - [custom_components/choreops/migration_pre_v50.py](../../custom_components/choreops/migration_pre_v50.py)
  - `users` must be canonical source of truth; any aliases are temporary and tracked for removal.

- [x] TODO-DATA-002: Enforce users-only default structure for new installs
  - File: [custom_components/choreops/store.py](../../custom_components/choreops/store.py)
  - Remove compatibility mirrors from default install shape after migration safety criteria are met.

### Shadow-link model removal

- [x] TODO-SHADOW-001: Remove canonical model dependency on `linked_shadow_kid_id`
  - Files:
    - [custom_components/choreops/managers/user_manager.py](../../custom_components/choreops/managers/user_manager.py)
    - [custom_components/choreops/services.py](../../custom_components/choreops/services.py)
    - [custom_components/choreops/helpers/entity_helpers.py](../../custom_components/choreops/helpers/entity_helpers.py)

- [x] TODO-SHADOW-002: Convert/retire shadow-link service pathways per pivot contract
  - Files:
    - [custom_components/choreops/services.py](../../custom_components/choreops/services.py)
    - [tests/test_shadow_link_service.py](../../tests/test_shadow_link_service.py)

## Exit criteria for this remediation batch

- No active code path requires role-bucket wrappers for authorization.
- No final helper names imply split-role model.
- Phase 1/2 contract docs and code naming are aligned (`users`, `user_id`, capability flags).
- Quality gates pass for remediation changes:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/` (or documented environment-equivalent)
  - targeted pytest suites for touched areas.

## Builder handoff message (ready to send)

Use the message below as the task brief for remediation before Phase 3 continuation.

---

**To:** Builder (Implementation)
**Subject:** Mandatory remediation pass — Phase 1/2 unified user pivot compliance

Complete a remediation-only pass before any Phase 3 continuation.

### Required outcomes

1. Authorization helpers must use capability/action-oriented naming and behavior.
2. Legacy wrappers and split-role semantics must be removed (or explicitly temporary with removal in this same remediation batch).
3. Canonical model remains `users` with `can_approve`, `can_manage`, `can_be_assigned`.
4. Shadow-link model is removed from canonical behavior.

### Execute TODOs in this order

- TODO-AUTH-001 through TODO-AUTH-004
- TODO-DATA-001 through TODO-DATA-002
- TODO-SHADOW-001 through TODO-SHADOW-002

### Validation

Run and report:

- `./utils/quick_lint.sh --fix`
- `mypy custom_components/choreops/` (or environment-equivalent path if parser-context issue persists)
- Focused pytest for modified files and adjacent workflows

### Completion condition

Do not start Phase 3 tasks until all TODO items above are complete and validated.

---
