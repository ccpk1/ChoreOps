# Initiative Plan: Admin Button Authorization — Fail-Closed (Issue #247)

## Initiative snapshot

- **Name / Code**: Admin Button Auth Fail-Closed / `AUTH-247`
- **Target release / milestone**: Next minor release (after 1.5.0) — **breaking change**
- **Owner / driver(s)**: ChoreOps maintainer / ChoreOps Builder
- **Status**: Complete — all phases implemented, validated, and merged-ready

## Summary & immediate steps

| Phase / Step                | Description                                                                  | % complete | Quick notes                                                                 |
| --------------------------- | ---------------------------------------------------------------------------- | ---------- | --------------------------------------------------------------------------- |
| Phase 1 – Foundation        | Constants, options-flow toggle, auth helper, translations                     | 100%       | ✅ Done — lint + mypy pass on changed files                                  |
| Phase 2 – Core              | Fail-closed auth on 7 admin button classes in `button.py`                     | 100%       | ✅ Done — shared `_ensure_admin_authorized` helper; lint + mypy pass         |
| Phase 3 – Testing           | Button auth tests + options-flow toggle tests                                 | 100%       | ✅ Done — 18 new tests pass; 238 existing tests pass (no regressions)        |
| Phase 4 – Docs & Release    | Wiki updates, cookbook review, breaking-change announcement, translations     | 100%       | ✅ Done — wiki auto-approval migrated to services; access-control + general-options docs updated |

1. **Key objective** – Close the security/cheating gap in Issue #247 by making **administrative button entities** deny anonymous (`user_id=None`) presses, while preserving user-action buttons (claim/redeem) and kiosk mode's intended scope. Add a config toggle so users can opt back to fail-open (with documented risk) while they migrate automations.
2. **Summary of recent work** – All 4 phases implemented and validated. Phase 1: added `CONF_ADMIN_BUTTON_AUTH` toggle (Category B/kiosk pattern) + `is_admin_button_auth_enforced` helper + translations. Phase 2: added shared `_ensure_admin_authorized` helper and applied fail-closed to all 7 admin buttons in `button.py` (preserving kiosk undo branches). Phase 3: 18 new tests in `tests/test_admin_button_auth.py`; 238 existing tests pass with no regressions. Phase 4: wiki auto-approval page migrated from `button.press` to `choreops.approve_chore`; access-control, general-options, and services-reference docs updated.
3. **Next steps (short term)** – PR creation with breaking-change release notes; sync wiki; final review.
4. **Risks / blockers** – (a) Existing user automations pressing admin buttons will break; mitigated by toggle (opt 2) + documented migration to equivalent services (opt 1). (b) `manage_ui_control` used by kid dashboards must remain fail-open. (c) Kiosk mode must NOT be widened to admin actions. (d) `approver_name` spoofing intentionally left as-is per maintainer decision.
5. **References**
   - `docs/ARCHITECTURE.md`
   - `docs/DEVELOPMENT_STANDARDS.md`
   - `docs/CODE_REVIEW_GUIDE.md`
   - `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md`
   - `docs/RELEASE_CHECKLIST.md`
   - `docs/PLAN_TEMPLATE.md`
   - Issue: https://github.com/ccpk1/ChoreOps/issues/247
   - Wiki: `Tips-&-Tricks:-Configure-Automatic-Approval-of-Chores.md`, `Services:-Reference.md`
6. **Decisions & completion check**
   - **Decisions captured**:
     - Fail-closed is the **default** (secure by design).
     - Config toggle `CONF_ADMIN_BUTTON_AUTH` (fail-open ↔ fail-closed) with documented risk, modeled on kiosk mode.
     - Services remain ungated (accepted HA tradeoff). Do NOT gate services.
     - `manage_ui_control` remains fail-open.
     - `approver_name` remains as-is.
     - Kiosk mode scope unchanged (user actions only).
     - Breaking change announced; wiki auto-approval page migrated to services.
   - **Completion confirmation**: `[x]` All follow-up items completed (architecture updates, cleanup, documentation) before requesting owner approval to mark initiative done.

> **Important:** Keep this Summary section current with every meaningful update.

## Platinum & standards compliance (applies to ALL phases)

Per `AGENTS.md`, `docs/DEVELOPMENT_STANDARDS.md`, and `docs/QUALITY_REFERENCE.md`:

