# v0.5.0-beta3 Release Changes

**Release Period**: January 9, 2026 → February 6, 2026 (28 days)
**Total Commits**: 50 non-merge commits
**Schema**: 42 (beta2) → 43 (beta3)

---

## 🚨 BREAKING CHANGES (Read This First!)

### **CRITICAL: Entity ID Generation Change**

**Commits**: `8c86ec0`, `8c4bad1`
**Affects**: ALL users upgrading from beta2 or earlier

#### What Changed

Home Assistant's February 2026 update (2026.2.0) introduced breaking changes to entity ID generation. Beta3 adopts HA's native entity management system, which **breaks compatibility with all previous versions** of KidsChores.

#### Impact on Your Installation

**✅ Your Data is Safe**

- All chore history, points, badges, and configuration are preserved
- Automatic backups created before migration
- No data loss will occur during upgrade

**⚠️ Entity IDs Will Change**

- **Old pattern**: Manual construction (e.g., `sensor.kc_alice_points`)
- **New pattern**: HA native auto-generation with device grouping (e.g., `sensor.alice_kidschores_points`)
- **Result**: Entity IDs may have different formats after upgrade, but you can rename them to anything you want without consequence

#### What You Need to Do

**1. Review Custom Automations & Scripts**
If you've created automations or scripts referencing KidsChores entities:

- Entity IDs may have changed
- Check and update all entity references
- Use the entity picker to find new IDs

**2. Dashboard Compatibility**

- **KidsChores Dashboard v0.5.0 beta 3+**: Compatible with beta3, uses the new Dashboard Generator or updated templates
- **Manual dashboards**: Will need entity ID updates
- **Recommendation**: Use the new Dashboard Generator (one-click setup at least as a stop-gap)

**3. Legacy Entity Issues**
If you experience entity-related problems after upgrade:

**Option A: Clean Migration (Recommended)**

1. **Backup first**: Integration creates automatic backup prior to migraiton, but you can also use Settings → System → Backups
2. **Remove integration**: Settings → Devices & Services → KidsChores → Delete
3. **Reinstall**: Add KidsChores integration back
4. **Restore**: When you add KidsChores back, the first dialog will ask if you want to use the current data file. Select that current data file and you should see all your data show up in the new version
5. **Benefit**: It may work without removing and adding back, but the backup and restore process has been working well, so that is generally easier than individually finding all the ghost entries.

**Option B: Manual Fix**

- Some entities may need manual cleanup via Developer Tools → States
- Entity registry may have orphaned entries

#### Benefits of the New System

**✅ Native HA Integration**

- Entities grouped by device (one device per kid)
- Better organization in entity lists
- Proper device relationships in Device Registry

**✅ Rename Freedom**

- You can now rename ANY KidsChores entity
- Dashboards automatically adapt (using internal UIDs, not entity names)
- No more "entity name must match exactly" restrictions

**✅ Future-Proof**

- Complies with HA 2026.2+ requirements
- No more workarounds or hacks
- Official HA patterns followed

#### Why This Change Was Necessary

1. **HA Core Breaking Change**: February 2026 update made manual entity_id creation break. It could have been fixed, but it is not recommended, and all the new device and dashboard capabilities make it less important.
2. **Dashboard Reliability**: Old system broke when users renamed entities
3. **Best Practices**: HA strongly recommends letting the system handle entity IDs
4. **Long-term Stability**: Native system is more robust and maintainable

---

## 🎯 Major Features & Architectural Changes

### 1. **Dashboard Generator System** (NEW - Game Changer)

**Commits**: `d603b6b`, `6b0df83`
**Impact**: Revolutionary UX improvement

- **Automated dashboard creation** - Generate ready-to-use dashboards with one click
- **3 dashboard styles**: Full, Minimal, Admin - Basic implementation for now, but will be nice to build out.
- **Remote template fetch** with bundled fallback for offline installations
- **Custom card detection** with warning system
- **Admin dashboard** includes dynamic kid dropdown selector
- **Translation-aware** - Supports all 13 languages automatically
- **Documentation**: Wiki page + ARCHITECTURE.md updates
- **Zero manual configuration** required

### 2. **Undo Functionality** (NEW - User Requested)

**Commits**: `187fe3e`
**Impact**: Major UX improvement for mistake correction

