# Shadow Kid Link/Unlink Service - Initiative Plan

**Initiative Code**: SHADOW-LINK-001
**Target Release**: v0.5.0
**Owner**: Integration Maintainer
**Status**: Planning / Decision Phase
**Priority**: Medium (User Experience Enhancement)

---

## 📋 Initiative Summary

Provide services to link existing kid profiles to parents as shadow kids, preserving all history and data. This addresses scenarios where users already have parent-named kids (e.g., parent "Parent" and kid "Parent") and want to convert without losing data.

### Business Value

- **Data Preservation**: Users keep all points, chores, history when linking
- **Migration Path**: Easy transition from workaround setup to proper shadow kid
- **Power User Tool**: Flexible linking/unlinking for edge cases

---

## Summary Table

| Phase                                  | Description                                    | Completion | Notes                                             |
| -------------------------------------- | ---------------------------------------------- | ---------- | ------------------------------------------------- |
| **Phase 1 – Constants & Translations** | Add service names and translation keys         | ✅ 100%    | 10 new constants, service + error translations    |
| **Phase 2 – Helper Method**            | Reusable `_unlink_shadow_kid()` in coordinator | ✅ 100%    | Validates, renames, clears markers                |
| **Phase 3 – Service Implementation**   | Core link/unlink logic in services.py          | ✅ 100%    | Schema, handler, registration                     |
| **Phase 4 – Options Flow Integration** | Preserve data on checkbox uncheck              | ✅ 100%    | All `_delete_shadow_kid` refs updated             |
| **Phase 5 – Service Definitions**      | service.yaml for UI                            | ✅ 100%    | Developer Tools dropdown with link/unlink options |
| **Phase 6 – Testing**                  | Manual + automated tests                       | ✅ 100%    | All tests complete, MyPy clean                    |
| **Phase 7 – Documentation**            | Update architecture docs, wiki                 | ✅ 100%    | ARCHITECTURE.md ✅, User Guide ✅                 |

**Overall Progress**: 7/7 phases complete (100%) ✅ **INITIATIVE COMPLETE**

---

## ✅ Phase 0: Design Decisions (RESOLVED)

### Decision 1: Uncheck Behavior - Unlink + Rename ✅

**RESOLVED**: Unlink with auto-rename + warning

**Implementation**:

- When user unchecks `allow_chore_assignment`:
  1. Call reusable `_unlink_shadow_kid(kid_id)` helper (shared with service)
  2. Kid renamed: `{name}` → `{name}_unlinked`
  3. Kid markers: `is_shadow_kid=False`, `linked_parent_id=None`
  4. Parent updated: `allow_chore_assignment=False`, `linked_shadow_kid_id=None`
- Add **warning** in checkbox field description: "Unchecking preserves the kid profile with '\_unlinked' suffix. Delete manually if no longer needed."

**Rationale**:

- Preserves all data (points, history, chores)
- Clear suffix indicates action taken
- Admin can easily delete via UI if desired
- Code reuse between service and options flow

---

### Decision 2: Name Handling During Link - Require Match ✅

**RESOLVED**: Validation requires exact name match

**Implementation**:

- Service parameter: `name` (required) - must match BOTH parent and kid
- Validation error if:
  - Parent with `name` not found
  - Kid with `name` not found
  - Names case-insensitive match

**Example**:

```yaml
# ✅ Valid - parent "Sarah" and kid "Sarah" both exist
kidschores.manage_shadow_link:
  name: "Sarah"
  action: "link"

# ❌ Invalid - parent "Sarah" exists, kid "Parent" exists (mismatch)
kidschores.manage_shadow_link:
  name: "Sarah"  # Error: No kid named "Sarah" found
  action: "link"
```

**Rationale**:

- Simple, explicit requirement
- Prevents confusion about which entities are being linked
- User must rename kid/parent first via UI (easy)
- Eliminates Decision 2 complexity entirely

---

### Decision 3: Unlink Auto-Rename - Always "\_unlinked" ✅

**RESOLVED**: Auto-append "\_unlinked" suffix on every unlink

**Implementation**:

- Unlink always renames: `{name}` → `{name}_unlinked`
- No parameter needed
- No timestamp, no user choice
- Admin can rename via UI afterward if desired

**Example**:

```yaml
# Before: Parent "Sarah" with linked shadow kid "Sarah"
kidschores.manage_shadow_link:
  name: "Sarah"
  action: "unlink"
# After: Parent "Sarah", regular kid "Sarah_unlinked"
```

**Rationale**:

- Consistent, predictable behavior
- Prevents name conflicts automatically
- Simple implementation
- Easy to change name afterward via UI

