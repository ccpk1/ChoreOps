# Calendar & RRULE Analysis: Time Handling Impact

## Current Calendar Special Time Handling

The calendar.py has **three distinct time representations** for calendar events:

### 1. **Timed Events (1-hour blocks)** - For Chores WITH Due Dates

```python
# Lines 230-235: _generate_non_recurring_with_due_date()
e = CalendarEvent(
    summary=summary,
    start=due_dt,                              # Actual due time (e.g., 2026-01-19 14:30:00)
    end=due_dt + datetime.timedelta(hours=1), # +1 hour to create block
    description=description,
)
```

**Applies to**:

- Non-recurring chores with due_date set
- Recurring chores with due_date set (weekly, monthly, etc.)
- DAILY_MULTI with time slots (15-minute events, not 1-hour)

**Semantics**: "This chore is due at 2:30 PM on Jan 19, and I'm visualizing it as a 1-hour window"

**Current Implementation**: Uses `dt_next_schedule()` and `dt_add_interval()` to calculate next occurrence time

---

### 2. **Full-Day Blocks (00:00 - 23:59)** - For Chores WITHOUT Due Dates

```python
# Lines 267-271: _generate_non_recurring_without_due_date()
day_start = datetime.datetime.combine(current.date(), datetime.time(0, 0, 0), tzinfo=local_tz)
day_end = datetime.datetime.combine(current.date(), datetime.time(23, 59, 59), tzinfo=local_tz)
e = CalendarEvent(
    summary=summary,
    start=day_start,   # 00:00:00
    end=day_end,       # 23:59:59
    description=description,
)
```

**Applies to**:

- Non-recurring chores WITHOUT due_date
- DAILY recurring without due_date
- Custom intervals without due_date

**Semantics**: "This chore can be done any time today"

---

### 3. **Multi-Day Blocks** - For Weekly/Monthly Recurring WITHOUT Due Dates

```python
# Lines 421-426: _generate_recurring_weekly_biweekly_without_due_date()
e = CalendarEvent(
    summary=summary,
    start=start_block.date(),                              # Monday of week
    end=end_block.date() + datetime.timedelta(days=1),    # Sunday+1 (all-day format)
    description=description,
)
```

**Applies to**:

- WEEKLY recurring without due_date → Monday-Sunday blocks
- BIWEEKLY recurring without due_date → 2-week blocks
- MONTHLY recurring without due_date → Full month blocks
- QUARTER recurring → Full quarter blocks

**Semantics**: "This chore belongs to this week/month/quarter"

---

## RRULE String Semantics vs Calendar Time Blocks

### Key Insight: RRULE describes RECURRENCE, not EVENT DURATION

```
FREQ=WEEKLY;INTERVAL=1;BYDAY=MO,WE,FR
↑ Describes when occurrences happen
↑ Does NOT describe how long each event lasts
```

**Problem**: `to_rrule_string()` currently returns only the recurrence pattern. It does NOT encode:

- Whether the chore has a due_date (timed 1-hour events)
- Whether it's a full-day event (00:00-23:59)
- Whether it's a multi-day block (week/month)

---

## Impact Analysis: How RRULE Will Affect Calendar Entries

### Scenario A: Timed Event (WITH Due Date)

**Current Implementation**:

```python
# calendar.py line 329-335
current_due = due_dt  # e.g., 2026-01-19 14:30:00 UTC
while current_due <= window_end:
    e = CalendarEvent(
        start=current_due,
        end=current_due + timedelta(hours=1),
        description=description,
    )
    # Calculate next using dt_add_interval() or dt_next_schedule()
    current_due = kh.dt_next_schedule(...)
```

**With RRULE Integration**:

```python
# Using RecurrenceEngine.get_occurrences()
engine = RecurrenceEngine(schedule_config)
occurrences = engine.get_occurrences(start=window_start, end=window_end, limit=100)

for occurrence_utc in occurrences:
    e = CalendarEvent(
        start=occurrence_utc,
        end=occurrence_utc + timedelta(hours=1),  # Still 1-hour block
        description=description,
        # NEW: Add RRULE for iCal compatibility
        rrule=engine.to_rrule_string(),  # e.g., "FREQ=WEEKLY;INTERVAL=1"
    )
```

