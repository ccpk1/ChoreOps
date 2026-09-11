# Initiative Plan — Auto-Advance Rotation & Always-Reset Chores (Issue #255)

> **This document supersedes and replaces** the following, which may be safely deleted once this plan is reviewed:
>
> - `AUTO-ADVANCE-AND-ALWAYS-RESET_IN-PROCESS.md`
> - `AUTO-ADVANCE-AND-ALWAYS-RESET_SUP_DASHBOARD-SCOPE.md`
>
> All decisions, corrections, and traps from both are consolidated here. **No logic was reconsidered** — this is a faithful rebuild with the known stale statements corrected.

## Initiative snapshot

- **Name / Code**: Auto-Advance Rotation & Always-Reset Chores (`ISSUE-255`)
- **Target release / milestone**: v1.6.0 (TBD — confirm with owner)
- **Owner / driver(s)**: ccpk1
- **Status**: **Complete** — all five phases done and committed on `feat/issue-255-auto-advance-rotation` (choreops, choreops-dashboards, choreops-wiki). Release notes drafted for the owner to publish.

## Summary & immediate steps

| Phase / Step                                                    | Description                                                                        | % complete | Quick notes                                                                  |
| --------------------------------------------------------------- | ---------------------------------------------------------------------------------- | ---------- | ---------------------------------------------------------------------------- |
| Phase 1 – Foundation                                            | New constants + validation error key                                                | **100%**   | ✅ Lint + mypy clean. Dedup mechanism **moved to Phase 3** (must be new-criteria-scoped) |
| Phase 2 – Feature 1 (`never_overdue_clear_at_approval_reset`)    | New overdue-lane option: never overdue presentation **plus** reset at the boundary  | **100%**   | ✅ Lint + mypy clean, 317 targeted tests pass. Presentation/scan pair updated together |
| Phase 3 – Feature 2 (`rotation_simple_from_turn_holder`)         | New completion criteria: simple rotation anchored on the current turn holder        | **100%**   | ✅ Lint + mypy clean, 434 targeted tests pass. Includes boundary-advance + dedup |
| Phase 4 – Tests                                                  | Engine, manager, workflow, and boundary tests for both features plus the guard      | **100%**   | ✅ 596 targeted tests pass. Steal-anchor, advance-once and no-churn all covered |
| Phase 5 – Docs, dashboards & polish                              | Wiki, dashboard labels (canonical repo + sync), English translations, release notes | **100%**   | ✅ Wiki updated (5 pages); release notes drafted; plan moved to completed     |

1. **Key objective** – Deliver the two features requested in issue #255 as **new, opt-in** options, with **zero behaviour change** for any existing chore configuration.

2. **Summary of recent work** – Deep code review and three correction rounds against maintainer feedback completed 2026-09-11. All ambiguities (A1–A6) are now closed; decisions D1–D12 are final. This document consolidates the parent plan and the dashboard-scope supporting document into one authoritative record.

3. **Next steps (short term)** – None outstanding. Open the PR(s), then run the full test suite (`python -m pytest tests/ -v --tb=line`) as part of release validation. The release notes and issue reply are drafted for the owner to publish.

4. **Risks / blockers** – Three critical traps:
   - **(a)** Omitting the new overdue type from `can_be_overdue` (`chore_manager.py:1912`) silently loses never-overdue presentation (C1).
   - **(b)** Omitting the new completion criteria from the create-path holder initialization (`data_builders.py:1889-1905`) leaves `rotation_current_assignee_id` as `None`, breaking all advancement (C9).
   - **(c)** Placing the new dedup guard inside the debug-gated `_reset_pipeline_tracking` (`chore_manager.py:319`) means it never clears in production — rotation would advance at most once ever (C7).

5. **References** – See "Notes & follow-up" for the full reference list.

6. **Decisions & completion check**
   - **Decisions captured**: D1–D18 and resolved ambiguities A1–A6 (see "Notes & follow-up").
   - **Completion confirmation**: `[ ]` All follow-up items completed (architecture updates, cleanup, documentation, etc.) before requesting owner approval to mark initiative done.

## Tracking expectations

- **Summary upkeep**: Whoever works on the initiative must refresh the Summary section after each significant change, including updated percentages per phase, new blockers, or completed steps. Mention dates or commit references if helpful.
- **Detailed tracking**: Use the phase-specific sections below for granular progress, issues, decision notes, and action items. Do not merge those details into the Summary table—Summary remains high level.

---

## Mandatory standards — Platinum quality & repository parity

**Non-negotiable for this initiative.** Both features are additive, but additive does not mean lower quality. Every item below must hold before hand-off.

### Platinum quality scale (see `docs/QUALITY_REFERENCE.md`)

- **100% type hints** on all new and modified functions, methods, and variables. Modern union syntax (`str | None`, not `Optional[str]`). MyPy must report **zero errors** — no `# type: ignore`, no suppressions.
- **Docstrings on all public methods** introduced or touched, in the existing Google-style format used throughout `engines/` and `managers/`. Explain the *why* when the behaviour is non-obvious (e.g. why the anchor differs for the new type).
- **Test coverage ≥95%** for the new code paths. Every new branch added to `calculate_boundary_action`, `resolve_assignee_chore_state`, and `_advance_rotation` needs direct coverage — including the negative paths (invalid combinations rejected by validation).
- **No hardcoded user-facing strings.** Every new label comes from a `const.TRANS_KEY_*` / translation key; new error keys follow the existing `TRANS_KEY_CFOF_*` convention.
- **Lazy logging only** — `const.LOGGER.debug("...%s", value)`, never f-strings. New log lines should follow the existing `"Chore Due Date - ..."` style prefixes already used in `chore_manager.py`.
- **Constants in `const.py`** — both new enum values and any new error keys, following the established naming patterns (`DATA_*`, `TRANS_KEY_*`, `CFOP_ERROR_*`).
- **Boundary checker must pass** — `./utils/quick_lint.sh --fix` includes the architectural boundary checks (e.g. no `homeassistant` imports in `utils/`, no direct `_data` writes outside managers).
- **Concision in comments** — one short line stating a non-obvious constraint, or none. No comments restating the code, no section-divider comments, no references to prior behaviour.

### Translation files — edit `en*` ONLY

**Hard rule: only `en*.json` files are ever hand-edited. Every other locale is owned by the translation pipeline (Crowdin). Never add placeholder keys to `de.json`, `fr.json`, or any other non-English file.**

