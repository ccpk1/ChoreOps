# Supporting Doc: ChoreOps unified users implementation blueprint

## Purpose

Provide a builder-ready, low-ambiguity execution plan for `CHOREOPS-ARCH-UNIFY-003` (Option 3) targeting `v0.5.0-beta5` / schema `45`.

## Success definition

Implementation is successful only if all are true:

1. Storage model is unified under `users` and migration is idempotent.
2. Runtime logic is capability-based (`can_approve`, `can_manage`, `can_be_assigned`).
3. HA admin override remains valid and tested.
4. Legacy payload compatibility is limited to input aliasing; canonical runtime/storage remains `users` only.
5. Full quality gates pass.

---

## Execution strategy

- Use **small PR batches** with strict entry/exit criteria.
- Keep system runnable after every PR (no long-lived broken branch).
- Prefer canonical model convergence over long-lived compatibility shims.

### PR sequencing overview

| PR   | Scope                                       | Primary files                                                              | Exit gate                         |
| ---- | ------------------------------------------- | -------------------------------------------------------------------------- | --------------------------------- |
| PR-0 | Contract freeze                             | `docs/*`, `const.py`                                                       | Contracts approved                |
| PR-1 | Schema + migration harness                  | `migration_pre_v50.py`, `system_manager.py`, `store.py`                    | Idempotent migration tests pass   |
| PR-2 | Coordinator unified-read bridge             | `coordinator.py`                                                           | Existing manager tests green      |
| PR-3 | Auth unification                            | `helpers/auth_helpers.py`, `services.py`                                   | Permission precedence tests green |
| PR-4 | User manager + service capability alignment | `user_manager.py`, `services.py`, `notification_action_handler.py`         | No split-role assumptions remain  |
| PR-5 | Manager refactor wave A                     | `chore_manager.py`, `reward_manager.py`                                    | Workflow tests green              |
| PR-6 | Manager/platform refactor wave B            | entity helpers + platforms                                                 | Entity/diagnostics tests green    |
| PR-7 | Flow + builder rename pass                  | `config_flow.py`, `options_flow.py`, `data_builders.py`, `flow_helpers.py` | Flow suite green                  |
| PR-8 | Test migration completion                   | `tests/helpers/*` + scenario tests                                         | Full targeted suites green        |
| PR-9 | Final contract cleanup                      | deprecated aliases, stale role references                                  | Full gate + release checklist     |

---

## Detailed PR playbook

### PR-0: Contract freeze (must happen first)

**Goal**: Freeze semantics before touching behavior.

- [ ] Confirm constants and capability semantics in main plan.
- [ ] Confirm auth precedence contract:
  - HA admin runtime override → capability flags → deny.
- [ ] Confirm compatibility window:
  - dual payload keys supported through target end version.
- [ ] Confirm merge collision policy:
  - preserve kid-origin record, remap parent-derived insert.

**Validation**

- [ ] Plan references updated.
- [ ] No unresolved contract TODOs remain in docs.

---

### PR-1: Schema + migration harness

**Goal**: Add migration machinery with no large logic refactor yet.

- [ ] Add `DATA_USERS` and user capability constants in `const.py`.
- [ ] Implement migration function (`kids` → `users`, parent merge).
- [ ] Ensure one-write migration pattern (transform in memory, persist once).
- [ ] Add collision remap handling with explicit logs.
- [ ] Register migration in `SystemManager.ensure_data_integrity()`.
- [ ] Ensure startup backup runs before migration write.

**Validation**

- [ ] Migration can run twice without changing final output.
- [ ] Forced collision fixture passes.
- [ ] Legacy data fixtures produce expected `users` result.

---

### PR-2: Coordinator unified-read bridge

**Goal**: Keep coordinator APIs stable while sourcing from canonical `users` data only.

- [ ] Introduce canonical `users_data` accessor.
- [ ] Ensure legacy-facing reads are filtered projections over `users` (not separate persisted buckets).
- [ ] Add explicit removal target for any temporary aliases.

**Validation**

- [ ] Existing manager behavior unchanged under bridge.
- [ ] No regressions in core workflow tests.

---

### PR-3: Authorization unification

**Goal**: Centralize permission logic and remove drift risk.

- [ ] Add centralized permission helper (capability-first design).
- [ ] Route service authorization calls through helper.
- [ ] Preserve HA admin override path.
- [ ] Add explicit deny paths with translation-safe errors.
- [ ] Introduce action/capability-oriented helper naming and mark any temporary wrappers for removal.