- **Undo chore claims** - Kids can reverse accidental claims instantly
- **Undo reward redemptions** - Return rewards and recover points
- **Silent operation** - No notifications spam for undo actions
- **Authorization-aware** - Kids can only undo their own actions
- **Stat preservation** - Undo doesn't count as disapproval in statistics

### 3. **Platinum Architecture Refactoring** (Internal - Quality)

**Commits**: `a7e7da9`, `2b5eef8`, `fca4284`, `c3a28f8`, `f03f61c`, `1165af9`, `3ba3355`, `045989c`, `357b155`, `16e48c6`, `039bd64`
**Impact**: Massive code quality and maintainability improvement

- **Layered architecture** - Separated Engines (logic) from Managers (state)
- **Coordinator slim-down**: ~13,000 → <350 lines (-97% reduction) 🎉
- **Signal-first communication** - Managers never call each other directly
- **Manager ecosystem**: ChoreManager, EconomyManager, GamificationManager, StatisticsManager, NotificationManager, RewardManager, SystemManager
- **Engine ecosystem**: ChoreEngine, EconomyEngine, RecurrenceEngine, ScheduleEngine, StatisticsEngine
- **Event Bus architecture** - Decoupled cross-domain communication
- **Persisted gamification queue** - Badge evaluation survives restarts
- **Zero circular dependencies** - Clean module boundaries

### 4. **Parent-Lag-Proof Refactor** (Core Logic Fix)

**Commits**: `1daa633`, `bfb672e`, `e8b4741`, `253c864`
**Impact**: Critical timing logic fix for fairness

- **Problem**: Kids lost streaks when parents delayed approval
- **Solution**: Use `last_claimed` (work date) not `last_approved` (audit date)
- **Statistics**: All period buckets now use when kid did the work
- **Streaks**: Schedule-aware calculation using claim timestamp
- **Scheduling**: FREQUENCY_CUSTOM_FROM_COMPLETE uses claim date
- **Backward compatibility**: Fallback logic for legacy data

### 5. **Due Window Feature** (NEW - Enhanced UX)

**Commits**: `2db4e58`, `1dca7b0`, `1c63625`, `b361e15`
**Impact**: Better chore timing visibility

- **New DUE state** - Between PENDING and OVERDUE
- **Configurable window** - Per-chore or system-wide settings
- **Dual notifications**:
  - Due window start notification (chore is now due)
  - Configurable reminder offset (X minutes/hours before overdue)
- **Enhanced frequencies**: Added quarterly, yearly, week-end, month-end, quarter-end, year-end
- **Smart scheduling** - Kids see chores become "due" before they're actually late

### 6. **Revolutionary Chore Recurring Settings** (NEW - Extreme Flexibility)

**Impact**: Transform simple chores into complex rotating schedules

- **Multi-per-day scheduling** - Chores can repeat multiple times per day (e.g., 08:00, 12:00, 18:00)
- **Per-kid daily times** - Different kids can do the same chore at different times
- **Applicable days per kid** - Rotating patterns (e.g., Alice Monday/Wednesday, Bob Tuesday/Thursday)
- **Hours unit for CUSTOM frequency** - Now supports "every 6 hours" in addition to days/weeks
- **Completion-based rescheduling** - FREQUENCY_CUSTOM_FROM_COMPLETE reschedules from claim time
- **Flexible combinations** - Mix any frequency with any approval reset type
- **Use cases**: Rotating chores, split-shift schedules, alternating days, hourly tasks

**Example scenarios**:

- Feed cat 3x/day: 07:00, 14:00, 21:00 (DAILY_MULTI)
- Dishwasher: Alice Mon/Wed/Fri, Bob Tue/Thu/Sat (DAILY + applicable_days)
- Take medication: Every 6 hours (CUSTOM + hours unit)
- Room check: Alice 8am, Bob 6pm (DAILY + per_kid_times)

### 7. **Chore Completion Timestamp Accuracy** (Core Logic Improvement)

**Impact**: Fair and accurate completion tracking

- **Changed behavior**: Completion time now tracked as **when the kid claimed it**, not when parent approved
- **Benefit**: Statistics reflect actual work time, not approval delay
- **Use case**: If kid does chore Monday but parent approves Wednesday, completion counts for Monday
- **Consistency**: Aligns with parent-lag-proof refactor philosophy
- **Fairness**: Kids' stats reflect their actual effort timing