1. Edit `custom_components/choreops/translations/en.json` **directly**.
   - There is **no `strings.json`** in this repo and **no `script.translations`** tooling. That is the Home Assistant *core* workflow and does not apply to a custom integration.
2. Do **not** touch any other file in `translations/`.
3. Confirm the option labels render (not raw enum values) and that `en.json` contains no orphaned keys.

> Several enums appear in **two** blocks in `en.json` — a flow `options` block and a sensor `state` block. Add new keys to **both**, or the label renders as a raw value on one surface.

New keys required (both features):

- `overdue_handling_type.options.never_overdue_clear_at_approval_reset`
- `completion_criteria.options.rotation_simple_from_turn_holder`
- One new validation error key for Phase 2 rule 13 (plus any additional compatibility error key from Phase 3).

> `translations/en.json` is what tests and runtime load, so it must be updated before running tests.

### Dashboard parity — REQUIRED, but MINIMAL scope

**Source-of-truth direction (do not edit both by hand):**

| Role                     | Location                                                                   | Action                                              |
| ------------------------ | -------------------------------------------------------------------------- | --------------------------------------------------- |
| **Canonical (source)**   | `/workspaces/choreops-dashboards` (`templates/`, `translations/`, `preferences/`, `dashboard_registry.json`) | ✏️ **Edit here**                                     |
| **Vendored (generated)** | `custom_components/choreops/dashboards/`                                    | ⛔ **Do not hand-edit** — regenerated by sync        |

Sync mechanism (`utils/sync_dashboard_assets.py`, `_default_canonical_root()` resolves to the sibling `choreops-dashboards` directory):

```bash
python utils/sync_dashboard_assets.py           # canonical → vendored
python utils/sync_dashboard_assets.py --check   # verify parity
```

> ✅ The **pre-existing** mismatch on `templates/zh-Hans_dashboard.json` was **resolved by the Phase 2 sync** (the vendored copy was stale; the canonical committed file is now mirrored). Both copies now hash identical. This is an accepted side effect of the one-way sync, not a scope change.

**Corrected behaviour (supersedes earlier claims):** a missing dashboard label key does **not** render an error token. Both lookups degrade gracefully to a title-cased raw value:

| Lookup                              | Location                                                  | Missing-key result                |
| ----------------------------------- | --------------------------------------------------------- | --------------------------------- |
| `completion_type_display`           | `admin-peruser-v1.yaml:1497`                              | `"Rotation Simple From Turn Holder"` |
| `overdue_handling_display`          | `admin-peruser-v1.yaml:1628`, `admin-shared-v1.yaml:1696` | `"Never Overdue Clear At Approval Reset"` |

Nothing *breaks* without the dashboard change — it degrades to unpolished text. That is why this work is **labelling polish plus verification**, not a compatibility fix, and why it stays minimal.

**Minimal required dashboard work:**

1. Add the two new labels to the canonical `translations/en_dashboard.json` — **`en*` only**; all other locales are pipeline-owned.
2. Add the new overdue key to the hardcoded `overdue_handling_map` in both canonical admin templates:
   - `templates/admin-peruser-v1.yaml` — map begins at `:1522`
   - `templates/admin-shared-v1.yaml` — map begins at `:1590`
3. Run `python utils/sync_dashboard_assets.py`, then `--check` (expect the pre-existing `zh-Hans_dashboard.json` mismatch to be the only one reported).
4. **Verification only — no template edit required for rotation** (see C10).

**Explicitly NOT required:** rotation controls in the classic (`admin-*-kidschores-classic.yaml`) or user templates — `set_rotation_turn` exists only in the two admin v1 templates (verified in both the canonical and vendored copies).

**Do not** refactor, restyle, or restructure any template.

---

## Verified context (read before implementing)

These findings were confirmed by code trace on 2026-09-11 and are load-bearing for the plan.

### C1 — The 5-minute periodic scan persists `OVERDUE`

`_on_periodic_update` (`managers/chore_manager.py:470`) → `_process_overdue` (called at `:525`, defined `:2073`) persists `CHORE_STATE_OVERDUE` via `ChoreEngine.calculate_transition(action=CHORE_ACTION_OVERDUE)`. So by midnight an uncompleted past-due chore is **`OVERDUE`, not `PENDING`** — for every "relaxed" overdue type. `never_overdue` is the exception because `can_be_overdue` is `False` (`chore_manager.py:1912`).

Consequence: Feature 1's new option **must** be excluded from `can_be_overdue` — otherwise the chore is persisted `OVERDUE` and never reaches FSM P5.5. This is the single highest-risk item in the plan.

### C2 — Midnight boundary decision matrix (uncompleted rotation chore, `at_midnight_*`)

| `overdue_handling_type`     | State at midnight | Boundary action      | Advances turn?     |
| --------------------------- | ----------------- | -------------------- | ------------------ |
| `never_overdue`             | pending           | skip                 | no                 |
| `at_due_date`               | overdue           | hold                 | no                 |
| `clear_immediate_on_late`   | overdue           | skip                 | no                 |
| `clear_at_approval_reset`   | overdue           | reset_and_reschedule | no                 |
| `clear_and_mark_missed`     | overdue           | reset_and_reschedule | no (+ missed)      |
| `mark_missed_and_lock`      | missed            | reset_and_reschedule | **yes** (+ missed) |
| `allow_steal`               | overdue           | skip                 | no                 |
| **NEW option**              | **pending**       | **reset_and_reschedule** | no (see C5)    |

**The hole**: no option resets *and* advances a non-punitive uncompleted chore. `mark_missed_and_lock` is the only row that advances — and it records a missed stat, which contradicts the requester's stated goal.

### C3 — Due-boundary gate already provides "only after the due date"

Midnight inclusion (`managers/chore_manager.py:1927-1934`):

```python
if chore_due_utc is None or now_utc >= chore_due_utc:
    include_in_reset = True
```

The comparison is **inclusive**, so a chore due at exactly 12:00 AM is not overdue at 12:00 AM and **is** included in that pass. Changeover day is therefore governed by the due **time**:

| Due time (Sat) | Included at   | Changeover |
| -------------- | ------------- | ---------- |
| 12:00 AM       | Sat 12:00 AM  | Saturday   |
| 6:00 PM        | Sun 12:00 AM  | Sunday     |
| 11:59 PM       | Sun 12:00 AM  | Sunday     |

