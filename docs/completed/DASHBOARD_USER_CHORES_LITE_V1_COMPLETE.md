# Initiative snapshot

- **Name / Code**: User chores lite dashboard profile / `DASHBOARD_USER_CHORES_LITE_V1`
- **Target release / milestone**: Next 1.0.x feature release
- **Owner / driver(s)**: TBD
- **Status**: In progress

## Summary & immediate steps

| Phase / Step                        | Description                                                             | % complete | Quick notes                                                 |
| ----------------------------------- | ----------------------------------------------------------------------- | ---------- | ----------------------------------------------------------- |
| Phase 1 - Spec and contract         | Capture the approved lightweight profile behavior and constraints       | 100%       | Phase 2 profile uses native cards plus `auto-entities` only |
| Phase 2 - Canonical assets          | Add template, preferences, and registry record in `choreops-dashboards` | 0%         | New user profile: `user-chores-lite-v1`                     |
| Phase 3 - Vendored mirror and tests | Sync assets into integration and add focused contract/render coverage   | 0%         | No Python runtime logic changes expected                    |
| Phase 4 - Validation                | Run dashboard sync and targeted tests                                   | 0%         | Focus on render, contract, and dependency coverage          |

1. **Key objective** - Add a dynamic, lower-risk user dashboard profile for older devices that preserves ChoreOps dashboard-helper intelligence while avoiding JavaScript-heavy custom row cards.
2. **Summary of recent work** -
   - Reframed issues 57 and 58 as enhancement requests for legacy-device compatibility.
   - Reviewed current template constraints and confirmed native Lovelace alone cannot build a fully dynamic chore list without a generator layer.
   - Confirmed `tile` supports `tap_action` and `hold_action`, which enables a native interaction path.
3. **Next steps (short term)** -
   - Implement the canonical dashboard assets for `user-chores-lite-v1`.
   - Mirror assets into the vendored integration dashboard directory.
   - Add focused tests for render, dependency, and template contract coverage.
4. **Risks / blockers** -
   - Native tile cards have a much smaller presentation surface than `button-card`, so some state nuance will be intentionally reduced.
   - Action selection must remain deterministic and gracefully degrade when a button entity is absent.
   - The profile must keep the same snippet, validation, and translation discipline as the existing reviewed user templates.
5. **References** -
   - [docs/DASHBOARD_TEMPLATE_GUIDE.md](../DASHBOARD_TEMPLATE_GUIDE.md)
   - [docs/DASHBOARD_UI_DESIGN_GUIDELINE.md](../DASHBOARD_UI_DESIGN_GUIDELINE.md)
   - [docs/DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)
   - [choreops-dashboards/dashboard_registry.json](../../choreops-dashboards/dashboard_registry.json)
   - [choreops-dashboards/templates/user-chores-essential-v1.yaml](../../choreops-dashboards/templates/user-chores-essential-v1.yaml)
6. **Decisions & completion check**
   - **Decisions captured**:
     - Use `user-chores-lite-v1` as the new profile identifier.
     - Keep `auto-entities` as the only custom dependency.
     - Use native `markdown` and `tile` cards for the visible UI.
     - Keep exactly three top-level cards: header, chores, rewards.
     - Remove reward summaries from the header.
     - Use a single-action rule for taps:
       - default: `claim_button_eid` then `approve_button_eid`
       - claimed/requested state: `disapprove_button_eid` first, then `approve_button_eid` fallback
     - Use hold-to-open `more-info` on the status sensor when supported.
   - **Completion confirmation**: `[ ]` All follow-up items completed before requesting owner approval to mark initiative done.

> **Important:** Keep the Summary section current with every meaningful update so the initiative can be understood quickly without reading the implementation details below.

## Functional contract

### Profile identity

- `template_id`: `user-chores-lite-v1`
- `display_name`: `Chores Lite`
- `audience`: `user`
- `category`: `minimal`
- `dependencies.required`: `ha-card:auto-entities`

### Top-level card model

The profile renders exactly three top-level cards inside one user view:

1. Header card
2. Chores card
3. Rewards card

### Header card

- Card type: native `markdown`
- Purpose:
  - welcome copy
  - points total when gamification is enabled
  - chore-only summary counts
- Required data:
  - `core_sensors.points_eid` when available
  - `core_sensors.chores_eid`
  - translated UI labels from `dashboard_helpers.translation_sensor_eid`
- Explicitly excluded:
  - reward summary counts
  - reward state overview

### Chores card

- Outer generator: `custom:auto-entities`
- Visible cards: native `markdown` section headers plus native `tile` cards
- Dynamic source: `dashboard_helper.chores` and `dashboard_helper.chores_by_label`
- Required behavior:
  - preserve the established grouping/sorting preferences from the lightweight chores path where practical
  - reuse the backend/helper sort order and smart-grouping logic rather than inventing a new frontend heuristic
  - keep validation, snippets, and translation behavior aligned with reviewed user templates

#### Chore tap action resolution

For each chore tile:

1. Normalize state:
   - `approved` and `already_approved` map to `completed`
   - `approved_in_part` maps to `completed_in_part`
2. If normalized state is `claimed` or `claimed_in_part`:
   - use `disapprove_button_eid` first
   - if missing, fall back to `approve_button_eid`
3. Otherwise:
   - use `claim_button_eid` first
   - if missing, fall back to `approve_button_eid`
4. If no action entity is available:
   - set `tap_action` to `none`
5. Set `hold_action` to `more-info` on the chore status sensor

### Rewards card

- Outer generator: `custom:auto-entities`
- Visible cards: native `markdown` section headers plus native `tile` cards
- Dynamic source: `dashboard_helper.rewards`
- Required behavior:
  - keep reward interaction local to the rewards card
  - do not duplicate reward status in the header card

#### Reward tap action resolution

For each reward tile:

1. If reward state is `requested`:
   - use `disapprove_button_eid` first
   - if missing, fall back to `approve_button_eid`
2. Otherwise:
   - use `claim_button_eid` first
   - if missing, fall back to `approve_button_eid`
3. If no action entity is available:
   - set `tap_action` to `none`
4. Set `hold_action` to `more-info` on the reward status sensor

## Authoring constraints

- Keep the full reviewed template structure:
  - card header comments
  - numbered configuration/validation/render sections
  - canonical snippet markers
  - graceful fallback validation
- Use the translation sensor and existing dashboard UI keys wherever possible.
- Avoid hardcoded user-facing English when an existing translation key already exists.
- Do not use `custom:button-card`, Mushroom cards, or `card-mod` for this profile.
- Keep colors theme-first and minimal; ordering and icon/state text should do most of the work.

## Testing requirements

- Add one render smoke test for `user-chores-lite-v1`.
- Add one template contract test covering required snippet markers.
- Add one template contract test confirming the lite template uses `auto-entities` and native `tile`, and does not use `button-card`.
- Ensure manifest dependency tests pass with only `ha-card:auto-entities` declared for the new profile.
