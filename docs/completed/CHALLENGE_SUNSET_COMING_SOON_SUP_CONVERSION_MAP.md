# Supporting Spec: Challenge to periodic badge conversion

## Purpose

Define deterministic conversion rules for migrating challenge records to periodic badges during schema45 migration.

## Scope

- Input source: `data.challenges`
- Output target: `data.badges` as periodic badges
- Removal target: `challenge_linked` badge type and challenge runtime capability
- No migration archive keys are required for challenge/challenge-linked payloads in this migration.

## Migration order (critical)

Conversion must run **after** schema45 legacy key normalization has remapped challenge assignee keys.

Confirmed current order in schema45 hook:

1. `_normalize_legacy_kid_keys(data)` remaps legacy challenge assignment keys
2. Challenge → periodic badge conversion runs
3. Challenge-linked badges are removed
4. `data.challenges` is cleared

Reason: conversion must read canonical `assigned_user_ids` (not legacy `assigned_kids` / `assigned_assignees`).

## Proposed conversion rules

### Shared field mapping

- `challenge.name` → `badge.name`
- `challenge.description` → `badge.description`
- `challenge.icon` → `badge.icon`
- `challenge.challenge_labels` → `badge.badge_labels`
- `challenge.assigned_user_ids` → `badge.assigned_user_ids`
- `challenge.reward_points` → `badge.reward_points`

### Type mapping

1. `challenge.type == total_within_window`
   - Badge type: `periodic`
   - Target class: count-based periodic target
   - Threshold: `challenge.target_value`
   - Selected chore behavior:
     - If `selected_chore_id` exists, include in tracked chore ids.
     - Else use all assigned chore scope.

2. `challenge.type == daily_minimum`
   - Badge type: `periodic`
   - Target class: nearest supported daily-min periodic target
   - Threshold fallback policy (required due non-1:1 support):
     - If target <= 3 → map to `days_min_3_chores`
     - If 3 < target <= 5 → map to `days_min_5_chores`
     - If target > 5 → map to `days_min_7_chores`
   - Add migration note attribute with original target for transparency.

3. Any other challenge type/value shape
   - Do not convert.
   - Increment `skipped_challenges_invalid_type`.

4. Non-positive target values (`target_value <= 0`)
   - Do not convert.
   - Increment `skipped_challenges_invalid_type`.

## Identity and idempotency

- Badge internal id format: deterministic from challenge id (for example `migrated_challenge_<challenge_id>`).
- If deterministic id already exists, do not duplicate.
- Badge name collision policy: if migrated badge name collides with an existing badge name, append `_2`.
- Name collision policy is intentionally single-step only: do not auto-increment to `_3`, `_4`, etc.
- Add migration markers in `meta.migrations_applied` and summary counters in `meta.schema45_last_summary`.

## Finalized marker and summary names

Use these exact names to avoid drift across migration code and tests:

- Marker: `schema45_challenges_to_periodic_badges`
- Marker: `schema45_remove_challenge_linked_badges`
- Summary counter: `converted_challenges`
- Summary counter: `skipped_challenges_existing_badge`
- Summary counter: `renamed_challenges_name_collision`
- Summary counter: `skipped_challenges_invalid_type`
- Summary counter: `removed_challenge_linked_badges`
- Summary passthrough: `kid_key_remaps`

Keep counters flat under `meta.schema45_last_summary` and avoid nested stats structures.

## Challenge-linked badge handling

- For existing `badge_type == challenge_linked`:
  - **Do not convert**.
  - Remove from active badges with summary counter.
- Remove `associated_challenge` runtime usage in active schemas.

## Data lifecycle after migration

- `data.challenges` emptied.
- `badge_type == challenge_linked` records removed from active badge data.
- Active runtime only uses converted periodic badges.

Decision captured in implementation plan:
- `data.challenges` is emptied after conversion.
- `challenge_linked` badges are removed (not converted).

## Validation checkpoints

- Migration is idempotent across reruns.
- No active badge with `badge_type == challenge_linked` remains.
- No active challenge records remain.
- Converted badges are visible in options flow and evaluate with existing badge engine paths.
- Conversion executes after legacy key normalization (verified by migration marker/snapshot assertions).

## Builder guardrails (non-negotiable)

- Do not add any archive containers or archive metadata keys.
- Do not convert `challenge_linked` badges; remove them only.
- Do not add runtime compatibility branches for challenge behavior.
- Do not mutate schema45 flow order for existing user-contract normalization.
- Do not create extra naming policies beyond the single `_2` suffix rule.

## Schema45 pseudo-code (implementation sequence)