Users wanting a Saturday-due chore should use 11:59 PM; 12:00 AM makes the chore due at the *start* of Saturday (separately reported odd behaviour; system is technically correct). **Out of scope for this initiative.**

Polling offset (pass may run 00:03/00:05) is a separate item and must not be folded into this work.

### C4 — No backlog accumulation on reschedule

`_calculate_next_due_date_for_chore` (`chore_manager.py:6632`) → `calculate_next_due_date_from_chore_info` (`engines/schedule_engine.py:1187`) uses `require_future=True`. A chore missed for N cycles reschedules to the **next occurrence after now** — one hop, not N. Confirmed for daily and weekly. This is what makes the new option safe: a chore can be ignored indefinitely and still land on a correct future date.

Non-issue: FSM P5.5 uses `now > due_date` (strict) while the gate uses `now >= due` (inclusive). In the single-tick overlap, P7 returns derived `due` anyway, so presentation is consistent and no overdue flash occurs.

### C5 — The boundary reset must ADVANCE for the new chore type (corrected 2026-09-11)

**Original claim (wrong):** "Feature 1 resets… does not advance; Feature 2 changes only the anchor."

**Verified gap:** for a rotation chore that was **never completed**, **neither** advance site fires:

| Site | Guard | Fires for a never-completed chore? |
| ---- | ----- | ---------------------------------- |
| `_execute_boundary_reset_plan` | `assignee_state == CHORE_STATE_APPROVED` | ❌ state is PENDING |
| `_transition_chore_state` (`:5151`) | `if completed_by_assignee_id:` | ❌ `completed_by` absent |

`auto_approve_pending` only converts pending **claims**; it does not create a completion. So Feature 1 + Feature 2 as originally specified would reset the chore nightly while leaving the turn **frozen** — failing issue #255.

**Owner decision (approved 2026-09-11):** for the new criteria, the **boundary reset itself advances** the turn from the holder, regardless of completion state. This is the "always advance rotation + always reset" pairing described in the issue thread.

### C6 — Two advance call sites, currently idempotent

| Site                                                              | Covers                                                                              |
| ----------------------------------------------------------------- | ----------------------------------------------------------------------------------- |
| `_execute_boundary_reset_plan` (`chore_manager.py:2791-2826`)      | `APPROVED` explicitly; `MISSED` + `mark_missed_and_lock` + midnight explicitly       |
| `_transition_chore_state` (`:5113-5120`) via `_apply_reset_action` | **`OVERDUE`** — an assignee can be persisted OVERDUE while approved-in-period        |

`_derive_boundary_assignee_state` (`:2583-2609`) returns explicit `OVERDUE` **before** checking `chore_is_approved_in_period`, which is why site 1's `== APPROVED` guard misses it and site 2 is required.

Today both sites resolve the **same** anchor (the completer) and compute an identical result, making the second call an **idempotent no-op**. That duplicate computation is a genuine latent inefficiency — and it is why nothing has broken. **Deleting either site loses coverage**, so the fix is a guard, not a deletion.

### C7 — Existing per-tick guard is debug-only

`_track_state_modification` (`chore_manager.py:296`) and `_reset_pipeline_tracking` (`:319`) implement a "single state per (assignee, chore) per tick" invariant, but:

```python
DEBUG_PIPELINE_GUARDS: Final = False   # const.py:56
```

- It is **disabled by default**.
- It only **logs a warning** — it does not prevent.
- `_reset_pipeline_tracking` clears its set **only when the flag is True**.

**Critical trap**: the new advance guard must **not** be placed inside the debug-gated `_reset_pipeline_tracking`. If it were, the set would never clear in production and rotation would advance at most once ever.

### C8 — Existing validation is stronger than first assessed

Rule 7 in `validate_chore_data` (`data_builders.py:1517`) already restricts the analogous existing option:

```python
if overdue_handling == const.OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_AT_APPROVAL_RESET:
    valid_reset_types = {AT_MIDNIGHT_ONCE, AT_MIDNIGHT_MULTI, UPON_COMPLETION}
    if approval_reset not in valid_reset_types:
        errors[...] = const.TRANS_KEY_CFOF_INVALID_OVERDUE_RESET_COMBINATION
```

`manual` is already excluded. See "Resolved: open item 2" in Notes & follow-up.

### C9 — Create path must initialize the holder

`build_chore` (`data_builders.py:1889-1905`) sets `rotation_current_assignee_id` to the first assignee **only on create** and **only** for `rotation_simple` / `rotation_smart` / `rotation_primary_standby`. A new criteria omitted here gets `None` → the anchor resolver has nothing to anchor on → **all advancement silently breaks**. Critical.

### C10 — Dashboard rotation controls activate automatically via a substring check

Both admin templates detect rotation with a **substring** test, not equality:

```jinja
{%- set is_rotation_type = 'rotation' in completion_type_key -%}
```

- `admin-peruser-v1.yaml:1585`
- `admin-shared-v1.yaml:1653`

Because `rotation_simple_from_turn_holder` **contains** `rotation`, `is_rotation_type` resolves `True` automatically — **no template edit is needed**. These all activate for the new type:

| Feature                                                                              | Location (`admin-peruser-v1.yaml`) |
| ------------------------------------------------------------------------------------ | ---------------------------------- |
| Turn-holder display                                                                  | `:1589`                            |
| Rotation-order grid                                                                  | `:1647-1666`                       |
| Rotation info block                                                                  | `:2204-2338`                       |
| Grid-area display gate                                                               | `:2403-2406`                       |
| **Admin cards** — `set_rotation_turn`, `open_rotation_cycle`, `reset_rotation`        | `:2064-2255`                       |

> **Load-bearing naming**: the `rotation` substring in the approved name (A1) drives this gate **and** the row icon (`type.includes('rotation')` in `button_card_template_chore_row_kids_v1.yaml:147`). It is **not** cosmetic — do not rename the value to anything lacking `rotation`.

**Only two templates** carry `set_rotation_turn` per repo (`admin-peruser-v1.yaml`, `admin-shared-v1.yaml`) — verified by repository-wide search in both the canonical and vendored copies. Classic and user templates have no rotation controls and need no change.

---

## Detailed phase tracking

### Phase 1 – Foundation