- **Typing**: 100% type hints on all new/edited public methods and helpers. Modern syntax `str | None` (never `Optional[str]`). **Zero mypy errors, no `# type: ignore` suppression.**
- **No hardcoded strings**: All user-facing text via `const` constants → translation keys → `translations/en.json`. Use `translation_domain=const.DOMAIN` and `translation_key=const.TRANS_KEY_*` in exceptions.
- **Lazy logging only**: `const.LOGGER.debug("msg %s", var)` — never f-strings in log statements.
- **Constant naming**: `CFOF_*` (plural, flow inputs) for form fields; `CONF_*` for config entry option keys; `DEFAULT_*` for defaults; `TRANS_KEY_*` for translation identifiers. (Per DEVELOPMENT_STANDARDS §3.)
- **Layer boundaries**: The auth gate lives in `button.py` (entity layer) — do NOT move write logic to managers. `helpers/` (auth_helpers) is the right home for the read-only toggle helper. No writes outside `managers/`.
- **Config-flow purity** (DEVELOPMENT_STANDARDS §4): `options_flow.py`/`config_flow.py` must not write storage; the new toggle is purely `config_entry.options`, which `_update_system_settings_and_reload()` handles. No direct `_data` writes.
- **Translations source of truth**: Edit `strings.json` → regenerate `en.json` via `script.translations develop --integration choreops`. Do not hand-edit `en.json`.
- **Definition of Done** (non-negotiable, run in order):
  1. `./utils/quick_lint.sh --fix`
  2. `mypy custom_components/choreops/`
  3. `python -m pytest tests/ -v --tb=line`

## Detailed phase tracking

### Phase 1 – Foundation: Constants, Toggle, Auth Helper, Translations

- **Goal**: Add the config toggle plumbing (modeled **exactly** on the kiosk-mode "Category B" pattern) and the auth helper the admin buttons consult.
- **⚠️ Critical architectural context — read before wiring anything:**
  ChoreOps has **two distinct categories** of config-entry options:
  - **Category A (`DEFAULT_SYSTEM_SETTINGS`)** — points label/icon, precision, default chore points, update interval, calendar period, retention periods, points-adjust values. These are backed up/restored via `backup_helpers.augment_backup_with_settings()` / `validate_config_entry_settings()`, built by `flow_helpers.build_all_system_settings_data()` (~3839) and `build_all_system_settings_schema()` (~3603), and consumed by `config_flow.async_step_reconfigure` and fresh-setup `async_create_entry`.
  - **Category B (special-case UI toggles)** — `kiosk_mode`, `admin_approval_bypass`. **NOT** in `DEFAULT_SYSTEM_SETTINGS`; **NOT** in `build_all_system_settings_data/schema`; not backup/restore tracked. Wired only through: `flow_helpers.build_general_options_schema()` (~3422), `options_flow.async_step_manage_general_options()` (persistence ~5125 + debug log ~5151), and runtime readers in `auth_helpers`.
  - **The new `admin_button_auth` toggle MUST follow Category B (kiosk) exactly.** It is a runtime authorization gate, not a data setting. Do **NOT** add it to `DEFAULT_SYSTEM_SETTINGS` or `build_all_system_settings_*` — that would wrongly wire it into backup/restore and the reconfigure flow, changing restore behavior for a flag that should default via `.get()` at read time.
