# Initiative: Immediate Reset on Late Approval (Overdue Handling Extension)

**Initiative Code**: OVERDUE-IMMEDIATE-RESET-2026-01
**Target Release**: v0.5.0 ✅ COMPLETE
**Owner**: Strategy / Implementation TBD
**Status**: Implementation Complete (2026-01-14)
**Created**: 2026-01-14

---

## Initiative Snapshot

| Attribute           | Value                                                                                  |
| ------------------- | -------------------------------------------------------------------------------------- |
| **Type**            | Enhancement / Feature Extension                                                        |
| **Scope**           | Rename existing option, change default, add new option, leverage UPON_COMPLETION logic |
| **Risk Level**      | Low-Medium (migration handles existing configs)                                        |
| **Breaking Change** | No (migration auto-converts old values)                                                |
| **Test Impact**     | Medium (focused testing on rename + new overdue option)                                |
| **User Impact**     | High (better defaults + solves universal late approval problem)                        |
| **Schema Impact**   | **Migration only** - no new fields, just rename value string                           |

---

## Problem Statement

### Universal Issue: Late Approvals Lose Time Windows

**CORE INSIGHT:** This is a **universal timing problem** affecting all chores when approval happens after the due date has passed, regardless of approval reset type (AT_MIDNIGHT or AT_DUE_DATE).

#### The Pattern Across Approval Reset Types

**All time-based reset types** have the same problem when approved after due date:

| Approval Reset Type | When Scheduled Reset Occurs | Late Approval Impact                                 |
| ------------------- | --------------------------- | ---------------------------------------------------- |
| `AT_MIDNIGHT_ONCE`  | Next midnight (00:00)       | Approved Wed 8AM → stays APPROVED until Thu midnight |
| `AT_MIDNIGHT_MULTI` | Next midnight               | **Wed entirely lost** for multi-claims               |
| `AT_DUE_DATE_ONCE`  | Next due date (varies)      | Stays APPROVED until next due date                   |
| `AT_DUE_DATE_MULTI` | Next due date               | **Time gap lost** for multi-claims                   |
| `UPON_COMPLETION`   | Immediate                   | ✅ No problem - resets immediately                   |

#### Current Behavior Problem

When a chore is approved **after its due date has passed**, it remains in APPROVED state until the next scheduled reset (controlled by `approval_reset_type`). This creates lost time windows:

#### Example Scenarios Across Reset Types

**Scenario 1: AT_MIDNIGHT_MULTI (Daily)**

- Chore due Tuesday 5PM, reset boundary = Wednesday 00:00
- **Approved Tuesday 6PM** (overdue but before midnight) → stays APPROVED until Wed midnight ✅
- **Approved Wednesday 8AM** (past reset boundary) → stays APPROVED until Thu midnight ❌
- **Result:** Wednesday entirely lost for multi-claims
- Approved Wednesday 8AM (after midnight boundary)
- **Stays APPROVED until Thursday midnight**
- **Wednesday 12:01 AM → 11:59 PM completely lost** for multi-claims

**Scenario 2: AT_DUE_DATE_MULTI (Every 3 Days)**

- Chore due Tuesday 5PM, next due Friday 5PM
- Approved Wednesday 8AM (after Tuesday 5PM boundary)
- **Stays APPROVED until Friday 5PM**
- **Wednesday 5PM → Friday 4:59 PM lost** (40+ hours)

**Scenario 3: AT_MIDNIGHT_ONCE (Daily)**

- Chore due Tuesday 5PM, reset = Wednesday 00:00
- Approved Wednesday 8AM
- Stays APPROVED until Thursday midnight
- Less critical (only one claim per day anyway)
  Design Decision:\*\* Approval logic separates "award points" from "reset chore state"

1. **Time-Based Reset Only** (coordinator.py lines 8679-8860):

   - `_reset_all_chore_counts()` runs at midnight via scheduler
   - AT_DUE_DATE checks happen during scheduled reset cycles
   - **NO approval-triggered reset** for time-based types

2. **Approval Logic Limitation** (coordinator.py lines 3100-3200):

   - Line 3120-3127: Only `UPON_COMPLETION` triggers immediate reschedule
   - AT*MIDNIGHT*_ and AT*DUE_DATE*_ have no immediate reset path
   - Assumption: Time-based reset will handle it "eventually"

3. **Missing Feature:** No configuration for late approval behavior
   - Current: One-size-fits-all (wait for scheduled reset)
   - Needed: Per-chore policy for what happens when approved late

| Reset Type            | Impact Severity | Time Window Lost    | Critical?  |
| --------------------- | --------------- | ------------------- | ---------- |
| **AT_MIDNIGHT_MULTI** | **CRITICAL**    | Up to 24 hours      | ✅ YES     |
| **AT_DUE_DATE_MULTI** | **HIGH**        | Varies by frequency | ✅ YES     |
| AT_MIDNIGHT_ONCE      | Low-Medium      | Up to 24 hours      | ⚠️ Depends |
| AT_DUE_DATE_ONCE      | Low             | Varies by frequency | ❌ No      |
| UPON_COMPLETION       | None            | N/A (immediate)     | N/A        |

### Root Cause

**Architectural:** Reset logic only runs at midnight (coordinator.py lines 8679-8860)

- `_reset_all_chore_counts()` triggered by time-based scheduler
- Checks chore states and advances due dates
- **NO immediate reset** when approval happens after overdue

**Approval Logic:** Does not trigger immediate reset for AT*MIDNIGHT*\* types (coordinator.py lines 3100-3200)

- Line 3120-3127: Only UPON_COMPLETION triggers immediate reschedule
- AT*MIDNIGHT*_ and AT*DUE_DATE*_ wait for scheduled reset

---

## User Impact Analysis

### Who Is Affected?

**Critical Impact Users:**

- **Any MULTI reset type** (AT_MIDNIGHT_MULTI, AT_DUE_DATE_MULTI)
- Families with late approval patterns (busy parents)
- Chores with frequent recurrence (daily, every 2 days)
- Kids earning points through volume (multiple completions)

**Medium Impact Users:**

- AT_MIDNIGHT_ONCE with daily frequency
- AT_DUE_DATE_ONCE with short frequency (every 2-3 days)
- Parents who sometimes approve morning-after

**Low Impact Users:**

- ONCE reset types with long frequency (weekly, monthly)
- Users with consistent on-time approval workflow
- UPON_COMPLETION chores (already immediate)

### Current Workarounds

❌ **None effective** - Users cannot force immediate reset

- Manual disapprove/re-claim loses points and history
- Waiting until Thursday midnight is only option

---

## Strategic Options

### Option A: Add New Field `approval_reset_late_behavior` (Original Plan)

**Behavior:** Add entirely new chore field to control late approval behavior

**Pros:**

- ✅ Explicit separation of concerns

**Cons:**

- ❌ New schema field + migration required
- ❌ Additional UI field (more complexity)
- ❌ Conceptual overlap with existing `overdue_handling_type`
- ❌ More configuration for users to understand

**Implementation Complexity:** Very High

- Schema v42 → v43 migration
- New constants, form fields, validation
- ~300+ lines of code

---

### Option B: Extend Existing `overdue_handling_type` (RECOMMENDED) ⭐

**Behavior:** Add new option to existing `overdue_handling_type` dropdown

**Current Options:**

- `never_overdue` - Never marks as overdue
- `at_due_date` - Goes overdue, stays until approved (current default)
- `at_due_date_then_reset` → **RENAME TO:** `at_due_date_clear_at_approval_reset`

**New Option:**

- `at_due_date_clear_immediate_on_late` - Goes overdue, resets immediately when approved

**How It Works:**

```python
# In approve_chore() after awarding points:
overdue_handling = chore_info.get(
    const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
    const.DEFAULT_OVERDUE_HANDLING_TYPE
)

# Treat as UPON_COMPLETION if the new overdue option is set
should_reschedule_immediately = (
    approval_reset_type == const.APPROVAL_RESET_UPON_COMPLETION
    or overdue_handling == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE
)

# Then use existing UPON_COMPLETION logic (lines 3123-3150)
if should_reschedule_immediately:
    if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
        self._reschedule_chore_next_due_date_for_kid(chore_info, chore_id, kid_id)
    elif all_kids_approved:  # SHARED
        self._reschedule_chore_next_due_date(chore_info)
```

**Pros:**

- ✅ **No schema migration** - field already exists
- ✅ **No new UI field** - just one more dropdown option
- ✅ **Conceptually correct** - overdue handling IS about what happens with late approval
- ✅ **Reuses proven logic** - UPON_COMPLETION already does exactly what we need
- ✅ **Dramatically simpler** - ~50 lines of code vs 300+
- ✅ **Easier to document** - extends familiar concept
- ✅ **Faster implementation** - no migration, no new form field

**Cons:**

- ❌ Name change for existing option (minor breaking change in YAML configs)
- ❌ Conceptually ties to "overdue" even though applies to all late approvals

**Implementation Complexity:** Low

- Rename existing constant
- Add one new constant
- Modify one conditional in `approve_chore()`
- ~6 new test scenarios

---

## Recommendation Matrix

| Option                            | User Impact       | Complexity | Risk    | Reuses Logic | Best For                                     |
| --------------------------------- | ----------------- | ---------- | ------- | ------------ | -------------------------------------------- |
| **A: New Field**                  | High Positive     | Very High  | Medium  | No           | Only if overdue_handling concept doesn't fit |
| **B: Extend overdue_handling** ⭐ | **High Positive** | **Low**    | **Low** | **Yes**      | **This initiative - perfect fit!**           |

---

## Recommended Approach: Option B (Extend `overdue_handling_type`)

### Why This Approach is Brilliant

**1. Conceptually Perfect**

- `overdue_handling_type` already controls "what happens when past due date"
- "What happens when approved while past due date" is a natural extension
- Users already understand this setting

**2. Zero Schema Impact**

- No migration needed
- No SCHEMA_VERSION increment
- Existing field accommodates new option

**3. Leverages Existing UPON_COMPLETION Logic**

- Lines 3123-3150: Already calls reschedule methods immediately
- Lines 9395-9408: Already resets to PENDING for UPON_COMPLETION
- **Just need one conditional check** to trigger same path

**4. Minimal Code Changes**