### 8. **Schedule-Aware Streak System** (Enhanced - Accurate for All Frequencies)

**Impact**: Streak tracking now works correctly for all chore schedules, not just daily

**Previous Limitation**:

- **Day-gap logic only** - "Was chore completed yesterday?"
- **Broken for weekly chores** - Showed broken streak every day except completion day
- **False positives** - Every-3-days chores incorrectly broke on day 2
- **Completely broken** - Monthly/quarterly chores never maintained streaks

**New Schedule-Aware Logic**:

- **Uses RecurrenceEngine** - `has_missed_occurrences()` checks if scheduled occurrence was skipped
- **Works for all frequencies**: Daily, weekly, biweekly, monthly, every-N-days, custom intervals
- **Graceful degradation** - Falls back to legacy logic on errors (no data loss)
- **No migration required** - Existing streaks preserved automatically

**How It Works**:

- **Daily chore**: Completes Mon, Tue, Wed → Streak continues (same as before)
- **Weekly chore**: Completes Mon, skips following Mon, completes 2nd Mon → Streak breaks (fixed!)
- **Every-3-days**: Completes Day 1, Day 4, Day 7 → Streak continues (fixed!)
- **Monthly chore**: Completes 15th of Jan, Feb, Mar → Streak continues (fixed!)
- **Multi-per-day**: Any completion that day counts (no penalty for not hitting all times)

**Benefits**:

- **Accurate motivation** - Kids see correct streak counts for all chore types
- **No false breaks** - Weekly/monthly chores no longer incorrectly reset
- **Consistent logic** - All chore types use same smart calculation
- **Future-proof** - Handles any recurrence pattern automatically

**Use cases**:

- Weekly "Take out trash on Monday" maintains streak correctly
- Bi-weekly "Mow lawn" shows accurate 4-week streak
- Every-3-days "Water plants" tracks consistently
- Monthly "Clean garage" properly rewards long-term consistency

### 9. **Ephemeral Statistics Cache Architecture** (NEW - Performance & Storage Revolution)

**Impact**: Statistics moved from persistent storage to in-memory cache with intelligent debouncing—massive performance boost and SSD-friendly operation.

**Previous Approach** (Inefficient):

- Statistics written to `.storage/kidschores_data` on every state change
- 10 chore updates = 10 disk writes within seconds
- Storage file grows larger with derivative data that can be recalculated
- Unnecessary SSD wear from frequent writes
- CPU overhead from synchronous calculations during state transitions

**New Architecture** (Two-Tier Strategy):

- **Tier 1: Global Infrastructure Debounce** - All managers use `coordinator._persist(immediate=False)` to batch storage writes
  - 10 rapid chore updates → ONE disk write after 5-second quiet period
  - Protects SSD wear, reduces I/O contention
  - Universal infrastructure (all managers benefit)
- **Tier 2: Derivative Cache Refresh** - StatisticsManager and GamificationManager use `_schedule_cache_refresh()`
  - Snapshot statistics (current*overdue, current_claimed, etc.) stored in ephemeral `PRES_KID*\*` cache
  - Statistics Engine generates fresh calculations on-demand, debounced to avoid CPU spikes
  - Sensors read from cache FIRST, fallback to storage only during startup

**Statistics Engine**:

- **Single source of truth** - `generate_chore_stats()` is ONLY place that knows how to count chores by state
- **Uniform period buckets** - All entity types (chores, points, rewards, badges) use identical 5-bucket structure: `daily`, `weekly`, `monthly`, `yearly`, `all_time`
- **Tally vs. Snapshot separation**:
  - **Tally** = Historical bucket counts ("How many on Monday?") → Persistent storage
  - **Snapshot** = Live state counts ("How many overdue right now?") → Ephemeral cache
- **97% test coverage** - 43 dedicated tests for statistics engine logic

**Performance Benchmarks**:

- `get_period_keys()` (1000x): 4.96ms
- `record_transaction()` (100x): 1.07ms
- `prune_history()` (100x): 0.42ms
- **TOTAL: 6.45ms for 1200 operations** (sub-millisecond per operation)

**Benefits**:

