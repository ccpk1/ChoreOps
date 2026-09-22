"""All-time point ledger reconciliation helpers for boot integrity repairs."""

from __future__ import annotations

from typing import Any

from custom_components.choreops import const

# Generic sources absorb repair adjustments so category history (chores,
# rewards, ...) stays untouched whenever a free carrier works.
_CARRIER_PREFERENCE: tuple[str, ...] = (
    const.POINTS_SOURCE_OTHER,
    const.POINTS_SOURCE_MANUAL,
    const.POINTS_SOURCE_CHORES,
    const.POINTS_SOURCE_REWARDS,
    const.POINTS_SOURCE_BONUSES,
    const.POINTS_SOURCE_PENALTIES,
    const.POINTS_SOURCE_BADGES,
    const.POINTS_SOURCE_ACHIEVEMENTS,
    const.POINTS_SOURCE_CHALLENGES,
)

# Half of the last stored decimal: any larger leftover means the redistribution
# genuinely does not fit rather than binary floating-point residue.
_SIGN_FIX_TOLERANCE = 0.005


def _positive_sum(by_source: dict[str, float]) -> float:
    """Return the sum of positive history entries, rounded to storage precision."""
    return round(
        sum(value for value in by_source.values() if value > 0.0),
        const.DATA_FLOAT_PRECISION,
    )


def _negative_sum(by_source: dict[str, float]) -> float:
    """Return the sum of negative history entries, rounded to storage precision."""
    return round(
        sum(value for value in by_source.values() if value < 0.0),
        const.DATA_FLOAT_PRECISION,
    )


def _free_carrier(by_source: dict[str, float], exclude: set[str]) -> str | None:
    """Return an unused standard source key (absent or exactly zero), if any."""
    for key in _CARRIER_PREFERENCE:
        if key not in exclude and by_source.get(key, 0.0) == 0.0:
            return key
    return None


def _distribution_order(
    keys: list[str], by_source: dict[str, float], *, largest_value: bool
) -> list[str]:
    """Order keys generic-first, then by value, for clamped redistribution."""
    key_set = set(keys)
    generic = [key for key in _CARRIER_PREFERENCE if key in key_set]
    specific = sorted(
        (key for key in key_set if key not in _CARRIER_PREFERENCE),
        key=lambda key: by_source[key],
        reverse=largest_value,
    )
    return generic + specific