```python
# Existing code at line 3122-3127:
if (
    chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA) == const.COMPLETION_CRITERIA_INDEPENDENT
    and approval_reset_type == const.APPROVAL_RESET_UPON_COMPLETION
):
    self._reschedule_chore_next_due_date_for_kid(chore_info, chore_id, kid_id)

# NEW code (replace above):
should_reschedule = (
    approval_reset_type == const.APPROVAL_RESET_UPON_COMPLETION
    or overdue_handling == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE
)
if (
    chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA) == const.COMPLETION_CRITERIA_INDEPENDENT
    and should_reschedule
):
    self._reschedule_chore_next_due_date_for_kid(chore_info, chore_id, kid_id)
```

**5. Simple User Story**
_"When this chore is approved after its due date has passed, should it reset immediately or wait for the scheduled reset time?"_

### Naming Convention

**Updated Options:**
| Constant | Value | User-Facing Label |
|----------|-------|-------------------|
| `OVERDUE_HANDLING_NEVER_OVERDUE` | `never_overdue` | Never mark as overdue |
| `OVERDUE_HANDLING_AT_DUE_DATE` | `at_due_date` | Mark overdue at due date (default) |
| `OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET` | `at_due_date_clear_at_approval_reset` | Overdue clears at scheduled reset |
| **NEW** `OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE` | `at_due_date_clear_immediate_on_late` | Overdue clears immediately when approved |

### Phase-Based Implementation

#### Phase 1: Constants & Naming (20%)

**Goal:** Add new constant, update existing constant name

**Steps:**

- [x] Research current reset timing (completed)
- [x] Analyze universal problem (completed)
- [x] Identify UPON_COMPLETION logic reuse (completed)
- [ ] Add new constant to const.py (line ~1057):
  ```python
  # Overdue handling types (line ~1055)
  OVERDUE_HANDLING_AT_DUE_DATE: Final = "at_due_date"
  OVERDUE_HANDLING_NEVER_OVERDUE: Final = "never_overdue"
  OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET: Final = "at_due_date_clear_at_approval_reset"  # RENAMED
  OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE: Final = "at_due_date_clear_immediate_on_late"  # NEW
  ```
- [ ] Update OVERDUE_HANDLING_TYPE_OPTIONS (line ~1058):
  ```python
  OVERDUE_HANDLING_TYPE_OPTIONS: Final = [
      {"value": OVERDUE_HANDLING_AT_DUE_DATE, "label": "at_due_date"},
      {"value": OVERDUE_HANDLING_NEVER_OVERDUE, "label": "never_overdue"},
      {"value": OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET, "label": "at_due_date_clear_at_approval_reset"},
      {"value": OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE, "label": "at_due_date_clear_immediate_on_late"},
  ]
  ```
- [ ] Find and replace `OVERDUE_HANDLING_AT_DUE_DATE_THEN_RESET` → `OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET`
  - Search coordinator.py for usage
  - Update all references
- [ ] Add translation keys to translations/en.json:
  ```json
  {
    "selector": {
      "overdue_handling_type": {
        "options": {
          "at_due_date": "Mark overdue at due date",
          "never_overdue": "Never mark as overdue",
          "at_due_date_clear_at_approval_reset": "Clear overdue at next scheduled reset",
          "at_due_date_clear_immediate_on_late": "Clear overdue immediately when approved late"
        }
      }
    },
    "options": {
      "step": {
        "edit_chore": {
          "data": {
            "overdue_handling_type": "Overdue handling"
          },
          "data_description": {
            "overdue_handling_type": "Controls when chore is marked overdue and how it clears. 'Immediate on late' causes chore to reset right away when approved after due date (maximizes earning opportunities)."
          }
        }
      }
    }
  }
  ```
- [ ] Add tooltip/help text explaining "late approval":
  - "Late approval = approving after the due date has passed"
  - "With 'immediate on late', chore resets and can be claimed again right away"
  - "With 'scheduled reset', chore stays approved until next midnight/due date"

**Translation Keys Summary:**
| Key Path | Value | Purpose |
|----------|-------|----------|
| `selector.overdue_handling_type.options.at_due_date` | "Mark overdue at due date" | Default option label |
| `selector.overdue_handling_type.options.never_overdue` | "Never mark as overdue" | Never overdue label |
| `selector.overdue_handling_type.options.at_due_date_clear_at_approval_reset` | "Clear overdue at next scheduled reset" | Renamed existing option |
| `selector.overdue_handling_type.options.at_due_date_clear_immediate_on_late` | "Clear overdue immediately when approved late" | NEW option label |
| `options.step.edit_chore.data.overdue_handling_type` | "Overdue handling" | Field label |
| `options.step.edit_chore.data_description.overdue_handling_type` | Description text | Tooltip/help text |

**Key Files:**

- `const.py` lines ~1055-1066
- `coordinator.py` - search for old constant name
- `translations/en.json` - add all selector options and descriptions

**Issues/Blockers:**

- Verify no YAML config files use old constant value string
- Check if wiki documentation references old name

---

#### Phase 2: Core Logic (30%)

**Goal:** Modify `approve_chore()` to trigger UPON_COMPLETION path for new overdue option

**Steps:**

- [ ] Modify `approve_chore()` around line 3122-3127:

  ```python
  # OLD code:
  if (
      chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA) == const.COMPLETION_CRITERIA_INDEPENDENT
      and approval_reset_type == const.APPROVAL_RESET_UPON_COMPLETION
  ):
      self._reschedule_chore_next_due_date_for_kid(chore_info, chore_id, kid_id)

  # NEW code:
  overdue_handling = chore_info.get(
      const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
      const.DEFAULT_OVERDUE_HANDLING_TYPE
  )

  # Check if approval is after reset boundary
  is_late_approval = self._is_approval_after_reset_boundary(
      chore_info, kid_id, approval_reset_type
  )

  should_reschedule_immediately = (
      approval_reset_type == const.APPROVAL_RESET_UPON_COMPLETION
      or (overdue_handling == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE
          and is_late_approval)
  )

  if (
      chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA) == const.COMPLETION_CRITERIA_INDEPENDENT
      and should_reschedule_immediately
  ):
      self._reschedule_chore_next_due_date_for_kid(chore_info, chore_id, kid_id)
  ```

- [ ] Modify SHARED reschedule logic around line 3132-3150:

  ```python
  # OLD code:
  if (
      completion_criteria in (const.COMPLETION_CRITERIA_SHARED, const.COMPLETION_CRITERIA_SHARED_FIRST)
      and approval_reset_type == const.APPROVAL_RESET_UPON_COMPLETION
  ):
      # ... all_approved check ...
      if all_approved:
          self._reschedule_chore_next_due_date(chore_info)

  # NEW code (replace approval_reset_type check with should_reschedule_immediately):
  if (
      completion_criteria in (const.COMPLETION_CRITERIA_SHARED, const.COMPLETION_CRITERIA_SHARED_FIRST)
      and should_reschedule_immediately  # Use variable from above
  ):
      # ... all_approved check ...
      if all_approved:
          self._reschedule_chore_next_due_date(chore_info)
  ```

- [ ] Add helper method `_is_approval_after_reset_boundary()`:

  ```python
  def _is_approval_after_reset_boundary(
      self, chore_info: dict, kid_id: str, approval_reset_type: str
  ) -> bool:
      """Check if approval is after reset boundary passed."""
      now_utc = dt_util.utcnow()

      # AT_MIDNIGHT: Check if due date was before last midnight
      if approval_reset_type in (const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
                                const.APPROVAL_RESET_AT_MIDNIGHT_MULTI):
          last_midnight = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
          due_date = parse_datetime(chore_info.get(const.DATA_CHORE_DUE_DATE))
          return due_date and due_date < last_midnight

      # AT_DUE_DATE: Check if past next scheduled due date
      elif approval_reset_type in (const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
                                  const.APPROVAL_RESET_AT_DUE_DATE_MULTI):
          # Get appropriate due date (INDEPENDENT uses per-kid)
          if chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA) == const.COMPLETION_CRITERIA_INDEPENDENT:
              due_date = parse_datetime(
                  chore_info.get(const.DATA_CHORE_KID_STATUS, {}).get(kid_id, {}).get(const.DATA_CHORE_DUE_DATE)
              )
          else:
              due_date = parse_datetime(chore_info.get(const.DATA_CHORE_DUE_DATE))

          if due_date:
              next_reset_time = self._calculate_next_due_date_from(due_date, chore_info)
              return now_utc > next_reset_time

      return False
  ```

- [ ] Add debug logging:
  ```python
  if is_late_approval and overdue_handling == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE:
      const.LOGGER.debug(
          "Late approval (past reset boundary) - immediate reset for chore '%s', kid '%s'",
          chore_info[const.DATA_CHORE_NAME],
          kid_id
      )
  ```
- [ ] **That's it!** Existing `_reschedule_chore_next_due_date()` methods handle everything:
  - Reset state to PENDING (lines 9395-9408)
  - Calculate next due date
  - Handle SHARED vs INDEPENDENT
  - Preserve approval history

**Key Files:**

- `coordinator.py` lines 3120-3155 (approve_chore modifications)

**Issues/Blockers:**

- None - reusing existing proven logic!

---

#### Phase 4: Testing (30%)

**Goal:** Comprehensive validation matrix across all reset types and behaviors

**Test Matrix Structure:**

```
2 Behaviors (immediate, scheduled) ×
4 Reset Types (AT_MIDNIGHT_ONCE, AT_MIDNIGHT_MULTI, AT_DUE_DATE_ONCE, AT_DUE_DATE_MULTI) ×
2 Timing (late, on-time) =
16 core scenarios
```

**Core Test Scenarios:**

- [ ] **Test Group 1: AT_MIDNIGHT_MULTI with immediate behavior**

  - Scenario 1a: Late approval (Wed 8AM after Tue 5PM due) → immediate reset
  - Scenario 1b: On-time approval (Tue 4PM) → scheduled reset (normal)
  - Scenario 1c: Multi-claim verification after late approval → can claim again

- [ ] **Test Group 2: AT_MIDNIGHT_MULTI with scheduled behavior (default)**

  - Scenario 2a: Late approval → waits for midnight (current behavior preserved)
  - Scenario 2b: Verify lost time window (cannot claim until next midnight)

- [ ] **Test Group 3: AT_MIDNIGHT_ONCE with immediate behavior**

  - Scenario 3a: Late approval → immediate reset
  - Scenario 3b: Verify single claim limit still enforced

- [ ] **Test Group 4: AT_MIDNIGHT_ONCE with scheduled behavior (default)**

  - Scenario 4a: Late approval → waits for midnight (current behavior)

- [ ] **Test Group 5: AT_DUE_DATE_MULTI with immediate behavior**

  - Scenario 5a: Late approval (Wed 8AM after Tue 5PM due) → immediate reset
  - Scenario 5b: Next due date calculated correctly (respects frequency)
  - Scenario 5c: Multi-claim after immediate reset works