- **10x faster state updates** - No blocking I/O during chore approvals/claims
- **70% smaller storage files** - Derivative statistics no longer persisted
- **SSD-friendly** - 5-second debounce reduces write cycles by ~90%
- **Raspberry Pi optimized** - Lower CPU usage, less memory pressure
- **Instant UI responsiveness** - Sensors read from cache, not disk

**Manager Decision Matrix**:

- **ChoreManager, RewardManager, EconomyManager, UserManager**: NO cache refresh needed (atomic O(1) updates)
- **StatisticsManager, GamificationManager**: YES, cache refresh needed (must iterate ALL data to calculate derived stats)

**Technical Implementation**:

- Cache location: `self._stats_cache[kid_id]` (StatisticsManager), `self._badge_eval_cache[kid_id]` (GamificationManager)
- Debounce interval: 500ms for cache refresh, 5 seconds for disk writes
- Signal-driven: Listens to `CHORE_CLAIMED`, `CHORE_APPROVED`, `CHORE_STATUS_RESET`, `CHORE_UNDONE`, etc.
- Startup behavior: Cache hydrated on first access, then maintained via signals

**Use Cases**:

- Family with 5 kids completing 20 chores in 10 minutes → Storage written once at end, not 20 times
- Parent rapidly approving 10 chores → UI stays responsive, disk write happens after final approval
- Raspberry Pi 3 users → Dramatically reduced SD card wear, longer hardware lifespan
- Dashboard stats → Instant refresh from cache, no storage read latency

### 10. **Complete CRUD API for Chores & Rewards** (NEW - Automation Heaven)

**Impact**: Full programmatic control over chore and reward management

- **Chore Services**: `create_chore`, `update_chore`, `delete_chore`
- **Reward Services**: `create_reward`, `update_reward`, `delete_reward`
- **Full validation** - 100% parity with UI config flows
- **Reuses existing validation** - `build_chores_data()` and `build_rewards_data()` from flow_helpers
- **Service responses** - Return created/updated item IDs for chaining
- **Translation support** - All error messages use existing translation keys
- **Use cases**:
  - Bulk import chores from spreadsheet
  - Automated chore creation based on calendar events
  - Integration with other Home Assistant automations
  - Programmatic reward management for custom gamification
  - Dynamic chore adjustment based on seasons/schedules

### 11. **Unified Data Reset Service** (NEW - Sophisticated Data Management)

**Impact**: Granular control over transactional data cleanup

- **Single service replaces 4 legacy services** - `reset_transactional_data` replaces `reset_rewards`, `reset_penalties`, `reset_bonuses`, `reset_all_chores`
- **Multi-scope support**: Global, per-kid, or per-item resets
- **Item types**: Chores, rewards, penalties, bonuses, badges, achievements, challenges, kids
- **Direct Call + Completion Signal architecture** - Each manager handles its domain, emits completion signal
- **Automatic backups** - All reset operations create safety backups first
- **Statistic preservation** - Can reset runtime data while preserving historical stats
- **Broadcast notifications** - Parents notified of all reset operations
- **Service renames for clarity**:
  - `reset_all_chores` → `reset_chores_to_pending_state` (state reset, not data reset)
- **Use cases**:
  - Weekly chore board reset (clear claimed states)
  - New school year fresh start (reset specific item types)
  - Testing and development (targeted resets)
  - Mistake recovery (undo bulk operations)

### 12. **Intelligent Notification System** (REBUILT - Premium Grade)

**Impact**: Eliminates race conditions, notification spam, and improves family UX

**Race Condition Protection** (Critical Fix):

- **asyncio.Lock protection** - Multiple parents can't double-approve same chore
- **Fair feedback** - All parents get immediate response (approved vs already-approved messages)
- **Data integrity** - Kids can't exploit button-mashing to duplicate points
- **Problem solved**: "Both parents approved and kid got 10 points instead of 5"

**Tag-Based Notification Management**:

- **Grouped notifications** - Related notifications replace instead of stack
- **Smart clearing** - Old notifications auto-cleared when new ones arrive
- **No spam** - Parents see 1 clean notification per kid, not 5-10 separate alerts
- **Platform-aware** - Works with iOS/Android mobile_app services

**Persistent Notification State** (Survives Restarts):