**Validation**

- [ ] Tests for:
  - HA admin override
  - designated approver
  - designated manager
  - non-approver deny
  - no dependency on legacy wrapper function names

---

### PR-4: Service capability alignment (no shadow model)

**Goal**: Eliminate shadow-link semantics and align service paths to capability flags.

- [ ] Remove canonical dependency on `linked_shadow_kid_id`.
- [ ] Support input aliasing for `kid_id` → `user_id` during transition window.
- [ ] Route service authorization through capability checks (`can_approve` / `can_manage`).

**Validation**

- [ ] Existing automations continue via input alias layer only.
- [ ] No service path requires parent/shadow link traversal.

---

### PR-5: Manager refactor wave A (high-value workflows)

**Goal**: Move core lifecycle managers to `user_id` semantics.

- [ ] Refactor `chore_manager.py` and `reward_manager.py`.
- [ ] Update signal payload internals to user terminology where safe.
- [ ] Preserve external compatibility aliases for transition window.

**Validation**

- [ ] Chore/reward workflow tests green.
- [ ] Approval/disapproval behavior unchanged.

---

### PR-6: Manager/platform refactor wave B

**Goal**: Move remaining managers/helpers/platforms to capability model.

- [ ] Refactor `gamification_manager.py`, `notification_manager.py`, helpers.
- [ ] Replace shadow branching in entity creation with capability checks.
- [ ] Preserve entity unique_id stability (or explicit migration path if needed).

**Validation**

- [ ] Entity snapshot/diagnostics tests green.
- [ ] Notification action parsing supports compatibility payloads.

---

### PR-7: Flow and data-builder rename pass

**Goal**: Align flow and builder APIs with canonical user terminology.

- [ ] Refactor `config_flow.py`, `options_flow.py`, `data_builders.py`, `flow_helpers.py`.
- [ ] Keep compatibility aliases where needed for migrated data and forms.
- [ ] Ensure no direct writes outside managers.

**Validation**

- [ ] Config/options flow suites green.
- [ ] No manager write ownership violations.

---

### PR-8: Test migration completion

**Goal**: Complete test-side refactor without brittle search/replace.

- [ ] Update `tests/helpers/*` naming and constants.
- [ ] Add migration fixture wrapper that runs old payload through real migration code.
- [ ] Keep at least one untouched legacy fixture to validate upgrade realism.

**Validation**

- [ ] Migration-path tests pass.
- [ ] Auth acceptance tests pass.
- [ ] Workflow parity tests pass.

---

### PR-9: Compatibility removals + release lock

**Goal**: remove temporary scaffolding only after all gates are green.

- [ ] Remove temporary alias properties (if all managers migrated).
- [ ] Remove any remaining shadow-link references and stale split-role language.
- [ ] Remove legacy payload aliases at end-version boundary.
- [ ] Remove temporary authorization wrappers introduced during staged migration.
- [ ] Finalize release notes with migration guidance.

**Validation**

- [ ] Full quality gate green.
- [ ] Release checklist complete.

---

## Gate checklist (non-skippable)

### Gate A: Pre-implementation

- [ ] Contracts frozen in docs.
- [ ] PR sequence approved by maintainers.

### Gate B: Post-migration harness (after PR-1)

- [ ] Idempotency proven.
- [ ] Collision policy tested.
- [ ] Backup-before-write confirmed.

### Gate C: Mid-refactor (after PR-4)

- [ ] Auth helper centralized.
- [ ] Service compatibility window active and tested.

### Gate D: Release gate (after PR-9)

- [ ] `./utils/quick_lint.sh --fix`
- [ ] `mypy custom_components/choreops/`
- [ ] `python -m pytest tests/ -v --tb=line`
- [ ] Migration notes and deprecation timeline published.

---

## Builder operating rules

- Do not run broad rename across repository in one pass.
- Keep each PR scoped to one subsystem family.
- Preserve external contracts until compatibility window closes.
- Add tests in the same PR as behavior changes.
- If a PR introduces temporary compatibility code, record explicit removal task in the next PR milestone.

---

## Fast-fail indicators (stop and reassess)

- More than 2 consecutive PRs with failing migration-path tests.
- Any evidence of data loss or overwrite during collision scenario.
- Service compatibility break that impacts existing automations.
- Entity unique_id churn without explicit migration plan.

When triggered, pause implementation and run a focused architecture correction checkpoint before continuing.