- [ ] **Test Group 6: AT_DUE_DATE_MULTI with scheduled behavior (default)**

  - Scenario 6a: Late approval → waits for next scheduled due date
  - Scenario 6b: Verify time gap lost

- [ ] **Test Group 7: AT_DUE_DATE_ONCE behaviors**

  - Similar to Group 5/6 but single claim

- [ ] **Test Group 8: Edge Cases**
  - Scenari5: Documentation & UI Polish (5%)
    **Goal:** Document new feature, update UI strings, finalize release materials

**Steps:**

- [ ] Update ARCHITECTURE.md:
  - Document `approval_reset_late_behavior` field
  - Add to chore data structure section
  - Explain reset period boundary concept
- [ ] Update wiki: Chore-Status-and-Recurrence-Handling.md
  - Add new section: "Late Approval Reset Behavior"
  - Explain when approval is considered "late"
  - Show examples with `immediate` vs `scheduled`
  - Update all Use Case tables with late approval rows
- [ ] Create wiki page: Chore-Configuration-Guide.md update
  - Add late approval behavior to chore configuration section
  - Provide decision guide: "When should I use immediate?"
  - Examples: dishes (immediate), weekly allowance (scheduled)
- [ ] Update translations/en.json:
  - UI labels for setting options
  - Tooltip/description text
  - Error messages (if any)
  - Entity state attributes (if shown in UI)
- [ ] Add tooltips in config flow:
  ```
  "When approved after reset period passes:
   • Immediate: Reset right away (good for multi-completion chores)
   • Scheduled: Wait for next reset (current behavior)"
  ```
- [ ] Add release notes entry:

  ```
  🎉 New Feature: Late Approval Reset Behavior

  Configure what happens when a chore is approved after its reset period has passed:
  - `immediate`: Reset immediately (maximize earning opportunities)
  - `scheduled`: Wait for next scheduled reset (default, current behavior)

  Benefits:
  • Solves lost time window problem for multi-completion chores
  • Applies to ALL reset types (AT_MIDNIGHT and AT_DUE_DATE)
  • Per-chore configuration for flexible workflows
  • Safe default preserves existing behavior

  Migration: Existing chores default to `scheduled` (no behavior change)
  ```

- [ ] Review all code comments for clarity

**Key Files:**

- `docs/ARCHITECTURE.md`
- `kidschores-ha.wiki/Chore-Status-and-Recurrence-Handling.md`
- `kidschores-ha.wiki/Chore-Configuration-Guide.md`
- `translations/en.json`
- `custom_components/kidschores/strings.json`
- Release notes file

**Issues/Blockers:**

- Crowdin sync for translation keys
- Wiki formatting for co, Design & Schema | 25% | Schema v43, constants, edge case analysis |
  | **Phase 2** | Schema Migration & Constants | 15% | Migration function, form schema, defaults |
  | **Phase 3** | Core Implementation | 25% | Detection logic, immediate reset, boundaries |
  | **Phase 4** | Testing | 30% | 16+ scenarios, all reset types, migration test |
  | **Phase 5** | Documentation & UI Polish | 5% | Wiki, tooltips, release notes, translation

#### Phase 4: Documentation & Polish (10%)

**Goal:** Update docs to reflect new behavior

**Steps:**

- [ ] Update wiki: Chore-Status-and-Recurrence-Handling.md
  - Add section explaining smart reset behavior
  - Update "Use Case 4" table for late approvals
  - Add examples showing multi vs once behavior
- [ ] Update ARCHITECTURE.md if reset timing section exists
- [ ] Add release notes entry:
  ```
  Enhancement: Late approval smart reset
  - AT_MIDNIGHT_MULTI chores now reset immediately when approved after due date
  - Maximizes earning opportunities for multi-completion chores
  - AT_MIDNIGHT_ONCE maintains existing behavior (reset at midnight)
  - No configuration needed - works automatically
  ```
- [ ] Review inline code comments in coordinator.py

**Key Files:**

- `kidschores-ha.wiki/Chore-Status-and-Recurrence-Handling.md`
- `docs/ARCHITECTURE.md` (if applicable)
- Release notes file

---

## 🔍 CRITICAL GAP ANALYSIS

### Issue #1: Reschedule Methods Check `approval_reset_type`, NOT `overdue_handling_type`

**Current Code (lines 9393-9405):**

```python
# In _reschedule_chore_next_due_date() (SHARED)
approval_reset = chore_info.get(const.DATA_CHORE_APPROVAL_RESET_TYPE, ...)
if approval_reset == const.APPROVAL_RESET_UPON_COMPLETION:
    for kid_id in chore_info.get(const.DATA_CHORE_ASSIGNED_KIDS, []):
        self._process_chore_state(kid_id, chore_id, const.CHORE_STATE_PENDING, ...)
```

**Problem:** The reschedule methods only reset state to PENDING if `approval_reset_type == UPON_COMPLETION`. Our new option is in `overdue_handling_type`, but the reschedule methods don't check it!

**Solution Options:**

1. **Option A:** Modify `_reschedule_chore_next_due_date()` and `_reschedule_chore_next_due_date_for_kid()` to ALSO check overdue_handling_type
2. **Option B:** Pass a flag to indicate "force reset to pending"
3. **Option C:** Call `_process_chore_state()` directly in `approve_chore()` before calling reschedule

**Recommendation:** Option A - modify the two reschedule methods

---

### Issue #2: We Need TWO Code Changes, Not Just One

**Change Location 1:** `approve_chore()` (lines ~3120-3155)

- Add `is_late_approval` check
- Modify condition to trigger reschedule for new overdue option

**Change Location 2:** `_reschedule_chore_next_due_date()` (lines ~9393-9405)

- Modify condition to reset state to PENDING for new overdue option
- Currently: `if approval_reset == UPON_COMPLETION`
- Needed: `if approval_reset == UPON_COMPLETION or (overdue_handling == CLEAR_IMMEDIATE_ON_LATE and is_late)`

**Change Location 3:** `_reschedule_chore_next_due_date_for_kid()` (lines ~9505-9515)

- Same modification as Location 2

---

### Issue #3: How Does `is_late_approval` Get Passed to Reschedule Methods?

**Problem:** The reschedule methods don't currently know if this is a "late" approval. They just reschedule.

**Options:**

1. **Option A:** Add `is_late: bool = False` parameter to reschedule methods
2. **Option B:** Re-calculate `is_late` inside reschedule methods (duplicate logic)
3. **Option C:** Always reset to PENDING when `overdue_handling == CLEAR_IMMEDIATE_ON_LATE` (simpler but may reset on-time approvals too)

**Recommendation:** Option C is simplest - if user chooses "immediate on late", they WANT immediate reset behavior. The "late" check is only needed to decide WHETHER to call reschedule, not inside reschedule.

**Corrected Logic:**

```python
# In approve_chore()
is_late = _is_approval_after_reset_boundary(...)
should_reschedule = (
    approval_reset_type == UPON_COMPLETION
    or (overdue_handling == CLEAR_IMMEDIATE_ON_LATE and is_late)  # Only trigger if late
)

# In _reschedule_chore_next_due_date()
# If we're being called, always reset to PENDING
# (The caller decided we should reschedule)
should_reset_state = (
    approval_reset == UPON_COMPLETION
    or overdue_handling == CLEAR_IMMEDIATE_ON_LATE  # If this option, always reset state
)
```

---

### Issue #4: ~~Existing `at_due_date_then_reset` Is NOT Being Renamed~~ **RESOLVED**

**Original concern:** Renaming is a breaking change for existing configs.

**UPDATED Decision:** We WILL rename with proper migration:

- Rename constant: `OVERDUE_HANDLING_AT_DUE_DATE_THEN_RESET` → `OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET`
- Rename value: `"at_due_date_then_reset"` → `"at_due_date_clear_at_approval_reset"`
- Add migration to convert old values in storage
- Test suite validates no regressions before proceeding

**Why rename?**

- Consistent naming scheme with new option (`clear_at_approval_reset` vs `clear_immediate_on_late`)
- Better describes actual behavior
- Clean slate for documentation
- Migration handles existing configs automatically

---

### Issue #5: ~~Value String in Storage~~ **RESOLVED**

**Original concern:** Users with existing `"at_due_date_then_reset"` in storage will have broken configs.

**UPDATED Solution:** Add migration in `_migrate_data()`:

```python
# Migrate old overdue_handling value to new name
for chore in chores:
    if chore.get(const.DATA_CHORE_OVERDUE_HANDLING_TYPE) == "at_due_date_then_reset":
        chore[const.DATA_CHORE_OVERDUE_HANDLING_TYPE] = "at_due_date_clear_at_approval_reset"
```

This runs automatically on startup, converting any existing chores with the old value.

---

### Issue #6: Default Should Change (NEW)

