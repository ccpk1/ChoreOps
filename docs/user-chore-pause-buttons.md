# Feature: Pause / Resume Chore Buttons (per user)

## Summary
Adds two button entities per user — **Pause Chores** and **Resume Chores** — for
quick "sick day" style control from any dashboard or the admin view. They wrap
the existing pause engine, so behaviour is identical to the `pause_user_chores`
service: while a user is paused, no overdue/missed stats accumulate and rotation
chores advance past that user. Pressing Resume clears the pause.

## How it works
- New entity class `UserChoresPauseButton` in `button.py` (one Pause + one Resume
  instance created per user in `async_setup_entry`).
- `async_press()` calls the existing
  `ChoreManager.set_user_chores_paused(assignee_id, paused=...)` — no new pause
  logic, no storage changes, no migration.
- Reuses the existing approver/assignee device, translation, and icon patterns.

## Files changed
- `const.py` — button UID suffixes, translation keys, and icons.
- `button.py` — `UserChoresPauseButton` class + setup wiring.
- `translations/en.json` — button entity names.

## Notes / follow-ups
- These are momentary buttons (Pause / Resume), since the integration has no
  switch platform. A single toggle switch would require adding a switch platform.
- The buttons do not gate on approver authorization; pausing is non-destructive
  and already exposed via the service. Add an auth check if stricter control is
  wanted.
- **Next update (separate PR):** recurring, time-of-day scheduled pauses per user
  (e.g. every Saturday 5:00pm → Sunday) configured from the admin menu.
