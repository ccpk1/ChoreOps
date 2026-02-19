# Initiative Plan: Multi-instance hardening and readiness

## Initiative snapshot

- **Name / Code**: Multi-instance hardening and readiness (`MIR-2026Q1`)
- **Target release / milestone**: v0.6.x (staged rollout)
- **Owner / driver(s)**: ChoreOps maintainers
- **Status**: In progress (planning approved)

## Summary & immediate steps

| Phase / Step                                | Description                                                                                     | % complete | Quick notes                                        |
| ------------------------------------------- | ----------------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------- |
| Phase 1 – Pre-install hygiene               | Fix high-risk cross-contamination vectors that should be corrected even in single-instance mode | 0%         | Prioritize service targeting + device identity     |
| Phase 2 – Storage and backup namespacing    | Introduce per-entry storage and backup namespace foundations                                    | 0%         | Day-1 architecture, no legacy migration track      |
| Phase 3 – Multi-instance activation         | Remove remaining single-instance assumptions and enable explicit per-entry UX                   | 0%         | Config/Options/Services become entry-aware         |
| Phase 4 – Validation and rollout guardrails | Prove isolation in tests and document operational guidance                                      | 0%         | Required before enabling multi-instance by default |

1. **Key objective** – Ensure complete isolation between config entries so no data, services, devices, dashboards, or notifications can cross-contaminate.
2. **Summary of recent work** – Initial technical barrier audit completed; high-risk hotspots identified in storage keying, service entry resolution, and device registry identifiers. Phase 1 policy refined to hybrid targeting UX and notifications deferred by decision.
3. **Next steps (short term)** – Execute Phase 1 in order: service target contract (hybrid UX), service lifecycle safety, device identifier scoping, and docs/wiki updates.
4. **Risks / blockers** – Broad services surface area (many handlers/schemas) increases regression risk; dashboard URL collisions still need policy decision (strict unique vs auto-suffix).
5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Multi-instance work is split into hygiene-first (safe for immediate adoption) and activation-later phases.
     - Service calls will use explicit config entry targeting rather than implicit “first loaded entry” routing.
    - Service targeting UX will be hybrid: if one instance exists, service calls may omit target; if multiple exist, target is required.
    - `config_entry_id` is the canonical target field; optional title-based targeting may be supported only when unambiguous.
     - Device identity will become entry-scoped as the canonical Day-1 behavior.
     - ChoreOps has not been installed by any user or beta user yet, so these changes are implemented as the initial production architecture (no backward migration track required).
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, release checklist) before requesting owner approval.

> **Important:** Keep this Summary section current as phase statuses change.

## Tracking expectations

- **Summary upkeep**: Update phase percentages, risks, and immediate steps after each meaningful implementation batch.
- **Detailed tracking**: Keep execution details in phase sections below; keep summary high-level only.

## Detailed phase tracking

### Phase 1 – Pre-install hygiene (highest priority)