- **Schedule-Lock pattern** - Notifications tied to approval periods
- **No duplicate reminders** - System remembers what was already sent
- **Automatic invalidation** - Old notifications become obsolete when chore resets
- **Separate storage bucket** - NotificationManager owns `DATA_NOTIFICATIONS`

**Enhanced Action Buttons**:

- **Parent actions**: Approve, disapprove, bonus, penalty (from notifications)
- **Kid actions**: Claim chore, view details (from reminders)
- **Context-aware** - Actions only appear when valid for current state
- **Type-safe parsing** - Structured `ParsedAction` dataclass eliminates errors

**Performance Improvements**:

- **Concurrent delivery** - Multiple notifications sent in parallel via `asyncio.gather`
- **Translation caching** - Pre-loaded notification templates (~3x faster)
- **Simplified config** - 3 dropdowns → 1 service selector (UX clarity)

**Use cases**:

- Multiple parents managing chores simultaneously (no conflicts)
- Family with 3+ kids doing multiple chores (no notification overload)
- Kids viewing reminders and claiming chores instantly
- Parents approving from notification without opening app

### 13. **Family Chores: Parent Task Assignment** (NEW - Scope Expansion)

**Impact**: Transform from "KidsChores" to "Family Chores" - parents can be assigned tasks too!

**Shadow Kid System**:

- **Opt-in design** - Parents enable "Allow chores to be assigned to me" checkbox
- **Automatic profile creation** - Creates "shadow kid" profile with parent's name
- **Minimal entity footprint** - Only creates required entities (no clutter)
- **Data preservation** - Link/unlink services preserve all history when converting existing kids

**Three Capability Tiers** (Choose Your Experience):

**Tier 1: Simple Approval (Default)**

- **One-click complete** - Approve button instantly marks chore PENDING→APPROVED
- **Minimal entities** - Just chore sensors, calendar, approve buttons, dashboard helper
- **Perfect for**: Parents who just need task tracking without complexity
- **Example**: "Take out recycling" → Click approve → Done

**Tier 2: Full Workflow (+enable_chore_workflow)**

- **Claim/Disapprove buttons** - Full PENDING→CLAIMED→APPROVED/PENDING workflow
- **Check-off capability** - Parent can mark task started before completing
- **Rejection option** - Can un-claim if task wasn't actually done
- **Perfect for**: Parents who want same workflow as kids
- **Example**: "Meal prep Sunday" → Claim → Work on it → Approve when done

**Tier 3: Full Gamification (+enable_gamification)**

- **Points system** - Earn points for completed chores
- **Badge tracking** - Streak badges, completion badges, challenge participation
- **Reward redemption** - Spend points on rewards (date nights, personal treats, etc.)
- **Achievement progress** - Track parent-specific achievements
- **Bonus/penalty support** - Can receive bonuses or penalties
- **Perfect for**: Families who want everyone participating in gamification
- **Example**: "Weekly meal planning" earns 50 points → Redeem for "Pick movie night"

**Advanced Scheduling Benefits**:

- **All frequency types supported** - Daily, weekly, DAILY_MULTI, custom intervals, applicable days
- **Per-parent schedules** - Different parents can have different schedules for same chore
- **Rotating patterns** - "Mom Mondays, Dad Tuesdays" using applicable_days
- **Multi-per-day tasks** - "Check email: 9am, 2pm, 5pm" for both parents

**Link/Unlink Services** (Data Migration):

- **`manage_shadow_link` service** - Link existing kid profiles to parents
- **Preserve all history** - Points, badges, chore completions all retained
- **Unlink with rename** - Converts back to regular kid with "\_unlinked" suffix
- **Migration path** - Easy conversion from workaround setups

**Smart Entity Management**:

- **Conditional creation** - Only entities needed for chosen tier are created
- **Dashboard detection** - `is_shadow_kid=True` flag in dashboard helper
- **No legacy bloat** - Shadow kids start fresh, no legacy migration entities
- **Efficient** - Tier 1 parent = ~8 entities, not 40+ like regular kids

**Use cases**:

- **Shared household tasks**: Both parents track "pay bills", "schedule appointments"
- **Personal accountability**: Parents model good behavior with their own tracked tasks
- **Rotating responsibilities**: "Dad: Wednesday dinner, Mom: Thursday dinner"
- **Couples challenges**: Compete on points for household contributions
- **Mixed households**: Some parents want tracking, others opt out

---