- **Steps / detailed work items**
  1. **`custom_components/choreops/const.py`** (~line 858, 955, 1821):
     - Add `CFOF_SYSTEM_INPUT_ADMIN_BUTTON_AUTH: Final = "admin_button_auth"` immediately after `CFOF_SYSTEM_INPUT_ADMIN_APPROVAL_BYPASS` (line ~859).
     - Add `CONF_ADMIN_BUTTON_AUTH: Final = "admin_button_auth"` immediately after `CONF_ADMIN_APPROVAL_BYPASS` (line ~956).
     - Add `DEFAULT_ADMIN_BUTTON_AUTH: Final = True` immediately after `DEFAULT_ADMIN_APPROVAL_BYPASS` (line ~1822). **`True` = enforce auth (fail-closed) = secure default.**
     - Add a brief comment stating the polarity: `True` = admin buttons require a logged-in account (fail-closed); `False` = legacy fail-open.
  2. **`custom_components/choreops/helpers/auth_helpers.py`**:
     - Add `is_admin_button_auth_enforced(hass: HomeAssistant) -> bool` mirroring `is_kiosk_mode_enabled` (lines ~50–70): iterate loaded entries, return `entry.options.get(const.CONF_ADMIN_BUTTON_AUTH, const.DEFAULT_ADMIN_BUTTON_AUTH)`, fall back to default. Must be fully type-annotated (`HomeAssistant -> bool`) and keep the `Final`/`Literal` style consistent.
  3. **`custom_components/choreops/helpers/flow_helpers.py`** (`build_general_options_schema`, ~lines 3467–3524):
     - Add `default_admin_button_auth = default.get(const.CONF_ADMIN_BUTTON_AUTH, const.DEFAULT_ADMIN_BUTTON_AUTH)` next to the kiosk/admin_approval defaults (~line 3468).
     - Add a `vol.Required(const.CFOF_SYSTEM_INPUT_ADMIN_BUTTON_AUTH, default=default_admin_button_auth): selector.BooleanSelector()` entry immediately after the `CFOF_SYSTEM_INPUT_ADMIN_APPROVAL_BYPASS` field (~line 3523). Follow the exact dict-entry formatting of its neighbors.
  4. **`custom_components/choreops/options_flow.py`** (`async_step_manage_general_options`, persistence ~line 5129–5135):
     - Add `self._entry_options[const.CONF_ADMIN_BUTTON_AUTH] = user_input.get(const.CFOF_SYSTEM_INPUT_ADMIN_BUTTON_AUTH, const.DEFAULT_ADMIN_BUTTON_AUTH)` after the `CONF_ADMIN_APPROVAL_BYPASS` assignment (~line 5133).
     - Append `Admin Button Auth=%s` to the debug log (~line 5151) for parity with kiosk/admin_approval.
     - **No** change to `_is_kiosk_mode_enabled()` or the non-kiosk link warning logic; the new toggle has no form-warning interaction.
  5. **Translations** — add `admin_button_auth` label + description:
     - **Source of truth**: `custom_components/choreops/strings.json` (general options `data` and `data_description` blocks, where `kiosk_mode`/`admin_approval_bypass` live).
     - Regenerate English master: `.venv/bin/python3 -m script.translations develop --integration choreops` (per AGENTS.md; tests load `translations/en.json`, not `strings.json` directly).
     - Verify `translations/en.json` label + description under the general options `data`/`data_description` (~lines 1703–1721). Do **not** hand-edit `en.json` before regenerating.
     - Label: `"Enforce Authorization for Admin Buttons"`.
     - Description must mirror kiosk's security-warning style: when enabled (default), admin buttons (approve/disapprove chore & reward, bonus, penalty, points adjust) require a logged-in account and will deny anonymous presses from scripts/automations; use the equivalent service (`choreops.approve_chore`, `choreops.apply_bonus`, etc.) for automated flows. When disabled, matches legacy fail-open behavior (security risk: anyone able to reach the button can trigger admin actions).
  6. **Quality-gate prerequisites (Platinum per AGENTS.md / QUALITY_REFERENCE.md):**
     - All new functions/params fully type-annotated (`str | None`, never `Optional[str]`); mypy clean, **no `# type: ignore` suppression**.
     - No hardcoded user-facing strings — everything through `const` + translation keys.
     - No f-strings in logs — use lazy `%s`.
     - Run `./utils/quick_lint.sh --fix`, `mypy custom_components/choreops/`, and the options-flow tests after this phase.
  7. **Key issues**
     - **Do NOT** touch `DEFAULT_SYSTEM_SETTINGS`, `build_all_system_settings_data`, `build_all_system_settings_schema`, `validate_all_system_settings`, or the config-flow reconfigure path. The toggle is Category B (kiosk-style), not a backup/restore-tracked data setting.
     - **Do NOT** add the toggle to the backup/restore round-trip (`backup_helpers`) — kiosk/admin_approval are deliberately excluded there; adding `admin_button_auth` would be inconsistent and require a backup format consideration. If a restore yields no value, the `.get(CONF_ADMIN_BUTTON_AUTH, DEFAULT_ADMIN_BUTTON_AUTH)` read returns the secure default (fail-closed) — which is the safe behavior.
     - Polarity must be unambiguous in the constant comment and translation: `True` = enforced (fail-closed), `False` = fail-open.

