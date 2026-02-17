# Notification System Modernization - Strategic Plan

> ⚠️ **SUPERSEDED**: This document has been replaced by the reality-checked plan:  
> **[NOTIFICATION_IMPROVEMENTS_REALISTIC_IN-PROCESS.md](./NOTIFICATION_IMPROVEMENTS_REALISTIC_IN-PROCESS.md)**  
> 
> **Why?** This original plan was over-engineered for the actual use case:
> - Actual volume: 25-50 notifications/day (not enterprise scale)
> - Priority queues, rate limiting, batching: unnecessary complexity
> - 24-32 hour estimate → reduced to 7-10 hours with realistic scope
> 
> The new plan delivers the same real value (concurrent delivery, race condition fix, 
> translation caching) without inventing features we don't need.

**Initiative Code**: NOTIF-MOD-v1  
**Target Release**: v0.6.0  
**Owner**: Development Team  
**Status**: ~~Planning~~ SUPERSEDED  

---

## Executive Summary

The current notification system works reliably for basic scenarios but has significant architectural limitations that impact performance, scalability, and user experience. This initiative proposes a comprehensive modernization to create a **best-in-class notification solution** that is:

- **Fast**: Concurrent delivery, intelligent batching, pre-loaded translations
- **Reliable**: Race condition protection, retry logic, graceful degradation
- **Intelligent**: Priority-based delivery, user preference filtering, rate limiting
- **Observable**: Delivery tracking, performance metrics, debugging tools
- **Maintainable**: Clean architecture, comprehensive constants, extensive testing

**Current Pain Points**:

- Sequential parent notifications (200ms-2.5s latency per approval)
- No race condition protection in action handler
- Translation loading per-parent (N+1 problem)
- No notification history or delivery tracking
- Limited user control over notification types
- Hardcoded strings and missing constants
- No retry logic for failed deliveries

**Expected Outcomes**:

- 70%+ faster multi-parent notifications (concurrent delivery)
- Zero race conditions (coordinator-level locking)
- 50%+ reduction in translation loading time (caching)
- Full notification history tracking
- Granular user preferences (per-notification-type control)
- 95%+ test coverage with comprehensive edge case handling

---

## Initiative Snapshot

| Metric               | Value                                |
| -------------------- | ------------------------------------ |
| **Phases**           | 6 phases                             |
| **Estimated Effort** | 24-32 hours                          |
| **Files Changed**    | ~15 files                            |
| **New Files**        | 5 files                              |
| **Test Files**       | 8 files                              |
| **Breaking Changes** | None (backward compatible)           |
| **Schema Version**   | v42 → v43 (notification preferences) |
| **Dependencies**     | None (uses existing HA services)     |

---

## Summary Table

| Phase                        | Description                         | Completion | Key Deliverables                         |
| ---------------------------- | ----------------------------------- | ---------- | ---------------------------------------- |
| **Phase 1 - Foundation**     | Constants, types, base classes      | 0%         | notification_types.py, constants, models |
| **Phase 2 - Core Engine**    | Manager, queue, concurrent delivery | 0%         | NotificationManager, delivery engine     |
| **Phase 3 - Action Handler** | Hardening, validation, locking      | 0%         | Race-condition-free handler              |
| **Phase 4 - Intelligence**   | Caching, batching, preferences      | 0%         | Translation cache, user prefs            |
| **Phase 5 - Observability**  | Tracking, metrics, debugging        | 0%         | History, diagnostics, sensors            |
| **Phase 6 - Testing**        | Comprehensive test suite            | 0%         | 95%+ coverage, load tests                |

---

## Problem Analysis

### 1. Performance Issues

**Current State**: Sequential notification delivery

```python
# coordinator.py lines 10583-10650
async def _notify_parents(...):
    for parent_id, parent_info in self.parents_data.items():
        # Sequential await - blocks on each parent
        await async_send_notification(...)  # 200-500ms each
```

**Impact**:

- 5 parents × 300ms avg = 1500ms total latency
- User perceives approval as "slow"
- Mobile apps show delayed feedback
- Parent 5 waits for Parents 1-4 to complete

**Root Cause**:

- No concurrent execution (`asyncio.gather`)
- No failure isolation (one slow parent blocks all)
- Translations loaded per-parent (N+1 query problem)

---

### 2. Race Condition Vulnerabilities

**Current State**: No debouncing or locking in action handler

```python
# notification_action_handler.py lines 95-98
coordinator.approve_chore(
    parent_name=parent_name,
    kid_id=kid_id,
    chore_id=chore_id,  # No lock, no debounce
)
```

**Attack Scenario**:

