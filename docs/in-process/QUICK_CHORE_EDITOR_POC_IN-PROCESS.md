# Initiative Plan

## Initiative snapshot

- **Name / Code**: Quick chore editor POC next phase
- **Target release / milestone**: Post-`1.0.8-beta.1` POC validation slice
- **Owner / driver(s)**: Builder handoff
- **Status**: Phase 2 complete

## Summary & immediate steps

| Phase / Step | Description | % complete | Quick notes |
| --- | --- | --- | --- |
| Phase 1 – Backend auth contract | Prove direct custom-card service calls enforce management authorization with frontend user context | 100% | Completed for create, update, delete, and `manage_ui_control` |
| Phase 2 – Frontend editor slice | Extend the current create-card POC into a standards-aligned admin create/edit slice with correct repo ownership | 100% | Temporary sandbox card expanded to create/edit; dashboard-visible translations authored canonically and synced |
| Phase 3 – Validation | Add focused service/auth/runtime-sync tests | 75% | CRUD auth regression coverage, dashboard helper contract coverage, and dedicated runtime sync regression coverage are in place |
| Phase 4 – POC wrap-up | Capture decisions, constraints, and whether the direct-service model is proven | 0% | No production polish yet |

1. **Key objective** – Prove four concepts in one narrow slice: direct frontend service calls carry the acting user context, backend management auth can gate create/update/delete, translation/helper sensors are sufficient for card UX, and CRUD changes still stay on the no-reload runtime-sync path while following the documented dashboard asset ownership model.
2. **Summary of recent work** – The current POC card already calls `choreops.create_chore` directly from the frontend in `utils/custom-card-poc/choreops-create-chore-poc.js` around lines 201-214. Chore CRUD already uses targeted runtime entity sync in `custom_components/choreops/services.py` around lines 1004-1393 and `custom_components/choreops/coordinator.py` around lines 408-470. Dashboard helpers and translation sensor pointers already exist in `custom_components/choreops/sensor.py` around lines 3990-4097 and 5038-5068. The architecture and standards docs also confirm that dashboard-visible translations and canonical dashboard assets belong in `choreops-dashboards`, not the vendored runtime mirror.
3. **Next steps (short term)** – Harden create/update/delete/ui-control service auth, move the next POC implementation to the standards-aligned repo boundaries, then add direct tests for authorized and unauthorized service calls plus runtime sync assertions.
4. **Risks / blockers** – The main risk is over-expanding the POC into full dashboard parity or blurring repo ownership. This phase should not add recurrence, due dates, labels, icons, workflow policy fields, popup framework work, or a new backend API.
5. **References**
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
  - `docs/DASHBOARD_TEMPLATE_GUIDE.md`
   - `docs/CODE_REVIEW_GUIDE.md`
   - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
   - `docs/RELEASE_CHECKLIST.md`
6. **Decisions & completion check**
   - **Decisions captured**:
    - Use direct custom-card service calls for create/update/delete rather than proxying through `button.press`.
    - Treat `call.context.user_id` as the source of truth for the acting user.
    - Reuse existing dashboard helper and translation sensor data instead of adding a new data endpoint.
    - Follow dashboard asset governance even for the POC: dashboard-visible translations and dashboard wiring changes are canonical in `choreops-dashboards`, while vendored dashboard assets in the integration repo remain sync outputs.
    - Do not assume the dashboard repo is the long-term source location for released custom-card code; current architecture ratifies separate frontend card repositories for that boundary.
    - Keep the next phase limited to a builder-validation POC, not a finished admin UI.
   - **Completion confirmation**: `[ ]` All follow-up items completed before requesting owner approval.

> **Important:** The success condition for this phase is confidence in the execution model, not UI completeness.

## Tracking expectations

- **Summary upkeep**: Update this file after each meaningful implementation checkpoint so the builder handoff stays current.
- **Detailed tracking**: Keep proof notes and edge cases in the phase sections below; do not expand the scope in the Summary table.

## Non-negotiable builder guardrails

