"""Reporting helper functions for KidsChores services.

This module provides read-only data shaping for report and export services.
Service handlers should delegate heavy composition logic here and remain thin.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import UTC, date, datetime, time, timedelta
import html
from typing import TYPE_CHECKING, Any, cast
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from .. import const
from ..utils.dt_utils import dt_parse

if TYPE_CHECKING:
    from ..type_defs import ActivityReportResponse, ReportDailyBlock, ReportRangeResult


DEFAULT_REPORT_TRANSLATIONS: dict[str, str] = {
    "title_default": "🌈 Your KidsChores Weekly Highlights",
    "intro": "Hey {kid_heading}! Here is what you accomplished this period:",
    "section_big_picture": "## ✨ Big picture",
    "section_weekly_summary": "## 📊 Weekly summary",
    "section_highlights": "## 🌟 Highlights",
    "section_daily_activity": "## 📅 Daily activity",
    "range_label": "Range",
    "range_short": "{start_date} → {end_date}",
    "total_points_earned": "Total points earned",
    "total_points_spent": "Total points spent",
    "net_points_change": "Net points change",
    "total_activities": "Total activities",
    "completed_chores_week": "Completed chores this week",
    "avg_points_per_day": "Average points per day",
    "avg_chores_per_day": "Average chores per day",
    "badges_earned": "🏅 Badges earned",
    "badges_earned_none": "🏅 Badges earned: none this period",
    "bonus_points": "✨ Bonus points",
    "rewards_highlight": "🎁 Rewards",
    "daily_ledger": "Ledger detail",
    "best_day": "🏆 Best day: {date} (net {net} points)",
    "no_activity": "No activity found for the selected range.",
    "day_points_earned": "🌟 Points earned",
    "day_points_spent": "🎁 Points spent",
    "day_net_change": "📊 Net change",
    "day_activities": "✅ Activities",
    "footer": "Great effort this week — keep it up! 🎉",
    "automation_title": "# KidsChores Activity Report",
    "automation_summary": "## Summary",
    "automation_daily": "## Daily",
    "automation_no_activity": "- no_activity",
    "automation_kids": "kids",
    "automation_range_start": "range_start",
    "automation_range_end": "range_end",
    "automation_total_earned": "total_earned",
    "automation_total_spent": "total_spent",
    "automation_net": "net",
    "automation_transactions": "transactions",
}


def normalize_report_style(raw_style: Any) -> str:
    """Normalize report style input into a supported style value.

    Handles common UI/service-call shapes and falls back to kid style.
    """
    style_value: str
    if isinstance(raw_style, str):
        style_value = raw_style
    elif isinstance(raw_style, dict):
        style_value = str(raw_style.get("value", ""))
    elif isinstance(raw_style, list) and raw_style:
        style_value = str(raw_style[0])
    else:
        style_value = ""

    normalized = style_value.strip().lower()
    if normalized in {
        const.REPORT_STYLE_KID,
        const.REPORT_STYLE_AUTOMATION,
        const.REPORT_STYLE_BOTH,
    }:
        return normalized

    return const.REPORT_STYLE_KID


def normalize_report_range_mode(
    raw_mode: Any,
    start_date: str | datetime | None = None,
    end_date: str | datetime | None = None,
) -> str:
    """Normalize report range mode into a supported mode value.

    Handles common UI/service-call payload shapes and supports implicit custom
    mode when explicit start/end dates are provided.
    """
    mode_value: str
    if isinstance(raw_mode, str):
        mode_value = raw_mode
    elif isinstance(raw_mode, dict):
        mode_value = str(raw_mode.get("value", ""))
    elif isinstance(raw_mode, list) and raw_mode:
        mode_value = str(raw_mode[0])
    else:
        mode_value = ""

    normalized = mode_value.strip().lower()
    if normalized in {
        const.REPORT_RANGE_MODE_LAST_7_DAYS,
        const.REPORT_RANGE_MODE_LAST_30_DAYS,
        const.REPORT_RANGE_MODE_CUSTOM,
    }:
        return normalized

    if start_date is not None or end_date is not None:
        return const.REPORT_RANGE_MODE_CUSTOM

    return const.REPORT_RANGE_MODE_LAST_7_DAYS


def resolve_report_range(
    mode: str,
    start_date: str | datetime | None,
    end_date: str | datetime | None,
    timezone_name: str = "UTC",
    now_utc: datetime | None = None,
) -> ReportRangeResult:
    """Resolve report range into timezone-aware ISO boundaries.

    Args:
        mode: Range mode (`last_7_days`, `last_30_days`, `custom`)
        start_date: Optional custom start date
        end_date: Optional custom end date
        timezone_name: Timezone label for response metadata
        now_utc: Optional override for deterministic tests

    Returns:
        Resolved range metadata including mode and ISO boundaries
    """
    now = now_utc or datetime.now(UTC)

    start_dt: datetime | None
    end_dt: datetime | None

    if mode == const.REPORT_RANGE_MODE_LAST_7_DAYS:
        start_dt = now - timedelta(days=7)
        end_dt = now
    elif mode == const.REPORT_RANGE_MODE_LAST_30_DAYS:
        start_dt = now - timedelta(days=30)
        end_dt = now
    else:
        start_dt = _coerce_datetime(start_date)
        end_dt = _coerce_datetime(end_date)
        if start_dt is None or end_dt is None:
            raise ValueError("Custom report range requires start_date and end_date")

    if start_dt.tzinfo is None:
        start_dt = start_dt.replace(tzinfo=UTC)
    if end_dt.tzinfo is None:
        end_dt = end_dt.replace(tzinfo=UTC)

    return {
        "mode": mode,
        "start_iso": start_dt.isoformat(),
        "end_iso": end_dt.isoformat(),
        "timezone": timezone_name,
    }


def build_activity_report(
    kids_data: dict[str, Any],
    range_result: ReportRangeResult,
    kid_id: str | None = None,
    report_title: str | None = None,
    report_style: str = const.REPORT_STYLE_KID,
    stats_manager: Any | None = None,
    report_translations: dict[str, str] | None = None,
    include_supplemental: bool = True,
) -> ActivityReportResponse:
    """Build a markdown activity report from ledger data.

    This is a read-only projection and does not mutate coordinator storage.
    """
    start_dt = _coerce_datetime(range_result["start_iso"])
    end_dt = _coerce_datetime(range_result["end_iso"])
    if start_dt is None or end_dt is None:
        raise ValueError("Invalid report range")
    local_tz = _resolve_timezone(range_result.get("timezone", "UTC"))

    kid_ids = [kid_id] if kid_id else list(kids_data.keys())
    kid_names = [
        str(
            kids_data.get(candidate_kid_id, {}).get(
                const.DATA_KID_NAME, candidate_kid_id
            )
        )
        for candidate_kid_id in kid_ids
    ]
    single_kid_scope = len(kid_ids) == 1

    daily_aggregate: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "earned": 0.0,
            "spent": 0.0,
            "transactions": 0,
            "events": [],
        }
    )

    total_earned = 0.0
    total_spent = 0.0
    transactions_count = 0

    for candidate_kid_id in kid_ids:
        kid_info = kids_data.get(candidate_kid_id, {})
        kid_name = str(kid_info.get(const.DATA_KID_NAME, candidate_kid_id))
        for entry in _iter_ledger_entries_in_range(kid_info, start_dt, end_dt):
            amount = float(entry.get(const.DATA_LEDGER_AMOUNT, 0.0))
            timestamp = str(entry.get(const.DATA_LEDGER_TIMESTAMP, ""))
            parsed_timestamp = _coerce_datetime(timestamp)
            if parsed_timestamp is None:
                continue

            day = parsed_timestamp.astimezone(local_tz).strftime("%Y-%m-%d")

            if amount >= 0:
                total_earned += amount
                daily_aggregate[day]["earned"] = (
                    float(daily_aggregate[day]["earned"]) + amount
                )
            else:
                spent = abs(amount)
                total_spent += spent
                daily_aggregate[day]["spent"] = (
                    float(daily_aggregate[day]["spent"]) + spent
                )

            daily_aggregate[day]["transactions"] = (
                int(daily_aggregate[day]["transactions"]) + 1
            )
            daily_aggregate[day]["events"].append(
                _format_ledger_event_line(
                    entry,
                    kid_name=kid_name,
                    single_kid_scope=single_kid_scope,
                    timezone=local_tz,
                )
            )
            transactions_count += 1

    daily_blocks: list[ReportDailyBlock] = []
    for day in sorted(daily_aggregate.keys(), reverse=True):
        earned = round(
            float(daily_aggregate[day]["earned"]), const.DATA_FLOAT_PRECISION
        )
        spent = round(float(daily_aggregate[day]["spent"]), const.DATA_FLOAT_PRECISION)
        net = round(earned - spent, const.DATA_FLOAT_PRECISION)
        tx_count = int(daily_aggregate[day]["transactions"])
        event_lines = cast("list[str]", daily_aggregate[day]["events"])
        event_markdown = "\n".join(f"- {event_line}" for event_line in event_lines)

        daily_blocks.append(
            {
                "date": day,
                "earned": earned,
                "spent": spent,
                "net": net,
                "transactions": tx_count,
                "markdown_section": (
                    f"### {day}\n"
                    f"- 🌟 Points earned: {earned}\n"
                    f"- 🎁 Points spent: {spent}\n"
                    f"- 📊 Net change: {net}\n"
                    f"- ✅ Activities: {tx_count}\n"
                    f"- 🧾 Ledger detail:\n"
                    f"{event_markdown}"
                ),
            }
        )

    supplemental_rollup = _build_supplemental_period_rollup(
        kids_data,
        kid_ids,
        start_iso=range_result["start_iso"],
        end_iso=range_result["end_iso"],
        stats_manager=stats_manager,
    )
    start_local_date = start_dt.astimezone(local_tz).date()
    end_local_date = end_dt.astimezone(local_tz).date()
    badge_highlights = _build_badge_highlights_from_kids_data(
        kids_data,
        kid_ids,
        start_local_date,
        end_local_date,
    )
    badges_rollup = cast("dict[str, Any]", supplemental_rollup.setdefault("badges", {}))
    badges_rollup["highlights"] = badge_highlights

    day_span = max(
        1, int((end_dt.astimezone(local_tz) - start_dt.astimezone(local_tz)).days)
    )
    markdown = _render_report_markdown(
        report_title=report_title,
        range_result=range_result,
        daily_blocks=daily_blocks,
        kid_names=kid_names,
        report_style=report_style,
        report_translations=report_translations,
        supplemental=supplemental_rollup,
        summary={
            "total_earned": round(total_earned, const.DATA_FLOAT_PRECISION),
            "total_spent": round(total_spent, const.DATA_FLOAT_PRECISION),
            "net": round(total_earned - total_spent, const.DATA_FLOAT_PRECISION),
            "transactions_count": transactions_count,
            "days_count": day_span,
        },
    )

    supplemental = supplemental_rollup if include_supplemental else {}

    return {
        "range": range_result,
        "scope": {
            "kid_filter_applied": kid_id is not None,
            "kid_ids": kid_ids,
        },
        "summary": {
            "total_earned": round(total_earned, const.DATA_FLOAT_PRECISION),
            "total_spent": round(total_spent, const.DATA_FLOAT_PRECISION),
            "net": round(total_earned - total_spent, const.DATA_FLOAT_PRECISION),
            "transactions_count": transactions_count,
        },
        "daily": daily_blocks,
        "markdown": markdown,
        "supplemental": supplemental,
        "delivery": {
            "notify_attempted": False,
            "notify_service": None,
            "delivered": False,
        },
    }


def convert_markdown_to_html(markdown_text: str) -> str:
    """Convert report markdown to simple HTML for email delivery.

    This converter intentionally supports the markdown constructs generated by
    this module (headings, bullets, separators, and paragraphs).
    """
    lines = markdown_text.splitlines()
    html_lines: list[str] = []
    in_list = False

    for raw_line in lines:
        line = raw_line.strip()

        if line == "":
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            continue

        if line == "---":
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append("<hr />")
            continue

        if line.startswith("### "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h3>{html.escape(line[4:])}</h3>")
            continue

        if line.startswith("## "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h2>{html.escape(line[3:])}</h2>")
            continue

        if line.startswith("# "):
            if in_list:
                html_lines.append("</ul>")
                in_list = False
            html_lines.append(f"<h1>{html.escape(line[2:])}</h1>")
            continue

        if line.startswith("- "):
            if not in_list:
                html_lines.append("<ul>")
                in_list = True
            html_lines.append(f"<li>{html.escape(line[2:])}</li>")
            continue

        if in_list:
            html_lines.append("</ul>")
            in_list = False

        html_lines.append(f"<p>{html.escape(line)}</p>")

    if in_list:
        html_lines.append("</ul>")

    return "\n".join(html_lines)


def _iter_ledger_entries_in_range(
    kid_info: dict[str, Any],
    start_dt: datetime,
    end_dt: datetime,
) -> list[dict[str, Any]]:
    """Return ledger entries for a kid in the requested datetime range."""
    ledger = kid_info.get(const.DATA_KID_LEDGER, [])
    if not isinstance(ledger, list):
        return []

    entries: list[dict[str, Any]] = []
    for raw_entry in ledger:
        if not isinstance(raw_entry, dict):
            continue

        timestamp = raw_entry.get(const.DATA_LEDGER_TIMESTAMP)
        parsed = _coerce_datetime(timestamp)
        if parsed is None:
            continue

        if start_dt <= parsed <= end_dt:
            entries.append(raw_entry)

    entries.sort(key=lambda entry: str(entry.get(const.DATA_LEDGER_TIMESTAMP, "")))
    return entries


def _build_supplemental_period_rollup(
    kids_data: dict[str, Any],
    kid_ids: list[str],
    start_iso: str,
    end_iso: str,
    stats_manager: Any | None,
) -> dict[str, Any]:
    """Build supplemental rollup from canonical StatisticsManager queries."""
    if stats_manager is None:
        raise ValueError("stats_manager is required for report supplemental rollups")

    total_points_earned = 0.0
    total_points_spent = 0.0

    total_chores_approved = 0
    total_chores_claimed = 0
    total_chores_disapproved = 0
    total_chores_missed = 0
    total_chores_overdue = 0
    in_range_chores_approved = 0
    in_range_chores_claimed = 0
    in_range_chores_disapproved = 0
    in_range_chores_missed = 0
    in_range_chores_overdue = 0

    total_rewards_approved = 0
    total_rewards_claimed = 0
    total_rewards_disapproved = 0
    total_rewards_points_spent = 0.0
    in_range_rewards_approved = 0
    in_range_rewards_claimed = 0
    in_range_rewards_disapproved = 0
    in_range_rewards_points_spent = 0.0
    total_bonus_applies = 0
    total_bonus_points = 0.0
    in_range_bonus_applies = 0
    in_range_bonus_points = 0.0
    total_penalty_applies = 0
    total_penalty_points = 0.0
    in_range_penalty_applies = 0
    in_range_penalty_points = 0.0

    highest_current_streak = 0
    highest_current_missed_streak = 0
    highest_longest_streak = 0
    highest_longest_missed_streak = 0
    total_badges_earned = 0
    total_badge_awards = 0
    earned_badge_names: set[str] = set()
    all_badges_by_id: dict[str, dict[str, Any]] = {}
    kid_breakdown: list[dict[str, Any]] = []

    for kid_id in kid_ids:
        kid_info = kids_data.get(kid_id, {})
        manager_rollup = cast(
            "dict[str, Any]",
            stats_manager.get_report_rollup(kid_id, start_iso, end_iso),
        )
        points_rollup = cast("dict[str, Any]", manager_rollup.get("points", {}))
        chores_rollup = cast("dict[str, Any]", manager_rollup.get("chores", {}))
        rewards_rollup = cast("dict[str, Any]", manager_rollup.get("rewards", {}))
        bonuses_rollup = cast("dict[str, Any]", manager_rollup.get("bonuses", {}))
        penalties_rollup = cast("dict[str, Any]", manager_rollup.get("penalties", {}))
        streaks = cast("dict[str, int]", manager_rollup.get("streaks", {}))
        badges = cast("dict[str, Any]", manager_rollup.get("badges", {}))

        total_points_earned += float(points_rollup.get("all_time_earned", 0.0))
        total_points_spent += float(points_rollup.get("all_time_spent", 0.0))
        total_chores_approved += int(chores_rollup.get("all_time_approved", 0))
        total_chores_claimed += int(chores_rollup.get("all_time_claimed", 0))
        total_chores_disapproved += int(chores_rollup.get("all_time_disapproved", 0))
        total_chores_missed += int(chores_rollup.get("all_time_missed", 0))
        total_chores_overdue += int(chores_rollup.get("all_time_overdue", 0))
        in_range_chores_approved += int(chores_rollup.get("in_range_approved", 0))
        in_range_chores_claimed += int(chores_rollup.get("in_range_claimed", 0))
        in_range_chores_disapproved += int(chores_rollup.get("in_range_disapproved", 0))
        in_range_chores_missed += int(chores_rollup.get("in_range_missed", 0))
        in_range_chores_overdue += int(chores_rollup.get("in_range_overdue", 0))
        total_rewards_approved += int(rewards_rollup.get("all_time_approved", 0))
        total_rewards_claimed += int(rewards_rollup.get("all_time_claimed", 0))
        total_rewards_disapproved += int(rewards_rollup.get("all_time_disapproved", 0))
        total_rewards_points_spent += float(
            rewards_rollup.get("all_time_points_spent", 0.0)
        )
        in_range_rewards_approved += int(rewards_rollup.get("in_range_approved", 0))
        in_range_rewards_claimed += int(rewards_rollup.get("in_range_claimed", 0))
        in_range_rewards_disapproved += int(
            rewards_rollup.get("in_range_disapproved", 0)
        )
        in_range_rewards_points_spent += float(
            rewards_rollup.get("in_range_points_spent", 0.0)
        )
        total_bonus_applies += int(bonuses_rollup.get("all_time_applies", 0))
        total_bonus_points += float(bonuses_rollup.get("all_time_points", 0.0))
        in_range_bonus_applies += int(bonuses_rollup.get("in_range_applies", 0))
        in_range_bonus_points += float(bonuses_rollup.get("in_range_points", 0.0))
        total_penalty_applies += int(penalties_rollup.get("all_time_applies", 0))
        total_penalty_points += float(penalties_rollup.get("all_time_points", 0.0))
        in_range_penalty_applies += int(penalties_rollup.get("in_range_applies", 0))
        in_range_penalty_points += float(penalties_rollup.get("in_range_points", 0.0))

        highest_current_streak = max(highest_current_streak, streaks["current_streak"])
        highest_current_missed_streak = max(
            highest_current_missed_streak,
            streaks["current_missed_streak"],
        )
        highest_longest_streak = max(
            highest_longest_streak,
            streaks["all_time_longest_streak"],
        )
        highest_longest_missed_streak = max(
            highest_longest_missed_streak,
            streaks["all_time_longest_missed_streak"],
        )

        total_badges_earned += badges["earned_unique_count"]
        total_badge_awards += badges["all_time_award_count"]
        earned_badge_names.update(badges["earned_badge_names"])
        for badge_id, badge_info in cast(
            "dict[str, dict[str, Any]]",
            badges.get("by_badge", {}),
        ).items():
            if badge_id not in all_badges_by_id:
                all_badges_by_id[badge_id] = dict(badge_info)
                all_badges_by_id[badge_id]["kid_ids"] = [kid_id]
                continue

            existing_badge = all_badges_by_id[badge_id]
            existing_badge["all_time_award_count"] = int(
                existing_badge.get("all_time_award_count", 0)
            ) + int(badge_info.get("all_time_award_count", 0))
            kid_ids = cast("list[str]", existing_badge.get("kid_ids", []))
            if kid_id not in kid_ids:
                kid_ids.append(kid_id)
                existing_badge["kid_ids"] = kid_ids

        kid_breakdown.append(
            {
                "kid_id": kid_id,
                "kid_name": str(kid_info.get(const.DATA_KID_NAME, kid_id)),
                "streaks": streaks,
                "badges": badges,
            }
        )

    return {
        "points": {
            "all_time_earned": round(total_points_earned, const.DATA_FLOAT_PRECISION),
            "all_time_spent": round(total_points_spent, const.DATA_FLOAT_PRECISION),
            "all_time_net": round(
                total_points_earned - total_points_spent,
                const.DATA_FLOAT_PRECISION,
            ),
        },
        "chores": {
            "in_range_approved": in_range_chores_approved,
            "in_range_claimed": in_range_chores_claimed,
            "in_range_disapproved": in_range_chores_disapproved,
            "in_range_missed": in_range_chores_missed,
            "in_range_overdue": in_range_chores_overdue,
            "all_time_approved": total_chores_approved,
            "all_time_claimed": total_chores_claimed,
            "all_time_disapproved": total_chores_disapproved,
            "all_time_missed": total_chores_missed,
            "all_time_overdue": total_chores_overdue,
        },
        "rewards": {
            "in_range_approved": in_range_rewards_approved,
            "in_range_claimed": in_range_rewards_claimed,
            "in_range_disapproved": in_range_rewards_disapproved,
            "in_range_points_spent": round(
                in_range_rewards_points_spent,
                const.DATA_FLOAT_PRECISION,
            ),
            "all_time_approved": total_rewards_approved,
            "all_time_claimed": total_rewards_claimed,
            "all_time_disapproved": total_rewards_disapproved,
            "all_time_points_spent": round(
                total_rewards_points_spent,
                const.DATA_FLOAT_PRECISION,
            ),
        },
        "bonuses": {
            "in_range_applies": in_range_bonus_applies,
            "in_range_points": round(
                in_range_bonus_points,
                const.DATA_FLOAT_PRECISION,
            ),
            "all_time_applies": total_bonus_applies,
            "all_time_points": round(total_bonus_points, const.DATA_FLOAT_PRECISION),
        },
        "penalties": {
            "in_range_applies": in_range_penalty_applies,
            "in_range_points": round(
                in_range_penalty_points,
                const.DATA_FLOAT_PRECISION,
            ),
            "all_time_applies": total_penalty_applies,
            "all_time_points": round(
                total_penalty_points,
                const.DATA_FLOAT_PRECISION,
            ),
        },
        "streaks": {
            "current_streak": highest_current_streak,
            "current_missed_streak": highest_current_missed_streak,
            "all_time_longest_streak": highest_longest_streak,
            "all_time_longest_missed_streak": highest_longest_missed_streak,
        },
        "badges": {
            "earned_unique_count": total_badges_earned,
            "all_time_award_count": total_badge_awards,
            "earned_badge_names": sorted(earned_badge_names),
            "by_badge": all_badges_by_id,
        },
        "kids": kid_breakdown,
    }


def _coerce_datetime(value: str | datetime | None) -> datetime | None:
    """Coerce datetime-like values to timezone-aware UTC datetimes."""
    result: datetime | None = None

    if value is None:
        return result

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)

    parsed = dt_parse(value)
    if isinstance(parsed, datetime):
        result = parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    elif isinstance(parsed, date):
        result = datetime.combine(parsed, time.min, tzinfo=UTC)

    return result


def _render_report_markdown(
    report_title: str | None,
    range_result: ReportRangeResult,
    daily_blocks: list[ReportDailyBlock],
    kid_names: list[str],
    report_style: str,
    report_translations: dict[str, str] | None,
    summary: dict[str, float | int],
    supplemental: dict[str, Any],
) -> str:
    """Render markdown report from daily aggregate blocks using selected style."""
    translations = _resolve_report_translations(report_translations)

    if report_style == const.REPORT_STYLE_AUTOMATION:
        return _render_automation_markdown(
            range_result,
            daily_blocks,
            kid_names,
            summary,
            translations,
        )

    if report_style == const.REPORT_STYLE_BOTH:
        kid_section = _render_kid_markdown(
            report_title=report_title,
            range_result=range_result,
            daily_blocks=daily_blocks,
            kid_names=kid_names,
            translations=translations,
            summary=summary,
            supplemental=supplemental,
        )
        automation_section = _render_automation_markdown(
            range_result,
            daily_blocks,
            kid_names,
            summary,
            translations,
        )
        return f"{kid_section}\n\n---\n\n{automation_section}".strip()

    return _render_kid_markdown(
        report_title=report_title,
        range_result=range_result,
        daily_blocks=daily_blocks,
        kid_names=kid_names,
        translations=translations,
        summary=summary,
        supplemental=supplemental,
    )


def _render_kid_markdown(
    report_title: str | None,
    range_result: ReportRangeResult,
    daily_blocks: list[ReportDailyBlock],
    kid_names: list[str],
    translations: dict[str, str],
    summary: dict[str, float | int],
    supplemental: dict[str, Any],
) -> str:
    """Render kid-friendly markdown report."""
    title = report_title or translations["title_default"]
    kid_heading = "Family"
    if len(kid_names) == 1:
        kid_heading = kid_names[0]
    elif kid_names:
        kid_heading = ", ".join(kid_names)

    total_earned = float(summary.get("total_earned", 0.0))
    total_spent = float(summary.get("total_spent", 0.0))
    net = float(summary.get("net", 0.0))
    tx_count = int(summary.get("transactions_count", 0))
    days_count = int(summary.get("days_count", 7))

    chores_rollup = cast("dict[str, Any]", supplemental.get("chores", {}))
    bonuses_rollup = cast("dict[str, Any]", supplemental.get("bonuses", {}))
    rewards_rollup = cast("dict[str, Any]", supplemental.get("rewards", {}))
    badges_rollup = cast("dict[str, Any]", supplemental.get("badges", {}))

    completed_chores = int(
        chores_rollup.get(
            "in_range_approved",
            chores_rollup.get("all_time_approved", 0),
        )
    )
    avg_points_per_day = round(net / max(1, days_count), const.DATA_FLOAT_PRECISION)
    avg_chores_per_day = round(
        completed_chores / max(1, days_count),
        const.DATA_FLOAT_PRECISION,
    )

    local_tz = _resolve_timezone(range_result.get("timezone", "UTC"))
    start_short = _to_local_short_date(range_result["start_iso"], local_tz)
    end_short = _to_local_short_date(range_result["end_iso"], local_tz)

    raw_highlights = badges_rollup.get("highlights", [])
    badges_highlights = (
        cast("list[str]", raw_highlights) if isinstance(raw_highlights, list) else []
    )
    badge_lines: list[str] = [f"- {translations['badges_earned_none']}"]
    if badges_highlights:
        badge_lines = [f"- {translations['badges_earned']}:"] + [
            f"  - {badge_item}" for badge_item in badges_highlights
        ]

    bonus_points = round(
        float(
            bonuses_rollup.get(
                "in_range_points",
                bonuses_rollup.get("all_time_points", 0.0),
            )
        ),
        const.DATA_FLOAT_PRECISION,
    )
    rewards_claimed = int(
        rewards_rollup.get(
            "in_range_claimed",
            rewards_rollup.get("all_time_claimed", 0),
        )
    )
    rewards_spent = round(
        float(
            rewards_rollup.get(
                "in_range_points_spent",
                rewards_rollup.get("all_time_points_spent", 0.0),
            )
        ),
        const.DATA_FLOAT_PRECISION,
    )

    best_day_line = ""
    if daily_blocks:
        best_day = max(daily_blocks, key=lambda block: float(block["net"]))
        best_day_line = translations["best_day"].format(
            date=best_day["date"],
            net=best_day["net"],
        )

    lines = [
        f"# {title}",
        translations["intro"].format(kid_heading=kid_heading),
        translations["section_weekly_summary"],
        f"- {translations['range_label']}: "
        f"{translations['range_short'].format(start_date=start_short, end_date=end_short)}",
        f"- {translations['completed_chores_week']}: {completed_chores}",
        f"- {translations['avg_points_per_day']}: {avg_points_per_day}",
        f"- {translations['avg_chores_per_day']}: {avg_chores_per_day}",
        translations["section_highlights"],
        f"- {translations['total_points_earned']}: {total_earned}",
        f"- {translations['total_points_spent']}: {total_spent}",
        f"- {translations['net_points_change']}: {net}",
        f"- {translations['total_activities']}: {tx_count}",
        f"- {translations['bonus_points']}: {bonus_points}",
        *badge_lines,
        (
            f"- {translations['rewards_highlight']}: "
            f"claimed={rewards_claimed}, spent={rewards_spent}"
        ),
        best_day_line,
        translations["section_daily_activity"],
        f"{translations['range_label']}: "
        f"{translations['range_short'].format(start_date=start_short, end_date=end_short)}",
    ]

    if not daily_blocks:
        lines.append(translations["no_activity"])
        return "\n".join(lines)

    for block in daily_blocks:
        lines.append(_render_daily_block(block, translations))

    lines.append(translations["footer"])

    return "\n".join(lines).strip()


def _render_automation_markdown(
    range_result: ReportRangeResult,
    daily_blocks: list[ReportDailyBlock],
    kid_names: list[str],
    summary: dict[str, float | int],
    translations: dict[str, str],
) -> str:
    """Render compact automation-oriented markdown summary."""
    kids_label = "all_kids" if not kid_names else ", ".join(kid_names)

    lines = [
        translations["automation_title"],
        "",
        translations["automation_summary"],
        f"- {translations['automation_kids']}: {kids_label}",
        f"- {translations['automation_range_start']}: {range_result['start_iso']}",
        f"- {translations['automation_range_end']}: {range_result['end_iso']}",
        f"- {translations['automation_total_earned']}: {round(float(summary.get('total_earned', 0.0)), const.DATA_FLOAT_PRECISION)}",
        f"- {translations['automation_total_spent']}: {round(float(summary.get('total_spent', 0.0)), const.DATA_FLOAT_PRECISION)}",
        f"- {translations['automation_net']}: {round(float(summary.get('net', 0.0)), const.DATA_FLOAT_PRECISION)}",
        f"- {translations['automation_transactions']}: {int(summary.get('transactions_count', 0))}",
        "",
        translations["automation_daily"],
    ]

    if not daily_blocks:
        lines.append(translations["automation_no_activity"])
        return "\n".join(lines)

    for block in daily_blocks:
        lines.append(
            "- "
            f"date={block['date']} "
            f"earned={block['earned']} "
            f"spent={block['spent']} "
            f"net={block['net']} "
            f"tx={block['transactions']}"
        )

    return "\n".join(lines)


def _resolve_report_translations(
    report_translations: dict[str, str] | None,
) -> dict[str, str]:
    """Merge report translation overrides with English defaults."""
    translations = dict(DEFAULT_REPORT_TRANSLATIONS)
    if isinstance(report_translations, dict):
        translations.update(
            {
                key: value
                for key, value in report_translations.items()
                if isinstance(value, str) and value
            }
        )
    return translations


def _render_daily_block(
    block: ReportDailyBlock,
    translations: dict[str, str],
) -> str:
    """Render one daily block using translated labels."""
    section = block.get("markdown_section")
    if isinstance(section, str) and section:
        return section

    return (
        f"### {block['date']}\n"
        f"- {translations['day_points_earned']}: {block['earned']}\n"
        f"- {translations['day_points_spent']}: {block['spent']}\n"
        f"- {translations['day_net_change']}: {block['net']}\n"
        f"- {translations['day_activities']}: {block['transactions']}"
    )


def _format_ledger_event_line(
    entry: dict[str, Any],
    kid_name: str,
    single_kid_scope: bool,
    timezone: ZoneInfo,
) -> str:
    """Format one ledger entry into a kid-friendly markdown bullet line."""
    amount = float(entry.get(const.DATA_LEDGER_AMOUNT, 0.0))
    source = str(entry.get(const.DATA_LEDGER_SOURCE, const.POINTS_SOURCE_OTHER))
    item_name = str(entry.get(const.DATA_LEDGER_ITEM_NAME, "Activity")).strip()
    timestamp = str(entry.get(const.DATA_LEDGER_TIMESTAMP, ""))

    source_label_map = {
        const.POINTS_SOURCE_CHORES: "Chore",
        const.POINTS_SOURCE_REWARDS: "Reward",
        const.POINTS_SOURCE_BONUSES: "Bonus",
        const.POINTS_SOURCE_PENALTIES: "Penalty",
        const.POINTS_SOURCE_BADGES: "Badge",
        const.POINTS_SOURCE_ACHIEVEMENTS: "Achievement",
        const.POINTS_SOURCE_CHALLENGES: "Challenge",
        const.POINTS_SOURCE_MANUAL: "Adjustment",
        const.POINTS_SOURCE_OTHER: "Activity",
    }
    source_label = source_label_map.get(source, "Activity")

    icon = "✅" if amount >= 0 else "🧾"
    signed_amount = (
        f"+{round(amount, const.DATA_FLOAT_PRECISION)}"
        if amount >= 0
        else f"-{round(abs(amount), const.DATA_FLOAT_PRECISION)}"
    )

    parsed_time = _coerce_datetime(timestamp)
    time_label = ""
    if parsed_time is not None:
        time_label = parsed_time.astimezone(timezone).strftime("%H:%M")

    name_prefix = "" if single_kid_scope else f"{kid_name}: "
    if time_label:
        return f"{icon} {name_prefix}{time_label} — {source_label}: {item_name} ({signed_amount} pts)"
    return f"{icon} {name_prefix}{source_label}: {item_name} ({signed_amount} pts)"


def _resolve_timezone(timezone_name: str) -> ZoneInfo:
    """Resolve timezone name with UTC fallback."""
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return ZoneInfo("UTC")


def _to_local_short_date(value: str, timezone: ZoneInfo) -> str:
    """Convert an ISO datetime string to local short date YYYY-MM-DD."""
    parsed = _coerce_datetime(value)
    if parsed is None:
        return value[: const.ISO_DATE_STRING_LENGTH]
    return parsed.astimezone(timezone).strftime("%Y-%m-%d")


def _build_badge_highlights_from_kids_data(
    kids_data: dict[str, Any],
    kid_ids: list[str],
    start_local_date: date,
    end_local_date: date,
) -> list[str]:
    """Build badge highlight lines from kid badge records using local date buckets."""
    single_kid_scope = len(kid_ids) == 1
    lines: list[str] = []
    for kid_id in kid_ids:
        kid_info = cast("dict[str, Any]", kids_data.get(kid_id, {}))
        kid_name = str(kid_info.get(const.DATA_KID_NAME, kid_id))
        badges_earned = cast(
            "dict[str, dict[str, Any]]",
            kid_info.get(const.DATA_KID_BADGES_EARNED, {}),
        )

        for badge_info in badges_earned.values():
            badge_name = str(badge_info.get(const.DATA_KID_BADGES_EARNED_NAME, "Badge"))
            last_awarded = cast(
                "str | None",
                badge_info.get(const.DATA_KID_BADGES_EARNED_LAST_AWARDED),
            )
            if not last_awarded:
                continue

            parsed_awarded = dt_parse(last_awarded)
            if isinstance(parsed_awarded, datetime):
                awarded_date = parsed_awarded.date()
            elif isinstance(parsed_awarded, date):
                awarded_date = parsed_awarded
            else:
                continue

            if awarded_date < start_local_date or awarded_date > end_local_date:
                continue

            if single_kid_scope:
                lines.append(f"{badge_name} ({awarded_date.isoformat()})")
            else:
                lines.append(f"{kid_name}: {badge_name} ({awarded_date.isoformat()})")

    lines.sort()
    return lines