**Current default:** `at_due_date` (mark overdue but don't clear until approved)

**NEW default:** `at_due_date_clear_at_approval_reset`

**Rationale:**

- Better user experience: overdue clears automatically at scheduled reset
- More forgiving for missed chores
- Fresh start each cycle without manual intervention
- Aligns with "clear" naming convention

**Implementation:** Change `DEFAULT_OVERDUE_HANDLING_TYPE` in Phase 1 after rename validated.

---

## ✅ CLEAN IMPLEMENTATION CHECKLIST

---

### Phase 0: Rename Existing Constant (FIRST - WITH MIGRATION) ✅ COMPLETE

**Objective:** Rename `at_due_date_then_reset` → `at_due_date_clear_at_approval_reset` with full storage migration

**File:** `custom_components/kidschores/const.py`

- [x] **Line ~1057:** Rename constant name AND value string

  ```python
  # OLD:
  OVERDUE_HANDLING_AT_DUE_DATE_THEN_RESET: Final = "at_due_date_then_reset"

  # NEW:
  OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET: Final = "at_due_date_clear_at_approval_reset"
  ```

- [x] **Line ~1058-1065:** Update options list
  ```python
  OVERDUE_HANDLING_TYPE_OPTIONS: Final = [
      {"value": OVERDUE_HANDLING_AT_DUE_DATE, "label": "at_due_date"},
      {"value": OVERDUE_HANDLING_NEVER_OVERDUE, "label": "never_overdue"},
      {"value": OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET, "label": "at_due_date_clear_at_approval_reset"},  # RENAMED
  ]
  ```

**File:** `custom_components/kidschores/coordinator.py`

- [x] **Global search-replace:** Updated all usages of old constant name
  - Lines 8938, 9043: Reset logic updated

**File:** `custom_components/kidschores/flow_helpers.py`

- [x] **Line ~1208:** Updated validation check for renamed constant

**File:** `custom_components/kidschores/migration_pre_v50.py`

- [x] **Lines ~1700-1715:** Added migration logic to convert old value strings
  ```python
  # Migrate old overdue_handling value to new name
  if chore_data.get(const.DATA_CHORE_OVERDUE_HANDLING_TYPE) == "at_due_date_then_reset":
      chore_data[const.DATA_CHORE_OVERDUE_HANDLING_TYPE] = const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET
  ```

**File:** `custom_components/kidschores/translations/en.json`

- [x] Updated selector option label at line ~1503

**File:** Test helpers and scenarios

- [x] `tests/helpers/constants.py` - Updated import
- [x] `tests/helpers/__init__.py` - Updated import and **all**
- [x] `tests/test_chore_scheduling.py` - Updated references (4 locations)
- [x] `tests/test_approval_reset_overdue_interaction.py` - Updated references (4 locations)
- [x] `tests/scenarios/scenario_approval_reset_overdue.yaml` - Updated all references
- [x] `tests/scenarios/scenario_scheduling.yaml` - Updated all references

**Validation:**

```bash
# Search for ANY remaining old references
grep -r "at_due_date_then_reset" custom_components/kidschores/
# Result: ZERO matches ✅

grep -r "AT_DUE_DATE_THEN_RESET" custom_components/kidschores/
# Result: ZERO matches ✅
```

---

### Phase 0.5: Regression Tests for Rename ✅ COMPLETE

**Objective:** Run full test suite to confirm rename didn't break existing functionality

**Commands:**

```bash
# Run all tests
python -m pytest tests/ -v --tb=line
```

**Result:** 640 passed, 2 deselected in 76.82s ✅
**MyPy:** Success: no issues found in 20 source files ✅
**Lint:** Passed (unrelated warning about unused variable in test file)

---

### Phase 1: Make Renamed Option the New Default ✅ COMPLETE

**Objective:** Change default overdue handling from `at_due_date` to `at_due_date_clear_at_approval_reset`

**File:** `custom_components/kidschores/const.py`

- [x] **Line ~1068:** Updated default constant
  ```python
  DEFAULT_OVERDUE_HANDLING_TYPE: Final = OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET
  ```

**File:** `custom_components/kidschores/flow_helpers.py`

- [x] **Lines 1208-1215:** Updated validation to allow `UPON_COMPLETION` with new default
  - `UPON_COMPLETION` provides immediate reset so clearing at approval reset is valid behavior
  - Validation now accepts: `AT_MIDNIGHT_ONCE`, `AT_MIDNIGHT_MULTI`, `UPON_COMPLETION`

**File:** `tests/test_frequency_validation.py`

- [x] Updated 4 tests to explicitly set `OVERDUE_HANDLING_AT_DUE_DATE` when using `AT_DUE_DATE_*` reset types:
  - `test_at_due_date_once_without_due_date_single_shared_any_rejected`
  - `test_at_due_date_once_with_due_date_single_shared_any_accepted`
  - `test_at_due_date_multi_without_due_date_rejected`
  - `test_independent_multi_kid_at_due_date_once_without_due_date_allowed`

**File:** `tests/test_approval_reset_overdue_interaction.py`

- [x] Renamed `test_upon_completion_with_then_reset_rejected` → `test_upon_completion_with_clear_at_approval_reset_accepted`
  - Test now validates that `UPON_COMPLETION + AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET` is accepted (not rejected)

**Validation:** ✅

```bash
./utils/quick_lint.sh --fix    # Passed
python -m pytest tests/ -v --tb=line  # 640 passed
```

---

### Phase 2: Add New Constant for Immediate-On-Late ✅ COMPLETE

**File:** `custom_components/kidschores/const.py`

- [x] **Line ~1059:** Added new constant

  ```python
  OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE: Final = (
      "at_due_date_clear_immediate_on_late"
  )
  ```

- [x] **Line ~1064:** Added to options list
  ```python
  {
      "value": OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE,
      "label": "at_due_date_clear_immediate_on_late",
  },
  ```

**File:** `custom_components/kidschores/translations/en.json`

- [x] **Line ~1503:** Added selector option label:
  ```json
  "at_due_date_clear_immediate_on_late": "Immediate Reset on Late Approval"
  ```

**Validation:** ✅

```bash
./utils/quick_lint.sh --fix    # Passed
python -m pytest tests/ -v --tb=line  # 640 passed
```

---

### Phase 3: Core Logic (coordinator.py) ✅ COMPLETE

**File:** `custom_components/kidschores/coordinator.py`

#### Change 1: Added Helper Method `_is_approval_after_reset_boundary()` ✅

- Location: After `_reschedule_chore_next_due_date_for_kid()` (~line 9530)
- Checks if approval is happening after the reset boundary (late approval)
- For AT_MIDNIGHT types: Due date must be before last midnight
- For AT_DUE_DATE types: Current time must be past the due date

#### Change 2 & 3: Modified `approve_chore()` ✅

- Added `overdue_handling` lookup
- Added `is_late_approval` check using new helper
- Added `should_reschedule_immediately` variable that triggers for:
  - `UPON_COMPLETION` reset type (existing behavior)
  - `immediate_on_late` overdue handling + late approval (new behavior)
- Updated both INDEPENDENT and SHARED reschedule checks

#### Change 4: Modified `_reschedule_chore_next_due_date()` ✅

- Added `overdue_handling` lookup
- Added `should_reset_state` to reset for `UPON_COMPLETION` OR `immediate_on_late`

#### Change 5: Modified `_reschedule_chore_next_due_date_for_kid()` ✅

- Added `overdue_handling` lookup
- Added `should_reset_state` to reset for `UPON_COMPLETION` OR `immediate_on_late`

**Validation:** ✅

```bash
./utils/quick_lint.sh --fix    # Passed
python -m pytest tests/ -v --tb=line  # 640 passed
mypy custom_components/kidschores/  # Zero errors
```

---

### Phase 4: Translations (translations/en.json) ✅ COMPLETE (Done in Phase 2)

### Phase 5: Testing ✅ COMPLETE

**File:** `tests/test_overdue_immediate_reset.py` (NEW - 684 lines)

**Test Scenarios:**

1. [x] AT_MIDNIGHT_MULTI + new option: approve Wed 8AM (after midnight boundary) → immediate reset
2. [x] AT_MIDNIGHT_MULTI + new option: approve Tue 6PM (before midnight boundary) → normal behavior
3. [x] AT_DUE_DATE_MULTI + new option: approve after due date → immediate reset
4. [x] INDEPENDENT multi-kid: each kid resets independently on late approval
5. [x] SHARED multi-kid: resets when all kids approve late
6. [x] Regression: existing options unchanged (at_due_date, never_overdue, at_due_date_clear_at_approval_reset)
7. [x] Helper method unit tests: `_is_approval_after_reset_boundary()` boundary conditions

**Test File Created:** `tests/test_overdue_immediate_reset.py`

- 11 test methods across 6 test classes
- Uses existing scenarios: `scenario_approval_reset_overdue.yaml`, `scenario_shared.yaml`
- All 651 tests pass (640 existing + 11 new)

---

## 📋 FINAL IMPLEMENTATION SUMMARY

| Phase              | Component                       | Changes                                                                 | Lines Affected          |
| ------------------ | ------------------------------- | ----------------------------------------------------------------------- | ----------------------- |
| **0 - Rename**     | const.py                        | Rename `AT_DUE_DATE_THEN_RESET` → `AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET` | ~1057-1065              |
| **0 - Rename**     | coordinator.py                  | Global search-replace constant name (~8 occurrences)                    | ~8462, 8499, 8931, 9036 |
| **0 - Rename**     | coordinator.py                  | Add migration for old value string                                      | `_migrate_data()`       |
| **0.5 - Validate** | tests/                          | Run full test suite to confirm rename                                   | All tests               |
| **1 - Default**    | const.py                        | Change `DEFAULT_OVERDUE_HANDLING_TYPE`                                  | ~1066                   |
| **2 - New Const**  | const.py                        | Add `AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE`                               | ~1059                   |
| **3 - Logic**      | coordinator.py                  | Add `_is_approval_after_reset_boundary()`                               | ~9530 (new)             |
| **3 - Logic**      | coordinator.py                  | Modify `approve_chore()` - late check + condition                       | ~3120-3155              |
| **3 - Logic**      | coordinator.py                  | Modify `_reschedule_chore_next_due_date()`                              | ~9393-9405              |
| **3 - Logic**      | coordinator.py                  | Modify `_reschedule_chore_next_due_date_for_kid()`                      | ~9505-9515              |
| **4 - Trans**      | translations/en.json            | Add all 4 option labels                                                 | selector section        |
| **5 - Tests**      | test_overdue_immediate_reset.py | 10 test scenarios                                                       | new file                |

**Total estimated lines of code change:** ~120 lines (including rename migration)

**Key Decisions Made:**

1. ✅ RENAME existing `at_due_date_then_reset` → `at_due_date_clear_at_approval_reset` (with migration)
2. ✅ Make renamed option the NEW DEFAULT for overdue handling
3. ✅ ADD new constant `at_due_date_clear_immediate_on_late` for immediate reset
4. ✅ Late check happens in `approve_chore()`, not in reschedule methods
5. ✅ Reschedule methods check `overdue_handling_type` to decide state reset
6. ✅ Works with ALL frequencies including `daily_multi`
7. ✅ Run tests after each phase to catch regressions early

---

## Summary Table

| Phase       | Description         | Completion | Quick Notes                                |
| ----------- | ------------------- | ---------- | ------------------------------------------ |
| **Phase 0** | Rename + Migration  | 100% ✅    | Renamed option, migration v49→v50          |
| **Phase 1** | Change Default      | 100% ✅    | New default: clear_at_approval_reset       |
| **Phase 2** | Add New Option      | 100% ✅    | Added: clear_immediate_on_late option      |
| **Phase 3** | Core Implementation | 100% ✅    | Smart reset helper, modify approve_chore() |
| **Phase 4** | Translations        | 100% ✅    | UI labels added to en.json                 |
| **Phase 5** | Testing             | 100% ✅    | 11 comprehensive tests, 651 total passing  |

---

## Alternative Approaches Considered

##**Too aggressive** for some workflows

- Breaking change for users expecting scheduled behavior
- No flexibility - one size doesn't fit all families
- Example: Weekly allowance chore shouldn't reset immediately

### Why Not Option D (Smart Auto-Detection)?

- **Assumes MULTI = immediate** (may not be true for all families)
- ONCE users who want immediate have no option
- Less flexible than configurable approach
- "Magic behavior" harder to troubleshoot

### Why Not Keep Option B (Status Quo)?

- **Critical problem remains** - lost time windows
- Poor user experience for multi-completion workflows
- No workaround available
- Competitive disadvantage
- Competitors handle this better

---

- **REQUIRED:** Increment SCHEMA_VERSION from v42 → v43
- New field: `DATA_CHORE_APPROVAL_RESET_LATE_BEHAVIOR`
- Default value: `APPROVAL_RESET_LATE_SCHEDULED` (preserves current behavior)
- Migration: All existing chores get default applied

**New Constants Required:**

- `APPROVAL_RESET_LATE_IMMEDIATE: Final = "immediate"`
- `APPROVAL_RESET_LATE_SCHEDULED: Final = "scheduled"`
- `DEFAULT_APPROVAL_RESETAdd/Modify:\*\*

1. `approve_chore()` - add late approval detection and conditional reset
2. **New:** `_is_approved_after_reset_period()` - detection helper
3. **New:** `_is_past_midnight_boundary()` - AT_MIDNIGHT boundary check
4. **New:** `_is_past_due_date_boundary()` - AT_DUE_DATE boundary check
5. **New:** `_process_immediate_late_reset()` - reset + reschedule logic
6. **New:** `_migrate_to_v43()` - schema migration
7. Verify: `_reschedule_chore_next_due_date_for_kid()` - handles immediate call correctly

**Flow Helpers to Modify:**

1. `build_chore_schema()` - add late behavior field
2. `build_chores_data()` - include field in chore creation
3. Validation: Ensure field only matters for time-based reset types

- Translation keys: labels, tooltips, description
  **New Constants Required:**
- Possibly new translation keys for notifications about immediate reset
- Debug logging constants

**Coordinator Methods to Modify:**

1. `approve_chore()` - add smart reset logic
2. New: `_should_reset_immediately_on_late_approval()`
3. Possibly: `\_re & Decision Points

### 1. Reset Period Boundary Definition (NEEDS DECISION)

**Question:** For AT_MIDNIGHT types, when is the reset period boundary?

- **Option A:** Last midnight (00:00)
- **Option B:** Due date time (e.g., 5PM), but reset happens at next midnight
- **Recommendation:** **Option B** - aligns with overdue logic

**Question:** For AT_DUE_DATE types, when is the reset period boundary?

- **Answer:** Due date time exactly (e.g., Tuesday 5:00:00 PM)

### 2. Boundary Edge Cases (NEEDS DECISION)

**Scenario:** Chore due Tuesday 5PM, approved exactly at 5:00:00 PM

- **Is this "late"?** No - treat as on-time (inclusive boundary)
- **Implementation:** Use `now_utc > boundary` (strictly greater than)

**Scenario:** Chore approved at 11:59:59 PM (1 second before midnight)

- **Is this "late" for AT_MIDNIGHT?** Depends on when reset ran
- **Implementation:** Compare to last midnight, not next midnight

### 3. SHARED Multi-Kid Coordination (NEEDS DECISION)

**Scenario:** SHARED chore, 2 kids, both approve late with immediate behavior

- **Question:** Does first kid's immediate reset affect second kid?
- **Option A:** Yes - reset happens immediately, second kid starts fresh cycle
- **Option B:** No - each kid tracks separately (like INDEPENDENT)
- **Recommendation:** **Option A** - SHARED means shared state

### 4. INDEPENDENT Per-Kid Boundaries (NEEDS DECISION)

**Scenario:** INDEPENDENT chore, 2 kids, different due dates

- Kid A: Due Monday 5PM
- Kid B: Due Tuesday 5PM
- Both approve Wednesday 8AM with immediate behavior
- **Question:** Each kid has own boundary?
- **Answer:** YES - INDEPENDENT means separate due dates, separate boundaries

### 5. Notification Behavior (NEEDS DECISION)

**Question:** Should immediate reset trigger notification to kid?

- **Option A:** Yes - "Chore reset, ready to claim again!"
- **Option B:** No - silent reset (consistent with scheduled resets)
- **Recommendation:** **Option B** - keep silent for consistency
- **Future:** Could be separate setting later

### 6. Applicable Days Interaction (DESIGN REQUIRED)

**Scenario:** Chore can only be done M/W/F, late approval on Tuesday

- With immediate behavior, should next due date be:
  - **Option A:** Wednesday (next valid day)
  - **Option B:** Friday (skip one cycle)
- **Recommendation:** **Option A** - next valid applicable day
- **Implementation:** Use existing applicable day logic

### 7. UI Default Value (NEEDS DECISION)

**Question:** What should default be in chore creation UI?

- **Option A:** `scheduled` (safest, current behavior)
- **Option B:** `immediate` (maximize opportunities)
- **Option C:** Smart pre-selection (MULTI → immediate, ONCE → scheduled)
- **Recommendation:** **Option A** - conservative default, users opt-in

### 8. Interaction with overdue_handling_type (VERIFY)

**Question:** Does `overdue_handling_type` affect late approval logic?

- **AT_DUE_DATE:** Goes overdue, keeps state until reset
- **AT_DUE_DATE_THEN_RESET:** Goes overdue, clears at next reset
- **Late approval with immediate:** Should it respect overdue_handling?
- **Answer:** NO - late approval behavior is orthogonal to overdue handling

### 9. UPON_COMPLETION Handling (VERIFY)

**Question:** Should late behavior setting apply to UPON_COMPLETION?

- **Answer:** NO - UPON_COMPLETION always resets immediately
- **Implementation:** Ignore setting, keep existing behavior
- **UI:** Gray out or hide setting when UPON_COMPLETION selected?d separate)