- **Goal**: Add the constants and validation error keys both features depend on, and land the rotation-advance dedup guard as a standalone, behavior-preserving optimization that de-risks Phase 3.

- **Steps / detailed work items**

  1. **Add Feature 1 value** in `custom_components/choreops/const.py` near line 1572:
     - `OVERDUE_HANDLING_NEVER_OVERDUE_CLEAR_AT_APPROVAL_RESET: Final = "never_overdue_clear_at_approval_reset"`
     - Register it in `OVERDUE_HANDLING_TYPE_OPTIONS` (`const.py:1586-1605`).
     - Const name length is precedented by `OVERDUE_HANDLING_AT_DUE_DATE_CLEAR_IMMEDIATE_ON_LATE`.
     - ⚠️ Do **not** add it to `_RELAXED_OVERDUE_TYPES` (`engines/chore_engine.py:45-53`) — that is exactly what would make it present as overdue.

  2. **Add Feature 2 value** in `const.py` near line 1536:
     - `COMPLETION_CRITERIA_ROTATION_SIMPLE_FROM_TURN_HOLDER: Final = "rotation_simple_from_turn_holder"`
     - Register it in `COMPLETION_CRITERIA_OPTIONS` (`const.py:1539-1550`).
     - ⚠️ The string **must** start with `rotation` — see C10. ✅ Satisfied by the approved name.

  3. **Add translation error keys** in `const.py` for the new validation rules (Phase 2 step 6 and Phase 3 step 4), following the `TRANS_KEY_CFOF_*` convention alongside `TRANS_KEY_CFOF_INVALID_OVERDUE_RESET_COMBINATION`.

  4. **Add the dedup guard** in `managers/chore_manager.py`:
     - Declare `self._pipeline_advanced_chores: set[str] = set()` in `__init__` near `_pipeline_modified_pairs` (`chore_manager.py:169`).
     - Clear it **unconditionally** at the start of `_on_midnight_rollover` (`chore_manager.py:342`, next to the existing `_reset_pipeline_tracking()` call) **and** `_on_periodic_update` (`chore_manager.py:470`).
     - ⚠️ **Do not** reuse or nest inside `_reset_pipeline_tracking` (`:319`) — it is gated by `DEBUG_PIPELINE_GUARDS` (C7).
     - Add a small helper (e.g. `_mark_rotation_advanced(chore_id) -> bool`) that returns `True` the first time a chore is advanced in a pass and `False` thereafter.

  5. **Wire the guard into both advance sites** so the change is behavior-preserving on its own:
     - `_execute_boundary_reset_plan` (`chore_manager.py:2791-2805`).
     - `_transition_chore_state` (`chore_manager.py:5113-5120`).
     - For **existing** criteria both sites resolve the same anchor, so suppressing the second is behaviourally a no-op — a pure optimisation removing the duplicate computation (C6).

  6. **Verify no behaviour change**: run the Phase 4 step 1 targeted regression suite with the guard in place *before* any new features land. This is the gate for the rest of the initiative.

- **Key issues**
  - C7: the guard set must clear unconditionally, not only in debug mode.
  - C6: do **not** implement this by deleting a call site — the OVERDUE path would lose its only advance.

---

### Phase 2 – Feature 1: `never_overdue_clear_at_approval_reset`

- **Goal**: Give users a never-overdue chore that still resets to a fresh cycle at each approval boundary, without ever becoming overdue and without punitive stats.

- **Steps / detailed work items**

  1. **Boundary category** — `engines/chore_engine.py:1600-1602` (the `CHORE_STATE_PENDING` short-circuit inside `calculate_boundary_action`, defined at `:1571`; `should_reschedule` is computed at `:1598`). Return `"reset_and_reschedule"` for the new type when `should_reschedule` is true, else `"skip"`.
     - No signature change is required — `overdue_handling` is already a parameter.
     - The `should_reschedule` condition is defensive only once validation (step 6) is in place.

  2. **FSM presentation** — `engines/chore_engine.py:865-873` (P5.5). Include the new type alongside `OVERDUE_HANDLING_NEVER_OVERDUE` (checked at `:869`) so a past-due chore presents as derived `due` (claimable, never late). Keep the `never_overdue` comments accurate.

  3. **Scan exclusion** — `managers/chore_manager.py:1912`. Change `can_be_overdue = overdue_handling != OVERDUE_HANDLING_NEVER_OVERDUE` to cover both never-overdue types.
     - ⚠️ **Highest-risk item.** If omitted, the chore is persisted `OVERDUE` (C1) and step 2 is bypassed, producing exactly the behaviour users are trying to escape.

  4. **Global aggregate** — `managers/chore_manager.py:3757` (`_chore_is_past_due_never_overdue`). Include the new type so the chore-level aggregate matches the assignee-level FSM branch.

  5. **Defensive OVERDUE branch** — `engines/chore_engine.py:1642`. If a chore is somehow already `OVERDUE` (e.g. legacy data or a type change), return `"reset_and_reschedule"` for the new type rather than falling through to `"skip"`.

  6. **Validation rule 13** — add to `validate_chore_data` (`data_builders.py:1363`; place after rule 7 at `:1517`). Require **all** of:
     - a due date is present (`missing_required_due_date` is false — the existing computed flag at `:1496-1510` is reusable),
     - `recurring_frequency != FREQUENCY_NONE`,
     - `approval_reset in {AT_MIDNIGHT_ONCE, AT_MIDNIGHT_MULTI}` — **owner-approved (A3)**. `at_midnight_once` is the priority and primary use case; `at_midnight_multi` is free (the rule is a set membership). `at_due_date_*`, `upon_completion`, and `manual` are **not required** and must stay out of the set.
     - Return a new `TRANS_KEY_CFOF_*` error keyed to `CFOP_ERROR_OVERDUE_RESET_COMBO`.
     - Rationale: conditions 1–2 together make `should_reschedule` always true and `should_clear_due_date` always false, so the due date is never cleared and the re-inclusion loop is **structurally impossible** rather than merely guarded.

  7. **Service-layer enum** — `services.py:801-810` (`_OVERDUE_HANDLING_VALUES`) and `services.yaml` — the `overdue_handling:` option lists at `:1367` (create) and `:1585` (update). Add the raw value to both.

  8. **English translations** — `translations/en.json`, edited **directly** (no `strings.json` or regeneration step exists in this repo). Add the new label to **both** `overdue_handling_type` blocks: the flow `options` block around `:2110` and the sensor `state` block around `:3419`. **Do not touch any other locale file.**

  9. **Dashboard label** — canonical `translations/en_dashboard.json` (key block around `:155`) only, plus the `overdue_handling_map` insertion described in "Dashboard parity" above.

  10. **Sync dashboards** — run `python utils/sync_dashboard_assets.py` then `--check` before running tests. There is no translation regeneration step in this repo.