1. Parent clicks "Approve" on mobile notification
2. HA dispatches event to handler
3. Handler calls `coordinator.approve_chore()`
4. Parent double-clicks (within 100ms)
5. Second event dispatched before first completes
6. Both read `approved_chores = []` (empty)
7. Both add approval + points
8. Result: Double approval, double points awarded

**Current "Protection"**:

- Chore-level duplicate check (lines 2356-2366)
- BUT: Race window exists if both requests read before either writes
- No atomic operations, no locking mechanism

---

### 3. Translation Performance

**Current State**: Load translations per-parent, per-notification

```python
# coordinator.py lines 10677-10681
translations = await kh.load_notification_translation(
    self.hass, parent_language  # File I/O per parent
)
```

**Impact**:

- 5 parents = 5 file reads (even if same language)
- Each read: ~5-10ms I/O + JSON parse
- Multiplied by every notification event
- No caching between notifications

**Root Cause**:

- Helper function doesn't cache
- No in-memory translation registry
- Loads entire file each time (wasteful)

---

### 4. Missing Architecture Patterns

**Current Gaps**:

| Pattern               | Current            | Needed                                      |
| --------------------- | ------------------ | ------------------------------------------- |
| **Queue Management**  | ❌ None            | ✅ Priority queue for notifications         |
| **Batch Processing**  | ❌ None            | ✅ Combine notifications within time window |
| **Retry Logic**       | ❌ None            | ✅ Exponential backoff for failures         |
| **Rate Limiting**     | ❌ None            | ✅ Per-user throttling to prevent spam      |
| **Delivery Tracking** | ❌ None            | ✅ Success/failure history                  |
| **User Preferences**  | ❌ On/off only     | ✅ Per-type granular control                |
| **Observability**     | ❌ Debug logs only | ✅ Metrics, diagnostics, sensors            |

---

### 5. Code Quality Issues

**From NOTIF_ANALYSIS2.md**:

| Issue                | Location                       | Impact                    |
| -------------------- | ------------------------------ | ------------------------- |
| Hardcoded strings    | notification_action_handler.py | Hard to maintain, no i18n |
| Inconsistent logging | All notification code          | Hard to debug             |
| Missing constants    | Action validation              | Magic strings scattered   |
| No type hints        | Helper functions               | Type errors at runtime    |
| Broad exceptions     | notification_helper.py         | Hides real errors         |

---

## Proposed Architecture

### High-Level Design

```
┌─────────────────────────────────────────────────────────────┐
│                    Notification System v2.0                  │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐      ┌───────────────┐     ┌──────────┐ │
│  │  Coordinator │─────▶│ Notification  │────▶│  Queue   │ │
│  │   (Source)   │      │    Manager    │     │ (Priority)│ │
│  └──────────────┘      └───────────────┘     └──────────┘ │
│                               │                     │       │
│                               ▼                     ▼       │
│                        ┌──────────────┐     ┌──────────┐  │
│                        │ Translation  │     │ Delivery │  │
│                        │    Cache     │     │  Engine  │  │
│                        └──────────────┘     └──────────┘  │
│                                                   │         │
│                                         ┌─────────┴─────┐  │
│                                         ▼               ▼  │
│                                   ┌──────────┐  ┌─────────┐│
│                                   │  Mobile  │  │Persistent││
│                                   │  Notify  │  │  Notify ││
│                                   └──────────┘  └─────────┘│
│                                         │               │   │
│                                         ▼               ▼   │
│                                   ┌───────────────────────┐│
│                                   │  Delivery Tracker    ││
│                                   │  (History/Metrics)   ││
│                                   └───────────────────────┘│
└─────────────────────────────────────────────────────────────┘
```

### Core Components

#### 1. NotificationManager (New)

**File**: `custom_components/kidschores/notification_manager.py`

**Responsibilities**:

- Central notification orchestration
- Queue management (priority-based)
- Translation cache management
- Delivery coordination
- Metrics collection

**Key Methods**:

```python
class NotificationManager:
    async def send_to_kid(self, kid_id, notif_type, data, priority)
    async def send_to_parents(self, kid_id, notif_type, data, priority)
    async def send_batch(self, notifications)  # Concurrent delivery
    def get_cached_translation(self, language, key)
    async def track_delivery(self, notif_id, status, metadata)
```

#### 2. NotificationQueue (New)

**File**: `custom_components/kidschores/notification_queue.py`

**Responsibilities**:

- Priority-based queueing (HIGH/NORMAL/LOW)
- Batching within time windows (configurable)
- Rate limiting per user
- Delivery scheduling

**Priority Levels**:

- **HIGH**: Overdue chores, critical achievements (immediate)
- **NORMAL**: Approvals, claims, rewards (5s batch window)
- **LOW**: Reminders, badge earned (30s batch window)

#### 3. TranslationCache (New)

