# Supporting reference: Dashboard card toolkit (button-card + auto-entities)

## Purpose

Provide a quick, execution-friendly reference so the dashboard UX builder can rapidly use high-value custom cards (`custom:button-card`, `custom:auto-entities`) without repeatedly re-researching basics.

Use this with:

- `docs/DASHBOARD_TEMPLATE_GUIDE.md`
- `docs/DASHBOARD_UI_DESIGN_GUIDELINE.md`
- `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_DASHBOARD_BUILDER_AGENT_DRAFT.md`

## Critical operating constraints

1. Template source edits are only in `choreops-dashboards/templates/*`.
2. If changes must be testable in integration runtime, sync to vendored copy at end of step/phase:
   - `python utils/sync_dashboard_assets.py`
   - `python utils/sync_dashboard_assets.py --check`
3. Dashboard translation source edits are only in `choreops-dashboards/translations/en_dashboard.json`.
4. Non-English dashboard translation files are pipeline-managed and should not be manually edited.

## Canonical external references

### Button card

- Main repo: `https://github.com/custom-cards/button-card`
- Stable docs: `https://custom-cards.github.io/button-card/`
- README (quick feature scan): `https://raw.githubusercontent.com/custom-cards/button-card/master/README.md`

### Auto entities

- Main repo: `https://github.com/thomasloven/lovelace-auto-entities`
- README (usage/filter/sort details): `https://raw.githubusercontent.com/thomasloven/lovelace-auto-entities/master/README.md`

### Home Assistant references

- Dashboards overview: `https://www.home-assistant.io/dashboards/`
- Templating: `https://www.home-assistant.io/docs/configuration/templating/`
- Conditional card/visibility patterns: `https://www.home-assistant.io/dashboards/conditional/`

## Quick decision matrix

| Need                                                | Prefer                          | Why                                     |
| --------------------------------------------------- | ------------------------------- | --------------------------------------- |
| App-like action tiles with rich visuals             | `custom:button-card`            | Maximum layout/state/action flexibility |
| Dynamic list of entities based on filters/templates | `custom:auto-entities`          | Handles include/exclude/sort at runtime |
| Static simple card                                  | Native cards                    | Lower complexity and fewer dependencies |
| Visibility by conditions                            | Native visibility / conditional | Cleaner than complex template branching |

## `custom:button-card` practical patterns

### Use when

- You need polished action affordances (claim/undo/approve) with strong state visual language.
- You need card-level styling and custom layout per state.

### Core strengths

- Tap/hold/double actions and service calls.
- Per-state styling/icon/label logic.
- JS template support for high customizability.

### Cautions

- Can become hard to maintain if too much logic is embedded in one card.
- Prefer reusable fragments/patterns over bespoke one-off mega-cards.

### ChoreOps usage guidance

- Keep primary chore icon visible in all states.
- Follow multi-channel state communication from UI guideline (text + icon + color, minimum).
- Avoid hardcoded entity IDs; keep dynamic helper lookup contracts intact.

## `custom:auto-entities` practical patterns

### Use when

- You need dynamic chore/reward/approval lists where entity membership changes.
- You need grouping/sorting by state/age/attribute without hardcoding entity lists.

### Core strengths

- `include` + `exclude` filter model (ALL rules per filter, ANY filter in list).
- Template-driven entity list generation.
- Sorting by state, attributes, timestamps, and numeric comparisons.

### Cautions

- Quoting and YAML syntax matter (`"on"`, `"> 25"`, regex strings).
- Template results must stay predictable; include empty-state strategy (`show_empty`, `else`).

### ChoreOps usage guidance

- Use for chore list cards and admin operational queues.
- Keep fallback card behavior user-friendly when no entities match.
- Preserve readability: split complex filter logic into documented sections.

## Required dependency governance (non-negotiable)

When adding or removing any `custom:*` card usage:

1. Update canonical dashboard registry dependencies in `choreops-dashboards/dashboard_registry.json`.
2. Sync to vendored runtime via `python utils/sync_dashboard_assets.py`.
3. Verify parity via `python utils/sync_dashboard_assets.py --check`.
4. Validate dependency contract tests:
   - `python -m pytest tests/test_dashboard_manifest_dependencies_contract.py -v --tb=line`

## Builder execution checklist (card-focused step)

Before editing:

- [ ] Identify target card and whether dynamic entities are needed.
- [ ] Choose `button-card` or `auto-entities` with quick matrix.
- [ ] Confirm required dependencies already declared for target template.

After editing:

- [ ] Validate template renders in smoke tests.
- [ ] Validate dependency contract tests.
- [ ] Update preference doc if new `pref_*` knobs are introduced.
- [ ] Update UI/template docs if behavior semantics changed.

## Suggested prompt snippet for UX builder agent

Use this snippet inside the agent instructions for easy access:

> For dashboard card decisions, consult `docs/in-process/DASHBOARD_UX_MODERNIZATION_SUP_CARD_TOOLKIT.md` first, then verify syntax/edge cases from upstream docs for `button-card` and `auto-entities` before implementing major card rewrites.