### Phase 2 – Core: Fail-Closed on 7 Admin Button Classes

- **Goal**: Change the auth guard in `button.py` from fail-open to fail-closed, gated by the new toggle. Minimize duplication by using a shared helper.
- **⚠️ Authorization semantics — read before implementing (drives the correct `action` per button):**
  `is_user_authorized_for_action()` dispatches to two different authority checks, and the buttons split across them:
  - **`AUTH_ACTION_MANAGEMENT`** → `_has_management_authority`: authorizes if the HA user **is an HA admin** (`user.is_admin`) OR is linked to a ChoreOps user record with `DATA_USER_CAN_MANAGE = True` (legacy approver-record fallback). **No target user.**
    - Applies to: `ApproverBonusApplyButton`, `ApproverPenaltyApplyButton`, `ApproverPointsAdjustButton`.
  - **`AUTH_ACTION_APPROVAL`** with `target_user_id=assignee_id` → `_has_approval_authority_for_target`: authorizes if the actor's linked ChoreOps user record has `DATA_USER_CAN_APPROVE = True` **AND** the target assignee is in the actor's `associated_user_ids` (i.e., a **linked approver of that specific assignee**). HA-admin is a bypass **only if** `CONF_ADMIN_APPROVAL_BYPASS` is enabled (default `True`); if all user records are unlinked, non-admin is allowed as a legacy fallback.
    - Applies to: `ApproverChoreApproveButton`, `ApproverChoreDisapproveButton` (approver branch), `ApproverRewardApproveButton`, `ApproverRewardDisapproveButton`.
  - **Our fail-closed change does NOT alter which rule applies.** It only makes "no authenticated user at all" (`user_id is None`) fail instead of silently succeeding. The existing `is_user_authorized_for_action` logic is unchanged; the helper just gates on it and on the toggle.
  - **Approver display name**: with fail-closed, an admin-button press always has an authenticated user, so the helper can resolve the real name via `hass.auth.async_get_user(user_id).name` for the audit trail (closing the spoofing gap). The `const.DISPLAY_UNKNOWN` fallback becomes unreachable for admin buttons.

- **✅ The gate automatically honors ALL existing integration access-control options (no new logic needed):**
  Because the helper delegates to the existing `is_user_authorized_for_action()`, it inherits every access-control option already wired into that function. Confirmed options:
  - **`CONF_ADMIN_APPROVAL_BYPASS`** (`admin_approval_bypass`, General Options, default `True`): controls whether HA admin accounts can approve/disapprove across the integration. When disabled, HA admins are **not** auto-authorized for approval actions (they must be linked approvers). The gate respects this automatically.
  - **Per-user `can_approve` / `can_manage`** (`DATA_USER_CAN_APPROVE` / `DATA_USER_CAN_MANAGE`, set in Users configuration): a non-admin is only authorized if their linked user record has the capability. `can_manage` gates the MANAGEMENT buttons (bonus/penalty/points-adjust); `can_approve` + `associated_user_ids` gates the APPROVAL buttons.
  - **`associated_user_ids`** (linked approver scope): for APPROVAL actions, the target assignee must be in the actor's associated list — a non-admin approver is **not** global.
  - **`CONF_KIOSK_MODE`**: unchanged — only affects user-action (claim/redeem/undo) buttons, never admin buttons. The new gate is independent of kiosk.
  - **`DATA_USER_CAN_BE_ASSIGNED`**: relevant to participation (claim) actions, not admin buttons; unaffected.
  - **Legacy fallbacks** (unlinked users, legacy approver records): preserved as-is inside `is_user_authorized_for_action`.
  - **Net effect**: the new `CONF_ADMIN_BUTTON_AUTH` toggle is purely the **outermost** gate — it decides whether anonymous presses are even allowed to reach the existing authorization logic. It does **not** re-implement or override any of the above. When `CONF_ADMIN_BUTTON_AUTH` is `True` (default), an anonymous press is denied before any of the above rules run; when `False`, the legacy fail-open behavior (and all the above rules) apply exactly as today.
  - **Implementation note**: the helper must call `is_user_authorized_for_action` with the **same `action` and `target_user_id`** each button currently uses, so the existing access-control options keep working. Do not change the action constants or add new capability checks.
