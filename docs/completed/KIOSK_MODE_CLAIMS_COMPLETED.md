# Initiative Plan: Kiosk Mode for Kid Claim Buttons

## Initiative snapshot

- **Name / Code**: Kiosk Mode for Kid Claim Buttons (`KIOSK_MODE_CLAIMS`)
- **Target release / milestone**: v0.5.x (post-beta4 patch train)
- **Owner / driver(s)**: KidsChores core team
- **Status**: Complete

## Summary & immediate steps

| Phase / Step                     | Description                                              | % complete | Quick notes                                        |
| -------------------------------- | -------------------------------------------------------- | ---------- | -------------------------------------------------- |
| Phase 1 – Settings & UX contract | Add general option and risk disclosure text              | 100%       | Implemented in const/schema/options/en.json        |
| Phase 2 – Authorization wiring   | Apply kiosk behavior to kid claim button paths only      | 100%       | Button-only bypass implemented; services unchanged |
| Phase 3 – Test & validation      | Add targeted coverage for auth branches and options flow | 100%       | Targeted tests added and passing                   |

1. **Key objective** – Add an optional `kiosk` mode in General Options so kid-facing claim buttons can be used from shared wall tablets without requiring the dashboard user to match the kid `ha_user_id`.
2. **Summary of recent work** – Implemented settings, button-only auth bypass, and focused test coverage (`test_kc_helpers.py` + new `test_kiosk_mode_buttons.py`) including options persistence and service-auth regression.
3. **Next steps (short term)** – None. Ready for archive and release-note mention.
4. **Risks / blockers** – Enabling kiosk mode lowers identity assurance on devices with open access; must include explicit warning copy and preserve strict checks for services and parent actions.
5. **References**
   - [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [docs/CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)
   - [tests/AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md)
   - [docs/RELEASE_CHECKLIST.md](../RELEASE_CHECKLIST.md)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Scope is **kid claim buttons only** (`KidChoreClaimButton`, `KidRewardRedeemButton`), not a global auth bypass.
     - Service-level authorization in `services.py` remains unchanged.
     - Default is secure (`kiosk mode` disabled).
  - **Completion confirmation**: `[x]` All follow-up items completed (tests, docs, risk text, validation gates) before requesting owner approval.

## Tracking expectations

- **Summary upkeep**: Update this table and bullets after each meaningful implementation checkpoint.
- **Detailed tracking**: Keep implementation detail and blockers in the phase sections below.

## Detailed phase tracking

### Phase 1 – Settings & UX contract

- **Goal**: Add a safe, explicit general option with user-facing warning language and stable constants.
- **Steps / detailed work items**
  - [x] Add system setting constants for kiosk mode
    - File: [custom_components/kidschores/const.py](../../custom_components/kidschores/const.py)
    - Add `CONF_*`, `DEFAULT_*`, and `CFOF_SYSTEM_INPUT_*` constants near existing General Options constants (around current `CFOF_SYSTEM_INPUT_SHOW_LEGACY_ENTITIES` and `CONF_SHOW_LEGACY_ENTITIES`, ~lines 825-861).
  - [x] Extend general options schema with kiosk toggle field
    - File: [custom_components/kidschores/helpers/flow_helpers.py](../../custom_components/kidschores/helpers/flow_helpers.py)
    - Update `build_general_options_schema()` (around ~2712-2785) with a `selector.BooleanSelector()` field for kiosk mode.
  - [x] Persist kiosk toggle in Options Flow update path
    - File: [custom_components/kidschores/options_flow.py](../../custom_components/kidschores/options_flow.py)
    - In `async_step_manage_general_options()` (~4248-4356), read and store the toggle in `self._entry_options`, and include it in debug logging payload.
  - [x] Add high-visibility risk disclosure copy in translations
    - File: [custom_components/kidschores/translations/en.json](../../custom_components/kidschores/translations/en.json)
    - Under `options.step.manage_general_options` (around ~1343-1369), add label + description that clearly warns: shared-device mode can allow any logged-in dashboard user on that device to submit kid claims.
  - [x] Update architecture/system-settings docs if setting count or list changes
    - File: [docs/ARCHITECTURE.md](../ARCHITECTURE.md)
    - Update the System Settings table/notes in the configuration section to include kiosk mode if it is counted as a system option.
- **Key issues**
  - Wording must balance safety and usability: clear warning without blocking legitimate wall-tablet deployments.
  - Keep naming aligned with existing constants and translation key patterns.

### Phase 2 – Authorization wiring (button-only)

- **Goal**: Allow kiosk mode to bypass kid-user match checks only for kid claim buttons.
- **Steps / detailed work items**
  - [x] Add helper accessor for kiosk mode state
    - File: [custom_components/kidschores/helpers/auth_helpers.py](../../custom_components/kidschores/helpers/auth_helpers.py)
    - Add a small helper to read current config-entry option with secure default (`False`) and avoid duplicated option lookups.
  - [x] Introduce conditional bypass in kid chore claim button path
    - File: [custom_components/kidschores/button.py](../../custom_components/kidschores/button.py)
    - In `KidChoreClaimButton.async_press()` (~428-468), bypass `is_user_authorized_for_kid()` only when kiosk mode is enabled.
  - [x] Introduce conditional bypass in kid reward redeem button path
    - File: [custom_components/kidschores/button.py](../../custom_components/kidschores/button.py)
    - In `KidRewardRedeemButton.async_press()` (~846-890), apply same kiosk condition.
  - [x] Preserve strict auth for parent/global actions and services
    - Files: [custom_components/kidschores/button.py](../../custom_components/kidschores/button.py), [custom_components/kidschores/services.py](../../custom_components/kidschores/services.py)
    - Confirm **no behavior change** for parent approve/disapprove buttons and service handlers (e.g., `handle_claim_chore` around ~985-1022).
  - [x] Add explicit log branch for kiosk authorization path
    - Files: [custom_components/kidschores/button.py](../../custom_components/kidschores/button.py)
    - Add concise lazy logs indicating kiosk path used vs standard auth path.
- **Key issues**
  - Avoid accidental widening of authorization via shared helper changes.
  - Must not alter undo/disapprove kid-vs-parent logic branches.

### Phase 3 – Test & validation

- **Goal**: Prove kiosk mode behavior is gated, deliberate, and does not weaken non-targeted authorization paths.
- **Steps / detailed work items**
  - [x] Add auth-helper unit coverage for kiosk mode accessor/decision function
    - File: [tests/test_kc_helpers.py](../../tests/test_kc_helpers.py)
    - Add tests for disabled default and enabled option states.
  - [x] Add button behavior tests for kid claim/redeem with kiosk off/on
    - Suggested file: [tests/test_kid_kiosk_mode_buttons.py](../../tests/test_kid_kiosk_mode_buttons.py) (new)
    - Validate: unauthorized kid context blocked when off; same context allowed when on.
  - [x] Add options-flow test for saving kiosk mode
    - File: [tests/test_options_flow_entity_crud.py](../../tests/test_options_flow_entity_crud.py) or dedicated new options-flow test module
    - Validate config entry options contains kiosk key after submit.
  - [x] Add regression test that service auth remains enforced
    - File: [tests/test_chore_services.py](../../tests/test_chore_services.py) and/or reward service test module
    - Validate unauthorized service call still fails even if kiosk mode is enabled.
  - [x] Run required quality gates and record results
    - Commands:
      - `./utils/quick_lint.sh --fix`
      - `mypy custom_components/kidschores/`
      - `python -m pytest tests/ -v --tb=line`
- **Key issues**
  - Tests should use scenario fixtures and `tests.helpers` constants per project testing standards.
  - Keep scope focused on new kiosk behavior; do not refactor unrelated auth tests.

## Testing & validation

- **Targeted tests to execute first**:
  - `python -m pytest tests/test_kc_helpers.py -v`
  - `python -m pytest tests/test_kid_kiosk_mode_buttons.py -v` (new)
  - `python -m pytest tests/test_options_flow_entity_crud.py -v`
  - `python -m pytest tests/test_chore_services.py -v`
- **Full gates before merge**:
  - `./utils/quick_lint.sh --fix`
  - `mypy custom_components/kidschores/`
  - `python -m pytest tests/ -v --tb=line`
- **Outstanding tests**: None.

## Notes & follow-up

- Security posture statement for release notes should explicitly recommend kiosk mode only for physically trusted devices (e.g., mounted household tablet with restricted profile).
- If future demand emerges for finer control, consider a separate initiative for per-kid or per-device trust scopes; keep this initiative intentionally minimal.
- No storage schema migration is expected because this is a `config_entry.options` setting.