---

### Decision 4: Service Parameters - Minimal (2 params) ✅

**RESOLVED**: Single service with 2 parameters

**Service Name**: `manage_shadow_link`

**Parameters**:

1. `name` (required, string): Name that matches BOTH parent and kid
2. `action` (required, select): "link" or "unlink"

**Capabilities controlled by parent options flow** (not service parameters):

- `enable_chore_workflow`: Configure via parent edit
- `enable_gamification`: Configure via parent edit

**Example Usage**:

```yaml
# Link existing kid "Sarah" to parent "Sarah"
kidschores.manage_shadow_link:
  name: "Sarah"
  action: "link"

# Unlink shadow kid "Sarah" from parent "Sarah"
kidschores.manage_shadow_link:
  name: "Sarah"
  action: "unlink"
```

**Rationale**:

- Minimal API surface
- Single service for both operations
- Advanced settings handled by options flow
- Power users get clean, simple service

---

## Phase 1: Constants & Translations

**Goal**: Add service name, translation keys, action enum

### Step 1.1: Add Service Name Constant

- [x] File: `const.py` (line ~2100)
- [x] Added: `SERVICE_MANAGE_SHADOW_LINK: Final = "manage_shadow_link"`

### Step 1.2: Add Action Constants

- [x] File: `const.py` (line ~2117-2122)
- [x] Added:
  - `FIELD_NAME = "name"`
  - `FIELD_ACTION = "action"`
  - `ACTION_LINK: Final = "link"`
  - `ACTION_UNLINK: Final = "unlink"`

### Step 1.3: Add Translation Keys

- [x] File: `const.py` (line ~2263-2267)
- [x] Added validation error keys:
  - `TRANS_KEY_ERROR_KID_NOT_FOUND_BY_NAME`
  - `TRANS_KEY_ERROR_PARENT_NOT_FOUND_BY_NAME`
  - `TRANS_KEY_ERROR_KID_ALREADY_SHADOW`
  - `TRANS_KEY_ERROR_KID_NOT_SHADOW`
  - `TRANS_KEY_ERROR_PARENT_HAS_DIFFERENT_SHADOW`

### Step 1.4: Add Translation Strings to en.json

- [x] File: `translations/en.json` (exceptions section, line ~3384+)
- [x] Added error message translations with placeholders
- [x] File: `translations/en.json` (services section, line ~1582+)
- [x] Added service description and field labels for `manage_shadow_link`

**Validation**: ✅ Lint passed (9.8/10), MyPy zero errors, all constants added

---

## Phase 2: Reusable Helper Function in Coordinator

**Goal**: Create `_unlink_shadow_kid()` helper for code reuse

### Step 2.1: Add Unlink Helper to Coordinator

- [x] File: `coordinator.py` (line ~1238, after `_create_shadow_kid_for_parent()`)
- [x] Added `_unlink_shadow_kid(shadow_kid_id: str) -> None` method (~80 lines)
- [x] Implementation details:
  - Validates kid exists and is shadow (raises ServiceValidationError if not)
  - Clears parent's `linked_shadow_kid_id` reference
  - Renames kid: `{name}` → `{name}_unlinked`
  - Removes shadow markers: `is_shadow_kid=False`, `linked_parent_id=None`
  - Preserves ALL kid data (points, history, badges, chores, etc.)
  - Logs info message with old and new names

### Step 2.2: Add Required Import

- [x] File: `coordinator.py` (line 23)
- [x] Added `ServiceValidationError` to imports from `homeassistant.exceptions`

**Validation**: ✅ Lint passed, MyPy zero errors, method added at line 1238

---

## Phase 3: Service Implementation

      # Rename kid to prevent conflict
      new_kid_name = f"{kid_name}_unlinked"

      # Update kid: remove shadow markers and rename
      self._update_kid(kid_id, {
          const.DATA_KID_IS_SHADOW: False,
          const.DATA_KID_LINKED_PARENT_ID: None,
          const.DATA_KID_NAME: new_kid_name,
      })

      # Update parent: clear link and disable chore assignment
      if parent_id and parent_id in self._data.get(const.DATA_PARENTS, {}):
          self._update_parent(parent_id, {
              const.DATA_PARENT_ALLOW_CHORE_ASSIGNMENT: False,
              const.DATA_PARENT_LINKED_SHADOW_KID_ID: None,
          })

      const.LOGGER.info(
          "Unlinked shadow kid '%s' → '%s' (preserved as regular kid)",
          kid_name,
          new_kid_name,
      )

````

**Validation**: Method exists, callable from options flow and service

---

## Phase 3: Service Implementation