- **No scope creep**: Keep this phase limited to proving auth context, service-layer authorization, helper/translation reuse, and no-reload CRUD behavior.
- **No field expansion without approval**: Do not add recurrence, due date, labels, icons, approval policy controls, or richer workflow settings unless the owner explicitly approves that scope change in this plan.
- **No modal/popup pivot without approval**: The default proof path is an inline admin create/edit slice. Do not switch to popup-first UX unless inline delivery is proven insufficient and the owner explicitly approves the deviation in this plan.
- **No new backend API**: Do not add websocket endpoints, HTTP views, or alternate CRUD contracts for this phase. Use the existing service contract and harden it.
- **No vendored-first dashboard edits**: Do not hand-edit `custom_components/choreops/dashboards/`; canonical dashboard asset work starts in `choreops-dashboards`, then syncs back.
- **No translation drift**: Do not hardcode new dashboard-visible copy in the card or template. Dashboard-visible UX copy belongs in `choreops-dashboards/translations/en_dashboard.json`; integration-owned errors and service text belong in `custom_components/choreops/translations/en.json`.
- **No auth-model invention**: Reuse `call.context.user_id` and `is_user_authorized_for_action(..., AUTH_ACTION_MANAGEMENT)` rather than adding a parallel permission mechanism.
- **No direct storage writes outside managers**: Service handlers must continue delegating writes to managers; do not write `_data` or call persistence helpers directly from services or frontend-driven helpers.
- **No repo-boundary shortcuts**: Do not treat `choreops-dashboards` as the permanent home for released ChoreOps-specific custom-card source code. That requires explicit owner approval because it deviates from the ratified custom-card strategy.
- **No temporary-hosting assumptions**: If the next POC iteration still needs repo-local custom-card source before a dedicated frontend repo exists, treat that as a temporary non-release artifact and record the temporary hosting decision explicitly in this plan.
- **No silent dependency expansion**: If the dashboard-facing implementation adds or changes custom-card dependencies, update canonical dashboard metadata and document the dependency change explicitly.

## Out of scope

- Production-grade visual polish or full dashboard parity.
- New service schemas beyond the auth hardening and any translation placeholders required for auth errors.
- New storage schema or migration work unless explicitly required by an approved design change.
- New release/distribution mechanics for a standalone custom card.
- Non-English translation edits.
- Broad dashboard redesign outside the targeted admin create/edit proof surface.
- Permanent repo-home decisions for a released custom card unless explicitly approved.

## Deviation protocol

- Any proposed deviation from scope or guardrails must be documented in this plan before implementation.
- Acceptable deviation triggers include only:
  - inline UX is provably insufficient to validate the service/auth model,
  - current helper/translation surfaces are provably missing required data,
  - standards compliance requires a different repo boundary than originally assumed.
- When a deviation is needed, the builder must pause and record:
  - the exact blocker,
  - why the current plan cannot satisfy the proof goal,
  - the smallest viable deviation,
  - the files/repos affected,
  - the tests/validation impact.
- Work must not continue on the deviating path until the owner gives explicit approval.

## Trap coverage matrix

- **Trap 1: Frontend call path assumption drift**
  - Risk: builder quietly reverts to `button.press` or another proxy path, which stops proving the direct-service model.
  - Mitigation: keep the proof path explicitly on direct `choreops.create_chore`, `choreops.update_chore`, and future `choreops.delete_chore` calls from the frontend.
- **Trap 2: Partial auth hardening**
  - Risk: create/update are hardened but delete or `manage_ui_control` remain unguarded, leaving the future editor contract inconsistent.
  - Mitigation: treat create, update, delete, and editor-state persistence as one service-layer auth slice.
- **Trap 3: Repo-boundary confusion**
  - Risk: builder edits vendored dashboard assets directly or places dashboard-visible translations in the integration repo.
  - Mitigation: canonical dashboard asset changes start in `choreops-dashboards`; vendored assets are sync outputs only.
- **Trap 4: Custom-card source boundary drift**
  - Risk: builder interprets dashboard repo ownership of templates/translations as approval to make `choreops-dashboards` the permanent source for released custom-card code.
  - Mitigation: treat that as out of bounds unless owner approval explicitly overrides the ratified architecture.
- **Trap 4b: Temporary POC hosting ambiguity**
  - Risk: builder loses time deciding where the unreleased POC card source should sit and silently chooses a path that looks canonical.
  - Mitigation: if a dedicated frontend repo is not being created in this phase, keep the card source in an explicitly temporary, non-release location and document that choice in this plan before implementation.
