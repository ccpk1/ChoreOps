# Initiative Plan: universal points precision dashboard sync

## Initiative snapshot

- **Name / Code**: Universal points precision dashboard sync (`UNIVERSAL_POINTS_PRECISION_DASHBOARD_SYNC`)
- **Target release / milestone**: v0.5.x next minor/patch after backend decimal rollout
- **Owner / driver(s)**: ChoreOps maintainers
- **Status**: Phase 3 complete, Phase 4 targeted validation complete with follow-up coverage work pending

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
| --- | --- | ---: | --- |
| Phase 1 – Backend option and helper contract | Add one general-options precision selector and surface the resolved value through a reviewed dashboard config contract | 100% | Universal precision selector added, dashboard config contract exposed, and integration-side validations passed |
| Phase 2 – Canonical dashboard repo updates | Update canonical dashboard templates in `choreops-dashboards` to read helper-provided precision instead of per-card local prefs | 100% | Active templates now read helper-driven precision, shared chore-row context passes it through, preference docs were updated, and dashboard release sanity passed |
| Phase 3 – Vendor sync into integration | Sync the updated dashboard assets into vendored integration copies after canonical dashboard work lands | 100% | Canonical dashboard assets were synced into the vendored integration mirror and parity check passed |
| Phase 4 – Tests, docs, and release validation | Cover options flow, helper payload, and template rendering/parity expectations | 85% | `quick_lint`, explicit mypy, dashboard repo sanity, vendored parity, and targeted dashboard pytest passed; kiosk-mode targeted rerun also passed |

1. **Key objective** – Add one universal points precision selector to General Options, expose that resolved precision through a reviewed `dashboard_config` contract, and update dashboards to consume it consistently without changing backend point storage or logic.
2. **Summary of recent work** – Phase 2 is complete in the canonical dashboard repo: all active templates were swept, shared chore-row precision wiring now flows from `dashboard_config.points_precision`, high-visibility Gamification Premier and classic admin point renderers now honor the helper-driven precision modes, active preference docs were updated, and dashboard release sanity passed.
3. **Next steps (short term)** – Finish the remaining focused Phase 4 follow-up by deciding whether to add any extra targeted assertions for general-options persistence or reward/chore helper payload coverage beyond the already-passing helper/render smoke tests.
4. **Risks / blockers** – No active blocker is currently reproduced on the touched slice. The main remaining risk is under-documenting validation if additional targeted assertions are desired before close-out.
5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
   - [docs/completed/POINTS_DECIMAL_PRECISION_BACKEND_COMPLETE.md](../completed/POINTS_DECIMAL_PRECISION_BACKEND_COMPLETE.md)
6. **Decisions & completion check**
   - **Decisions captured**:
     - The universal precision selector changes presentation only; it does not alter backend rounding, storage, statistics, affordability, or other point logic.
     - Integer-style display remains the default via a universal precision value of `fixed_0`.
     - Canonical dashboard work must be authored in `choreops-dashboards` first and only then vendored into `custom_components/choreops/dashboards/`.
     - Templates should read a reviewed helper contract rather than defining `pref_points_precision` separately in each card block.
  - The resolved universal precision value should be exposed on the assignee dashboard helper surface used by user templates, rather than requiring additional lookups to the system dashboard helper.
     - No `.storage/choreops/choreops_data` schema bump is expected; this work should persist in config/options and helper attributes only.
   - **Completion confirmation**: `[ ]` All follow-up items completed (backend option wiring, helper contract, canonical dashboard repo updates, vendor sync, tests, and docs) before requesting owner approval to mark initiative done.

> **Important:** Keep the entire Summary section current with every meaningful update so backend/helper work, canonical dashboard changes, and vendor sync do not drift apart.

## Tracking expectations

- **Summary upkeep**: Refresh phase percentages, quick notes, and blockers after each meaningful implementation batch or decision.
- **Detailed tracking**: Keep file-level implementation notes in the phase sections below; keep the summary concise.

## Detailed phase tracking

### Phase 1 – Backend option and helper contract