4. **Applicable days interaction:** If chore can only be done M/W/F?

   - Late approval on Tuesday (overdue from Monday)
   - Should reset to Wednesday or Friday?
   - **Recommendation:** Next valid applicable day

5. **Custom frequency handling:** What if custom schedule has long gaps?
   - Example: Every 3 days
   - Late approval should follow custom schedule logic

---

## Success Criteria

**Functional:**

- [ ] AT_MIDNIGHT_MULTI chores reset immediately when approved late
- [ ] AT_MIDNIGHT_ONCE chores maintain current behavior
- [ ] No regression in on-time approval flow
- [ ] INDEPENDENT per-kid due dates work correctly
- [ ] Points and history preserved across reset
      (modify)
- `coordinator.py` lines 8679-8860: `_reset_all_chore_counts()` (reference for boundary logic)
- `coordinator.py` lines 8860-9100: `_reset_daily_chore_statuses()` (reference)
- `const.py` lines 1039-1051: Approval reset type constants
- `const.py` line 2565: SCHEMA_VERSION (increment to 43)
- `flow_helpers.py` lines 1000-1100: Chore creation schema (add field)
- `translations/en.json`: Add UI strings for new setting

---

## Implementation Checklist

**Before Starting:**

- [x] Review and approve Option C (Configurable) approach
- [x] Resolve all open questions (especially boundary definitions)
- [x] Confirm UI placement for new setting
- [x] Verify no conflicts with other in-progress features

**Phase Gates:**

- [x] Phase 0 Complete: Constant renamed with migration, default changed
- [x] Phase 0.5 Complete: Full test suite validated rename
- [x] Phase 1 Complete: Default changed to renamed option
- [x] Phase 2 Complete: New constant added to options list
- [x] Phase 3 Complete: Core logic implemented in approve_chore + reschedule methods
- [x] Phase 4 Complete: Translations added (done in Phase 2)
- [x] Phase 5 Complete: 11 new tests created, all 651 tests pass

**Final Sign-Off:**

- [x] Quick lint passes (./utils/quick_lint.sh --fix) ✅
- [x] MyPy zero errors ✅
- [x] Full test suite passes (651 tests) ✅
- [ ] Manual testing with multiple reset types
- [ ] Documentation reviewed
- [ ] Ready for user testing / beta release

---

---

## Technical Implementation: Variable Flow

### How Overdue Handling Works (All Chore Types)

**Key Variables:**

```python
# From chore configuration
overdue_handling_type = chore_info.get(
    const.DATA_CHORE_OVERDUE_HANDLING_TYPE,  # Field key
    const.DEFAULT_OVERDUE_HANDLING_TYPE       # Default: "at_due_date"
)

approval_reset_type = chore_info.get(
    const.DATA_CHORE_APPROVAL_RESET_TYPE,     # Field key
    const.DEFAULT_APPROVAL_RESET_TYPE         # Default varies
)

due_date = chore_info.get(const.DATA_CHORE_DUE_DATE)  # ISO string or None
```

**The Four Options (Constant Values):**

```python
const.OVERDUE_HANDLING_AT_DUE_DATE                          = "at_due_date"
const.OVERDUE_HANDLING_NEVER_OVERDUE                        = "never_overdue"
const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET = "at_due_date_clear_at_approval_reset"
const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE = "at_due_date_clear_immediate_on_late"  # NEW
```

---

### Option 1: `at_due_date` (Default Behavior)

**Constant:** `const.OVERDUE_HANDLING_AT_DUE_DATE`

**Logic Flow:**

```python
# During coordinator update cycle
if due_date and now_utc > due_date:
    chore_state = "overdue"  # Turn red
    # Stays overdue until approved

# During approval
def approve_chore(chore_id, kid_id):
    # Award points
    _award_points(kid_id, chore_points)

    # Set state to approved
    chore_info[const.DATA_CHORE_KID_STATUS][kid_id] = const.STATUS_APPROVED

    # Does NOT reset immediately
    # Waits for scheduled reset (controlled by approval_reset_type)

# During scheduled reset (midnight or due date)
def _reset_chores():
    if approval_reset_type == const.APPROVAL_RESET_AT_MIDNIGHT_ONCE:
        # Reset at next midnight
        chore_state = const.STATUS_PENDING
    elif approval_reset_type == const.APPROVAL_RESET_AT_DUE_DATE_ONCE:
        # Reset at next due date
        chore_state = const.STATUS_PENDING
        due_date = calculate_next_due_date()
    # etc.
```

**Works with ALL approval_reset_type values:**

- ✅ `AT_MIDNIGHT_ONCE` - Resets at midnight
- ✅ `AT_MIDNIGHT_MULTI` - Resets at midnight, allows multiple claims
- ✅ `AT_DUE_DATE_ONCE` - Resets at next due date
- ✅ `AT_DUE_DATE_MULTI` - Resets at next due date, allows multiple claims
- ✅ `UPON_COMPLETION` - Resets immediately (overdue handling N/A)