- **Trap 5: Dashboard helper overreach**
  - Risk: builder bloats helper payloads or adds raw storage dumps to avoid reading the existing chore status sensor.
  - Mitigation: use helper data for discovery and selection only; use the existing chore sensor for detailed field values.
- **Trap 6: Translation split regression**
  - Risk: dashboard copy, service errors, and helper labels get mixed across translation systems.
  - Mitigation: keep dashboard-visible card copy in dashboard translations and integration-owned exception/service text in integration translations.
- **Trap 7: Runtime sync regression masked by happy-path manual testing**
  - Risk: auth hardening appears fine manually, but create/update/delete lose no-reload behavior or leave orphaned runtime entities.
  - Mitigation: extend CRUD auth tests and runtime-sync tests together; do not accept manual-only validation.
- **Trap 8: POC becomes product**
  - Risk: builder starts solving release packaging, standalone repository structure, dependency distribution, or production UX polish in this phase.
  - Mitigation: stop at proof of concept. Capture follow-up needs, but do not implement them without approval.

## Opportunities to capture while implementing

1. Keep the auth checks factored through one small helper or repeatable pattern so CRUD services stay consistent and future service additions do not drift.
2. Reuse translation sensor plumbing cleanly so the same pattern can support later admin cards without adding a new frontend data endpoint.
3. Keep persisted editor UI state minimal and well-named so the future production editor can reuse it without schema churn.
4. Add one concise builder note showing exactly which data comes from the system helper, which comes from the chore status sensor, and which comes from integration translations versus dashboard translations.
5. Record the temporary source location for the unreleased POC card so future extraction into a dedicated frontend repo is straightforward.

## Verification gate

- `[ ]` Direct frontend service calls remain the authoritative proof path.
- `[x]` `create_chore`, `update_chore`, and `delete_chore` all enforce management auth consistently.
- `[x]` `manage_ui_control` is either hardened consistently or explicitly excluded from the implemented POC path.
- `[x]` Dashboard-visible translations are authored canonically in `choreops-dashboards`.
- `[x]` No vendored dashboard asset was hand-edited as source.
- `[x]` No-reload runtime entity sync still works for create/update/delete after auth hardening.
- `[x]` Any deviation from inline UX, repo boundaries, or field scope has explicit owner approval recorded in this plan.

## Detailed phase tracking

### Phase 1 – Backend auth contract

- **Goal**: Prove that direct custom-card calls to ChoreOps CRUD services can rely on frontend-authenticated user context and can be safely gated by the existing management authorization model.
- **Steps / detailed work items**
  - [x] Add a management auth check to `handle_create_chore(...)` in `custom_components/choreops/services.py` around lines 1004-1144, using `call.context.user_id` and the existing `is_user_authorized_for_action(..., AUTH_ACTION_MANAGEMENT)` helper from `custom_components/choreops/helpers/auth_helpers.py`.
  - [x] Add the same management auth check to `handle_update_chore(...)` in `custom_components/choreops/services.py` around lines 1145-1323.
  - [x] Add the same management auth check to `handle_delete_chore(...)` in `custom_components/choreops/services.py` around lines 1328-1393 so the future delete action uses the same service-layer contract.
  - [x] Add the same management auth check to `handle_manage_ui_control(...)` in `custom_components/choreops/services.py` around lines 3243-3259 if the card will persist open/selected editor state.
  - [x] Mirror the existing service auth pattern already used in `custom_components/choreops/services.py` around lines 2555-2571 rather than inventing a new contract.
  - [x] Add explicit management action identifiers in `custom_components/choreops/const.py` around lines 3171-3182 so authorization errors can identify create, update, delete, and `manage_ui_control` actions with the existing `TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION` flow.
- **Key issues**
  - The card should not attempt to pass a `user_id` field. The backend must trust `call.context.user_id`, not request payload data.
  - No schema version bump is expected for this phase. Reusing the existing UI control bucket does not require a storage schema migration unless a new top-level storage structure is introduced.

### Phase 2 – Frontend editor slice