- **Key issues**
  - C1/C3: the presentation pair (FSM P5.5 + `can_be_overdue`) must change **together**. Changing one without the other yields either an overdue-looking chore or a chore that never resets.
  - C4: confirm in tests that a chore missed for several cycles lands on the next future occurrence, not a backlog.
  - Pre-existing observation, **out of scope**: the analogous existing options carry the same structural coupling between presentation and scan membership. Do not refactor them here.

---

### Phase 3 – Feature 2: `rotation_simple_from_turn_holder`

- **Goal**: A new completion criteria that is 100% simple rotation, with the single difference that advancement anchors on the **current turn holder** instead of the last completer — including when a different assignee steals and completes.

- **Steps / detailed work items**

  1. **Engine adapters** (D-12 — adding to these inherits claim gating, FSM P3 `not_my_turn`, paused-skip, steal, and standby for free):
     - `uses_chore_level_due_date` — `engines/chore_engine.py:650`
     - `is_rotation_mode` — `:668`
     - `is_single_claimer_mode` — `:690`
     - ⚠️ **`uses_chore_level_due_date` has three separate copies** and all three must be updated, or the new type is treated as *independent* (per-assignee due dates) in some code paths and *chore-level* in others — a silent data-shape split:
       1. `engines/chore_engine.py:650` — `ChoreEngine.uses_chore_level_due_date`
       2. `data_builders.py:1399` — local `_uses_chore_level_due_date` (used at `:1498` to pick the due-date branch during validation)
       3. `services.py:210` — `_service_uses_chore_level_due_date` (used at `:362`)
     - This is the highest-value de-duplication opportunity in this feature; see Phase 5 step 8.

  2. **Criteria transition actions** — `engines/chore_engine.py:1189` and `:1194` (`get_criteria_transition_actions`). Rotation→rotation keeps the existing turn, which is correct for this type.

  3. **Create-path holder initialization** — `data_builders.py:1898`. Add the new criteria to the `is_create` tuple.
     - ⚠️ **Highest-risk item for this feature.** Omission yields `rotation_current_assignee_id = None` and silently disables all advancement (C9).

  4. **Validation** — `data_builders.py`:
     - A **single** local `rotation_criteria` set is defined at `:1609` and consumed by **both** rule 11 (`:1613`, ≥2 assignees) and rule 12 (`:1624`, `allow_steal` compatibility). Adding the new criteria to that one set satisfies both rules.
     - **Owner-approved (A2): `allow_steal` IS permitted for the new criteria.** No separate edit is needed beyond the shared set.
     - Note rule 11 currently omits `rotation_primary_standby`; leave that as-is (pre-existing, out of scope) but ensure the new type **is** included.

  5. **Anchor resolver** — `managers/chore_manager.py:5531` (`_advance_rotation`):
     - Resolve the anchor as: the current turn holder (`DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID`) when criteria is the new type; otherwise the existing completer behaviour.
     - Prefer an explicit local variable (e.g. `anchor_assignee_id`) resolved once at the top, so the intent reads clearly and the parameter no longer silently means "completer".
     - Keep `calculate_next_turn_simple`'s `ValueError → assigned_assignees[0]` fallback intact.

  6. **Dispatch** — `managers/chore_manager.py:5574`. Route the new criteria to the `"simple"` method (mirroring `ROTATION_SIMPLE`), so no smart-rotation statistics are queried.

  7. **Ownership handling** — `chore_manager.py:5416`: add the new criteria to the set that applies ownership to the chore record rather than per-assignee.

  8. **Criteria transition validation** — `chore_manager.py:5695` (`_handle_criteria_transition`): ensure the new criteria is subject to the ≥2-assignee validation. (This list currently omits `rotation_primary_standby`; leave as-is.)

  9. **Boundary advance for the new criteria** (replaces the original "guard both sites" plan):
     - `_execute_boundary_reset_plan` (`chore_manager.py:2836`, `:2855`) — **extend for the new criteria**: advance whenever this plan owns the reset **and** `assignee_id == DATA_CHORE_ROTATION_CURRENT_ASSIGNEE_ID`, regardless of `assignee_state`. This makes "always advance" work for a never-completed chore (D15).
     - `_transition_chore_state` (`:5151`) — **suppress for the new criteria during the boundary pass** via a boundary-scoped local flag (D16), threaded `_execute_boundary_reset_plan` → `_apply_reset_action` → `_transition_chore_state`.
     - ⚠️ **Do NOT use a manager-level per-pass set** (D17). It would be consulted by non-boundary `_transition_chore_state` callers and silently suppress legitimate advances for **existing** criteria. It would also change the steal-case anchor precedence, because site 1 passes the plan's assignee while site 2 passes `completed_by` and site 2 currently wins.
     - Only one plan per pass can match the holder, so the extension cannot double-advance across the N-assignee loop. A local flag is not shared state, so there is no staleness window.

  10. **Keep the state gate for all other criteria.** The `assignee_state == APPROVED` guard stays exactly as-is for existing criteria. Only the new criteria bypasses it, and only when the plan's assignee is the current holder. Do not relax the gate globally — that would change behaviour for existing rotation types (D6). See C5.

  11. **Service-layer** — `services.py`:
      - `:210` `_service_uses_chore_level_due_date` — add the new criteria (see step 1.3).
      - `:771` `_COMPLETION_CRITERIA_VALUES` — add the new criteria. This is a single constant referenced by the chore CRUD service schema; adding it here covers both create and update paths.
      - Note: **the `allow_steal` compatibility check lives only in `data_builders.py` rule 12** (via the shared `rotation_criteria` set at `:1609`). There is no `rotation_criteria` set in `services.py` — do not add one.
      - `services.yaml:1317` `completion_criteria` — add the raw value to the `options` list and update the `description` text (it currently enumerates the valid values inline).

  12. **Translations & dashboards**:
      - `translations/en.json` `completion_criteria.options` (around `:2088`) — **`en` only**; all other locales are pipeline-owned.
      - Canonical `translations/en_dashboard.json` (around `:241`) — **`en*` only**.
      - Verify `dashboards/templates/admin-peruser-v1.yaml:1496`, `admin-shared-v1.yaml:1564`, `user-kidschores-classic-v1.yaml:502` treat the new type as rotation/shared rather than independent.

  13. **Do not touch** `migrations/pre_v50.py:3033` — historical migration snapshot. New chores receive the field from `build_chore`, and the migration guards on field absence.