- **Goal**: Eliminate hygiene issues that are problematic regardless of multi-instance rollout timing.
- **Steps / detailed work items**
  - [ ] Add explicit service target contract across code and service docs
    - File: `custom_components/choreops/const.py` (add `SERVICE_FIELD_CONFIG_ENTRY_ID` in service field constants block)
    - File: `custom_components/choreops/services.py` (inject field into shared schema bases so every service supports one targeting contract)
    - File: `custom_components/choreops/services.yaml` (document `config_entry_id` field for every service action)
    - Define Day-1 hybrid policy:
      - If `config_entry_id` provided → use exact target.
      - If omitted and exactly one loaded entry exists → auto-target that entry.
      - If omitted and multiple loaded entries exist → fail with actionable error listing available entries.
    - Optional usability enhancement: accept `config_entry_title` (or `instance_title`) only when uniquely resolvable.
  - [ ] Replace implicit first-entry routing in all service handlers
    - File: `custom_components/choreops/services.py` (all handlers currently using `get_first_choreops_entry`, beginning around line ~538 and repeated through the module)
    - File: `custom_components/choreops/helpers/entity_helpers.py` (remove/deprecate `get_first_choreops_entry` usage path)
    - Resolve coordinator through a shared resolver implementing the hybrid policy and clear errors for ambiguous/missing target.
  - [ ] Make service registration/unregistration multi-entry safe
    - File: `custom_components/choreops/__init__.py` (`async_setup_entry`, `async_unload_entry`)
    - File: `custom_components/choreops/services.py` (`async_setup_services`, `async_unload_services`)
    - File: `custom_components/choreops/const.py` (runtime key constant for service registration reference counting)
    - Introduce reference-count or equivalent guard so unloading one entry does not remove services for others.
  - [ ] Scope device identifiers by entry everywhere devices are created/queried
    - File: `custom_components/choreops/helpers/device_helpers.py` (`create_assignee_device_info`)
    - File: `custom_components/choreops/__init__.py` (`_update_all_assignee_device_names` lookup path)
    - File: `custom_components/choreops/managers/user_manager.py` (device removal lookup by identifier)
    - File: `custom_components/choreops/managers/system_manager.py` (orphan device cleanup lookup by identifier)
    - File: `custom_components/choreops/diagnostics.py` (assignee extraction from device identifier format)
    - Implement canonical identifier shape with `entry_id` scope as default Day-1 behavior.
  - [ ] Update user documentation and wiki for service targeting
    - File: `custom_components/choreops/services.yaml` (field descriptions and examples for single-instance and multi-instance)
    - File: `README.md` (automation examples and troubleshooting for ambiguous target errors)
    - Wiki: update service-call examples and FAQ to explain when `config_entry_id` is required and where to find it.
- **Key issues**
  - Service field injection must remain consistent across all schemas and service docs.
  - Handler conversion touches many call paths; strong targeted tests are required to avoid regressions.
  - Title-based targeting can become ambiguous if users rename entries similarly; ID remains canonical for scripts.

### Phase 2 – Storage and backup namespacing (foundation)

- **Goal**: Ensure each config entry has isolated persistent data and backup artifacts.
- **Steps / detailed work items**
  - [ ] Introduce per-entry storage key strategy
    - File: `custom_components/choreops/store.py` (constructor and pathing)
    - File: `custom_components/choreops/__init__.py` (`async_setup_entry` currently using `const.STORAGE_KEY`)
    - Define canonical pattern (e.g., `choreops_data_<entry_id>` or equivalent stable key).
  - [ ] Remove single-key assumptions from backup helpers (Day-1 format)
    - File: `custom_components/choreops/helpers/backup_helpers.py` (filename prefixing and discovery filters)
    - File: `custom_components/choreops/const.py` (backup naming constants if needed)
    - Generate/discover backups by active entry-scoped storage key.
  - [ ] Scope backup discovery/create/delete to target entry storage
    - File: `custom_components/choreops/helpers/backup_helpers.py` (filename prefixing, discovery filters)
    - File: `custom_components/choreops/options_flow.py` (restore and backup selection flows near backup management steps)
    - Ensure options flow only lists backups for the current entry context.
  - [ ] Make remove-entry delete only owned storage
    - File: `custom_components/choreops/__init__.py` (`async_remove_entry`)
    - Ensure entry removal cannot clear another entry’s active data.
  - [ ] Update diagnostics payload metadata for entry-scoped storage context
    - File: `custom_components/choreops/diagnostics.py`
    - Include storage key/source metadata for clearer support and restore workflows.
- **Key issues**
  - Backup retention logic must remain per-entry and avoid cross-entry pruning.
  - Storage key derivation must be stable across reloads and restart cycles.

### Phase 3 – Multi-instance activation and UX alignment