- **Goal**: Extend the current create-only POC into a small admin create/edit card that proves helper reuse, translation reuse, direct service-based editing, and standards-compliant repo ownership.
- **Steps / detailed work items**
  - [x] Treat the current file in `utils/custom-card-poc/choreops-create-chore-poc.js` as a sandbox reference only, not as the intended canonical location for the next POC phase.
  - [x] Record the temporary source location for the unreleased POC card. This phase keeps the card code in `utils/custom-card-poc/choreops-create-chore-poc.js` as an explicitly temporary non-release artifact; it is not the canonical long-term home.
  - [x] Put dashboard-visible translation work in `choreops-dashboards/translations/en_dashboard.json`, following `docs/ARCHITECTURE.md` around lines 757-786 and `docs/DASHBOARD_TEMPLATE_GUIDE.md` around lines 24-33.
  - [x] Put any dashboard template wiring, dependency metadata, and dashboard-facing integration changes in the canonical dashboard repo (`choreops-dashboards`) and then sync vendored assets back into the integration mirror with `python utils/sync_dashboard_assets.py` and `python utils/sync_dashboard_assets.py --check`, following `docs/DEVELOPMENT_STANDARDS.md` around lines 107-114 and `docs/DASHBOARD_TEMPLATE_GUIDE.md` around lines 91-110. No template or dependency metadata changes were needed in this slice; translation sync completed successfully.
  - [x] Keep backend service, helper, and runtime-sync changes in the integration repo (`custom_components/choreops/`), since those are backend contracts rather than dashboard assets.
  - [x] Keep the editor limited to three business fields only: `name`, `points`, and `assigned_user_names`. The sandbox card now supports create and edit using only those fields.
  - [x] Resolve translation strings from the translation sensor pointer exposed by the system dashboard helper in `custom_components/choreops/sensor.py` around lines 4090-4097, and consume the `ui_translations` payload exposed by the translation sensor in `custom_components/choreops/sensor.py` around lines 3990-4008.
  - [x] Resolve assignee options from the system helper’s `user_dashboard_helpers` map in `custom_components/choreops/sensor.py` around lines 4089-4094, just as the current POC already does.
  - [x] For edit mode, use dashboard helper chore discovery only for selection and list rendering. Pull detailed edit values from the backing chore status sensor entity, because the helper chore list is intentionally minimal in `custom_components/choreops/sensor.py` around lines 4243-4262.
  - [x] Add a stable `chore_id` field to the minimal dashboard helper chore payload so edit-mode updates can target the existing `update_chore` service by ID even when the name changes.
  - [x] State persistence was not needed for this slice. Editor mode, selected assignee, and selected chore stay local to the temporary sandbox card, so `manage_ui_control` remains available but unused here.
  - [ ] If this POC evolves into a real released custom-card dependency, do not treat `choreops-dashboards` as the permanent source repo for the card code. The current architecture and release docs expect dedicated frontend card repositories for released custom cards.
- **Key issues**
  - Do not build a modal system in this phase unless it is strictly required to prove the service/auth model. The simplest proof is an inline admin card.
  - Do not duplicate dashboard translations locally in the card. Reuse the translation sensor payload.
  - Do not hand-edit vendored runtime dashboard assets in `custom_components/choreops/dashboards/`; canonical changes belong in `choreops-dashboards`.
  - The standards support dashboard repo ownership for templates, preferences, and dashboard-visible translations, but released custom-card source code remains a separate boundary.

### Phase 3 – Validation

- **Goal**: Prove the contract end-to-end with focused tests instead of manual-only verification.
- **Steps / detailed work items**
  - [ ] Extend `tests/test_chore_crud_services.py` near the existing CRUD coverage around lines 313-321 and 750 onward to add explicit authorized and unauthorized `create_chore`, `update_chore`, and `delete_chore` service-call tests.
  - [ ] Add focused tests for `manage_ui_control` authorization if the card uses that service, keeping coverage close to the service contract rather than the card implementation.
  - [x] Reuse the runtime sync assertions already centered on `async_sync_chore_entities` in `tests/test_chore_runtime_entity_sync.py` around lines 104-129 and 173-301 to verify the auth changes do not regress no-reload entity create/update/delete behavior.
  - [ ] If a manual verification pass is needed, validate that a permitted frontend user can create and edit a chore from the custom card and that a non-management user receives the expected translated authorization error.