```python
async def async_apply_schema45_user_contract(coordinator) -> dict[str, int]:
  data = coordinator._data
  meta = data.setdefault("meta", {})
  applied = meta.setdefault("migrations_applied", [])

  # Existing schema45 steps
  ...
  kid_key_remaps = _normalize_legacy_kid_keys(data)

  # New migration markers (idempotency)
  challenge_conv_marker = "schema45_challenges_to_periodic_badges"
  challenge_linked_rm_marker = "schema45_remove_challenge_linked_badges"

  summary = {
    ...existing_summary_fields,
    "converted_challenges": 0,
    "skipped_challenges_existing_badge": 0,
    "renamed_challenges_name_collision": 0,
    "skipped_challenges_invalid_type": 0,
    "removed_challenge_linked_badges": 0,
    "kid_key_remaps": kid_key_remaps,
  }

  # 1) Convert challenge records -> periodic badges
  if challenge_conv_marker not in applied:
    conv = _migrate_schema45_challenges_to_periodic_badges(data, meta)
    summary["converted_challenges"] += conv["converted_challenges"]
    summary["skipped_challenges_existing_badge"] += conv["skipped_existing"]
    summary["renamed_challenges_name_collision"] += conv["renamed_name_collision"]
    summary["skipped_challenges_invalid_type"] += conv["skipped_invalid_type"]
    applied.append(challenge_conv_marker)

  # 2) Remove challenge-linked badges (never convert)
  if challenge_linked_rm_marker not in applied:
    rm = _remove_schema45_challenge_linked_badges(data, meta)
    summary["removed_challenge_linked_badges"] += rm["removed"]
    applied.append(challenge_linked_rm_marker)

  # 3) Ensure challenges container is no longer active
  _clear_challenges_container(data)

  # Existing schema45 wrap-up
  meta["schema_version"] = SCHEMA_VERSION_BETA5
  meta["schema45_last_summary"] = summary
  return summary
```

### Helper pseudo-code: challenge conversion

```python
def _migrate_schema45_challenges_to_periodic_badges(data, meta) -> dict[str, int]:
  badges = data.setdefault("badges", {})
  challenges = data.get("challenges", {})

  converted = 0
  skipped_existing = 0
  renamed_name_collision = 0
  skipped_invalid_type = 0

  for challenge_id, challenge in challenges.items():
    if not isinstance(challenge, dict):
      skipped_invalid_type += 1
      continue

    # Deterministic identity to prevent duplicates
    badge_id = f"migrated_challenge_{challenge_id}"
    if badge_id in badges:
      skipped_existing += 1
      continue

    # Type mapping with fallback
    challenge_type = challenge.get("type", "")
    target_value = int(challenge.get("target_value", 0) or 0)
    if target_value <= 0:
      skipped_invalid_type += 1
      continue

    if challenge_type == "total_within_window":
      mapped_target_type = "chore_count"
      mapped_threshold = target_value
    elif challenge_type == "daily_minimum":
      mapped_target_type, mapped_threshold = _map_daily_min_threshold(target_value)
    else:
      skipped_invalid_type += 1
      continue

    base_name = challenge.get("name", f"Migrated challenge {challenge_id}")
    migrated_name = base_name
    existing_names = {
      badge.get("name")
      for badge in badges.values()
      if isinstance(badge, dict)
    }
    if migrated_name in existing_names:
      migrated_name = f"{base_name}_2"
      renamed_name_collision += 1

    badges[badge_id] = {
      "internal_id": badge_id,
      "name": migrated_name,
      "description": challenge.get("description", ""),
      "icon": challenge.get("icon"),
      "badge_labels": challenge.get("challenge_labels", []),
      "assigned_user_ids": challenge.get("assigned_user_ids", []),
      "badge_type": "periodic",
      "reward_points": challenge.get("reward_points", 0),
      "target": {
        "type": mapped_target_type,
        "threshold_value": mapped_threshold,
      },
      "migration_meta": {
        "source": "challenge",
        "source_challenge_id": challenge_id,
        "source_challenge_type": challenge_type,
        "source_target_value": target_value,
      },
    }

    converted += 1

  return {
    "converted_challenges": converted,
    "skipped_existing": skipped_existing,
    "renamed_name_collision": renamed_name_collision,
    "skipped_invalid_type": skipped_invalid_type,
  }
```

### Helper pseudo-code: remove challenge-linked badges

```python
def _remove_schema45_challenge_linked_badges(data, meta) -> dict[str, int]:
  badges = data.get("badges", {})
  if not isinstance(badges, dict):
    return {"removed": 0}

  to_remove = [
    badge_id
    for badge_id, badge in badges.items()
    if isinstance(badge, dict) and badge.get("badge_type") == "challenge_linked"
  ]

  for badge_id in to_remove:
    badges.pop(badge_id, None)

  return {"removed": len(to_remove)}
```

### Helper pseudo-code: daily minimum fallback mapper

```python
def _map_daily_min_threshold(target_value: int) -> tuple[str, int]:
  # Fallback to nearest supported periodic badge target family
  if target_value <= 3:
    return ("days_min_3_chores", 1)
  if target_value <= 5:
    return ("days_min_5_chores", 1)
  return ("days_min_7_chores", 1)
```

## Recommended wording for UX/docs

- Availability banner: “Challenges will be made available in future update.”
- Migration banner: “During migration, existing Challenge records are converted to equivalent Periodic Badge tracking to preserve intent and progress behavior where possible. They will be returning in a future release completely reimagined from their original implementation in KidsChores”