**File**: `custom_components/kidschores/notification_translation_cache.py`

**Responsibilities**:

- In-memory translation storage (per language)
- TTL-based invalidation (5 minutes default)
- Async pre-loading on startup
- Fallback to file loading on cache miss

**Cache Structure**:

```python
{
    "en": {
        "chore_approved": {"title": "...", "message": "..."},
        "reward_claimed": {"title": "...", "message": "..."},
        # ... all notification types
    },
    "es": {...},
    "de": {...}
}
```

#### 4. NotificationActionHandler (Enhanced)

**File**: `custom_components/kidschores/notification_action_handler.py` (refactored)

**New Features**:

- Constants-based validation
- Coordinator-level locking (async locks per action type)
- Request deduplication (tracking in-flight operations)
- Comprehensive error handling with translations
- Type-safe parameter extraction

#### 5. DeliveryTracker (New)

**File**: `custom_components/kidschores/notification_delivery_tracker.py`

**Responsibilities**:

- Track delivery success/failure per notification
- Store last N notifications (configurable, default 100)
- Provide diagnostics endpoint
- Calculate delivery metrics (success rate, avg latency)

**Storage**:

```python
{
    "history": [
        {
            "id": "notif_uuid",
            "timestamp": "2026-01-15T10:30:00Z",
            "type": "chore_approved",
            "recipient": "parent_id",
            "status": "success",
            "latency_ms": 234,
            "service": "notify.mobile_app_iphone"
        }
    ],
    "metrics": {
        "total_sent": 1234,
        "success_rate": 0.987,
        "avg_latency_ms": 245
    }
}
```

---

## Phase Breakdown

### Phase 1: Foundation & Constants (6-8 hours)

**Goal**: Establish solid foundation with types, constants, and data models

#### Step 1.1: Create notification type definitions

- [ ] Create `custom_components/kidschores/notification_types.py`
  - Define `NotificationType` enum (all 18+ notification types)
  - Define `NotificationPriority` enum (HIGH/NORMAL/LOW)
  - Define `DeliveryStatus` enum (QUEUED/SENDING/SUCCESS/FAILED/RETRY)
  - Define `NotificationRecipient` enum (KID/PARENT/BOTH)

#### Step 1.2: Add comprehensive constants

- [ ] File: `custom_components/kidschores/const.py` (lines ~1470-1500)
  - Add `NOTIF_TYPE_*` constants for all notification types
  - Add `NOTIF_PRIORITY_*` constants (HIGH/NORMAL/LOW)
  - Add `NOTIF_DELIVERY_STATUS_*` constants
  - Add `NOTIF_BATCH_WINDOW_*` constants (timing)
  - Add `NOTIF_CACHE_TTL` constant (translation cache)
  - Add `NOTIF_MAX_HISTORY` constant (delivery tracking)
  - Add `NOTIF_RATE_LIMIT_*` constants (per-user throttling)

#### Step 1.3: Define data models

- [ ] Create `custom_components/kidschores/notification_models.py`
  - `NotificationRequest` dataclass (immutable)
  - `NotificationDelivery` dataclass (tracking)
  - `TranslationCacheEntry` dataclass (with TTL)
  - `DeliveryMetrics` dataclass (statistics)

#### Step 1.4: Add action handler constants

- [ ] File: `custom_components/kidschores/const.py` (lines ~1474-1490)
  - Replace hardcoded action strings with constants
  - Add `NOTIF_ACTION_TYPE_*` constants
  - Add `NOTIF_DATA_KEY_*` constants (action payloads)
  - Add validation sets (e.g., `VALID_NOTIFICATION_ACTIONS`)

#### Step 1.5: Update schema for notification preferences

- [ ] File: `custom_components/kidschores/const.py`
  - Increment `SCHEMA_VERSION` to 43
  - Add `DATA_KID_NOTIFICATION_PREFERENCES` key
  - Add `DATA_PARENT_NOTIFICATION_PREFERENCES` key
  - Structure: `{"chore_approved": True, "reward_claimed": False, ...}`

**Validation**:

```bash
# Import check
python -c "from custom_components.kidschores.notification_types import NotificationType; print(NotificationType.CHORE_APPROVED)"

# Mypy validation
mypy custom_components/kidschores/notification_types.py
mypy custom_components/kidschores/notification_models.py
```

**Deliverables**:

- 3 new files (types, models, updated const.py)
- Zero mypy errors
- All enums importable and usable

---

### Phase 2: Core Notification Engine (8-10 hours)

**Goal**: Build the central notification orchestration system

#### Step 2.1: Create NotificationManager class

- [ ] Create `custom_components/kidschores/notification_manager.py`
  - Initialize with hass, coordinator reference
  - Set up internal queue (asyncio.Queue with priority)
  - Initialize translation cache dictionary
  - Add async startup/shutdown methods