- **Steps / detailed work items**
  1. **Shared auth-helper method** (recommended over 7 nearly-identical inline guards):
     - Add a module-level (or class-level in `button.py`) helper, e.g. `_ensure_admin_authorized(hass, context, assignee_id, action, error_action) -> str`, that:
       - Reads `is_admin_button_auth_enforced(hass)` — if False, returns the current user's name (legacy behavior, no-op).
       - If True: checks `user_id` from `context` — if `None`, raises `HomeAssistantError` with appropriate translation key.
       - Calls `is_user_authorized_for_action(hass, user_id, action, target_user_id=assignee_id)` — if False, raises.
       - On success, resolves the user name via `hass.auth.async_get_user(user_id).name` and returns it (so the caller can use it for the audit trail instead of a separate lookup).
       - This eliminates the `user_obj = await self.hass.auth.async_get_user(user_id) if user_id else None; approver_name = (user_obj.name if user_obj else None) or const.DISPLAY_UNKNOWN` pattern from each button, consolidating 3 duplicated lines × 7 buttons = 21 lines into one helper.
     - **Type signature**: `_ensure_admin_authorized(hass: HomeAssistant, context: Context | None, assignee_id: str | None, action: AuthorizationAction, error_action: str) -> str` returning the approver display name.
     - Note: `ApproverBonusApplyButton`, `ApproverPenaltyApplyButton`, `ApproverPointsAdjustButton` use `AUTH_ACTION_MANAGEMENT` (no `target_user_id`). The helper must accept `target_user_id: str | None = None` for this case.
  2. **Import** `is_admin_button_auth_enforced` in `button.py` (near the existing `is_kiosk_mode_enabled` import at ~line 33). Add import for `_ensure_admin_authorized` (or define it).
  3. **Update 7 admin button classes** to use the shared helper:
     - `ApproverChoreApproveButton` (line ~765): replace `user_id = ...; if user_id and not await ...; user_obj = ...; approver_name = ...` with `approver_name = await _ensure_admin_authorized(self.hass, self._context, self._assignee_id, AUTH_ACTION_APPROVAL, const.ERROR_ACTION_APPROVE_CHORES)`.
     - `ApproverRewardApproveButton` (line ~1221): same pattern with `AUTH_ACTION_APPROVAL`, `const.ERROR_ACTION_APPROVE_REWARDS`.
     - `ApproverRewardDisapproveButton` (line ~1394): same.
     - `ApproverBonusApplyButton` (line ~1544): `AUTH_ACTION_MANAGEMENT`, `target_user_id=None`.
     - `ApproverPenaltyApplyButton` (line ~1696): same.
     - `ApproverPointsAdjustButton` (line ~1875): same.
  4. **`ApproverChoreDisapproveButton` (line ~939)**: the helper is called ONLY in the approver-disapproval branch (`else:`, line ~937). **Preserve** the assignee-undo / kiosk anonymous-undo path (`if is_assignee or is_kiosk_anonymous_undo or is_kiosk_authenticated_undo:`) exactly as-is — this path does NOT call the helper.
  5. **Do NOT touch** user-action buttons (`AssigneeChoreClaimButton` line ~627, `AssigneeRewardRedeemButton` line ~1082) — they remain kiosk-controlled.
  6. **Keep the `try/except HomeAssistantError` wrapper** in each button's `async_press` — the helper raises `HomeAssistantError` which the existing outer catch handles.
  7. **Quality gates**:
     - Helper must be fully type-annotated; modern `str | None` syntax, **no `# type: ignore`**.
     - No hardcoded strings — use `const.TRANS_KEY_ERROR_NOT_AUTHORIZED_ACTION_GLOBAL` and `const.ERROR_ACTION_*`.
     - No f-strings in logs.
     - Run `./utils/quick_lint.sh --fix`, `mypy custom_components/choreops/` after changes.
  8. **Key issues**
     - The helper eliminates the `user_obj`/`approver_name` derivation from each button, making the `approver_name` in the audit trail always come from the authenticated user (closing the spoofing gap as a side benefit). This is a behavioral change for the `approver_name` in the ledger — previously it fell back to `const.DISPLAY_UNKNOWN` when `user_id` was None; now anonymous presses are denied entirely, so the fallback is unreachable for admin buttons.
     - Do NOT widen kiosk mode to admin actions. Kiosk only gates claim/undo user actions.
     - Ensure the disapprove button's undo branch stays functional for kiosk anonymous undo.

