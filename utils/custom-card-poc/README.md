# ChoreOps Quick Chore Editor POC

This folder contains a minimal proof-of-concept custom card for creating and
editing chores through the existing ChoreOps CRUD services.

Scope is intentionally narrow:

- one chore name field
- one points field
- assignee selection from existing dashboard helper data
- compact completion type selector
- compact description field
- compact icon field
- compact due date field
- compact non-custom frequency selector
- create and edit modes only
- no labels, custom recurrence interval controls, or deeper workflow policy controls

The card reads live assignee options from the ChoreOps system dashboard helper and
uses direct `create_chore` and `update_chore` service calls while reusing the
existing translation sensor, system dashboard helper, and chore status sensors.

Current compact field set:

- name
- points
- assigned users
- completion criteria
- description
- icon
- due date
- frequency (non-custom options only)

## File

- `choreops-create-chore-poc.js`

## Expected card config

```yaml
type: custom:choreops-quick-chore-editor-poc
title: Quick chore editor
system_dashboard_helper: sensor.choreops_system_dashboard_helper
```

Optional alternative:

```yaml
type: custom:choreops-quick-chore-editor-poc
title: Quick chore editor
config_entry_id: YOUR_CONFIG_ENTRY_ID
```

Legacy alias still supported for the same card:

```yaml
type: custom:choreops-create-chore-poc
title: Quick chore editor
```

If `system_dashboard_helper` is omitted, the card tries to auto-discover a single
ChoreOps system dashboard helper. If multiple ChoreOps instances exist, set either
`system_dashboard_helper` or `config_entry_id`.

## Manual install for local testing

One simple workflow for testing is:

1. Copy `choreops-create-chore-poc.js` into a frontend resource location such as
   Home Assistant `www/`.
2. Add it as a Lovelace JavaScript module resource.
3. Add the card to an admin dashboard.

Example resource:

```yaml
url: /local/choreops-create-chore-poc.js
type: module
```

## Notes

- This is a POC only. It is not bundled, published, or wired into dashboard assets.
- It assumes the existing ChoreOps CRUD services remain the source of truth.
- Dashboard-visible runtime strings are expected to come from the dashboard
   translation sensor, with canonical source keys owned in `choreops-dashboards`.
- It keeps the POC source local to this repository only as a temporary
   non-release artifact.