- **Goal**: Remove remaining single-instance assumptions and allow clean multi-entry operations.
- **Steps / detailed work items**
  - [ ] Replace single-instance config flow assumptions
    - File: `custom_components/choreops/config_flow.py` (`async_step_user` single-entry abort near line ~65)
    - Allow multiple entries while preserving onboarding/recovery choices.
  - [ ] Entry-aware options flow restore/import operations
    - File: `custom_components/choreops/options_flow.py` (restore handlers around `async_step_restore_from_options` and backup selection)
    - Ensure restore targets only current entry namespace.
  - [ ] Dashboard URL collision policy and implementation
    - File: `custom_components/choreops/helpers/dashboard_builder.py` (`get_multi_view_url_path`, existence checks)
    - File: `custom_components/choreops/const.py` (`DASHBOARD_URL_PATH_PREFIX` and related constants)
    - Decide and implement one policy: required unique name per entry or automatic entry-scoped suffixing.
  - [ ] Remove helper patterns that assume “first loaded entry”
    - File: `custom_components/choreops/helpers/entity_helpers.py` (`get_first_choreops_entry`)
    - Deprecate/remove in favor of explicit entry selection patterns.
  - [ ] Update user-facing docs and service examples for entry targeting
    - File: `README.md` and relevant wiki-linked docs if maintained in-repo
    - Add migration notes for automation authors.
  - [ ] Notification action payload follow-up (deferred)
    - File: `custom_components/choreops/managers/notification_manager.py`
    - File: `custom_components/choreops/notification_action_handler.py`
    - Keep current truncated entry token behavior for now; revisit only when/if broader multi-instance notification routing requires it.
- **Key issues**
  - UX decision needed for dashboard naming strategy.
  - Potential automation breakage if users omit the new service target field.

### Phase 4 – Validation, quality gates, and release readiness

- **Goal**: Prove isolation and prevent regressions before enabling multi-instance broadly.
- **Steps / detailed work items**
  - [ ] Add isolation-focused tests for services, devices, storage, and notifications
    - Files: `tests/test_services*.py`, `tests/test_workflow_*.py`, and new focused test modules as needed
    - Cover two-entry scenarios with overlapping assignee names and identical workflows.
  - [ ] Add clean-install isolation tests for Day-1 architecture
    - Files: setup and workflow test modules using dual-entry fixtures
    - Validate independent storage keys, device identifiers, and service routing from initial install.
  - [ ] Add regression tests for unload/reload service lifecycle
    - Validate one entry unload does not deregister domain services while another remains loaded.
  - [ ] Run and document quality gates
    - Commands: `./utils/quick_lint.sh --fix`, `mypy custom_components/choreops/`, `python -m pytest tests/ -v`
  - [ ] Final readiness review against architecture and release checklist
    - Confirm docs and release notes include migration behavior and rollback guidance.
- **Key issues**
  - Multi-entry tests may require new reusable scenario fixture patterns.
  - CI duration may increase; prioritize targeted test modules for fast feedback.

## Testing & validation

- **Planned test strategy**
  - Use existing Stårblüm scenarios and add dual-entry fixtures for isolation checks.
  - Prefer service/button workflows (user-context aware), with direct coordinator calls only for internal migration assertions.
- **Validation commands (Definition of Done)**
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/ -v`
- **Outstanding tests**
  - Multi-instance-specific dual-entry fixtures are not yet implemented.

## Notes & follow-up

- This plan intentionally front-loads hygiene fixes that improve correctness immediately, even if multi-instance remains disabled for a short period.
- Because no users/beta users have installed ChoreOps yet, this plan treats isolation behavior as the initial production baseline rather than a backward-compatibility migration.
- If implementation complexity grows, create supporting docs under `docs/in-process/`:
  - `MULTI_INSTANCE_HARDENING_SUP_TEST_STRATEGY.md`
  - `MULTI_INSTANCE_HARDENING_SUP_ISOLATION_MATRIX.md`
- Move this plan to `docs/completed/` only after completion confirmation is checked and owner sign-off is recorded.