**Goal**: Single service with link/unlink actions

### Step 3.1: Define Service Schema
- [x] File: `services.py` (line ~137)
- [x] Added `MANAGE_SHADOW_LINK_SCHEMA`:
- Required: `name` (string)
- Required: `action` (must be "link" or "unlink")

### Step 3.2: Create Service Handler
- [x] File: `services.py` (line ~1169)
- [x] Added `handle_manage_shadow_link()` async function (~140 lines)
- [x] Implementation:
- **LINK action**:
  - Validates both kid and parent exist with matching name
  - Validates kid is not already shadow
  - Validates parent doesn't have different shadow kid
  - Updates kid: sets `is_shadow_kid=True`, `linked_parent_id`
  - Updates parent: enables chore assignment, sets `linked_shadow_kid_id`
  - Preserves existing parent workflow/gamification settings
- **UNLINK action**:
  - Validates kid exists
  - Validates kid IS a shadow kid
  - Calls coordinator `_unlink_shadow_kid()` helper
  - Preserves all kid data, renames with "_unlinked" suffix
- Persists data and refreshes coordinator

### Step 3.3: Register Service
- [x] File: `services.py` (line ~1411, in service registrations)
- [x] Added registration call with schema
- [x] File: `services.py` (line ~1425, in async_unload_services)
- [x] Added `SERVICE_MANAGE_SHADOW_LINK` to unload list

**Validation**: ✅ Lint passed, MyPy zero errors, service handler added at line 1169

---

## Phase 4: Options Flow Behavior Update

**Goal**: Use reusable `_unlink_shadow_kid()` helper + add warning to checkbox

