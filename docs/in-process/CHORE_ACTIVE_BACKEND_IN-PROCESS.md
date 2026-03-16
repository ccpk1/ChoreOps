# Initiative snapshot

- **Name / Code**: Backend chore activation flag / `CHORE_ACTIVE_BACKEND`
- **Target release / milestone**: TBD after go/no-go review; suitable for next 1.0.x feature release
- **Owner / driver(s)**: TBD
- **Status**: Not started

## Summary & immediate steps

| Phase / Step                        | Description                                                                 | % complete | Quick notes                                                         |
| ----------------------------------- | --------------------------------------------------------------------------- | ---------- | ------------------------------------------------------------------- |
| Phase 1 – Contract and storage      | Add a first-class chore active flag and migration contract                  | 0%         | Requires schema bump because chore items gain a new persisted field |
| Phase 2 – Backend workflow          | Add toggle service/manager behavior and hard-stop disabled workflow actions | 0%         | Keep disable separate from chore lifecycle state                    |
| Phase 3 – Entity surface and reload | Prevent disabled chores from producing chore sensors/buttons/helper entries | 0%         | Reload-based rehydration is the pragmatic first implementation      |
| Phase 4 – Tests and rollout         | Cover migration, filtering, services, and user-facing docs                  | 0%         | Must test both existing installs and fresh create/update flows      |

1. **Key objective** – Introduce a backend-owned `active`/`enabled` chore flag so a disabled chore stays in storage but is removed from the normal Home Assistant entity surface and dashboard workflow, without overloading labels or assignment.
2. **Summary of recent work** –
   - Reviewed issue 24 and confirmed labels already solve dashboard-only hiding.
   - Traced current entity creation in `sensor.py`, `button.py`, and dashboard helper/select paths.
   - Confirmed reload-based entity rebuild is already supported through coordinator reload behavior.
3. **Next steps (short term)** –
   - Decide whether disabled chores should also be excluded from calendar and admin selectors in v1.
   - Confirm naming: `active` vs `enabled`.
   - Confirm service shape: dedicated `enable_chore` / `disable_chore` vs `set_chore_active`.
4. **Risks / blockers** –
   - Runtime enable is asymmetric today: sensors can be created dynamically, but chore buttons are setup-time only, so enabling without reload adds complexity.
   - Several helper surfaces build directly from `coordinator.chores_data`; if those paths are not filtered consistently, disabled chores will still appear in selectors or helper payloads even when their entities are gone.
   - Notification actions, direct services, and manager methods can still target disabled chores unless backend guards are added.
   - A schema change means existing stored chore records must be backfilled cleanly with a default of `true`.
5. **References** –
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Do not use labels or empty assignee lists as the backend disable contract.
     - Do not add a new chore lifecycle state for this feature.
     - Prefer a reload-based first release rather than building fully dynamic button re-creation.
     - Disabled chores should remain in storage and remain addressable by internal UUID.
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Contract and storage

- **Goal**: Add a first-class chore activation contract that is explicit in storage, typing, constants, and create/update paths.
- **Steps / detailed work items**
  1. [ ] Add the canonical chore activation field and default constant in `custom_components/choreops/const.py` near the chore data keys around lines 1374-1400, using a name such as `DATA_CHORE_ACTIVE` and a `DEFAULT_CHORE_ACTIVE` boolean.
  2. [ ] Extend `ChoreData` and any related typed payloads in `custom_components/choreops/type_defs.py` around lines 190-252 so the active flag is part of the chore storage contract and downstream helper types remain aligned.
  3. [ ] Update `validate_chore_data()` and `build_chore()` in `custom_components/choreops/data_builders.py` around lines 1261 and 1461 so fresh creates default to active, updates preserve existing values, and the new field is never treated as a lifecycle state.
  4. [ ] Bump `SCHEMA_VERSION_CURRENT` in `custom_components/choreops/const.py` around lines 333-350 and add a migration/backfill step so existing chore records without the field are stamped with `true`.
  5. [ ] Update the store/bootstrap path in `custom_components/choreops/store.py` and the data integrity flow in `custom_components/choreops/managers/system_manager.py` so fresh installs and upgrades both converge on the same contract.
- **Key issues**
  - The current schema version is `100`; any persisted field addition should be treated as a real schema increment, not an implicit lazy default.
  - The field name matters. `active` reads as domain state, while `enabled` reads as feature gating. Pick one and use it everywhere.
  - Avoid mixing the new flag with `state`; disabled must not behave like `pending`, `missed`, or `overdue`.

### Phase 2 – Backend workflow and service contract

- **Goal**: Add a manager-owned toggle path and ensure all action entry points reject disabled chores even if an entity or automation still references one.
- **Steps / detailed work items**
  1. [ ] Add a dedicated manager method in `custom_components/choreops/managers/chore_manager.py` near the CRUD section around lines 3084-3245 to toggle chore activation, persist, and emit a post-persist update signal.
  2. [ ] Add service exposure in `custom_components/choreops/services.py` alongside the existing chore CRUD services around lines 556-1104 and 1172-1406. Decide between `enable_chore` / `disable_chore` or a single `set_chore_active` boolean service.
  3. [ ] Document the service contract in `custom_components/choreops/services.yaml` next to `update_chore`, including targeting semantics and expected reload behavior.
  4. [ ] Insert hard-stop checks inside `claim_chore()`, `approve_chore()`, and `disapprove_chore()` in `custom_components/choreops/managers/chore_manager.py` around lines 540-900 and 1235-1260 so backend workflows reject disabled chores regardless of entity presence.
  5. [ ] Mirror those guardrails for mobile actions in `custom_components/choreops/notification_action_handler.py` around lines 200-290 by relying on the same manager validation rather than duplicating logic.
  6. [ ] Add translation keys in `custom_components/choreops/translations/en.json` for service labels and the error returned when a disabled chore is targeted.
