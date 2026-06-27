# Feature: Chore-Restricted Rewards (Eligible Chores)

## Summary

Adds an optional **"Limit to chores"** setting to the Add/Edit Reward forms. When
set, a reward can only be paid for with points the assignee earned from the
selected chores. Points are **shared and used up**: a point earned from a chore
can only be spent once, even when that chore funds more than one reward.

Example: a "30 min screen time" reward limited to *Playing Outside*, *Reading*,
and *Math Workbook* can only be redeemed using points earned from those chores —
even though the child accumulates a single overall point total from all chores.

When no chores are selected, the reward behaves exactly as before (any points may
be used). This makes the feature fully backward compatible.

## Data model

- `RewardData.eligible_chore_ids: NotRequired[list[str]]` — chore ids that may
  fund the reward. Empty/absent = unrestricted.
- `AssigneeData["points_by_chore"]: dict[chore_id, float]` — remaining spendable
  points the assignee earned per chore. Lazily created on first chore deposit
  (no storage migration required). Not historically backfilled, so points earned
  before upgrade are treated as unrestricted.

## Behaviour (where the logic lives)

Follows the existing Landlord/Tenant + Choreography conventions in `AGENTS.md`
(only managers write to storage; pure math lives in engines).

1. **Earn** — `EconomyManager.deposit()`: when `source == POINTS_SOURCE_CHORES`
   and a `reference_id` (chore id) is present, the awarded amount is added to
   `points_by_chore[chore_id]` alongside the normal balance update.
2. **Gate (redeem)** — `RewardManager._redeem_locked()`: the affordability check
   uses `EconomyManager.get_available_for_reward(assignee_id, eligible_chore_ids)`
   instead of the raw balance. Unrestricted rewards return the full balance.
3. **Spend (approve)** — `EconomyManager._on_reward_approved()`: after the normal
   withdrawal, restricted rewards draw the cost down from the funding chores via
   the pure helper `EconomyEngine.allocate_debit()` (sequential, never negative).
4. **Undo** — `EconomyManager._on_chore_undone()`: reclaimed chore points are
   removed from `points_by_chore` too (clamped at 0).

`EconomyEngine.allocate_debit(balances, order, amount)` is pure and unit-tested in
`tests/test_economy_engine.py` (`TestAllocateDebit`).

## UI / translations

- `flow_helpers.build_reward_schema()` gains a `chores_dict` parameter and renders
  a multi-select of chores (`CFOF_REWARDS_INPUT_ELIGIBLE_CHORE_IDS`).
- `options_flow.async_step_add_reward` / `async_step_edit_reward` pass
  `coordinator.chores_data` and pre-populate the field on edit.
- `data_builders.build_reward()` persists `eligible_chore_ids`; the field is
  added to `_REWARD_DATA_RESET_PRESERVE_FIELDS` so it survives a data reset.
- `translations/en.json`: field label + description for `add_reward` and
  `edit_reward`.

## Known limitations (v1)

- Manual adjustments, bonuses, and penalties change the overall balance but are
  not attributed to a chore, so they do not contribute to a restricted reward.
- Penalties reduce the overall balance but not `points_by_chore`, so in rare
  cases a restricted balance can briefly exceed the overall balance; the overall
  NSF check at approval still applies.
- No sensor attribute yet exposes per-reward available points to dashboards
  (suggested follow-up). Enforcement is complete; this is display-only.

## Files changed

- `const.py`, `type_defs.py`, `data_builders.py`
- `helpers/flow_helpers.py`, `options_flow.py`
- `managers/reward_manager.py`, `managers/economy_manager.py`
- `engines/economy_engine.py`
- `translations/en.json`
- `tests/test_economy_engine.py`, `README.md`