def _reconcile_by_source_signs(
    by_source: dict[str, float], earned: float, spent: float
) -> str:
    """Align positive/negative by_source sums with the earned/spent ledger.

    Applies a zero-sum, never-crossing redistribution on a candidate copy and
    commits it only when both target sums verify exactly, so a failed attempt
    cannot leave the history net broken.

    Returns:
        "unchanged" when already aligned, "repaired" after a verified commit,
        or "deferred" when no safe redistribution exists (net stays exact).
    """
    delta = round(
        earned - _positive_sum(by_source),
        const.DATA_FLOAT_PRECISION,
    )
    if delta == 0.0:
        return "unchanged"

    candidate = dict(by_source)

    if delta > 0.0:
        positive_keys = [key for key, value in candidate.items() if value > 0.0]
        negative_keys = [key for key, value in candidate.items() if value < 0.0]

        grow_key = next(
            (key for key in _CARRIER_PREFERENCE if key in positive_keys), None
        )
        if grow_key is None and positive_keys:
            grow_key = max(positive_keys, key=lambda key: (candidate[key], key))
        if grow_key is None:
            grow_key = _free_carrier(candidate, exclude=set())

        shrink_key = next(
            (key for key in _CARRIER_PREFERENCE if key in negative_keys), None
        )
        if shrink_key is None and negative_keys:
            shrink_key = min(negative_keys, key=lambda key: (candidate[key], key))
        if shrink_key is None:
            exclude = {grow_key} if grow_key is not None else set()
            shrink_key = _free_carrier(candidate, exclude=exclude)

        if grow_key is None or shrink_key is None or grow_key == shrink_key:
            return "deferred"

        candidate[grow_key] = round(
            candidate.get(grow_key, 0.0) + delta, const.DATA_FLOAT_PRECISION
        )
        candidate[shrink_key] = round(
            candidate.get(shrink_key, 0.0) - delta, const.DATA_FLOAT_PRECISION
        )
    else:
        need = round(-delta, const.DATA_FLOAT_PRECISION)
        positive_keys = [key for key, value in candidate.items() if value > 0.0]
        negative_keys = [key for key, value in candidate.items() if value < 0.0]
        if not positive_keys or not negative_keys:
            return "deferred"

        # Shrink positives toward zero; capacity equals earned + need, so it fits.
        remaining = need
        for key in _distribution_order(positive_keys, candidate, largest_value=True):
            take = min(candidate[key], remaining)
            if take <= 0.0:
                continue
            candidate[key] = round(candidate[key] - take, const.DATA_FLOAT_PRECISION)
            remaining = round(remaining - take, const.DATA_FLOAT_PRECISION)
            if remaining <= _SIGN_FIX_TOLERANCE:
                break
        if remaining > _SIGN_FIX_TOLERANCE:
            return "deferred"

        # Grow negatives toward zero; capacity equals |spent| + need, so it fits.
        remaining = need
        for key in _distribution_order(negative_keys, candidate, largest_value=False):
            take = min(-candidate[key], remaining)
            if take <= 0.0:
                continue
            candidate[key] = round(candidate[key] + take, const.DATA_FLOAT_PRECISION)
            remaining = round(remaining - take, const.DATA_FLOAT_PRECISION)
            if remaining <= _SIGN_FIX_TOLERANCE:
                break
        if remaining > _SIGN_FIX_TOLERANCE:
            return "deferred"

    if _positive_sum(candidate) != round(
        earned, const.DATA_FLOAT_PRECISION
    ) or _negative_sum(candidate) != round(spent, const.DATA_FLOAT_PRECISION):
        return "deferred"

    by_source.clear()
    by_source.update(candidate)
    return "repaired"


