# Supporting matrix: UX contract inconsistencies (attributes, services, purpose)

- Generated: 2026-02-24
- Scope: `custom_components/choreops/` user-facing contracts only
- Goal: Side-by-side mismatch view to support one coordinated cleanup pass

## Canonical contract target (proposed)

1. **Singular identity/display**
   - `user_id` = UUID
   - `user_name` = display name
2. **Assignment collections**
   - `assigned_user_ids` = list of UUIDs only
   - `assigned_user_names` = list of names only
   - Avoid `assigned_to` for list contracts (ambiguous); reserve only for single summary text if ever needed
3. **Purpose attributes**
   - `ATTR_PURPOSE` value should be a translation-key constant (`TRANS_KEY_PURPOSE_*`), not prose literal constants
   - Use `user` in lifecycle/profile contexts
   - Keep `assignee`/`approver` only when explicitly role-semantic

---

## A) Attribute key/payload mismatches (highest impact)

| Area         | Symbol / key                                   | Current behavior                                      | Expected behavior                                                                         | Mismatch type                                  | Evidence                                                                                                    |
| ------------ | ---------------------------------------------- | ----------------------------------------------------- | ----------------------------------------------------------------------------------------- | ---------------------------------------------- | ----------------------------------------------------------------------------------------------------------- |
| Entity attrs | `ATTR_ASSIGNED_USER_IDS` / `assigned_user_ids` | Populated from `assigned_assignees_names` (name list) | Should be UUID list (or rename key to `assigned_user_names`)                              | Key says IDs, payload is names                 | `sensor.py` L1072, L2468, L3122, L3324, L3594, L3805; source var at L904/L919/L2423/L3070/L3276/L3568/L3779 |
| Entity attrs | `ATTR_USERS_ASSIGNED` / `assignees_assigned`   | List of names                                         | Explicit names-list key (`assigned_user_names`)                                           | Ambiguous key/value naming                     | `const.py` L2301; population in `sensor.py` L2239-L2252                                                     |
| Entity attrs | `ATTR_USERS_EARNED` / `assignees_earned`       | List of names                                         | Explicit names-list key (`earned_user_names`)                                             | Ambiguous key/value naming                     | `const.py` L2302; population in `sensor.py` L2231-L2241, L3133, L3333                                       |
| Button attrs | literal `"assignee_id"`                        | Exposed in points-adjust button attributes            | Should use canonical const-backed user identity key (`user_id`) or be removed if internal | Untracked literal + assignee lifecycle leakage | `button.py` L1656                                                                                           |

### Notes

- The points-buttons issue is **real** and user-visible via state attributes.
- `ATTR_DASHBOARD_USER_NAME`, `ATTR_SELECTED_USER_NAME`, `ATTR_SELECTED_USER_SLUG`, `ATTR_CHORE_TURN_USER_NAME`, `ATTR_USER_NAME` are already aligned to user-based naming.

---

## B) Service field semantic mismatches

| Area                 | Symbol / key                                                       | Current behavior                                            | Expected behavior                                                                                   | Mismatch type              | Evidence                                                      |
| -------------------- | ------------------------------------------------------------------ | ----------------------------------------------------------- | --------------------------------------------------------------------------------------------------- | -------------------------- | ------------------------------------------------------------- |
| Service schema/input | `SERVICE_FIELD_CHORE_CRUD_ASSIGNED_USER_IDS` / `assigned_user_ids` | Create/update accepts names; handler resolves names → UUIDs | Key ending in `_ids` should accept UUID list directly; optional companion field for names if needed | Payload semantics mismatch | `services.py` schema at L323/L375; conversion logic L708-L727 |
| Service alias        | `SERVICE_FIELD_ASSIGNED_USER_IDS` / `assigned_user_ids`            | Alias used for same semantic surface                        | Should mirror canonical UUID-list semantics                                                         | Alias inherits mismatch    | `const.py` L2724                                              |

### Notes

- `SERVICE_FIELD_USER_ID` and `SERVICE_FIELD_USER_NAME` naming is already good; behavior choice (require one/both) should be decided per service but does not require renaming.

---

## C) Purpose contract inconsistencies (symbol/value style)

### C1. Mixed value style by platform

| Platform           | Current `ATTR_PURPOSE` value style                              | Status          | Evidence                                                            |
| ------------------ | --------------------------------------------------------------- | --------------- | ------------------------------------------------------------------- |
| `sensor.py` (main) | `TRANS_KEY_PURPOSE_*`                                           | ✅ Consistent   | examples: L1066, L1333, L1943, L4921                                |
| `button.py`        | `TRANS_KEY_PURPOSE_BUTTON_*`                                    | ✅ Consistent   | examples: L415, L549, L1653                                         |
| `calendar.py`      | `TRANS_KEY_PURPOSE_CALENDAR_SCHEDULE`                           | ✅ Consistent   | L1049                                                               |
| `datetime.py`      | `TRANS_KEY_PURPOSE_DATETIME_DASHBOARD_HELPER`                   | ✅ Consistent   | L141                                                                |
| `select.py`        | **Mixed** (`PURPOSE_SELECT_*` literals + `TRANS_KEY_PURPOSE_*`) | ⚠️ Inconsistent | literals at L198/L250/L302/L354; translation keys at L430/L465/L557 |
| `sensor_legacy.py` | `PURPOSE_SENSOR_*` prose literals                               | ⚠️ Inconsistent | L143, L208, L273, ..., L1221                                        |