- **Goal**: Add one General Options selector for universal points precision and expose the resolved value through a reviewed `dashboard_config` contract without changing point math or storage behavior.
- **Steps / detailed work items**
  - [x] Add a new system-setting constant set for universal dashboard precision in [custom_components/choreops/const.py](../../custom_components/choreops/const.py#L832) near the existing General Options/system-setting constants, including the config option key, form field key, default value, translation key, and any helper attribute key needed for dashboard consumption.
  - [x] Extend the General Options schema in [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L3293) to include a selector with the supported precision modes (`fixed_0`, `adaptive`, `fixed_1`, `fixed_2`) alongside `default_chore_points`, keeping this explicitly presentation-only.
  - [x] Update the consolidated system-settings builders and validators in [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L3467) and [custom_components/choreops/helpers/flow_helpers.py](../../custom_components/choreops/helpers/flow_helpers.py#L3500) so the new setting round-trips through the same options-flow path as other general settings.
  - [x] Update General Options translations in [custom_components/choreops/translations/en.json](../../custom_components/choreops/translations/en.json#L1633) with a clear label and help text stating this affects dashboard display precision only and does not change stored values.
  - [x] Expose the resolved precision through the reviewed dashboard config contract, using the dashboard-helper payload builder in [custom_components/choreops/sensor.py](../../custom_components/choreops/sensor.py#L4762) and the public helper payload in [custom_components/choreops/sensor.py](../../custom_components/choreops/sensor.py#L4825), so templates can read one resolved value instead of local card prefs.
  - [x] Surface the resolved universal precision on a dedicated top-level `dashboard_config` payload for user-template access, while leaving `dashboard_helpers` focused on helper pointers such as translation and shard entity IDs.
- **Key issues**
  - User-facing dashboards usually start from an assignee `dashboard_helper`, so the assignee helper should be the primary source for the resolved precision value; system-helper usage should remain optional and secondary.
  - The architecture note in [docs/ARCHITECTURE.md](../ARCHITECTURE.md#L788) requires future helper UI data to be exposed as resolved helper attributes, not raw preference dumps.

### Phase 2 – Canonical dashboard repo updates

- **Goal**: Update the canonical dashboard templates in `choreops-dashboards` so they consume the universal helper-provided precision and render decimal-capable values consistently.
- **Steps / detailed work items**
  - [x] Treat the active dashboard registry as the implementation inventory and verify all nine active templates are included in the sweep: [choreops-dashboards/templates/user-chores-standard-v1.yaml](../../../choreops-dashboards/templates/user-chores-standard-v1.yaml), [choreops-dashboards/templates/user-chores-essential-v1.yaml](../../../choreops-dashboards/templates/user-chores-essential-v1.yaml), [choreops-dashboards/templates/user-chores-lite-v1.yaml](../../../choreops-dashboards/templates/user-chores-lite-v1.yaml), [choreops-dashboards/templates/user-gamification-premier-v1.yaml](../../../choreops-dashboards/templates/user-gamification-premier-v1.yaml), [choreops-dashboards/templates/user-kidschores-classic-v1.yaml](../../../choreops-dashboards/templates/user-kidschores-classic-v1.yaml), [choreops-dashboards/templates/admin-shared-v1.yaml](../../../choreops-dashboards/templates/admin-shared-v1.yaml), [choreops-dashboards/templates/admin-peruser-v1.yaml](../../../choreops-dashboards/templates/admin-peruser-v1.yaml), [choreops-dashboards/templates/admin-shared-kidschores-classic.yaml](../../../choreops-dashboards/templates/admin-shared-kidschores-classic.yaml), and [choreops-dashboards/templates/admin-peruser-kidschores-classic.yaml](../../../choreops-dashboards/templates/admin-peruser-kidschores-classic.yaml).
  - [x] Inventory and replace local precision defaults in canonical templates that currently define `pref_points_precision` directly, starting with [choreops-dashboards/templates/user-chores-standard-v1.yaml](../../../choreops-dashboards/templates/user-chores-standard-v1.yaml#L56), [choreops-dashboards/templates/user-chores-essential-v1.yaml](../../../choreops-dashboards/templates/user-chores-essential-v1.yaml#L52), [choreops-dashboards/templates/user-chores-lite-v1.yaml](../../../choreops-dashboards/templates/user-chores-lite-v1.yaml#L58), [choreops-dashboards/templates/user-kidschores-classic-v1.yaml](../../../choreops-dashboards/templates/user-kidschores-classic-v1.yaml#L48), and [choreops-dashboards/templates/user-gamification-premier-v1.yaml](../../../choreops-dashboards/templates/user-gamification-premier-v1.yaml#L60).
  - [x] Update the shared chore engine contract in [choreops-dashboards/templates/shared/chore_engine/context_v1.yaml](../../../choreops-dashboards/templates/shared/chore_engine/context_v1.yaml#L128) and [choreops-dashboards/templates/shared/chore_engine/group_render_v1.yaml](../../../choreops-dashboards/templates/shared/chore_engine/group_render_v1.yaml#L52) so chore row button-card variables receive the resolved precision value used by [choreops-dashboards/templates/shared/button_card_template_chore_row_v1.yaml](../../../choreops-dashboards/templates/shared/button_card_template_chore_row_v1.yaml#L151) and [choreops-dashboards/templates/shared/button_card_template_chore_row_kids_v1.yaml](../../../choreops-dashboards/templates/shared/button_card_template_chore_row_kids_v1.yaml#L148).
  - [x] Update Gamification Premier showcase and reward sections to use the helper-provided precision consistently, especially the showcase summary branch at [choreops-dashboards/templates/user-gamification-premier-v1.yaml](../../../choreops-dashboards/templates/user-gamification-premier-v1.yaml#L364) and the reward-cost rendering path at [choreops-dashboards/templates/user-gamification-premier-v1.yaml](../../../choreops-dashboards/templates/user-gamification-premier-v1.yaml#L1225) and [choreops-dashboards/templates/user-gamification-premier-v1.yaml](../../../choreops-dashboards/templates/user-gamification-premier-v1.yaml#L1281).
  - [x] Sweep admin templates to remove drift between local card prefs and universal precision sources, starting with [choreops-dashboards/templates/admin-shared-v1.yaml](../../../choreops-dashboards/templates/admin-shared-v1.yaml#L1027), [choreops-dashboards/templates/admin-peruser-v1.yaml](../../../choreops-dashboards/templates/admin-peruser-v1.yaml#L943), [choreops-dashboards/templates/admin-shared-kidschores-classic.yaml](../../../choreops-dashboards/templates/admin-shared-kidschores-classic.yaml#L251), and [choreops-dashboards/templates/admin-peruser-kidschores-classic.yaml](../../../choreops-dashboards/templates/admin-peruser-kidschores-classic.yaml#L249).
  - [x] Add one repo-wide audit pass over `choreops-dashboards/templates/**` before handoff completion to catch any remaining point-like raw string rendering outside the obvious entry points, including `reward_cost|string`, `badge.threshold|string`, `award_points`, `bonus_points | string`, `penalty_points | string`, and similar paths that should honor the universal precision unless intentionally exempted.
  - [x] Update canonical dashboard preference docs so they describe the new universal helper-driven precision source, or explicitly note where local per-template overrides are being retired, starting with [choreops-dashboards/preferences/user-gamification-premier-v1.md](../../../choreops-dashboards/preferences/user-gamification-premier-v1.md#L22), [choreops-dashboards/preferences/user-chores-standard-v1.md](../../../choreops-dashboards/preferences/user-chores-standard-v1.md#L19), and [choreops-dashboards/preferences/admin-peruser-v1.md](../../../choreops-dashboards/preferences/admin-peruser-v1.md#L13).
  - [x] Preserve one fallback-to-`fixed_0` behavior in templates when the helper value is absent during transition, but treat helper-provided precision as the new primary source.
- **Key issues**
  - Some templates currently mix three patterns: local top-of-card `pref_points_precision`, shared row variables, and raw `reward_cost|string` output. This phase must standardize all three.
  - The canonical repo is the source of truth, so no vendored integration template should be updated first “just to unblock” render fixes.
  - Handoff is not complete until the builder can point to a clean registry-wide audit result for all active templates, not just the initial user-facing dashboard set.

### Phase 3 – Vendor sync into integration

- **Goal**: Bring the integration’s vendored dashboard assets back into parity only after canonical dashboard repo changes are complete and reviewed.
- **Steps / detailed work items**
  - [x] Sync the updated canonical templates and preference docs from `choreops-dashboards` into vendored integration assets under [custom_components/choreops/dashboards/templates](../../custom_components/choreops/dashboards/templates) and [custom_components/choreops/dashboards/preferences](../../custom_components/choreops/dashboards/preferences), preserving canonical text and shared markers.
  - [x] Verify shared fragment parity for the chore-engine and button-card template surfaces, especially [custom_components/choreops/dashboards/templates/shared/chore_engine/context_v1.yaml](../../custom_components/choreops/dashboards/templates/shared/chore_engine/context_v1.yaml), [custom_components/choreops/dashboards/templates/shared/chore_engine/group_render_v1.yaml](../../custom_components/choreops/dashboards/templates/shared/chore_engine/group_render_v1.yaml), [custom_components/choreops/dashboards/templates/shared/button_card_template_chore_row_v1.yaml](../../custom_components/choreops/dashboards/templates/shared/button_card_template_chore_row_v1.yaml), and [custom_components/choreops/dashboards/templates/shared/button_card_template_chore_row_kids_v1.yaml](../../custom_components/choreops/dashboards/templates/shared/button_card_template_chore_row_kids_v1.yaml).
  - [x] Confirm the vendored registry and release metadata remain coherent with the synced assets in [custom_components/choreops/dashboards/dashboard_registry.json](../../custom_components/choreops/dashboards/dashboard_registry.json) if any manifest-facing dashboard preference documentation or shared-fragment requirements change.
  - [x] Record the vendor-sync step explicitly in the initiative log so future archaeology does not mistake direct vendored edits for the primary change source.
- **Key issues**
  - The architecture contract in [docs/ARCHITECTURE.md](../ARCHITECTURE.md#L820) is explicit that canonical templates live in `choreops-dashboards` and vendored assets are synced artifacts.
  - If canonical and vendored copies drift during implementation, render smoke tests in the integration repo may validate stale or partially updated templates.

### Phase 4 – Tests, docs, and release validation

- **Goal**: Add coverage for the universal precision option, helper payload, canonical template rendering expectations, and vendor parity.
- **Steps / detailed work items**
  - [x] Add General Options coverage for the new precision selector in the relevant options-flow tests, starting from the current General Options helpers and patterns referenced by [tests/AGENT_TESTING_USAGE_GUIDE.md](../../tests/AGENT_TESTING_USAGE_GUIDE.md#L28) and the helper constants in [tests/helpers/constants.py](../../tests/helpers/constants.py#L241).
  - [x] Extend helper payload tests around resolved dashboard helper attributes in [tests/test_dashboard_helper_size_reduction.py](../../tests/test_dashboard_helper_size_reduction.py#L232) to verify the new reviewed precision value is exposed in the helper surface and defaults correctly.
  - [ ] Add or update reward/chore dashboard helper assertions so decimal-capable reward costs and chore point values continue to round-trip through helper payloads, using existing dashboard helper verification patterns in [tests/test_reward_crud_services.py](../../tests/test_reward_crud_services.py#L431) and decimal-related checks in [tests/test_points_migration_validation.py](../../tests/test_points_migration_validation.py#L215).
  - [x] Update render smoke coverage in [tests/test_dashboard_template_render_smoke.py](../../tests/test_dashboard_template_render_smoke.py#L1) to ensure the vendored templates still render after switching from per-card local precision prefs to helper-driven precision sourcing.
  - [x] Record dashboard-repo-side validation expectations in the plan and release notes, including whichever parity or asset checks are used to prove canonical and vendored templates match before merge.
  - [x] Run and record the targeted repo validations used for this change: `./utils/quick_lint.sh --fix`, `mypy custom_components/choreops/ --python-version 3.14 --explicit-package-bases`, `python utils/sync_dashboard_assets.py --check`, `python -m pytest tests/test_dashboard_helper_size_reduction.py tests/test_dashboard_template_render_smoke.py -v --tb=line`, and `python -m pytest tests/test_kiosk_mode_buttons.py -v --tb=line`, plus `python utils/release_sanity.py` in the dashboard repo.
- **Key issues**
  - The dashboard repo does not run through the same integration smoke tests unless the vendored sync happens, so both canonical and vendored validation steps need to be called out explicitly.
  - Tests should prove presentation contract behavior, not alter or re-litigate backend point arithmetic that was already covered by the decimal backend initiative.

## Testing & validation

- Planned validation commands for the integration repo:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/ -v --tb=line`
- Planned validation focus areas:
  - General Options persistence of the universal precision selector
  - Dashboard helper payload exposure of the resolved precision value
  - Reward/chore helper payload consistency for decimal-capable point values
  - Vendored dashboard template render smoke coverage
- Planned validation for dashboard repo:
  - Use the dashboard repo’s parity/render workflow to confirm canonical templates compile and match the vendored sync target before final integration vendoring
  - Phase 2 builder validation recorded: `python utils/release_sanity.py` passed in `choreops-dashboards`
- Outstanding tests:
  - Integration repo validation for this contract adjustment: `./utils/quick_lint.sh --fix` passed, `mypy custom_components/choreops/ --python-version 3.14 --explicit-package-bases` passed, `python utils/sync_dashboard_assets.py --check` passed, `python -m pytest tests/test_dashboard_helper_size_reduction.py tests/test_dashboard_template_render_smoke.py -v --tb=line` passed, and `python -m pytest tests/test_kiosk_mode_buttons.py -v --tb=line` passed.
  - Optional follow-up coverage remains for extra focused reward/chore helper payload round-trip assertions if we want to raise Phase 4 from targeted validation to fuller coverage completion.

## Notes & follow-up

- **Schema migration note**: No `.storage/choreops/choreops_data` schema bump is expected; this is a presentation-settings and helper-contract effort.
- **Contract note**: The existing helper pattern already provides reviewed surfaces such as `translation_sensor_eid`, `chore_helper_eids`, and `ui_control`; universal precision should follow that same model instead of introducing ad hoc template-local state.
- **Dashboard source-of-truth note**: All authored template changes belong in `choreops-dashboards`. Vendored template edits inside the integration are a downstream sync step only.
- **Rollout note**: During transition, templates may temporarily support both helper-driven precision and local fallback-to-`fixed_0`, but the end state should remove redundant per-card precision declarations where they no longer provide value.
- **Release note**: Communicate that users can now set one dashboard-wide points precision from General Options, and that the setting affects dashboard display only.