### Phase 3 – Testing

- **Goal**: Prove anonymous admin presses are denied (fail-closed), toggle flips behavior, and user buttons/kiosk are unaffected.
- **Steps / detailed work items**
  1. **Extend `tests/test_kiosk_mode_buttons.py`** (or add `tests/test_admin_button_auth.py`) using existing fixtures (`scenario_minimal`, `scenario_full`) and helpers (`claim_chore`, `get_chore_buttons`, `get_reward_buttons`, `get_points_adjustment_buttons`, `find_bonus`, `find_penalty`).
  2. Parameterized tests covering all 7 admin buttons, asserting `HomeAssistantError` when `Context(user_id=None)` is used and the toggle is enforced (default):
     - Chore approve (requires a claim first, per existing pattern at line ~124).
     - Chore disapprove (requires a claim first; use the approver branch, not undo).
     - Reward approve (set points, claim first — see `test_kiosk_disabled_blocks_unauthorized_reward_approve_button`).
     - Reward disapprove.
     - Bonus, penalty, points-adjust (no preconditions needed — see existing tests ~lines 369–400).
  3. **Toggle behavior tests**:
     - With `is_admin_button_auth_enforced` patched to `False` (fail-open), anonymous press on an admin button is ALLOWED (regression guard for opt 2).
     - With `True` (default), anonymous press is DENIED.
  4. **Kiosk regression tests** (must still pass):
     - `test_kiosk_enabled_allows_unauthorized_chore_claim_button` (user button).
     - `test_kiosk_enabled_skips_reward_assignee_auth_guard` (user button).
     - Kiosk enabled + anonymous press on an ADMIN button → still denied (kiosk must not bypass admin auth).
     - Kiosk enabled + anonymous undo (disapprove button) → still allowed (preserve undo branch).
  5. **Options-flow toggle test**: extend `test_options_flow_saves_kiosk_mode_toggle` (or add) to persist `CFOF_SYSTEM_INPUT_ADMIN_BUTTON_AUTH` and assert it survives reopen (default `True`; set `False` and assert persisted).
  6. **Shared-helper unit test**: directly test `_ensure_admin_authorized` in isolation (no entity setup):
     - toggle False + any context → returns approver name (no raise).
     - toggle True + `user_id=None` → raises `HomeAssistantError`.
     - toggle True + unauthorized user → raises.
     - toggle True + authorized user → returns the user's name.
     - Uses `pytest.mark.parametrize` to merge cases; mock `is_admin_button_auth_enforced` and `is_user_authorized_for_action` with `AsyncMock`.
  7. **Access-control-option integration tests** (verify the gate honors existing options — these should already pass via `is_user_authorized_for_action`, but add explicit coverage):
     - **`admin_approval_bypass`**: with `CONF_ADMIN_APPROVAL_BYPASS=False`, an HA admin pressing an APPROVAL button is denied (unless linked approver); with `True`, allowed. Confirm the new gate does not override this.
     - **`can_approve` / `associated_user_ids`**: a non-admin approver with `can_approve=True` but target NOT in `associated_user_ids` is denied on APPROVAL buttons; with the target linked, allowed.
     - **`can_manage`**: a user with `can_manage=False` is denied on MANAGEMENT buttons (bonus/penalty/points-adjust); with `can_manage=True`, allowed.
     - **Kiosk independence**: kiosk enabled does NOT allow anonymous admin presses (already covered in Phase 3 step 4).
     - These tests confirm the new toggle is purely the outermost gate and does not regress the existing access-control matrix.
  8. **Validation commands**:
     ```bash
     ./utils/quick_lint.sh --fix
     mypy custom_components/choreops/
     python -m pytest tests/test_kiosk_mode_buttons.py tests/test_admin_button_auth.py -v --tb=line
     python -m pytest tests/ -v --tb=line
     ```
  9. **Key issues**
     - All new test params need type annotations (per AGENTS.md).
     - Prefer `@pytest.mark.usefixtures` and `pytest.mark.parametrize` to avoid branching.
     - Mock `custom_components.choreops.button.is_admin_button_auth_enforced` (like the existing `is_kiosk_mode_enabled` patch at line ~234) and `is_user_authorized_for_action` with `AsyncMock`.
     - Verify the options-flow persistence test does NOT add the toggle to `DEFAULT_SYSTEM_SETTINGS`-driven assertions (it must not appear in backup/restore or reconfigure tests).