---

### Option 2: `never_overdue` (Flexible Timing)

**Constant:** `const.OVERDUE_HANDLING_NEVER_OVERDUE`

**Logic Flow:**

```python
# During coordinator update cycle
if overdue_handling_type == const.OVERDUE_HANDLING_NEVER_OVERDUE:
    # NEVER set chore_state to "overdue" even if past due date
    chore_state = const.STATUS_PENDING  # Stays pending

# During approval (same as Option 1)
def approve_chore(chore_id, kid_id):
    _award_points(kid_id, chore_points)
    chore_info[const.DATA_CHORE_KID_STATUS][kid_id] = const.STATUS_APPROVED
    # Waits for scheduled reset

# During scheduled reset (same as Option 1)
def _reset_chores():
    # Follows normal reset logic based on approval_reset_type
    chore_state = const.STATUS_PENDING
    due_date = calculate_next_due_date()
```

**Works with ALL approval_reset_type values:**

- ✅ `AT_MIDNIGHT_ONCE/MULTI` - Never goes overdue, resets at midnight
- ✅ `AT_DUE_DATE_ONCE/MULTI` - Never goes overdue, resets at next due date
- ✅ `UPON_COMPLETION` - Never goes overdue, resets immediately

---

### Option 3: `at_due_date_clear_at_approval_reset` (Auto-Clear Overdue)

**Constant:** `const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET`

**Logic Flow:**

```python
# During coordinator update cycle
if due_date and now_utc > due_date:
    chore_state = "overdue"  # Turn red

# During scheduled reset (even if NOT approved)
def _reset_chores():
    if overdue_handling_type == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET:
        # Clear overdue automatically
        chore_state = const.STATUS_PENDING
        due_date = calculate_next_due_date()
        # Fresh start - overdue cleared even without approval

# During approval (if approved while overdue)
def approve_chore(chore_id, kid_id):
    _award_points(kid_id, chore_points)
    chore_info[const.DATA_CHORE_KID_STATUS][kid_id] = const.STATUS_APPROVED
    # Stays approved until scheduled reset
    # Overdue clears at next scheduled reset time
```

**Works with ALL approval_reset_type values:**

- ✅ `AT_MIDNIGHT_ONCE/MULTI` - Overdue clears at midnight (with or without approval)
- ✅ `AT_DUE_DATE_ONCE/MULTI` - Overdue clears at next due date
- ✅ `UPON_COMPLETION` - N/A (already resets immediately)

---

### Option 4: `at_due_date_clear_immediate_on_late` (NEW - Immediate Reset)

**Constant:** `const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE`

**Logic Flow:**

```python
# During coordinator update cycle (same as Option 1)
if due_date and now_utc > due_date:
    chore_state = "overdue"  # Turn red

# During approval - KEY DIFFERENCE
def approve_chore(chore_id, kid_id):
    _award_points(kid_id, chore_points)

    # Check if approval is "late" (after reset boundary passed)
    is_late_approval = _is_approval_after_reset_boundary(
        chore_info, kid_id, approval_reset_type
    )

    # Check overdue handling
    overdue_handling = chore_info.get(
        const.DATA_CHORE_OVERDUE_HANDLING_TYPE,
        const.DEFAULT_OVERDUE_HANDLING_TYPE
    )

    # NEW: Treat as UPON_COMPLETION if approved after reset boundary
    should_reschedule_immediately = (
        approval_reset_type == const.APPROVAL_RESET_UPON_COMPLETION
        or (overdue_handling == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE
            and is_late_approval)
    )

    if should_reschedule_immediately:
        # Reset immediately (reuse UPON_COMPLETION logic)
        if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
            # Each kid resets independently
            self._reschedule_chore_next_due_date_for_kid(chore_info, chore_id, kid_id)
            # Inside reschedule method:
            # - chore_state = const.STATUS_PENDING
            # - due_date = calculate_next_due_date()

        elif completion_criteria in (const.COMPLETION_CRITERIA_SHARED, const.COMPLETION_CRITERIA_SHARED_FIRST):
            # Check if all kids approved
            if all_kids_approved:
                self._reschedule_chore_next_due_date(chore_info)
                # - chore_state = const.STATUS_PENDING
                # - due_date = calculate_next_due_date()
    else:
        # Normal approval (waits for scheduled reset)
        chore_info[const.DATA_CHORE_KID_STATUS][kid_id] = const.STATUS_APPROVED

# Helper function to check "late" approval
def _is_approval_after_reset_boundary(
    chore_info: dict, kid_id: str, approval_reset_type: str
) -> bool:
    """Check if approval is happening after reset period boundary."""
    now_utc = dt_util.utcnow()

    # AT_MIDNIGHT types: Check if past last midnight
    if approval_reset_type in (const.APPROVAL_RESET_AT_MIDNIGHT_ONCE,
                              const.APPROVAL_RESET_AT_MIDNIGHT_MULTI):
        last_midnight = now_utc.replace(hour=0, minute=0, second=0, microsecond=0)
        due_date = parse_datetime(chore_info.get(const.DATA_CHORE_DUE_DATE))
        if due_date and due_date < last_midnight:
            return True  # Due date was before last midnight = late

    # AT_DUE_DATE types: Check if past next scheduled due date
    elif approval_reset_type in (const.APPROVAL_RESET_AT_DUE_DATE_ONCE,
                                const.APPROVAL_RESET_AT_DUE_DATE_MULTI):
        # For INDEPENDENT, check per-kid due date
        if chore_info.get(const.DATA_CHORE_COMPLETION_CRITERIA) == const.COMPLETION_CRITERIA_INDEPENDENT:
            due_date = parse_datetime(
                chore_info.get(const.DATA_CHORE_KID_STATUS, {}).get(kid_id, {}).get(const.DATA_CHORE_DUE_DATE)
            )
        else:
            due_date = parse_datetime(chore_info.get(const.DATA_CHORE_DUE_DATE))

        if due_date:
            # Calculate when next reset would have been
            next_reset_time = calculate_next_due_date_from(due_date, chore_info)
            if now_utc > next_reset_time:
                return True  # Past next reset time = late

    return False  # Not late
```

**Works with ALL approval_reset_type values:**

- ✅ `AT_MIDNIGHT_ONCE` - Approved late → resets immediately to PENDING
- ✅ `AT_MIDNIGHT_MULTI` - Approved late → resets immediately, can claim again
- ✅ `AT_DUE_DATE_ONCE` - Approved late → resets immediately to PENDING
- ✅ `AT_DUE_DATE_MULTI` - Approved late → resets immediately, can claim again
- ✅ `UPON_COMPLETION` - Already immediate (new option has no effect)

**Key Implementation Detail:**
The condition triggers immediate reset by **reusing existing UPON_COMPLETION logic**:

```python
# Lines 9395-9408 in coordinator.py (existing code)
def _reschedule_chore_next_due_date(self, chore_info: dict) -> None:
    """Reschedule chore to next due date (SHARED)."""

    # Reset state to PENDING (this already exists!)
    if chore_info.get(const.DATA_CHORE_APPROVAL_RESET_TYPE) == const.APPROVAL_RESET_UPON_COMPLETION:
        # Process state (sets to PENDING)
        self._process_chore_state(chore_info)

    # Calculate next due date (already implemented)
    chore_info[const.DATA_CHORE_DUE_DATE] = self._calculate_next_due_date(chore_info)
```

**NEW implementation just extends the condition:**

```python
should_reset_state = (
    chore_info.get(const.DATA_CHORE_APPROVAL_RESET_TYPE) == const.APPROVAL_RESET_UPON_COMPLETION
    or chore_info.get(const.DATA_CHORE_OVERDUE_HANDLING_TYPE) == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE
)

if should_reset_state:
    self._process_chore_state(chore_info)  # Existing method!
```

---

## Chore Type Compatibility Matrix

### Universal Compatibility: All Approval Reset Types

| Approval Reset Type | Works with new option? | Behavior                           | Notes                                                  |
| ------------------- | ---------------------- | ---------------------------------- | ------------------------------------------------------ |
| `AT_MIDNIGHT_ONCE`  | ✅ YES                 | Approved late → resets immediately | Single claim limit still enforced                      |
| `AT_MIDNIGHT_MULTI` | ✅ YES                 | Approved late → resets immediately | **KILLER USE CASE** 🚀 - maximizes daily opportunities |
| `AT_DUE_DATE_ONCE`  | ✅ YES                 | Approved late → resets immediately | Single claim limit still enforced                      |
| `AT_DUE_DATE_MULTI` | ✅ YES                 | Approved late → resets immediately | Maximizes multi-claim window                           |
| `UPON_COMPLETION`   | N/A (always immediate) | Already resets immediately         | New option has no effect                               |

---

## 🚀 Killer Use Case: AT_MIDNIGHT_MULTI (Daily Multi-Claim)

### Confirmed: Works with `frequency = daily_multi` Recurrence Type

**YES - fully compatible!** The new overdue handling option works perfectly with the `daily_multi` recurrence type (frequency field).

**Key Understanding:**

- `frequency` (recurrence_type) = Controls HOW OFTEN chore recurs and how due dates are calculated
- `approval_reset_type` = Controls WHEN chore resets after approval
- `overdue_handling_type` = Controls overdue behavior and late approval handling

**These three fields work together independently:**

```python
# Example chore configuration
chore = {
    "frequency": const.FREQUENCY_DAILY_MULTI,  # Recurs daily with multiple time slots
    "approval_reset_type": const.APPROVAL_RESET_AT_MIDNIGHT_MULTI,  # Resets at midnight, allows multi-claim
    "overdue_handling_type": const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE,  # NEW - immediate reset on late
    "daily_multi_times": ["08:00", "14:00", "18:00"],  # 3 time slots per day
    "due_date": "2026-01-14T08:00:00+00:00"  # First time slot
}
```

**How They Interact:**

1. **`frequency = daily_multi`** determines next due date calculation:

   ```python
   # In _calculate_next_due_date()
   if frequency == const.FREQUENCY_DAILY_MULTI:
       # Use daily_multi_times to set next due date
       # e.g., if current is 08:00, next is 14:00 same day
       #       if current is 18:00, next is 08:00 next day
   ```