- **Key issues**
  - The manager method should own persistence and the service layer should stay thin, consistent with the architecture rules.
  - If a disabled chore is re-enabled, the first version should trigger reload rather than trying to dynamically materialize missing buttons.
  - Existing automations may still call `claim_chore` directly by name; those calls must fail cleanly with a translatable error.

### Phase 3 – Entity surface and reload strategy

- **Goal**: Make disabled chores disappear from chore-specific sensors, buttons, dashboard helper payloads, and chore selectors while preserving the underlying stored item.
- **Steps / detailed work items**
  1. [ ] Filter disabled chores out of sensor setup in `custom_components/choreops/sensor.py` around lines 436-470 so `AssigneeChoreStatusSensor` and `SystemChoreSharedStateSensor` are not created for inactive chores.
  2. [ ] Filter disabled chores out of button setup in `custom_components/choreops/button.py` around lines 51-120 so claim, approve, and disapprove buttons are not created for inactive chores.
  3. [ ] Filter disabled chores out of dynamic chore sensor creation in `custom_components/choreops/sensor.py` around lines 605-653 so service-created or reloaded chores follow the same rule.
  4. [ ] Filter disabled chores out of dashboard helper chore arrays in `custom_components/choreops/sensor.py` around lines 4631-4660 so helper payloads never include chores whose entity IDs are intentionally absent.
  5. [ ] Filter disabled chores out of the assignee dashboard chore selector in `custom_components/choreops/select.py` around lines 512-540 so helper selectors do not list chores that are backend-disabled.
  6. [ ] Wire the toggle flow to `coordinator.async_sync_entities_after_service_create()` or a sibling reload helper in `custom_components/choreops/coordinator.py` around lines 378-389 so disable/enable uses a clean unload/rebuild cycle for buttons and sensors.
  7. [ ] Decide whether calendar output should also honor the active flag in `custom_components/choreops/calendar.py`; if deferred, document that explicitly as an intentional v1 limitation.
- **Key issues**
  - Dashboard helper generation is tolerant of missing entity IDs, but only if disabled chores are excluded before helper payload construction.
  - `button.py` has no dynamic add callback like `sensor.py`, so a no-reload design materially increases scope.
  - Reload-based rehydration is operationally simple but should be called out in service docs and tests because users may notice the entity graph refresh.

### Phase 4 – Tests, documentation, and rollout decision

- **Goal**: Prove upgrade safety, filtering consistency, and workflow blocking; then decide whether the feature is implement-now or defer.
- **Steps / detailed work items**
  1. [ ] Add unit coverage for the new field defaulting and schema backfill in the existing migration/storage tests, including upgrade payloads that omit the field.
  2. [ ] Add service and manager tests covering disable, enable, and blocked claim/approve/disapprove flows. Follow the guidance in `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md` and reuse existing scenario fixtures.
  3. [ ] Add entity-surface tests to verify disabled chores do not appear in chore sensors, chore buttons, dashboard helper `chores` arrays, or assignee chore selectors.
  4. [ ] Add regression tests for notification actions to ensure actions targeting disabled chores fail safely without mutating state.
  5. [ ] Update user-facing docs and release notes to explain the initial semantics: disabled chores remain stored but are removed from the chore UI surface and cannot be acted on.
  6. [ ] Record the rollout recommendation based on final scope: implement now if reload-based behavior and calendar deferral are acceptable; defer if the requirement expands to full dynamic entity churn or archive-like behavior.
- **Key issues**
  - Test setup should use YAML scenarios and `config_entry.runtime_data`, not direct `hass.data` access.
  - Existing tests likely assume all assigned chores appear in selectors and helper payloads; those assertions will need targeted updates.
  - If admin flows later expose the active flag, additional config/options-flow tests will be needed beyond the initial service-only implementation.

## Testing & validation

- Planned validation commands:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `mypy tests/`
  - `python -m pytest tests/ -v --tb=line`
  - Targeted suites expected during development:
    - `python -m pytest tests/test_chore_services.py -v`
    - `python -m pytest tests/test_chore_manager.py -v`
    - `python -m pytest tests/test_workflow_notifications.py -v`
- Tests executed: None yet; planning only.
- Outstanding tests: All implementation and migration tests are pending.

## Notes & follow-up

- **Recommended v1 shape**: storage-backed boolean flag plus reload-based entity rebuild.
- **Recommended non-goals for v1**:
  - Do not introduce a new chore lifecycle state.
  - Do not auto-delete disabled chores.
  - Do not require fully dynamic button creation on enable.
- **Open decision points**:
  - Should admin/config flows expose the flag immediately, or should the first release be service-driven only?
  - Should disabled chores remain visible in admin management selectors for achievements/challenges, or only disappear from end-user/dashboard selectors?
  - Should calendar honor the flag in v1 or stay unchanged until follow-up work?
- **Effort estimate**:
  - Reload-based v1: medium.
  - Fully dynamic runtime toggle without reload: medium-high.
  - Archive/state-machine variant: high.
- **Implementation-now recommendation threshold**:
  - Implement now if the team accepts reload-based enable/disable and a limited v1 scope.
  - Defer if stakeholders require disabled chores to instantly add/remove all entities without reload, or require broader archive/reporting semantics in the same change.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS` (for example: `MY-INITIATIVE_PLAN_IN-PROCESS.md`). Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