- **Key issues**
  - Follow `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`: use established scenario/setup patterns, not ad hoc coordinator mutation.
  - The card itself does not need frontend-specific automated tests in this phase if backend behavior is covered and the manual POC remains small.

### Phase 4 – POC wrap-up

- **Goal**: End this phase with a clean yes/no answer on whether the direct-service admin card model is valid for ChoreOps.
- **Steps / detailed work items**
  - [ ] Record whether direct custom-card service calls consistently surface `call.context.user_id` in the hardened CRUD handlers.
  - [ ] Record whether the limited editor can be built entirely from existing helper and translation sensor data without a new API.
  - [ ] Record whether `create_chore`, `update_chore`, and `delete_chore` still produce correct runtime entity sync without config-entry reload after auth hardening.
  - [ ] Decide whether the next step should be popup UX work, broader field coverage, or a production-grade admin editor.
- **Key issues**
  - If any of the three proof targets fail, stop and redesign the contract before adding more UI.

## Testing & validation

- Tests executed:
  - `./utils/quick_lint.sh --fix`
  - `./.venv/bin/mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops`
  - `./.venv/bin/pytest tests/test_chore_crud_services.py tests/test_ui_control_services.py -v --tb=line`
  - `python utils/sync_dashboard_assets.py`
  - `python utils/sync_dashboard_assets.py --check`
  - `./.venv/bin/pytest tests/test_dashboard_helper_size_reduction.py -q`
  - `./.venv/bin/pytest tests/test_chore_runtime_entity_sync.py -q`
- Recommended validation commands:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `mypy tests/`
  - `python -m pytest tests/test_chore_crud_services.py -v --tb=line`
  - `python -m pytest tests/test_chore_runtime_entity_sync.py -v --tb=line`
- Outstanding tests:
  - Manual dashboard verification of translated errors and no-reload entity visibility

## Notes & follow-up

- The current dashboard row action path is still a proxy-entity model: the row template calls `button.press` in `choreops-dashboards/templates/shared/button_card_template_chore_row_v1.yaml` around lines 182-183 and 230-231, and the backend button entities then read `self._context.user_id` in `custom_components/choreops/button.py` around lines 493-520.
- The next POC phase should intentionally prove the alternate model: direct custom-card to ChoreOps service calls, with auth enforced at the service layer.
- Existing no-reload CRUD support is already present in `custom_components/choreops/services.py` around lines 1004-1393 and `custom_components/choreops/coordinator.py` around lines 408-470. This phase should preserve that path, not replace it.
- Dashboard governance note: canonical dashboard authoring assets live in `choreops-dashboards`; vendored runtime copies in `custom_components/choreops/dashboards/` are sync outputs only.
- Custom-card boundary note: the current documented architecture does not ratify `choreops-dashboards` as the permanent home for released custom-card source code. Use the dashboard repo for dashboard-facing translations and wiring, but treat any future released ChoreOps-specific card as a separate frontend-repo concern.
- Recommendation to builder: keep this phase narrow and evidence-driven. If the direct-service card plus service-level auth works, and the repo ownership stays aligned with the standards, that is enough proof to justify a richer admin editor later.

## End-of-plan decision note

- POC exception: keep `utils/custom-card-poc/choreops-create-chore-poc.js` as the temporary non-release source during this proof phase.
- Post-POC repository decision: if the quick chore editor graduates into a released dependency, move the custom card source into a dedicated frontend card repository or dedicated frontend bundle repository.
- Dashboard repo boundary: `choreops-dashboards` remains the canonical source only for templates, registry metadata, preference docs, dependency declarations, and dashboard-visible translations.
- Integration delivery boundary: the integration should consume card dependencies through declared frontend dependency metadata and user-facing install/update guidance, not by treating the dashboard repo as the long-term source for custom card implementation code.

## Builder completion template

When the builder reports back, use this structure:

1. **What changed**: backend files, dashboard repo files, and synced runtime files
2. **Auth proof**: how `call.context.user_id` is enforced across create/update/delete and optional `manage_ui_control`
3. **Repo-boundary proof**: canonical dashboard edits vs vendored sync evidence
4. **Runtime-sync proof**: create/update/delete no-reload validation results
5. **Deviation log**: explicit statement that no deviations were taken, or owner-approved deviations with rationale
6. **Open follow-ups**: anything intentionally deferred to the next phase