**Impact**: ✅ **SAME** - RRULE only affects iCal export, not UI visualization. Calendar still shows 1-hour blocks.

---

### Scenario B: Full-Day Event (WITHOUT Due Date)

**Current Implementation**:

```python
# calendar.py line 390-395
current = gen_start
while current <= cutoff:
    day_start = datetime.combine(current.date(), time(0, 0, 0), tzinfo=local_tz)
    day_end = datetime.combine(current.date(), time(23, 59, 59), tzinfo=local_tz)
    e = CalendarEvent(start=day_start, end=day_end, ...)
    current += timedelta(days=1)
```

**With RRULE Integration**:

```python
# Still needs manual iteration because we MUST show 00:00-23:59
engine = RecurrenceEngine(schedule_config_daily)
occurrences = engine.get_occurrences(start=window_start, end=window_end, limit=100)

for occurrence_utc in occurrences:
    occurrence_local = dt_util.as_local(occurrence_utc)
    day_start = datetime.combine(occurrence_local.date(), time(0, 0, 0), tzinfo=local_tz)
    day_end = datetime.combine(occurrence_local.date(), time(23, 59, 59), tzinfo=local_tz)
    e = CalendarEvent(
        start=day_start,
        end=day_end,
        rrule=engine.to_rrule_string(),  # e.g., "FREQ=DAILY;INTERVAL=1"
    )
```

**Impact**: ✅ **SAME** - Calendar shows full-day events. RRULE describes the daily recurrence.

---

### Scenario C: Multi-Day Block (Weekly/Monthly WITHOUT Due Date)

**Current Implementation**:

```python
# calendar.py line 423-425
e = CalendarEvent(
    start=start_block.date(),                              # Mon 1/20
    end=end_block.date() + timedelta(days=1),             # Sun 1/26 + 1 day (all-day format)
    description=description,
)
```

**With RRULE Integration**:

```python
# This is tricky - multi-day blocks don't fit neatly into RRULE
# RRULE = "FREQ=WEEKLY;INTERVAL=1" means "happens every week"
# But the calendar event spans 7 days

# Options:
# 1. Keep current multi-day block visualization + RRULE for iCal
e = CalendarEvent(
    start=start_block.date(),         # Mon 1/20
    end=end_block.date() + timedelta(days=1),  # Sun 1/26 + 1
    rrule="FREQ=WEEKLY;INTERVAL=1",  # Describes weekly recurrence
)

# 2. OR split into individual day events (more granular but different UX)
# Not recommended - changes existing behavior
```

**Impact**: ⚠️ **POTENTIAL MISMATCH** - Multi-day blocks + RRULE creates semantic ambiguity:

- RRULE says "happens weekly"
- Calendar shows "Mon-Sun block"
- iCal consumer might interpret this as "single 7-day event that repeats weekly" vs "7 separate daily events"

---

## Critical Design Decision: How to Handle RRULE in Calendar Events

### Option 1: Add RRULE Only for Timed Events (RECOMMENDED)

```python
# For chores WITH due_date (timed events)
if chore_has_due_date:
    e = CalendarEvent(
        start=due_dt,
        end=due_dt + timedelta(hours=1),
        rrule=engine.to_rrule_string(),  # Include RRULE
    )
else:
    # For chores WITHOUT due_date (full-day or multi-day blocks)
    e = CalendarEvent(
        start=day_start,
        end=day_end,
        rrule="",  # Omit RRULE for full-day events
    )
```

**Rationale**:

- Timed events map cleanly to RRULE (each occurrence is same 1-hour block)
- Full-day blocks have ambiguous RRULE representation
- Many iCal viewers handle all-day events differently (they expect `VALUE=DATE` not `VALUE=DATE-TIME`)

---

### Option 2: Add RRULE to All Events (Comprehensive but Risky)