- **Key issues**
  - C9: create-path initialization is the most likely silent failure.
  - C6: the guard is required, and must not be implemented by deleting a call site.
  - A1: the criteria string must contain `rotation` for dashboard iconography and gate activation (C10).
  - Paused-assignee skipping lives in `_advance_rotation_past_paused_assignee` (`chore_manager.py:6376`, called from `:6509`). Verify the new path still reaches it and does not reintroduce turns for paused users.

---

### Phase 4 – Tests

- **Goal**: Prove zero regression for existing behaviour and correct behaviour for both new options.

> ⚠️ **Run TARGETED suites only** (see "Testing policy" below). Do **not** run the full suite during development — it takes ~15 minutes and happens once before the next release.

- **Steps / detailed work items**

  1. **Regression gate (before features)**: with only the Phase 1 guard in place, run `tests/test_chore_engine.py`, `tests/test_chore_manager.py`, `tests/test_workflow_chores.py`, `tests/test_scheduler_delegation.py`, and the rotation suites. All must pass unchanged.
  2. **Feature 1 — boundary decisions** in `tests/test_chore_engine.py` (extend `TestCalculateBoundaryAction`): PENDING + new type + due passed + recurring → `reset_and_reschedule`; same but no due date or `FREQUENCY_NONE` → `skip`; OVERDUE + new type → `reset_and_reschedule` (defensive branch).
  3. **Feature 1 — FSM presentation** in `tests/test_chore_engine.py` (`TestResolveAssigneeChoreStateNeverOverduePastDue` family): past-due + new type → derived `due`, never `overdue`.
  4. **Feature 1 — scan exclusion**: assert the new type is excluded from `CHORE_SCAN_RESULT_OVERDUE` (`can_be_overdue` path) via `_on_periodic_update` / `_process_overdue`.
  5. **Feature 1 — validation**: new type + `manual` → rejected; + `upon_completion` → rejected (per A3); + no due date → rejected; + `FREQUENCY_NONE` → rejected.
  6. **Feature 1 — no churn (multi-night)**: simulate N consecutive midnight passes for a weekly (Sat) chore with the new type; assert exactly **one** reset per due cycle, the due date advances to the next occurrence (one hop), and no repeat reset occurs on the following nights.
  7. **Feature 1 — claim lane unchanged**: with `hold_pending`, an unapproved claim holds the chore; with `auto_approve_pending` (default), the claim is approved and points are awarded. Assert no missed stats and no overdue stats are recorded.
  8. **Feature 2 — anchor behaviour**:
     - Normal completion: turn advances from holder (identical to `rotation_simple` when completer == holder).
     - **Steal + complete**: a non-holder claims and completes; assert the turn advances from the **holder**, not the stealer. This is the defining test.
  9. **Feature 2 — advance exactly once**: assert a single boundary pass advances the turn exactly **one** step for a 3-assignee rotation (regression test for the double-advance trap), and that the dedup guard suppresses the second site.
  10. **Feature 2 — config surface**: ≥2 assignee validation; `rotation_current_assignee_id` initialized on create; criteria transition into/out of the new type; `allow_steal` compatibility per A2.
  11. **Feature 2 — paused users**: a paused holder is skipped; all-paused freezes at the current position (no infinite loop).
  12. Update `tests/helpers/constants.py:371` and `tests/helpers/__init__.py:215` export lists.

- **Key issues**
  - Test 8's steal case is the only test that can distinguish the new type from `rotation_simple` — it must exist.
  - Test 9 is the regression guard for the C6 double-advance trap; without it the bug ships silently for 3+ assignee rotations.

---

### Phase 5 – Docs, dashboards & polish

- **Goal**: User-facing completeness and parity across repos.

- **Steps / detailed work items**

  1. **Wiki** (`choreops-wiki`, keep in sync with `ChoreOps-Dashboards`):
     - `Configuration:-Chores.md:228` — add the new overdue option to the Overdue Handling list and state the "only after the due date" semantics and the due-time guidance (C3).
     - `Advanced:-Chores.md:215-265` — document the new rotation type next to Rotation Simple, including the steal rule (holder anchors) and the "needs the always-reset option too" pairing (C5).
     - `Technical:-Chores.md:52` and `:195` if they enumerate overdue strategies.
     - ⚠️ Do not document the new options as "regenerate dashboards required" for all users — the values are opt-in (see step 4).
  2. **Translations (integration)** — edit `translations/en.json` **directly** (no `strings.json` or regeneration tooling exists in this repo). Add both new labels to **both** enum blocks where present. **Do not hand-edit any other locale file** — the pipeline owns them.
  3. **Dashboards (canonical repo only)** — add the two labels to `translations/en_dashboard.json` (**`en*` only**), add the new overdue key to the two `overdue_handling_map` blocks (`templates/admin-peruser-v1.yaml:1522`, `templates/admin-shared-v1.yaml:1590`), then run `python utils/sync_dashboard_assets.py` followed by `--check`. Verify the admin detail grid shows the new overdue label and that the rotation cards activate (C10). No template edit is needed for rotation.
  4. **Release notes** — state plainly that **Feature 1 resets** and **Feature 2 advances**, and that both are required for "auto-advance if not completed" (C5). Also note the due-time guidance (11:59 PM vs 12:00 AM). Both options are opt-in, so note that dashboards must be regenerated to pick up the new labels.
  5. **Respond on issue #255** — confirm scope, note the requester can use the existing automations until release, and mention dashboard regeneration for the new labels.
  6. **Schema decision** — **owner-approved (A5): no schema bump.** Neither feature adds a storage field or changes data shape, so `SCHEMA_VERSION_CURRENT` (`SCHEMA_VERSION_1_5_0 = 150`, `const.py:355`) stays put. Record this rationale in `docs/ARCHITECTURE.md` only if that document enumerates enum-value changes.
  7. Move this plan to `docs/completed/` with the `_COMPLETE` suffix, and delete the two superseded documents named at the top of this file.
  8. **Follow-up (optional, not blocking)**: three copies of `uses_chore_level_due_date` now exist (`engines/chore_engine.py:650`, `data_builders.py:1399`, `services.py:210`). Feature 2 adds a member to each. Consider consolidating them onto the `ChoreEngine` adapter as a **separate** maintenance change — deliberately not bundled here, to keep this initiative additive and low-risk.

