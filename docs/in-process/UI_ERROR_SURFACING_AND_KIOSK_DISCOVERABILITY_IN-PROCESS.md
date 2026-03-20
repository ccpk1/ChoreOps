# Initiative snapshot

- **Name / Code**: UI error surfacing and kiosk discoverability / `UI_ERROR_SURFACING_KIOSK_DISCOVERABILITY`
- **Target release / milestone**: TBD; suitable for next user-facing feature release after the claim-button proof of concept
- **Owner / driver(s)**: TBD
- **Status**: In progress

## Summary & immediate steps

| Phase / Step                                   | Description                                                                                                       | % complete | Quick notes                                                                |
| ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------------- | ---------- | -------------------------------------------------------------------------- |
| Phase 1 – Error surface audit and UX contract  | Define where backend failures should reach the UI and lock the narrow wording scope before implementation         | 100%       | Audit complete; wording gate approved as propagation-only with current IDs |
| Phase 2 – Buttons and service-call propagation | Stop swallowing actionable exceptions in button/service entry points and keep wording changes intentionally small | 100%       | Actionable button handlers now re-raise after logging; auth copy unchanged |
| Phase 3 – Kiosk and user-link discoverability  | Add proactive warnings when users are unlinked and kiosk mode is off, including dashboard generator guidance      | 100%       | User form and dashboard generator warnings now land before save/apply      |
| Phase 4 – Tests, docs, and rollout             | Add regression coverage, update quick-start/access-control docs, and prepare release-note language                | 80%        | Wiki docs updated; release-note work intentionally deferred                |

1. **Key objective** – Surface backend failures in the Home Assistant UI wherever the failure is actionable for an end user, and reduce kiosk-mode/user-linking confusion by warning earlier when a user profile has no linked HA user while kiosk mode is disabled.
2. **Summary of recent work** –

- Completed the Phase 1 audit across button and service entry points and locked the auth wording gate to keep existing `ERROR_ACTION_*` identifiers unchanged for v1.
- Updated all remaining actionable button handlers in `custom_components/choreops/button.py` so `HomeAssistantError` exceptions are re-raised after logging instead of being swallowed.
- Added focused regression coverage in `tests/test_kiosk_mode_buttons.py` for unauthorized chore, reward, bonus, penalty, and manual-points button presses.
- Aligned three pre-existing tests with the corrected surfaced-error behavior in `tests/test_chore_scheduling.py`, `tests/test_rotation_services.py`, and `tests/test_workflow_chores.py`.
- Added Phase 3 non-kiosk discoverability in the add/edit user flow and dashboard generator review step, including a one-time soft warning before saving an unlinked assignee profile and an explicit acknowledgement gate before generating dashboards for selected unlinked users.
- Updated user-form `ha_user_id` help text to explain the shared-device consequence when kiosk mode is disabled.
- Updated the wiki quick start, access control guide, and FAQ so claiming or authorization errors now route users toward linked-user and kiosk-mode guidance before they hit deeper troubleshooting.
- Validation is clean for the current scope: `./utils/quick_lint.sh --fix` passed and `python -m pytest tests/ -v --tb=line` passed with `1758 passed, 4 skipped, 2 deselected`.

3. **Next steps (short term)** –

- Release-note language is intentionally deferred for later.
- Decide whether any remaining wiki pages need cross-links back to the updated quick start, FAQ, and access-control docs.
- Decide whether a follow-up issue is needed for any broader access-control copy cleanup beyond this scoped warning work.

4. **Risks / blockers** –

- Some current error text is technically correct but not especially polished for end users; however, this initiative remains intentionally **not** a broad translation cleanup.
- Over-surfacing low-value internal failures could create noisy UI if exceptions that should remain logs-only are exposed without triage.
- Kiosk-mode guidance must remain explicit about the security tradeoff on shared devices and must not weaken service-level authorization.
  - Standalone `mypy custom_components/choreops/` still collides with the separate Core checkout parser environment, even though repo-local mypy inside `./utils/quick_lint.sh --fix` passes.