### C2. Purpose key naming drift (`assignee` in lifecycle contexts)

| Symbol                                              | Current value                             | Suggested target                      | Why                                                         |
| --------------------------------------------------- | ----------------------------------------- | ------------------------------------- | ----------------------------------------------------------- |
| `TRANS_KEY_PURPOSE_ASSIGNEE_BADGES`                 | `purpose_assignee_badges`                 | `purpose_user_badges`                 | Lifecycle/profile context, not actor-role action            |
| `TRANS_KEY_PURPOSE_SELECT_ASSIGNEE_CHORES`          | `purpose_select_assignee_chores`          | `purpose_select_user_chores`          | Dashboard helper selection context is user-target selection |
| `TRANS_KEY_PURPOSE_SYSTEM_DASHBOARD_ADMIN_ASSIGNEE` | `purpose_system_dashboard_admin_assignee` | `purpose_system_dashboard_admin_user` | Admin dashboard target context is user profile selection    |

### C3. Legacy prose PURPOSE constants with assignee wording

These are still used in `sensor_legacy.py` and keep assignee prose in user-lifecycle contexts:

- `PURPOSE_SENSOR_PENALTY_APPLIED`
- `PURPOSE_SENSOR_BONUS_APPLIED`
- `PURPOSE_SENSOR_CHORES_PENDING_APPROVAL_EXTRA`
- `PURPOSE_SENSOR_REWARDS_PENDING_APPROVAL_EXTRA`
- `PURPOSE_SENSOR_POINTS_EARNED_TODAY_EXTRA`
- `PURPOSE_SENSOR_POINTS_EARNED_WEEK_EXTRA`
- `PURPOSE_SENSOR_POINTS_EARNED_MONTH_EXTRA`
- `PURPOSE_SENSOR_CHORE_STREAK_EXTRA`

Evidence base: `const.py` L2228-L2263, and usages in `sensor_legacy.py` L1095/L1221 and related sections.

---

## D) Side-by-side mismatch index (single execution backlog)

| ID    | Category              | Current                                        | Target                                                         | Blast radius                        | Batch   |
| ----- | --------------------- | ---------------------------------------------- | -------------------------------------------------------------- | ----------------------------------- | ------- |
| UX-01 | Attribute payload     | `ATTR_ASSIGNED_USER_IDS` carries names         | Make it UUID list OR rename key to `assigned_user_names`       | Medium (dashboards/templates/tests) | Batch A |
| UX-02 | Attribute naming      | `assignees_assigned`                           | `assigned_user_names` (or explicit count key if count)         | Medium                              | Batch A |
| UX-03 | Attribute naming      | `assignees_earned`                             | `earned_user_names` (or explicit count key if count)           | Medium                              | Batch A |
| UX-04 | Literal attribute key | `"assignee_id"` in button attrs                | const-backed `user_id` or remove if internal                   | Low-Medium                          | Batch A |
| UX-05 | Service semantic      | `_ASSIGNED_USER_IDS` accepts names             | UUID list only; optional separate names field                  | High (automation callers)           | Batch B |
| UX-06 | Purpose style         | `select.py` uses `PURPOSE_SELECT_*` literals   | switch to `TRANS_KEY_PURPOSE_*`                                | Low-Medium                          | Batch C |
| UX-07 | Purpose style         | `sensor_legacy.py` uses prose PURPOSE literals | switch to `TRANS_KEY_PURPOSE_*` (or explicit legacy exemption) | Medium                              | Batch C |
| UX-08 | Purpose naming        | `purpose_*assignee*` lifecycle keys            | `purpose_*user*` where non-role semantic                       | Medium (translations/tests)         | Batch D |

---

## E) Recommended one-pass cleanup sequencing

### Batch A — Attributes (non-service)

- Fix `ATTR_ASSIGNED_USER_IDS` semantic mismatch.
- Normalize name-list keys (`assignees_assigned`, `assignees_earned`).
- Replace literal `"assignee_id"` attribute key in points button.

### Batch B — Service input semantics

- Make `assigned_user_ids` inputs UUID-only.
- If needed for UX convenience, add explicit `assigned_user_names` inputs (separate field, explicit conversion path).
- Update service docs/tests accordingly.

### Batch C — Purpose style consistency

- Convert `select.py` and `sensor_legacy.py` purpose values to translation-key constants.
- Keep `ATTR_PURPOSE` key unchanged.

### Batch D — Purpose naming cleanup

- Rename non-role-semantic `purpose_*assignee*` keys to `purpose_*user*`.
- Keep actor-role purpose keys where role wording is intentional.

---

## F) Validation checklist for the cleanup PR

- No user-facing attribute key contains `assignee_` unless role-semantic by design.
- `assigned_user_ids` payloads are UUID lists everywhere.
- Name lists use explicit keys (`*_user_names`).
- `ATTR_PURPOSE` values are translation-key constants across all entity platforms.
- Translation keys and `translations/en.json` remain in sync after purpose-key changes.
- Focused tests for services + entity attributes + dashboard helper entities are updated and passing.