def repair_point_all_time_ledger(data: dict[str, Any]) -> dict[str, int]:
    """Reconcile each assignee's all-time point ledger, balance, and history.

    Invariant: balance == points_earned + points_spent == sum(by_source), with
    points_earned equal to the positive history entries and points_spent to the
    negative ones. Legacy KidsChores migrations fabricated earned/spent from the
    balance and highest_balance without adjusting by_source (#306), so historic
    installs carry all three views out of agreement.

    Repair precedence: the balance wins for the net, the earned/spent ledger
    wins for the sign split, by_source entries are adjusted to match - never the
    other way around. Earned is only ever raised, so cumulative badge progress
    can stay the same or grow, never regress.

    Idempotent: a reconciled ledger reports all-zero counters.
    """
    summary = {
        "assignees_repaired": 0,
        "ledger_gaps_folded": 0,
        "history_nets_folded": 0,
        "history_signs_fixed": 0,
        "history_sign_fixes_deferred": 0,
        "highest_floored": 0,
    }

    users_raw = data.get(const.DATA_USERS)
    if not isinstance(users_raw, dict):
        return summary

    for user_value in users_raw.values():
        if not isinstance(user_value, dict):
            continue
        assignee: dict[str, Any] = user_value

        balance = round(
            float(assignee.get(const.DATA_USER_POINTS, 0.0)),
            const.DATA_FLOAT_PRECISION,
        )

        periods_raw = assignee.get(const.DATA_USER_POINT_PERIODS)
        periods = periods_raw if isinstance(periods_raw, dict) else {}
        bucket_raw = periods.get(const.DATA_USER_POINT_PERIODS_ALL_TIME)
        bucket = bucket_raw if isinstance(bucket_raw, dict) else {}
        entry_raw = bucket.get(const.PERIOD_ALL_TIME)
        entry = entry_raw if isinstance(entry_raw, dict) else {}

        earned = round(
            float(entry.get(const.DATA_USER_POINT_PERIOD_POINTS_EARNED, 0.0)),
            const.DATA_FLOAT_PRECISION,
        )
        spent = round(
            float(entry.get(const.DATA_USER_POINT_PERIOD_POINTS_SPENT, 0.0)),
            const.DATA_FLOAT_PRECISION,
        )
        highest = round(
            float(entry.get(const.DATA_USER_POINT_PERIOD_HIGHEST_BALANCE, 0.0)),
            const.DATA_FLOAT_PRECISION,
        )

        by_source: dict[str, float] = {}
        by_source_raw = entry.get(const.DATA_USER_POINT_PERIOD_BY_SOURCE)
        if isinstance(by_source_raw, dict):
            for source, value in by_source_raw.items():
                try:
                    by_source[str(source)] = round(
                        float(value), const.DATA_FLOAT_PRECISION
                    )
                except (TypeError, ValueError):
                    by_source[str(source)] = 0.0

        assignee_changed = False

        # 1) The ledger net must equal the current balance.
        gap = round(balance - (earned + spent), const.DATA_FLOAT_PRECISION)
        if gap > 0.0:
            earned = round(earned + gap, const.DATA_FLOAT_PRECISION)
        elif gap < 0.0:
            spent = round(spent + gap, const.DATA_FLOAT_PRECISION)
        if gap != 0.0:
            summary["ledger_gaps_folded"] += 1
            assignee_changed = True

        # 2) The by_source net must equal the ledger net.
        history_net = round(sum(by_source.values()), const.DATA_FLOAT_PRECISION)
        gap = round((earned + spent) - history_net, const.DATA_FLOAT_PRECISION)
        if gap != 0.0:
            by_source[const.POINTS_SOURCE_OTHER] = round(
                by_source.get(const.POINTS_SOURCE_OTHER, 0.0) + gap,
                const.DATA_FLOAT_PRECISION,
            )
            summary["history_nets_folded"] += 1
            assignee_changed = True

        # 3) Positive/negative history entries must match the earned/spent split.
        sign_status = _reconcile_by_source_signs(by_source, earned, spent)
        if sign_status == "repaired":
            summary["history_signs_fixed"] += 1
            assignee_changed = True
        elif sign_status == "deferred":
            summary["history_sign_fixes_deferred"] += 1

        # 4) highest_balance must cover the balance and the earned ledger.
        new_highest = round(max(highest, balance, earned), const.DATA_FLOAT_PRECISION)
        if new_highest != highest:
            highest = new_highest
            summary["highest_floored"] += 1
            assignee_changed = True

        if not assignee_changed:
            continue

        if not isinstance(periods_raw, dict):
            periods_raw = {}
            assignee[const.DATA_USER_POINT_PERIODS] = periods_raw
        target_bucket = periods_raw.setdefault(
            const.DATA_USER_POINT_PERIODS_ALL_TIME, {}
        )
        if not isinstance(target_bucket, dict):
            target_bucket = {}
            periods_raw[const.DATA_USER_POINT_PERIODS_ALL_TIME] = target_bucket
        target_entry = target_bucket.setdefault(const.PERIOD_ALL_TIME, {})
        if not isinstance(target_entry, dict):
            target_entry = {}
            target_bucket[const.PERIOD_ALL_TIME] = target_entry

        target_entry[const.DATA_USER_POINT_PERIOD_POINTS_EARNED] = earned
        target_entry[const.DATA_USER_POINT_PERIOD_POINTS_SPENT] = spent
        target_entry[const.DATA_USER_POINT_PERIOD_HIGHEST_BALANCE] = highest
        target_entry[const.DATA_USER_POINT_PERIOD_BY_SOURCE] = dict(by_source)
        summary["assignees_repaired"] += 1

    return summary