5. **References** –
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
   - [docs/completed/legacy-kidschores/KIOSK_MODE_CLAIMS_COMPLETED.md](../completed/legacy-kidschores/KIOSK_MODE_CLAIMS_COMPLETED.md)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Keep the first release focused on actionable user-facing failures from buttons and service calls; do not broaden to every internal exception path by default.
     - This is **not** a full translation or message-normalization initiative.
     - Auth wording changes, if any, must stay intentionally small and require an explicit approval gate with the exact list of changed phrases before implementation.
     - If the approved wording list is empty, the implementation proceeds with existing action identifiers such as `claim_chores` and only changes propagation behavior.
     - Include the kiosk/user-linking warning idea from user feedback, with highest priority on the soft warning when a user has no linked HA account and kiosk mode is disabled.
     - Add a dashboard generator warning/check when selected assignees are not linked to HA users and kiosk mode is disabled, using the same override pattern users already understand from dependency validation if implementation complexity remains reasonable.
     - Initial setup onboarding question is explicitly out of scope for this initiative.
     - No schema bump is expected because the scoped changes are exception propagation, light copy adjustments, and options-flow/dashboard validation only.
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section (table + bullets) current with every meaningful update (after commits, tickets, or blockers change). Records should stay concise, fact-based, and readable so anyone can instantly absorb where each phase stands. This summary is the only place readers should look for the high-level snapshot.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

## Detailed phase tracking

### Phase 1 – Error surface audit and UX contract

- **Goal**: Identify which backend failures should be surfaced to end users, preserve pragmatic exception behavior, and produce an explicit approval list for any auth wording changes.
- **Steps / detailed work items**
  1. [x] Audit button entry points in `custom_components/choreops/button.py` around lines 344-1638 and classify each `except HomeAssistantError as e` branch as one of: re-raise to UI, keep log-only, or needs a small copy cleanup before surfacing.
  2. [x] Audit service handlers in `custom_components/choreops/services.py` around lines 1172-1235, 1239-1408, 1959-2186, and 2222-2466 to identify which failures already raise correctly and which surfaced errors are likely acceptable as-is versus obviously too technical.
  3. [x] Produce a **gated wording inventory** for approval before implementation begins on any auth copy changes. This inventory must list:
     - the current surfaced auth/action strings,
     - the exact proposed replacement text, if any,
     - the files/constants involved,
     - and a clear note when the recommendation is to keep the current identifier unchanged.
  4. [x] Treat the auth wording inventory as a hard gate for Phase 2. If the approved list is empty, Phase 2 proceeds with propagation-only changes and no auth-label edits.
  5. [x] Document scope boundaries in this plan: notification-action flows, background tasks, and purely diagnostic logs stay out unless they directly back a user action.
- **Key issues**
  - The current integration already has good logging; the real work is deciding which of those failures are user-actionable enough to surface.
  - The goal is not perfect copy everywhere; the goal is avoiding obviously confusing surfaced text while keeping the scope small.
  - A single audit pass should prevent one-off fixes from creating inconsistent UI behavior across similar button entities.

### Phase 2 – Buttons and service-call propagation

- **Goal**: Make user-triggered actions fail visibly in the UI when they already produce meaningful backend exceptions, with minimal behavioral risk and only approved copy changes.
- **Steps / detailed work items**
  1. [x] **Phase gate**: confirm the approved auth wording inventory from Phase 1 before changing any auth/action copy. If no wording changes are approved, explicitly record that Phase 2 is propagation-only.
  2. [x] Update chore button handlers in `custom_components/choreops/button.py` around lines 388-405, 523-538, and 699-714 so authorization and actionable workflow errors are re-raised after logging instead of being swallowed.
  3. [x] Update reward button handlers in `custom_components/choreops/button.py` around lines 843-857, 979-994, and 1151-1166 using the same propagation rule for redeem/approve/disapprove flows.
  4. [x] Review bonus, penalty, and manual-points buttons in `custom_components/choreops/button.py` around lines 1297-1312, 1450-1465, and 1634-1649 to confirm whether the same propagation behavior should apply there; include them only if the errors are clearly actionable and useful in the UI.
  5. [x] Keep service-layer changes pragmatic in `custom_components/choreops/services.py` around lines 1172-1235, 1959-2035, and 2222-2466: fix clearly user-facing auth/validation cases first, and do not expand into a repo-wide message-normalization effort.
  6. [x] Only if explicitly approved in the wording gate, introduce the smallest possible action-label or auth-copy edits in `custom_components/choreops/const.py` and `custom_components/choreops/translations/en.json`; otherwise preserve existing identifiers such as `claim_chores`.
  7. [x] Verify that service handlers invoked by automations still receive actionable exception text while preserving the project rule that services stay thin and manager-owned logic remains unchanged.