#### Step 2.2: Implement translation cache

- [ ] File: `notification_manager.py`
  - Method: `async def _preload_translations(self)`
    - Load all enabled languages on startup
    - Store in memory with TTL metadata
    - Use `kc_helpers.load_notification_translation()`
  - Method: `def get_cached_translation(lang, key) -> dict`
    - Check cache, return if valid (not expired)
    - Load and cache on miss
    - Fallback to English if language not found

#### Step 2.3: Implement concurrent parent notification

- [ ] File: `notification_manager.py`
  - Method: `async def notify_parents_concurrent(kid_id, notif_type, data)`
    - Gather all eligible parents (associated + notifications enabled)
    - Create notification tasks (one per parent)
    - Use `asyncio.gather(*tasks, return_exceptions=True)`
    - Isolate failures (log but don't block others)
    - Track delivery per-parent
    - Measure and log total latency

#### Step 2.4: Implement batching logic

- [ ] File: `notification_manager.py`
  - Method: `async def _batch_processor(self)`
    - Background task (runs continuously)
    - Collect notifications from queue within time window
    - Group by recipient + type (deduplication)
    - Flush batch at window end or queue full
    - Use priority to override batching (HIGH = immediate)

#### Step 2.5: Implement retry logic

- [ ] File: `notification_manager.py`
  - Method: `async def _retry_failed_delivery(notif_id, attempt)`
    - Exponential backoff: 2^attempt seconds (max 5 attempts)
    - Re-queue notification with RETRY status
    - Track retry count in delivery metadata
    - Give up after max attempts, log failure

#### Step 2.6: Integrate with coordinator

- [ ] File: `custom_components/kidschores/coordinator.py`
  - Add `self.notification_manager = NotificationManager(hass, self)`
  - Replace `_notify_parents_translated()` with manager call
  - Replace `_notify_kid_translated()` with manager call
  - Maintain backward compatibility (fall back to old method if manager fails)

**Validation**:

```bash
# Test concurrent notification speed
pytest tests/test_notification_manager.py::test_concurrent_parent_notification -v

# Test translation cache hit rate
pytest tests/test_notification_manager.py::test_translation_cache -v

# Performance test
pytest tests/test_notification_performance.py -v
```

**Deliverables**:

- NotificationManager fully functional
- 70%+ faster multi-parent notifications
- Translation cache working (95%+ hit rate)
- Retry logic in place

---

### Phase 3: Action Handler Hardening (4-6 hours)

**Goal**: Eliminate race conditions and improve action handler reliability

#### Step 3.1: Add coordinator-level locking

- [ ] File: `custom_components/kidschores/coordinator.py`
  - Add `self._action_locks: dict[str, asyncio.Lock] = {}`
  - Add method: `def _get_action_lock(self, action_type, kid_id, entity_id) -> asyncio.Lock`
    - Key: `f"{action_type}:{kid_id}:{entity_id}"`
    - Create lock if not exists, return existing otherwise
    - Auto-cleanup locks after 5 minutes of inactivity

#### Step 3.2: Refactor action handler with locking

- [ ] File: `custom_components/kidschores/notification_action_handler.py`
  - Wrap all coordinator calls with `async with coordinator._get_action_lock(...):`
  - Add request deduplication tracking (set of in-flight operation IDs)
  - Add validation using constants (no hardcoded strings)
  - Add comprehensive error handling with translation keys
  - Add type hints to all functions

#### Step 3.3: Add debouncing at handler level

- [ ] File: `notification_action_handler.py`
  - Track last action timestamp per (action_type, kid_id, entity_id)
  - Reject duplicate actions within 1 second
  - Log rejected duplicates at debug level

#### Step 3.4: Standardize logging

- [ ] File: `notification_action_handler.py`
  - Add `LOG_PREFIX = "[Notification Action Handler]"`
  - Update all `LOGGER` calls to use prefix
  - Use lazy logging (no f-strings)
  - Add structured logging (action_type, kid_id in context)

**Validation**:

```bash
# Race condition test (concurrent action handler calls)
pytest tests/test_notification_action_handler.py::test_race_condition_protection -v

# Debounce test (rapid double-clicks)
pytest tests/test_notification_action_handler.py::test_debouncing -v

# Lock cleanup test (memory leak prevention)
pytest tests/test_notification_action_handler.py::test_lock_cleanup -v
```

**Deliverables**:

- Zero race conditions (proven by tests)
- All hardcoded strings replaced with constants
- Comprehensive logging with consistent prefix
- 100% type hint coverage

---

### Phase 4: Intelligence Layer (4-6 hours)

**Goal**: Add smart features (preferences, rate limiting, batching)

#### Step 4.1: Implement user notification preferences

- [ ] File: `custom_components/kidschores/coordinator.py`
  - Add migration method: `_migrate_to_v43()`
    - Add `notification_preferences` dict to all kids/parents
    - Default: all notification types enabled
  - Add method: `def should_send_notification(user_id, notif_type) -> bool`
    - Check user preferences
    - Check global enable/disable setting
    - Return combined result

#### Step 4.2: Add preference management to config flow

- [ ] File: `custom_components/kidschores/config_flow.py`
  - Add new options step: `async_step_notification_preferences`
  - Show multi-select for notification types
  - Apply to specific kid or parent
  - Persist to storage via coordinator

#### Step 4.3: Implement rate limiting

- [ ] File: `notification_manager.py`
  - Add rate limiter: track notifications sent per user per hour
  - Limits: 60 notifications/hour per user (configurable)
  - On limit exceeded: queue notification as LOW priority, delay delivery
  - Log rate limit hits (potential spam detection)

#### Step 4.4: Implement smart batching

- [ ] File: `notification_manager.py`
  - Combine similar notifications (e.g., 3 chore approvals → 1 summary)
  - Time windows: NORMAL=5s, LOW=30s, HIGH=0s (immediate)
  - Deduplicate by (recipient, type, entity_id)
  - Generate batch summary messages

#### Step 4.5: Add notification scheduling

- [ ] File: `notification_manager.py`
  - Support "quiet hours" per user (no notifications 10pm-7am)
  - Queue non-urgent notifications during quiet hours
  - Deliver queued notifications at quiet hours end
  - Allow HIGH priority to override quiet hours

**Validation**:

```bash
# Preference filtering test
pytest tests/test_notification_preferences.py -v

# Rate limiting test
pytest tests/test_notification_rate_limiting.py -v

# Batching test
pytest tests/test_notification_batching.py -v
```

**Deliverables**:

- Granular per-type notification preferences
- Rate limiting active (prevents spam)
- Smart batching reduces notification fatigue
- Quiet hours respected

---

### Phase 5: Observability & Debugging (3-4 hours)

**Goal**: Add comprehensive tracking, metrics, and debugging tools

#### Step 5.1: Implement delivery tracking

- [ ] Create `custom_components/kidschores/notification_delivery_tracker.py`
  - Store last 100 notifications (configurable)
  - Track: timestamp, type, recipient, status, latency, service
  - Persist to storage (new data key: `notification_history`)
  - Add method: `get_recent_deliveries(count=20) -> list`

#### Step 5.2: Create notification sensor entities

- [ ] Create `custom_components/kidschores/sensor_notifications.py`
  - Sensor: `sensor.kc_notification_delivery_rate` (notifications/hour)
  - Sensor: `sensor.kc_notification_success_rate` (percentage)
  - Sensor: `sensor.kc_notification_avg_latency` (ms)
  - Sensor: `sensor.kc_notification_queue_size` (pending count)
  - Update frequency: 5 minutes

#### Step 5.3: Add diagnostics endpoint

- [ ] File: `custom_components/kidschores/diagnostics.py`
  - Add section: "notification_system"
  - Include: delivery history, metrics, cache stats, queue status
  - Redact: user IDs, entity IDs (privacy)
  - Format: JSON-serializable

#### Step 5.4: Add debug service

- [ ] File: `custom_components/kidschores/services.yaml`
  - Service: `kidschores.debug_notification_system`
  - Returns: current queue, cache stats, recent deliveries
  - Admin-only (check user permissions)

#### Step 5.5: Performance logging

- [ ] File: `notification_manager.py`
  - Log notification latency (queue → delivery)
  - Log cache hit/miss rates
  - Log batch effectiveness (items combined)
  - Use `PERF:` prefix for easy filtering

**Validation**:

```bash
# Diagnostics test
pytest tests/test_notification_diagnostics.py -v

# Sensor entities test
pytest tests/test_notification_sensors.py -v

# Delivery tracking test
pytest tests/test_notification_delivery_tracker.py -v
```

**Deliverables**:

- Full notification history (last 100)
- Real-time metrics via sensor entities
- Comprehensive diagnostics
- Performance insights via logging

---

### Phase 6: Comprehensive Testing (3-4 hours)

**Goal**: Achieve 95%+ test coverage with focus on edge cases

#### Step 6.1: Create test fixtures

- [ ] File: `tests/fixtures/notification_fixtures.py`
  - Mock notification services (mobile, persistent)
  - Mock translation files
  - Test scenarios: Stårblüm Family with 5 parents
  - Helper: `generate_notification_request()`

#### Step 6.2: Unit tests for core components

- [ ] File: `tests/test_notification_manager.py`
  - Test: Translation cache (hit/miss/expiry)
  - Test: Concurrent parent notification
  - Test: Retry logic (exponential backoff)
  - Test: Batch processing
  - Test: Rate limiting

#### Step 6.3: Integration tests

- [ ] File: `tests/test_notification_integration.py`
  - Test: End-to-end chore approval → parent notification
  - Test: Multiple simultaneous approvals (no race conditions)
  - Test: Notification preference filtering
  - Test: Quiet hours scheduling
  - Test: Service failure graceful degradation

#### Step 6.4: Performance tests

- [ ] File: `tests/test_notification_performance.py`
  - Test: 10 parents, 50 notifications → measure total time
  - Baseline: <500ms for 50 notifications
  - Test: Translation cache reduces load time by 80%
  - Test: Concurrent vs sequential delivery (measure improvement)

#### Step 6.5: Race condition tests

- [ ] File: `tests/test_notification_race_conditions.py`
  - Test: Concurrent action handler calls (same chore)
  - Test: Rapid double-click simulation
  - Test: Lock acquisition/release
  - Test: Deadlock prevention

#### Step 6.6: Edge case tests

- [ ] File: `tests/test_notification_edge_cases.py`
  - Test: Missing translation file (fallback to English)
  - Test: Invalid notification service (graceful skip)
  - Test: Network timeout (retry logic)
  - Test: Queue overflow (backpressure)
  - Test: Parent with no associated kids (skip)
  - Test: Notification to deleted kid (error handling)

**Validation**:

```bash
# Full test suite
pytest tests/test_notification_*.py -v --cov=custom_components/kidschores/notification_* --cov-report=term-missing

# Coverage report (must be 95%+)
pytest tests/ --cov=custom_components/kidschores --cov-report=html

# Performance regression test
pytest tests/test_notification_performance.py -v --benchmark-only
```

**Deliverables**:

- 95%+ test coverage
- All edge cases handled
- Zero race conditions
- Performance benchmarks established

---

## Migration Strategy

### Backward Compatibility

**No breaking changes** - old notification methods remain functional:

```python
# Old method (coordinator.py) - still works
await self._notify_parents_translated(kid_id, title_key, message_key, ...)

# New method (uses manager internally) - gradual adoption
await self.notification_manager.send_to_parents(kid_id, notif_type, data)
```

**Feature Flags** (config entry options):

- `use_notification_manager_v2` (default: True)
- `enable_notification_batching` (default: True)
- `enable_notification_caching` (default: True)
- `notification_batch_window_seconds` (default: 5)

### Schema Migration (v42 → v43)

```python
# coordinator.py - _migrate_to_v43()
def _migrate_to_v43(self, data: dict) -> dict:
    """Add notification preferences to all kids and parents."""

    # Default preferences: all notification types enabled
    default_prefs = {
        notif_type.value: True
        for notif_type in NotificationType
    }

    # Add to all kids
    for kid_id, kid_info in data.get(const.DATA_KIDS, {}).items():
        if const.DATA_KID_NOTIFICATION_PREFERENCES not in kid_info:
            kid_info[const.DATA_KID_NOTIFICATION_PREFERENCES] = default_prefs.copy()

    # Add to all parents
    for parent_id, parent_info in data.get(const.DATA_PARENTS, {}).items():
        if const.DATA_PARENT_NOTIFICATION_PREFERENCES not in parent_info:
            parent_info[const.DATA_PARENT_NOTIFICATION_PREFERENCES] = default_prefs.copy()

    return data
```

### Rollback Plan

If issues arise:

1. Set `use_notification_manager_v2 = False` in options
2. System falls back to old notification methods
3. No data loss (preferences remain in storage)
4. Re-enable after fixes deployed

---

## Performance Targets

| Metric                                | Current               | Target        | Improvement          |
| ------------------------------------- | --------------------- | ------------- | -------------------- |
| **Multi-parent notification latency** | 1500ms (5 parents)    | 450ms         | 70% faster           |
| **Translation load time**             | 50ms per notification | 5ms (cached)  | 90% faster           |
| **Action handler response**           | 200-500ms             | <100ms        | 50-75% faster        |
| **Notification queue throughput**     | N/A (no queue)        | 100 notif/sec | New capability       |
| **Memory footprint**                  | Baseline              | +5MB (cache)  | Acceptable trade-off |
| **Cache hit rate**                    | N/A                   | 95%+          | New capability       |

### Load Testing Scenarios

1. **Burst Load**: 50 concurrent chore approvals → All notifications delivered in <1s
2. **Sustained Load**: 1000 notifications over 10 minutes → No queue buildup
3. **Large Family**: 10 kids, 5 parents, 100 chores → Instant approvals
4. **Translation Stress**: 20 languages, 500 notifications → Cache handles all
5. **Failure Recovery**: 50% of notification services down → 50% still deliver instantly

---

## Dependencies & Risks

### Dependencies

✅ **None** - Uses existing Home Assistant services and async patterns

### Risks & Mitigations

| Risk                            | Probability | Impact   | Mitigation                                   |
| ------------------------------- | ----------- | -------- | -------------------------------------------- |
| Translation cache memory growth | Medium      | Low      | TTL expiration + LRU eviction                |
| Queue backpressure (overwhelm)  | Low         | Medium   | Max queue size + backpressure handling       |
| Lock contention (performance)   | Low         | Low      | Fine-grained locks per (action, kid, entity) |
| Migration issues (v42→v43)      | Low         | High     | Extensive testing, rollback plan             |
| Backward compatibility breaks   | Very Low    | Critical | Feature flags, fallback to old methods       |

---

## Testing Strategy

### Test Pyramid

```
         ┌─────────────┐
         │   E2E (5)   │  Full flow tests (approval → notification → action)
         └─────────────┘
       ┌───────────────────┐
       │ Integration (20)  │  Component interaction tests
       └───────────────────┘
    ┌────────────────────────┐
    │   Unit Tests (100+)    │  Individual component tests
    └────────────────────────┘
```

### Coverage Requirements

| Module                         | Target | Critical Paths                    |
| ------------------------------ | ------ | --------------------------------- |
| notification_manager.py        | 98%+   | Concurrent delivery, retry logic  |
| notification_action_handler.py | 100%   | All action types, race conditions |
| notification_queue.py          | 95%+   | Priority handling, batching       |
| translation_cache.py           | 95%+   | Cache hits, expiry, fallback      |
| delivery_tracker.py            | 90%+   | History tracking, metrics         |

### Test Scenarios (from test fixtures)

Use existing scenarios:

- `scenario_minimal_starblumsons` (1 kid, 1 parent) - Basic tests
- `scenario_shared_starblumsons` (3 kids, 2 parents) - Concurrent tests
- `scenario_full_starblumsons` (3 kids, 5 parents) - Load tests

---

## Success Criteria

### Functional Requirements

- [ ] All notification types supported (18+ types)
- [ ] Concurrent parent notification working
- [ ] Translation cache operational (95%+ hit rate)
- [ ] User preferences respected (per-type filtering)
- [ ] Rate limiting active (prevents spam)
- [ ] Delivery tracking functional (history + metrics)
- [ ] Zero race conditions (proven by tests)

### Non-Functional Requirements

- [ ] 70%+ performance improvement (multi-parent)
- [ ] 95%+ test coverage
- [ ] Zero breaking changes (backward compatible)
- [ ] Schema migration successful (v42 → v43)
- [ ] Memory footprint acceptable (<10MB increase)
- [ ] Comprehensive documentation (code + user guide)

### User Experience

- [ ] Approvals feel instant (<100ms perceived)
- [ ] No notification spam (rate limiting works)
- [ ] Granular control over notification types
- [ ] Clear delivery status in diagnostics
- [ ] No lost notifications (retry logic works)

---

## Documentation Requirements

### Code Documentation

- [ ] All classes have comprehensive docstrings
- [ ] All methods have type hints + docstrings
- [ ] Complex algorithms explained with comments
- [ ] Architecture diagram in code comments

### User Documentation

- [ ] Update README with notification features
- [ ] Add wiki page: "Notification System Overview"
- [ ] Add wiki page: "Customizing Notifications"
- [ ] Add wiki page: "Troubleshooting Notifications"
- [ ] Update ARCHITECTURE.md with new components

### Developer Documentation

- [ ] Update DEVELOPMENT_STANDARDS.md
- [ ] Add notification system design doc
- [ ] Add testing guide for notifications
- [ ] Add performance tuning guide

---

## Post-Implementation Review

### Metrics to Track (30 days post-release)

1. **Performance**: Average notification latency (target: <500ms)
2. **Reliability**: Notification success rate (target: 98%+)
3. **Usage**: Notification preference adoption (% users customizing)
4. **Issues**: Bug reports related to notifications (target: <5)
5. **Performance**: Translation cache hit rate (target: 95%+)

### Feedback Collection

- [ ] User survey: Notification satisfaction (1-5 scale)
- [ ] GitHub issues: Monitor notification-related reports
- [ ] Diagnostics: Analyze delivery failure patterns
- [ ] Performance logs: Review PERF: log entries

### Iteration Planning

Based on feedback:

- **v0.7.0**: Advanced features (push notification customization, rich media)
- **v0.8.0**: ML-based notification timing optimization
- **v0.9.0**: Integration with external notification services (Telegram, Discord)

---

## References

| Document                                                                               | Relevance                       |
| -------------------------------------------------------------------------------------- | ------------------------------- |
| [ARCHITECTURE.md](../ARCHITECTURE.md)                                                  | Data model, storage patterns    |
| [DEVELOPMENT_STANDARDS.md](../DEVELOPMENT_STANDARDS.md)                                | Code conventions, patterns      |
| [CODE_REVIEW_GUIDE.md](../CODE_REVIEW_GUIDE.md)                                        | Quality standards               |
| [AGENT_TEST_CREATION_INSTRUCTIONS.md](../../tests/AGENT_TEST_CREATION_INSTRUCTIONS.md) | Test patterns                   |
| [NOTIF_ANALYSIS_1.md](./NOTIF_ANALYSIS_1.md)                                           | Performance analysis (archived) |
| [NOTIF_ANALYSIS2.md](./NOTIF_ANALYSIS2.md)                                             | Reliability analysis (archived) |

---

## Decisions & Completion Check

### Key Architectural Decisions

1. **Manager Pattern**: Centralized NotificationManager vs distributed responsibility

   - **Decision**: Manager pattern for better observability and control

2. **Caching Strategy**: In-memory vs Redis vs file-based

   - **Decision**: In-memory with TTL (simplicity, no external deps)

3. **Queue Implementation**: asyncio.Queue vs priority queue library

   - **Decision**: asyncio.PriorityQueue (built-in, lightweight)

4. **Backward Compatibility**: Feature flags vs big-bang migration

   - **Decision**: Feature flags with gradual adoption

5. **Storage Impact**: New schema version vs extend existing
   - **Decision**: New version (v43) for clean separation

### Completion Requirements

**Phase Sign-Off**:

- [ ] Phase 1: All constants defined, types created, schema migration tested
- [ ] Phase 2: Manager operational, concurrent delivery working, tests pass
- [ ] Phase 3: Action handler hardened, zero race conditions, all constants used
- [ ] Phase 4: Preferences working, rate limiting active, batching functional
- [ ] Phase 5: Tracking enabled, sensors created, diagnostics complete
- [ ] Phase 6: 95%+ coverage, all tests pass, performance benchmarks met

**Final Approval Checklist**:

- [ ] All phases completed and signed off
- [ ] Zero critical bugs (blocking issues)
- [ ] Performance targets met (70%+ improvement)
- [ ] Test coverage ≥95%
- [ ] Documentation complete (code + user + dev)
- [ ] Migration tested on real data (backup → migrate → restore)
- [ ] Rollback procedure validated
- [ ] User acceptance testing (5+ users)

**Release Criteria**:

- [ ] All completion requirements met
- [ ] Code review passed (2+ reviewers)
- [ ] Integration tests pass in HA dev environment
- [ ] No regressions in existing functionality
- [ ] Performance regression tests pass
- [ ] Release notes written
- [ ] Wiki documentation published

---

## Appendix: Example Implementations

### A. Concurrent Parent Notification (Before/After)

**Before** (Sequential - 1500ms for 5 parents):

```python
async def _notify_parents_translated(...):
    for parent_id, parent_info in self.parents_data.items():
        translations = await load_notification_translation(...)  # 10ms each
        await async_send_notification(...)  # 300ms each
    # Total: 5 × (10ms + 300ms) = 1550ms
```

**After** (Concurrent - 450ms for 5 parents):

```python
async def send_to_parents_concurrent(...):
    translations = self.get_cached_translation(lang)  # 1ms (cached)
    tasks = [
        self._send_to_parent(parent_id, translations, ...)
        for parent_id in eligible_parents
    ]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    # Total: max(300ms) + 1ms = 301ms (5x faster!)
```

### B. Race Condition Protection

**Before** (Vulnerable):

```python
# notification_action_handler.py
coordinator.approve_chore(kid_id, chore_id)  # No lock
# Double-click → Both execute → Double approval
```

**After** (Protected):

```python
# notification_action_handler.py
async with coordinator._get_action_lock("approve_chore", kid_id, chore_id):
    # Check if already approved (inside lock)
    if coordinator.is_approved(kid_id, chore_id):
        return  # Skip duplicate
    coordinator.approve_chore(kid_id, chore_id)
# Second click waits for lock → sees already approved → skips
```

### C. Translation Cache

**Before** (N+1 Problem):

```python
for parent in parents:
    translations = await load_from_file(parent.language)  # File I/O each time
```

**After** (Cached):

```python
# On startup
await notification_manager._preload_translations()  # Load all once

# Per notification
translations = notification_manager.get_cached_translation(lang)  # Memory lookup
```

---

**End of Plan** - Ready for implementation by KidsChores Plan Agent