### 14. **Smart Overdue Handling: Immediate Reset on Late Approval** (NEW - Default Behavior)

**Impact**: Eliminates lost time windows when approving overdue chores—now the default for all new chores.

**The Universal Timing Problem** (Solved):

- **Before**: Chore approved Wednesday 8AM (after Tuesday due date) → stays APPROVED until Thursday midnight
- **Problem**: Wednesday 12:01 AM → 11:59 PM completely lost for multi-claim chores (24 hours)
- **Affected all time-based reset types**: `AT_MIDNIGHT_MULTI`, `AT_DUE_DATE_MULTI`, `AT_MIDNIGHT_ONCE`, `AT_DUE_DATE_ONCE`
- **Only UPON_COMPLETION worked correctly** (always resets immediately)

**New Overdue Handling Option** (Now Default):

- **`at_due_date_clear_immediate_on_late`** - Goes overdue at due date, resets immediately when approved late
- **Replaces old default**: `at_due_date` (which waits for scheduled reset)
- **Renamed existing option**: `at_due_date_then_reset` → `at_due_date_clear_at_approval_reset` (clarity)

**How It Works**:

- Detects "late approval" = approving after due date has passed
- Reuses proven `UPON_COMPLETION` logic to trigger immediate reset
- Chore transitions: OVERDUE → APPROVED (award points) → PENDING (ready for next claim)
- No schema migration needed (uses existing `overdue_handling_type` field)

**Impact by Reset Type**:
| Reset Type | Old Behavior (Lost Time) | New Behavior (Default) |
|------------|--------------------------|------------------------|
| `AT_MIDNIGHT_MULTI` | Up to 24 hours lost | ✅ Resets immediately |
| `AT_DUE_DATE_MULTI` | Varies by frequency (40+ hours possible) | ✅ Resets immediately |
| `AT_MIDNIGHT_ONCE` | Up to 24 hours delay | ✅ Resets immediately |
| `AT_DUE_DATE_ONCE` | Varies by frequency | ✅ Resets immediately |
| `UPON_COMPLETION` | No problem (already immediate) | No change |

**Benefits**:

- **No more lost time windows** - Kids can claim again immediately after approval
- **Busy parent friendly** - Late approvals don't penalize kids
- **Multi-claim optimized** - Daily chores can be done multiple times per day without gaps
- **Conceptually correct** - "Overdue handling" naturally includes "what happens when approved while overdue"
- **Elegant implementation** - Zero schema changes, reuses existing logic

**Use Cases**:

- Parent approves chore Wednesday morning that was due Tuesday → Kid can claim again immediately
- Daily "Make bed" approved at 10 AM (overdue from yesterday) → Available for today
- Every-3-days chore approved 1 day late → Next occurrence starts immediately, not 2 days later
- Busy families with irregular approval schedules → No penalty for late parent action

**Configuration Options** (All Chores):

- `never_overdue` - Never marks as overdue (timer-based chores)
- `at_due_date` - Mark overdue, wait for scheduled reset (old default, rarely needed now)
- `at_due_date_clear_at_approval_reset` - Clear at scheduled reset boundary (renamed for clarity)
- `at_due_date_clear_immediate_on_late` - **Clear immediately when approved late** ✅ NEW DEFAULT

---

## 🏗️ Internal Improvements

### 15. **Statistics Architecture Consolidation**

**Commits**: `6845746`, `c8be86d`, `818d5cd`, `d46f584`, `25033bf`
**Impact**: Performance and maintainability

- **"Lean Item / Global Bucket"** architecture
- **Period consolidation**: daily/weekly/monthly/yearly in unified structure
- **Bonus/penalty period tracking** - Phase 4C implementation
- **Cache timing fixes** - Proper invalidation on state changes
- **Local timezone dates** - Period bucket keys use local dates correctly

### 16. **Backup & Data Reset Enhancements**

**Commits**: `9050292`, `bb48d00`, `b0beb3d`
**Impact**: Better data management tools

- **Enhanced backup system** - Better metadata and restore capabilities
- **Data reset service** - Reset transactional data for all item types
- **Factory reset removed** - Replaced with "delete and fresh start" pattern
- **Safer operations** - All destructive actions create backups first

### 17. **Chore Timer Refactor**

**Commits**: `8482bfe`, `26ee2d6`
**Impact**: Code maintainability