### Phase 4 – Documentation, Wiki & Release

- **Goal**: Communicate the breaking change, migrate documented automation guidance, and finalize release assets.
- **Steps / detailed work items**
  1. **Wiki** (`/workspaces/choreops-wiki/`):
     - Rewrite `Tips-&-Tricks:-Configure-Automatic-Approval-of-Chores.md` to call `choreops.approve_chore` service instead of `button.press` on approve buttons. Add a callout: button press from automations is now denied by default; use the equivalent service.
     - Add a note to `Services:-Reference.md` that services are the recommended path for automation/admin actions.
     - Review `Tips-&-Tricks:-Use-NFC-Tag-to-Mark-Chore-Claimed.md` (claim button = user action, unaffected) and confirm no admin-button-press guidance needs changing. Review cookbook for any other admin `button.press` references.
     - Optionally document the new `admin_button_auth` option in `Configuration:-General-Options.md`.
  2. **Release notes / breaking change**:
     - PR body: mark "Breaking change" in `.github/PULL_REQUEST_TEMPLATE.md` section; add release-note summary.
     - Ensure PR title is release-note friendly and the `enh: breaking-change` label is applied (per `.github/release.yml`).
     - State clearly: users with automations pressing admin buttons must (a) set the toggle to fail-open during migration, and (b) migrate to the equivalent service.
  3. **README / docs** (optional): add a short "Access Control" note pointing to the new toggle and its risk warning.
  4. **Key issues**
     - Sync wiki via the "📖 Sync ChoreOps Wiki" task before/after edits.
     - Regenerate `translations/en.json` from `strings.json` before tests (Phase 1 step 5).
     - Confirm the breaking-change label/categorization with the release process.

## Testing & validation

- Tests executed: (pending — Phase 3)
- Outstanding tests: admin-button anonymous-denial matrix; toggle flips; kiosk regression; options-flow persistence; shared-helper unit test.
- Commands:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/choreops/`
  - `python -m pytest tests/ -v --tb=line`

## Notes & follow-up

- Follow-up: after merge, monitor Issue #247 for confirmation; add wiki/cookbook migration examples; consider a future doc page on "ChoreOps access control & service vs button".
- **Data schema impact — RESOLVED precisely (two separate versioning systems):**
  - **Storage data schema** (`SCHEMA_VERSION_CURRENT`, const.py ~355): versions the `.storage/choreops/choreops_data` file via `store.py`, `migrations/`, and `coordinator.ensure_data_integrity`. Adding `CONF_ADMIN_BUTTON_AUTH` to `config_entry.options` does **NOT** touch this file, so **no storage-data schema bump** and **no `migrations/`/`integrity/` change**.
  - **Config entry schema** (`config_flow.py VERSION = 1`, `MINOR_VERSION`): HA core's own versioning for the config entry, which **stores the entire options dict as-is** (no per-field options schema file exists — there is no `OPTIONS_SCHEMA`/`async_migrate_entry`). New known fields are read defensively via `.get(CONF_X, DEFAULT_X)`, so a new field requires **no config-entry version bump and no migration**.
  - **Terminology corrected**: adding the toggle is a **known-field addition** to the config entry options, *not* a schema migration. The config entry options contract is versioned by HA's `VERSION`/`MINOR_VERSION` machinery — separate from `SCHEMA_VERSION_CURRENT`. Because the toggle is a **Category B** flag (not in `DEFAULT_SYSTEM_SETTINGS`), it is also excluded from the backup/restore round-trip; on restore the `.get(..., DEFAULT_ADMIN_BUTTON_AUTH=True)` read returns the secure fail-closed default. For rigor, the PR should note the config-entry options surface changed (new known key), even though no migration is required.
- **Why Category B (not Category A):** Kiosk/admin_approval_bypass are deliberately excluded from `DEFAULT_SYSTEM_SETTINGS` and `build_all_system_settings_data/schema`. Adding `admin_button_auth` to Category A would wrongly pull it into `backup_helpers.augment_backup_with_settings()` and the config-flow reconfigure path — a restore would then overwrite the flag, and the reconfigure form would expose it under a schema that currently only holds the 9 data settings. Follow the kiosk pattern to keep these runtime gates separate from data settings.