```python
e = CalendarEvent(
    start=event_start,
    end=event_end,
    rrule=engine.to_rrule_string(),  # Always include
)
```

**Risk**: Some iCal viewers might misinterpret all-day event RRULE strings, causing display issues.

---

## Special Cases: DAILY_MULTI and Period-Ends

### DAILY_MULTI (Time Slots)

```python
# calendar.py line 550+
# "Feed pets" at 08:00 and 17:00 creates TWO separate events per day
e1 = CalendarEvent(start=slot1_08am, end=slot1_08am + timedelta(minutes=15))
e2 = CalendarEvent(start=slot2_05pm, end=slot2_05pm + timedelta(minutes=15))
```

**RRULE Applicability**: ❌ **NOT APPLICABLE**

- `to_rrule_string()` returns `""` for DAILY_MULTI (not RFC 5545 representable)
- Each slot is already a separate calendar event
- Omit RRULE for these events

---

### Period-End Frequencies

```python
# PERIOD_MONTH_END → "Chore due last day of every month at 23:59"
# to_rrule_string() returns: "FREQ=MONTHLY;BYMONTHDAY=-1"

# This IS representable but special case:
# - Event might show as timed (due at 23:59) or full-day depending on interpretation
# - RRULE string is correct for iCal
```

**Recommendation**: Include RRULE for period-end timed events, as they map cleanly.

---

## Implementation Approach for Phase 2d

### Step 1: Identify Event Categories

```python
def _categorize_event(chore_info):
    has_due_date = chore_info.get(const.DATA_CHORE_DUE_DATE) is not None
    is_daily_multi = chore_info.get(const.DATA_CHORE_FREQUENCY) == const.FREQUENCY_DAILY_MULTI
    is_recurring = chore_info.get(const.DATA_CHORE_FREQUENCY) not in (
        const.FREQUENCY_NONE,
        const.FREQUENCY_DAILY_MULTI,
    )

    if is_daily_multi:
        return "DAILY_MULTI"  # No RRULE
    if has_due_date:
        return "TIMED"  # Include RRULE
    if is_recurring and not has_due_date:
        return "FULLDAY_OR_BLOCK"  # RRULE optional
    return "NONTIMED"  # No RRULE
```

### Step 2: Generate RRULE Conditionally

```python
for event in generate_events(...):
    if event_category == "TIMED":
        engine = RecurrenceEngine(schedule_config)
        rrule_str = engine.to_rrule_string()
        event.rrule = rrule_str
    elif event_category == "FULLDAY_OR_BLOCK":
        # Option: Include RRULE with caveat about all-day interpretation
        engine = RecurrenceEngine(schedule_config)
        rrule_str = engine.to_rrule_string()
        event.rrule = rrule_str  # or omit if risky
    else:
        event.rrule = ""  # DAILY_MULTI or no recurrence
```

### Step 3: Testing

```python
# Verify RRULE strings are valid by parsing them back
from dateutil.rrule import rrulestr

rrule_str = engine.to_rrule_string()
if rrule_str:
    try:
        parsed = rrulestr(rrule_str, dtstart=engine._base_date)
        # Verify first few occurrences match engine calculations
    except Exception:
        # Invalid RRULE - log error
```

---

## Summary

| Event Type             | Current Duration    | RRULE Handling | Impact                                        |
| ---------------------- | ------------------- | -------------- | --------------------------------------------- |
| Timed (with due date)  | 1 hour              | ✅ Include     | No visual change, improves iCal export        |
| Full-day (no due date) | 00:00-23:59         | ⚠️ Optional    | Ambiguous interpretation in some iCal viewers |
| Multi-day block        | Mon-Sun             | ⚠️ Omit        | Safer to omit, reduces ambiguity              |
| DAILY_MULTI            | 15 minutes per slot | ❌ Omit        | Not RFC 5545 representable                    |
| Period-end timed       | 1 hour at 23:59     | ✅ Include     | Correct RFC 5545 representation               |

**Recommendation**: Start with RRULE for **timed events only** (with due dates). Test iCal export. Consider adding RRULE to full-day events in Phase 3 after user feedback.