- **Key issues**
  - The canonical dashboard repo is the edit target; the vendored copy is generated. Do not edit both.
  - The pre-existing `zh-Hans_dashboard.json` parity mismatch is unrelated — do not fix it here.
  - Users must regenerate dashboards to see the new option labels.

---

## Testing & validation

### ⚠️ Testing policy — TARGETED TESTS ONLY during development

**This is a hard priority for this initiative. Do not run the full suite during implementation.**

- The full test suite takes **~15 minutes**. It is **not** to be run while developing or iterating on this work.
- Run **only the targeted suites** listed below, scoped to the files being changed (use `-k` / node IDs to narrow further).
- The **full suite is run once, before the next release**, as part of release validation — not per-iteration and not per-commit.
- If a targeted suite passes but you suspect broader impact, add a *narrow targeted* test rather than escalating to a full run.

**Targeted runner commands:**

```bash
# Fast inner loop while editing a single area
python -m pytest tests/test_chore_engine.py -v --tb=line
python -m pytest tests/test_chore_manager.py -v --tb=line

# Narrow to the specific behaviour being changed
python -m pytest tests/test_chore_engine.py -k "Boundary or NeverOverdue" -v --tb=line
python -m pytest tests/test_chore_manager.py -k "rotation or boundary" -v --tb=line
```

**Targeted suites for this initiative:**

| Area                    | Suite                                                          | Used by                        |
| ----------------------- | -------------------------------------------------------------- | ------------------------------ |
| Boundary decisions & FSM | `tests/test_chore_engine.py`                                    | Phase 2, Phase 4 (1–3, 6)      |
| Manager rotation/reset  | `tests/test_chore_manager.py`                                   | Phase 1, Phase 3, Phase 4 (8–11) |
| End-to-end chore workflow | `tests/test_workflow_chores.py`                                 | Phase 3, Phase 4               |
| CRUD + service validation | `tests/test_chore_crud_services.py`, `tests/test_chore_services.py` | Phase 2/3 validation rules     |
| Options flow            | `tests/test_options_flow_entity_crud.py`                        | Phase 2/3 config surface       |
| Scheduling / no-churn   | `tests/test_chore_scheduling.py`, `tests/test_scheduler_delegation.py` | Phase 4 (6)              |
| Notifications untouched | `tests/test_workflow_notifications.py`                          | Regression only                |

**Lint & types** (required before hand-off, and fast enough to run freely):

1. `./utils/quick_lint.sh --fix`
2. `mypy --config-file mypy_quick.ini --explicit-package-bases custom_components/choreops` — the bare `mypy custom_components/choreops/` form fails with a duplicate-module error in this repo.
3. Targeted pytest as above

**Deferred to release validation (owner runs before next release):**

- `python -m pytest tests/ -v --tb=line` (full suite, ~15 minutes)
- Full pre-commit pass: `uv run --no-sync prek run --all-files`

- **Outstanding tests**: full-suite run deferred by design to release validation; dashboard-template rendering is validated manually (no template harness in this repo).
- **Links to failing logs or CI runs**: none yet.

## Notes & follow-up

### References

- `docs/ARCHITECTURE.md` — data model, storage, schema versioning
- `docs/DEVELOPMENT_STANDARDS.md` — constants, logging, types, translations, event architecture
- `docs/CODE_REVIEW_GUIDE.md` — Phase 0 audit framework
- `docs/QUALITY_REFERENCE.md` — Platinum quality requirements
- `docs/DASHBOARD_TEMPLATE_GUIDE.md`, `docs/DASHBOARD_UI_DESIGN_GUIDELINE.md` — dashboard conventions
- `tests/AGENT_TEST_CREATION_INSTRUCTIONS.md` — test patterns
- `docs/RELEASE_CHECKLIST.md` — release process
- `choreops-wiki/Configuration:-Chores.md`, `choreops-wiki/Advanced:-Chores.md`
- `utils/sync_dashboard_assets.py` — canonical → vendored dashboard sync
- Issue #255 (feature request, `thepianoman3`)

### Decisions captured