- **Key issues**
  - Re-raising all `HomeAssistantError` branches blindly may expose low-level text that should first be triaged, even if no wording changes are ultimately approved.
  - Button and service flows should remain behaviorally equivalent aside from surfacing the failure to the user.
  - This phase should avoid refactoring unrelated manager logic, exception taxonomies, or translation systems unless necessary for a specifically approved surfaced message.

### Phase 3 – Kiosk and user-link discoverability

- **Goal**: Warn users earlier when their configuration makes claim buttons fail on shared devices, with minimal friction and no authorization weakening.
- **Steps / detailed work items**
  1. [x] Update the user-form help text in `custom_components/choreops/translations/en.json` around lines 80-95, 563-578, and 994-1009 so the HA user link field more clearly explains the kiosk-mode/shared-device consequence. This should be a simple clarity improvement, not a large copy rewrite.
  2. [x] Add a soft validation or attention-callout path in the add/edit user flow in `custom_components/choreops/options_flow.py` around lines 702-770 and 794-860 so a user profile with no linked HA user can be flagged when `CONF_KIOSK_MODE` is false.
  3. [x] Introduce any needed helper logic in `custom_components/choreops/helpers/flow_helpers.py` around lines 341-460 and 3150-3215 to keep the warning criteria centralized and consistent with existing form normalization patterns.
  4. [x] Add a dashboard generator warning/check in `custom_components/choreops/options_flow.py` around lines 4058-4308 and 4448-4505 so selected assignees without linked HA users are flagged when kiosk mode is disabled.
  5. [x] Prefer integrating the dashboard-generator warning into the existing custom-card/dependency validation experience if implementation complexity remains reasonable, so users can acknowledge it with the same override pattern they already understand.
  6. [x] The dashboard-generator warning must:
  - identify the affected selected users,
  - explain that claim/redeem actions may not work as expected on shared devices when kiosk mode is disabled,
  - provide an override path rather than a hard blocker,
  - and point users to access-control documentation.
  7. [x] If the warning needs reusable data access, extend dashboard helper/schema support in `custom_components/choreops/helpers/dashboard_helpers.py` around lines 1882-2020 so assignee options can carry or validate HA-user-link state without leaking UI logic into unrelated builder code.
  8. [x] Add only the narrowly needed constants/translation keys in `custom_components/choreops/const.py` and `custom_components/choreops/translations/en.json` for the user-link hint and dashboard-generator warning paths.
- **Key issues**
  - The warning should be high-value but not blocking for intentional kiosk-disabled setups where users only use services or admin flows.
  - The dashboard generator check should explain the consequence clearly: claim buttons will not work for that user unless the dashboard is used by the linked HA account or kiosk mode is enabled.
  - Keep the wording short enough for forms, but explicit enough that users do not repeat the same troubleshooting loop.
  - Reuse of the existing override pattern is preferred, but not at the cost of introducing disproportionate flow complexity.

### Phase 4 – Tests, docs, and rollout

- **Goal**: Prove the UI-surfacing behavior is deliberate, add coverage for the new warnings, and document the user-visible behavior change.
- **Steps / detailed work items**
  1. [x] Extend `tests/test_kiosk_mode_buttons.py` with additional button cases so unauthorized and actionable failures are asserted as raised service-call errors for chore and reward buttons, not just claim.
  2. [ ] Add or extend service-focused coverage in `tests/test_chore_services.py`, `tests/test_reward_services.py`, and related points/badge service tests for user-facing auth/validation error behavior.
  3. [x] Add options-flow coverage for the unlinked-user warning path in `tests/test_ha_user_id_options_flow.py` or a dedicated new flow test module, using existing scenario fixtures and `mock_hass_users`.
  4. [x] Add dashboard-generator validation coverage in `tests/test_options_flow_dashboard_release_selection.py` or a dedicated dashboard-generator test module for the unlinked-assignee plus kiosk-disabled warning/check.
  5. [ ] Update user-facing documentation in `README.md`, relevant wiki pages, and release-note text to explain that button/service failures now surface in the UI and that unlinked users on non-kiosk setups receive proactive warnings. Note: README and release-note work intentionally deferred for now.
  6. [x] Update the quick-start wiki at `/workspaces/choreops-wiki/Getting-Started:-Quick-Start.md` with a high-visibility warning near the top that ChoreOps has built-in access rights, linked Home Assistant users matter, and shared-device deployments must intentionally consider kiosk mode and access control.
  7. [x] Ensure the quick-start warning points readers to `/workspaces/choreops-wiki/Advanced:-Access-Control.md` for the full access-control guidance.
  8. [ ] Run and record required validation commands: `./utils/quick_lint.sh --fix`, `mypy custom_components/choreops/`, and `python -m pytest tests/ -v --tb=line`.
