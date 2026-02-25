# Phase 1 execution spec: Multi-instance hardening (hygiene-first)

## Purpose

This document converts Phase 1 of `MIR-2026Q1` into implementation-ready steps with file-level acceptance criteria.

Primary source plan:
- [MULTI_INSTANCE_HARDENING_IN-PROCESS.md](./MULTI_INSTANCE_HARDENING_IN-PROCESS.md)

## Scope boundaries

- In scope:
  - Service target contract (hybrid UX)
  - Service resolver refactor (remove first-entry assumptions)
  - Service lifecycle safety across multiple config entries
  - Device identifier entry scoping
  - README/services docs + wiki updates
- Out of scope (deferred):
  - Notification action payload token changes

## Implementation order (strict)

1. Service target contract primitives
2. Handler resolver migration
3. Service lifecycle registration guards
4. Device identifier scoping updates
5. Documentation and wiki updates
6. Tests + validation commands

---

## Step 1: Service target contract primitives

### Goal
Add canonical service targeting fields and resolver contract with clear behavior.

### Required code changes

- `custom_components/choreops/const.py`
  - Add constants:
    - `SERVICE_FIELD_CONFIG_ENTRY_ID = "config_entry_id"`
    - Optional convenience field (if implemented): `SERVICE_FIELD_CONFIG_ENTRY_TITLE = "config_entry_title"`
- `custom_components/choreops/services.py`
  - Add resolver helpers near `_get_coordinator_by_entry_id`:
    - `_resolve_target_entry_id(hass, call_data) -> str`
    - `_list_loaded_entry_targets(hass) -> list[dict[str, str]]` (for actionable error payloads/messages)
  - Expand shared schema bases to include optional target fields so all services inherit target support.
- `custom_components/choreops/services.yaml`
  - Add `config_entry_id` (and title field if used) in each service field list and examples.

### Resolver behavior contract

- If `config_entry_id` provided:
  - Must match existing loaded ChoreOps entry exactly.
  - Otherwise raise explicit, user-actionable error.
- If `config_entry_id` omitted:
  - Exactly 1 loaded entry -> use that entry.
  - 0 loaded entries -> explicit “no loaded entry” error.
  - >1 loaded entries -> explicit “ambiguous target” error listing available entries.
- If `config_entry_title` convenience is supported:
  - Resolve only on unique title match among loaded entries.
  - Ambiguous/nonexistent title -> explicit error.
  - ID always takes precedence.

### Acceptance criteria

- No service handler uses implicit “first loaded entry” resolution.
- Errors contain enough context for users to fix automations in one edit.
- Single-instance UX remains frictionless (no required extra field).

---

## Step 2: Handler resolver migration

### Goal
Move all service handlers to one centralized target resolution path.

### Required code changes

- `custom_components/choreops/services.py`
  - Replace all `get_first_choreops_entry(hass)` call paths with `_resolve_target_entry_id(...)`.
  - Ensure every handler obtains `coordinator` from resolved `entry_id`.
- `custom_components/choreops/helpers/entity_helpers.py`
  - Deprecate/remove `get_first_choreops_entry` once no callers remain.

### Acceptance criteria

- Search for `get_first_choreops_entry(` returns zero usages in production code.
- All handlers consistently route through resolver.

---

## Step 3: Service lifecycle safety

### Goal
Prevent unloading one entry from deregistering services needed by another loaded entry.

### Required code changes

- `custom_components/choreops/const.py`
  - Add runtime key constant for service registration count/state.
- `custom_components/choreops/services.py`
  - Add idempotent registration guard (register once).
  - Add ref-count aware unload function (only remove services when last entry unloads).
- `custom_components/choreops/__init__.py`
  - Ensure setup/unload calls use new guard behavior.

### Acceptance criteria

- With two entries loaded, unloading one keeps services available.
- With last entry unloaded, services are removed.

---

## Step 4: Device identifier scoping

### Goal
Ensure device registry identity cannot collide across entries.

### Required code changes

- `custom_components/choreops/helpers/device_helpers.py`
  - Change assignee device identifier from `(DOMAIN, assignee_id)` to entry-scoped form (e.g., `(DOMAIN, f"{entry_id}_{assignee_id}")`).
- `custom_components/choreops/__init__.py`
  - Update `_update_all_assignee_device_names` device lookup to scoped identifier.
- `custom_components/choreops/managers/user_manager.py`
  - Update device removal lookup to scoped identifier.
- `custom_components/choreops/managers/system_manager.py`
  - Update orphan device cleanup lookup to scoped identifier.
- `custom_components/choreops/diagnostics.py`
  - Update assignee extraction logic to support scoped identifier parsing.

### Acceptance criteria

- Device creation and lookup are consistent on one canonical identifier shape.
- Multi-entry duplicate assignee IDs cannot merge onto same device.

---

## Step 5: Docs and wiki updates

### Goal
Make targeting easy to discover and easy to apply.

### Required updates

- `custom_components/choreops/services.yaml`
  - Add single-instance and multi-instance examples for each major service family.
- `README.md`
  - Add service targeting section with resolver behavior table and troubleshooting.
- Wiki (`/workspaces/choreops-wiki`)
  - Update service docs and FAQ:
    - When target field is optional
    - When target field is required
    - How to find `config_entry_id`

### Acceptance criteria

- Users can resolve “ambiguous target” without reading source code.
- Docs are consistent with implemented resolver behavior.

---

## Validation checklist

Run in this order:

1. `./utils/quick_lint.sh --fix`
2. `mypy custom_components/choreops/`
3. `python -m pytest tests/ -v`

Targeted tests expected at minimum:

- Service resolver behavior (0/1/multi entries)
- Service lifecycle unload safety
- Device identifier scoping and lookup consistency

---

## Open decisions (must be resolved before coding)

1. Title convenience field included now or deferred?
   - Default recommendation: include support now but keep ID canonical.
2. Error payload format for ambiguous target:
   - Plain string only vs structured placeholders.
3. Exact scoped device identifier format:
   - Recommendation: `"{entry_id}_{assignee_id}"` for consistency with current unique_id conventions.