2. **`overdue_handling_type = at_due_date_clear_immediate_on_late`** triggers immediate reset:

   ```python
   # In approve_chore()
   if is_late_approval and overdue_handling == CLEAR_IMMEDIATE_ON_LATE:
       # Call _reschedule_chore_next_due_date()
       # Which internally calls _calculate_next_due_date()
       # Which uses daily_multi logic to set next time slot!
   ```

3. **Result:** Late approval triggers immediate reset, next due date calculated using `daily_multi_times` ✅

### Why This Combination Shines

### Why This Combination Shines

**`daily_multi` frequency + immediate late reset = Perfect match!**

**Problem:** Daily multi-claim chores (dishes, laundry, pet feeding) lose entire days when approved late.

**Example with `daily_multi` frequency:**

**Chore Configuration:**

```python
{
    "name": "Load Dishwasher",
    "frequency": "daily_multi",
    "daily_multi_times": ["08:00", "14:00", "20:00"],  # Morning, afternoon, evening
    "approval_reset_type": "at_midnight_multi",
    "overdue_handling_type": "at_due_date_clear_immediate_on_late",  # NEW
    "due_date": "2026-01-14T08:00:00+00:00"
}
```

**Scenario: Late Morning Approval**

**WITHOUT Option 4:**

```
Tuesday 8:00 AM  → Due date (first time slot)
Tuesday 8:01 AM  → Kid doesn't claim, goes overdue
Wednesday 12:00 AM → Midnight passes (reset boundary)
Wednesday 10:00 AM → Parent approves late
Wednesday 10:01 AM → Chore still APPROVED ❌
Wednesday 2:00 PM → 14:00 time slot missed (can't claim) ❌
Wednesday 8:00 PM → 20:00 time slot missed (can't claim) ❌
Thursday 12:00 AM → Finally resets to PENDING
Thursday 8:00 AM → Due date becomes Thu 8:00 AM

Result: Entire Wednesday lost (0 claims possible) ❌
```

**WITH Option 4:**

```
Tuesday 8:00 AM  → Due date (first time slot)
Tuesday 8:01 AM  → Kid doesn't claim, goes overdue
Wednesday 12:00 AM → Midnight passes (reset boundary)
Wednesday 10:00 AM → Parent approves late
                   → ✅ _is_approval_after_reset_boundary() returns TRUE
                   → ✅ Immediate reset triggered!
                   → ✅ _calculate_next_due_date() called
                   → ✅ Uses daily_multi_times to find next slot
                   → ✅ Next slot after 10:00 AM is 14:00 (2 PM)
Wednesday 10:01 AM → Chore now PENDING, due_date = Wed 14:00 ✅
Wednesday 1:00 PM  → Kid can claim it! ✅
Wednesday 1:30 PM  → Kid completes, parent approves
Wednesday 1:31 PM  → Chore APPROVED (until next time slot)
Wednesday 8:00 PM  → Due date becomes 20:00 (evening slot)
Wednesday 8:30 PM  → Kid claims again! ✅
Wednesday 9:00 PM  → Completed and approved
Thursday 12:00 AM  → Scheduled reset for next day
Thursday 8:00 AM  → Due date becomes Thu 8:00 AM

Result: Wednesday recovered! 2 time slots still available ✅
```

**Key Validation Points:**

✅ **`_calculate_next_due_date()` respects `daily_multi` frequency**

- When called during immediate reset, it uses `daily_multi_times` array
- Finds next time slot after current time
- If past last slot (20:00), advances to next day's first slot (08:00)

✅ **Immediate reset doesn't break daily_multi logic**

- Reset happens in same methods used by UPON_COMPLETION
- UPON_COMPLETION already works with daily_multi
- Therefore new option inherits daily_multi compatibility ✅

✅ **Multi-claim tracking preserved**

- Each time slot is a separate claim opportunity
- Immediate reset just advances to next slot
- Claim counter managed correctly per period

### Technical Confirmation: daily_multi Integration

**In coordinator.py `_calculate_next_due_date()` method:**

```python
def _calculate_next_due_date(self, chore_info: dict) -> str | None:
    """Calculate next due date based on frequency."""
    frequency = chore_info.get(const.DATA_CHORE_FREQUENCY)

    if frequency == const.FREQUENCY_DAILY_MULTI:
        # Get time slots
        daily_multi_times = chore_info.get(const.DATA_CHORE_DAILY_MULTI_TIMES, [])
        current_time = dt_util.now()

        # Find next time slot after current time
        for time_slot in daily_multi_times:
            slot_time = parse_time_slot(time_slot)
            if slot_time > current_time.time():
                # Next slot today
                return combine_date_time(current_time.date(), slot_time)

        # All slots passed today, use first slot tomorrow
        next_day = current_time.date() + timedelta(days=1)
        return combine_date_time(next_day, daily_multi_times[0])
```

**This method is called by:**

1. Scheduled reset (midnight) - ✅ Works
2. UPON_COMPLETION immediate reset - ✅ Works
3. **NEW: Late approval immediate reset** - ✅ Works (same code path!)

**Therefore: `daily_multi` frequency fully compatible with new overdue option!** ✅

**AT_MIDNIGHT_MULTI Behavior WITHOUT Option 4:**

```
Tuesday 5:00 PM  → Chore due, kid doesn't claim
Tuesday 5:01 PM  → Goes overdue (red)
Wednesday 12:00 AM → Scheduled reset would happen here
Wednesday 8:00 AM  → Parent approves late
Wednesday 8:01 AM  → Chore still APPROVED ❌
Wednesday 3:00 PM  → Still APPROVED (can't claim again) ❌
Thursday 12:00 AM  → Finally resets to PENDING
Result: Entire Wednesday lost (0 additional claims possible)
```

**AT_MIDNIGHT_MULTI WITH Option 4 (`at_due_date_clear_immediate_on_late`):**

```
Tuesday 5:00 PM  → Chore due, kid doesn't claim
Tuesday 5:01 PM  → Goes overdue (red)
Wednesday 12:00 AM → Reset boundary passes (but not approved yet)
Wednesday 8:00 AM  → Parent approves late
                   → ✅ _is_approval_after_reset_boundary() returns TRUE
                   → ✅ due_date (Tue 5PM) < last_midnight (Wed 00:00)
                   → ✅ should_reschedule_immediately = TRUE
                   → ✅ Immediate reset triggered!
Wednesday 8:01 AM  → Chore now PENDING with due date Wed 5:00 PM ✅
Wednesday 8:02 AM  → Kid can claim it! ✅
Wednesday 9:00 AM  → Kid completes, parent approves ✅
Wednesday 9:01 AM  → Chore APPROVED (normal behavior until Thu midnight)
Wednesday 2:00 PM  → Kid claims again (multi-claim works!) ✅
Wednesday 6:00 PM  → Kid completes, parent approves ✅
Thursday 12:00 AM  → Scheduled reset for next cycle

Result: Wednesday recovered! 2 additional claims possible ✅
```

### Technical Flow for AT_MIDNIGHT_MULTI

**Step-by-step execution:**

1. **During approval (Wed 8:00 AM):**

   ```python
   # In approve_chore()
   approval_reset_type = const.APPROVAL_RESET_AT_MIDNIGHT_MULTI
   overdue_handling = const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE

   # Check if late
   is_late_approval = self._is_approval_after_reset_boundary(
       chore_info, kid_id, approval_reset_type
   )
   # Returns True because:
   #   due_date = Tue 5:00 PM
   #   last_midnight = Wed 00:00
   #   due_date < last_midnight ✅

   should_reschedule_immediately = (
       approval_reset_type == const.APPROVAL_RESET_UPON_COMPLETION  # False
       or (overdue_handling == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE  # True
           and is_late_approval)  # True
   )
   # Result: should_reschedule_immediately = True ✅
   ```

2. **Immediate reschedule triggered:**

   ```python
   if should_reschedule_immediately:
       if completion_criteria == const.COMPLETION_CRITERIA_INDEPENDENT:
           self._reschedule_chore_next_due_date_for_kid(chore_info, chore_id, kid_id)
       # Inside this method:
       # - Resets state to PENDING
       # - Calculates new due date (Wed 5:00 PM)
       # - Preserves approval history in period structure
   ```

3. **Result state:**
   ```python
   chore_info[const.DATA_CHORE_KID_STATUS][kid_id] = const.STATUS_PENDING
   chore_info[const.DATA_CHORE_DUE_DATE] = "2026-01-15T17:00:00+00:00"  # Wed 5PM
   # Multi-claim counter reset for new period
   # Kid can claim immediately!
   ```

### Why AT_MIDNIGHT_MULTI Is The Perfect Match

**Daily Multi-Claim Characteristics:**

- ✅ High-frequency chores (happens every day)
- ✅ Multiple completion opportunities per day (2-3+ times)
- ✅ Late approvals common (parent busy in morning)
- ✅ Lost days = significant earning opportunity loss
- ✅ Kids motivated by immediate availability

**Real-World Examples:**

**Dishes (AT_MIDNIGHT_MULTI + Option 4):**

- Morning: Load dishwasher
- Afternoon: Unload and reload
- Evening: Final load
- If parent approves late morning → kid can still do afternoon/evening loads! ✅

**Pet Care (AT_MIDNIGHT_MULTI + Option 4):**

- Morning: Feed dog
- Afternoon: Walk dog
- Evening: Feed dog again
- Late approval doesn't forfeit remaining opportunities ✅

**Laundry (AT_MIDNIGHT_MULTI + Option 4):**

- Can do multiple loads per day
- Late approval = immediate availability for next load ✅

### Configuration Recommendation

**For AT_MIDNIGHT_MULTI chores, ALWAYS use:**

```yaml
approval_reset_type: at_midnight_multi
overdue_handling_type: at_due_date_clear_immediate_on_late # NEW option
```

**Why?**

- Maximum earning flexibility
- Recovers lost time windows automatically
- No manual intervention needed
- Perfect for busy parents who approve in batches

### Completion Criteria Compatibility

| Completion Criteria | Works? | Behavior Details                                                                 |
| ------------------- | ------ | -------------------------------------------------------------------------------- |
| `INDEPENDENT`       | ✅ YES | Each kid's late approval triggers their own immediate reset                      |
| `SHARED`            | ✅ YES | Resets immediately when all kids have approved (follows UPON_COMPLETION pattern) |
| `SHARED_FIRST`      | ✅ YES | Resets immediately when first kid approves                                       |

### Key Clarifications

**"Late" Definition (CRITICAL):**

