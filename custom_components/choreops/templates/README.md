# ChoreOps Dashboard Templates

This folder contains Jinja2/YAML templates for auto-generating Lovelace dashboards via the ChoreOps integration.

## Template Schema Version

**Current Schema Version**: 1
**Integration Compatibility**: v0.5.0-beta3+ (Schema 43)

> ⚠️ **Important**: The schema version is bumped ONLY when the Python context structure changes incompatibly. Style updates do NOT change the schema version.

## Delimiter Strategy

Templates use **two different Jinja2 syntaxes**:

| Syntax | Processed By | When Evaluated | Example |
|--------|--------------|----------------|---------|
| `<< variable >>` | Python (integration) | Dashboard generation time | `<< assignee.name >>`, `<< assignee.slug >>` |
| `{{ expression }}` | Home Assistant | Dashboard runtime | `{{ states('sensor.x') }}` |

This separation prevents conflicts. The Python Jinja2 environment uses custom delimiters:
- Variable: `<<` and `>>`
- Block: `<%` and `%>` (if needed)

**Assignee-specific templates** (`full`, `minimal`, `compact`) only need two injection points:
- `<< assignee.name >>` - Child's display name (used in `{%- set name = '...' -%}`)
- `<< assignee.slug >>` - URL-safe slug (used in `path:` only)

**Admin template** needs NO injection - it's fully dynamic using HA Jinja2 to discover all assignees.

## Available Styles

| Style     | File                     | Description                                                                                                    |
| --------- | ------------------------ | -------------------------------------------------------------------------------------------------------------- |
| `full`    | `dashboard_full.yaml`    | Full-featured dashboard with all cards (welcome, chores, rewards, badges, achievements, challenges, approvals) |
| `minimal` | `dashboard_minimal.yaml` | Essentials only: welcome card, chores, and rewards                                                             |
| `compact` | `dashboard_compact.yaml` | Same as full but with denser 3-column layout and smaller cards                                                 |
| `admin`   | `dashboard_admin.yaml`   | Approver administration dashboard with assignee dropdown selector                                                     |

## Template Variables (Simplified)

For assignee dashboards, the integration passes just:

```python
{
    "assignee": {
        "name": str,   # e.g., "Alice" - injected as << assignee.name >>
        "slug": str,   # e.g., "alice" - injected as << assignee.slug >>
    }
}
```

All other data (entity IDs, points, chores, etc.) is discovered at runtime using HA Jinja2 via the `ui_dashboard_helper` sensor pattern already built into the templates.

For admin dashboard: No injection needed - fully dynamic.

## Maintenance

### Aesthetic Updates

Edit the `.yaml` file directly and push to GitHub. Users can regenerate dashboards via Options Flow → Dashboard Generator → Force Rebuild.

### New Styles

1. Create `dashboard_{style}.yaml` in this folder
2. Add `DASHBOARD_STYLE_{STYLE}` constant to `const.py`
3. Add style to `DASHBOARD_STYLES` list
4. Update Options Flow to include new style

### Breaking Context Changes

If the Python context structure changes incompatibly:

1. Bump `DASHBOARD_TEMPLATE_SCHEMA_VERSION` in `const.py`
2. Update ALL style templates to use new context structure
3. Document migration in release notes

## Local Fallback

Templates are also bundled in `custom_components/choreops/templates/` for offline installations. Keep both locations in sync when updating.