- **D1** – Feature 1 lives in the **overdue lane**, not the approval-reset lane. `never_overdue` and `clear_at_approval_reset` are mutually exclusive enum values, so the trigger lane cannot express "never overdue **and** reset." The overdue lane is also smaller: no `should_process_at_boundary`, `calculate_boundary_action` signature, or `_is_chore_approval_after_reset` changes.
- **D2** – Extending the existing `clear_at_approval_reset` is **rejected**: near-no-op for existing users (those chores already reset today) and structurally unable to serve the requester (selecting it forfeits never-overdue presentation).
- **D3** – Completer-anchoring is **intentional** and must not change. The new chore type is an additional option; existing types keep completer anchoring.
- **D4** – For the new chore type, holder anchoring is **unconditional**, including after a steal.
- **D5** – The dedup guard is a **behaviour-preserving optimization** for existing types and a **required bug-prevention** measure for the new type. Implemented as a guard, never by removing a call site.
- **D6** – Both features are **opt-in and additive**. No existing chore configuration changes behaviour.
- **D7** – "Only after the due date" is delivered by the **existing** inclusive due-boundary gate; no new gating logic is added.
- **D8** – No new storage fields, so no schema migration is expected (see A5).
- **D9** – Feature 2 is named `rotation_simple_from_turn_holder` (A1). It must start with `rotation` for dashboard iconography and gate activation (C10).
- **D10** – `allow_steal` applies to `rotation_simple_from_turn_holder` (A2). The criteria is added to the **shared** `rotation_criteria` set at `data_builders.py:1609` (which rule 11 and rule 12 both consume), plus `_COMPLETION_CRITERIA_VALUES` at `services.py:771` for the service schema.
- **D11** – Feature 1's compatible `approval_reset_type` set is `{at_midnight_once, at_midnight_multi}` (A3). `at_midnight_once` is the priority; `at_midnight_multi` is included because it costs nothing. `at_due_date_once`, `at_due_date_multi`, `upon_completion`, and `manual` are **not required** and stay out of the set.
- **D12** – The existing `at_due_date_clear_at_approval_reset` validation (rule 7) and the no-recurrence due-date clear behaviour are **left untouched**. Neither is a defect, and neither collides with Feature 1 (see "Resolved: open item 2").
- **D13** – Dashboard updates are **in scope** but **minimal**, performed in the **canonical** `ChoreOps-Dashboards` repo and synced to the vendored copy (see "Dashboard parity").
- **D14** – Only `en*.json` translation files are hand-edited; all other locales are owned by the translation pipeline.
- **D15** – For the new criteria, the **boundary reset advances the turn regardless of completion state** (owner-approved 2026-09-11). This closes the C5 gap: a never-completed rotation chore must still rotate, which is the core of issue #255.
- **D16** – The dedup is a **boundary-scoped local flag**, threaded `_execute_boundary_reset_plan` → `_apply_reset_action` → `_transition_chore_state`, and **gated on the new criteria**. A local value is used deliberately — no manager-level shared state, so there is no stale-set window.
- **D18** – When you change a `services.yaml` field description, also update the matching `en.json` `services.<service>.fields.<field>.description` when the two already matched. `en.json` is what the UI renders; `services.yaml` is the developer-facing source. Note there are ~55 **pre-existing** drift cases repo-wide (e.g. `update_chore.*` uses "New X" in `services.yaml` but fuller text in `en.json`), so this is "keep the fields you touch in sync", not a repo-wide invariant. The `frequency` field already followed this convention; `completion_criteria` had drifted (generic text in `en.json` vs an enumeration in `services.yaml`). When the `services.yaml` description gained the new criteria, the `en.json` description was updated to match. Phase 2's `overdue_handling` change was options-only, so no description update was required there.
- **D17** – The original plan's **manager-level per-pass set is rejected**. It would be consulted by non-boundary `_transition_chore_state` callers (approval at `:1760`, `reset_overdue_chores` at `:3320`, data-reset at `:7063`/`:7209`), silently suppressing legitimate advances for **existing** criteria and breaking D6. It would also alter the steal-case anchor precedence: site 1 passes the plan's assignee while site 2 passes `completed_by`, and site 2 currently wins — so suppressing site 2 for existing types is itself a behaviour change.

### Resolved: open item 2 (approval-reset compatibility)

The question was about `approval_reset_type` compatibility for `*_clear_at_approval_reset` options — **not** about the no-recurrence case. The concern was that such an option is inert when no scheduled boundary exists, because `should_process_at_boundary` (`engines/chore_engine.py:1535`) returns `False` for both triggers under `upon_completion` and `manual`.

**Finding: validation already handles this, and the earlier "latent hole" claim was wrong.** Rule 7 (`data_builders.py:1517`) already restricts the existing option to `{AT_MIDNIGHT_ONCE, AT_MIDNIGHT_MULTI, UPON_COMPLETION}` and rejects `manual`. `UPON_COMPLETION` is coherent because the approval reset *is* completion in that mode.

Separately, the no-recurrence + due-date behaviour (process the chore, clear the due date, so it is not stuck approved) is a **different mechanism** — `should_clear_due_date` (`chore_manager.py:2690`, approval-path variant `should_clear_due_date_after_immediate_reset` at `:1232`) and `_clear_due_date_after_reset` (`:1732`). It is triggered only when `recurring_frequency == FREQUENCY_NONE`.

**Impact on this initiative: none, and the two do not collide.** Because the new overdue option requires a recurring frequency (Phase 2 step 6), `should_clear_due_date` can never be true for it. The existing no-recurrence clear behaviour is untouched. The only new work is applying the same style of compatibility validation to the new option.

### Resolved decisions (owner, 2026-09-11)

All ambiguities are closed. The plan is unblocked for implementation.

- **A1 — Feature 2 naming.** ✅ **`rotation_simple_from_turn_holder`** / const `COMPLETION_CRITERIA_ROTATION_SIMPLE_FROM_TURN_HOLDER`. Label *"Rotation Simple (Advance From Current Turn Holder)"*. Satisfies the dashboard `rotation` substring requirement.
- **A2 — `allow_steal` for the new type.** ✅ **Allowed.** One edit at the shared `rotation_criteria` set (`data_builders.py:1609`) satisfies both rule 11 and rule 12; `_COMPLETION_CRITERIA_VALUES` (`services.py:771`) covers the service schema. Removal of the `not_my_turn` block after the steal window opens (FSM P3) applies automatically via the `is_rotation_mode` adapter. Holder anchoring remains unconditional: the stealer completes, the turn still advances from the holder.
- **A3 — Feature 1 compatible `approval_reset_type` set.** ✅ **`{at_midnight_once, at_midnight_multi}`.** `at_midnight_once` is the priority and primary use case. `at_midnight_multi` is included because it costs nothing. `at_due_date_once`, `at_due_date_multi`, `upon_completion`, and `manual` are **not required** and stay out of the set.
- **A4 — Feature 1 naming.** ✅ **`never_overdue_clear_at_approval_reset`** / const `OVERDUE_HANDLING_NEVER_OVERDUE_CLEAR_AT_APPROVAL_RESET`. Consistent with the existing `at_due_date_clear_at_approval_reset` suffix.
- **A5 — Schema version bump.** ✅ **None needed.** No new storage fields; `SCHEMA_VERSION_CURRENT` stays at `SCHEMA_VERSION_1_5_0`.
- **A6 — Communication.** ✅ Accepted — the issue reply will note that dashboards must be regenerated to pick up the new option labels.

### Explicitly out of scope

- Polling offset for the midnight pass (pass may run 00:03/00:05).
- The 12:00 AM vs 11:59 PM due-time confusion (separately reported; system is technically correct).
- Relaxing `PENDING → skip` globally, or otherwise changing reset eligibility for existing options.
- Refactoring the presentation/scan coupling of existing never-overdue options.
- The pre-existing `rotation_primary_standby` omission from the ≥2-assignee validation rules.
- Adding rotation controls to the classic or user dashboard templates (they have none).
- Fixing the pre-existing `zh-Hans_dashboard.json` parity mismatch.
- Refactoring / restyling any dashboard template.
- `migrations/pre_v50.py` (historical snapshot).