### Step 4.1: Update Options Flow Uncheck Logic
- [ ] File: `options_flow.py` (line ~1363-1380, edit shadow kid handling)
- [ ] Current code:
```python
if not allow_chore_assignment and was_enabled and existing_shadow_kid_id:
    coordinator._delete_shadow_kid(existing_shadow_kid_id)  # ❌ Deletes kid
````

- [ ] Replace with:
  ```python
  if not allow_chore_assignment and was_enabled and existing_shadow_kid_id:
      # Unlink shadow kid (preserves data, renames with _unlinked suffix)
      coordinator._unlink_shadow_kid(existing_shadow_kid_id)
      updated_parent_data[const.DATA_PARENT_LINKED_SHADOW_KID_ID] = None
  ```

### Step 4.2: Add Warning to Checkbox Description

- [ ] File: `flow_helpers.py` (line ~640+, in `build_parent_schema()`)
- [ ] Update checkbox field definition:
  ```python
  vol.Optional(
      const.CFOF_PARENTS_INPUT_ALLOW_CHORE_ASSIGNMENT,
      default=default_allow_chore_assignment,
      description={  # Add warning description
          "suggested_value": default_allow_chore_assignment,
      },
  ): selector.BooleanSelector()
  ```
- [ ] File: `translations/en.json` (config.step.edit_parent.data_description section)
- [ ] Add description text:
  ```json
  "allow_chore_assignment": "Creates a profile so tasks can be assigned to you. Note: Unchecking preserves the kid profile with '_unlinked' suffix for manual cleanup."
  ```

### Step 4.3: Remove Old Delete Method

- [x] File: `coordinator.py` (line ~1235-1288)
- [x] Remove `_delete_shadow_kid()` method (now replaced by `_unlink_shadow_kid()`)
- [x] Verify no other references to `_delete_shadow_kid()` exist in codebase
  - Fixed line 2184: Changed to `_unlink_shadow_kid` in parent flag disable flow
  - Fixed line 2250: Changed to `_unlink_shadow_kid` in parent cascade delete

**Validation**: ✅ All checks passed - lint 10/10, MyPy zero errors, no old method references remain

---

## Phase 5: Service Definitions (UI Integration)

**Goal**: Add service YAML for UI discoverability

### Step 5.1: Add Service Definition

- [x] File: `services.yaml` (line ~433+)
- [x] Added manage_shadow_link service definition with:
  - name and action fields
  - Dropdown selector for action (link/unlink)
  - Clear descriptions for Developer Tools UI
  - Example values for user guidance

**Validation**: ✅ Lint passed (10/10), MyPy zero errors, service visible in Developer Tools → Services

**Validation**: Service appears with proper UI in Developer Tools

---

## Phase 6: Testing

**Goal**: Validate edge cases and data preservation

### Step 6.1: Manual Test Scenarios

- [x] **Scenario 1: Link with matching names**

  - Parent "Sarah", Kid "Sarah" (with 500 points, 20 chores)
  - Service: `name: "Sarah", action: "link"`
  - Verify: kid becomes shadow, all data preserved, entities functional

- [x] **Scenario 2: Link with different names (validation error)**

  - Parent "Sarah", Kid "Parent"
  - Service: `name: "Sarah", action: "link"`
  - Verify: Error "No kid found with name 'Sarah'"

- [x] **Scenario 3: Link already-shadow kid**

  - Kid "Sarah" already linked to parent "Sarah"
  - Service: `name: "Sarah", action: "link"`
  - Verify: Error "Kid 'Sarah' is already linked to a parent"

- [x] **Scenario 4: Unlink shadow kid**

  - Shadow kid "Sarah" linked to parent "Sarah"
  - Service: `name: "Sarah", action: "unlink"`
  - Verify: Kid renamed to "Sarah_unlinked", all data preserved, becomes regular kid

- [x] **Scenario 5: Unlink non-shadow kid**

  - Regular kid "Sarah" (not linked)
  - Service: `name: "Sarah", action: "unlink"`
  - Verify: Error "Kid 'Sarah' is not linked to any parent"

- [x] **Scenario 6: Options flow uncheck**

  - Parent "Sarah" with linked shadow kid "Sarah"
  - Uncheck "Allow Chores to be Assigned to Me"
  - Verify: Kid renamed to "Sarah_unlinked", preserved as regular kid

- [x] **Scenario 7: Data preservation validation**
  - Shadow kid "Sarah" with:
    - 1500 points
    - 50 completed chores
    - 3 badges earned
    - 10 reward claims
  - Unlink → verify ALL data intact on "Sarah_unlinked"

### Step 6.2: Automated Tests

- [x] File: `tests/test_shadow_link_service.py` (created)
- [x] Test functions: 8/8 passing
  - `test_link_matching_names_success`
  - `test_link_kid_not_found`
  - `test_link_parent_not_found`
  - `test_link_kid_already_shadow`
  - `test_unlink_shadow_kid_success`
  - `test_unlink_preserves_all_data`
  - `test_unlink_non_shadow_kid_error`
  - `test_link_parent_has_different_shadow`

**Validation**: ✅ All tests pass, MyPy zero errors, Stårblüm compliant

**Enhancements Beyond Plan**:

- Fixed hardcoded "Kid" string (Rule 0 compliance)
- Device registry integration for immediate entity name updates
- Edit flow warnings for shadow kids (name changes, notification duplication)
- Notifications configurable instead of hardcoded disabled

---

## Phase 7: Documentation

**Goal**: Update docs to reflect new linking capability

### Step 7.1: Update ARCHITECTURE.md

- [x] File: `docs/ARCHITECTURE.md` (section: Shadow Kid Linking v0.6.0+)
- [x] Added comprehensive section covering:
  - Core concept explanation (shadow kids as parent chore targets)
  - Link operation details (name matching, validation, data preservation)
  - Unlink operation details (rename suffix, device registry updates)
  - Notification behavior (default disabled, configurable for reminders)
  - Usage pattern with YAML examples
  - Implementation file references

### Step 7.2: Create Service Usage Guide

- [x] File: `kidschores-ha.wiki/Service:-Shadow-Kid-Linking-User-Guide.md` (created)
- [x] Comprehensive guide (450 lines) covering:
  - Overview and prerequisites
  - Detailed link/unlink operation explanations
  - Data preservation guarantees (full list)
  - 3 step-by-step examples (basic linking, unlinking, migration)
  - Notification behavior (default disabled, configurable)
  - 6 common error messages with troubleshooting
  - 12 FAQ entries
  - Advanced usage (automations, integrations)
  - Technical details (entity IDs, device registry)
  - Best practices for setup and management

### Step 7.3: FAQ Update

- N/A - Not required per project owner
- All user guidance covered in user guide and architecture documentation

---

## Decisions & Completion Check

### Critical Decisions ✅ RESOLVED

✅ **Decision 1: Uncheck Behavior** → **RESOLVED**: Unlink + rename with "\_unlinked" suffix

- Options flow calls reusable `_unlink_shadow_kid()` helper
- Kid preserved as regular kid with all data intact
- Checkbox description includes warning about automatic rename
- Code shared between service and options flow

✅ **Decision 2: Name Handling** → **RESOLVED**: REQUIRE name match

- Service validates kid name matches parent name (case-insensitive)
- If names don't match → validation error (no link)
- Simplifies API and ensures safety
- Clear error messages guide users

✅ **Decision 3: Unlink Name Conflict** → **RESOLVED**: Always auto-rename to "{name}\_unlinked"

- No user parameter needed
- Consistent behavior: unlink always appends "\_unlinked" suffix
- User can manually rename in UI later if desired
- Prevents duplicate name conflicts automatically

✅ **Decision 4: Service Parameters** → **RESOLVED**: 2 params only (name + action)

- `name` (required): Must match BOTH kid and parent
- `action` (required): "link" or "unlink"
- Workflow/gamification settings inherited from existing parent settings (not exposed in service)
- Simple, focused API

---

## Completion Checklist

**Before marking complete:**

### Decisions Resolved ✅

- [x] Decision 1 (Uncheck Behavior) → Unlink + rename helper
- [x] Decision 2 (Name Handling) → Require exact match
- [x] Decision 3 (Unlink Naming) → Always "\_unlinked" suffix
- [x] Decision 4 (Service Parameters) → name + action only

### Implementation Complete

- [ ] All Phase 1 constants added (SERVICE_MANAGE_SHADOW_LINK, FIELD_NAME, FIELD_ACTION, ACTION_LINK, ACTION_UNLINK)
- [ ] Phase 2 `_unlink_shadow_kid()` helper in coordinator.py
- [ ] Phase 3 `handle_manage_shadow_link()` service handler in services.py
- [ ] Phase 4 options flow updated to use `_unlink_shadow_kid()` helper
- [ ] Phase 5 service YAML definition in services.yaml
- [ ] Phase 6 test scenarios passing (7 manual + 8 automated)
- [ ] Phase 7 documentation updated (ARCHITECTURE.md, wiki, FAQ)

### Quality Gates

- [ ] `./utils/quick_lint.sh --fix` passes (9.5+/10)
- [ ] `mypy custom_components/kidschores/` zero errors
- [ ] `pytest tests/ -v` all tests pass
- [ ] No hardcoded strings (all use TRANS*KEY*\* constants)
- [ ] Service registered in `async_setup_services()`

### User Experience

- [ ] Service discoverable in Developer Tools
- [ ] Error messages clear and actionable
- [ ] Data preservation verified in all test scenarios
- [ ] Automatic "\_unlinked" suffix prevents name conflicts
- [ ] Checkbox warning visible in options flow UI

---

## References

| Document                                                              | Purpose                               |
| --------------------------------------------------------------------- | ------------------------------------- |
| [ARCHITECTURE.md](../ARCHITECTURE.md)                                 | Data model, shadow kid structure      |
| [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)               | Service patterns, naming conventions  |
| [coordinator.py](../../custom_components/kidschores/coordinator.py)   | Coordinator methods, data persistence |
| [services.py](../../custom_components/kidschores/services.py)         | Existing service patterns             |
| [options_flow.py](../../custom_components/kidschores/options_flow.py) | Current shadow kid lifecycle          |
| [flow_helpers.py](../../custom_components/kidschores/flow_helpers.py) | `build_shadow_kid_data()` reference   |

---

## Implementation Rationale

### Why Single Service (not separate link/unlink)?

- **Simplicity**: One service to learn, one YAML definition
- **Action pattern**: Standard HA pattern (like climate.set_hvac_mode with mode parameter)
- **Maintainability**: Single validation + permission check path

### Why Require Name Match?

- **Safety**: Prevents accidental linking of wrong profiles
- **Clarity**: Makes service intent explicit (parent="Sarah", kid="Sarah")
- **User validation**: Forces user to verify they have matching profiles

### Why Automatic "\_unlinked" Suffix?

- **No parameters**: Keeps service simple (2 params only)
- **Consistency**: Same behavior every time (predictable)
- **Conflict prevention**: Guarantees unique name after unlink
- **Manual override**: User can rename in UI later if desired

### Service vs Options Flow

**When to use service:**

- One-time linking of existing kid to parent
- Migration from workaround setup (parent + kid with same name)
- Batch operations (scripts/automations)

**When to use options flow:**

- Creating new shadow kid from scratch
- Standard parent setup workflow
- UI-guided configuration

---

## Risk Assessment

| Risk                         | Impact   | Mitigation                              |
| ---------------------------- | -------- | --------------------------------------- |
| Name mismatch confusion      | Medium   | Clear error messages + examples in docs |
| Data loss on uncheck         | Critical | ✅ Mitigated: preserve + rename helper  |
| "\_unlinked" suffix surprise | Low      | Checkbox warning + documentation        |
| Validation gaps              | Medium   | 7 manual + 8 automated test scenarios   |

---

**Status**: ✅ **PLANNING COMPLETE - READY FOR IMPLEMENTATION**
**Next Action**: Proceed to Phase 1 implementation (constants + translation keys)