- **Key issues**
  - Tests should verify real service-call failure behavior, not only post-state assertions, because frontend toasts depend on the service returning an error.
  - If standalone `mypy` still collides with the multi-root workspace, validation notes should explicitly separate code correctness from environment-specific interpreter issues.
  - Documentation should describe kiosk mode as a deliberate shared-device workflow, not a hidden troubleshooting-only switch.

## Testing & validation

- Planned validation commands:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/ -v --tb=line`
  - Targeted suites expected during development:
    - `python -m pytest tests/test_kiosk_mode_buttons.py -v --tb=line`
    - `python -m pytest tests/test_chore_services.py -v --tb=line`
    - `python -m pytest tests/test_reward_services.py -v --tb=line`
    - `python -m pytest tests/test_ha_user_id_options_flow.py -v --tb=line`
    - `python -m pytest tests/test_options_flow_dashboard_release_selection.py -v --tb=line`
- Tests executed:
  - `./utils/quick_lint.sh --fix`
  - `python -m pytest tests/test_kiosk_mode_buttons.py -v --tb=line`
  - `python -m pytest tests/test_chore_scheduling.py::TestDueWindowClaimLockBehavior::test_can_claim_blocks_before_window_then_allows_in_window tests/test_rotation_services.py::test_open_rotation_cycle_allows_one_claim_then_blocks_others tests/test_workflow_chores.py::TestSharedAllChores::test_secondary_assignee_enters_missed_when_strict_overdue_lock_enabled -v --tb=line`
  - `python -m pytest tests/test_ha_user_id_options_flow.py tests/test_options_flow_dashboard_release_selection.py -v --tb=line`
  - `python -m pytest tests/test_options_flow_entity_crud.py tests/test_ha_user_id_options_flow.py tests/test_options_flow_dashboard_release_selection.py -v --tb=line`
  - `python -m pytest tests/ -v --tb=line`
- Outstanding tests:
  - Standalone `mypy custom_components/choreops/` remains blocked by the known multi-root environment collision with the separate Core checkout.
  - README and release-note updates are intentionally deferred.

## Notes & follow-up

- **Recommended v1 outcome**: user-triggered actions return visible UI errors where the integration already knows the action failed and already has meaningful exception content.
- **Auth wording policy for v1**:
  - Default position: keep existing action identifiers if they are judged sufficiently helpful for troubleshooting.
  - Only change auth wording if the Phase 1 approval gate produces a small, explicit approved list.
  - No broad translation cleanup or comprehensive message rewrite is part of this initiative.
- **Recommended kiosk UX scope for v1**:
  - Add the inline hint on the HA user field.
  - Add the soft warning for unlinked users when kiosk mode is disabled.
  - Add a dashboard-generator warning/check for selected assignees with no linked HA user when kiosk mode is disabled, preferably through the same override pattern used for existing validation warnings.
  - Do **not** add the first-time onboarding question in this initiative.
- **Copy/translation scope for v1**:
  - Existing auth templates may remain in place unchanged if approved.
  - New keys should be limited to the user-link hint, unlinked-user non-kiosk warning, and dashboard-generator warning if those UI surfaces require dedicated copy.
  - Friendly action-label keys are optional and require explicit approval through the Phase 1 wording gate.
- **Non-goals for this initiative**:
  - No storage migration or schema change.
  - No kiosk-mode behavior expansion beyond current security posture.
  - No attempt to surface every background/internal exception in the UI.
  - No broad repo-wide translation or message-normalization campaign.

> **Template usage notice:** Do **not** modify this template. Copy it for each new initiative and replace the placeholder content while keeping the structure intact. Save the copy under `docs/in-process/` with the suffix `_IN-PROCESS` (for example: `MY-INITIATIVE_PLAN_IN-PROCESS.md`). Once the work is complete, rename the document to `_COMPLETE` and move it to `docs/completed/`. The template itself must remain unchanged so we maintain consistency across planning documents.