- "Late" means approved **AFTER the reset boundary has passed**, not just after due date
- **AT_MIDNIGHT types:** Late = approval after midnight boundary (last midnight if due date before that)
- **AT_DUE_DATE types:** Late = approval after next scheduled due date time would have been
- **Example:** Chore due Tuesday 5PM with AT_MIDNIGHT_MULTI (reset boundary = Wed 00:00):
  - Approved Tuesday 6PM = **NOT late** ❌ (before midnight boundary) → stays APPROVED until Wed midnight
  - Approved Wednesday 8AM = **LATE** ✅ (past midnight boundary) → immediate reset triggers

**Boundary Behavior:**

- Approval **at exact due time** (5:00:00 PM) = on-time (NOT late)
- Approval **one second after** (5:00:01 PM) = late
- Implementation uses `>` not `>=` for boundary check

**SHARED Multi-Kid:**

- Each kid approves individually
- Chore resets when **ALL kids** have approved (same as UPON_COMPLETION)
- If kid A approves late and kid B hasn't approved yet, chore doesn't reset until kid B approves

**INDEPENDENT Per-Kid:**

- Each kid has own due date and "late" boundary
- Kid A approving late only resets **Kid A's cycle**
- Kid B's cycle unaffected until they approve

---

## User-Facing Summary: Overdue Handling Options

### The Four Options Explained

#### Option 1: **Mark overdue at due date** (was default before v0.6.0)

**Constant:** `at_due_date`

**Behavior:**

- Chore turns red when due date passes
- Stays overdue until someone approves it
- After approval, stays APPROVED until next scheduled reset
- **Does NOT auto-clear overdue** - requires approval

**Best for:**

- When strict overdue tracking is needed
- When you want kids to see what's overdue and address it
- Chores that must be explicitly completed or skipped

**Example:** Daily dishes due 5PM with AT_MIDNIGHT_MULTI

- Tue 5:01 PM → Goes overdue (red)
- Wed 8 AM → Approved, points awarded, stays APPROVED
- Thu 12:00 AM → Scheduled reset, back to PENDING
- **Wednesday lost for multi-claims**

---

#### Option 2: **Never mark as overdue**

**Constant:** `never_overdue`

**Behavior:**

- Chore NEVER turns red
- Always shows as PENDING even after due date passes
- After approval, stays APPROVED until next scheduled reset

**Best for:**

- Low-pressure chores (bed making, room tidying)
- Kids who get discouraged by red states
- Flexible timing chores

**Example:** Weekly room cleaning

- Never shows as overdue
- Can approve anytime
- Resets on schedule

---

#### Option 3: **Clear overdue at next scheduled reset** ⭐ NEW DEFAULT

**Constant:** `at_due_date_clear_at_approval_reset`

**Behavior:**

- Chore goes overdue (red) when due date passes
- Overdue state clears automatically at next scheduled reset even if not approved
- If approved while overdue, stays APPROVED until scheduled reset

**Best for:**

- Most chores (good default behavior)
- Chores with grace periods
- Weekly/monthly chores where missing one is okay
- When you want automatic overdue clearing without manual intervention

**Example:** Weekly allowance chore

- Goes overdue if missed
- Automatically clears at next Monday
- Gives fresh start each week

---

#### Option 4: **Clear overdue immediately when approved late** 🚀 NEW

**Constant:** `at_due_date_clear_immediate_on_late`

**Behavior:**

- Chore goes overdue (red) when due date passes
- If approved **before reset boundary** → stays APPROVED until scheduled reset (normal)
- If approved **after reset boundary** → **immediately resets to PENDING**
- Can be claimed again right away after late approval
- **Maximizes earning opportunities**

**Best for:**

- **Any chores** where late approvals happen (ONCE or MULTI)
- High-frequency chores (dishes, laundry)
- When you want maximum flexibility
- Families who approve late often

**Example 1 - Not Late:** Daily dishes due Tue 5PM with AT_MIDNIGHT_MULTI

- Tue 5:01 PM → Goes overdue (red)
- Tue 6:00 PM → Approved (before Wed midnight) → stays APPROVED ✅
- Wed 12:00 AM → Scheduled reset, back to PENDING
- **Normal behavior** - approved within same period

**Example 2 - Late Approval:** Daily dishes due Tue 5PM with AT_MIDNIGHT_MULTI

- Tue 5:01 PM → Goes overdue (red)
- Wed 8:00 AM → Approved (past Wed midnight boundary) → **immediately resets to PENDING** ✅
- Wed 9:00 AM → Kid can claim again!
- **Wednesday NOT lost** - immediate reset recovered the window

---

### Decision Guide: Which Option to Choose?

**Choose "clear at approval reset" (NEW DEFAULT) if:**

- ✅ Most chores - good default behavior
- ✅ You want automatic overdue clearing without manual intervention
- ✅ Grace periods matter (missed chores don't stay red forever)
- ✅ Fresh starts each cycle automatically
- ✅ Example chores: most daily/weekly chores, homework tracking

**Choose "immediate on late" if:**

- ✅ Kids often approve after reset boundaries pass (not just after due date)
- ✅ You want to maximize earning opportunities for multi-claim chores
- ✅ Lost time windows between resets are a problem
- ✅ Works for both ONCE and MULTI types
- ✅ Example chores: dishes, laundry, pet care (high-frequency multi-claim)

**Choose "mark overdue at due date" if:**

- ✅ Strict overdue tracking needed
- ✅ Chores must be explicitly completed or manually skipped
- ✅ You want overdue state to persist until addressed
- ✅ Example chores: critical daily tasks that can't be missed

**Choose "never overdue" if:**

- ✅ Flexible timing chores
- ✅ Low-pressure environment
- ✅ Kids discouraged by red states
- ✅ Example chores: bed making, tidying, optional tasks

---

### Real-World Scenarios

**Scenario 1: Power User Family (Maximizing Earnings)**

- Daily dishes: `at_due_date_clear_immediate_on_late` + AT_MIDNIGHT_MULTI
- Result: Late approvals don't lose opportunities

**Scenario 2: Structured Family (Predictable Schedule)**

- Daily chores: `at_due_date` (default) + AT_MIDNIGHT_ONCE
- Result: Clear schedule, no surprises

**Scenario 3: Flexible Family (Low Pressure)**

- Most chores: `never_overdue`
- Weekly tasks: `at_due_date_clear_at_approval_reset`
- Result: Minimal stress, automatic resets

**Scenario 4: Mixed Approach (Per Chore)**

- High-value MULTI: `immediate on late`
- Low-pressure ONCE: `never overdue`
- Weekly tasks: `clear at approval reset`
- Result: Customized to each chore's purpose

---

### Key Watches & Gotchas

⚠️ **Watch #1: UPON_COMPLETION Override**

- If `approval_reset_type = UPON_COMPLETION`, it ALWAYS resets immediately
- The overdue handling option is **ignored**
- Immediate behavior happens regardless of setting

⚠️ **Watch #2: "Late" Timing (CRITICAL)**

- "Late" means **after reset boundary**, NOT just after due date
- AT_MIDNIGHT chore due Tue 5PM (reset boundary Wed 00:00):
  - Approved Tue 6PM = **NOT LATE** (before midnight) → stays APPROVED until Wed midnight
  - Approved Wed 8AM = **LATE** (past midnight boundary) → immediate reset triggers
- This is the key difference from Option 1!

⚠️ **Watch #3: SHARED All-Kids Requirement**

- SHARED chore with "immediate on late" only resets when **ALL kids** approve
- If 2 kids, both must approve before reset triggers
- Follows same pattern as UPON_COMPLETION

⚠️ **Watch #4: Boundary Edge Case**

- Approved at **exactly** 5:00:00 PM = on-time (NOT late)
- Approved at 5:00:01 PM = late ✅
- Implementation uses strict greater-than check

⚠️ **Watch #5: Existing Chores Unchanged**

- All existing chores keep default: `at_due_date`
- No behavior change unless you explicitly select new option
- Safe to upgrade

⚠️ **Watch #6: Not a Scheduled Reset Replacement**

- Immediate reset only happens **when approved late**
- On-time approvals still use scheduled reset timing
- Example: Approve on-time → waits for midnight/due date

---

**Last Updated:** 2026-01-14 (Finalized: Extend overdue_handling_type, leverage UPON_COMPLETION)
**Next Review:** After implementation Phase 1 complete (constants added)

- [ ] Code comments explain decision logic
- [ ] Release notes written

---

## Risk Assessment

| Risk                          | Severity | Likelihood | Mitigation                         |
| ----------------------------- | -------- | ---------- | ---------------------------------- |
| Breaks existing workflows     | Medium   | Low        | Preserve AT_MIDNIGHT_ONCE behavior |
| Duplicate notifications       | Low      | Medium     | Test notification logic carefully  |
| Race condition at midnight    | Medium   | Low        | Ensure atomic state transitions    |
| Multi-kid coordination issues | Medium   | Medium     | Test SHARED chores with 2+ kids    |
| Per-kid due date bugs         | High     | Low        | Comprehensive INDEPENDENT tests    |

---

## Completion Check

### Decisions Captured

- [x] Option C (Extend overdue_handling_type) selected as implementation approach
- [x] Notification behavior: Single notification on late approval (existing logic)
- [x] Applicable days: Follows existing next_valid_day logic
- [x] Multi-kid coordination: INDEPENDENT per-kid, SHARED all-kids-must-approve

### Sign-Off Requirements

- [x] **Strategy Review:** Approach validated by project owner
- [x] **Implementation Plan:** Builder confirms phases are actionable
- [x] **Test Strategy:** All edge cases identified and testable
- [x] **Quality Gates:** Lint 9.5+/10, MyPy zero errors, 651 tests pass
- [x] **Implementation Complete:** All 5 phases implemented and validated

### Ready for Implementation When:

1. Open questions resolved (notification, applicable days, multi-kid)
2. Phase 1 analysis complete (edge cases documented)
3. Builder confirms approach feasibility
4. Project owner approves behavior change

---

## References

- [ARCHITECTURE.md](../ARCHITECTURE.md) - Data model, storage schema
- [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md) - Coding patterns
- [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md) - Quality standards
- [Wiki: Chore Status and Recurrence](../../kidschores-ha.wiki/Chore-Status-and-Recurrence-Handling.md) - Current behavior documentation

**Related Code Locations:**

- `coordinator.py` lines 2900-3200: `approve_chore()` method
- `coordinator.py` lines 8679-8860: `_reset_all_chore_counts()` and reset logic
- `coordinator.py` lines 8860-9100: `_reset_daily_chore_statuses()`
- `const.py` line 1039-1051: Approval reset type constants

---

**Last Updated:** 2026-01-14
**Next Review:** After user/owner feedback on Option D recommendation