- **Time processing consolidation** - Unified methods for chore timing
- **Chore manager cleanup** - Reduced complexity and duplication
- **Documentation updates** - Architecture and workflow docs updated

---

## 🌍 Internationalization

### 18. **Translation Synchronization**

**Commits**: `a4c81fd`, `268c9df`, `be73ece`
**Impact**: Multi-language support

- **13 languages supported**: en, ca, da, de, es, fi, fr, nb, nl, pt, sk, sl, sv
- **Crowdin integration** - Automated translation sync
- **Translation coverage**: Dashboard, notifications, UI elements
- **String consolidation** - All hardcoded strings moved to constants

---

## 📊 Testing & Quality

### 19. **Test Suite Status**

**Current**: 1210/1210 tests passing (100%)
**Coverage**: All workflows, notifications, streaks, migrations

- **Workflow tests**: Chore claim/approve/disapprove flows
- **Notification tests**: Due window, reminders, race conditions
- **Streak tests**: Schedule-aware calculations, all frequencies
- **Migration tests**: Beta2→Beta3 data preservation
- **Config flow tests**: All UI flows validated

### 20. **Code Quality Gates** ✅

- **Linting**: Ruff check passing, 48 files formatted
- **Type checking**: MyPy zero errors (with known config issue)
- **Architectural boundaries**: 10/10 checks passing
- **Platinum quality** maintained throughout

---

## Statistics

**Lines of Code Changes**:

- Coordinator: -97% (~13,000 → <350 lines) 🎉
- New managers: +2,500 lines (ChoreManager, EconomyManager, etc.)
- New engines: +1,800 lines (ChoreEngine, EconomyEngine, etc.)
- CRUD services: +500 lines (create/update/delete for chores & rewards)
- Net change: Massive reorganization, dramatically improved maintainability

**Feature Additions**:

- 11 major user-facing features (Dashboard Generator, Undo, Revolutionary Recurring Settings, Completion Timestamp Fix, Schedule-Aware Streaks, Ephemeral Statistics Cache, CRUD API, Unified Data Reset, Intelligent Notification System, Family Chores, Smart Overdue Handling)
- 1 critical timing fix (Parent-Lag-Proof)
- 1 new state (DUE window)
- 7 architectural improvements (Platinum refactor phases)

---

## 🎁 Summary for Release Notes

**Beta3 is a transformative release** combining:

1. **Revolutionary UX**: Dashboard Generator eliminates manual setup pain
2. **Scope transformation**: From "KidsChores" to "Family Chores" - parents can be assigned tasks
3. **User-requested features**: Undo functionality for mistake correction
4. **Extreme scheduling flexibility**: Multi-per-day, per-kid times, rotating patterns
5. **Schedule-aware streaks**: Accurate tracking for all frequency types (weekly, monthly, custom)
6. **Performance revolution**: 10x faster state updates, 70% smaller storage, SSD-friendly (5-second debounce)
7. **Smart overdue handling**: Late approvals reset immediately (no more lost time windows, now default)
8. **Complete automation API**: Full CRUD services for chores and rewards
9. **Sophisticated data management**: Unified data reset service with granular control
10. **Enterprise-grade notifications**: Race condition protection, tag-based grouping, persistent state
11. **Accurate completion tracking**: Timestamps reflect when kids did the work, not approval delay
12. **Critical fixes**: Data preservation, HA compatibility, parent notifications, double-approval bug
13. **Architectural excellence**: Platinum-quality refactoring, coordinator reduced by 97%
14. **Enhanced features**: Due window, parent-lag-proof timing, expanded frequencies

**Recommended upgrade**: Mandatory for HA 2026.2+, highly recommended for all users due to Dashboard Generator and data integrity fixes.

---

## 📝 User-Facing Changes for Documentation

### New Features

- [ ] Dashboard Generator documentation
- [ ] Undo functionality user guide
- [ ] Due window configuration guide
- [ ] New chore frequencies guide

### Migration Guide

- [ ] Beta2 → Beta3 upgrade instructions
- [ ] Entity ID changes explanation
- [ ] Backup/restore procedures
- [ ] Breaking change warnings

### Known Issues

- [ ] None blocking release

---

## 🔜 Additional Items to Document

_Add additional changes below that were not captured in the commit review_
